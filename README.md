# Assistant Chatbot 

It's an assistant chatbot powered by Llama 3.1 with ChromaDB for persistent memory storage.

## Live Demo
[Try it here](your-streamlit-url)

---

## Project Overview
This project demonstrates creating a chatbot with persistent memory using Llama 3.1 & Groq-api. It focuses on having the chatbot persistent memory across all chats,
web search for current information (limitation in llama), date awareness & chat history being saved for context when required. The user also has options to have multiple chat sessions with ability to change chat names & delete them as needed.

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

## Tech Stack
- Python
- Llama 3.1
- Groq API
- SQLite
- Streamlit 
- dotenv
- langchain
- duckduckgosearch

---

## Installation
1. Clone the repo
2. Create a virtual environment
3. pip install -r requirements.txt
4. Add your GROQ_API_KEY to .env
5. streamlit run app.py

---
