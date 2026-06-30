# Raise Calculator

Shows what a pay raise is actually worth, long-term, by comparing three
scenarios:

1. **Current path** -- no raise; your savings stay the same.
2. **Raise kept as cash** -- you get the raise, but don't invest it. It
   still adds to your net worth, but earns no investment return. Since
   every amount here is tracked in today's money (real terms), idle
   cash also loses purchasing power to inflation over time -- it
   slowly shrinks in real terms rather than just sitting still.
3. **Raise invested** -- the entire raise is added to your monthly
   savings/investments.

Optionally, you can compare all three against a FIRE target, to see how
many years sooner -- if any -- investing the raise gets you there.

This tool is self-contained and has no dependency on any other tool in
this repository.

## Usage

Use whichever interface suits you -- both share the same calculation
code, so results are always identical:

- **Command line** (`raise_calculator.py`) -- no installation beyond
  Python itself plus `matplotlib` for the chart.
- **Browser** (`app.py`) -- a small local Flask app with sliders for
  the adjustable assumptions and an interactive chart.

### Command-line usage

```bash
pip install -r requirements.txt
python3 raise_calculator.py
```

You'll be prompted for:

| Input | Description |
|---|---|
| Current monthly savings | What you currently invest each month |
| Net monthly raise amount | The take-home (net) increase in your monthly pay |
| Current net worth *(optional)* | Starting balance for the projection. Default: **0** |
| Annual expenses in retirement *(optional)* | If provided, used to compute a FIRE target. Press Enter to skip the FIRE comparison entirely |
| Withdrawal rate *(optional)* | Used to size the FIRE target from your annual expenses. Default: **4%** (recommended range: 3-5%) |
| Expected nominal annual investment return *(optional)* | Default: **8%** |
| Expected annual inflation rate *(optional)* | Default: **3%** |
| Chart horizon in years *(optional)* | Default: **30** (automatically extended if needed to show a FIRE target being reached) |

All amounts should be entered as **net** (take-home) figures, in the same
currency, in today's money. Working in net, real terms avoids having to
model any country-specific tax system.

## Web interface

```bash
pip install -r requirements.txt
python3 app.py
```

Then open **http://127.0.0.1:5000** in your browser. Same inputs as the
command line, as a form: number fields for current savings / raise
amount / net worth, a checkbox to optionally compare against a FIRE
target, and sliders (pre-filled with the defaults) for return,
inflation, and chart horizon. Press **Calculate** to see the comparison
and chart.

`app.py` has no calculation logic of its own -- it calls the exact same
functions in `raise_calculator.py` as the command-line version, so both
interfaces always agree.

To open this alongside the other tools in this repo from one page, see
`../hub`.

## Output

- Real (inflation-adjusted) return used in the calculation
- FIRE target (target net worth), if requested
- For each scenario: monthly savings, and either time to reach the FIRE
  target, or projected net worth at the end of the chart horizon
- How much sooner investing the raise gets you to your FIRE target,
  compared to the current path (if a target was set)
- A **chart** comparing net worth growth across scenarios, with the FIRE
  target as a horizontal reference line (if set) and the crossing point
  marked for each scenario that reaches it

## Default assumptions

- Nominal annual investment return: **8%**
- Annual inflation rate: **3%**
- Safe withdrawal rate: **4%**

These mirror the defaults used in `fire_calculator` (see that tool's
README for the underlying reasoning and sources). Real return is
computed via the Fisher equation, `(1 + nominal) / (1 + inflation) − 1`,
used consistently across this repository -- including for idle cash
(modeled as 0% nominal return).

## Requirements

Python 3.10+. The core calculation has no external dependencies; the
command-line chart needs `matplotlib`, and the web interface also needs
`flask` (see `requirements.txt`).
