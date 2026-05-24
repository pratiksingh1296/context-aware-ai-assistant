try:
    __import__('pysqlite3')
    import sys
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ModuleNotFoundError:
    pass


# ==================================================
# Imports
# ==================================================


import streamlit as st 
from llm import generate_response, generate_chat_title
from memory import add_to_memory, retrieve_memory
from storage import init_db, save_sessions, load_sessions


# ==================================================
# Streamlit Page Configuration
# ==================================================


st.set_page_config(page_title="Assistant Chatbot", page_icon="🤖", layout="centered")


# ==================================================
# Database Initialization
# ==================================================


init_db()


# ==================================================
# User Authentication / User Session Setup
# ==================================================

def store_user_profile(user_id):
    """
    Stores a simple user profile in memory for personalized interactions
    """
    add_to_memory(
        user_id,
        f"My name is {user_id}",
        "profile"
    )

if "user_id" not in st.session_state:
    st.session_state.user_id = ""

if not st.session_state.user_id:
    st.title("🤖 Assistant Chatbot")
    name = st.text_input("Welcome! How would you like me to address you?")
    if name.strip():
        st.session_state.user_id = name.strip().title()
        st.rerun()
    st.stop()

USER_ID = st.session_state.user_id

existing = retrieve_memory(USER_ID, "What is my name?", limit=5)

if not any(USER_ID.lower() in str(mem).lower() for mem in existing):
    store_user_profile(USER_ID)


# ==================================================
# Session State Initialization
# ==================================================


if "sessions" not in st.session_state:
    st.session_state.sessions, st.session_state.current_session = load_sessions(USER_ID)

if "editing_session" not in st.session_state:
    st.session_state.editing_session = None


# ==================================================
# Sidebar - Chat Session Management
# ==================================================


with st.sidebar:
    st.header("Chat Sessions")
    st.write(f"User: `{USER_ID}`")

    ## Custom CSS for edit & delete buttons
    st.html("""
        <style>
            /* Target edit and delete buttons in the sidebar */
            div[data-testid="stSidebar"] button[data-testid^="stBaseButton-edit_btn_"],
            div[data-testid="stSidebar"] button[data-testid^="stBaseButton-del_"] {
                min-height: 28px !important;  /* Standard is ~38px; this shrinks the height */
                height: 28px !important;
                width: 32px !important;       /* Gives it a neat, narrow rectangular shape */
                min-width: 32px !important;
                padding: 0px !important;      /* Removes default bulky padding */
                font-size: 12px !important;    /* Makes the emoji smaller */
                line-height: 28px !important; /* Centers the emoji vertically */
                margin: auto !important;      /* Centers the button in its column */
            }
            
            /* Optional: Align them nicely with the row text */
            div[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] {
                align-items: center;
            }
        </style>
    """)

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

    if st.button("Clear Current Chat", key="clear_current", use_container_width=True):
        st.session_state.sessions[st.session_state.current_session] = []
        save_sessions(USER_ID, st.session_state.sessions)
        st.rerun()
    if st.button("Clear All Chat History", key="clear_all", use_container_width=True):
        st.session_state.sessions = {"Default Chat": []}
        st.session_state.current_session = "Default Chat"
        save_sessions(USER_ID, st.session_state.sessions)
        st.rerun()


# ==================================================
# Main Chat Interface
# ==================================================


st.title("🤖 Assistant Chatbot")
st.markdown(f"**Current Chat:** `{st.session_state.current_session}`")
st.caption("Powered by Llama 3.3 + ChromaDB persistent memory")


# ==================================================
# Chat History Rendering
# ==================================================


if st.session_state.current_session is None:
    st.session_state.current_session = "Chat 1"
    st.session_state.sessions["Chat 1"] = []
messages = st.session_state.sessions[st.session_state.current_session]

# Display chat history
for message in messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


# ==================================================
# Initial Greeting Logic
# ==================================================


if len(messages) == 0:

    st.info(
f"""
👋 Welcome back, {USER_ID}!

🧠 Persistent memory across chats

🌐 Real-time web search

💬 Multi-session conversations

📅 Date-aware reasoning

Try asking:
• What do you remember about me?
• Latest AI news
• Help me prepare for a DS interview
• Explain Random Forests
"""
    )

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


# ==================================================
# User Input Handling
# ==================================================


if prompt := st.chat_input("Say something..."):

    current_session = st.session_state.current_session

    # ==================================================
    # Automatic Chat Title Generation
    # ==================================================

    if (current_session.startswith("Chat ") or current_session == "Default Chat"):
        new_title = generate_chat_title(prompt).strip()
        new_title = new_title[:30]  # Limit title length to 30 characters
        
        if not new_title:
            new_title = current_session

        original_title = new_title
        counter = 1

        while (new_title in st.session_state.sessions and new_title != current_session):
            new_title = f"{original_title} ({counter})"
            counter += 1

        st.session_state.sessions[new_title] = st.session_state.sessions.pop(current_session)
        st.session_state.current_session = new_title

        save_sessions(USER_ID, st.session_state.sessions)
    # Always get current session messages
    messages = st.session_state.sessions[st.session_state.current_session]

    messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)


    # ==================================================
    # Memory Retrieval + Prompt Construction
    # ==================================================


    past_context = retrieve_memory(USER_ID, prompt)
    context_text = "\n".join(past_context) if past_context else ""
    full_prompt = f"Context from memory: {context_text}\n\nCurrent question: {prompt}" if context_text else prompt


    # ==================================================
    # Response Generation
    # ==================================================


    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = generate_response(full_prompt, st.session_state.sessions[st.session_state.current_session])
        st.markdown(response)


    # ==================================================
    # Save Chat Session + Persistent Memory
    # ==================================================

    messages.append({ "role": "assistant", "content": response})
    save_sessions(USER_ID, st.session_state.sessions)

    add_to_memory(USER_ID, prompt, st.session_state.current_session)

