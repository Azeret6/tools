# Monte Carlo FIRE Simulator

Every other calculator in this repo shows you **one** version of the
future. `fire_calculator` assumes one constant return, forever.
`historical_backtest` replays the sequences that *actually happened* in
history. Neither answers: *given how volatile markets really are, what
realistic spread of outcomes should I expect?*

That's what Monte Carlo simulation does: generate thousands of randomly
simulated futures — each year's return drawn from a distribution you
control — and look at the resulting spread, not a single number.

## This is *not* the same tool as Historical Backtest

| | [`historical_backtest`](../historical_backtest) | This tool |
|---|---|---|
| Data | ~96 sequences that **actually happened**, 1928–2023 | Thousands of **randomly generated** sequences |
| Method | Deterministic replay | Random draws from a normal distribution |
| Strength | Grounded in real history | Much larger sample, smoother statistics |
| Weakness | Limited to the handful of sequences history produced | Only as good as the assumed mean/volatility |

They're complementary — use both.

## Running the web interface

```bash
pip install -r requirements.txt
python3 app.py
```

Then open **http://127.0.0.1:5000**.

## What it shows

A **fan chart**: your balance over time, as a widening cone of
uncertainty. The shaded bands show the 10th–90th and 25th–75th
percentile range across all simulations; the solid line is the median;
the dashed red line is your FIRE target.

Below the chart: success rate (% of simulations that reached the
target within your horizon) and years-to-FIRE at each percentile.

## Inputs

| Input | Notes |
|---|---|
| Savings rate | % of income saved. Income is normalised to 1 unit — same trick as `savings_rate_explorer`, so no income figure is needed. |
| Withdrawal rate | Sets the target: `(1 − savings rate) / withdrawal rate`. |
| Horizon | How many years each simulation runs. |
| Mean annual real return | The average return each year's random draw is centred on. Default ~6.5% roughly matches long-run US stock market real returns. |
| Annual volatility (std. dev.) | How much returns swing year to year. Higher = wider spread of outcomes, same average — this is what makes the fan chart fan out. |
| Number of simulations | More = smoother percentile bands, slightly slower. |

## Method

Each simulation draws an independent random annual real return for
every year of the horizon, from a **normal distribution** with the
mean and standard deviation you set. Each drawn annual rate is
compounded monthly (`(1 + annual)^(1/12) - 1`). The simulation checks,
month by month, whether the target was reached.

This is a standard, widely-used technique — the same broad approach
tools like FIRECalc's Monte Carlo mode use. A normal distribution is a
simplification of real market behaviour (real returns have "fatter
tails" — extreme years happen more often than a normal distribution
predicts), so treat this as a useful way to see the *shape* of
uncertainty, not a precise forecast.

## Command line

```bash
python3 monte_carlo_simulator.py
```

Prints success rate and percentile years, and saves a matplotlib fan
chart (`monte_carlo_fan_chart.png`).

## Limitations

- Normal distribution assumption — doesn't capture fat tails, market
  crashes clustering together, or serial correlation between years
  (a bad year doesn't make the next year any more or less likely to be
  bad, which isn't quite how real markets behave).
- Each year's return is independent — no modelling of multi-year bear
  markets or recoveries as connected events.
- US stock market real-return assumptions only; no bonds, no
  international diversification, no rebalancing.

## Requirements

Python 3.9+. Needs `matplotlib` for the CLI chart and `flask` for the
web interface.

```bash
pip install -r requirements.txt
```
