import sqlite3

connection = sqlite3.connect("blog.db")
cursor = connection.cursor()

cursor.execute("""
    CREATE TABLE posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        date TEXT,
        excerpt TEXT
    )
""")

cursor.execute("INSERT INTO posts (title, date, excerpt) VALUES (?, ?, ?)",
               ("Post Title", "July 18, 2026", "Short Excerpt..."))

cursor.execute("INSERT INTO posts (title, date, excerpt) VALUES (?, ?, ?)",
               ("Post Title2", "July 18, 2026", "Shorter Excerpt..."))

connection.commit()
connection.close()
