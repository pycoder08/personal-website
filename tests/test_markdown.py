"""Markdown rendering for blog post / portfolio project bodies, and the
/admin/upload-image utility that gives inline Markdown images a real URL
to point at."""

import io

import db as db_module

VALID_IMAGE_BYTES = b"\x89PNG\r\n\x1a\n" + b"fake-but-good-enough-image-bytes" * 10

NEW_POST_FORM = {
    "title": "A Markdown Test Post",
    "date": "2026-08-13",
    "tag": "Backend",
    "excerpt": "Testing Markdown rendering.",
    "body": (
        "# A Heading\n\n"
        "Some **bold** text and a [link](https://example.com).\n\n"
        "- one\n- two\n- three\n\n"
        "```\ncode block\n```"
    ),
}

NEW_PROJECT_FORM = {
    "title": "A Markdown Test Project",
    "excerpt": "Testing Markdown rendering.",
    "body": (
        "# A Heading\n\n"
        "Some **bold** text and a [link](https://example.com).\n\n"
        "- one\n- two\n- three"
    ),
}


def _new_post_id():
    connection = db_module.get_db_connection()
    row = connection.execute(
        "SELECT id FROM posts WHERE title = ?", ("A Markdown Test Post",)
    ).fetchone()
    connection.close()
    return row["id"]


def test_blog_post_body_renders_markdown_to_real_html(client, good_auth):
    client.post("/blog/new", data=NEW_POST_FORM, auth=good_auth)
    response = client.get(f"/blog/{_new_post_id()}")
    assert b"<h1>A Heading</h1>" in response.data
    assert b"<strong>bold</strong>" in response.data
    assert b'<a href="https://example.com">link</a>' in response.data
    assert b"<li>one</li>" in response.data
    assert b"<code>code block" in response.data


def test_blog_post_markdown_source_is_not_shown_raw(client, good_auth):
    client.post("/blog/new", data=NEW_POST_FORM, auth=good_auth)
    response = client.get(f"/blog/{_new_post_id()}")
    assert b"# A Heading" not in response.data
    assert b"**bold**" not in response.data


def test_portfolio_body_renders_markdown_to_real_html(client, good_auth):
    client.post("/portfolio/new", data=NEW_PROJECT_FORM, auth=good_auth)

    connection = db_module.get_db_connection()
    row = connection.execute(
        "SELECT id FROM portfolio_items WHERE title = ?",
        ("A Markdown Test Project",),
    ).fetchone()
    connection.close()

    response = client.get(f"/portfolio/{row['id']}")
    assert b"<h1>A Heading</h1>" in response.data
    assert b"<strong>bold</strong>" in response.data
    assert b'<a href="https://example.com">link</a>' in response.data
    assert b"<li>one</li>" in response.data


def test_upload_image_page_requires_auth(client, bad_auth):
    assert client.get("/admin/upload-image").status_code == 401
    assert client.get("/admin/upload-image", auth=bad_auth).status_code == 401


def test_upload_image_saves_file_and_returns_a_url(client, good_auth, content_upload_dir):
    response = client.post(
        "/admin/upload-image",
        data={"image": (io.BytesIO(VALID_IMAGE_BYTES), "photo.png")},
        auth=good_auth,
    )
    assert response.status_code == 200
    assert b"/static/images/uploads/" in response.data
    assert b".png" in response.data

    saved_files = list(content_upload_dir.glob("*.png"))
    assert len(saved_files) == 1


def test_upload_image_shows_a_ready_to_paste_markdown_snippet(client, good_auth):
    response = client.post(
        "/admin/upload-image",
        data={"image": (io.BytesIO(VALID_IMAGE_BYTES), "photo.png")},
        auth=good_auth,
    )
    assert b"![](" in response.data


def test_upload_image_rejects_disallowed_extension(client, good_auth, content_upload_dir):
    response = client.post(
        "/admin/upload-image",
        data={"image": (io.BytesIO(b"not an image"), "notes.txt")},
        auth=good_auth,
    )
    assert response.status_code == 200
    assert b"isn&#39;t supported" in response.data or b"isn't supported" in response.data
    assert list(content_upload_dir.glob("*")) == []


def test_upload_image_requires_a_file(client, good_auth):
    response = client.post("/admin/upload-image", data={}, auth=good_auth)
    assert response.status_code == 200
    assert b"Choose an image file first." in response.data


def test_upload_image_oversized_file_rejected_with_413(client, good_auth):
    oversized_bytes = b"a" * (6 * 1024 * 1024)  # 6MB, over the 5MB limit
    response = client.post(
        "/admin/upload-image",
        data={"image": (io.BytesIO(oversized_bytes), "huge.png")},
        auth=good_auth,
    )
    assert response.status_code == 413


def test_upload_image_link_shown_on_blog_form(client, good_auth):
    response = client.get("/blog/new", auth=good_auth)
    assert b'href="/admin/upload-image"' in response.data


def test_upload_image_link_shown_on_portfolio_form(client, good_auth):
    response = client.get("/portfolio/new", auth=good_auth)
    assert b'href="/admin/upload-image"' in response.data


def test_upload_image_page_not_counted_in_visitor_analytics(client, good_auth):
    client.get("/admin/upload-image", auth=good_auth)
    connection = db_module.get_db_connection()
    count = connection.execute("SELECT COUNT(*) AS n FROM page_views").fetchone()["n"]
    connection.close()
    assert count == 0
