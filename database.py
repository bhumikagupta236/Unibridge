import sqlite3
import os
from datetime import datetime

DATABASE_FILE = 'unibridge.db'

def get_db_connection():
    """Establish a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row  # Returns rows as dictionaries
    return conn

def init_db():
    """Initialize the database with tables if they don't exist."""
    conn = get_db_connection()
    c = conn.cursor()
    
    # Create the user table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create the activity log table
    c.execute('''
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            activity_name TEXT NOT NULL,
            details TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    conn.commit()
    conn.close()

def create_user(username, password_hash):
    """Insert a new user."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (username, password_hash))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # Username already exists
    finally:
        conn.close()

def get_user_by_username(username):
    """Retrieve a user by username."""
    conn = get_db_connection()
    c = conn.cursor()
    user = c.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    return user

def log_activity(user_id, activity_name, details=''):
    """Log user activity."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('INSERT INTO activity_log (user_id, activity_name, details) VALUES (?, ?, ?)', 
              (user_id, activity_name, details))
    conn.commit()
    conn.close()

def get_user_activity(user_id):
    """Retrieve activity log for a specific user."""
    conn = get_db_connection()
    c = conn.cursor()
    activities = c.execute('''
        SELECT activity_name, details, timestamp 
        FROM activity_log 
        WHERE user_id = ? 
        ORDER BY timestamp DESC
    ''', (user_id,)).fetchall()
    conn.close()
    return activities

def clear_user_activity(user_id):
    """Clear all activity log entries for a specific user."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('DELETE FROM activity_log WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
