"""Quick sanity check: print every row in both tables."""

from db import get_db_connection

connection = get_db_connection()

print("== posts ==")
for row in connection.execute("SELECT id, title, date_display FROM posts ORDER BY date_iso DESC"):
    print(dict(row))

print("\n== portfolio_items ==")
for row in connection.execute("SELECT id, title FROM portfolio_items ORDER BY id"):
    print(dict(row))

print("\n== videos ==")
for row in connection.execute("SELECT id, title, duration, video_url FROM videos ORDER BY id"):
    print(dict(row))

connection.close()
