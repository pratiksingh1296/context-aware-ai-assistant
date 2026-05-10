# Assistant Chatbot 

It's an assistant chatbot powered by Llama 3.1 with ChromaDB for persistent memory storage.

## Live Demo

[Try it here](https://memory-chatbot-ai.streamlit.app/)

---

## Project Overview
This project demonstrates building an AI chatbot with persistent memory using Llama 3.1 and the Groq API. The chatbot maintains context across conversations by storing chat history and memory, enabling more personalized and context-aware interactions.

The project also integrates web search for retrieving current information beyond the model’s knowledge cutoff. Users can manage multiple chat sessions, rename conversations, and delete chats when needed.

---

## Features
- Persistent memory across chats
- Multiple chat sessions
- Rename & delete chats
- Web search integration
- Context-aware responses
- SQLite chat history storage
- Groq API integration with Llama 3.1

---

## Project Structure

```
assistant-chatbot/
├── .gitignore
├── app.py
├── llm.py
├── memory.py
├── README.md
├── requirements.txt
└── storage.py
```

---

## Architecture
User messages are embedded using sentence-transformers and stored in ChromaDB. On each query, semantically relevant past context is retrieved and injected into the prompt, enabling the chatbot to remember information across separate sessions.

---

## Usage

### Start a New Chat
- Open the streamlit app
- Enter your name or userid name
- Create a new chat session
- Begin interacting with the assistant.

### Persistent Memory
The chatbot remembers relevant information from previous conversations using ChromaDB vector storage.

Example:
- User: "My favorite language is Python."
- Later: "What language do I like?"
- Assistant: "You previously mentioned that your favorite language is Python."

### Managing Chats
Users can:
- Create multiple chat sessions
- Rename conversations
- Delete chats when no longer needed

### Web Search
If current or real-time information is required, the assistant performs a web search to improve response accuracy.

---

## Workflow

- The system retrieves semantically similar memories using embeddings generated from sentence-transformers. Relevant memories are appended to the prompt before sending the request to the Groq-hosted Llama 3.1 model.

```text
User Input
    ↓
Chat History Retrieval
    ↓
Memory Search (ChromaDB)
    ↓
Relevant Context Injection
    ↓
(Optional) Web Search
    ↓
Llama 3.1 Response Generation
    ↓
Store Conversation in Memory
```

---

## Tech Stack
- Python
- Llama 3.1
- Groq API
- SQLite
- Streamlit 
- dotenv
- LangChain
- duckduckgosearch
- ChromaDB

---

## Installation
1. Clone the repo
2. Create a virtual environment
3. pip install -r requirements.txt
4. Add your GROQ_API_KEY to .env
5. streamlit run app.py

---

## Future Improvements
- Memory threshold tuning for better context relevance
- Support for file uploads and document Q&A
- User authentication for multi-user support
- LangGraph integration for more complex agentic workflows
- Voice input support

---
