r"""Flask app for the personal site.

Run it with:

    venv\Scripts\python backend\app.py

from the project root (personal-website-full/). Templates live in
../templates and static assets (css, images) live in ../static, both
resolved from this file's location so it doesn't matter which folder
you launch it from.
"""

import os
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps

import markdown as markdown_lib
import yt_dlp
from flask import Flask, Response, abort, flash, redirect, render_template, request, session, url_for
from markupsafe import Markup
from werkzeug.utils import secure_filename

from db import get_db_connection

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

app = Flask(
    __name__,
    template_folder=os.path.join(PROJECT_ROOT, "templates"),
    static_folder=os.path.join(PROJECT_ROOT, "static"),
)

# ---------------------------------------------------------------------------
# Image uploads: the only place in the app that accepts binary file input.
# Uploaded files are saved under static/images/... using a freshly
# generated filename (never the client-supplied one) so there's no
# path-traversal risk and no chance of two uploads colliding.
#
# PORTFOLIO_IMAGE_DIR holds each project's one thumbnail (tied 1:1 to a
# portfolio_items row via image_filename). CONTENT_IMAGE_DIR holds inline
# images referenced from Markdown body text (blog posts, portfolio
# write-ups) via the /admin/upload-image utility -- these aren't tied to
# any single row/column, just referenced by URL from whatever body text
# happens to link to them, so there's no automatic cleanup when a post/
# project is deleted (matching the personal-site scale this is built for;
# an orphaned image now and then isn't worth a reference-counting system).
# ---------------------------------------------------------------------------
# Tests point these at temporary upload directories via the
# PORTFOLIO_IMAGE_DIR / CONTENT_IMAGE_DIR environment variables (see the
# project root conftest.py) so they never write into the real
# static/images/ folders. Normal local dev and production never set these,
# so they resolve to the same hardcoded folders as before.
PORTFOLIO_IMAGE_DIR = os.environ.get(
    "PORTFOLIO_IMAGE_DIR", os.path.join(PROJECT_ROOT, "static", "images", "portfolio")
)
CONTENT_IMAGE_DIR = os.environ.get(
    "CONTENT_IMAGE_DIR", os.path.join(PROJECT_ROOT, "static", "images", "uploads")
)
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

# Flask/Werkzeug reject any request whose body exceeds this before the view
# function even runs, raising a 413 that's handled by the errorhandler below.
app.config["MAX_CONTENT_LENGTH"] = MAX_IMAGE_SIZE_BYTES

# ---------------------------------------------------------------------------
# SECRET_KEY signs Flask's session cookie. This app keeps two things in the
# session: one-time flash messages ("Post published.", "Project deleted.",
# etc. -- see flash() calls below) and the preview_mode flag (see
# /admin/preview/*) -- but Flask requires a secret key to sign that cookie
# at all. Set a real SECRET_KEY environment variable before deploying
# anywhere public -- the fallback below is fixed (so it survives app
# restarts during local dev) and must NOT be relied on outside your own
# machine, exactly like the ADMIN_USERNAME/ADMIN_PASSWORD fallback just
# below.
# ---------------------------------------------------------------------------
app.secret_key = os.environ.get(
    "SECRET_KEY", "local-dev-only-secret-key-9f2b6e4a1d7c8035-do-not-use-in-production"
)


# ---------------------------------------------------------------------------
# Analytics: a page_views table that isn't part of init_db.py's normal
# create-and-seed flow, because that script drops and recreates every table
# from scratch -- fine for a fresh dev database, but running it against the
# live production database would destroy every real post/project/video
# that's been added since launch. This runs once at import time instead and
# only ever adds the table if it's missing, so it's safe to deploy against
# an existing database with real data in it.
# ---------------------------------------------------------------------------
def _ensure_page_views_table():
    connection = get_db_connection()
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS page_views (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            visitor_id TEXT NOT NULL,
            viewed_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_page_views_viewed_at ON page_views (viewed_at);
        """
    )
    connection.commit()
    connection.close()


_ensure_page_views_table()


# ---------------------------------------------------------------------------
# Portfolio schema migrations. SQLite's ALTER TABLE can't drop a column or
# split one column's data into two on every version still in the wild, so
# each step below rebuilds the table instead -- idempotent (a no-op once
# already migrated) and safe to run against the live database.
#
# History: originally required a manually-typed emoji `icon` for the
# gradient-placeholder fallback (dropped once every new project got a
# standardized gradient instead, so a plain gradient with no icon renders
# fine). Then a single `description` shown identically on both the grid
# card and the detail page (split into a short `excerpt`, shown on cards,
# and a longer `body`, shown only on the detail page -- same shape as
# `posts`) plus an optional `project_url` link to a repo/live demo.
# ---------------------------------------------------------------------------
def _ensure_portfolio_schema():
    connection = get_db_connection()
    table_exists = (
        connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'portfolio_items'"
        ).fetchone()
        is not None
    )
    # Nothing to migrate if the table doesn't exist yet at all -- that's a
    # database that's never had init_db.py run against it (fresh test DB,
    # fresh clone), and init_schema() there already creates the table with
    # today's correct columns directly.
    columns = (
        {row["name"] for row in connection.execute("PRAGMA table_info(portfolio_items)")}
        if table_exists
        else set()
    )
    if table_exists and "excerpt" not in columns:
        connection.executescript(
            """
            CREATE TABLE portfolio_items_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                excerpt TEXT NOT NULL,
                body TEXT NOT NULL,
                color_start TEXT NOT NULL,
                color_end TEXT NOT NULL,
                image_filename TEXT,
                project_url TEXT
            );
            INSERT INTO portfolio_items_new
                (id, title, excerpt, body, color_start, color_end, image_filename)
                SELECT id, title, description, description, color_start, color_end, image_filename
                FROM portfolio_items;
            DROP TABLE portfolio_items;
            ALTER TABLE portfolio_items_new RENAME TO portfolio_items;
            """
        )
        connection.commit()
    connection.close()


_ensure_portfolio_schema()


# ---------------------------------------------------------------------------
# Pinning: lets the site owner pin specific projects to the top of the
# /portfolio grid and into the homepage's Featured Work section, instead of
# those always just being whichever projects happen to have the lowest ids.
# A plain ALTER TABLE ADD COLUMN suffices here (unlike the rebuilds above)
# since SQLite has always supported adding a column, just not dropping or
# renaming one on every version still in the wild.
# ---------------------------------------------------------------------------
def _ensure_portfolio_pinned_column():
    connection = get_db_connection()
    table_exists = (
        connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'portfolio_items'"
        ).fetchone()
        is not None
    )
    if table_exists:
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(portfolio_items)")}
        if "pinned" not in columns:
            connection.execute(
                "ALTER TABLE portfolio_items ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0"
            )
            connection.commit()
    connection.close()


_ensure_portfolio_pinned_column()


# ---------------------------------------------------------------------------
# Videos originally had one `description` column shown in full, verbatim,
# in both the grid card teaser and the detail page -- fine for a one-line
# description, but a real problem once someone writes an actual multi-
# paragraph write-up: the grid card grows to fit the entire thing instead
# of staying a short teaser. Splits it into `excerpt` (short, grid card)
# and `body` (full write-up, Markdown-rendered, detail page only) -- same
# shape `posts` and `portfolio_items` already have, for the same reason.
# Existing rows get their old description copied into both columns as a
# starting point (nothing vanishes), same rebuild-the-table approach as
# the portfolio excerpt/body migration above, since SQLite can't split one
# column's data into two via ALTER TABLE.
# ---------------------------------------------------------------------------
def _ensure_video_schema():
    connection = get_db_connection()
    table_exists = (
        connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'videos'"
        ).fetchone()
        is not None
    )
    if table_exists:
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(videos)")}
        if "excerpt" not in columns:
            connection.executescript(
                """
                CREATE TABLE videos_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    excerpt TEXT NOT NULL,
                    body TEXT NOT NULL,
                    duration TEXT NOT NULL,
                    color_start TEXT NOT NULL,
                    color_end TEXT NOT NULL,
                    video_url TEXT
                );
                INSERT INTO videos_new
                    (id, title, excerpt, body, duration, color_start, color_end, video_url)
                    SELECT id, title, description, description, duration, color_start, color_end, video_url
                    FROM videos;
                DROP TABLE videos;
                ALTER TABLE videos_new RENAME TO videos;
                """
            )
            connection.commit()
    connection.close()


_ensure_video_schema()


def _has_allowed_image_extension(filename):
    """Real allowlist check against the actual file extension -- never trust
    a client-supplied Content-Type/MIME header for this."""
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_IMAGE_EXTENSIONS


def save_portfolio_image(file_storage):
    """Save an uploaded portfolio image under a safe, collision-proof name
    and return just the filename (what gets stored in the database)."""
    os.makedirs(PORTFOLIO_IMAGE_DIR, exist_ok=True)
    safe_original = secure_filename(file_storage.filename)
    ext = os.path.splitext(safe_original)[1].lower()
    generated_name = f"{uuid.uuid4().hex}{ext}"
    file_storage.save(os.path.join(PORTFOLIO_IMAGE_DIR, generated_name))
    return generated_name


def delete_portfolio_image(filename):
    """Remove a previously-uploaded portfolio image from disk, if present."""
    if not filename:
        return
    path = os.path.join(PORTFOLIO_IMAGE_DIR, filename)
    if os.path.isfile(path):
        os.remove(path)


def save_content_image(file_storage):
    """Save an image uploaded via /admin/upload-image (for inline Markdown
    images) under a safe, collision-proof name and return the URL path to
    reference it from a blog post or portfolio write-up's body text."""
    os.makedirs(CONTENT_IMAGE_DIR, exist_ok=True)
    safe_original = secure_filename(file_storage.filename)
    ext = os.path.splitext(safe_original)[1].lower()
    generated_name = f"{uuid.uuid4().hex}{ext}"
    file_storage.save(os.path.join(CONTENT_IMAGE_DIR, generated_name))
    return url_for("static", filename=f"images/uploads/{generated_name}")


# ---------------------------------------------------------------------------
# Markdown rendering for blog post / portfolio project body text. Only the
# authenticated site owner can ever write this content (every route that
# saves a body is require_auth-gated, and there's no comment system or any
# other way for a visitor to submit text) -- the rendered HTML is trusted
# to the exact same degree the raw Python/template code already is, so it's
# marked safe and passed through to the page unescaped rather than run
# through an HTML sanitizer.
# ---------------------------------------------------------------------------
def render_markdown(text):
    # nl2br: a single Enter press (one newline, no blank line) becomes a
    # real line break instead of being silently swallowed. Standard
    # Markdown only starts a new paragraph on a blank line -- technically
    # correct, but surprising for anyone not already fluent in Markdown's
    # conventions, and this app is meant to be typed into by exactly one
    # person who shouldn't have to learn that rule first.
    html = markdown_lib.markdown(text, extensions=["extra", "sane_lists", "nl2br"])
    return Markup(html)


app.jinja_env.filters["markdown"] = render_markdown


# ---------------------------------------------------------------------------
# Placeholder thumbnails (portfolio + video): rather than asking for a
# gradient every time, every new project/video gets the same standardized
# gradient (matching the site's own --primary/--accent brand colors).
# Editing never touches the stored colors, so this only affects
# newly-created rows.
# ---------------------------------------------------------------------------
DEFAULT_PORTFOLIO_COLOR_START = "#0d9488"
DEFAULT_PORTFOLIO_COLOR_END = "#ffbb54"
DEFAULT_VIDEO_COLOR_START = "#0d9488"
DEFAULT_VIDEO_COLOR_END = "#ffbb54"


def _looks_like_youtube_url(url):
    lowered = url.lower()
    return "youtube.com" in lowered or "youtu.be" in lowered


def _format_duration(total_seconds):
    total_seconds = int(total_seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def extract_youtube_duration(url):
    """Best-effort: ask yt-dlp for a YouTube video's length and format it
    as M:SS (or H:MM:SS for longer videos). Returns None on any failure
    (private/deleted video, network hiccup, not actually a YouTube link,
    etc.) so callers fall back to asking for it manually rather than
    blowing up the whole request."""
    try:
        with yt_dlp.YoutubeDL(
            {"quiet": True, "no_warnings": True, "skip_download": True, "socket_timeout": 8}
        ) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:
        return None

    seconds = info.get("duration") if info else None
    if not seconds:
        return None
    return _format_duration(seconds)


# ---------------------------------------------------------------------------
# Auth: this is a single-owner personal site, so a full user/session system
# would be overkill. All write routes (create/edit/delete for posts and
# portfolio items) are protected with plain HTTP Basic Auth instead. Set
# ADMIN_USERNAME / ADMIN_PASSWORD as environment variables before deploying
# anywhere public -- "admin" / "changeme" is a local-dev-only fallback and
# must NOT be relied on outside your own machine.
# ---------------------------------------------------------------------------
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "changeme")


def _credentials_valid(username, password):
    # secrets.compare_digest avoids leaking timing information about how
    # much of the supplied credentials matched.
    return username is not None and password is not None and secrets.compare_digest(
        username, ADMIN_USERNAME
    ) and secrets.compare_digest(password, ADMIN_PASSWORD)


def _has_admin_credentials():
    """True if the current request's browser-cached Basic Auth credentials
    are valid, regardless of preview mode (see is_authenticated())."""
    auth = request.authorization
    return bool(auth and _credentials_valid(auth.username, auth.password))


def is_authenticated():
    """True if the current request should see admin management controls.

    Used to hide management controls (New/Edit/Delete) from anonymous
    visitors on read-only pages. This is a UX nicety, not the real security
    boundary -- the write routes themselves still enforce auth via
    require_auth regardless of what a template does or doesn't render.

    Valid credentials alone aren't enough: an admin who has switched into
    preview mode (/admin/preview/start) still has those credentials cached
    in their browser, but should see the site exactly as a visitor would
    until they exit preview (/admin/preview/stop).
    """
    return _has_admin_credentials() and not session.get("preview_mode", False)


@app.context_processor
def inject_auth_state():
    """Makes is_authenticated and previewing available in every template
    automatically, so the preview-mode banner in base.html doesn't need
    every single route to remember to pass it in."""
    return {
        "is_authenticated": is_authenticated(),
        "previewing": _has_admin_credentials() and session.get("preview_mode", False),
    }


def require_auth(view):
    """Decorator that gates a route behind HTTP Basic Auth."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        auth = request.authorization
        if not auth or not _credentials_valid(auth.username, auth.password):
            return Response(
                "Authentication required to manage content on this site.",
                401,
                {"WWW-Authenticate": 'Basic realm="Admin Area"'},
            )
        return view(*args, **kwargs)

    return wrapped


# ---------------------------------------------------------------------------
# Visitor analytics: counts page views per content page without tracking
# anything identifying. No IP address or user agent is ever stored -- just
# a random per-browser cookie (VISITOR_COOKIE_NAME) so repeat visits from
# the same browser count as one visitor instead of one per page view. The
# site owner's own browsing never gets counted: any request carrying valid
# admin credentials is skipped outright, regardless of preview mode. That's
# deliberately _has_admin_credentials() and not is_authenticated() -- the
# point is to exclude the owner's own traffic, and browsing in preview mode
# is still the owner's traffic, not a real visitor's.
# ---------------------------------------------------------------------------
TRACKED_ENDPOINTS = {
    "home",
    "portfolio",
    "portfolio_detail",
    "blog_list",
    "blog_post",
    "videos",
    "video_detail",
}
VISITOR_COOKIE_NAME = "visitor_id"
VISITOR_COOKIE_MAX_AGE = 60 * 60 * 24 * 365 * 2  # 2 years


@app.after_request
def _record_page_view(response):
    if (
        request.method != "GET"
        or request.endpoint not in TRACKED_ENDPOINTS
        or response.status_code >= 400
        or _has_admin_credentials()
    ):
        return response

    visitor_id = request.cookies.get(VISITOR_COOKIE_NAME)
    if not visitor_id:
        visitor_id = uuid.uuid4().hex
        response.set_cookie(
            VISITOR_COOKIE_NAME,
            visitor_id,
            max_age=VISITOR_COOKIE_MAX_AGE,
            httponly=True,
            samesite="Lax",
        )

    connection = get_db_connection()
    connection.execute(
        "INSERT INTO page_views (path, endpoint, visitor_id, viewed_at) VALUES (?, ?, ?, ?)",
        (request.path, request.endpoint, visitor_id, datetime.now(timezone.utc).isoformat()),
    )
    connection.commit()
    connection.close()
    return response


def get_all_tags():
    connection = get_db_connection()
    tags = [
        row["tag"]
        for row in connection.execute(
            "SELECT DISTINCT tag FROM posts ORDER BY tag"
        ).fetchall()
    ]
    connection.close()
    return tags


def normalize_tag(connection, tag, exclude_post_id=None):
    """Reduce accidental duplicate tags caused by typos in case or spacing.

    If an existing tag in `posts` matches `tag` case-insensitively (after
    stripping whitespace on both sides), return that existing tag's exact
    stored casing instead -- so typing "sql" when "SQL" already exists
    reuses "SQL" rather than creating a near-duplicate "sql" tag. A
    genuinely new tag is returned unchanged (already stripped by the
    caller). `exclude_post_id` leaves the post currently being edited out
    of the comparison, so a post that's the *only* one using a given tag
    can still have that tag's own casing corrected.
    """
    query = "SELECT tag FROM posts WHERE LOWER(TRIM(tag)) = LOWER(?)"
    params = [tag]
    if exclude_post_id is not None:
        query += " AND id != ?"
        params.append(exclude_post_id)
    query += " LIMIT 1"
    existing = connection.execute(query, params).fetchone()
    return existing["tag"] if existing else tag


def format_display_date(date_iso):
    """Turn '2026-07-18' into 'July 18, 2026' without relying on
    platform-specific strftime flags (Windows doesn't support %-d)."""
    dt = datetime.strptime(date_iso, "%Y-%m-%d")
    return f"{dt.strftime('%B')} {dt.day}, {dt.year}"


# ---------------------------------------------------------------------------
# Cache-busting for static assets whose URL never changes on its own (CSS,
# the site logo, the Markdown toolbar script): browsers can and do keep
# serving a stale cached copy indefinitely after an edit. Appending
# ?v=<file mtime> to the URL (see base.html) means the URL itself changes
# whenever the file's contents change, forcing a fresh fetch without
# needing a manual version bump.
# ---------------------------------------------------------------------------
def _file_mtime_version(*relative_path_parts):
    path = os.path.join(PROJECT_ROOT, "static", *relative_path_parts)
    try:
        return int(os.path.getmtime(path))
    except OSError:
        return 0


@app.context_processor
def inject_asset_version():
    return {
        "asset_version": _file_mtime_version("css", "style.css"),
        "logo_version": _file_mtime_version("images", "FlameMeem1.png"),
        "js_version": _file_mtime_version("js", "markdown-toolbar.js"),
    }


_YOUTUBE_ID_RE = re.compile(
    r"(?:youtube(?:-nocookie)?\.com/(?:watch\?(?:.*&)?v=|embed/|shorts/)|youtu\.be/)"
    r"([A-Za-z0-9_-]{11})"
)


def youtube_video_id(url):
    """Pull the 11-character video id out of a YouTube URL (watch, youtu.be,
    embed, or shorts links all work). Returns None for anything else, so
    templates can branch on it to decide between a real thumbnail/embed and
    the CSS-gradient placeholder."""
    if not url:
        return None
    match = _YOUTUBE_ID_RE.search(url)
    return match.group(1) if match else None


app.jinja_env.filters["youtube_id"] = youtube_video_id


@app.route("/")
def home():
    connection = get_db_connection()
    recent_posts = connection.execute(
        "SELECT * FROM posts ORDER BY date_iso DESC LIMIT 3"
    ).fetchall()
    featured_items = connection.execute(
        "SELECT * FROM portfolio_items ORDER BY pinned DESC, id ASC LIMIT 3"
    ).fetchall()
    connection.close()
    return render_template(
        "index.html", recent_posts=recent_posts, featured_items=featured_items
    )


@app.route("/portfolio")
def portfolio():
    connection = get_db_connection()
    items = connection.execute(
        "SELECT * FROM portfolio_items ORDER BY pinned DESC, id ASC"
    ).fetchall()
    connection.close()
    return render_template(
        "portfolio.html", items=items
    )


@app.route("/portfolio/new", methods=["GET", "POST"])
@require_auth
def portfolio_new():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        excerpt = request.form.get("excerpt", "").strip()
        body = request.form.get("body", "").strip()
        project_url = request.form.get("project_url", "").strip() or None
        image_file = request.files.get("image")
        has_upload = image_file is not None and image_file.filename.strip() != ""

        error = None
        if not title or not excerpt or not body:
            error = "Please fill out every field before saving."
        elif has_upload and not _has_allowed_image_extension(image_file.filename):
            error = (
                "That image type isn't supported -- please upload a "
                ".png, .jpg, .jpeg, .gif, or .webp file (5MB max)."
            )

        if error:
            return render_template(
                "portfolio_form.html", error=error, form=request.form, item=None
            )

        image_filename = save_portfolio_image(image_file) if has_upload else None

        try:
            connection = get_db_connection()
            connection.execute(
                """
                INSERT INTO portfolio_items
                    (title, excerpt, body, color_start, color_end, image_filename, project_url)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    title,
                    excerpt,
                    body,
                    DEFAULT_PORTFOLIO_COLOR_START,
                    DEFAULT_PORTFOLIO_COLOR_END,
                    image_filename,
                    project_url,
                ),
            )
            connection.commit()
            connection.close()
        except Exception:
            # Don't leave an orphaned file on disk if the database write failed.
            delete_portfolio_image(image_filename)
            raise
        flash("Project added.")
        return redirect(url_for("portfolio"))

    return render_template("portfolio_form.html", error=None, form={}, item=None)


@app.route("/portfolio/<int:item_id>")
def portfolio_detail(item_id):
    connection = get_db_connection()
    item = connection.execute(
        "SELECT * FROM portfolio_items WHERE id = ?", (item_id,)
    ).fetchone()
    connection.close()
    if item is None:
        abort(404)
    return render_template("portfolio_detail.html", item=item)


@app.route("/portfolio/<int:item_id>/edit", methods=["GET", "POST"])
@require_auth
def portfolio_edit(item_id):
    connection = get_db_connection()
    item = connection.execute(
        "SELECT * FROM portfolio_items WHERE id = ?", (item_id,)
    ).fetchone()
    if item is None:
        connection.close()
        abort(404)

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        excerpt = request.form.get("excerpt", "").strip()
        body = request.form.get("body", "").strip()
        project_url = request.form.get("project_url", "").strip() or None
        image_file = request.files.get("image")
        has_upload = image_file is not None and image_file.filename.strip() != ""

        error = None
        if not title or not excerpt or not body:
            error = "Please fill out every field before saving."
        elif has_upload and not _has_allowed_image_extension(image_file.filename):
            error = (
                "That image type isn't supported -- please upload a "
                ".png, .jpg, .jpeg, .gif, or .webp file (5MB max)."
            )

        if error:
            connection.close()
            return render_template(
                "portfolio_form.html", error=error, form=request.form, item=item
            )

        old_image_filename = item["image_filename"]
        image_filename = old_image_filename
        if has_upload:
            image_filename = save_portfolio_image(image_file)

        try:
            # Colors are intentionally left untouched here -- new projects
            # get a standardized gradient (see portfolio_new), but editing
            # never changes a project's existing colors.
            connection.execute(
                """
                UPDATE portfolio_items
                SET title = ?, excerpt = ?, body = ?, image_filename = ?, project_url = ?
                WHERE id = ?
                """,
                (title, excerpt, body, image_filename, project_url, item_id),
            )
            connection.commit()
            connection.close()
        except Exception:
            # Don't leave an orphaned new file on disk if the database write failed.
            if has_upload:
                delete_portfolio_image(image_filename)
            raise

        # Only remove the old file once the new row has actually been saved.
        if has_upload:
            delete_portfolio_image(old_image_filename)
        flash("Project updated.")
        return redirect(url_for("portfolio_detail", item_id=item_id))

    connection.close()
    form = {
        "title": item["title"],
        "excerpt": item["excerpt"],
        "body": item["body"],
        "project_url": item["project_url"] or "",
    }
    return render_template("portfolio_form.html", error=None, form=form, item=item)


@app.route("/portfolio/<int:item_id>/delete", methods=["POST"])
@require_auth
def portfolio_delete(item_id):
    connection = get_db_connection()
    item = connection.execute(
        "SELECT image_filename FROM portfolio_items WHERE id = ?", (item_id,)
    ).fetchone()
    if item is None:
        connection.close()
        abort(404)
    connection.execute("DELETE FROM portfolio_items WHERE id = ?", (item_id,))
    connection.commit()
    connection.close()
    delete_portfolio_image(item["image_filename"])
    flash("Project deleted.")
    return redirect(url_for("portfolio"))


@app.route("/portfolio/<int:item_id>/pin", methods=["POST"])
@require_auth
def portfolio_toggle_pin(item_id):
    """Pinned projects sort first on both /portfolio and the homepage's
    Featured Work section (see the ORDER BY pinned DESC, id ASC in the
    portfolio() and home() routes) -- one flag drives both places rather
    than needing separate controls for each."""
    connection = get_db_connection()
    item = connection.execute(
        "SELECT pinned FROM portfolio_items WHERE id = ?", (item_id,)
    ).fetchone()
    if item is None:
        connection.close()
        abort(404)
    newly_pinned = not item["pinned"]
    connection.execute(
        "UPDATE portfolio_items SET pinned = ? WHERE id = ?", (int(newly_pinned), item_id)
    )
    connection.commit()
    connection.close()
    flash("Project pinned to the top." if newly_pinned else "Project unpinned.")
    return _redirect_back()


POSTS_PER_PAGE = 5


@app.route("/blog")
def blog_list():
    selected_tag = request.args.get("tag", "").strip()
    search_query = request.args.get("q", "").strip()

    try:
        page = int(request.args.get("page", "1"))
    except ValueError:
        page = 1
    page = max(page, 1)

    # Build the WHERE clause piece by piece -- every value that comes from
    # the querystring is still passed through as a parameterized `?`
    # placeholder, never string-formatted into the SQL itself.
    conditions = []
    params = []
    if selected_tag:
        conditions.append("tag = ?")
        params.append(selected_tag)
    if search_query:
        like_pattern = f"%{search_query}%"
        # SQLite's LIKE is case-insensitive for ASCII by default, so this
        # covers "case-insensitive substring match" without extra LOWER()
        # calls on every row.
        conditions.append("(title LIKE ? OR excerpt LIKE ? OR body LIKE ?)")
        params.extend([like_pattern, like_pattern, like_pattern])
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    connection = get_db_connection()
    total_posts = connection.execute(
        f"SELECT COUNT(*) AS n FROM posts {where_clause}", params
    ).fetchone()["n"]
    total_pages = max(1, -(-total_posts // POSTS_PER_PAGE))  # ceiling division
    page = min(page, total_pages)
    offset = (page - 1) * POSTS_PER_PAGE

    posts = connection.execute(
        f"SELECT * FROM posts {where_clause} ORDER BY date_iso DESC LIMIT ? OFFSET ?",
        params + [POSTS_PER_PAGE, offset],
    ).fetchall()
    connection.close()

    # Only the filters that are actually active get carried over into the
    # Previous/Next/tag-pill links -- keeps URLs clean when no filter is set.
    filter_args = {}
    if selected_tag:
        filter_args["tag"] = selected_tag
    if search_query:
        filter_args["q"] = search_query

    return render_template(
        "blog_list.html",
        posts=posts,
        tags=get_all_tags(),
        selected_tag=selected_tag,
        search_query=search_query,
        page=page,
        total_pages=total_pages,
        has_prev=page > 1,
        has_next=page < total_pages,
        filter_args=filter_args,
    )


@app.route("/blog/new", methods=["GET", "POST"])
@require_auth
def blog_new():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        date_iso = request.form.get("date", "").strip()
        tag = request.form.get("tag", "").strip()
        excerpt = request.form.get("excerpt", "").strip()
        body = request.form.get("body", "").strip()

        error = None
        if not title or not date_iso or not tag or not excerpt or not body:
            error = "Please fill out every field before publishing."
        else:
            try:
                date_display = format_display_date(date_iso)
            except ValueError:
                error = "That date doesn't look right -- please use the date picker."

        if error:
            return render_template(
                "blog_new.html",
                error=error,
                form=request.form,
                tags=get_all_tags(),
                post=None,
            )

        connection = get_db_connection()
        tag = normalize_tag(connection, tag)
        connection.execute(
            """
            INSERT INTO posts (title, date_iso, date_display, tag, excerpt, body)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (title, date_iso, date_display, tag, excerpt, body),
        )
        connection.commit()
        connection.close()
        flash("Post published.")
        return redirect(url_for("blog_list"))

    return render_template(
        "blog_new.html", error=None, form={}, tags=get_all_tags(), post=None
    )


@app.route("/blog/<int:post_id>")
def blog_post(post_id):
    connection = get_db_connection()
    post = connection.execute(
        "SELECT * FROM posts WHERE id = ?", (post_id,)
    ).fetchone()
    connection.close()
    if post is None:
        abort(404)
    return render_template(
        "blog_post.html", post=post
    )


@app.route("/blog/<int:post_id>/edit", methods=["GET", "POST"])
@require_auth
def blog_edit(post_id):
    connection = get_db_connection()
    post = connection.execute(
        "SELECT * FROM posts WHERE id = ?", (post_id,)
    ).fetchone()
    if post is None:
        connection.close()
        abort(404)

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        date_iso = request.form.get("date", "").strip()
        tag = request.form.get("tag", "").strip()
        excerpt = request.form.get("excerpt", "").strip()
        body = request.form.get("body", "").strip()

        error = None
        if not title or not date_iso or not tag or not excerpt or not body:
            error = "Please fill out every field before saving."
        else:
            try:
                date_display = format_display_date(date_iso)
            except ValueError:
                error = "That date doesn't look right -- please use the date picker."

        if error:
            connection.close()
            return render_template(
                "blog_new.html",
                error=error,
                form=request.form,
                tags=get_all_tags(),
                post=post,
            )

        tag = normalize_tag(connection, tag, exclude_post_id=post_id)
        connection.execute(
            """
            UPDATE posts
            SET title = ?, date_iso = ?, date_display = ?, tag = ?, excerpt = ?, body = ?
            WHERE id = ?
            """,
            (title, date_iso, date_display, tag, excerpt, body, post_id),
        )
        connection.commit()
        connection.close()
        flash("Post updated.")
        return redirect(url_for("blog_post", post_id=post_id))

    connection.close()
    form = {
        "title": post["title"],
        "date": post["date_iso"],
        "tag": post["tag"],
        "excerpt": post["excerpt"],
        "body": post["body"],
    }
    return render_template(
        "blog_new.html", error=None, form=form, tags=get_all_tags(), post=post
    )


@app.route("/blog/<int:post_id>/delete", methods=["POST"])
@require_auth
def blog_delete(post_id):
    connection = get_db_connection()
    post = connection.execute(
        "SELECT id FROM posts WHERE id = ?", (post_id,)
    ).fetchone()
    if post is None:
        connection.close()
        abort(404)
    connection.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    connection.commit()
    connection.close()
    flash("Post deleted.")
    return redirect(url_for("blog_list"))


@app.route("/videos")
def videos():
    connection = get_db_connection()
    all_videos = connection.execute("SELECT * FROM videos ORDER BY id").fetchall()
    connection.close()
    return render_template(
        "videos.html", videos=all_videos
    )


@app.route("/videos/new", methods=["GET", "POST"])
@require_auth
def video_new():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        excerpt = request.form.get("excerpt", "").strip()
        body = request.form.get("body", "").strip()
        manual_duration = request.form.get("duration", "").strip()
        video_url = request.form.get("video_url", "").strip() or None

        duration = manual_duration
        detected = False
        if video_url and _looks_like_youtube_url(video_url):
            extracted = extract_youtube_duration(video_url)
            if extracted:
                duration = extracted
                detected = True

        error = None
        if not title or not excerpt or not body:
            error = "Please fill out every field before saving."
        elif not duration:
            error = (
                "Couldn't detect the duration automatically from that link -- "
                "please enter it manually (e.g. 8:14)."
            )

        if error:
            return render_template(
                "video_form.html", error=error, form=request.form, video=None
            )

        connection = get_db_connection()
        connection.execute(
            """
            INSERT INTO videos (title, excerpt, body, duration, color_start, color_end, video_url)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title,
                excerpt,
                body,
                duration,
                DEFAULT_VIDEO_COLOR_START,
                DEFAULT_VIDEO_COLOR_END,
                video_url,
            ),
        )
        connection.commit()
        connection.close()
        flash(f"Video added -- duration detected automatically ({duration})." if detected else "Video added.")
        return redirect(url_for("videos"))

    return render_template("video_form.html", error=None, form={}, video=None)


@app.route("/videos/<int:video_id>")
def video_detail(video_id):
    connection = get_db_connection()
    video = connection.execute(
        "SELECT * FROM videos WHERE id = ?", (video_id,)
    ).fetchone()
    connection.close()
    if video is None:
        abort(404)
    return render_template(
        "video_detail.html", video=video
    )


@app.route("/videos/<int:video_id>/edit", methods=["GET", "POST"])
@require_auth
def video_edit(video_id):
    connection = get_db_connection()
    video = connection.execute(
        "SELECT * FROM videos WHERE id = ?", (video_id,)
    ).fetchone()
    if video is None:
        connection.close()
        abort(404)

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        excerpt = request.form.get("excerpt", "").strip()
        body = request.form.get("body", "").strip()
        manual_duration = request.form.get("duration", "").strip()
        video_url = request.form.get("video_url", "").strip() or None

        duration = manual_duration
        detected = False
        if video_url and _looks_like_youtube_url(video_url):
            extracted = extract_youtube_duration(video_url)
            if extracted:
                duration = extracted
                detected = True

        error = None
        if not title or not excerpt or not body:
            error = "Please fill out every field before saving."
        elif not duration:
            error = (
                "Couldn't detect the duration automatically from that link -- "
                "please enter it manually (e.g. 8:14)."
            )

        if error:
            connection.close()
            return render_template(
                "video_form.html", error=error, form=request.form, video=video
            )

        # Colors are intentionally left untouched here -- new videos get a
        # standardized gradient (see video_new), but editing never changes
        # a video's existing colors.
        connection.execute(
            """
            UPDATE videos
            SET title = ?, excerpt = ?, body = ?, duration = ?, video_url = ?
            WHERE id = ?
            """,
            (title, excerpt, body, duration, video_url, video_id),
        )
        connection.commit()
        connection.close()
        flash(f"Video updated -- duration detected automatically ({duration})." if detected else "Video updated.")
        return redirect(url_for("video_detail", video_id=video_id))

    connection.close()
    form = {
        "title": video["title"],
        "excerpt": video["excerpt"],
        "body": video["body"],
        "duration": video["duration"],
        "video_url": video["video_url"] or "",
    }
    return render_template("video_form.html", error=None, form=form, video=video)


@app.route("/videos/<int:video_id>/delete", methods=["POST"])
@require_auth
def video_delete(video_id):
    connection = get_db_connection()
    video = connection.execute(
        "SELECT id FROM videos WHERE id = ?", (video_id,)
    ).fetchone()
    if video is None:
        connection.close()
        abort(404)
    connection.execute("DELETE FROM videos WHERE id = ?", (video_id,))
    connection.commit()
    connection.close()
    flash("Video deleted.")
    return redirect(url_for("videos"))


@app.route("/admin")
@require_auth
def admin():
    """No dashboard of its own -- just a stable, always-linked URL that
    exists purely to trigger the browser's login prompt. Once your browser
    has valid credentials cached, every page's New/Edit/Delete controls
    show up on their own (see is_authenticated()), so this just redirects
    straight to the blog afterward."""
    return redirect(url_for("blog_list"))


def _redirect_back():
    """Redirect to the page the request came from, falling back to the
    homepage. Only trusts Referer when it points back at this same site --
    the header is browser-supplied from wherever you actually just were,
    never attacker-controlled input, but this keeps it from ever sending
    you somewhere else entirely if a browser sends something unexpected."""
    referrer = request.referrer
    if referrer and referrer.startswith(request.host_url):
        return redirect(referrer)
    return redirect(url_for("home"))


@app.route("/admin/preview/start")
@require_auth
def admin_preview_start():
    """Lets the logged-in admin browse the site as an anonymous visitor
    would -- New/Edit/Delete controls hidden -- without logging out. The
    browser keeps sending its cached Basic Auth credentials the whole time
    (require_auth above still honors them), so exiting preview never
    requires typing the password again."""
    session["preview_mode"] = True
    flash("Previewing as a visitor. Admin controls are hidden until you exit preview.")
    return _redirect_back()


@app.route("/admin/preview/stop")
@require_auth
def admin_preview_stop():
    session.pop("preview_mode", None)
    flash("Exited preview mode.")
    return _redirect_back()


@app.route("/admin/upload-image", methods=["GET", "POST"])
@require_auth
def admin_upload_image():
    """A small standalone utility, not tied to any specific post/project:
    upload an image, get back a URL to paste into a Markdown body as
    `![](url)`. Exists because inline images in blog/portfolio write-ups
    need a real URL to point at, and this is the only way to get one for
    anything beyond a portfolio item's single thumbnail.

    Also the endpoint the toolbar's Image button (see
    static/js/markdown-toolbar.js) uploads to directly via fetch(), rather
    than a separate route -- same validation, same save_content_image()
    call, just a JSON response instead of a rendered page when the request
    asks for one via an Accept header, so one code path serves both the
    JS-driven toolbar and the plain-HTML fallback page."""
    wants_json = "application/json" in request.headers.get("Accept", "")
    uploaded_url = None
    error = None

    if request.method == "POST":
        image_file = request.files.get("image")
        has_upload = image_file is not None and image_file.filename.strip() != ""

        if not has_upload:
            error = "Choose an image file first."
        elif not _has_allowed_image_extension(image_file.filename):
            error = (
                "That image type isn't supported -- please upload a "
                ".png, .jpg, .jpeg, .gif, or .webp file (5MB max)."
            )
        else:
            uploaded_url = save_content_image(image_file)

        if wants_json:
            if error:
                return {"error": error}, 400
            return {"url": uploaded_url}

    return render_template("admin_upload_image.html", uploaded_url=uploaded_url, error=error)


ANALYTICS_PAGE_LABELS = {
    "home": "Home",
    "portfolio": "Portfolio",
    "portfolio_detail": "Project",
    "blog_list": "Blog",
    "blog_post": "Blog post",
    "videos": "Videos",
    "video_detail": "Video",
}

ANALYTICS_DAILY_CHART_DAYS = 14


@app.route("/admin/analytics")
@require_auth
def analytics():
    connection = get_db_connection()

    total_views = connection.execute("SELECT COUNT(*) AS n FROM page_views").fetchone()["n"]
    unique_visitors = connection.execute(
        "SELECT COUNT(DISTINCT visitor_id) AS n FROM page_views"
    ).fetchone()["n"]

    now = datetime.now(timezone.utc)
    views_last_7_days = connection.execute(
        "SELECT COUNT(*) AS n FROM page_views WHERE viewed_at >= ?",
        ((now - timedelta(days=7)).isoformat(),),
    ).fetchone()["n"]
    views_last_30_days = connection.execute(
        "SELECT COUNT(*) AS n FROM page_views WHERE viewed_at >= ?",
        ((now - timedelta(days=30)).isoformat(),),
    ).fetchone()["n"]

    top_pages = connection.execute(
        """
        SELECT path, endpoint, COUNT(*) AS views
        FROM page_views
        GROUP BY path, endpoint
        ORDER BY views DESC, path ASC
        LIMIT 10
        """
    ).fetchall()

    # One grouped query for the whole chart window instead of one query per
    # day -- viewed_at is an ISO timestamp, so its first 10 characters are
    # always that visit's calendar day (YYYY-MM-DD) in UTC.
    chart_start_day = (now - timedelta(days=ANALYTICS_DAILY_CHART_DAYS - 1)).date()
    rows = connection.execute(
        """
        SELECT substr(viewed_at, 1, 10) AS day, COUNT(*) AS n
        FROM page_views
        WHERE substr(viewed_at, 1, 10) >= ?
        GROUP BY day
        """,
        (chart_start_day.isoformat(),),
    ).fetchall()
    connection.close()

    views_by_day = {row["day"]: row["n"] for row in rows}
    daily_counts = []
    for days_ago in range(ANALYTICS_DAILY_CHART_DAYS - 1, -1, -1):
        day = (now - timedelta(days=days_ago)).date()
        daily_counts.append(
            {
                "label": f"{day.strftime('%b')} {day.day}",
                "count": views_by_day.get(day.isoformat(), 0),
            }
        )
    max_daily_count = max((day["count"] for day in daily_counts), default=0)

    return render_template(
        "analytics.html",
        total_views=total_views,
        unique_visitors=unique_visitors,
        views_last_7_days=views_last_7_days,
        views_last_30_days=views_last_30_days,
        top_pages=top_pages,
        page_labels=ANALYTICS_PAGE_LABELS,
        daily_counts=daily_counts,
        max_daily_count=max_daily_count,
    )


@app.errorhandler(404)
def not_found(_error):
    return render_template("404.html"), 404


@app.errorhandler(413)
def file_too_large(_error):
    return render_template("413.html"), 413


if __name__ == "__main__":
    debug_enabled = os.environ.get("FLASK_DEBUG", "1").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    app.run(debug=debug_enabled)
