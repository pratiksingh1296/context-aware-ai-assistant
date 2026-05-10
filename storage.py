# Imports
import sqlite3
import json

# Database file path
DB_PATH = "chat_history.db"

# Create sessions table if it doesn't exist
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            user_id TEXT,
            session_name TEXT,
            messages TEXT,
            PRIMARY KEY (user_id, session_name)
        )
    ''')
    conn.commit()
    conn.close()

# Save sessions to DB
def save_sessions(user_id, sessions):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
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