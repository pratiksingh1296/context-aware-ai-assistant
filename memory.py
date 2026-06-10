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
from llm import get_llm, get_fast_llm
from utils import debug_print
import streamlit as st

# Database file path
load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

# Initialize embedding model 
@st.cache_resource
def get_embedding_model():
    return SentenceTransformer('all-MiniLM-L6-v2')


# ==============================================================================
# CORE MEMORY FUNCTIONS
# ==============================================================================

def add_to_memory(user_id: str, text: str, session_id: str):
    """
    Stores conversational memories in the chat_memory table for future
    semantic retrieval.

    The function breaks incoming text into sentence-level memory chunks,
    generates vector embeddings for each chunk, and persists unique
    memories to the database.

    Behavior:
    - Splits text into atomic chunks using punctuation and line breaks.
    - Ignores empty, very short, or low-information fragments.
    - Skips question-like content to avoid storing transient queries
    as long-term memory.
    - Generates embeddings for each memory chunk.
    - Performs semantic deduplication using vector similarity against
    existing memories for the same user.
    - Stores only memories that are sufficiently distinct from
    previously saved memories.
    - Associates each stored memory with the current user and session.

    Args:
        user_id: Unique identifier of the user.
        text: Conversational text to be processed and stored.
        session_id: Identifier of the current conversation session.

    Returns:
        None

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
                embedding = get_embedding_model().encode(chunk).tolist()

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

# Retrieve Memory
def retrieve_memory(user_id: str, query: str, limit: int = 10, threshold: float = 1.2)-> list:
    """
    Retrieves relevant conversational memories for a user using
    semantic vector search.

    The function embeds the query, searches the chat_memory table
    using PGVector similarity search, and returns only memories that
    meet the configured relevance threshold.

    Behavior:
    - Generates an embedding for the incoming query.
    - Performs nearest-neighbor vector search against the user's
    stored memories.
    - Retrieves the closest matching memory candidates ordered by
    vector distance.
    - Filters results using an L2 distance threshold to remove
    semantically weak matches.
    - Returns only memory contents that are considered relevant.
    - Returns an empty list when no suitable memories are found.

    Args:
        user_id: Unique identifier of the user.
        query: Text used to search for relevant memories.
        limit: Maximum number of candidate memories to retrieve
            before relevance filtering.
        threshold: Maximum allowed vector distance for a memory
            to be considered relevant.
    Returns:
        list[str]: Relevant memory contents ordered by semantic
        similarity.

    """
    # Generate query embedding
    query_embedding = get_embedding_model().encode(query).tolist()

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
    Extracts long-term user facts from a user message and stores them
    in the user_facts table.

    The function uses a lightweight LLM to identify stable personal
    information that may be useful across future conversations.

    Behaviour:
    - Only stores facts from user messages (never agent responses)
    - Supports extraction of multiple facts from a single message
    - Stores facts with vector embeddings for semantic retrieval
    - For single-value categories (profile, location, occupation), any existing value is replaced with the newly extracted fact
    - For multi-value categories (goal, project, skill, interest), semantic deduplication is performed before storage to avoid
    saving near-duplicate facts.
    - Silently skips malformed LLM output or storage errors so the main chat flow is never interrupted.
    
    Args:
        user_id: Unique identifier of the user.
        user_message: Raw message sent by the user.
        session_id: Identifier of the current conversation session.
    Returns:
        None
        
    """

    llm = get_fast_llm()

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
    - Ongoing projects
    - Skills being learned or possessed
    - Hobbies and interests
    - Strong preferences (favourite foods, sports, technologies, etc.)

    CRITICAL RULES:
    - Always write the "fact" value as a full sentence in third person, starting with "The user..."
    - Never infer facts that are not explicitly stated
    - Only extract information directly present in the user message
    - Extract every valid long-term fact present in the message, not just the first one.
    - NEVER store negative statements such as "The user does not have a stated X" or "The user has not mentioned X"
    - NEVER infer the absence of information as a fact

    - Do NOT store:
        - Temporary plans for the next few days
        - Current mood or emotions
        - Questions
        - One-time events
        - Small talk

    Valid categories: profile | interest | location | goal | occupation | project | skill

    CATEGORY GUIDELINES:

    IMPORTANT DISTINCTIONS:

    - A goal is something the user wants to achieve in the future.
    - A project is something the user is actively building, developing, researching, creating or working on.
    - A skill is something the user knows or is actively learning.

    - profile: 
        Stable personal identity information.
        Examples: name, age, education level, nationality.

    - location:
        Where the user currently lives or is based.
        Examples: "I live in Mumbai", "I moved to Bangalore".
    
    - occupation:
        The user's current profession, job, or role.
        Examples: "I work as a Data Analyst", "I am a Software Engineer".

    - interest:
        Long-term hobbies, passions, preferences, or things the user consistently enjoys.
        Examples: football, chess, reading, favourite foods, favourite technologies.
    
    - goal: 
        Something the user wants to achieve in the future.
        Example: "I want to become a Data Scientist", "I want to crack ML interviews".

    - project: Something the user is actively building, developing, or working on.
        Example: "I am building a chatbot", "I am developing a forecasting model".

    - skill: Knowledge, technologies, subjects, or capabilities the user possesses or is actively learning.
        Example: "I know Python", "I am learning machine learning", "I am studying SQL".

    Examples:
    - "I'm Pratik by the way"         -> {{"fact": "The user's name is Pratik", "category": "profile"}}
    - "I love playing football"       -> {{"fact": "The user loves playing football", "category": "interest"}}
    - "I live in Navi Mumbai"         -> {{"fact": "The user lives in Navi Mumbai", "category": "location"}}
    - "I am preparing for DS interviews" -> {{"fact": "The user is preparing for Data Science interviews", "category": "goal"}}
    - "I work as a data analyst"      -> {{"fact": "The user works as a Data Analyst", "category": "occupation"}}
    - "I am building a chatbot"      -> {{"fact": "The user is building a chatbot", "category": "project"}}
    - "I am developing an AI assistant" -> {{"fact": "The user is developing an AI assistant", "category": "project"}}
    - "I know Python and SQL"        -> {{"fact": "The user knows Python and SQL", "category": "skill"}}
    - "I am learning machine learning" -> {{"fact": "The user is learning machine learning", "category": "skill"}}

    MULTI-FACT EXAMPLES:

    - "I live in Mumbai and work as a Data Analyst"
    ->
    {{
    "facts": [
        {{"fact": "The user lives in Mumbai", "category": "location"}},
        {{"fact": "The user works as a Data Analyst", "category": "occupation"}}
        ]
    }}

    - "I am learning machine learning and building a chatbot"
    ->
    {{
    "facts": [
        {{"fact": "The user is learning machine learning", "category": "skill"}},
        {{"fact": "The user is building a chatbot", "category": "project"}}
        ]
    }}

    User message: "{user_message}"

    If one or more long-term personal facts are present, respond with ONLY this JSON structure:
    {{
    "facts": [
        {{"fact": "The user...", "category": "<one valid category>"}},
        {{"fact": "The user...", "category": "<one valid category>"}}
        ]
    }}

    If no long-term personal fact is found, respond with ONLY:
    {{"facts": []}}

    If no personal fact is clearly present, return {{"facts": []}} immediately — do not attempt to fill in blanks
    
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

    SINGLE_VALUE_CATEGORIES = {"location", "occupation", "profile"}

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
                        fact_embedding = get_embedding_model().encode(fact_text).tolist()

                        if category in SINGLE_VALUE_CATEGORIES:
                            # Delete existing fact in this category for this user
                            try:
                                c.execute('''
                                    DELETE FROM user_facts
                                    WHERE user_id = %s AND category = %s
                                ''', (user_id,category))

                                # Then insert new one unconditionally
                                c.execute('''
                                    INSERT INTO user_facts (user_id, session_id, content, category, embedding, timestamp)
                                    VALUES (%s, %s, %s, %s, %s, %s)
                                    ''', (user_id, session_id, fact_text, category, fact_embedding, time.time()))

                                stored_count += 1
                                debug_print(f"FACT UPDATED (single-value): {fact_text}")
                            
                            except Exception as e:
                                debug_print("SINGLE VALUE FACT UPDATE ERROR:", e)

                        else:
                            # Multi-value categories — existing dedup logic
                            try:
                                c.execute('''
                                        SELECT content, embedding <-> %s::vector AS distance
                                        FROM user_facts
                                        WHERE user_id = %s AND category = %s
                                        ORDER BY distance
                                        LIMIT 3
                                    ''', (fact_embedding, user_id, category))
                                
                                results = c.fetchall()

                                if results:
                                    best_content, best_distance = results[0]
                                    if best_distance < 0.3:
                                        debug_print(f"DUPLICATE FACT SKIPPED: {fact_text} (distance: {best_distance:.3f})")
                                        continue

                            except Exception as e:
                                debug_print("DEDUPLICATION CHECK ERROR:", e)

                            # Insert new fact
                            try:
                                c.execute('''
                                        INSERT INTO user_facts (user_id, session_id, content, category, embedding, timestamp)
                                        VALUES (%s, %s, %s, %s, %s, %s)
                                    ''', (user_id, session_id, fact_text, category, fact_embedding, time.time()))
                                
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
    Retrieves stored user facts from the user_facts table for use
    as persistent profile memory.

    Unlike conversational memory retrieval, this function does not
    perform semantic search or relevance filtering. All stored facts
    for the user are considered important profile information and are
    returned directly.

    Behavior:
    - Retrieves facts associated with the specified user.
    - Returns facts as plain text strings.
    - Applies a configurable maximum result limit.
    - Returns an empty list if no facts exist.
    - Gracefully handles database errors without interrupting the
    main chat flow.

    Args:
        user_id: Unique identifier of the user.
        limit: Maximum number of facts to retrieve.

    Returns:
        list[str]: Stored user facts suitable for prompt injection
        and long-term personalization.
        
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
    add_to_memory(TEST_USER, "I love football", TEST_SESSION)
    add_to_memory(TEST_USER, "I enjoy football", TEST_SESSION)
    add_to_memory(TEST_USER, "I enjoy playing football every weekend", TEST_SESSION)
    
    print("\n--- Testing memory conflict resolution ---")
    extract_and_store_facts(TEST_USER, "I live in Navi Mumbai", TEST_SESSION)
    print("After first location:")
    print(retrieve_facts(TEST_USER))

    extract_and_store_facts(TEST_USER, "I moved to Bangalore", TEST_SESSION)
    print("After location update:")
    print(retrieve_facts(TEST_USER))

