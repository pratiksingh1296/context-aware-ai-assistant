# Imports
import sqlite3
import json

# Database file path
DB_PATH = "chat_history.db"

# Create sessions table if it doesn't exist
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Session Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            user_id TEXT,
            session_name TEXT,
            messages TEXT,
            PRIMARY KEY (user_id, session_name)
        )
    ''')

    # Summary Table
    c.execute(
        '''
        CREATE TABLE IF NOT EXISTS summaries(
        user_id TEXT,
        session_name TEXT,
        summary_text TEXT,
        last_summarized_message INTEGER,
        PRIMARY KEY(user_id, session_name)
        )
    ''')
    conn.commit()
    conn.close()

# Save sessions to DB
def save_sessions(user_id, sessions):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Remove existing sessions for user
    c.execute(
        "DELETE FROM sessions WHERE user_id = ?",
        (user_id,)
    )

    # Save current sessions
    for session_name, messages in sessions.items():
        c.execute('''
            INSERT OR REPLACE INTO sessions (user_id, session_name, messages)
            VALUES (?, ?, ?)
        ''', (user_id, session_name, json.dumps(messages)))
    conn.commit()
    conn.close()

# Retrieve sessions from DB
def load_sessions(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT session_name, messages FROM sessions WHERE user_id = ?', (user_id,))
    rows = c.fetchall()
    conn.close()
    if not rows:
        return {"Default Chat": []}, "Default Chat"
    sessions = {}
    for session_name, messages in rows:
        sessions[session_name] = json.loads(messages)
    return sessions, list(sessions.keys())[0]


# Save summaries to DB
def save_summary(user_id, session_name, summary_text, last_summarized_message):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO summaries (user_id, session_name, summary_text, last_summarized_message)
        VALUES (?, ?, ?, ?)
    ''', (user_id, session_name, summary_text, last_summarized_message))
    conn.commit()
    conn.close()

# Load summaries
def load_summary(user_id, session_name):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT summary_text, last_summarized_message FROM summaries WHERE user_id = ? AND session_name = ?
        ''',(user_id,session_name))
    summary = c.fetchone()
    conn.close()
    return summary

# Counting messages
def count_user_messages(messages):
    return sum(1 for msg in messages if msg["role"] == "user")