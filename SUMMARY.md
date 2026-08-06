# Personal Site -- Full Reference Build

This is a fully-built-out reference version of the personal site concept:
a Flask app with Jinja2 templates, a SQLite-backed blog and portfolio, a
working "add post" form, a videos section, and a complete visual redesign.
It's meant to show what a polished version of the site could look like --
your hand-written copy in the other project folder is still the one you're
learning from.

## What's here

```
personal-website-full/
├── backend/
│   ├── app.py          Flask app: every route lives here
│   ├── db.py           Opens a SQLite connection (shared by all scripts)
│   ├── init_db.py      Drops + recreates blog.db and seeds sample data
│   ├── check_db.py     Prints every row in both tables (sanity check)
│   └── blog.db         The SQLite database (created by init_db.py)
├── templates/           Jinja2 templates (Flask renders these)
│   ├── base.html         Shared header / nav / footer layout
│   ├── index.html        Home page
│   ├── portfolio.html    Portfolio grid (from the database)
│   ├── blog_list.html    Blog feed (from the database)
│   ├── blog_post.html    Single post detail page
│   ├── blog_new.html     "Add Post" form
│   ├── videos.html       Video grid (from the database)
│   ├── video_detail.html Single video detail page
│   ├── video_form.html   "Add/Edit Video" form
│   └── 404.html          Not-found page
├── static/
│   ├── css/style.css             The full stylesheet (design system + all pages)
│   └── images/portfolio/         Uploaded portfolio screenshots (git-tracked, real content)
├── tests/                Pytest test suite (routes, auth, CRUD, uploads, validation)
├── conftest.py           Shared pytest fixtures: isolated temp DB + upload dir
├── requirements.txt      Pinned direct runtime dependencies
├── requirements-dev.txt  Adds pytest on top of requirements.txt, for running tests
├── wsgi.py               Production entry point (credentials required, debug off)
└── venv/                 Local virtual environment
```

## Installation

From the `personal-website-full` folder:

```
venv\Scripts\python -m pip install -r requirements.txt
venv\Scripts\python backend\init_db.py   # (re)creates and seeds blog.db -- only needed once, or to reset
```

`requirements.txt` contains only the direct runtime dependencies: Flask and
the Waitress WSGI server. Pip installs their transitive dependencies.

## Local development

```powershell
venv\Scripts\python backend\app.py
```

This uses Flask's development server and defaults debug mode on for the
existing local workflow. Set `$env:FLASK_DEBUG = "0"` first when you want
local debug mode off. Never expose the development server to visitors.

Then open **http://127.0.0.1:5000/** in a browser. Press `Ctrl+C` in the
terminal to stop the server.

If you ever want to wipe your changes and start over with the original
sample data, just re-run `init_db.py` -- it drops and recreates both
tables from scratch.

## Running the test suite

```
venv\Scripts\python -m pip install -r requirements-dev.txt
venv\Scripts\python -m pytest
```

The suite (`tests/`, fixtures in the root `conftest.py`) uses Flask's
`test_client()` -- no server needs to be running. It's fully isolated from
real data: `conftest.py` sets `BLOG_DB_PATH` and `PORTFOLIO_IMAGE_DIR`
environment variables to a temporary directory before `backend/app.py` and
`backend/db.py` are imported, so the real `backend/blog.db` and
`static/images/portfolio/` are never opened or written to. Each test gets a
freshly reseeded copy of the schema (reusing `init_db.py`'s
`init_schema`/`seed_sample_data` functions, so there's one source of truth
for the schema) and a cleared-out upload directory, and runs against fixed
test admin credentials rather than the real environment's.

## Real deployment with Waitress

Set unique admin credentials in the environment before starting the real
server. Both variables are required: the local `admin` / `changeme` fallback
must never be used for a deployment.

```powershell
$env:ADMIN_USERNAME = "your-private-admin-name"
$env:ADMIN_PASSWORD = "a-long-unique-password"
venv\Scripts\waitress-serve --host=127.0.0.1 --port=5000 wsgi:application
```

The `wsgi.py` entry point refuses to start if either credential is absent and
forces Flask debug mode off even if `FLASK_DEBUG=1` is set. It preserves the
existing absolute template, static, and SQLite paths. `127.0.0.1` is suitable
behind a reverse proxy on the same machine; choose the bind address and port
that match the actual host setup.

Required production environment variables:

- `ADMIN_USERNAME` -- the single site owner's Basic Auth username.
- `ADMIN_PASSWORD` -- a long, unique Basic Auth password.

`FLASK_DEBUG` controls only the direct local-development command. It has no
effect on the Waitress production entry point.

## Routes

| Route | Method | Auth? | What it does |
|---|---|---|---|
| `/` | GET | No | Home page: hero, about blurb, 3 featured projects, 3 recent posts |
| `/portfolio` | GET | No | Full portfolio grid, read from the `portfolio_items` table |
| `/portfolio/new` | GET | Yes | The "add project" form |
| `/portfolio/new` | POST | Yes | Validates the fields, inserts a new row (parameterized query), redirects to `/portfolio` |
| `/portfolio/<id>/edit` | GET | Yes | The "edit project" form, pre-filled from the existing row; 404 if the id doesn't exist |
| `/portfolio/<id>/edit` | POST | Yes | Validates the fields, updates the row (parameterized query), redirects to `/portfolio` |
| `/portfolio/<id>/delete` | POST | Yes | Deletes the row (parameterized query), redirects to `/portfolio` |
| `/blog` | GET | No | Full blog feed, read from the `posts` table, newest first; supports `?tag=X` filtering and shows the tag pill bar |
| `/blog/<id>` | GET | No | Full text of one post; 404 if the id doesn't exist |
| `/blog/new` | GET | Yes | The "add post" form (includes the tag field + datalist of existing tags) |
| `/blog/new` | POST | Yes | Validates the fields, inserts a new row (parameterized query), redirects to `/blog` |
| `/blog/<id>/edit` | GET | Yes | The "edit post" form, pre-filled from the existing row (same template as "add post"); 404 if the id doesn't exist |
| `/blog/<id>/edit` | POST | Yes | Validates the fields, updates the row (parameterized query), redirects to the post |
| `/blog/<id>/delete` | POST | Yes | Deletes the row (parameterized query), redirects to `/blog` |
| `/videos` | GET | No | Full video grid, read from the `videos` table |
| `/videos/new` | GET | Yes | The "add video" form |
| `/videos/new` | POST | Yes | Validates the fields, inserts a new row (parameterized query), redirects to `/videos` |
| `/videos/<id>` | GET | No | Single video detail page; 404 if the id doesn't exist |
| `/videos/<id>/edit` | GET | Yes | The "edit video" form, pre-filled from the existing row; 404 if the id doesn't exist |
| `/videos/<id>/edit` | POST | Yes | Validates the fields, updates the row (parameterized query), redirects to the video's detail page |
| `/videos/<id>/delete` | POST | Yes | Deletes the row (parameterized query), redirects to `/videos` |

### Logging in

The "Yes" routes above are protected with plain HTTP Basic Auth (no
sessions or user accounts -- this is a single-owner site). Your browser
will prompt for a username/password the first time you hit one of them
(e.g. clicking "+ New Post", "Edit", or "Delete").

Default local-dev credentials (only valid until you set real env vars):

```
username: admin
password: changeme
```

Override them by setting `ADMIN_USERNAME` and `ADMIN_PASSWORD` before
starting the local server. The production WSGI entry point requires both
values and will not use these defaults.

## Database schema

**posts** -- `id, title, date_iso, date_display, tag, excerpt, body`
`date_iso` (e.g. `2026-07-18`) is used for sorting; `date_display`
(e.g. `July 18, 2026`) is what's shown on the page. The add-post form
only asks for one date field (a date picker) -- the app converts it to
both formats for you. `tag` (e.g. `SQL`, `Design`) powers the pill-style
filter bar on `/blog` and `/blog?tag=X`.

**portfolio_items** -- `id, title, description, color_start, color_end, icon, image_filename`
Each project renders as a card. If `image_filename` is set, the card shows
a real uploaded screenshot (`<img src="/static/images/portfolio/<filename>">`);
if it's `NULL` (the default for seed data, and for any row where the upload
was skipped), the card falls back to a CSS gradient (`color_start` to
`color_end`) with an emoji icon, exactly like before.

**videos** -- `id, title, description, duration, color_start, color_end, video_url`
Each video renders as a card with a CSS-gradient (`color_start` to
`color_end`) placeholder thumbnail and a `duration` badge -- there's no
uploaded thumbnail image or real video file behind it. `video_url` is
optional/nullable: when set (via `/videos/new` or `/videos/<id>/edit`), the
video's detail page (`/videos/<id>`) shows a plain link -- "Watch the full
video" -- pointing at it, opened in a new tab; when it's `NULL` (the default
for all seed data), the detail page shows only the placeholder, no link.
This is intentionally not a real video player or embed -- linking out to
wherever the video is actually hosted (e.g. YouTube) is the full extent of
video "hosting" this app does.

### Portfolio image uploads

`/portfolio/new` and `/portfolio/<id>/edit` accept an optional file upload
(the form is `multipart/form-data`, field name `image`). Rules enforced in
`backend/app.py`:

- Allowed extensions: `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp` -- checked
  against the actual file extension, not the browser-supplied MIME type.
  Anything else is rejected with a normal form validation error (same
  pattern as the "please fill out every field" error), no crash.
- Max size: **5MB** per upload, enforced via Flask's `MAX_CONTENT_LENGTH`.
  Going over shows a friendly `413.html` page instead of a raw error.
- Uploaded files are never saved under their original name. Each one is
  passed through `werkzeug.utils.secure_filename` and then renamed to a
  generated `uuid4` + extension before being written to
  `static/images/portfolio/`, so two uploads can never collide and a
  crafted filename can't escape that folder.
- Editing a project with a new file replaces the old image (the old file
  is deleted from disk); leaving the file field empty on edit keeps
  whatever image (or lack of one) the project already had.
- Deleting a project also deletes its image file from disk, if it has one.
- `static/images/portfolio/` is committed to git (with a `.gitkeep` so the
  folder exists even before any upload) -- unlike `blog.db`, uploaded
  images are real content, not generated data, so they aren't git-ignored.

The videos section *is* in the database (see the `videos` schema above),
with the same create/edit/delete flow as portfolio -- the difference is
there's no file upload for videos, since this app deliberately doesn't do
real video file hosting. Instead, an optional `video_url` column lets a
video link out to wherever it's actually hosted (e.g. YouTube).

## Design notes

- Design system lives entirely in `static/css/style.css`, driven by CSS
  custom properties at the top (`--primary`, `--bg`, `--radius`, etc.) so
  colors/spacing can be tweaked from one place.
- Includes a basic dark-mode variant via `prefers-color-scheme: dark`.
- Responsive down to mobile widths (nav wraps, form padding shrinks, etc.)
- Portfolio thumbnails now support real uploaded screenshots (see
  "Portfolio image uploads" above), falling back to a CSS gradient plus
  emoji/icon when no image has been uploaded. Video "thumbnails" are still
  pure CSS gradients plus a play icon -- there's no uploaded thumbnail
  image or video file, though a video can now optionally link out to a
  real recording hosted elsewhere (see "Videos" schema section above).

## Verified before handoff

- `init_db.py` runs cleanly and seeds 6 blog posts (with full body text),
  9 portfolio items, and 6 videos.
- The full pytest suite (58 tests, including `tests/test_videos.py`) passes.
- Confirmed the real `backend/blog.db` is byte-for-byte unchanged (sha256
  hash compared before/after) by a full pytest run -- the test suite never
  touches it.
- Started the Flask server and curl-tested every route above, including the
  new `/videos/new`, `/videos/<id>/edit`, `/videos/<id>/delete` routes:
  read routes return 200 (or 404 for a nonexistent id), write routes return
  401 without/with-wrong credentials and succeed with the right ones.
- Created a video with a `video_url` via curl, confirmed the "Watch the
  full video" link appeared on its detail page and pointed at the right
  URL, edited it to clear the URL and confirmed the link disappeared,
  then deleted it and confirmed the row was gone -- then reset the
  database back to the clean seed data with `init_db.py` afterward.
- Server was stopped after testing -- nothing is left listening on port 5000.
