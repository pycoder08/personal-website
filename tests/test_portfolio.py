"""Portfolio item CRUD, form validation, and image upload handling."""

import io

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
    "description": "A project created by the test suite.",
    "color_start": "#111111",
    "color_end": "#222222",
    "icon": "\U0001F9EA",
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


def test_edit_item_updates_row(client, good_auth):
    response = client.post(
        "/portfolio/1/edit",
        data={
            "title": "An Edited Project Title",
            "description": "Edited description.",
            "color_start": "#333333",
            "color_end": "#444444",
            "icon": "\U0001F680",
        },
        auth=good_auth,
    )
    assert response.status_code == 302

    listing = client.get("/portfolio")
    assert b"An Edited Project Title" in listing.data


def test_delete_item_removes_row(client, good_auth):
    before = _count_items()

    response = client.post("/portfolio/1/delete", auth=good_auth)
    assert response.status_code == 302
    assert _count_items() == before - 1
    assert client.get("/portfolio/1/edit", auth=good_auth).status_code == 404


def test_new_item_missing_fields_shows_validation_error(client, good_auth):
    before = _count_items()

    response = client.post(
        "/portfolio/new",
        data={
            "title": "",
            "description": "desc",
            "color_start": "#111111",
            "color_end": "#222222",
            "icon": "X",
        },
        auth=good_auth,
    )

    assert response.status_code == 200
    assert b"Please fill out every field before saving." in response.data
    assert _count_items() == before


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
