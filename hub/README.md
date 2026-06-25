# Hub

Runs every tool's web interface in one place. Start this one script and
a single page opens with all the tools, each one click away.

This file has no calculation logic of its own. It imports each tool's
existing Flask blueprint and mounts it under its own URL path:

| Tool | URL |
|---|---|
| FIRE Calculator | `/fire-calculator/` |
| Raise Calculator | `/raise-calculator/` |
| Savings Target Calculator | `/savings-target/` |

Every tool still works exactly as before on its own too (`cd <tool>`,
`python3 app.py`) -- this is an additional way to reach all of them at
once, not a replacement.

## Usage

```bash
pip install -r requirements.txt
python3 hub.py
```

Then open **http://127.0.0.1:5000** in your browser.

## Adding a new tool to the hub

1. Give the tool's `app.py` a Blueprint named `bp` instead of a bare
   Flask app (see any existing tool's `app.py` for the pattern -- it's
   a small, mechanical change: `Blueprint(...)` instead of
   `Flask(__name__)`, `@bp.route` instead of `@app.route`, and a
   `create_app()` wrapper so it can still run standalone). In its
   template(s), point `url_for('static', ...)` at
   `url_for('<tool>.static', ...)` instead.
2. Add one entry to the `TOOLS` list in `hub.py`: folder name, URL
   prefix, title, one-line description.

No other file needs to change.

## Requirements

Combines the dependencies of every tool it mounts -- currently `flask`
and `matplotlib`.
