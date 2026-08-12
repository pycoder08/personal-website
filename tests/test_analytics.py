"""Visitor analytics: page views get logged for anonymous traffic on the
public content pages, the site owner's own traffic (anything carrying valid
admin credentials, preview mode or not) is never counted, and the dashboard
at /admin/analytics is gated behind require_auth like every other admin
surface. This exercises _record_page_view (an after_request hook) and the
analytics() route directly, via the real page_views table -- not a mock."""

from db import get_db_connection


def _page_view_count():
    connection = get_db_connection()
    count = connection.execute("SELECT COUNT(*) AS n FROM page_views").fetchone()["n"]
    connection.close()
    return count


def _distinct_visitor_count():
    connection = get_db_connection()
    count = connection.execute(
        "SELECT COUNT(DISTINCT visitor_id) AS n FROM page_views"
    ).fetchone()["n"]
    connection.close()
    return count


def test_anonymous_page_view_is_recorded(client):
    assert _page_view_count() == 0
    client.get("/")
    assert _page_view_count() == 1


def test_multiple_tracked_pages_are_all_recorded(client):
    client.get("/")
    client.get("/portfolio")
    client.get("/portfolio/1")
    client.get("/blog")
    client.get("/blog/1")
    client.get("/videos")
    client.get("/videos/1")
    assert _page_view_count() == 7


def test_admin_page_view_is_not_recorded(client, good_auth):
    client.get("/", auth=good_auth)
    assert _page_view_count() == 0


def test_preview_mode_traffic_is_still_not_recorded(client, good_auth):
    """Preview mode hides admin controls, but the browser is still the
    owner's -- that traffic must not count as a visitor either."""
    client.get("/admin/preview/start", auth=good_auth)
    client.get("/", auth=good_auth)
    client.get("/portfolio", auth=good_auth)
    assert _page_view_count() == 0


def test_nonexistent_page_is_not_recorded(client):
    response = client.get("/this-page-does-not-exist")
    assert response.status_code == 404
    assert _page_view_count() == 0


def test_write_route_is_not_recorded_even_when_authenticated(client, good_auth):
    client.get("/blog/new", auth=good_auth)
    assert _page_view_count() == 0


def test_repeat_visits_from_the_same_browser_count_as_one_unique_visitor(client):
    client.get("/")
    client.get("/portfolio")
    client.get("/blog")
    assert _page_view_count() == 3
    assert _distinct_visitor_count() == 1


def test_visitor_cookie_is_set_once_and_then_reused(client):
    first_response = client.get("/")
    set_cookie_headers = first_response.headers.getlist("Set-Cookie")
    assert any("visitor_id=" in header for header in set_cookie_headers)

    second_response = client.get("/portfolio")
    assert not any(
        "visitor_id=" in header for header in second_response.headers.getlist("Set-Cookie")
    )


def test_different_browsers_count_as_different_visitors(client):
    client.get("/")  # first "browser" -- the shared `client` fixture's cookie jar
    with client.application.test_client() as second_browser:
        second_browser.get("/")
    assert _page_view_count() == 2
    assert _distinct_visitor_count() == 2


def test_analytics_dashboard_requires_auth(client, bad_auth, good_auth):
    assert client.get("/admin/analytics").status_code == 401
    assert client.get("/admin/analytics", auth=bad_auth).status_code == 401
    assert client.get("/admin/analytics", auth=good_auth).status_code == 200


def test_analytics_dashboard_reports_accurate_totals(client, good_auth):
    client.get("/")
    client.get("/")
    client.get("/portfolio")
    with client.application.test_client() as second_browser:
        second_browser.get("/")

    response = client.get("/admin/analytics", auth=good_auth)
    assert response.status_code == 200
    body = response.data
    assert b">4<" in body  # total page views
    assert b">2<" in body  # unique visitors


def test_analytics_dashboard_lists_top_pages(client, good_auth):
    client.get("/")
    client.get("/")
    client.get("/portfolio")

    response = client.get("/admin/analytics", auth=good_auth)
    assert response.status_code == 200
    assert b"Home" in response.data
    assert b"Portfolio" in response.data


def test_analytics_nav_link_hidden_when_anonymous(client):
    assert b">Analytics<" not in client.get("/").data


def test_analytics_nav_link_shown_when_authenticated(client, good_auth):
    assert b">Analytics<" in client.get("/", auth=good_auth).data
