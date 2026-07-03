# FIRE Calculator

A tool for financial independence planning. Enter your income, savings,
and a few assumptions — get an estimate of how long until your
investments can sustainably cover your expenses.

Use whichever interface suits you — both share the same calculation
code, so results are always identical:

- **Command line** (`fire_calculator.py`) — runs anywhere Python is installed.
- **Browser** (`app.py`) — sliders, checkboxes, and an interactive chart.

## Running the web interface

```bash
pip install -r requirements.txt
python3 app.py
```

Then open **http://127.0.0.1:5000**. The app opens automatically in your
default browser. To run it alongside the other tools from one page,
use `../hub` instead.

## Inputs

All amounts must be in the **same currency**. Everything is in
**today's money** (real terms) — you never need to think in inflated
future prices.

| Input | Description |
|---|---|
| Current net worth | Your invested assets today — can be left blank (treated as 0) |
| Annual income | Net (take-home) annual income |
| Monthly savings | Amount you invest every month |
| Nominal annual return *(slider, default 8%)* | Expected investment return before inflation |
| Inflation rate *(slider, default 3%)* | Expected long-term inflation |
| Withdrawal rate *(slider, default 4%)* | Safe withdrawal rate used to size your FIRE number. Recommended range: 3–5% |
| Annual savings increase *(slider, default 0%)* | How much more you plan to invest each year, in nominal terms. 0 = constant savings |
| Savings diary CSV *(optional)* | A personal log of `date,net_worth` entries — see below |

## Optional modes (checkboxes)

All modes can be combined freely. Shared inputs (income, return,
inflation, etc.) are entered once.

### Partial FIRE
Targets a specific sustainable monthly income rather than full
financial independence — useful for a pension top-up or a part-time
retirement scenario. The target becomes `(desired income × 12) /
withdrawal rate`. The calculator also shows what that amount will be
worth in nominal terms in the year you reach it.

### Coast FIRE
The amount you need saved *now* so that — even if you stopped
contributing entirely — compound growth alone would reach your FIRE
number by your chosen retirement age. Requires your current age and
target retirement age. Shown as a separate line on the chart.

### Required monthly savings
The inverse calculation: given a desired monthly income and a fixed
time horizon, how much do you need to set aside each month to get
there? Useful if you have a deadline (e.g. "I want to retire in 20
years") rather than asking how long it will take.

## Savings diary (optional)

Keep a personal log of your net worth over time and load it into the
calculator. The most recent entry is used as your current net worth
and as the starting date for the projection.

Format — a CSV with exactly two columns:

```csv
date,net_worth
2025-01-01,15000
2025-06-01,18500
```

- Dates must be in `YYYY-MM-DD` format.
- Rows that can't be parsed are skipped without failing.
- The chart shows your recorded history (green) alongside the
  projection (blue).
- A sample file, `savings_log_example.csv`, is included as a template.

Name your real diary `savings_log_private.csv` — the repo's
`.gitignore` keeps `*_private.csv` files out of version control
automatically.

## Output

- Savings rate (% of income invested)
- Annual expenses (derived as `income − savings × 12`)
- FIRE number — the net worth you're aiming for
- Time to financial independence — years and months, plus calendar date
- Interactive chart — hover to see balance and distance to target at
  any point; includes Coast FIRE line and history if applicable
- Reference table — years to FIRE at savings rates from 10% to 90%,
  using your own assumptions, starting from zero

## Assumptions & defaults

- **8% nominal return** — conservative blend between the S&P 500 long-run
  average (~10%) and a globally diversified index such as the FTSE
  All-World (~7–8%).
- **3% inflation** — long-run historical average used as a planning default.
- **4% withdrawal rate** — the Trinity Study's widely cited "4% rule".
  Sustainable over a 30-year retirement with a balanced portfolio.
- **Real return via the Fisher equation** — `(1 + nominal) / (1 + inflation) − 1`,
  used consistently across all tools in this repository.
- **Annual savings increase** — when set above 0%, modelled as a nominal
  growth rate; converted to real terms via the Fisher equation. 0%
  means constant savings in real terms (original behaviour).

## Limitations

- No taxes, one-off windfalls, or spending changes in retirement.
- Single-point estimate — no Monte Carlo or sequence-of-returns modelling.
- The savings growth model assumes a fixed percentage increase each year;
  real salary trajectories are more irregular.

## Requirements

Python 3.9+. The command-line version needs `matplotlib`; the web
interface also needs `flask`.

```bash
pip install -r requirements.txt
```
