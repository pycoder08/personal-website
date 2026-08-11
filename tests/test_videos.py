"""Video CRUD, form validation, standardized gradient colors, and
video_url link/placeholder + duration-auto-detection behavior.

Duration auto-detection calls out to yt-dlp (real network access to
YouTube), which the test suite must never do -- every test that exercises
that path monkeypatches `app_module.extract_youtube_duration` instead of
hitting the real network, so the suite stays fast, isolated, and doesn't
depend on YouTube being reachable (or a given video still existing) from
CI."""

import app as app_module
import db as db_module


def _count_videos():
    connection = db_module.get_db_connection()
    count = connection.execute("SELECT COUNT(*) AS n FROM videos").fetchone()["n"]
    connection.close()
    return count


def _get_video_by_title(title):
    connection = db_module.get_db_connection()
    row = connection.execute(
        "SELECT * FROM videos WHERE title = ?", (title,)
    ).fetchone()
    connection.close()
    return row


NEW_VIDEO_FORM = {
    "title": "A Brand New Test Video",
    "description": "A video created by the test suite.",
    "duration": "3:33",
}


def test_create_video_inserts_row_and_shows_in_grid(client, good_auth):
    before = _count_videos()

    response = client.post("/videos/new", data=NEW_VIDEO_FORM, auth=good_auth)
    assert response.status_code == 302
    assert _count_videos() == before + 1

    listing = client.get("/videos")
    assert b"A Brand New Test Video" in listing.data


def test_create_video_flashes_success_message(client, good_auth):
    response = client.post(
        "/videos/new", data=NEW_VIDEO_FORM, auth=good_auth, follow_redirects=True
    )
    assert response.status_code == 200
    assert b"Video added." in response.data


def test_new_video_gets_standardized_gradient_colors(client, good_auth):
    client.post("/videos/new", data=NEW_VIDEO_FORM, auth=good_auth)
    row = _get_video_by_title("A Brand New Test Video")
    assert row["color_start"] == app_module.DEFAULT_VIDEO_COLOR_START
    assert row["color_end"] == app_module.DEFAULT_VIDEO_COLOR_END


def test_edit_video_updates_row(client, good_auth):
    response = client.post(
        "/videos/1/edit",
        data={
            "title": "An Edited Video Title",
            "description": "Edited description.",
            "duration": "4:44",
        },
        auth=good_auth,
    )
    assert response.status_code == 302

    detail = client.get("/videos/1")
    assert detail.status_code == 200
    assert b"An Edited Video Title" in detail.data

    listing = client.get("/videos")
    assert b"An Edited Video Title" in listing.data


def test_editing_video_does_not_change_its_stored_colors(client, good_auth):
    connection = db_module.get_db_connection()
    before = connection.execute(
        "SELECT color_start, color_end FROM videos WHERE id = 1"
    ).fetchone()
    connection.close()

    client.post(
        "/videos/1/edit",
        data={
            "title": "An Edited Video Title",
            "description": "Edited description.",
            "duration": "4:44",
        },
        auth=good_auth,
    )

    connection = db_module.get_db_connection()
    after = connection.execute(
        "SELECT color_start, color_end FROM videos WHERE id = 1"
    ).fetchone()
    connection.close()
    assert after["color_start"] == before["color_start"]
    assert after["color_end"] == before["color_end"]


def test_edit_video_flashes_success_message(client, good_auth):
    response = client.post(
        "/videos/1/edit",
        data={
            "title": "An Edited Video Title",
            "description": "Edited description.",
            "duration": "4:44",
        },
        auth=good_auth,
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Video updated." in response.data


def test_delete_video_removes_row(client, good_auth):
    before = _count_videos()

    response = client.post("/videos/1/delete", auth=good_auth)
    assert response.status_code == 302
    assert _count_videos() == before - 1
    assert client.get("/videos/1").status_code == 404
    assert client.get("/videos/1/edit", auth=good_auth).status_code == 404


def test_delete_video_flashes_success_message(client, good_auth):
    response = client.post("/videos/1/delete", auth=good_auth, follow_redirects=True)
    assert response.status_code == 200
    assert b"Video deleted." in response.data


def test_new_video_missing_fields_shows_validation_error(client, good_auth):
    before = _count_videos()

    response = client.post(
        "/videos/new",
        data={"title": "", "description": "desc", "duration": "1:00"},
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
    # A plain (non-YouTube) link -- this test is about the watch-link
    # rendering, not duration detection, so it deliberately avoids
    # triggering the YouTube extraction path.
    form = dict(NEW_VIDEO_FORM)
    form["video_url"] = "https://example.com/my-video"

    response = client.post("/videos/new", data=form, auth=good_auth)
    assert response.status_code == 302

    row = _get_video_by_title("A Brand New Test Video")
    assert row is not None
    assert row["video_url"] == "https://example.com/my-video"

    detail = client.get(f"/videos/{row['id']}")
    assert detail.status_code == 200
    assert b"Watch the full video" in detail.data
    assert b"https://example.com/my-video" in detail.data
    # The placeholder gradient thumbnail is still shown alongside the link --
    # this app never builds a real video player.
    assert b"video-player" in detail.data


def test_editing_video_to_clear_url_removes_watch_link(client, good_auth):
    form = dict(NEW_VIDEO_FORM)
    form["video_url"] = "https://example.com/my-video"
    create_response = client.post("/videos/new", data=form, auth=good_auth)
    assert create_response.status_code == 302

    row = _get_video_by_title("A Brand New Test Video")
    video_id = row["id"]
    assert b"Watch the full video" in client.get(f"/videos/{video_id}").data

    edit_form = dict(NEW_VIDEO_FORM)
    edit_form["video_url"] = ""
    response = client.post(f"/videos/{video_id}/edit", data=edit_form, auth=good_auth)
    assert response.status_code == 302

    detail = client.get(f"/videos/{video_id}")
    assert b"Watch the full video" not in detail.data


# --- YouTube duration auto-detection (mocked, no real network calls) -------


def test_youtube_url_with_no_manual_duration_uses_detected_duration(
    client, good_auth, monkeypatch
):
    monkeypatch.setattr(app_module, "extract_youtube_duration", lambda url: "12:34")

    response = client.post(
        "/videos/new",
        data={
            "title": "Auto Duration Video",
            "description": "desc",
            "duration": "",
            "video_url": "https://www.youtube.com/watch?v=abc123",
        },
        auth=good_auth,
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"duration detected automatically (12:34)" in response.data

    row = _get_video_by_title("Auto Duration Video")
    assert row["duration"] == "12:34"


def test_youtube_url_detected_duration_overrides_manual_entry(
    client, good_auth, monkeypatch
):
    monkeypatch.setattr(app_module, "extract_youtube_duration", lambda url: "9:00")

    client.post(
        "/videos/new",
        data={
            "title": "Override Duration Video",
            "description": "desc",
            "duration": "1:11",  # should be ignored in favor of the detected value
            "video_url": "https://youtu.be/xyz789",
        },
        auth=good_auth,
    )

    row = _get_video_by_title("Override Duration Video")
    assert row["duration"] == "9:00"


def test_youtube_extraction_failure_falls_back_to_manual_duration(
    client, good_auth, monkeypatch
):
    monkeypatch.setattr(app_module, "extract_youtube_duration", lambda url: None)

    response = client.post(
        "/videos/new",
        data={
            "title": "Manual Fallback Video",
            "description": "desc",
            "duration": "5:55",
            "video_url": "https://www.youtube.com/watch?v=doesnotmatter",
        },
        auth=good_auth,
    )
    assert response.status_code == 302

    row = _get_video_by_title("Manual Fallback Video")
    assert row["duration"] == "5:55"


def test_youtube_extraction_failure_with_no_manual_duration_shows_error(
    client, good_auth, monkeypatch
):
    monkeypatch.setattr(app_module, "extract_youtube_duration", lambda url: None)
    before = _count_videos()

    response = client.post(
        "/videos/new",
        data={
            "title": "Should Not Be Created",
            "description": "desc",
            "duration": "",
            "video_url": "https://www.youtube.com/watch?v=doesnotmatter",
        },
        auth=good_auth,
    )
    assert response.status_code == 200
    assert b"Couldn&#39;t detect the duration automatically" in response.data
    assert _count_videos() == before


def test_non_youtube_url_does_not_trigger_extraction(client, good_auth, monkeypatch):
    def _fail_if_called(url):
        raise AssertionError("extract_youtube_duration should not be called for a non-YouTube URL")

    monkeypatch.setattr(app_module, "extract_youtube_duration", _fail_if_called)

    response = client.post(
        "/videos/new",
        data={
            "title": "Non-YouTube Link Video",
            "description": "desc",
            "duration": "2:22",
            "video_url": "https://example.com/some-video",
        },
        auth=good_auth,
    )
    assert response.status_code == 302

    row = _get_video_by_title("Non-YouTube Link Video")
    assert row["duration"] == "2:22"


def test_editing_video_with_youtube_url_detects_duration(client, good_auth, monkeypatch):
    monkeypatch.setattr(app_module, "extract_youtube_duration", lambda url: "7:07")

    response = client.post(
        "/videos/1/edit",
        data={
            "title": "Edited With YouTube Link",
            "description": "desc",
            "duration": "",
            "video_url": "https://www.youtube.com/watch?v=edited123",
        },
        auth=good_auth,
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"duration detected automatically (7:07)" in response.data

    connection = db_module.get_db_connection()
    row = connection.execute("SELECT duration FROM videos WHERE id = 1").fetchone()
    connection.close()
    assert row["duration"] == "7:07"
