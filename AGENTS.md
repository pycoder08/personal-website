# AGENTS.md

Shared context for any AI coding tool working in this repo (Claude Code,
Codex, Antigravity, etc.).

## What this project is

A fully-built-out reference/demo version of a personal website (portfolio +
blog + videos, with a "mock social media" feel — an Instagram-style
portfolio grid and a dynamic, database-backed blog). It exists to show
what a polished version of a much simpler hand-written project (in the
sibling folder `personal-website`) could look like. This is the sandbox
for exploring new features; the hand-written copy is a separate learning
project and must never be touched from here.

## Stack

Python 3 + Flask (Jinja2 templates) + SQLite (via the stdlib `sqlite3`
module, no ORM). Plain HTML/CSS on the frontend — no JS framework, no
build step. Direct runtime dependencies are pinned in `requirements.txt`
and installed into a `venv/` at the project root.

## Structure

- `backend/app.py` — every Flask route lives here.
- `backend/db.py` — shared SQLite connection helper (resolves the DB path
  from `__file__`, so it works regardless of current working directory).
- `backend/init_db.py` — drops + recreates `blog.db` and seeds sample data.
  Run this whenever the schema changes.
- `backend/check_db.py` — prints every row in every table (quick sanity check).
- `templates/` — Jinja2 templates, all extending `base.html`.
- `static/css/style.css` — the entire design system (CSS custom properties
  at the top control the palette/spacing).
- `static/images/portfolio/` — uploaded portfolio screenshots (see "Portfolio
  image uploads" below). Contains a `.gitkeep` so git tracks the folder even
  when no images have been uploaded yet.
- `static/images/` — video "thumbnails" are still pure CSS gradients + emoji
  icons, not real image/video files -- there's no video file hosting, and
  none is planned (see "Videos" below for what real video links look like).
- `tests/` — pytest test suite; `conftest.py` at the project root holds the
  shared fixtures (isolated temp DB + upload dir, test admin credentials).

## Conventions

- All SQL that includes user or variable input MUST use parameterized
  queries (`?` placeholders), never string formatting/concatenation.
- Keep the whole site running as a single Flask app serving templates —
  don't reintroduce standalone static HTML files.
- New tables/columns: update `init_db.py`'s `CREATE TABLE` and seed data
  together so a fresh clone can run `init_db.py` and get a working DB.
- Match the existing CSS design system (custom properties in
  `static/css/style.css`) rather than introducing new ad-hoc colors/spacing.

## Auth for write routes

All create/edit/delete routes (`/blog/new`, `/blog/<id>/edit`,
`/blog/<id>/delete`, `/portfolio/new`, `/portfolio/<id>/edit`,
`/portfolio/<id>/delete`, `/videos/new`, `/videos/<id>/edit`,
`/videos/<id>/delete`) are protected by plain HTTP Basic Auth (see
`require_auth` in `backend/app.py`) -- no sessions, JWTs, or user table,
since this is a single-owner personal site. All read-only routes stay
public.

Credentials come from the `ADMIN_USERNAME` / `ADMIN_PASSWORD` environment
variables. `app.py` retains an `admin` / `changeme` fallback only for local
development; `wsgi.py` requires both variables and will not start a real
server with the fallback.

## Flash messages

Every create/edit/delete route calls Flask's `flash()` right before its
`redirect(...)` (e.g. "Post published.", "Project updated.", "Video
deleted."), rendered by markup in `templates/base.html` (`.flash-message` /
`.flash-messages` in `static/css/style.css`, styled with a distinct success
color from `.form-error`'s). This requires `app.secret_key` to sign the
session cookie, read from the `SECRET_KEY` environment variable with a
fixed local-dev-only fallback -- same pattern as `ADMIN_USERNAME` /
`ADMIN_PASSWORD` above. `wsgi.py` requires `SECRET_KEY` in production
alongside the two admin variables.

## Blog tag normalization

`normalize_tag()` in `backend/app.py` runs on every `/blog/new` and
`/blog/<id>/edit` POST: if the submitted tag matches an existing tag
case-insensitively (whitespace-trimmed), it's rewritten to that existing
tag's exact stored casing before the INSERT/UPDATE, so typing "sql" when
"SQL" already exists reuses "SQL" instead of creating a near-duplicate.
Editing excludes the post's own current row from the comparison, so a post
that's the only one using a given tag can still have that tag's casing
corrected. This is route-level logic only -- the `tag` column is still a
plain TEXT column, no separate tags table.

## Blog search and pagination

`/blog` accepts `?q=` (case-insensitive substring match against title,
excerpt, and body via parameterized `LIKE` queries) and `?page=` (5 posts
per page), both combinable with the existing `?tag=` filter. The search box
and Previous/Next links live in `templates/blog_list.html`; Previous/Next
preserve whichever of `tag`/`q` are active. A search with no results shows
a distinct "No posts match ..." empty state, separate from the "No posts
tagged ..." state. Portfolio and videos are not paginated -- their seed
counts don't warrant it.

## Favicon and Open Graph tags

`templates/base.html`'s `<head>` has an inline SVG data-URI favicon (no
image file to source/generate) and `og:title` / `og:description` /
`og:type` / `og:site_name` meta tags. `og:title` and `og:description` are
Jinja blocks (same pattern as the existing `{% block title %}`) that
default to the site's generic name/description and are overridden per-item
on `templates/blog_post.html` and `templates/video_detail.html` (post/video
title and excerpt/description, `og:type` set to `article` / `video.other`).

## Continuous integration

`.github/workflows/tests.yml` runs the pytest suite on every push and pull
request targeting `master`: checkout, set up Python 3.12, install
`requirements.txt` + `requirements-dev.txt`, run `pytest`. One job, no OS/
Python version matrix -- this is a personal site, not a library that needs
broad compatibility testing.

## Portfolio image uploads

`portfolio_items` has an `image_filename` column (nullable). When set, the
portfolio card renders `<img src="/static/images/portfolio/<filename>">`
instead of the CSS gradient + emoji thumbnail; when null (the default for
old/seeded rows), the gradient + icon rendering is unchanged. This applies
to both `templates/portfolio.html` and the "Featured Work" section of
`templates/index.html`.

Upload handling lives in `backend/app.py` (`/portfolio/new` and
`/portfolio/<id>/edit`, both `multipart/form-data` POSTs with an `image`
file field):

- **Extension allowlist**: only `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp` are
  accepted, checked against the real file extension -- never the
  client-supplied Content-Type/MIME header, which can't be trusted.
- **Max size**: 5MB, enforced via `app.config["MAX_CONTENT_LENGTH"]`. Over
  that limit, Flask raises a 413 before the view runs, handled by a
  friendly `templates/413.html` page (registered in `app.errorhandler(413)`)
  instead of a raw error.
- **Filenames**: never trust the client-supplied filename. Every upload is
  passed through `werkzeug.utils.secure_filename` and then renamed to a
  fresh `uuid4().hex` + original extension before being saved to
  `static/images/portfolio/`, so uploads can't collide or path-traverse.
- **Edit replaces, delete cleans up**: uploading a new file on `/edit`
  deletes the old file from disk before saving the new one; leaving the
  file field blank on edit keeps the existing image. Deleting a portfolio
  item (`/portfolio/<id>/delete`) also deletes its image file from disk, if
  it has one.
- Uploaded images are real site content (not build artifacts), so
  `static/images/portfolio/` is intentionally **not** git-ignored.

## Videos

`videos` is a real table (`id, title, description, duration, color_start,
color_end, video_url`), following the exact same CRUD shape as
`portfolio_items` (`/videos/new`, `/videos/<id>/edit`, `/videos/<id>/delete`,
all `require_auth`-gated). Unlike portfolio, there is **no file upload** --
this is a personal site, not a video hosting platform, so no real video
files are ever stored on disk.

- `color_start`/`color_end` drive the same CSS-gradient placeholder
  thumbnail used everywhere a real image/video file doesn't exist (shown on
  both the `/videos` grid and the `/videos/<id>` detail page). The add-video
  form doesn't ask for these anymore -- every new video gets the same fixed
  gradient (`DEFAULT_VIDEO_COLOR_START`/`DEFAULT_VIDEO_COLOR_END` in
  `backend/app.py`, matching the site's `--primary`/`--accent` brand
  colors). Editing a video never changes its stored colors.
- `video_url` is optional/nullable TEXT. When set, `/videos/<id>` renders a
  plain `<a href="{{ video_url }}">Watch the full video</a>` link (opens in
  a new tab) below the placeholder -- not a custom player, not an embed.
  When it's null (the default, and true for all seed data), the detail page
  just shows the placeholder with no watch link, same as before.
- Leave the `video_url` field blank on the add/edit form to keep a video
  placeholder-only.
- If `video_url` looks like a YouTube link (`youtube.com`/`youtu.be`), the
  `duration` field is auto-filled via `yt-dlp` (`extract_youtube_duration()`
  in `backend/app.py`) and overrides whatever's typed manually. Non-YouTube
  links, or a failed lookup, fall back to the manually-typed duration; if
  there isn't one either, the form shows a validation error rather than
  saving an empty duration. Tests must always monkeypatch
  `extract_youtube_duration` -- never let the suite hit the real network.

## Running it

From this folder, install dependencies:

```
venv\Scripts\python -m pip install -r requirements.txt
```

For local development:

```
venv\Scripts\python backend\init_db.py   # (re)creates and seeds blog.db
venv\Scripts\python backend\app.py       # Flask dev server; debug defaults on
```

Set `FLASK_DEBUG=0` to disable local debug mode. Never expose Flask's
development server publicly.

For a real deployment, set non-default `ADMIN_USERNAME` and
`ADMIN_PASSWORD`, initialize the database once, and run Waitress:

```
venv\Scripts\waitress-serve --host=127.0.0.1 --port=5000 wsgi:application
```

`wsgi.py` refuses to start without both admin variables and forces debug
off regardless of `FLASK_DEBUG`. Choose the bind address and port appropriate
for the host or reverse proxy. See `SUMMARY.md` for the complete deployment
instructions, route table, and schema.

## Running the test suite

A pytest-based test suite lives in `tests/` (fixtures in the root
`conftest.py`). It never touches the real `backend/blog.db` or
`static/images/portfolio/` -- `conftest.py` points `BLOG_DB_PATH` and
`PORTFOLIO_IMAGE_DIR` at a temporary directory before the app is ever
imported, and reseeds a fresh copy of the schema (via `init_db.py`'s
`init_schema`/`seed_sample_data`, not a hand-copied schema) before every
test.

```
venv\Scripts\python -m pip install -r requirements-dev.txt
venv\Scripts\python -m pytest
```

`requirements-dev.txt` layers `pytest` on top of `requirements.txt` --
`requirements.txt` itself stays production-only, per the convention
explained in its own comment.

## Multi-agent branches (if in use)

If this repo uses the branch-per-agent workflow (see
`../MULTI-AGENT-WORKFLOW.md`), branches follow `<agent>/<task-slug>`.
Don't merge a `*/<task-slug>` branch without running `/deliberate
<task-slug>` first if more than one agent branch exists for that task.

## Known gotchas

- `backend/blog.db` is git-ignored (generated data) — always regenerate
  it via `init_db.py` after a fresh clone or after a schema change.
- Videos are a real database table (`videos`), same CRUD pattern as
  portfolio -- see "Videos" above. There's still no real video file
  hosting; `video_url` only ever holds a link to somewhere else (e.g.
  YouTube), never an uploaded file.
- Windows paths: use `venv\Scripts\python` / `venv\Scripts\pip`, not the
  Unix `venv/bin/...` paths.
