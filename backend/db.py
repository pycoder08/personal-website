"""Small helper module for talking to the SQLite database.

Keeping this in one place means every route in app.py opens/closes
connections the same way, and the database file always resolves to the
same path no matter what folder you run `python app.py` from.
"""

import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "blog.db")


def get_db_connection():
    """Return a new SQLite connection with rows accessible by column name."""
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection
