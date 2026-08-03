"""Flask app for the personal site.

Run it with:

    venv/Scripts/python backend/app.py

from the project root (personal-website-full/). Templates live in
../templates and static assets (css, images) live in ../static, both
resolved from this file's location so it doesn't matter which folder
you launch it from.
"""

import os
from datetime import datetime

from flask import Flask, abort, redirect, render_template, request, url_for

from db import get_db_connection

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

app = Flask(
    __name__,
    template_folder=os.path.join(PROJECT_ROOT, "templates"),
    static_folder=os.path.join(PROJECT_ROOT, "static"),
)

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
                "blog_new.html", error=error, form=request.form, tags=get_all_tags()
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

    return render_template("blog_new.html", error=None, form={}, tags=get_all_tags())


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


if __name__ == "__main__":
    app.run(debug=True)
