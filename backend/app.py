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

from flask import Flask, Response, abort, flash, redirect, render_template, request, url_for
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

# ---------------------------------------------------------------------------
# SECRET_KEY signs Flask's session cookie. The only thing this app keeps in
# the session is one-time flash messages ("Post published.", "Project
# deleted.", etc. -- see flash() calls below), but Flask requires a secret
# key to sign that cookie at all. Set a real SECRET_KEY environment variable
# before deploying anywhere public -- the fallback below is fixed (so it
# survives app restarts during local dev) and must NOT be relied on outside
# your own machine, exactly like the ADMIN_USERNAME/ADMIN_PASSWORD fallback
# just below.
# ---------------------------------------------------------------------------
app.secret_key = os.environ.get(
    "SECRET_KEY", "local-dev-only-secret-key-9f2b6e4a1d7c8035-do-not-use-in-production"
)


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


def is_authenticated():
    """True if the current request already carries valid admin credentials.

    Used to hide management controls (New/Edit/Delete) from anonymous
    visitors on read-only pages. This is a UX nicety, not the real security
    boundary -- the write routes themselves still enforce auth via
    require_auth regardless of what a template does or doesn't render.
    """
    auth = request.authorization
    return bool(auth and _credentials_valid(auth.username, auth.password))


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
    return render_template(
        "portfolio.html", items=items, is_authenticated=is_authenticated()
    )


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
        flash("Project added.")
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
        flash("Project updated.")
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
    flash("Project deleted.")
    return redirect(url_for("portfolio"))


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
        is_authenticated=is_authenticated(),
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
        "blog_post.html", post=post, is_authenticated=is_authenticated()
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
        "videos.html", videos=all_videos, is_authenticated=is_authenticated()
    )


@app.route("/videos/new", methods=["GET", "POST"])
@require_auth
def video_new():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        duration = request.form.get("duration", "").strip()
        color_start = request.form.get("color_start", "").strip()
        color_end = request.form.get("color_end", "").strip()
        video_url = request.form.get("video_url", "").strip() or None

        error = None
        if not title or not description or not duration or not color_start or not color_end:
            error = "Please fill out every field before saving."

        if error:
            return render_template(
                "video_form.html", error=error, form=request.form, video=None
            )

        connection = get_db_connection()
        connection.execute(
            """
            INSERT INTO videos (title, description, duration, color_start, color_end, video_url)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (title, description, duration, color_start, color_end, video_url),
        )
        connection.commit()
        connection.close()
        flash("Video added.")
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
        "video_detail.html", video=video, is_authenticated=is_authenticated()
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
        description = request.form.get("description", "").strip()
        duration = request.form.get("duration", "").strip()
        color_start = request.form.get("color_start", "").strip()
        color_end = request.form.get("color_end", "").strip()
        video_url = request.form.get("video_url", "").strip() or None

        error = None
        if not title or not description or not duration or not color_start or not color_end:
            error = "Please fill out every field before saving."

        if error:
            connection.close()
            return render_template(
                "video_form.html", error=error, form=request.form, video=video
            )

        connection.execute(
            """
            UPDATE videos
            SET title = ?, description = ?, duration = ?, color_start = ?, color_end = ?, video_url = ?
            WHERE id = ?
            """,
            (title, description, duration, color_start, color_end, video_url, video_id),
        )
        connection.commit()
        connection.close()
        flash("Video updated.")
        return redirect(url_for("video_detail", video_id=video_id))

    connection.close()
    form = {
        "title": video["title"],
        "description": video["description"],
        "duration": video["duration"],
        "color_start": video["color_start"],
        "color_end": video["color_end"],
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
