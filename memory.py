# ==============================================================================
# IMPORTS & DATABASE INITIALIZATION
# ==============================================================================

import psycopg2
import time
import re
import json
import os

# 3rd Party Imports
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
from llm import get_llm
from utils import debug_print

# Database file path
load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

# Initialize embedding model 
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')


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

    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as c:
            for chunk in chunks:
                chunk = chunk.strip()

                # Content Guard: Avoid cluttering the database with empty words or short fillers
                # Only store chunks that are reasonably long
                if len(chunk) < 10:
                    continue

                # Skip questions
                if chunk.lower().startswith(('what', 'who', 'where', 'when', 'why', 'how', 'is ', 'are ', 'do ', 'does ', 'can ', 'could ')):
                    debug_print(f"SKIPPING QUESTION: {chunk}")
                    continue

                debug_print(f"ADDING MEMORY: {chunk}")

                # 1. Generate embedding for chunk
                embedding = embedding_model.encode(chunk).tolist()

                # 2. Check for duplicates before inserting
                c.execute('''
                    SELECT content, embedding <-> %s::vector AS distance
                    FROM chat_memory
                    WHERE user_id = %s
                    ORDER BY distance
                    LIMIT 1
                ''', (embedding, user_id) )

                existing = c.fetchone()

                if existing:
                    debug_print(
                    f"Closest memory: {existing[0][:50]}... "
                    f"distance={existing[1]:.4f}")

                if existing and existing[1] < 0.3:
                    debug_print(f"Closest memory: {existing[0][:50]}... " 
                                f"distance={existing[1]:.4f}")
                    debug_print(f"DUPLICATE MEMORY SKIPPED: {chunk}")
                    continue

                # 2. Insert into chat_memory if not duplicate
                c.execute('''
                        INSERT INTO chat_memory (user_id, session_id, content, embedding, timestamp)
                        VALUES (%s, %s, %s, %s, %s)
                    ''', (user_id, session_id, chunk, embedding, time.time()) )
                
                c.execute("SELECT COUNT(*) FROM chat_memory WHERE user_id = %s", (user_id,))
                count = c.fetchone()[0]
                debug_print(f"MEMORIES FOR {user_id}: {count}")


def retrieve_memory(user_id: str, query: str, limit: int = 10, threshold: float = 1.2)-> list:
    """
    Queries ChromaDB vector space using semantic search.
    Filters out irrelevant noise using an L2 Distance similarity cap.
    """
    # Generate query embedding
    query_embedding = embedding_model.encode(query).tolist()

    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as c:
            # Semantic search with L2 distance operator <-> (PGVector)
            c.execute('''
                    SELECT content, embedding <-> %s::vector AS distance
                    FROM chat_memory
                    WHERE user_id = %s
                    ORDER BY distance
                    LIMIT %s
                ''', (query_embedding, user_id, limit)
                )
            
            results = c.fetchall()

    # Defensive Guard: Gracefully exit if database returns empty or missing dictionary payload keys
    if not results:
        debug_print("DEBUG: No matching documents found in vector database.")
        return []
        
    documents = [row[0] for row in results]
    distances = [row[1] for row in results]

    debug_print("\n--- PGVECTOR SEARCH DEBUG ---")
    debug_print("MATCHED DOCS:", documents)
    debug_print("L2 DISTANCES:", distances)
    debug_print("-----------------------------\n")

    filtered = []

    for content, distance in results:
        debug_print(f"DISTANCE={distance:.4f} | {content}")

        # Vector Distance Filter, keep matches closer than our threshold
        if distance < threshold:
            filtered.append(content)

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


    # Opening connection 
    with psycopg2.connect(DATABASE_URL) as conn:
                with conn.cursor() as c:
                    
                    # Process each extracted fact independently
                    for item in extracted_facts:

                        fact_text = item.get("fact", "").strip()
                        category = item.get("category", "general").strip()

                        if not fact_text or fact_text.lower() in ["null", "none", ""]:
                            continue
        
                        debug_print(f"EXTRACTED FACT: {fact_text} | CATEGORY: {category}")

                        # Embedding the facts
                        fact_embedding = embedding_model.encode(fact_text).tolist()


                        # Handling duplicates, deduplicating against existing facts
                        try:
                            c.execute('''
                                SELECT content, embedding <-> %s::vector AS distance
                                FROM user_facts
                                WHERE user_id = %s
                                ORDER BY distance
                                LIMIT 3
                            ''', (fact_embedding, user_id))
            
                            results = c.fetchall()

                            if results:
                                best_match = results[0] # closest match
                                best_content, best_distance = best_match
                
                                # If a very similar fact already exists, skip storage
                                if best_distance < 0.3:
                                    debug_print(f"DUPLICATE FACT SKIPPED: {fact_text} (distance: {best_distance:.3f})")
                                    continue

                        except Exception as e:
                            debug_print("DEDUPLICATION CHECK ERROR:", e) 
                            
                        # If dedup check fails, still attempt to store rather than silently drop

                        # Store new fact
                        try:
                            c.execute('''   
                                INSERT INTO user_facts (user_id, session_id, content, category, embedding, timestamp)
                                VALUES(%s,%s,%s,%s,%s,%s)
                            ''', (user_id, session_id, fact_text, category, fact_embedding,time.time()))

                            stored_count += 1
                            debug_print(f"FACT STORED: {fact_text}")

            
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
        with psycopg2.connect(DATABASE_URL) as conn:
                with conn.cursor() as c:
                    c.execute('''
                        SELECT content FROM user_facts WHERE user_id = %s LIMIT %s
                        ''', (user_id, limit)
                )   
                    results = c.fetchall()

        # Handling No User Facts
        if not results:
            debug_print(f"NO FACTS FOUND FOR {user_id}")
            return []
        

        facts = [row[0] for row in results]

        debug_print(f"RETRIEVED {len(facts)} FACTS FOR {user_id}: {facts}")

        return facts

    except Exception as e:
        debug_print("FACT RETRIEVAL ERROR:", e)
        return []


# ==============================================================================
# LOCAL SCRIPT EXECUTION TEST UNIT
# ==============================================================================

def clear_test_user(user_id):
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as c:
            c.execute(
                "DELETE FROM chat_memory WHERE user_id = %s",
                (user_id,)
            )

            c.execute(
                "DELETE FROM user_facts WHERE user_id = %s",
                (user_id,)
            )


if __name__ == "__main__":
    # Define uniform test variables to mimic frontend calls
    TEST_USER = "user123"   
    TEST_SESSION = "session_abc_99"

    clear_test_user(TEST_USER)
    debug_print(f"CLEARED TEST DATA FOR {TEST_USER}")

    print("Populating database with conversational text snapshots...")
    
    # FIX: Added the missing 3rd argument (session_id) to match function definition signature
    add_to_memory(TEST_USER, "I love playing football", TEST_SESSION)
    add_to_memory(TEST_USER, "My favourite food is pizza", TEST_SESSION)
    add_to_memory(TEST_USER, "I work as a data scientist", TEST_SESSION)
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

    print("\n--- Testing memory deduplication ---")
    add_to_memory("user123", "I love football", TEST_SESSION)
    add_to_memory("user123", "I enjoy football", TEST_SESSION)
    add_to_memory("user123", "I enjoy playing football every weekend", TEST_SESSION)
    

