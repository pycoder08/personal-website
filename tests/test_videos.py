"""Video CRUD, form validation, and video_url link/placeholder rendering."""

import db as db_module


def _count_videos():
    connection = db_module.get_db_connection()
    count = connection.execute("SELECT COUNT(*) AS n FROM videos").fetchone()["n"]
    connection.close()
    return count


NEW_VIDEO_FORM = {
    "title": "A Brand New Test Video",
    "description": "A video created by the test suite.",
    "duration": "3:33",
    "color_start": "#111111",
    "color_end": "#222222",
}


def test_create_video_inserts_row_and_shows_in_grid(client, good_auth):
    before = _count_videos()

    response = client.post("/videos/new", data=NEW_VIDEO_FORM, auth=good_auth)
    assert response.status_code == 302
    assert _count_videos() == before + 1

    listing = client.get("/videos")
    assert b"A Brand New Test Video" in listing.data


def test_edit_video_updates_row(client, good_auth):
    response = client.post(
        "/videos/1/edit",
        data={
            "title": "An Edited Video Title",
            "description": "Edited description.",
            "duration": "4:44",
            "color_start": "#333333",
            "color_end": "#444444",
        },
        auth=good_auth,
    )
    assert response.status_code == 302

    detail = client.get("/videos/1")
    assert detail.status_code == 200
    assert b"An Edited Video Title" in detail.data

    listing = client.get("/videos")
    assert b"An Edited Video Title" in listing.data


def test_delete_video_removes_row(client, good_auth):
    before = _count_videos()

    response = client.post("/videos/1/delete", auth=good_auth)
    assert response.status_code == 302
    assert _count_videos() == before - 1
    assert client.get("/videos/1").status_code == 404
    assert client.get("/videos/1/edit", auth=good_auth).status_code == 404


def test_new_video_missing_fields_shows_validation_error(client, good_auth):
    before = _count_videos()

    response = client.post(
        "/videos/new",
        data={
            "title": "",
            "description": "desc",
            "duration": "1:00",
            "color_start": "#111111",
            "color_end": "#222222",
        },
        auth=good_auth,
    )

    assert response.status_code == 200
    assert b"Please fill out every field before saving." in response.data
    assert _count_videos() == before


def test_video_edit_nonexistent_id_returns_404(client, good_auth):
    response = client.get("/videos/99999/edit", auth=good_auth)
    assert response.status_code == 404


def test_video_without_url_falls_back_to_placeholder(client):
    # Seeded videos never have a video_url set.
    response = client.get("/videos/1")
    assert response.status_code == 200
    assert b"video-player" in response.data
    assert b"Watch the full video" not in response.data


def test_video_with_url_renders_watch_link(client, good_auth):
    form = dict(NEW_VIDEO_FORM)
    form["video_url"] = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    response = client.post("/videos/new", data=form, auth=good_auth)
    assert response.status_code == 302

    connection = db_module.get_db_connection()
    row = connection.execute(
        "SELECT * FROM videos WHERE title = ?",
        ("A Brand New Test Video",),
    ).fetchone()
    connection.close()
    assert row is not None
    assert row["video_url"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    detail = client.get(f"/videos/{row['id']}")
    assert detail.status_code == 200
    assert b"Watch the full video" in detail.data
    assert b"https://www.youtube.com/watch?v=dQw4w9WgXcQ" in detail.data
    # The placeholder gradient thumbnail is still shown alongside the link --
    # this app never builds a real video player.
    assert b"video-player" in detail.data


def test_editing_video_to_clear_url_removes_watch_link(client, good_auth):
    form = dict(NEW_VIDEO_FORM)
    form["video_url"] = "https://example.com/my-video"
    create_response = client.post("/videos/new", data=form, auth=good_auth)
    assert create_response.status_code == 302

    connection = db_module.get_db_connection()
    row = connection.execute(
        "SELECT * FROM videos WHERE title = ?",
        ("A Brand New Test Video",),
    ).fetchone()
    connection.close()
    video_id = row["id"]
    assert b"Watch the full video" in client.get(f"/videos/{video_id}").data

    edit_form = dict(NEW_VIDEO_FORM)
    edit_form["video_url"] = ""
    response = client.post(f"/videos/{video_id}/edit", data=edit_form, auth=good_auth)
    assert response.status_code == 302

    detail = client.get(f"/videos/{video_id}")
    assert b"Watch the full video" not in detail.data
