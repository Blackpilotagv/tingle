import sqlite3

# Connect to database (creates file if not exists)
conn = sqlite3.connect('userstocks.db')

# Create table if not exists
conn.execute('''
CREATE TABLE IF NOT EXISTS user_stocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    stock_symbol TEXT

);
''')

conn.close()