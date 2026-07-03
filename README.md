# tools

A collection of small, practical tools — useful to a wide range of
people, not just developers. Each tool lives in its own folder and
works independently. A `hub/` combines them into one web interface.

## Tools

| Tool | What it does |
|---|---|
| [`fire_calculator`](./fire_calculator) | Financial independence planning: how long until you can retire, how much you need to save, Coast FIRE, and more. CLI and web. |
| [`raise_calculator`](./raise_calculator) | Model a pay raise three ways — spend it, hold it as cash, or invest it — with an optional FIRE-target comparison. CLI and web. |
| [`savings_target_calculator`](./savings_target_calculator) | Given a desired retirement income and a time horizon, work out how much to save each month. CLI and web. |
| [`color_palette_generator`](./color_palette_generator) | Generate colour palettes with five harmony modes, four style moods, and WCAG contrast checking. Web. |

## Running all tools from one page

```bash
cd hub
pip install -r requirements.txt
python3 hub.py
```

Opens at **http://127.0.0.1:5000** — a landing page with links to every
tool, each at its own URL. See `hub/README.md` for details.

## Running a single tool

1. Open the tool's subfolder.
2. Read its `README.md`.
3. Install dependencies if needed, then run:
   ```bash
   cd <tool_name>
   pip install -r requirements.txt
   python3 app.py          # web interface
   python3 <tool_name>.py  # command line
   ```

## Structure

```
tools/
├── README.md
├── .gitignore
├── hub/                    <- runs all web interfaces at once
│   ├── hub.py
│   ├── templates/
│   └── static/
├── fire_calculator/
│   ├── fire_calculator.py  <- calculation logic (no UI dependencies)
│   ├── app.py              <- web interface (Flask Blueprint)
│   ├── templates/fire_calculator/
│   ├── static/
│   ├── README.md
│   └── requirements.txt
└── <other_tools>/          <- same structure
```

Each tool is self-contained: its own README, its own dependencies, its
own templates in a named subfolder to avoid clashes in the hub.

## Adding a new tool

Follow the same pattern — subfolder, `README.md`, `requirements.txt`
if needed. For a web interface, define it as a Flask **Blueprint** (see
any existing `app.py`) with templates in `templates/<tool_name>/`.
This lets it run standalone *and* be added to the hub with a one-line
change. Add a row to the table above.
