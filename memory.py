# ==============================================================================
# IMPORTS & DATABASE INITIALIZATION
# ==============================================================================

import chromadb
import uuid
import time
import re

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


# ==============================================================================
# DEBUG CONFIGURATION
# ==============================================================================

DEBUG = False

def debug_print(*args):
    if DEBUG:
        print(*args)

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


def retrieve_memory(user_id: str, query: str, limit: int = 10, threshold: float = 1)-> list:
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

    retrieved_facts = retrieve_memory(TEST_USER, SEARCH_QUERY, limit=2, threshold=0.7)
    print("Final Filtered Memory Payload Sent To LLM Prompt:")
    print(retrieved_facts)