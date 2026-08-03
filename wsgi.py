"""Production WSGI entry point for Waitress."""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

missing_credentials = [
    name for name in ("ADMIN_USERNAME", "ADMIN_PASSWORD") if not os.environ.get(name)
]
if missing_credentials:
    raise RuntimeError(
        "Production requires these environment variables: "
        + ", ".join(missing_credentials)
    )

from app import app as application  # noqa: E402

# The production entry point must never expose Flask's interactive debugger,
# even if FLASK_DEBUG is present in the process environment.
application.debug = False
