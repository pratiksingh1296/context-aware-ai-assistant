# 🧠 Context-Aware AI Assistant

Built as an AI engineering portfolio project exploring retrieval-augmented generation (RAG), long-term memory architectures, and conversational agent design.

An AI-powered conversational assistant with persistent vector memory, multi-session chat management, and real-time web retrieval.

Built using Llama 3.3, LangChain, ChromaDB, Tavily Search, and Streamlit.

---

## 🚀 Live Demo

👉 **Try the app:** https://memory-chatbot-ai.streamlit.app/

---

## 📸 Screenshots

### Main Interface

![Main Interface](screenshots/main-ui.png)

### Persistent Memory Demo

![Persistent Memory](screenshots/memory-demo.png)

### Web Search Demo

![Web Search](screenshots/web-search-demo.png)

### Multi-Session Chat Management

![Multi-Session Chat](screenshots/chat-management.png)

---

# Project Overview
This project demonstrates building a context-aware AI assistant capable of:
- remembering relevant information across conversations,
- retrieving real-time web information,
- managing multiple chat sessions,
- maintaining conversational continuity using semantic memory retrieval.

The assistant combines:
- short-term conversational memory through session history,
- long-term semantic memory through vector embeddings,
- dynamic web retrieval for up-to-date information.

The project focuses heavily on:
- retrieval quality,
- memory architecture,
- prompt engineering,
- conversational UX,
- semantic search systems.

---

# ✨ Features

## 🧠 Memory & Personalization
- Persistent semantic memory using ChromaDB vector search
- Structured fact memory with automatic user profile extraction
- Multi-session conversation management
- Real-time web search using Tavily
- Date-aware reasoning and temporal query normalization
- User profile persistence across sessions
- Streamlit-based conversational interface
---

## 🌐 Real-Time Web Search
- Tavily Search integration for current information retrieval
- Handles:
  - news
  - weather
  - sports results
  - recent events
  - current information after the model cutoff
- Source-aware responses with clean citation formatting

---

## 💬 Multi-Session Chat Management
- Create multiple chat sessions
- Rename and delete conversations
- Automatic chat title generation based on first user query
- Persistent chat history using SQLite

---

## 🔍 Retrieval-Augmented Context Injection
- Retrieves relevant memories using semantic similarity search
- Injects retrieved context into prompts dynamically
- Prevents irrelevant memory pollution using retrieval filtering


---

## 🎨 Improved Conversational UX
- Clean Streamlit chat interface
- Current active chat indicator
- Welcome onboarding screen
- Typing / thinking indicators
- Cleaner source formatting
- Persistent personalized greetings

---

# Project Structure

```
context-aware-ai-assistant/
│
├── screenshots/
│   ├── main-ui.png
│   ├── memory-demo.png
│   ├── web-search-demo.png
│   └── chat-management.png
│
├── app.py
├── llm.py
├── memory.py
├── storage.py
├── requirements.txt
├── runtime.txt
├── README.md
└── .gitignore

```

---

# 🏗️ Architecture

## Memory System

The assistant uses a three-layer memory architecture designed to balance conversational context, long-term recall, and retrieval quality.

### 1. Short-Term Conversational Memory

Maintained through session chat history.

Used for:
- conversational continuity
- remembering recent exchanges
- maintaining context within an active conversation

---

### 2. Long-Term Semantic Memory

Powered by ChromaDB vector embeddings.

Workflow:
1. User messages are converted into vector embeddings
2. Embeddings are stored in ChromaDB
3. Relevant memories are retrieved using semantic similarity search
4. Retrieved context is injected into prompts dynamically

Examples:
- "I enjoy football"
- "I'm preparing for Data Science interviews"

---

### 3. Structured Fact Memory

Uses an LLM-powered extraction pipeline to identify stable user facts and preferences.
Unlike conversational memory, structured facts are stored independently and semantically deduplicated, allowing the assistant to maintain stable user preferences and profile information across conversations.

Workflow:
1. User messages are analyzed for long-term personal facts
2. Facts are categorized (profile, location, interest, goal, occupation)
3. Semantic deduplication prevents duplicate storage
4. Stored facts are retrieved independently from conversational memory

Examples:
- The user's name is Pratik
- The user lives in Navi Mumbai
- The user loves football

This separation improves retrieval quality by distinguishing stable personal facts from general conversational context.


---

## Retrieval Flow

```text
User Input
    ↓
Chat History Retrieval
    ↓
Semantic Memory Retrieval
    ↓
Fact Memory Retrieval
    ↓
Context Injection
    ↓
(Optional) Web Search
    ↓
Llama 3.3 Response Generation
    ↓
Store Conversation + Facts
```

---

# Usage

## Start a New Chat
- Open the streamlit app
- Enter your name or userid name
- Create a new chat session
- Begin interacting with the assistant.

---

# Tech Stack

| Component              | Technology                          |
| ---------------------- | ----------------------------------- |
| LLM                    | Llama 3.3 (llama-3.3-70b-versatile) |
| Inference API          | Groq API                            |
| Framework              | LangChain                           |
| Vector Database        | ChromaDB                            |
| Chat Storage           | SQLite                              |
| Web Search             | Tavily Search                       |
| Frontend               | Streamlit                           |
| Embeddings             | sentence-transformers               |
| Environment Management | python-dotenv                       |
| Structured Fact Memory | Groq + LangChain                    |

---

# Installation
1. Clone the repo
2. Create a virtual environment
3. `pip install -r requirements.txt`
4. Add your `GROQ_API_KEY` & `TAVILY_API_KEY` to `.env`
5. `streamlit run app.py`

---

# 📈 Key Engineering Concepts Explored
- Retrieval-Augmented Generation (RAG)
- Semantic similarity search
- Vector memory systems
- Prompt orchestration
- Context injection
- Multi-session conversational architecture
- Temporal query normalization
- Persistent conversational memory
- Tool-augmented LLM agents
- Conversational UX design

---

# Engineering Challenges

### Building Reliable Long-Term Memory

A major challenge was balancing memory recall with retrieval quality as conversations grow over time.

Naively storing every message leads to noisy retrieval and duplicate information. To address this, the assistant combines semantic vector search with a dedicated structured fact memory layer.

The fact extraction pipeline:
- identifies stable user attributes and preferences
- categorizes extracted facts
- performs semantic deduplication
- stores facts separately from conversational context

This design improves memory precision while preserving rich conversational history.

### Additional Challenges

- Designing a memory system that balances retrieval quality and noise reduction
- Preventing duplicate memory storage across sessions
- Managing persistent chat history alongside vector memory
- Handling relative date normalization for temporal queries
- Optimizing Streamlit performance using resource caching

---

# 🚧 Future Improvements

- Conversation summarisation for long-running chats
- PostgreSQL + pgvector migration
- Memory conflict resolution and fact updates (e.g., detecting when a user's location or occupation changes)
- PDF upload and retrieval-augmented generation (RAG)
- Hybrid memory ranking (recency + semantic relevance)

---

# 📌 Notes

- Local ChromaDB and SQLite persistence may reset on Streamlit Cloud deployments
- Designed primarily as an AI engineering / retrieval systems portfolio project
- Focused on retrieval quality, memory systems, and conversational architecture rather than only chatbot UI

---
