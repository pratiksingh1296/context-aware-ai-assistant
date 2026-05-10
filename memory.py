# ==================================================
# Imports
# ==================================================

import chromadb
import uuid
import time

'''
To use different embedding function :

from chromadb.utils import embedding_functions

embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

'''
# ==================================================
# Memory Store
# ==================================================

client = chromadb.PersistentClient(path="./memory_store")
collection = client.get_or_create_collection(name="chat_memory")

def add_to_memory(user_id, text, session_id):
    collection.add(
        documents=[text],
        metadatas=[{
            "user_id": user_id,
            "session_id": session_id,
            "timestamp": time.time()
        }],
        ids=[str(uuid.uuid4())]
    )

def retrieve_memory(user_id, query, limit=5, threshold=0.3):
    results = collection.query(
        query_texts=[query],
        n_results=limit,
        where={"user_id": user_id}
    )
    if not results['documents'] or not results['documents'][0]:
        return []
        
    documents = results['documents'][0]
    distances = results['distances'][0]

    # Only return results that are above the similarity threshold
    filtered = [doc for doc, dist in zip(documents, distances) if dist < threshold]
    return filtered

# ==================================================
# Main - Testing
# ==================================================

if __name__ == "__main__":
    # Test storing
    add_to_memory("user123", "I love playing football")
    add_to_memory("user123", "My favourite food is pizza")
    add_to_memory("user123", "I work as a data scientist")
    print("Stored 3 messages successfully")

    # Test retrieving
    results = retrieve_memory("user123", "what food do I like")
    print("Retrieved:", results)