"""Small helper module for talking to the SQLite database.

Keeping this in one place means every route in app.py opens/closes
connections the same way, and the database file always resolves to the
same path no matter what folder you run `python app.py` from.
"""

import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "blog.db")

# Tests point this at a temporary, isolated database via the BLOG_DB_PATH
# environment variable (see the project root conftest.py). Normal local dev
# and production never set that variable, so DB_PATH resolves to the same
# hardcoded blog.db path as before -- zero config changes for normal use.
DB_PATH = os.environ.get("BLOG_DB_PATH", DEFAULT_DB_PATH)


def get_db_connection():
    """Return a new SQLite connection with rows accessible by column name."""
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection
