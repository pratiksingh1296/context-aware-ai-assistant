# ==============================================================================
# IMPORTS & DATABASE INITIALIZATION
# ==============================================================================

import chromadb
import uuid
import time
import re
import json

from llm import get_llm
from utils import debug_print

'''
# To use different embedding function :

from chromadb.utils import embedding_functions

embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

'''

# Initialize a persistent local vector database directory.
# This creates a folder named './memory_store' to save data permanently across restarts
client = chromadb.PersistentClient(path="./memory_store")

# Create or connect to an existing vector database table (Collection).
collection = client.get_or_create_collection(name="chat_memory")

# New facts collection — stores extracted personal facts per user
facts_collection = client.get_or_create_collection(name="user_facts")

# ==============================================================================
# CORE MEMORY FUNCTIONS
# ==============================================================================

def add_to_memory(user_id: str, text: str, session_id: str):
    """
    Splits long conversational text blocks into logical atomic chunks,
    generates vector embeddings automatically, and saves them into ChromaDB.
    """

    # Split incoming text by punctuation marks (. ! ?) or line breaks to isolate sentences
    chunks = re.split(r"[.!?\n]+", text)

    for chunk in chunks:
        chunk = chunk.strip()

        # Content Guard: Avoid cluttering the database with empty words or short fillers
        if len(chunk) >= 10: # Only store chunks that are reasonably long
            debug_print(f"ADDING MEMORY: {chunk}")
            collection.add(
                documents=[chunk],
                metadatas=[{
                    "user_id": user_id,
                    "session_id": session_id,
                    "timestamp": time.time()
                }],
                # ChromaDB requires a string-formatted globally unique ID for every single document
                ids=[str(uuid.uuid4())]
            )
    debug_print("COLLECTION COUNT:", collection.count())


def retrieve_memory(user_id: str, query: str, limit: int = 10, threshold: float = 1.2)-> list:
    """
    Queries ChromaDB vector space using semantic search.
    Filters out irrelevant noise using an L2 Distance similarity cap.
    """
    # Perform semantic query filtered strictly to the requesting user's ID
    results = collection.query(
        query_texts=[query], 
        n_results=limit,
        where={"user_id": user_id}
    )
    debug_print(results)

    # Defensive Guard: Gracefully exit if database returns empty or missing dictionary payload keys
    if not results['documents'] or not results['documents'][0]:
        debug_print("DEBUG: No matching documents found in vector database.")
        return []
        
    documents = results['documents'][0]
    # Fallback to empty list if distances are omitted by ChromaDB engine configuration
    distances = results.get('distances', [[]])[0] if results.get('distances') else [0.0] * len(documents)
    debug_print("\n--- CHROMADB SEARCH DEBUG ---")
    debug_print("MATCHED DOCS:", documents)
    debug_print("L2 DISTANCES:", distances)
    debug_print("-----------------------------\n")

    # Vector Distance Filter (L2 Score): Keep matches closer than our threshold
    # Lower distance scale limits mean tighter contextual relevance matches.
    filtered = [doc for doc, dist in zip(documents, distances) if dist < threshold]
    debug_print("FILTERED MEMORIES:", filtered)
    return filtered


# ==============================================================================
# FACT EXTRACTION & STORAGE
# ==============================================================================

def extract_and_store_facts(user_id: str, user_message: str, session_id: str):
    """
    Uses the LLM to detect whether the user's message contains a personal fact
    worth remembering. If a fact is found and is not already stored, saves it
    to the dedicated facts collection in ChromaDB.

    Only stores facts from user messages — not agent responses.
    Skips storage if a semantically similar fact already exists (deduplication).
    """

    llm = get_llm()

    extraction_prompt = f"""

    You are a precise user-profile extraction assistant. Your job is to identify if the user's message contains long-term personal facts about themselves.

    Store personal facts that are either:
    - stable for months or years
    OR 
    - important ongoing goals likely to remain relevant across future conversations.

    Valid facts include:
    - Name
    - Location
    - Occupation
    - Long-term goals
    - Hobbies and interests
    - Strong preferences (favourite foods, sports, technologies, etc.)



    CRITICAL RULES:
    - Always write the "fact" value as a full sentence in third person, starting with "The user..."
    - Never infer facts that are not explicitly stated
    - Only extract information directly present in the user message
    - Do NOT store:
        - Temporary plans for the next few days
        - Current mood or emotions
        - Questions
        - One-time events
        - Small talk

    Valid categories: profile | interest | location | goal | occupation

    Examples:
    - "I'm Pratik by the way"         -> {{"fact": "The user's name is Pratik", "category": "profile"}}
    - "I love playing football"       -> {{"fact": "The user loves playing football", "category": "interest"}}
    - "I live in Navi Mumbai"         -> {{"fact": "The user lives in Navi Mumbai", "category": "location"}}
    - "I am preparing for DS interviews" -> {{"fact": "The user is preparing for Data Science interviews", "category": "goal"}}
    - "I work as a data analyst"      -> {{"fact": "The user works as a Data Analyst", "category": "occupation"}}

    User message: "{user_message}"

    If one or more long-term personal facts are present, respond with ONLY this JSON structure:
    {{
    "facts": [
        {{"fact": "The user...", "category": "profile/interest/location/goal/occupation"}},
        {{"fact": "The user...", "category": "profile/interest/location/goal/occupation"}}
        ]
    }}

    If no long-term personal fact is found, respond with ONLY:
    {{"facts": []}}

    Do not include markdown, code block wrappers, or any explanation. Return pure JSON only.

"""

    try:
        raw = llm.invoke(extraction_prompt).content.strip()
        debug_print("FACT EXTRACTION RAW:", raw)

        raw = re.sub(r"```json|```", "", raw).strip()

        parsed = json.loads(raw)
        extracted_facts = parsed.get("facts", [])
        debug_print(f"EXTRACTED {len(extracted_facts)} FACT(S)"
)

    except(json.JSONDecodeError, Exception) as e:
        debug_print("FACT EXTRACTION ERROR:", e)
        return  # Silently skip — never break the main chat flow
    
    if not extracted_facts:
        debug_print("No personal facts detected in message.")
        return

    stored_count = 0
    # Process each extracted fact independently
    for item in extracted_facts:
        fact_text = item.get("fact", "").strip()
        category = item.get("category", "general").strip()

        if not fact_text or fact_text.lower() in ["null", "none", ""]:
            continue
        
        debug_print(f"EXTRACTED FACT: {fact_text} | CATEGORY: {category}")

        # Handling duplicates, deduplicating against existing facts
        try: 
            existing = facts_collection.query(
                query_texts=[fact_text],
                n_results= 3,
                where={"user_id": user_id}
            )

            if existing['documents'] and existing['documents'][0]:
                distances = existing.get('distances', [[]])[0]
                # If a very similar fact already exists, skip storage
                if distances and distances[0] < 0.3:
                    debug_print(f"DUPLICATE FACT SKIPPED: {fact_text} (distance: {distances[0]:.3f})")
                    continue

        except Exception as e:
            debug_print("DEDUPLICATION CHECK ERROR:", e)
            # If dedup check fails, still attempt to store rather than silently drop

        # Store new fact
        try:
            facts_collection.add(
                documents=[fact_text],
                metadatas=[{
                    "user_id": user_id,
                    "session_id": session_id,
                    "category": category,
                    "timestamp": time.time()
                }],
                ids=[str(uuid.uuid4())]
            )
            debug_print(f"FACT STORED: {fact_text}")
            stored_count += 1
            
    
        except Exception as e:
            debug_print("FACT STORAGE ERROR:", e)
    debug_print(f"STORED {stored_count} NEW FACT(S)")

# ==============================================================================
# FACT RETRIEVAL
# ==============================================================================

def retrieve_facts(user_id: str, limit: int = 25) -> list:
    """
    Retrieves all stored facts for a given user from the facts collection.
    No semantic filtering — all known facts are always returned for prompt injection.
    Returns a list of fact strings, or an empty list if none exist.
    """
    try:
        # ChromaDB requires n_results to not exceed collection count
        total = facts_collection.count()
        if total == 0:
            return []

        results = facts_collection.get(
            where={"user_id": user_id}
        )
        
        if not results or not results.get('documents'):
            return []
        
        facts = results['documents'][:limit]

        debug_print(f"RETRIEVED {len(facts)} FACTS FOR {user_id}: {facts}")
        return facts


    except Exception as e:
        debug_print("FACT RETRIEVAL ERROR:", e)
        return []


# ==============================================================================
# LOCAL SCRIPT EXECUTION TEST UNIT
# ==============================================================================


if __name__ == "__main__":
    # Define uniform test variables to mimic frontend calls
    TEST_USER = "user123"   
    TEST_SESSION = "session_abc_99"

    print("Populating database with conversational text snapshots...")
    
    # FIX: Added the missing 3rd argument (session_id) to match function definition signature
    add_to_memory("user123", "I love playing football", TEST_SESSION)
    add_to_memory("user123", "My favourite food is pizza", TEST_SESSION)
    add_to_memory("user123", "I work as a data scientist", TEST_SESSION)
    print("Stored 3 contextual statements successfully.\n")

    # Query Test: Notice how the query words don't explicitly match "pizza" or "pepperoni"
    SEARCH_QUERY = "what kind of dishes do I enjoy eating?"
    print(f"Executing semantic search for: '{SEARCH_QUERY}'")
    retrieved = retrieve_memory(TEST_USER, SEARCH_QUERY, limit=2, threshold=1.2)
    print("Final Filtered Memory Payload Sent To LLM Prompt:")
    print(retrieved)

    print("\n--- Testing fact extraction ---")
    extract_and_store_facts(TEST_USER, "I love playing football and my favourite food is pizza", TEST_SESSION)
    extract_and_store_facts(TEST_USER, "I work as a data scientist in Mumbai", TEST_SESSION)

    print("\n--- Testing fact retrieval ---")
    facts = retrieve_facts(TEST_USER)
    print("Stored facts:", facts)



