# Imports
import psycopg2
import json
import os
from dotenv import load_dotenv

# Database file path
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# Create sessions table if it doesn't exist
def init_db():
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as c:


            # Session Table
            c.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                user_id TEXT,
                session_name TEXT,
                messages JSONB,
                PRIMARY KEY (user_id, session_name)
                    );
            ''')

            # Summary Table
            c.execute('''
                CREATE TABLE IF NOT EXISTS summaries(
                user_id TEXT,
                session_name TEXT,
                summary_text TEXT,
                last_summarized_message INTEGER,
                PRIMARY KEY(user_id, session_name)
                    );
            ''')


# Save sessions to DB
def save_sessions(user_id, sessions):
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as c:


            # Remove existing sessions for user
            c.execute(
                    "DELETE FROM sessions WHERE user_id = %s;",
                    (user_id,)
            )

            # Save current sessions
            for session_name, messages in sessions.items():
                c.execute('''
                    INSERT INTO sessions (user_id, session_name, messages)
                    VALUES (%s, %s, %s);
                ''', (user_id, session_name, json.dumps(messages)))


# Retrieve sessions from DB
def load_sessions(user_id):
    sessions = {}

    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as c:
            c.execute(
                'SELECT session_name, messages FROM sessions WHERE user_id = %s;', (user_id,)
            )
            rows = c.fetchall()
            
            # If no rows found, immediately return defaults
            if not rows:
                return {"Default Chat": []}, "Default Chat"

            for session_name, messages in rows:
                sessions[session_name] = messages 

    return sessions, list(sessions.keys())[0]


# Save summaries to DB
def save_summary(user_id, session_name, summary_text, last_summarized_message):
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as c:
            c.execute('''
                INSERT INTO summaries (user_id, session_name, summary_text, last_summarized_message)
                VALUES (%s, %s, %s, %s);
            ''', (user_id, session_name, summary_text, last_summarized_message)
            )


# Load summaries
def load_summary(user_id, session_name):
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as c:

            c.execute('''
                SELECT summary_text, last_summarized_message FROM summaries WHERE user_id = %s AND session_name = %s;
                ''',(user_id,session_name)
                )
            summary = c.fetchone()
    return summary

# Counting messages
def count_user_messages(messages):
    return sum(1 for msg in messages if msg["role"] == "user")