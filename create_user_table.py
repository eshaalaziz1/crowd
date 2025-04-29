import sqlite3

# Connect to the database (creates it if it doesn't exist)
conn = sqlite3.connect('users.db')

# Create the "user" table if it doesn't exist
conn.execute('''
CREATE TABLE IF NOT EXISTS user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL
)
''')

conn.commit()
conn.close()

print("User table created or already exists.")
