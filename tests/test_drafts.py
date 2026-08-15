"""Non-public drafts for all three content types (posts, portfolio items,
videos): each New/Edit form now posts one of two submit buttons -- Publish
(publish_state=publish) and Save as Draft (publish_state=draft) -- which
sets an is_published flag. A draft is skipped by public list pages and
404s on its own detail page for anyone without admin credentials, but
still shows up (with a Draft badge) for the logged-in admin."""

import db as db_module


def _post_id(title):
    connection = db_module.get_db_connection()
    row = connection.execute("SELECT id FROM posts WHERE title = ?", (title,)).fetchone()
    connection.close()
    return row["id"]


def _portfolio_id(title):
    connection = db_module.get_db_connection()
    row = connection.execute(
        "SELECT id FROM portfolio_items WHERE title = ?", (title,)
    ).fetchone()
    connection.close()
    return row["id"]


def _video_id(title):
    connection = db_module.get_db_connection()
    row = connection.execute("SELECT id FROM videos WHERE title = ?", (title,)).fetchone()
    connection.close()
    return row["id"]


NEW_POST_DRAFT = {
    "title": "Unfinished Post",
    "date": "2026-08-14",
    "tags": "Draft-Only-Tag",
    "excerpt": "Not ready yet.",
    "body": "Still writing this.",
    "publish_state": "draft",
}

NEW_PROJECT_DRAFT = {
    "title": "Unfinished Project",
    "excerpt": "Not ready yet.",
    "body": "Still building this.",
    "publish_state": "draft",
}

NEW_VIDEO_DRAFT = {
    "title": "Unfinished Video",
    "excerpt": "Not ready yet.",
    "body": "Still editing this.",
    "duration": "1:23",
    "publish_state": "draft",
}


# ---------------------------------------------------------------------------
# Blog posts
# ---------------------------------------------------------------------------
def test_new_post_defaults_to_published_when_publish_state_is_omitted(client, good_auth):
    """Backward compatibility: a form submission with no publish_state
    field at all (an old cached form, or any other client that doesn't
    send it) behaves exactly like the single-button flow did before
    drafts existed."""
    form = {
        "title": "No Action Field",
        "date": "2026-08-14",
        "tags": "Misc",
        "excerpt": "e",
        "body": "b",
    }
    client.post("/blog/new", data=form, auth=good_auth)
    response = client.get("/blog")
    assert b"No Action Field" in response.data
    assert b"draft-badge" not in response.data


def test_post_saved_as_draft_is_hidden_from_public_blog_list(client, good_auth):
    client.post("/blog/new", data=NEW_POST_DRAFT, auth=good_auth)
    response = client.get("/blog")
    assert b"Unfinished Post" not in response.data


def test_post_saved_as_draft_shows_with_badge_to_admin(client, good_auth):
    client.post("/blog/new", data=NEW_POST_DRAFT, auth=good_auth)
    response = client.get("/blog", auth=good_auth)
    assert b"Unfinished Post" in response.data
    assert b"draft-badge" in response.data
    assert b"Draft" in response.data


def test_draft_post_detail_page_404s_for_anonymous_visitors(client, good_auth):
    client.post("/blog/new", data=NEW_POST_DRAFT, auth=good_auth)
    post_id = _post_id("Unfinished Post")
    assert client.get(f"/blog/{post_id}").status_code == 404


def test_draft_post_detail_page_visible_to_admin_with_banner(client, good_auth):
    client.post("/blog/new", data=NEW_POST_DRAFT, auth=good_auth)
    post_id = _post_id("Unfinished Post")
    response = client.get(f"/blog/{post_id}", auth=good_auth)
    assert response.status_code == 200
    assert b"draft-banner" in response.data


def test_editing_a_draft_post_to_publish_makes_it_public(client, good_auth):
    client.post("/blog/new", data=NEW_POST_DRAFT, auth=good_auth)
    post_id = _post_id("Unfinished Post")

    edit_form = dict(NEW_POST_DRAFT)
    edit_form["publish_state"] = "publish"
    client.post(f"/blog/{post_id}/edit", data=edit_form, auth=good_auth)

    response = client.get("/blog")
    assert b"Unfinished Post" in response.data
    assert client.get(f"/blog/{post_id}").status_code == 200


def test_editing_a_published_post_to_draft_hides_it_again(client, good_auth):
    publish_form = dict(NEW_POST_DRAFT)
    publish_form["publish_state"] = "publish"
    client.post("/blog/new", data=publish_form, auth=good_auth)
    post_id = _post_id("Unfinished Post")
    assert client.get(f"/blog/{post_id}").status_code == 200

    draft_form = dict(NEW_POST_DRAFT)
    client.post(f"/blog/{post_id}/edit", data=draft_form, auth=good_auth)
    assert client.get(f"/blog/{post_id}").status_code == 404


def test_publishing_a_draft_post_redirects_to_its_own_page(client, good_auth):
    response = client.post("/blog/new", data=NEW_POST_DRAFT, auth=good_auth)
    post_id = _post_id("Unfinished Post")
    assert response.headers["Location"].endswith(f"/blog/{post_id}")


def test_draft_only_tag_is_excluded_from_public_tag_filter_bar(client, good_auth):
    client.post("/blog/new", data=NEW_POST_DRAFT, auth=good_auth)
    anonymous_response = client.get("/blog")
    assert b"Draft-Only-Tag" not in anonymous_response.data

    admin_response = client.get("/blog", auth=good_auth)
    assert b"Draft-Only-Tag" in admin_response.data


def test_save_draft_flash_message(client, good_auth):
    response = client.post("/blog/new", data=NEW_POST_DRAFT, auth=good_auth, follow_redirects=True)
    assert b"Post saved as a draft." in response.data


# ---------------------------------------------------------------------------
# Portfolio projects
# ---------------------------------------------------------------------------
def test_project_saved_as_draft_is_hidden_from_public_portfolio_grid(client, good_auth):
    client.post("/portfolio/new", data=NEW_PROJECT_DRAFT, auth=good_auth)
    response = client.get("/portfolio")
    assert b"Unfinished Project" not in response.data


def test_project_saved_as_draft_shows_with_badge_to_admin(client, good_auth):
    client.post("/portfolio/new", data=NEW_PROJECT_DRAFT, auth=good_auth)
    response = client.get("/portfolio", auth=good_auth)
    assert b"Unfinished Project" in response.data
    assert b"draft-badge" in response.data


def test_draft_project_detail_page_404s_for_anonymous_visitors(client, good_auth):
    client.post("/portfolio/new", data=NEW_PROJECT_DRAFT, auth=good_auth)
    item_id = _portfolio_id("Unfinished Project")
    assert client.get(f"/portfolio/{item_id}").status_code == 404


def test_draft_project_detail_page_visible_to_admin_with_banner(client, good_auth):
    client.post("/portfolio/new", data=NEW_PROJECT_DRAFT, auth=good_auth)
    item_id = _portfolio_id("Unfinished Project")
    response = client.get(f"/portfolio/{item_id}", auth=good_auth)
    assert response.status_code == 200
    assert b"draft-banner" in response.data


def test_editing_a_draft_project_to_publish_makes_it_public(client, good_auth):
    client.post("/portfolio/new", data=NEW_PROJECT_DRAFT, auth=good_auth)
    item_id = _portfolio_id("Unfinished Project")

    edit_form = dict(NEW_PROJECT_DRAFT)
    edit_form["publish_state"] = "publish"
    client.post(f"/portfolio/{item_id}/edit", data=edit_form, auth=good_auth)

    assert client.get(f"/portfolio/{item_id}").status_code == 200
    response = client.get("/portfolio")
    assert b"Unfinished Project" in response.data


def test_draft_project_excluded_from_homepage_featured_work_even_pinned(client, good_auth):
    client.post("/portfolio/new", data=NEW_PROJECT_DRAFT, auth=good_auth)
    item_id = _portfolio_id("Unfinished Project")
    client.post(f"/portfolio/{item_id}/pin", auth=good_auth)

    response = client.get("/", auth=good_auth)
    assert b"Unfinished Project" not in response.data


# ---------------------------------------------------------------------------
# Videos
# ---------------------------------------------------------------------------
def test_video_saved_as_draft_is_hidden_from_public_video_grid(client, good_auth):
    client.post("/videos/new", data=NEW_VIDEO_DRAFT, auth=good_auth)
    response = client.get("/videos")
    assert b"Unfinished Video" not in response.data


def test_video_saved_as_draft_shows_with_badge_to_admin(client, good_auth):
    client.post("/videos/new", data=NEW_VIDEO_DRAFT, auth=good_auth)
    response = client.get("/videos", auth=good_auth)
    assert b"Unfinished Video" in response.data
    assert b"draft-badge" in response.data


def test_draft_video_detail_page_404s_for_anonymous_visitors(client, good_auth):
    client.post("/videos/new", data=NEW_VIDEO_DRAFT, auth=good_auth)
    video_id = _video_id("Unfinished Video")
    assert client.get(f"/videos/{video_id}").status_code == 404


def test_draft_video_detail_page_visible_to_admin_with_banner(client, good_auth):
    client.post("/videos/new", data=NEW_VIDEO_DRAFT, auth=good_auth)
    video_id = _video_id("Unfinished Video")
    response = client.get(f"/videos/{video_id}", auth=good_auth)
    assert response.status_code == 200
    assert b"draft-banner" in response.data


def test_editing_a_draft_video_to_publish_makes_it_public(client, good_auth):
    client.post("/videos/new", data=NEW_VIDEO_DRAFT, auth=good_auth)
    video_id = _video_id("Unfinished Video")

    edit_form = dict(NEW_VIDEO_DRAFT)
    edit_form["publish_state"] = "publish"
    client.post(f"/videos/{video_id}/edit", data=edit_form, auth=good_auth)

    assert client.get(f"/videos/{video_id}").status_code == 200
    response = client.get("/videos")
    assert b"Unfinished Video" in response.data


# ---------------------------------------------------------------------------
# Homepage
# ---------------------------------------------------------------------------
def test_draft_post_excluded_from_homepage_recent_posts(client, good_auth):
    client.post("/blog/new", data=NEW_POST_DRAFT, auth=good_auth)
    response = client.get("/", auth=good_auth)
    assert b"Unfinished Post" not in response.data


def test_draft_video_excluded_from_homepage_recent_videos(client, good_auth):
    client.post("/videos/new", data=NEW_VIDEO_DRAFT, auth=good_auth)
    response = client.get("/", auth=good_auth)
    assert b"Unfinished Video" not in response.data


# ---------------------------------------------------------------------------
# Preview mode: an admin previewing as a visitor should see the site
# exactly like an anonymous visitor, including drafts staying hidden.
# ---------------------------------------------------------------------------
def test_draft_post_hidden_while_admin_is_in_preview_mode(client, good_auth):
    client.post("/blog/new", data=NEW_POST_DRAFT, auth=good_auth)
    client.get("/admin/preview/start", auth=good_auth)
    response = client.get("/blog", auth=good_auth)
    assert b"Unfinished Post" not in response.data
