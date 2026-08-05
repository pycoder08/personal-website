"""Blog post CRUD, tag filtering, and form validation."""

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


def test_delete_post_removes_row_and_subsequent_get_404s(client, good_auth):
    before = _count_posts()

    response = client.post("/blog/1/delete", auth=good_auth)
    assert response.status_code == 302
    assert _count_posts() == before - 1

    assert client.get("/blog/1").status_code == 404
    assert b"Building This Site From Scratch" not in client.get("/blog").data


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
