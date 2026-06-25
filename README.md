# tools

A growing collection of small, practical tools meant to be useful to a
wide range of people — not just developers. Each tool lives in its own
folder, is self-contained, and can be used independently of the others.

## Available tools

| Tool | Description |
|---|---|
| [`fire_calculator`](./fire_calculator) | Estimate how long it will take to reach Financial Independence (FIRE), with a chart of your projected net worth vs. your target. |
| [`raise_calculator`](./raise_calculator) | Compare what happens to a pay raise if you spend it, hold it as cash, or invest it. |
| [`savings_target_calculator`](./savings_target_calculator) | Work out how much you need to save each month to reach a target retirement income within a chosen number of years. |

*(More tools will be added here as they're built.)*

## Structure

Each tool gets its own subfolder containing everything it needs. Some
tools are CLI-only; others also ship a small web interface. A `hub/`
folder runs all of them together from one page (see below):

```
tools/
├── README.md              <- you are here
├── .gitignore
│
├── hub/                    <- runs every tool's web interface at once
│   ├── hub.py
│   ├── templates/
│   ├── static/
│   └── README.md
│
├── fire_calculator/
│   ├── fire_calculator.py
│   ├── app.py              <- optional: web interface
│   ├── templates/
│   │   └── fire_calculator/index.html   <- namespaced so the hub can tell tools apart
│   ├── static/
│   ├── README.md          <- usage, inputs, assumptions for this tool
│   └── requirements.txt   <- dependencies for this tool only
│
└── <next_tool>/
    └── ...
```

This keeps tools independent: each one documents and declares its own
dependencies, so anyone can grab a single subfolder without dragging in
the rest of the repo.

## Running all tools from one page

```bash
cd hub
pip install -r requirements.txt
python3 hub.py
```

Then open **http://127.0.0.1:5000** — a landing page links to every
tool, each mounted at its own URL. See `hub/README.md` for how it works
and how to add a new tool to it.

## Using a tool

1. Open the subfolder for the tool you want.
2. Read its `README.md` for what it does and how to run it — some have
   both a command-line and a web version.
3. If it has a `requirements.txt`, install dependencies first:
   ```bash
   cd <tool_name>
   pip install -r requirements.txt
   python3 <tool_name>.py
   ```

## Contributing / adding a new tool

When adding a new tool, please follow the same pattern: its own
subfolder, its own `README.md`, and its own `requirements.txt` if it
needs external packages. Add a row for it in the table above.

If the tool has a web interface, define it as a Flask **Blueprint**
(see any existing tool's `app.py`) rather than a bare `Flask` app, and
put its template(s) in a subfolder named after the tool (e.g.
`templates/my_tool/index.html`) rather than directly in `templates/`.
This is what lets the tool be added to `hub/` later with a one-line
change, and avoids template name clashes if it ever is. The tool still
runs completely on its own either way.
