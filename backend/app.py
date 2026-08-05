r"""Flask app for the personal site.

Run it with:

    venv\Scripts\python backend\app.py

from the project root (personal-website-full/). Templates live in
../templates and static assets (css, images) live in ../static, both
resolved from this file's location so it doesn't matter which folder
you launch it from.
"""

import os
import secrets
import uuid
from datetime import datetime
from functools import wraps

from flask import Flask, Response, abort, redirect, render_template, request, url_for
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
# Portfolio image uploads: the only place in the app that accepts binary
# file input. Uploaded files are saved under static/images/portfolio/ using
# a freshly generated filename (never the client-supplied one) so there's
# no path-traversal risk and no chance of two uploads colliding.
# ---------------------------------------------------------------------------
# Tests point this at a temporary upload directory via the
# PORTFOLIO_IMAGE_DIR environment variable (see the project root
# conftest.py) so they never write into the real static/images/portfolio/.
# Normal local dev and production never set that variable, so this resolves
# to the same hardcoded folder as before.
PORTFOLIO_IMAGE_DIR = os.environ.get(
    "PORTFOLIO_IMAGE_DIR", os.path.join(PROJECT_ROOT, "static", "images", "portfolio")
)
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

# Flask/Werkzeug reject any request whose body exceeds this before the view
# function even runs, raising a 413 that's handled by the errorhandler below.
app.config["MAX_CONTENT_LENGTH"] = MAX_IMAGE_SIZE_BYTES


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

# The videos section is presented as sample/placeholder content -- there's
# no real video hosting behind it, so it's a simple in-memory list rather
# than a database table (the blog and portfolio are the parts that need to
# demonstrate real database-backed content).
VIDEOS = [
    {
        "id": 1,
        "title": "Building a Nav Bar From Scratch",
        "description": "A walkthrough of turning a plain list of links into "
        "a sticky, responsive nav bar with an active-page indicator.",
        "duration": "8:14",
        "color_start": "#6366f1",
        "color_end": "#8b5cf6",
    },
    {
        "id": 2,
        "title": "Flask Routes Explained",
        "description": "What actually happens between typing a URL and "
        "Flask deciding which function should handle it.",
        "duration": "12:02",
        "color_start": "#0ea5e9",
        "color_end": "#22d3ee",
    },
    {
        "id": 3,
        "title": "SQLite in 10 Minutes",
        "description": "Tables, rows, and just enough SQL to store and "
        "retrieve real data from a personal project.",
        "duration": "10:47",
        "color_start": "#10b981",
        "color_end": "#34d399",
    },
    {
        "id": 4,
        "title": "Designing a Card Grid",
        "description": "Spacing, shadows, and hover states -- the small "
        "details that make a grid of boxes feel like a real product.",
        "duration": "6:33",
        "color_start": "#f97316",
        "color_end": "#facc15",
    },
    {
        "id": 5,
        "title": "Parameterized Queries, No Excuses",
        "description": "Why string-formatting SQL is dangerous and how "
        "placeholder queries fix it without extra effort.",
        "duration": "9:21",
        "color_start": "#e11d48",
        "color_end": "#fb7185",
    },
    {
        "id": 6,
        "title": "From Static HTML to Jinja Templates",
        "description": "Turning four copy-pasted HTML files into one shared "
        "layout with a handful of small, focused templates.",
        "duration": "11:05",
        "color_start": "#7c3aed",
        "color_end": "#a855f7",
    },
]


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


def format_display_date(date_iso):
    """Turn '2026-07-18' into 'July 18, 2026' without relying on
    platform-specific strftime flags (Windows doesn't support %-d)."""
    dt = datetime.strptime(date_iso, "%Y-%m-%d")
    return f"{dt.strftime('%B')} {dt.day}, {dt.year}"


@app.route("/")
def home():
    connection = get_db_connection()
    recent_posts = connection.execute(
        "SELECT * FROM posts ORDER BY date_iso DESC LIMIT 3"
    ).fetchall()
    featured_items = connection.execute(
        "SELECT * FROM portfolio_items ORDER BY id LIMIT 3"
    ).fetchall()
    connection.close()
    return render_template(
        "index.html", recent_posts=recent_posts, featured_items=featured_items
    )


@app.route("/portfolio")
def portfolio():
    connection = get_db_connection()
    items = connection.execute(
        "SELECT * FROM portfolio_items ORDER BY id"
    ).fetchall()
    connection.close()
    return render_template("portfolio.html", items=items)


@app.route("/portfolio/new", methods=["GET", "POST"])
@require_auth
def portfolio_new():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        color_start = request.form.get("color_start", "").strip()
        color_end = request.form.get("color_end", "").strip()
        icon = request.form.get("icon", "").strip()
        image_file = request.files.get("image")
        has_upload = image_file is not None and image_file.filename.strip() != ""

        error = None
        if not title or not description or not color_start or not color_end or not icon:
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
                    (title, description, color_start, color_end, icon, image_filename)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (title, description, color_start, color_end, icon, image_filename),
            )
            connection.commit()
            connection.close()
        except Exception:
            # Don't leave an orphaned file on disk if the database write failed.
            delete_portfolio_image(image_filename)
            raise
        return redirect(url_for("portfolio"))

    return render_template("portfolio_form.html", error=None, form={}, item=None)


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
        description = request.form.get("description", "").strip()
        color_start = request.form.get("color_start", "").strip()
        color_end = request.form.get("color_end", "").strip()
        icon = request.form.get("icon", "").strip()
        image_file = request.files.get("image")
        has_upload = image_file is not None and image_file.filename.strip() != ""

        error = None
        if not title or not description or not color_start or not color_end or not icon:
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
            connection.execute(
                """
                UPDATE portfolio_items
                SET title = ?, description = ?, color_start = ?, color_end = ?, icon = ?, image_filename = ?
                WHERE id = ?
                """,
                (title, description, color_start, color_end, icon, image_filename, item_id),
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
        return redirect(url_for("portfolio"))

    connection.close()
    form = {
        "title": item["title"],
        "description": item["description"],
        "color_start": item["color_start"],
        "color_end": item["color_end"],
        "icon": item["icon"],
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
    return redirect(url_for("portfolio"))


@app.route("/blog")
def blog_list():
    selected_tag = request.args.get("tag", "").strip()

    connection = get_db_connection()
    if selected_tag:
        posts = connection.execute(
            "SELECT * FROM posts WHERE tag = ? ORDER BY date_iso DESC",
            (selected_tag,),
        ).fetchall()
    else:
        posts = connection.execute(
            "SELECT * FROM posts ORDER BY date_iso DESC"
        ).fetchall()
    connection.close()
    return render_template(
        "blog_list.html", posts=posts, tags=get_all_tags(), selected_tag=selected_tag
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
        connection.execute(
            """
            INSERT INTO posts (title, date_iso, date_display, tag, excerpt, body)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (title, date_iso, date_display, tag, excerpt, body),
        )
        connection.commit()
        connection.close()
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
    return render_template("blog_post.html", post=post)


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
    return redirect(url_for("blog_list"))


@app.route("/videos")
def videos():
    return render_template("videos.html", videos=VIDEOS)


@app.route("/videos/<int:video_id>")
def video_detail(video_id):
    video = next((v for v in VIDEOS if v["id"] == video_id), None)
    if video is None:
        abort(404)
    return render_template("video_detail.html", video=video)


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
