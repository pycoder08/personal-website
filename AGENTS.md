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
  icons, not real image files (no video hosting exists yet).
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
`/portfolio/<id>/delete`) are protected by plain HTTP Basic Auth (see
`require_auth` in `backend/app.py`) -- no sessions, JWTs, or user table,
since this is a single-owner personal site. All read-only routes stay
public.

Credentials come from the `ADMIN_USERNAME` / `ADMIN_PASSWORD` environment
variables. `app.py` retains an `admin` / `changeme` fallback only for local
development; `wsgi.py` requires both variables and will not start a real
server with the fallback.

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
- The videos section is NOT in the database — it's a plain Python list in
  `app.py`, since there's no real video hosting yet.
- Windows paths: use `venv\Scripts\python` / `venv\Scripts\pip`, not the
  Unix `venv/bin/...` paths.
