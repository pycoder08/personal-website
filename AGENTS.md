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
build step. Dependencies are managed via a `venv/` at the project root
(Flask is already installed there).

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
- `static/images/` — currently empty; portfolio/video "thumbnails" are pure
  CSS gradients + emoji icons, not real image files.

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
variables, with a local-dev-only fallback of `admin` / `changeme` baked
into `app.py`. **That fallback must be overridden with real env vars
before this app is ever deployed anywhere public.**

## Running it

From this folder:
```
venv\Scripts\python backend\init_db.py   # (re)creates and seeds blog.db
venv\Scripts\python backend\app.py       # starts the dev server
```
Then open `http://127.0.0.1:5000/`. See `SUMMARY.md` for the full route
table and schema.

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
