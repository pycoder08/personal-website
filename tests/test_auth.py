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
]

DELETE_ROUTES = [
    ("POST", "/blog/1/delete"),
    ("POST", "/portfolio/1/delete"),
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
