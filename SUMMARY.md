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
│   ├── videos.html       Video grid (placeholder thumbnails)
│   ├── video_detail.html Single video detail page
│   └── 404.html          Not-found page
├── static/
│   ├── css/style.css     The full stylesheet (design system + all pages)
│   └── images/           (empty -- everything uses CSS-drawn placeholders)
└── venv/                 Existing virtual environment (Flask already installed)
```

## How to run it

From the `personal-website-full` folder:

```
venv\Scripts\python backend\init_db.py   # (re)creates and seeds blog.db -- only needed once, or to reset
venv\Scripts\python backend\app.py       # starts the Flask dev server
```

Then open **http://127.0.0.1:5000/** in a browser. Press `Ctrl+C` in the
terminal to stop the server.

If you ever want to wipe your changes and start over with the original
sample data, just re-run `init_db.py` -- it drops and recreates both
tables from scratch.

## Routes

| Route | Method | What it does |
|---|---|---|
| `/` | GET | Home page: hero, about blurb, 3 featured projects, 3 recent posts |
| `/portfolio` | GET | Full portfolio grid, read from the `portfolio_items` table |
| `/blog` | GET | Full blog feed, read from the `posts` table, newest first |
| `/blog/<id>` | GET | Full text of one post; 404 if the id doesn't exist |
| `/blog/new` | GET | The "add post" form |
| `/blog/new` | POST | Validates the fields, inserts a new row (parameterized query), redirects to `/blog` |
| `/videos` | GET | Video grid (sample data defined directly in `app.py`, not a DB table) |
| `/videos/<id>` | GET | Single video detail placeholder page |

## Database schema

**posts** -- `id, title, date_iso, date_display, excerpt, body`
`date_iso` (e.g. `2026-07-18`) is used for sorting; `date_display`
(e.g. `July 18, 2026`) is what's shown on the page. The add-post form
only asks for one date field (a date picker) -- the app converts it to
both formats for you.

**portfolio_items** -- `id, title, description, color_start, color_end, icon`
Each project renders as a card with a CSS gradient (`color_start` to
`color_end`) and an emoji icon standing in for a real screenshot.

The videos section is *not* in the database -- it's a small Python list
inside `app.py`, since there's no real video content or hosting behind it.
If you ever add real project screenshots or video files, swapping the
placeholders for `<img>`/`<video>` tags is a small, contained change.

## Design notes

- Design system lives entirely in `static/css/style.css`, driven by CSS
  custom properties at the top (`--primary`, `--bg`, `--radius`, etc.) so
  colors/spacing can be tweaked from one place.
- Includes a basic dark-mode variant via `prefers-color-scheme: dark`.
- Responsive down to mobile widths (nav wraps, form padding shrinks, etc.)
- Portfolio and video "thumbnails" are pure CSS gradients plus an
  emoji/icon -- no image files needed, but the markup is ready to swap in
  real images later.

## Verified before handoff

- `init_db.py` runs cleanly and seeds 6 blog posts (with full body text)
  and 9 portfolio items.
- Started the Flask server and curl-tested every route above: all return
  200 (or 404 for a nonexistent id, as expected).
- Submitted the add-post form via curl -- confirmed the new row appeared
  in `blog.db` and on `/blog`, then reset the database back to the clean
  seed data with `init_db.py` afterward.
- Loaded the home and videos pages in a browser to confirm templates
  render correctly with no console errors.
- Server was stopped after testing -- nothing is left running.
