#!/usr/bin/env python3
"""
hub.py -- combined launcher for all tools in this repository.

Runs every tool's web interface inside a single Flask app and process,
each mounted at its own URL path, plus a landing page listing them all.

This file has no calculation logic of its own -- it only imports each
tool's existing Flask blueprint (the `bp` object defined in that tool's
own app.py) and registers it under a URL prefix. Each tool still works
completely on its own too (`cd <tool>` then `python3 app.py`) -- this is
an additional way to reach all of them at once, not a replacement.

Run it with:

    pip install -r requirements.txt
    python3 hub.py

Then open http://127.0.0.1:5000 in your browser.

Adding a new tool to the hub later:
    1. Give the tool's app.py a Blueprint named `bp` (see any existing
       tool's app.py for the pattern -- it's a small, mechanical change).
    2. Add one entry to TOOLS below: folder name, URL prefix, title,
       one-line description.
That's it -- no other file needs to change.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from flask import Flask, render_template

REPO_ROOT = Path(__file__).resolve().parent.parent

# Each entry describes one tool's web interface. `folder` must match the
# tool's subfolder name; `prefix` is where it's mounted in the hub.
TOOLS = [
    {
        "folder": "fire_calculator",
        "prefix": "/fire-calculator",
        "title": "FIRE Calculator",
        "description": "Estimate how long until your investments can cover your expenses.",
    },
    {
        "folder": "raise_calculator",
        "prefix": "/raise-calculator",
        "title": "Raise Calculator",
        "description": "See what a pay raise is actually worth -- spent, kept as cash, or invested.",
    },
    {
        "folder": "savings_target_calculator",
        "prefix": "/savings-target",
        "title": "Savings Target Calculator",
        "description": "Work out how much to save each month to reach a target retirement income.",
    },
]


def _load_blueprint(folder: str):
    """Import a tool's app.py from its own folder and return its `bp`
    Blueprint. Every tool's web layer file is named `app.py`, so this
    loads each one under a unique synthetic module name to avoid them
    overwriting each other in sys.modules, and adds the tool's own
    folder to sys.path first so its `import <tool>_calculator` line
    resolves exactly as it does when run standalone."""
    tool_dir = REPO_ROOT / folder
    if str(tool_dir) not in sys.path:
        sys.path.insert(0, str(tool_dir))

    module_name = f"_hub_loaded_{folder}_app"
    spec = importlib.util.spec_from_file_location(module_name, tool_dir / "app.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module.bp


def create_app() -> Flask:
    app = Flask(__name__)

    for tool in TOOLS:
        blueprint = _load_blueprint(tool["folder"])
        app.register_blueprint(blueprint, url_prefix=tool["prefix"])

    @app.route("/")
    def index():
        return render_template("index.html", tools=TOOLS)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
