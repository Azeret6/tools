# Savings Target Calculator

A tool that answers the mirror question to `fire_calculator`: instead of
"how long until I reach my number at my current savings rate", it asks

> Given a desired income in retirement and a savings horizon, how much
> do I need to set aside each month to get there?

The underlying target uses the same FIRE-movement math:

```
target amount = (desired monthly income x 12) / withdrawal rate
```

The required monthly contribution is then the amount that, growing at
your expected real rate of return, reaches that target by the end of
your chosen savings horizon.

**Everything is calculated in real terms** (today's purchasing power).
The desired income, the target amount, and the required monthly saving
are all expressed in today's money. The nominal return and inflation
rate you enter are only used to derive the real rate of return used for
growth - you never need to think in inflated future numbers.

This tool is standalone: it does not import anything from
`fire_calculator` or any other tool in this repo.

Use whichever interface suits you - both share the same calculation
code, so results are always identical:

- **Command line** (`savings_target_calculator.py`) - no installation
  beyond Python itself plus `matplotlib` for the chart.
- **Browser** (`app.py`) - a small local Flask app with sliders for the
  adjustable assumptions and a live interactive chart.

## Command-line usage

```bash
python3 savings_target_calculator.py
```

You'll be prompted for:

- Desired monthly income in retirement (today's money)
- Number of years you plan to save
- Withdrawal rate (default 4%)
- Expected nominal annual return (default 8%)
- Expected annual inflation (default 3%)
- Anything already saved today (default 0)

The script prints the target amount, the required monthly savings, and
how much of the final amount comes from contributions vs. investment
growth, then shows a chart of the projected net worth against the
target.

## Web interface

```bash
pip install -r requirements.txt
python3 app.py
```

Then open **http://127.0.0.1:5000** in your browser. The savings
horizon is a slider in years, with an exact-months field next to it so
you can fine-tune it either way. Withdrawal rate, expected return, and
inflation are also sliders with a live percentage readout. Every change
recalculates the result panel and chart immediately - no submit button
needed (though one is there too).

`app.py` has no calculation logic of its own - it calls the exact same
functions in `savings_target_calculator.py` as the command-line version,
so both interfaces always agree.

To open this alongside the other tools in this repo from one page, see
`../hub`.

## Requirements

Python 3.9+. The core calculation has no external dependencies; the CLI
chart needs `matplotlib` and the web interface needs `flask` (see
`requirements.txt`).

```bash
pip install -r requirements.txt
```
