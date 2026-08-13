"""Read-only routes: everything here is public (no auth) and should never
mutate anything, so the shared `client` fixture (fresh reseeded temp DB per
test) is enough."""

import db as db_module


def test_home_returns_200_with_expected_content(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Hi, I'm Muhammad." in response.data
    # Featured work / recent posts come from the seeded sample data.
    assert b"Personal Site Rebuild" in response.data
    # Home only shows the 3 most recent posts by date_iso -- this one
    # (2026-07-24) is the newest in the seed data.
    assert b"Giving the Videos Page an Actual Purpose" in response.data


def test_home_has_a_watch_videos_hero_button(client):
    response = client.get("/")
    assert b'href="/videos"' in response.data
    assert b"Watch Videos" in response.data


def test_home_shows_recent_videos_section(client):
    response = client.get("/")
    assert b"Recent Videos" in response.data
    assert b'href="/videos">See all videos' in response.data
    # Home shows the 3 most recently added videos by id -- videos have no
    # publish-date column, so id 6 (last in seed order) is "newest".
    assert b"From Static HTML to Jinja Templates" in response.data
    assert b"Parameterized Queries, No Excuses" in response.data
    assert b"Designing a Card Grid" in response.data
    # Only the 3 most recent -- the oldest seeded video shouldn't appear.
    assert b"Building a Nav Bar From Scratch" not in response.data


def test_home_hides_recent_videos_section_when_there_are_none(client):
    connection = db_module.get_db_connection()
    connection.execute("DELETE FROM videos")
    connection.commit()
    connection.close()

    response = client.get("/")
    assert response.status_code == 200
    assert b"Recent Videos" not in response.data


def test_portfolio_list_returns_200_with_seeded_items(client):
    response = client.get("/portfolio")
    assert response.status_code == 200
    assert b"Portfolio" in response.data
    assert b"SQL Study Tracker" in response.data


def test_blog_list_returns_200_with_seeded_posts(client):
    response = client.get("/blog")
    assert response.status_code == 200
    assert b"Blog" in response.data
    assert b"My First Real SQL Query" in response.data


def test_blog_post_valid_id_returns_200(client):
    response = client.get("/blog/1")
    assert response.status_code == 200
    assert b"Building This Site From Scratch" in response.data
    assert b"Process" in response.data


def test_blog_post_nonexistent_id_returns_404(client):
    response = client.get("/blog/99999")
    assert response.status_code == 404


def test_videos_returns_200_with_expected_content(client):
    response = client.get("/videos")
    assert response.status_code == 200
    assert b"Videos" in response.data
    assert b"Building a Nav Bar From Scratch" in response.data


def test_video_detail_valid_id_returns_200(client):
    response = client.get("/videos/1")
    assert response.status_code == 200
    assert b"Building a Nav Bar From Scratch" in response.data


def test_video_detail_nonexistent_id_returns_404(client):
    response = client.get("/videos/99999")
    assert response.status_code == 404


def test_portfolio_nonexistent_id_returns_404_via_edit(client, good_auth):
    # There's no public /portfolio/<id> detail route -- the edit route is
    # the one that looks up a single item by id and 404s if missing.
    response = client.get("/portfolio/99999/edit", auth=good_auth)
    assert response.status_code == 404
