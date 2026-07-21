# FIRE Calculator

A tool for financial independence planning. Enter your income, savings,
and a few assumptions — choose what you want to calculate and get
a clear projection with an interactive chart.

Use whichever interface suits you — both share the same calculation
code, so results are always identical:

- **Command line** (`fire_calculator.py`) — runs anywhere Python is installed.
- **Browser** (`app.py`) — interactive chart, live-updating sliders, scenario comparison.

## Running the web interface

```bash
pip install -r requirements.txt
python3 app.py
```

Then open **http://127.0.0.1:5000**. To run it alongside the other
tools from one page, use `../hub` instead.

## Layout

The web interface has three zones:

1. **Top bar** — the four core inputs (savings diary, net worth, income, savings)
   plus the Calculate button, always visible.
2. **Sidebar + chart** — a narrow left panel with the calculation mode
   selector, assumptions, and results; a large interactive chart on the right.
3. **Reference table** — years to FIRE at savings rates 10–90%, using your
   current assumptions, starting from zero.

## Calculation modes

Select one at a time using the radio buttons. All input fields stay
visible and remember their values when you switch modes — only the
irrelevant ones are greyed out.

### When will I reach FI?
The main mode. Answers: *how many years and months until my portfolio
can cover my expenses?*

- Leave **target monthly income** empty → calculates full financial
  independence (expenses = income − savings × 12).
- Fill **target monthly income** → calculates *Partial FIRE*: the
  earlier point where your portfolio sustains that specific amount.

### How much must I save monthly?
Inverse calculation: given a desired retirement income and a time
horizon, computes the required monthly savings. The Monthly savings
field in the top bar becomes an output (greyed as input).

### When can I stop saving?
Calculates your **Coast FIRE** number — the portfolio value at which
compound growth alone, with no further contributions, reaches your
FIRE target by your chosen retirement age.

## ±5 % scenarios

A cross-mode checkbox that adds two extra curves to the chart:

- **Green band (+5 pp)** — what happens if you save 5 percentage
  points more of your income each month. Both the portfolio grows
  faster and the FIRE target drops (you spend less).
- **Red line (−5 pp)** — the mirror image: higher target, slower growth.

Crossing markers show exactly when each scenario reaches your FIRE goal.
Active in "When will I reach FI?" and "When can I stop saving?" modes.

## Chart

- **Drag to zoom** — click and drag to select any rectangular area;
  the chart zooms into it. Click **↺ Reset** to restore the full view.
- **Hover tooltip** — shows projected net worth, distance to target,
  and scenario values at any date.
- **Scenario band** — a filled area between +5 % and −5 % curves,
  with the main projection as a solid blue line through the middle.
- **Crossing markers** — coloured dots where each projection crosses
  the FIRE target line.

## Assumptions (sliders)

| Assumption | Default | Notes |
|---|---|---|
| Nominal annual return | 8 % | Before inflation |
| Inflation rate | 3 % | Long-run planning figure |
| Withdrawal rate | 4 % | Safe withdrawal rate (recommended 3–5 %) |
| Annual savings increase | 0 % | *Real* annual increase in savings amount. 2 % means you invest 2 % more purchasing power each year. 0 = constant. |

All calculations use the **Fisher equation** for real returns:
`real return = (1 + nominal) / (1 + inflation) − 1`.
Everything is expressed in today's money (real terms) throughout.

## Savings diary (optional)

Keep a personal log of your net worth over time. The most recent entry
is used as your starting balance and date.

```csv
date,net_worth
2025-01-01,15000
2025-06-01,18500
```

- Dates in `YYYY-MM-DD` format; unparseable rows are skipped silently.
- Recorded history appears as a green line on the chart.
- Name your real file `savings_log_private.csv` — `.gitignore` excludes
  `*_private.csv` files automatically.
- A sample file `savings_log_example.csv` is included as a template.

## Defaults & assumptions

- **8 % nominal return** — conservative blend of S&P 500 long-run
  average (~10 %) and a globally diversified index (~7–8 %).
- **3 % inflation** — long-run historical average.
- **4 % withdrawal rate** — the Trinity Study "4 % rule"; sustainable
  over a 30-year retirement with a balanced portfolio.

## Limitations

- No taxes, transaction costs, or fee drag.
- No one-off events (windfalls, large purchases, career breaks).
- Single deterministic projection — no Monte Carlo or historical
  sequence-of-returns modelling.
- Savings growth assumes a fixed annual percentage; real salary paths
  are irregular.

## Requirements

Python 3.9+. The command-line version needs `matplotlib`; the web
interface also needs `flask` and `hammerjs`/`chartjs-plugin-zoom`
(loaded from CDN at runtime, no local install needed).

```bash
pip install -r requirements.txt
```
