"""Portfolio item CRUD, form validation, and image upload handling."""

import io

import app as app_module
import db as db_module

VALID_IMAGE_BYTES = b"\x89PNG\r\n\x1a\n" + b"fake-but-good-enough-image-bytes" * 10


def _count_items():
    connection = db_module.get_db_connection()
    count = connection.execute(
        "SELECT COUNT(*) AS n FROM portfolio_items"
    ).fetchone()["n"]
    connection.close()
    return count


NEW_ITEM_FORM = {
    "title": "A Brand New Test Project",
    "excerpt": "A short summary of the project created by the test suite.",
    "body": "The longer write-up of the project created by the test suite.",
}


def test_create_item_inserts_row_and_shows_in_grid(client, good_auth):
    before = _count_items()

    response = client.post(
        "/portfolio/new", data=NEW_ITEM_FORM, auth=good_auth,
    )
    assert response.status_code == 302
    assert _count_items() == before + 1

    listing = client.get("/portfolio")
    assert b"A Brand New Test Project" in listing.data


def test_create_item_flashes_success_message(client, good_auth):
    response = client.post(
        "/portfolio/new", data=NEW_ITEM_FORM, auth=good_auth, follow_redirects=True
    )
    assert response.status_code == 200
    assert b"Project added." in response.data


def test_edit_item_updates_row(client, good_auth):
    response = client.post(
        "/portfolio/1/edit",
        data={
            "title": "An Edited Project Title",
            "excerpt": "Edited excerpt.",
            "body": "Edited body.",
        },
        auth=good_auth,
    )
    assert response.status_code == 302

    listing = client.get("/portfolio")
    assert b"An Edited Project Title" in listing.data


def test_edit_item_flashes_success_message(client, good_auth):
    response = client.post(
        "/portfolio/1/edit",
        data={
            "title": "An Edited Project Title",
            "excerpt": "Edited excerpt.",
            "body": "Edited body.",
        },
        auth=good_auth,
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Project updated." in response.data


def test_new_item_gets_the_standardized_gradient_colors(client, good_auth):
    client.post("/portfolio/new", data=NEW_ITEM_FORM, auth=good_auth)

    connection = db_module.get_db_connection()
    row = connection.execute(
        "SELECT * FROM portfolio_items WHERE title = ?",
        ("A Brand New Test Project",),
    ).fetchone()
    connection.close()
    assert row["color_start"] == app_module.DEFAULT_PORTFOLIO_COLOR_START
    assert row["color_end"] == app_module.DEFAULT_PORTFOLIO_COLOR_END


def test_editing_an_item_does_not_change_its_colors(client, good_auth):
    connection = db_module.get_db_connection()
    original = connection.execute(
        "SELECT color_start, color_end FROM portfolio_items WHERE id = 1"
    ).fetchone()
    connection.close()

    client.post(
        "/portfolio/1/edit",
        data={"title": "An Edited Project Title", "excerpt": "Edited excerpt.", "body": "Edited body."},
        auth=good_auth,
    )

    connection = db_module.get_db_connection()
    after = connection.execute(
        "SELECT color_start, color_end FROM portfolio_items WHERE id = 1"
    ).fetchone()
    connection.close()
    assert after["color_start"] == original["color_start"]
    assert after["color_end"] == original["color_end"]


def test_delete_item_removes_row(client, good_auth):
    before = _count_items()

    response = client.post("/portfolio/1/delete", auth=good_auth)
    assert response.status_code == 302
    assert _count_items() == before - 1
    assert client.get("/portfolio/1/edit", auth=good_auth).status_code == 404


def test_delete_item_flashes_success_message(client, good_auth):
    response = client.post("/portfolio/1/delete", auth=good_auth, follow_redirects=True)
    assert response.status_code == 200
    assert b"Project deleted." in response.data


def test_new_item_missing_fields_shows_validation_error(client, good_auth):
    before = _count_items()

    response = client.post(
        "/portfolio/new",
        data={"title": "", "excerpt": "summary", "body": "write-up"},
        auth=good_auth,
    )

    assert response.status_code == 200
    assert b"Please fill out every field before saving." in response.data
    assert _count_items() == before


def test_new_item_form_no_longer_asks_for_colors_or_an_icon(client, good_auth):
    response = client.get("/portfolio/new", auth=good_auth)
    assert response.status_code == 200
    assert b'name="color_start"' not in response.data
    assert b'name="color_end"' not in response.data
    assert b'name="icon"' not in response.data
    assert b'id="description"' not in response.data
    assert b'name="excerpt"' in response.data
    assert b'name="body"' in response.data
    assert b'name="project_url"' in response.data


def test_new_item_with_project_link_shows_view_project_button(client, good_auth):
    form = dict(NEW_ITEM_FORM)
    form["project_url"] = "https://github.com/pycoder08/test-project"
    response = client.post("/portfolio/new", data=form, auth=good_auth, follow_redirects=True)
    assert response.status_code == 200

    connection = db_module.get_db_connection()
    row = connection.execute(
        "SELECT * FROM portfolio_items WHERE title = ?",
        ("A Brand New Test Project",),
    ).fetchone()
    connection.close()
    assert row["project_url"] == "https://github.com/pycoder08/test-project"

    detail = client.get(f"/portfolio/{row['id']}")
    assert b"View Project" in detail.data
    assert b"https://github.com/pycoder08/test-project" in detail.data


def test_new_item_without_project_link_shows_no_view_project_button(client, good_auth):
    client.post("/portfolio/new", data=NEW_ITEM_FORM, auth=good_auth)

    connection = db_module.get_db_connection()
    row = connection.execute(
        "SELECT * FROM portfolio_items WHERE title = ?",
        ("A Brand New Test Project",),
    ).fetchone()
    connection.close()
    assert row["project_url"] is None

    detail = client.get(f"/portfolio/{row['id']}")
    assert b"View Project" not in detail.data


def test_excerpt_shown_on_grid_but_body_only_on_detail_page(client, good_auth):
    client.post("/portfolio/new", data=NEW_ITEM_FORM, auth=good_auth)

    listing = client.get("/portfolio")
    assert NEW_ITEM_FORM["excerpt"].encode() in listing.data
    assert NEW_ITEM_FORM["body"].encode() not in listing.data

    connection = db_module.get_db_connection()
    row = connection.execute(
        "SELECT id FROM portfolio_items WHERE title = ?",
        ("A Brand New Test Project",),
    ).fetchone()
    connection.close()

    detail = client.get(f"/portfolio/{row['id']}")
    assert NEW_ITEM_FORM["body"].encode() in detail.data


def test_edit_redirects_to_the_detail_page(client, good_auth):
    response = client.post(
        "/portfolio/1/edit",
        data={"title": "An Edited Project Title", "excerpt": "Edited excerpt.", "body": "Edited body."},
        auth=good_auth,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/portfolio/1")


def test_grid_placeholder_has_no_icon_glyph(client):
    response = client.get("/portfolio")
    assert response.status_code == 200
    assert b"thumb-icon" not in response.data


def test_valid_image_upload_is_accepted_and_renders_img_tag(client, good_auth):
    form = dict(NEW_ITEM_FORM)
    form["image"] = (io.BytesIO(VALID_IMAGE_BYTES), "screenshot.png")

    response = client.post(
        "/portfolio/new", data=form, auth=good_auth,
    )
    assert response.status_code == 302

    connection = db_module.get_db_connection()
    row = connection.execute(
        "SELECT * FROM portfolio_items WHERE title = ?",
        ("A Brand New Test Project",),
    ).fetchone()
    connection.close()
    assert row is not None
    assert row["image_filename"] is not None
    assert row["image_filename"].endswith(".png")

    listing = client.get("/portfolio")
    assert b"<img" in listing.data
    assert row["image_filename"].encode() in listing.data


def test_invalid_image_extension_is_rejected_without_crashing(client, good_auth, upload_dir):
    form = dict(NEW_ITEM_FORM)
    form["image"] = (io.BytesIO(b"not really an image"), "notes.txt")

    response = client.post(
        "/portfolio/new", data=form, auth=good_auth,
    )

    assert response.status_code == 200
    assert b"isn&#39;t supported" in response.data or b"isn't supported" in response.data
    # Nothing should have been written to disk or inserted into the DB.
    assert list(upload_dir.glob("*")) == []
    connection = db_module.get_db_connection()
    row = connection.execute(
        "SELECT * FROM portfolio_items WHERE title = ?",
        ("A Brand New Test Project",),
    ).fetchone()
    connection.close()
    assert row is None


def test_oversized_image_upload_is_rejected_with_413(client, good_auth):
    oversized_bytes = b"a" * (6 * 1024 * 1024)  # 6MB, over the 5MB limit
    form = dict(NEW_ITEM_FORM)
    form["image"] = (io.BytesIO(oversized_bytes), "huge.png")

    response = client.post(
        "/portfolio/new", data=form, auth=good_auth,
    )

    assert response.status_code == 413
    assert b"too large" in response.data.lower()


def test_detail_page_shows_title_and_full_writeup(client):
    response = client.get("/portfolio/1")
    assert response.status_code == 200
    assert b"Personal Site Rebuild" in response.data
    assert b"CRUD for blog posts, portfolio items, and videos" in response.data


def test_detail_page_404s_for_missing_id(client):
    assert client.get("/portfolio/9999").status_code == 404


def test_detail_page_links_back_to_portfolio_grid(client):
    response = client.get("/portfolio/1")
    assert b'href="/portfolio"' in response.data


def test_grid_card_links_to_detail_page(client):
    response = client.get("/portfolio")
    assert b'href="/portfolio/1"' in response.data


def test_homepage_featured_card_links_to_detail_page(client):
    response = client.get("/")
    assert b'href="/portfolio/1"' in response.data


def test_delete_item_with_uploaded_image_removes_file_from_disk(client, good_auth, upload_dir):
    form = dict(NEW_ITEM_FORM)
    form["image"] = (io.BytesIO(VALID_IMAGE_BYTES), "screenshot.png")

    client.post(
        "/portfolio/new", data=form, auth=good_auth,
    )

    connection = db_module.get_db_connection()
    row = connection.execute(
        "SELECT * FROM portfolio_items WHERE title = ?",
        ("A Brand New Test Project",),
    ).fetchone()
    connection.close()
    item_id = row["id"]
    saved_path = upload_dir / row["image_filename"]
    assert saved_path.is_file()

    response = client.post(f"/portfolio/{item_id}/delete", auth=good_auth)
    assert response.status_code == 302
    assert not saved_path.is_file()
