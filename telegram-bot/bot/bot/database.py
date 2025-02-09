# Create a new file database.py
import sqlite3

def init_db():
    conn = sqlite3.connect('quiz.db')
    c = conn.cursor()
    
    # Create tables
    c.execute('''
        CREATE TABLE IF NOT EXISTS quizzes
        (id INTEGER PRIMARY KEY, title TEXT, creator_id INTEGER)
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS questions
        (id INTEGER PRIMARY KEY, quiz_id INTEGER, question TEXT,
        image_path TEXT, options TEXT, correct_option INTEGER)
    ''')
    
    conn.commit()
    conn.close()