# Historical Backtest

Every other calculator in this repo asks: *"if returns average X% a
year, forever, how long until FIRE?"* That single constant number
hides something important — real markets don't return a steady 8%.
They crash, boom, and crash again, in a different order for every
possible starting year. Two people who both average 8% real return
over 30 years can have wildly different outcomes if one of them
started right before a crash.

This tool asks a different question: *"if I'd started saving in YEAR,
using the actual historical sequence of returns from that point
onward, how long would FIRE have taken?"* — repeated for every
possible historical starting year, so you see the full spread of
outcomes history has actually produced, not just their average.

A companion to [`fire_calculator`](../fire_calculator) and
[`savings_rate_explorer`](../savings_rate_explorer) — same "only the
savings rate matters, income cancels out" trick, no income figure
needed.

## Running the web interface

```bash
pip install -r requirements.txt
python3 app.py
```

Then open **http://127.0.0.1:5000**.

## What it shows

A bar chart: one bar per historical starting year, showing how many
years FIRE took starting from that year, using the real historical
sequence of annual returns from that point forward.

- **Green bar** — reached the target within your horizon.
- **Red bar** — didn't reach it within your horizon (the money grew
  too slowly in that particular historical sequence).
- **Grey bar** — not enough historical data exists yet to test the
  full horizon from that starting year (e.g. testing a 30-year horizon
  starting in 2010 would need data through 2040).

Summary stats above the chart: success rate across all fully-testable
historical windows, plus the best, median, and worst case in years.

## Inputs

| Input | Notes |
|---|---|
| Savings rate | % of income saved. Income is normalised to 1 unit — same as `savings_rate_explorer`, so no income figure is needed; results only depend on the rate. |
| Withdrawal rate | Sets the target: `(1 − savings rate) / withdrawal rate`. Recommended 3–5%. |
| Horizon | How many years you're willing to test each starting year over (10–50). |

## Data

`ANNUAL_NOMINAL_RETURNS_PCT` and `ANNUAL_INFLATION_PCT` in
`historical_backtest.py` are approximate, illustrative year-by-year
figures for US stock market total returns (S&P 500, dividends
reinvested) and CPI-U inflation, broadly consistent with widely
published historical series — the kind of data that tools like
FIRECalc and cFIREsim are themselves built on. They were reconstructed
from general knowledge rather than pulled from a live, verified feed.

The **shape** of the story (sequence-of-returns risk is real and
large) and the long-run averages are the point; treat any single
year's exact decimal as approximate. For research-grade work,
cross-check against a primary source (e.g. Robert Shiller's or Aswath
Damodaran's public datasets).

Real returns are derived from the two raw series via the same Fisher
equation used throughout this repo: `real = (1 + nominal) / (1 +
inflation) − 1`, applied year by year instead of as one constant
assumption.

## Command line

```bash
python3 historical_backtest.py
```

Prints summary stats and saves a matplotlib bar chart
(`historical_backtest.png`) with the same data as the web chart.

## Limitations

- US stock market only — no bonds, no international diversification,
  no rebalancing between asset classes.
- Annual data compounded monthly in 12 equal steps within each year
  (real intra-year sequencing is smoothed out).
- A "starting year" here means "started investing every month from
  January of that year" — not a specific calendar date within the year.
- No fees, taxes, or behavioural factors (panic-selling in a crash,
  etc.) — the actual return sequence, applied mechanically.

## Requirements

Python 3.9+. Needs `matplotlib` for the CLI chart and `flask` for the
web interface.

```bash
pip install -r requirements.txt
```
