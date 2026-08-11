"""Blog post CRUD, tag filtering, search, pagination, and form validation."""

import re

import db as db_module


def _count_posts():
    connection = db_module.get_db_connection()
    count = connection.execute("SELECT COUNT(*) AS n FROM posts").fetchone()["n"]
    connection.close()
    return count


NEW_POST_FORM = {
    "title": "A Brand New Test Post",
    "date": "2026-08-01",
    "tag": "Testing",
    "excerpt": "A short teaser for the new post.",
    "body": "The full body of the new post.",
}


def test_create_post_inserts_row_and_shows_in_list(client, good_auth):
    before = _count_posts()

    response = client.post("/blog/new", data=NEW_POST_FORM, auth=good_auth)
    assert response.status_code == 302

    assert _count_posts() == before + 1

    listing = client.get("/blog")
    assert b"A Brand New Test Post" in listing.data
    assert b"Testing" in listing.data


def test_create_post_flashes_success_message(client, good_auth):
    response = client.post(
        "/blog/new", data=NEW_POST_FORM, auth=good_auth, follow_redirects=True
    )
    assert response.status_code == 200
    assert b"Post published." in response.data


def test_edit_post_updates_row(client, good_auth):
    response = client.post(
        "/blog/1/edit",
        data={
            "title": "An Edited Title",
            "date": "2026-06-02",
            "tag": "Process",
            "excerpt": "Edited excerpt.",
            "body": "Edited body.",
        },
        auth=good_auth,
    )
    assert response.status_code == 302

    post_page = client.get("/blog/1")
    assert post_page.status_code == 200
    assert b"An Edited Title" in post_page.data
    assert b"Edited body." in post_page.data


def test_edit_post_flashes_success_message(client, good_auth):
    response = client.post(
        "/blog/1/edit",
        data={
            "title": "An Edited Title",
            "date": "2026-06-02",
            "tag": "Process",
            "excerpt": "Edited excerpt.",
            "body": "Edited body.",
        },
        auth=good_auth,
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Post updated." in response.data


def test_delete_post_removes_row_and_subsequent_get_404s(client, good_auth):
    before = _count_posts()

    response = client.post("/blog/1/delete", auth=good_auth)
    assert response.status_code == 302
    assert _count_posts() == before - 1

    assert client.get("/blog/1").status_code == 404
    assert b"Building This Site From Scratch" not in client.get("/blog").data


def test_delete_post_flashes_success_message(client, good_auth):
    response = client.post("/blog/1/delete", auth=good_auth, follow_redirects=True)
    assert response.status_code == 200
    assert b"Post deleted." in response.data


def test_tag_filter_returns_only_matching_posts(client):
    response = client.get("/blog?tag=SQL")
    assert response.status_code == 200
    # Both SQL-tagged seed posts should be present...
    assert b"My First Real SQL Query" in response.data
    assert b"Turning a Hardcoded List Into a Database Table" in response.data
    # ...but posts tagged something else should not be.
    assert b"Giving the Videos Page an Actual Purpose" not in response.data
    assert b"What &#39;Add Post&#39; Actually Does" not in response.data


def test_tag_filter_with_no_matches_shows_empty_state_not_error(client):
    response = client.get("/blog?tag=NoSuchTagAtAll")
    assert response.status_code == 200
    assert b"No posts tagged" in response.data


def test_new_post_missing_fields_shows_validation_error(client, good_auth):
    before = _count_posts()

    response = client.post(
        "/blog/new",
        data={
            "title": "",
            "date": "2026-08-01",
            "tag": "Testing",
            "excerpt": "teaser",
            "body": "body",
        },
        auth=good_auth,
    )

    assert response.status_code == 200
    assert b"Please fill out every field before publishing." in response.data
    # No row was inserted.
    assert _count_posts() == before


# ---------------------------------------------------------------------------
# Tag normalization: reduce accidental duplicate tags caused by typos in
# case or surrounding whitespace.
# ---------------------------------------------------------------------------


def test_new_post_tag_normalized_to_match_existing_casing(client, good_auth):
    # Seed data already has a post tagged exactly "SQL".
    form = dict(NEW_POST_FORM)
    form["tag"] = "sql"

    response = client.post("/blog/new", data=form, auth=good_auth)
    assert response.status_code == 302

    connection = db_module.get_db_connection()
    row = connection.execute(
        "SELECT tag FROM posts WHERE title = ?", (form["title"],)
    ).fetchone()
    distinct_tags = [
        r["tag"] for r in connection.execute("SELECT DISTINCT tag FROM posts").fetchall()
    ]
    connection.close()

    assert row["tag"] == "SQL"
    # No separate "sql" tag was created alongside "SQL".
    assert "sql" not in distinct_tags
    assert distinct_tags.count("SQL") == 1


def test_new_post_tag_with_surrounding_whitespace_is_normalized(client, good_auth):
    form = dict(NEW_POST_FORM)
    form["tag"] = "  SQL  "

    response = client.post("/blog/new", data=form, auth=good_auth)
    assert response.status_code == 302

    connection = db_module.get_db_connection()
    row = connection.execute(
        "SELECT tag FROM posts WHERE title = ?", (form["title"],)
    ).fetchone()
    connection.close()
    assert row["tag"] == "SQL"


def test_new_post_genuinely_new_tag_is_stored_as_typed(client, good_auth):
    form = dict(NEW_POST_FORM)
    form["tag"] = "BrandNewTag"

    response = client.post("/blog/new", data=form, auth=good_auth)
    assert response.status_code == 302

    connection = db_module.get_db_connection()
    row = connection.execute(
        "SELECT tag FROM posts WHERE title = ?", (form["title"],)
    ).fetchone()
    connection.close()
    assert row["tag"] == "BrandNewTag"


def test_edit_post_tag_normalized_to_match_existing_casing(client, good_auth):
    # Post 1 is seeded with tag "Process"; retagging it with a case-variant
    # of "SQL" (used by other posts) should reuse "SQL", not create "sql".
    response = client.post(
        "/blog/1/edit",
        data={
            "title": "Edited Title",
            "date": "2026-06-02",
            "tag": "sql",
            "excerpt": "Edited excerpt.",
            "body": "Edited body.",
        },
        auth=good_auth,
    )
    assert response.status_code == 302

    connection = db_module.get_db_connection()
    row = connection.execute("SELECT tag FROM posts WHERE id = 1").fetchone()
    connection.close()
    assert row["tag"] == "SQL"


def test_edit_post_can_recase_its_own_unique_tag(client, good_auth):
    # Give post 1 a tag no other post uses, then edit it to a different
    # casing -- since it's not competing with any other post's tag, the
    # newly typed casing should be honored, not silently reverted.
    connection = db_module.get_db_connection()
    connection.execute("UPDATE posts SET tag = 'Unique' WHERE id = 1")
    connection.commit()
    connection.close()

    response = client.post(
        "/blog/1/edit",
        data={
            "title": "Edited Title",
            "date": "2026-06-02",
            "tag": "unique",
            "excerpt": "Edited excerpt.",
            "body": "Edited body.",
        },
        auth=good_auth,
    )
    assert response.status_code == 302

    connection = db_module.get_db_connection()
    row = connection.execute("SELECT tag FROM posts WHERE id = 1").fetchone()
    connection.close()
    assert row["tag"] == "unique"


# ---------------------------------------------------------------------------
# Search (?q=)
# ---------------------------------------------------------------------------


def test_search_matches_title(client):
    response = client.get("/blog?q=SQL+Query")
    assert response.status_code == 200
    assert b"My First Real SQL Query" in response.data


def test_search_matches_body_text_case_insensitively(client):
    # "embarrassingly" only appears in the body of this post, not its
    # title or excerpt -- and the query is deliberately the wrong case.
    response = client.get("/blog?q=EMBARRASSINGLY")
    assert response.status_code == 200
    assert b"My First Real SQL Query" in response.data


def test_search_with_no_matches_shows_distinct_empty_state(client):
    response = client.get("/blog?q=zzzznonexistentsearchtermxyz")
    assert response.status_code == 200
    assert b"No posts match" in response.data
    assert b"No posts tagged" not in response.data


def test_search_combined_with_tag_filter_narrows_results(client):
    # Both SQL posts are tagged "SQL", but only one mentions "embarrassingly".
    response = client.get("/blog?tag=SQL&q=embarrassingly")
    assert response.status_code == 200
    assert b"My First Real SQL Query" in response.data
    assert b"Turning a Hardcoded List Into a Database Table" not in response.data


def test_search_combined_with_tag_filter_can_produce_no_matches(client):
    response = client.get("/blog?tag=Design&q=embarrassingly")
    assert response.status_code == 200
    assert b"No posts match" in response.data


# ---------------------------------------------------------------------------
# Pagination (?page=)
# ---------------------------------------------------------------------------


def test_blog_list_first_page_shows_page_size_posts_with_next_only(client):
    response = client.get("/blog")
    assert response.status_code == 200
    assert response.data.count(b'class="card post-preview"') == 5
    assert b">Next" in response.data
    assert b"Previous</a>" not in response.data


def test_blog_list_second_page_shows_remaining_post_with_prev_only(client):
    response = client.get("/blog?page=2")
    assert response.status_code == 200
    # 6 seeded posts, 5 per page -> exactly 1 post left on page 2.
    assert response.data.count(b'class="card post-preview"') == 1
    assert b"Previous</a>" in response.data
    assert b">Next" not in response.data


def test_blog_list_page_beyond_last_page_clamps_to_last_page(client):
    response = client.get("/blog?page=999")
    assert response.status_code == 200
    assert response.data.count(b'class="card post-preview"') == 1


def test_pagination_links_preserve_active_tag_and_search_filters(client, good_auth):
    # Create enough same-tag posts to force a second page under a filter.
    for i in range(6):
        form = dict(NEW_POST_FORM)
        form["title"] = f"Pager Post {i}"
        form["tag"] = "PagerTest"
        client.post("/blog/new", data=form, auth=good_auth)

    response = client.get("/blog?tag=PagerTest")
    assert response.status_code == 200

    next_link_match = re.search(rb'href="([^"]+)">Next', response.data)
    assert next_link_match is not None
    next_href = next_link_match.group(1).decode()
    assert "tag=PagerTest" in next_href
    assert "page=2" in next_href
