# Savings Rate Explorer

An interactive chart answering one question: **how much does your savings
rate alone determine how long until financial independence?**

No income figure is needed. If you save X% of your income, your expenses
are automatically the other (100−X)%, and your monthly contribution is
X% too — both scale with income, so income cancels out of the years-to-FI
math entirely. A person earning 500,000/year saving 24% reaches FI in
exactly the same number of years as someone earning 50,000/year saving
24%. Only the rate matters.

This is a standalone companion to [`fire_calculator`](../fire_calculator) —
same underlying math (Fisher equation for real returns), but zoomed out
to show the whole curve across every savings rate at once, rather than
a single projection for your specific numbers.

## Running the web interface

```bash
pip install -r requirements.txt
python3 app.py
```

Then open **http://127.0.0.1:5000**. To run it alongside the other tools
from one page, use `../hub` instead.

## What it shows

An interactive line chart: **savings rate (5–95%)** on the x-axis,
**years to financial independence** on the y-axis. Three sliders
(nominal return, inflation, withdrawal rate) update the curve live.

Optionally, enter your own savings rate directly, or your annual income
and monthly savings (the rate is worked out automatically) to plot a
single red marker showing exactly where you sit on the curve.

## Command line

```bash
python3 savings_rate_explorer.py
```

Prints years to FI at a range of savings rates and saves a matplotlib
chart (`savings_rate_curve.png`) with the same curve.

## Assumptions

Same defaults as `fire_calculator`: 8% nominal return, 3% inflation,
4% withdrawal rate. Real returns computed via the Fisher equation:
`real return = (1 + nominal) / (1 + inflation) − 1`.

## Limitations

- Assumes a constant savings rate throughout (no raises, no savings
  growth over time — for that level of detail, use `fire_calculator`).
- Starts from zero net worth (a head start isn't modelled here).
- Single deterministic curve — no Monte Carlo or historical backtesting.

## Requirements

Python 3.9+. Needs `matplotlib` for the CLI chart and `flask` for the
web interface.

```bash
pip install -r requirements.txt
```
