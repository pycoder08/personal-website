"""Pinning portfolio projects: pinned items sort first on both /portfolio
and the homepage's Featured Work section, via a single POST toggle route
(portfolio_toggle_pin) rather than separate controls for each page."""

import db as db_module


def _item_id(title):
    connection = db_module.get_db_connection()
    row = connection.execute(
        "SELECT id FROM portfolio_items WHERE title = ?", (title,)
    ).fetchone()
    connection.close()
    return row["id"]


def _is_pinned(item_id):
    connection = db_module.get_db_connection()
    row = connection.execute(
        "SELECT pinned FROM portfolio_items WHERE id = ?", (item_id,)
    ).fetchone()
    connection.close()
    return bool(row["pinned"])


def test_new_item_is_not_pinned_by_default(client, good_auth):
    client.post(
        "/portfolio/new",
        data={"title": "Unpinned By Default", "excerpt": "e", "body": "b"},
        auth=good_auth,
    )
    assert not _is_pinned(_item_id("Unpinned By Default"))


def test_toggle_pin_requires_auth(client, bad_auth):
    assert client.post("/portfolio/1/pin").status_code == 401
    assert client.post("/portfolio/1/pin", auth=bad_auth).status_code == 401


def test_toggle_pin_pins_an_unpinned_item(client, good_auth):
    assert not _is_pinned(1)
    response = client.post("/portfolio/1/pin", auth=good_auth)
    assert response.status_code == 302
    assert _is_pinned(1)


def test_toggle_pin_unpins_an_already_pinned_item(client, good_auth):
    client.post("/portfolio/1/pin", auth=good_auth)
    assert _is_pinned(1)
    client.post("/portfolio/1/pin", auth=good_auth)
    assert not _is_pinned(1)


def test_toggle_pin_flashes_pin_message(client, good_auth):
    response = client.post("/portfolio/1/pin", auth=good_auth, follow_redirects=True)
    assert b"Project pinned to the top." in response.data


def test_toggle_pin_flashes_unpin_message(client, good_auth):
    client.post("/portfolio/1/pin", auth=good_auth)
    response = client.post("/portfolio/1/pin", auth=good_auth, follow_redirects=True)
    assert b"Project unpinned." in response.data


def test_toggle_pin_404s_for_missing_item(client, good_auth):
    assert client.post("/portfolio/9999/pin", auth=good_auth).status_code == 404


def test_toggle_pin_redirects_to_the_referring_page(client, good_auth):
    response = client.post(
        "/portfolio/1/pin",
        auth=good_auth,
        headers={"Referer": "http://localhost/portfolio/1"},
    )
    assert response.headers["Location"].endswith("/portfolio/1")


def test_pinned_item_sorts_first_on_portfolio_grid(client, good_auth):
    # "Chess Puzzle Solver" is seed id 5 -- pin it and confirm it now
    # appears before id 1 in the grid, even though 1 < 5.
    chess_id = _item_id("Chess Puzzle Solver")
    client.post(f"/portfolio/{chess_id}/pin", auth=good_auth)

    response = client.get("/portfolio")
    body = response.data.decode()
    assert body.index("Chess Puzzle Solver") < body.index("Personal Site Rebuild")


def test_pinned_item_sorts_first_in_featured_work(client, good_auth):
    chess_id = _item_id("Chess Puzzle Solver")
    client.post(f"/portfolio/{chess_id}/pin", auth=good_auth)

    response = client.get("/")
    body = response.data.decode()
    assert body.index("Chess Puzzle Solver") < body.index("Personal Site Rebuild")


def test_featured_work_falls_back_to_lowest_ids_when_nothing_pinned(client):
    """Existing behavior, preserved: with nothing pinned, ORDER BY pinned
    DESC, id ASC degrades to the original ORDER BY id -- the featured
    section still shows the first 2 projects (the homepage's Featured
    Work/Recent Videos pair shows 2 apiece, see home() in app.py), not an
    empty section."""
    response = client.get("/")
    body = response.data.decode()
    assert "Personal Site Rebuild" in body
    assert body.index("Personal Site Rebuild") < body.index("SQL Study Tracker")
    assert "Weather CLI" not in body


def test_unpinned_items_keep_id_order_among_themselves(client, good_auth):
    chess_id = _item_id("Chess Puzzle Solver")
    client.post(f"/portfolio/{chess_id}/pin", auth=good_auth)

    response = client.get("/portfolio")
    body = response.data.decode()
    # Pinned item first, then the rest still in their original id order.
    assert body.index("Chess Puzzle Solver") < body.index("Personal Site Rebuild")
    assert body.index("Personal Site Rebuild") < body.index("SQL Study Tracker")


def test_pinned_badge_shown_for_pinned_item(client, good_auth):
    client.post("/portfolio/1/pin", auth=good_auth)
    response = client.get("/portfolio")
    assert b"pinned-badge" in response.data
    assert b"Pinned" in response.data


def test_pinned_badge_not_shown_when_nothing_pinned(client):
    response = client.get("/portfolio")
    assert b"pinned-badge" not in response.data


def test_pin_toggle_button_hidden_when_anonymous(client):
    response = client.get("/portfolio")
    assert b"Pin to Top" not in response.data
    assert b'action="/portfolio/1/pin"' not in response.data


def test_pin_toggle_button_shown_when_authenticated(client, good_auth):
    response = client.get("/portfolio", auth=good_auth)
    assert b"Pin to Top" in response.data
    assert b'action="/portfolio/1/pin"' in response.data


def test_pin_toggle_button_on_detail_page_reflects_current_state(client, good_auth):
    unpinned = client.get("/portfolio/1", auth=good_auth)
    assert b"Pin to Top" in unpinned.data
    assert b"Unpin" not in unpinned.data

    client.post("/portfolio/1/pin", auth=good_auth)

    pinned = client.get("/portfolio/1", auth=good_auth)
    assert b"Unpin" in pinned.data
