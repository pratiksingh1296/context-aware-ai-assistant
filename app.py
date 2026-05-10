__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

import streamlit as st
from llm import generate_response
from memory import add_to_memory, retrieve_memory
from storage import init_db, save_sessions, load_sessions

# Page Config
st.set_page_config(page_title="Assistant Chatbot", page_icon="🤖", layout="centered")

# Initialize DB
init_db()

# User Authentication
if "user_id" not in st.session_state:
    st.session_state.user_id = ""

if not st.session_state.user_id:
    st.title("🤖 Assistant Chatbot")
    name = st.text_input("Welcome! How would you like me to address you?")
    if name.strip():
        st.session_state.user_id = name.strip()
        st.rerun()
    st.stop()

USER_ID = st.session_state.user_id

# Session Management
if "sessions" not in st.session_state:
    st.session_state.sessions, st.session_state.current_session = load_sessions(USER_ID)

if "editing_session" not in st.session_state:
    st.session_state.editing_session = None

# Sidebar
with st.sidebar:
    st.header("Chat Sessions")
    st.write(f"User: `{USER_ID}`")

    if st.button("+ New Chat"):
        new_name = f"Chat {len(st.session_state.sessions) + 1}"
        st.session_state.sessions[new_name] = []
        st.session_state.current_session = new_name
        save_sessions(USER_ID, st.session_state.sessions)
        st.rerun()

    for session_name in list(st.session_state.sessions.keys()):
        col1, col2, col3 = st.columns([3, 1, 1])

        with col1:
            if st.session_state.editing_session == session_name:
                new_name = st.text_input("", value=session_name, key=f"edit_{session_name}")
                if new_name.strip() and new_name != session_name:
                    st.session_state.sessions[new_name] = st.session_state.sessions.pop(session_name)
                    if st.session_state.current_session == session_name:
                        st.session_state.current_session = new_name
                    st.session_state.editing_session = None
                    save_sessions(USER_ID, st.session_state.sessions)
                    st.rerun()
            else:
                if st.button(session_name, key=f"btn_{session_name}"):
                    st.session_state.current_session = session_name
                    st.rerun()

        with col2:
            if st.button("✏️", key=f"edit_btn_{session_name}"):
                st.session_state.editing_session = session_name
                st.rerun()

        with col3:
            if st.button("🗑", key=f"del_{session_name}"):
                del st.session_state.sessions[session_name]
                if st.session_state.current_session == session_name:
                    remaining = list(st.session_state.sessions.keys())
                    st.session_state.current_session = remaining[0] if remaining else None
                st.session_state.editing_session = None
                save_sessions(USER_ID, st.session_state.sessions)
                st.rerun()

    st.divider()
    st.header("Settings")
    if st.button("Clear Chat History"):
        st.session_state.sessions[st.session_state.current_session] = []
        save_sessions(USER_ID, st.session_state.sessions)
        st.rerun()

# Main Chat UI
st.title("🤖 Assistant Chatbot")
st.caption("Powered by Llama 3.1 + ChromaDB persistent memory")

# Shortcut for current session messages
messages = st.session_state.sessions[st.session_state.current_session]

# Display chat history
for message in messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Greet User
if len(messages) == 0:
    past = retrieve_memory(USER_ID, USER_ID, limit=3)
    if past:
        greeting_prompt = f"Greet the user named {USER_ID} warmly in one sentence. You have spoken to them before so welcome them back."
    else:
        greeting_prompt = f"Greet the user named {USER_ID} warmly in one sentence. This is their first time here so welcome them."

    greeting = generate_response(greeting_prompt)
    messages.append({"role": "assistant", "content": greeting})
    with st.chat_message("assistant"):
        st.markdown(greeting)
    save_sessions(USER_ID, st.session_state.sessions)

# User Input
if prompt := st.chat_input("Say something..."):
    messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    past_context = retrieve_memory(USER_ID, prompt)
    context_text = "\n".join(past_context) if past_context else ""
    full_prompt = f"Context from memory: {context_text}\n\nCurrent question: {prompt}" if context_text else prompt

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = generate_response(full_prompt, st.session_state.sessions[st.session_state.current_session])
        st.markdown(response)

    messages.append({"role": "assistant", "content": response})
    save_sessions(USER_ID, st.session_state.sessions)
    add_to_memory(USER_ID, f"User: {prompt}", st.session_state.current_session)
    add_to_memory(USER_ID, f"Assistant: {response}", st.session_state.current_session)