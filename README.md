# tools

A growing collection of small, practical tools meant to be useful to a
wide range of people — not just developers. Each tool lives in its own
folder, is self-contained, and can be used independently of the others.

## Available tools

| Tool | Description |
|---|---|
| [`fire_calculator`](./fire_calculator) | Estimate how long it will take to reach Financial Independence (FIRE), with a chart of your projected net worth vs. your target. |

*(More tools will be added here as they're built.)*

## Structure

Each tool gets its own subfolder containing everything it needs:

```
tools/
├── README.md              <- you are here
├── .gitignore
│
├── fire_calculator/
│   ├── fire_calculator.py
│   ├── README.md          <- usage, inputs, assumptions for this tool
│   └── requirements.txt   <- dependencies for this tool only
│
└── <next_tool>/
    └── ...
```

This keeps tools independent: each one documents and declares its own
dependencies, so anyone can grab a single subfolder without dragging in
the rest of the repo.

## Using a tool

1. Open the subfolder for the tool you want.
2. Read its `README.md` for what it does and how to run it.
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
