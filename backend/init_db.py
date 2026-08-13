"""Creates blog.db from scratch and fills it with sample data.

Run this any time you want a clean slate:

    venv/Scripts/python backend/init_db.py

It drops the old tables (if any) and recreates them, so it's safe to
run more than once.
"""

from db import get_db_connection

POSTS = [
    (
        "Why I'm Building This Site From Scratch",
        "2026-06-02",
        "June 2, 2026",
        "Process",
        "Instead of using a template, I decided to hand-write my own HTML, "
        "CSS, and a tiny Flask backend. Here's why I think the slower "
        "route is actually the faster one.",
        "Instead of using a template, I decided to hand-write my own HTML, "
        "CSS, and a tiny Flask backend. It would have been faster to pick a "
        "theme off the shelf, but the whole point of this project is to "
        "understand what's happening under the hood.\n\n"
        "Every button, every grid, every route is something I typed myself "
        "at least once, even if I later asked for help polishing it up. "
        "That's the deal I made with myself: I'm allowed to look things up, "
        "I'm allowed to ask for a second opinion, but I'm not allowed to "
        "paste in code I don't understand.\n\n"
        "So far that's meant a lot of small wins: my first working nav bar, "
        "my first database query, my first form that actually saves "
        "something. None of it is groundbreaking, but it's mine, and I "
        "understand every line of it.\n\n"
        "The plan going forward is to keep this blog itself as a build log "
        "of sorts -- part personal site, part running diary of what I "
        "learned that week.",
    ),
    (
        "My First Real SQL Query (And Why It Didn't Work)",
        "2026-06-14",
        "June 14, 2026",
        "SQL",
        "I finally connected Flask to a real SQLite database, and of "
        "course my very first query returned nothing. Here's what went "
        "wrong and what finally fixed it.",
        "I finally connected Flask to a real SQLite database this week. Big "
        "milestone. The excitement lasted about four minutes, right up "
        "until my very first SELECT statement returned an empty list "
        "instead of the two rows I knew were sitting in the table.\n\n"
        "Turns out the bug was embarrassingly simple: I had opened a "
        "connection to a database file in the wrong folder. SQLite happily "
        "created a brand new, empty blog.db right next to the one I "
        "actually wanted, and my query was technically correct -- just "
        "pointed at the wrong file.\n\n"
        "The fix was to stop relying on whatever folder I happened to be "
        "standing in when I ran the script, and instead build the database "
        "path from the location of the Python file itself. Once every "
        "script agreed on where the database actually lived, the query "
        "worked on the first try.\n\n"
        "Lesson learned: 'it returned nothing' is almost never a SQL "
        "problem. It's almost always a 'I'm not looking at the file I "
        "think I'm looking at' problem.",
    ),
    (
        "Designing a Grid That Doesn't Look Like a Spreadsheet",
        "2026-06-27",
        "June 27, 2026",
        "Design",
        "My first pass at the portfolio page was technically a grid, but "
        "it looked like a table of contents. Here's how a bit of spacing "
        "and a hover effect changed everything.",
        "My first pass at the portfolio page was technically a grid -- "
        "boxes lined up in rows and columns -- but it looked more like a "
        "spreadsheet than a showcase. Everything was cramped against the "
        "edges, the borders were a flat gray, and nothing gave your eye "
        "anywhere to rest.\n\n"
        "The fix wasn't really about the grid at all. It was whitespace. "
        "Adding real gaps between cards, padding inside them, and a "
        "consistent rounded corner made the exact same content feel "
        "designed instead of default.\n\n"
        "The other big change was a hover effect: cards lift slightly and "
        "gain a soft shadow when you mouse over them. It's a tiny bit of "
        "motion, but it makes the grid feel alive instead of static, and "
        "it gives visual feedback that the cards are actually clickable.\n\n"
        "None of this required new tools or frameworks -- just box-shadow, "
        "transform, and transition, three properties I'd seen a hundred "
        "times before but never really understood the effect of until I "
        "played with the numbers myself.",
    ),
    (
        "Turning a Hardcoded List Into a Database Table",
        "2026-07-09",
        "July 9, 2026",
        "SQL",
        "The portfolio page used to be a wall of copy-pasted HTML. Moving "
        "the projects into a database table meant one new project is now "
        "one new row, not one new block of markup.",
        "The portfolio page used to be a wall of copy-pasted HTML -- one "
        "block per project, each one slightly different from the last "
        "because I'd tweak one and forget to update the others. Adding a "
        "ninth project meant finding the eighth one, copying it, and "
        "hoping I didn't break the closing tags.\n\n"
        "Moving the projects into a database table fixed that completely. "
        "Now the page loops over whatever rows are in the portfolio_items "
        "table and renders each one the same way, every time. Adding a "
        "new project means adding one row, not editing HTML at all.\n\n"
        "It also made me think differently about what a 'project' even is "
        "as data: a title, a short description, and -- since I don't have "
        "real screenshots yet -- a couple of colors to build a placeholder "
        "thumbnail out of CSS gradients instead of an image file.\n\n"
        "It's a small refactor, but it's the first time this site has "
        "actually felt like an application instead of a stack of pages.",
    ),
    (
        "What 'Add Post' Actually Does Behind the Scenes",
        "2026-07-18",
        "July 18, 2026",
        "Backend",
        "This post exists because the form on /blog/new works now. Here's "
        "a walkthrough of what happens between clicking Publish and seeing "
        "the new post show up in the feed.",
        "This post exists because the form on /blog/new works now, and "
        "writing a post about the form felt like the most honest way to "
        "test it.\n\n"
        "Here's what happens when you click Publish: the browser sends a "
        "POST request with the title, date, excerpt, and body as form "
        "data. Flask reads each of those fields, checks that none of them "
        "are empty, and formats the date into something human-readable.\n\n"
        "Then comes the part I was most nervous about getting wrong: "
        "saving user-typed text into a database without leaving a security "
        "hole. The trick is a parameterized query -- instead of gluing the "
        "title and body directly into a SQL string, you leave placeholders "
        "(question marks) and hand the actual values to SQLite separately. "
        "That way there's no way for someone to type something that gets "
        "interpreted as SQL instead of as text.\n\n"
        "Once the row is inserted, the app redirects back to the blog list, "
        "which re-reads the table from scratch -- so the new post just "
        "appears at the top, sorted by date like everything else. No "
        "special-casing required.",
    ),
    (
        "Giving the Videos Page an Actual Purpose",
        "2026-07-24",
        "July 24, 2026",
        "Design",
        "The videos page sat as a single 'coming later' sentence for "
        "weeks. Here's how I turned it into a YouTube-style grid without "
        "hosting a single real video file.",
        "The videos page sat as a single 'coming later' sentence for weeks "
        "-- which was fine, because portfolio and blog were the priority. "
        "But once those felt solid, it was time to actually build the "
        "thing out.\n\n"
        "The catch is I don't have any real video files, and I'm not "
        "trying to stand up video hosting for a personal site. So instead "
        "of a real <video> player, each entry is a placeholder thumbnail "
        "-- a colored block with a play icon drawn in CSS -- that links to "
        "a detail page with a bigger version of the same placeholder plus "
        "a title and description.\n\n"
        "It's a bit of a magic trick: from a distance, a grid of colorful "
        "thumbnails with titles and durations reads exactly like a real "
        "video gallery. Nobody needs actual footage to evaluate whether "
        "the layout, spacing, and hover states feel right.\n\n"
        "When there is real video content to add later, the swap is easy: "
        "replace the placeholder div with a real thumbnail image and the "
        "detail page's placeholder with an actual <video> tag. The "
        "surrounding structure doesn't have to change at all.",
    ),
]

PORTFOLIO_ITEMS = [
    (
        "Personal Site Rebuild",
        "A full rebuild of this very site: Flask backend, SQLite-backed "
        "blog, and a from-scratch CSS design system.",
        "Started as a hand-written HTML/CSS exercise, then grew into a "
        "full Flask + Jinja2 + SQLite app with CRUD for blog posts, "
        "portfolio items, and videos, HTTP Basic Auth for admin routes, "
        "a pytest suite, and CI on every push. Self-hosted on a "
        "Raspberry Pi 5 behind Waitress.",
        "#6366f1",
        "#8b5cf6",
    ),
    (
        "SQL Study Tracker",
        "A command-line tool that logs study sessions to a local database "
        "and prints weekly summaries of time spent per topic.",
        "Built to answer one question honestly: was I actually studying "
        "math as much as I thought? Each session gets logged with a "
        "topic and duration, and a weekly summary command aggregates "
        "everything into a per-topic breakdown straight in the "
        "terminal -- no spreadsheet required.",
        "#0ea5e9",
        "#22d3ee",
    ),
    (
        "Weather CLI",
        "A small Python script that fetches a forecast for any city and "
        "prints a clean, color-coded summary straight to the terminal.",
        "Pulls current conditions and a short forecast from a public "
        "weather API, then formats the output with ANSI color codes so "
        "temperature extremes and rain chances are readable at a glance "
        "without opening a browser tab.",
        "#f97316",
        "#facc15",
    ),
    (
        "Budget Tracker Automation",
        "A spreadsheet automation project that categorizes transactions "
        "and flags months where spending jumps more than 15%.",
        "Reads exported transaction data, assigns each row a category "
        "based on a set of keyword rules, and compares month-over-month "
        "totals per category -- flagging anything that jumps more than "
        "15% so it's easy to catch a spending pattern before it becomes "
        "a habit.",
        "#10b981",
        "#34d399",
    ),
    (
        "Chess Puzzle Solver",
        "A brute-force puzzle solver for small chess endgames, built to "
        "learn recursion and board-state representation.",
        "Represents the board as a simple grid and searches recursively "
        "for a forced mate within a small number of moves. Not fast "
        "enough for anything beyond small endgames, but it was never "
        "about speed -- it was about finally understanding recursion by "
        "watching it search a real problem.",
        "#1f2937",
        "#4b5563",
    ),
    (
        "Flask Blog Engine",
        "The mini blogging engine powering this site's /blog section, "
        "complete with a parameterized add-post form.",
        "Posts live in a SQLite table and render through Jinja2 "
        "templates, with tag filtering, search, and pagination layered "
        "on top over time. The add-post form uses parameterized queries "
        "throughout, so there's no way for typed content to be "
        "interpreted as SQL.",
        "#e11d48",
        "#fb7185",
    ),
    (
        "Desktop File Organizer",
        "A script that watches a downloads folder and automatically sorts "
        "new files into folders by type and date.",
        "Runs as a background watcher on the downloads folder and moves "
        "each new file into a type-based subfolder (images, documents, "
        "archives, etc.), then further into a folder named for the "
        "current month -- so nothing has to be sorted by hand at the "
        "end of the week.",
        "#7c3aed",
        "#a855f7",
    ),
    (
        "Habit Tracker Widget",
        "A tiny local web app for checking off daily habits, with streaks "
        "stored in SQLite and a calendar-style heatmap view.",
        "Each habit gets a daily checkbox and a running streak count "
        "stored in SQLite, plus a GitHub-style heatmap calendar so a "
        "month of consistency (or the lack of it) is visible at a "
        "glance instead of buried in a list.",
        "#059669",
        "#10b981",
    ),
    (
        "Retro Terminal Game",
        "A text-based adventure game played entirely in the terminal, "
        "written to practice control flow and state management.",
        "A small choose-your-own-adventure game driven entirely by a "
        "state machine of rooms and choices, played through plain "
        "terminal input/output. Built specifically to practice managing "
        "game state cleanly instead of falling back on a tangle of "
        "if/else branches.",
        "#0f172a",
        "#334155",
    ),
]


VIDEOS = [
    (
        "Building a Nav Bar From Scratch",
        "A walkthrough of turning a plain list of links into "
        "a sticky, responsive nav bar with an active-page indicator.",
        "Turns a plain unordered list of links into a sticky, responsive "
        "nav bar -- covers the CSS for the sticky positioning, the hover "
        "states, and the active-page indicator that highlights whichever "
        "link matches the current route.",
        "8:14",
        "#6366f1",
        "#8b5cf6",
    ),
    (
        "Flask Routes Explained",
        "What actually happens between typing a URL and "
        "Flask deciding which function should handle it.",
        "Walks through what actually happens between typing a URL into "
        "the browser and Flask deciding which view function should "
        "handle it -- the URL map, route converters like `<int:id>`, and "
        "how Flask matches a request to the right function.",
        "12:02",
        "#0ea5e9",
        "#22d3ee",
    ),
    (
        "SQLite in 10 Minutes",
        "Tables, rows, and just enough SQL to store and "
        "retrieve real data from a personal project.",
        "Covers just enough SQL to be useful: creating tables, inserting "
        "rows, and running SELECT queries against a real personal-project "
        "database, plus why parameterized queries matter from the very "
        "first INSERT.",
        "10:47",
        "#10b981",
        "#34d399",
    ),
    (
        "Designing a Card Grid",
        "Spacing, shadows, and hover states -- the small "
        "details that make a grid of boxes feel like a real product.",
        "Spacing, shadows, and hover states -- the small details that "
        "separate a grid of plain boxes from something that feels like a "
        "real product, using this site's own portfolio grid as the "
        "working example.",
        "6:33",
        "#f97316",
        "#facc15",
    ),
    (
        "Parameterized Queries, No Excuses",
        "Why string-formatting SQL is dangerous and how "
        "placeholder queries fix it without extra effort.",
        "Explains why string-formatting SQL is dangerous -- a live demo "
        "of a basic SQL injection against a vulnerable query -- and how "
        "placeholder-based parameterized queries close that hole without "
        "adding any real complexity.",
        "9:21",
        "#e11d48",
        "#fb7185",
    ),
    (
        "From Static HTML to Jinja Templates",
        "Turning four copy-pasted HTML files into one shared "
        "layout with a handful of small, focused templates.",
        "Turns four copy-pasted HTML files into one shared base template "
        "with a handful of small, focused Jinja templates extending it -- "
        "the exact refactor this site went through early on.",
        "11:05",
        "#7c3aed",
        "#a855f7",
    ),
]


SCHEMA_SCRIPT = """
    DROP TABLE IF EXISTS posts;
    DROP TABLE IF EXISTS portfolio_items;
    DROP TABLE IF EXISTS videos;
    DROP TABLE IF EXISTS page_views;

    CREATE TABLE posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        date_iso TEXT NOT NULL,
        date_display TEXT NOT NULL,
        tag TEXT NOT NULL,
        excerpt TEXT NOT NULL,
        body TEXT NOT NULL
    );

    CREATE TABLE portfolio_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        excerpt TEXT NOT NULL,
        body TEXT NOT NULL,
        color_start TEXT NOT NULL,
        color_end TEXT NOT NULL,
        image_filename TEXT,
        project_url TEXT,
        pinned INTEGER NOT NULL DEFAULT 0,
        thumbnail_fit TEXT NOT NULL DEFAULT 'cover',
        thumbnail_position TEXT NOT NULL DEFAULT 'center'
    );

    CREATE TABLE videos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        excerpt TEXT NOT NULL,
        body TEXT NOT NULL,
        duration TEXT NOT NULL,
        color_start TEXT NOT NULL,
        color_end TEXT NOT NULL,
        video_url TEXT
    );

    CREATE TABLE page_views (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        path TEXT NOT NULL,
        endpoint TEXT NOT NULL,
        visitor_id TEXT NOT NULL,
        viewed_at TEXT NOT NULL
    );

    CREATE INDEX idx_page_views_viewed_at ON page_views (viewed_at);
    """


def init_schema(connection):
    """(Re)create the posts and portfolio_items tables, dropping any existing
    data. This is the single source of truth for the schema -- both the CLI
    entry point below and the test suite's conftest.py call this instead of
    each keeping their own copy of the CREATE TABLE statements."""
    connection.executescript(SCHEMA_SCRIPT)


def seed_sample_data(connection):
    """Insert the sample posts and portfolio items used for local dev and
    as the known, deterministic fixture data for the test suite."""
    connection.executemany(
        """
        INSERT INTO posts (title, date_iso, date_display, tag, excerpt, body)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        POSTS,
    )

    connection.executemany(
        """
        INSERT INTO portfolio_items
            (title, excerpt, body, color_start, color_end)
        VALUES (?, ?, ?, ?, ?)
        """,
        PORTFOLIO_ITEMS,
    )

    connection.executemany(
        """
        INSERT INTO videos (title, excerpt, body, duration, color_start, color_end)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        VIDEOS,
    )


def main():
    connection = get_db_connection()

    init_schema(connection)
    seed_sample_data(connection)

    connection.commit()
    connection.close()

    print(
        f"Seeded {len(POSTS)} posts, {len(PORTFOLIO_ITEMS)} portfolio items, "
        f"and {len(VIDEOS)} videos."
    )


if __name__ == "__main__":
    main()
