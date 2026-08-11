"""Favicon and Open Graph meta tags render without error on every page
type, with per-page overrides where they matter (a blog post or video's
og:title/og:description reflect that item, not the generic site default)."""


def test_favicon_and_default_og_tags_on_home(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b'rel="icon"' in response.data
    assert b'property="og:title" content="Muhammad Conn"' in response.data
    assert b'property="og:type" content="website"' in response.data
    assert b'property="og:site_name" content="Muhammad Conn"' in response.data


def test_favicon_and_og_tags_on_blog_list(client):
    response = client.get("/blog")
    assert response.status_code == 200
    assert b'rel="icon"' in response.data
    assert b'property="og:title" content="Muhammad Conn"' in response.data


def test_favicon_and_og_tags_on_portfolio(client):
    response = client.get("/portfolio")
    assert response.status_code == 200
    assert b'rel="icon"' in response.data
    assert b'property="og:title" content="Muhammad Conn"' in response.data


def test_favicon_and_og_tags_on_videos(client):
    response = client.get("/videos")
    assert response.status_code == 200
    assert b'rel="icon"' in response.data
    assert b'property="og:title" content="Muhammad Conn"' in response.data


def test_blog_post_og_title_and_description_reflect_the_post(client):
    response = client.get("/blog/1")
    assert response.status_code == 200
    assert b'rel="icon"' in response.data
    assert (
        b'property="og:title" content="Why I&#39;m Building This Site From Scratch"'
        in response.data
    )
    assert b'property="og:type" content="article"' in response.data


def test_video_detail_og_title_reflects_the_video(client):
    response = client.get("/videos/1")
    assert response.status_code == 200
    assert b'rel="icon"' in response.data
    assert (
        b'property="og:title" content="Building a Nav Bar From Scratch"'
        in response.data
    )
