"""Per-project thumbnail fit (cover vs. contain): lets the admin switch a
project's uploaded image away from the default crop-to-fill behavior when
that crops out something that matters, e.g. a tall terminal screenshot."""

import io

import db as db_module

VALID_IMAGE_BYTES = b"\x89PNG\r\n\x1a\n" + b"fake-but-good-enough-image-bytes" * 10

NEW_ITEM_FORM = {
    "title": "A Thumbnail Fit Test Project",
    "excerpt": "e",
    "body": "b",
}


def _get_item(title):
    connection = db_module.get_db_connection()
    row = connection.execute(
        "SELECT * FROM portfolio_items WHERE title = ?", (title,)
    ).fetchone()
    connection.close()
    return row


def test_new_item_defaults_to_cover(client, good_auth):
    client.post("/portfolio/new", data=NEW_ITEM_FORM, auth=good_auth)
    assert _get_item("A Thumbnail Fit Test Project")["thumbnail_fit"] == "cover"


def test_new_item_can_be_created_with_contain(client, good_auth):
    form = dict(NEW_ITEM_FORM)
    form["thumbnail_fit"] = "contain"
    client.post("/portfolio/new", data=form, auth=good_auth)
    assert _get_item("A Thumbnail Fit Test Project")["thumbnail_fit"] == "contain"


def test_invalid_thumbnail_fit_value_falls_back_to_cover(client, good_auth):
    form = dict(NEW_ITEM_FORM)
    form["thumbnail_fit"] = "stretch-and-distort"  # not a real option
    client.post("/portfolio/new", data=form, auth=good_auth)
    assert _get_item("A Thumbnail Fit Test Project")["thumbnail_fit"] == "cover"


def test_editing_an_item_can_change_its_thumbnail_fit(client, good_auth):
    connection = db_module.get_db_connection()
    assert connection.execute(
        "SELECT thumbnail_fit FROM portfolio_items WHERE id = 1"
    ).fetchone()["thumbnail_fit"] == "cover"
    connection.close()

    client.post(
        "/portfolio/1/edit",
        data={"title": "Personal Site Rebuild", "excerpt": "e", "body": "b", "thumbnail_fit": "contain"},
        auth=good_auth,
    )

    connection = db_module.get_db_connection()
    after = connection.execute(
        "SELECT thumbnail_fit FROM portfolio_items WHERE id = 1"
    ).fetchone()
    connection.close()
    assert after["thumbnail_fit"] == "contain"


def test_thumbnail_fit_form_offers_both_options(client, good_auth):
    response = client.get("/portfolio/new", auth=good_auth)
    assert response.status_code == 200
    assert b'name="thumbnail_fit"' in response.data
    assert b'value="cover"' in response.data
    assert b'value="contain"' in response.data


def test_contain_fit_applied_as_inline_style_on_grid_card(client, good_auth):
    form = dict(NEW_ITEM_FORM)
    form["thumbnail_fit"] = "contain"
    form["image"] = (io.BytesIO(VALID_IMAGE_BYTES), "screenshot.png")
    client.post("/portfolio/new", data=form, auth=good_auth)

    response = client.get("/portfolio")
    assert b"object-fit: contain;" in response.data


def test_cover_fit_applied_as_inline_style_on_grid_card(client, good_auth):
    form = dict(NEW_ITEM_FORM)
    form["image"] = (io.BytesIO(VALID_IMAGE_BYTES), "screenshot.png")
    client.post("/portfolio/new", data=form, auth=good_auth)

    response = client.get("/portfolio")
    assert b"object-fit: cover;" in response.data


def test_contain_fit_applied_on_detail_page_with_gradient_letterbox(client, good_auth):
    form = dict(NEW_ITEM_FORM)
    form["thumbnail_fit"] = "contain"
    form["image"] = (io.BytesIO(VALID_IMAGE_BYTES), "screenshot.png")
    client.post("/portfolio/new", data=form, auth=good_auth)

    item = _get_item("A Thumbnail Fit Test Project")
    response = client.get(f"/portfolio/{item['id']}")
    assert b"object-fit: contain;" in response.data
    assert b"linear-gradient(135deg," in response.data
