import sqlite3

# Connect to database (creates file if not exists)
conn = sqlite3.connect('users.db')

# Create table if not exists
conn.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    phone TEXT
);
''')

conn.close()