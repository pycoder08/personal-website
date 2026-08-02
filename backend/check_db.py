import sqlite3

connection = sqlite3.connect("blog.db")
cursor = connection.cursor()

cursor.execute("SELECT * FROM posts")
rows = cursor.fetchall()

for row in rows:
    print(row)

connection.close()
