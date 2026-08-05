"""Shared pytest fixtures for the whole test suite.

Test isolation strategy
------------------------
This module sets BLOG_DB_PATH / PORTFOLIO_IMAGE_DIR / ADMIN_USERNAME /
ADMIN_PASSWORD environment variables to point at a single temporary
directory *before* backend/db.py and backend/app.py are imported for the
first time (those modules read the env vars once, at import time, exactly
like the hardcoded defaults they replace -- see backend/db.py and the
PORTFOLIO_IMAGE_DIR comment in backend/app.py). That means:

- The real backend/blog.db is never opened by the test suite.
- The real static/images/portfolio/ directory is never written to.
- Tests use known, fixed admin credentials instead of the local-dev
  admin/changeme fallback or whatever the developer's real env has set.

The temporary database and upload directory are shared for the whole test
session (simpler than a fresh file per test, and the task description
explicitly allows either), but the `client` fixture re-creates the schema
and reseeds the same known sample data before every test function, and
clears out any uploaded files -- so tests never see leftover state from a
previous test.
"""

import base64
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

TEST_ADMIN_USERNAME = "test-admin"
TEST_ADMIN_PASSWORD = "test-password-123"

_TEST_ROOT = Path(tempfile.mkdtemp(prefix="personal-website-tests-"))
_TEST_DB_PATH = _TEST_ROOT / "test_blog.db"
_TEST_UPLOAD_DIR = _TEST_ROOT / "portfolio_uploads"
_TEST_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Must happen before the first `import db` / `import app` anywhere in the
# process, since both modules read these variables at module import time.
os.environ["BLOG_DB_PATH"] = str(_TEST_DB_PATH)
os.environ["PORTFOLIO_IMAGE_DIR"] = str(_TEST_UPLOAD_DIR)
os.environ["ADMIN_USERNAME"] = TEST_ADMIN_USERNAME
os.environ["ADMIN_PASSWORD"] = TEST_ADMIN_PASSWORD

import app as app_module  # noqa: E402
import db as db_module  # noqa: E402
import init_db as init_db_module  # noqa: E402


def _reset_database():
    connection = db_module.get_db_connection()
    init_db_module.init_schema(connection)
    init_db_module.seed_sample_data(connection)
    connection.commit()
    connection.close()


def _clear_uploaded_images():
    for path in _TEST_UPLOAD_DIR.glob("*"):
        if path.is_file():
            path.unlink()


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001
    shutil.rmtree(_TEST_ROOT, ignore_errors=True)


@pytest.fixture()
def client():
    """A Flask test client backed by a freshly reseeded temporary database
    and an empty temporary upload directory. Use this for every test that
    talks to a route."""
    _reset_database()
    _clear_uploaded_images()
    app_module.app.config.update(TESTING=True)
    with app_module.app.test_client() as test_client:
        yield test_client


@pytest.fixture()
def upload_dir():
    """The temp directory portfolio image uploads are saved to during
    tests, for assertions that a file was written/removed on disk."""
    return _TEST_UPLOAD_DIR


@pytest.fixture()
def good_auth():
    """The `auth=` kwarg for flask test client requests, with valid
    credentials."""
    return (TEST_ADMIN_USERNAME, TEST_ADMIN_PASSWORD)


@pytest.fixture()
def bad_auth():
    """The `auth=` kwarg for flask test client requests, with valid-looking
    but wrong credentials."""
    return ("wrong-user", "wrong-password")


def basic_auth_header(username, password):
    """Build a raw Authorization header value, for the couple of places a
    test wants to assert on the header-based flow directly rather than
    relying on the test client's `auth=` helper."""
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {token}"
