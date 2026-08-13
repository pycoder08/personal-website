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

NEW_VIDEO_FORM = {
    "title": "A Markdown Test Video",
    "excerpt": "A short, plain-text summary shown on the video grid.",
    "body": (
        "# A Heading\n\n"
        "Some **bold** text and a [link](https://example.com).\n\n"
        "- one\n- two\n- three"
    ),
    "duration": "4:20",
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


def test_single_line_breaks_render_as_br_not_get_swallowed(client, good_auth):
    """Standard Markdown only starts a new paragraph on a blank line, which
    silently mashes together anything separated by a single Enter press --
    surprising for someone not already fluent in Markdown. nl2br fixes
    that: a lone newline becomes a real <br>, not nothing."""
    form = dict(NEW_POST_FORM)
    form["body"] = "Line one.\nLine two.\nLine three."
    client.post("/blog/new", data=form, auth=good_auth)

    response = client.get(f"/blog/{_new_post_id()}")
    assert b"Line one.<br" in response.data
    assert b"Line two.<br" in response.data
    assert b"Line three." in response.data


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


def _new_video_id():
    connection = db_module.get_db_connection()
    row = connection.execute(
        "SELECT id FROM videos WHERE title = ?", ("A Markdown Test Video",)
    ).fetchone()
    connection.close()
    return row["id"]


def test_video_body_renders_markdown_to_real_html_on_detail_page(client, good_auth):
    client.post("/videos/new", data=NEW_VIDEO_FORM, auth=good_auth)
    response = client.get(f"/videos/{_new_video_id()}")
    assert b"<h1>A Heading</h1>" in response.data
    assert b"<strong>bold</strong>" in response.data
    assert b'<a href="https://example.com">link</a>' in response.data
    assert b"<li>one</li>" in response.data


def test_video_grid_card_shows_plain_excerpt_not_the_full_markdown_body(client, good_auth):
    """The grid card teaser is the short, plain excerpt -- not the full
    Markdown body. Rendering the whole body there was the original bug:
    a long write-up would blow the card up to fit all of it."""
    client.post("/videos/new", data=NEW_VIDEO_FORM, auth=good_auth)
    response = client.get("/videos")
    assert b"A short, plain-text summary shown on the video grid." in response.data
    assert b"<strong>bold</strong>" not in response.data
    assert b"<h1>A Heading</h1>" not in response.data


def test_video_body_single_line_breaks_render_as_br(client, good_auth):
    form = dict(NEW_VIDEO_FORM)
    form["body"] = "Line one.\nLine two.\nLine three."
    client.post("/videos/new", data=form, auth=good_auth)

    response = client.get(f"/videos/{_new_video_id()}")
    assert b"Line one.<br" in response.data
    assert b"Line two.<br" in response.data


def test_video_og_description_meta_tag_uses_the_plain_excerpt_not_the_markdown_body(
    client, good_auth
):
    """The og:description meta tag's content attribute must never contain
    rendered Markdown HTML -- it uses the plain excerpt, same as
    blog/portfolio use their excerpt there instead of the rendered body."""
    client.post("/videos/new", data=NEW_VIDEO_FORM, auth=good_auth)
    response = client.get(f"/videos/{_new_video_id()}")
    assert (
        b'property="og:description" content="A short, plain-text summary shown on the video grid."'
        in response.data
    )
    assert b"<strong>" not in response.data.split(b"</head>")[0]


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


# ---------------------------------------------------------------------------
# The formatting toolbar (static/js/markdown-toolbar.js) itself runs in the
# browser and isn't exercised by these server-side tests -- what's tested
# here is everything the server is responsible for: the toolbar markup
# actually being on the page, the JSON upload path it calls via fetch(),
# and that it's wired up with the same validation as the plain-HTML form.
# ---------------------------------------------------------------------------
def test_upload_image_json_response_on_success(client, good_auth, content_upload_dir):
    response = client.post(
        "/admin/upload-image",
        data={"image": (io.BytesIO(VALID_IMAGE_BYTES), "photo.png")},
        auth=good_auth,
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 200
    assert response.content_type == "application/json"
    body = response.get_json()
    assert body["url"].startswith("/static/images/uploads/")
    assert body["url"].endswith(".png")


def test_upload_image_json_response_on_missing_file(client, good_auth):
    response = client.post(
        "/admin/upload-image",
        data={},
        auth=good_auth,
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "Choose an image file first."


def test_upload_image_json_response_on_bad_extension(client, good_auth, content_upload_dir):
    response = client.post(
        "/admin/upload-image",
        data={"image": (io.BytesIO(b"not an image"), "notes.txt")},
        auth=good_auth,
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 400
    assert "isn't supported" in response.get_json()["error"]
    assert list(content_upload_dir.glob("*")) == []


def test_upload_image_json_endpoint_requires_auth(client, bad_auth):
    response = client.post(
        "/admin/upload-image",
        data={"image": (io.BytesIO(VALID_IMAGE_BYTES), "photo.png")},
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 401

    response = client.post(
        "/admin/upload-image",
        data={"image": (io.BytesIO(VALID_IMAGE_BYTES), "photo.png")},
        auth=bad_auth,
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 401


def test_toolbar_present_on_blog_form_targeting_the_body_field(client, good_auth):
    response = client.get("/blog/new", auth=good_auth)
    assert b'class="md-toolbar" data-target="body"' in response.data
    assert b'data-md="bold"' in response.data
    assert b'data-md="image"' in response.data


def test_toolbar_present_on_portfolio_form_targeting_the_body_field(client, good_auth):
    response = client.get("/portfolio/new", auth=good_auth)
    assert b'class="md-toolbar" data-target="body"' in response.data
    assert b'data-md="bold"' in response.data
    assert b'data-md="image"' in response.data


def test_toolbar_script_is_included_and_loads_successfully(client, good_auth):
    response = client.get("/blog/new", auth=good_auth)
    assert b"js/markdown-toolbar.js" in response.data

    script_response = client.get("/static/js/markdown-toolbar.js")
    assert script_response.status_code == 200
    assert b"md-toolbar" in script_response.data


def test_toolbar_not_present_on_public_read_only_pages(client):
    """The toolbar (and its script) is a write-form-only affordance --
    it has no reason to load on pages a visitor actually reads."""
    response = client.get("/blog")
    assert b"md-toolbar" not in response.data
    assert b"markdown-toolbar.js" not in response.data
