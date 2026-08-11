"""Every create/edit/delete route must be gated behind HTTP Basic Auth:
401 with no credentials, 401 with wrong credentials, success with the
right ones. This exercises `require_auth` in backend/app.py directly."""

import pytest

# (method, path) for every write route, using seeded id 1 (present in
# every test thanks to the per-test reseed in the `client` fixture).
GET_FORM_ROUTES = [
    ("GET", "/blog/new"),
    ("GET", "/blog/1/edit"),
    ("GET", "/portfolio/new"),
    ("GET", "/portfolio/1/edit"),
    ("GET", "/videos/new"),
    ("GET", "/videos/1/edit"),
]

DELETE_ROUTES = [
    ("POST", "/blog/1/delete"),
    ("POST", "/portfolio/1/delete"),
    ("POST", "/videos/1/delete"),
]

ALL_GATED_ROUTES = GET_FORM_ROUTES + DELETE_ROUTES


@pytest.mark.parametrize("method,path", ALL_GATED_ROUTES)
def test_write_route_401_without_credentials(client, method, path):
    response = client.open(path, method=method)
    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers


@pytest.mark.parametrize("method,path", ALL_GATED_ROUTES)
def test_write_route_401_with_wrong_credentials(client, method, path, bad_auth):
    response = client.open(path, method=method, auth=bad_auth)
    assert response.status_code == 401


@pytest.mark.parametrize("method,path", GET_FORM_ROUTES)
def test_get_form_route_200_with_correct_credentials(client, method, path, good_auth):
    response = client.open(path, method=method, auth=good_auth)
    assert response.status_code == 200


def test_blog_delete_succeeds_with_correct_credentials(client, good_auth):
    response = client.post("/blog/1/delete", auth=good_auth)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/blog")
    # The row is actually gone, not just a redirect.
    assert client.get("/blog/1").status_code == 404


def test_portfolio_delete_succeeds_with_correct_credentials(client, good_auth):
    response = client.post("/portfolio/1/delete", auth=good_auth)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/portfolio")
    assert client.get("/portfolio/1/edit", auth=good_auth).status_code == 404


def test_video_delete_succeeds_with_correct_credentials(client, good_auth):
    response = client.post("/videos/1/delete", auth=good_auth)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/videos")
    assert client.get("/videos/1").status_code == 404


# Read-only routes are always public, but the management controls (New/Edit/
# Delete) on them should only render for a visitor whose browser already has
# valid credentials cached -- see is_authenticated() in app.py. This is a UX
# nicety, not the real security boundary (that's require_auth on the write
# routes themselves, tested above), so these checks just confirm the
# affordance is hidden/shown correctly, not that it's "secure".
READ_ROUTES_WITH_CONTROLS = [
    # /blog (page 1) doesn't necessarily include post id 1 -- the blog list
    # is sorted newest-first and paginated, so check for any edit link
    # rather than a specific post's, to avoid coupling this test to seed
    # data ordering.
    ("/blog", "/edit\""),
    ("/blog/1", "/blog/1/edit"),
    ("/portfolio", "/portfolio/1/edit"),
    ("/videos", "/videos/1/edit"),
    ("/videos/1", "/videos/1/edit"),
]


@pytest.mark.parametrize("path,control_href", READ_ROUTES_WITH_CONTROLS)
def test_management_controls_hidden_when_anonymous(client, path, control_href):
    response = client.get(path)
    assert response.status_code == 200
    assert control_href.encode() not in response.data


@pytest.mark.parametrize("path,control_href", READ_ROUTES_WITH_CONTROLS)
def test_management_controls_shown_when_authenticated(client, path, control_href, good_auth):
    response = client.get(path, auth=good_auth)
    assert response.status_code == 200
    assert control_href.encode() in response.data


def test_new_post_button_hidden_when_anonymous(client):
    response = client.get("/blog")
    assert b"+ New Post" not in response.data


def test_new_post_button_shown_when_authenticated(client, good_auth):
    response = client.get("/blog", auth=good_auth)
    assert b"+ New Post" in response.data
