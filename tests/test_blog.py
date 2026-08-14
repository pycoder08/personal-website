"""Blog post CRUD, multi-tag support, search, pagination, and form
validation. Tags are a many-to-many relationship (tags + post_tags), not a
single column -- a post can carry more than one tag."""

import re

import db as db_module


def _count_posts():
    connection = db_module.get_db_connection()
    count = connection.execute("SELECT COUNT(*) AS n FROM posts").fetchone()["n"]
    connection.close()
    return count


def _tags_for(post_id):
    connection = db_module.get_db_connection()
    names = [
        row["name"]
        for row in connection.execute(
            """
            SELECT tags.name FROM tags
            JOIN post_tags ON post_tags.tag_id = tags.id
            WHERE post_tags.post_id = ?
            ORDER BY tags.name
            """,
            (post_id,),
        ).fetchall()
    ]
    connection.close()
    return names


def _post_id_by_title(title):
    connection = db_module.get_db_connection()
    row = connection.execute("SELECT id FROM posts WHERE title = ?", (title,)).fetchone()
    connection.close()
    return row["id"]


NEW_POST_FORM = {
    "title": "A Brand New Test Post",
    "date": "2026-08-01",
    "tags": "Testing",
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


def test_create_post_with_multiple_tags_shows_all_of_them(client, good_auth):
    form = dict(NEW_POST_FORM)
    form["tags"] = "SQL, Backend, Testing"
    client.post("/blog/new", data=form, auth=good_auth)

    post_id = _post_id_by_title("A Brand New Test Post")
    assert _tags_for(post_id) == ["Backend", "SQL", "Testing"]

    response = client.get(f"/blog/{post_id}")
    assert b"SQL" in response.data
    assert b"Backend" in response.data
    assert b"Testing" in response.data


def test_edit_post_updates_row(client, good_auth):
    response = client.post(
        "/blog/1/edit",
        data={
            "title": "An Edited Title",
            "date": "2026-06-02",
            "tags": "Process",
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
            "tags": "Process",
            "excerpt": "Edited excerpt.",
            "body": "Edited body.",
        },
        auth=good_auth,
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Post updated." in response.data


def test_edit_post_replaces_its_entire_tag_set(client, good_auth):
    # Post 2 is seeded with ["Backend", "SQL"] -- editing it to a totally
    # different tag set should replace both, not add to them.
    assert _tags_for(2) == ["Backend", "SQL"]

    client.post(
        "/blog/2/edit",
        data={
            "title": "My First Real SQL Query (And Why It Didn't Work)",
            "date": "2026-06-14",
            "tags": "Design, Process",
            "excerpt": "e",
            "body": "b",
        },
        auth=good_auth,
    )

    assert _tags_for(2) == ["Design", "Process"]


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


def test_delete_post_also_removes_its_tag_associations(client, good_auth):
    """post_tags has a real foreign key with ON DELETE CASCADE (db.py turns
    on PRAGMA foreign_keys), so deleting a post shouldn't leave orphaned
    rows in post_tags behind it."""
    connection = db_module.get_db_connection()
    before = connection.execute("SELECT COUNT(*) AS n FROM post_tags").fetchone()["n"]
    connection.close()

    client.post("/blog/2/delete", auth=good_auth)  # seeded with 2 tags

    connection = db_module.get_db_connection()
    after = connection.execute("SELECT COUNT(*) AS n FROM post_tags").fetchone()["n"]
    orphaned = connection.execute(
        "SELECT COUNT(*) AS n FROM post_tags WHERE post_id = 2"
    ).fetchone()["n"]
    connection.close()
    assert after == before - 2
    assert orphaned == 0


def test_new_post_missing_fields_shows_validation_error(client, good_auth):
    before = _count_posts()

    response = client.post(
        "/blog/new",
        data={
            "title": "",
            "date": "2026-08-01",
            "tags": "Testing",
            "excerpt": "teaser",
            "body": "body",
        },
        auth=good_auth,
    )

    assert response.status_code == 200
    assert b"Please fill out every field before publishing." in response.data
    # No row was inserted.
    assert _count_posts() == before


def test_new_post_with_no_tags_at_all_shows_validation_error(client, good_auth):
    before = _count_posts()

    response = client.post(
        "/blog/new",
        data={
            "title": "A Post With No Tags",
            "date": "2026-08-01",
            "tags": "   ",  # blank after stripping -- no real tags submitted
            "excerpt": "teaser",
            "body": "body",
        },
        auth=good_auth,
    )

    assert response.status_code == 200
    assert b"Please fill out every field before publishing." in response.data
    assert _count_posts() == before


# ---------------------------------------------------------------------------
# Tag normalization: reduce accidental duplicate tags caused by typos in
# case or surrounding whitespace. Now per-tag, since a post can have more
# than one.
# ---------------------------------------------------------------------------


def test_new_post_tag_normalized_to_match_existing_casing(client, good_auth):
    # Seed data already has posts tagged exactly "SQL".
    form = dict(NEW_POST_FORM)
    form["tags"] = "sql"

    response = client.post("/blog/new", data=form, auth=good_auth)
    assert response.status_code == 302

    post_id = _post_id_by_title(form["title"])
    assert _tags_for(post_id) == ["SQL"]

    connection = db_module.get_db_connection()
    distinct_names = [
        r["name"] for r in connection.execute("SELECT name FROM tags").fetchall()
    ]
    connection.close()
    # No separate "sql" tag row was created alongside "SQL".
    assert "sql" not in distinct_names
    assert distinct_names.count("SQL") == 1


def test_multiple_tags_are_each_normalized_independently(client, good_auth):
    # Seed data already has "SQL" and "Backend" (both used on post 2 and 4).
    form = dict(NEW_POST_FORM)
    form["tags"] = "sql, BACKEND"

    client.post("/blog/new", data=form, auth=good_auth)
    post_id = _post_id_by_title(form["title"])
    assert _tags_for(post_id) == ["Backend", "SQL"]


def test_new_post_tag_with_surrounding_whitespace_is_normalized(client, good_auth):
    form = dict(NEW_POST_FORM)
    form["tags"] = "  SQL  "

    response = client.post("/blog/new", data=form, auth=good_auth)
    assert response.status_code == 302

    post_id = _post_id_by_title(form["title"])
    assert _tags_for(post_id) == ["SQL"]


def test_new_post_genuinely_new_tag_is_stored_as_typed(client, good_auth):
    form = dict(NEW_POST_FORM)
    form["tags"] = "BrandNewTag"

    response = client.post("/blog/new", data=form, auth=good_auth)
    assert response.status_code == 302

    post_id = _post_id_by_title(form["title"])
    assert _tags_for(post_id) == ["BrandNewTag"]


def test_duplicate_tags_in_the_same_submission_collapse_to_one(client, good_auth):
    form = dict(NEW_POST_FORM)
    form["tags"] = "SQL, sql, SQL"

    client.post("/blog/new", data=form, auth=good_auth)
    post_id = _post_id_by_title(form["title"])
    assert _tags_for(post_id) == ["SQL"]


def test_edit_post_tag_normalized_to_match_existing_casing(client, good_auth):
    # Post 1 is seeded with tag "Process"; retagging it with a case-variant
    # of "SQL" (used by other posts) should reuse "SQL", not create "sql".
    response = client.post(
        "/blog/1/edit",
        data={
            "title": "Edited Title",
            "date": "2026-06-02",
            "tags": "sql",
            "excerpt": "Edited excerpt.",
            "body": "Edited body.",
        },
        auth=good_auth,
    )
    assert response.status_code == 302
    assert _tags_for(1) == ["SQL"]


def test_editing_a_posts_tags_never_changes_an_existing_tags_stored_casing(client, good_auth):
    """Unlike the old single-column design, a tag is now a shared row that
    other posts may also reference -- so retyping an existing tag with
    different casing while editing one post must never silently rename it
    for everyone else using that same tag. The first-seen casing sticks
    until there's a dedicated rename action (there isn't one)."""
    connection = db_module.get_db_connection()
    connection.execute("DELETE FROM post_tags WHERE post_id = 1")
    tag_id = connection.execute("INSERT INTO tags (name) VALUES ('Unique')").lastrowid
    connection.execute("INSERT INTO post_tags (post_id, tag_id) VALUES (1, ?)", (tag_id,))
    connection.commit()
    connection.close()

    response = client.post(
        "/blog/1/edit",
        data={
            "title": "Edited Title",
            "date": "2026-06-02",
            "tags": "unique",
            "excerpt": "Edited excerpt.",
            "body": "Edited body.",
        },
        auth=good_auth,
    )
    assert response.status_code == 302
    assert _tags_for(1) == ["Unique"]

    connection = db_module.get_db_connection()
    tag_row_count = connection.execute(
        "SELECT COUNT(*) AS n FROM tags WHERE LOWER(name) = 'unique'"
    ).fetchone()["n"]
    connection.close()
    # No separate "unique" row was created alongside "Unique" either.
    assert tag_row_count == 1


def test_get_all_tags_excludes_tags_no_longer_used_by_any_post(client, good_auth):
    # "Process" starts out used by post 1 -- retag it away, and "Process"
    # should stop showing up as a filter option (unless another post still
    # has it -- seed post 6 also has "Process", so give that one away too).
    client.post(
        "/blog/1/edit",
        data={
            "title": "Post 1",
            "date": "2026-06-02",
            "tags": "SQL",
            "excerpt": "e",
            "body": "b",
        },
        auth=good_auth,
    )
    client.post(
        "/blog/6/edit",
        data={
            "title": "Post 6",
            "date": "2026-07-24",
            "tags": "Design",
            "excerpt": "e",
            "body": "b",
        },
        auth=good_auth,
    )

    response = client.get("/blog")
    assert b">Process<" not in response.data


# ---------------------------------------------------------------------------
# Tag filtering (?tag=)
# ---------------------------------------------------------------------------


def test_tag_filter_returns_only_matching_posts(client):
    response = client.get("/blog?tag=SQL")
    assert response.status_code == 200
    # Both SQL-tagged seed posts should be present...
    assert b"My First Real SQL Query" in response.data
    assert b"Turning a Hardcoded List Into a Database Table" in response.data
    # ...but posts tagged something else (and not also SQL) should not be.
    assert b"Designing a Grid That Doesn&#39;t Look Like a Spreadsheet" not in response.data


def test_tag_filter_with_no_matches_shows_empty_state_not_error(client):
    response = client.get("/blog?tag=NoSuchTagAtAll")
    assert response.status_code == 200
    assert b"No posts tagged" in response.data


def test_post_with_multiple_tags_matches_filter_for_either_one(client):
    # Seed post 2 has both "SQL" and "Backend" -- it should show up under
    # a filter for either tag, not just one of them.
    sql_filtered = client.get("/blog?tag=SQL")
    backend_filtered = client.get("/blog?tag=Backend")
    assert b"My First Real SQL Query" in sql_filtered.data
    assert b"My First Real SQL Query" in backend_filtered.data


def test_post_with_multiple_tags_appears_only_once_under_a_matching_filter(client):
    # A post with several tags matching a JOIN-based filter query must not
    # come back as duplicate rows.
    response = client.get("/blog?tag=SQL")
    assert response.data.count(b"My First Real SQL Query") == 1


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
        form["tags"] = "PagerTest"
        client.post("/blog/new", data=form, auth=good_auth)

    response = client.get("/blog?tag=PagerTest")
    assert response.status_code == 200

    next_link_match = re.search(rb'href="([^"]+)">Next', response.data)
    assert next_link_match is not None
    next_href = next_link_match.group(1).decode()
    assert "tag=PagerTest" in next_href
    assert "page=2" in next_href
