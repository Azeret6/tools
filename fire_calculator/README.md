# FIRE Calculator

A tool that estimates how long it will take you to reach **Financial
Independence (FI)** — the point at which your invested assets can
sustainably cover your living expenses, based on the classic
FIRE-movement math:

```
FIRE number = annual expenses / withdrawal rate
```

Use whichever interface suits you — both share the same calculation
code, so results are identical either way:

- **Command line** (`fire_calculator.py`) — no installation beyond
  Python itself plus `matplotlib` for the chart.
- **Browser** (`app.py`) — a small local Flask app with sliders for the
  adjustable assumptions.

## Command-line usage

```bash
python3 fire_calculator.py
```

You'll be asked for your current net worth, annual income, and monthly
savings. A few more values (expected return, inflation, withdrawal rate)
have sensible defaults — just press **Enter** to accept them, or type
your own.

All amounts must be entered in the **same currency** — the calculator
doesn't care which one. All values are treated as "today's money" (real
terms).

## Inputs

| Input | Description |
|---|---|
| Savings diary CSV *(optional)* | A file with `date` and `net_worth` columns (see [Savings diary](#savings-diary-optional) below). If provided, its most recent entry is used as your current net worth automatically. |
| Current net worth | Current invested assets / starting balance — only asked if no diary was loaded |
| Annual income | Net (take-home) annual income |
| Monthly savings | Amount you invest every month |
| Nominal annual return *(optional)* | Expected investment return, before inflation. Default: **8%** |
| Inflation rate *(optional)* | Expected long-term inflation. Default: **3%** |
| Withdrawal rate *(optional)* | The "safe withdrawal rate" used to size your FIRE number. Default: **4%** (recommended range: 3–5%) |

## Savings diary (optional)

If you keep a personal log of your net worth over time, save it as a CSV
with exactly these two columns:

```csv
date,net_worth
2025-01-01,15000
2025-04-01,17200
2025-07-01,19800
```

- `date` must be in `YYYY-MM-DD` format.
- Rows that can't be parsed are skipped (with a warning), not fatal.
- The calculator uses the **most recent** entry as your current net
  worth and as the anchor date for the projection — so you don't need to
  re-enter it manually.
- The chart will show your real recorded history (green) alongside the
  future projection (blue).

A sample file, `savings_log_example.csv`, is included as a template.

**Privacy tip:** if you save your *real* diary, name it with a
`_private.csv` suffix (e.g. `savings_log_private.csv`) — this repo's
`.gitignore` is already set up to keep such files out of version
control, while `*_example.csv` files stay tracked.

## Web interface

```bash
pip install -r requirements.txt
python3 app.py
```

Then open **http://127.0.0.1:5000** in your browser. The same inputs as
the command-line version are there, just as a form: number fields for
current net worth / income / savings, a file picker for an optional
savings diary CSV, and sliders (pre-filled with the defaults) for
return, inflation, and withdrawal rate. Press **Calculate** to see your
results and chart.

`app.py` has no calculation logic of its own — it calls the exact same
functions in `fire_calculator.py` as the command-line version, so both
interfaces always agree.

## Output

- Estimated annual expenses (derived as `income − savings × 12`)
- Real (inflation-adjusted) return used in the calculation
- **FIRE number** — the target net worth you're aiming for
- **Time to FI** — in years and months, plus an estimated calendar date
- A **chart** (opens automatically) showing your projected net worth over
  time, with the FIRE target as a horizontal reference line and the
  estimated crossing point marked — plus your recorded history, if a
  savings diary was loaded

## Assumptions & default values

- **Nominal return (8%)** — a conservative blend between the long-run
  historical nominal return of the S&P 500 (~10%) and a globally
  diversified index such as the FTSE All-World (~7–8% since inception).
- **Inflation (3%)** — long-run historical average commonly used as a
  planning default.
- **Withdrawal rate (4%)** — the widely cited "4% rule" from the Trinity
  Study, found sustainable over a 30-year retirement. 3–5% is a
  reasonable range depending on how conservative you want to be.
- **Real return = nominal − inflation** — the same simplified approach
  used by most popular FIRE calculators (rather than the more precise
  Fisher equation). Accurate enough for long-term planning.

## Limitations

This is an intentionally simple calculator:

- Assumes constant monthly savings and a constant rate of return — no
  salary growth, lifestyle changes, or market volatility.
- Doesn't account for taxes, one-off windfalls/expenses, or changing
  spending needs in retirement.
- Single-point estimate only — no Monte Carlo simulation or
  sequence-of-returns risk modeling.
- No support for current age / target retirement age.

## Requirements

Python 3.9+.

- Command-line version: no dependencies beyond `matplotlib` (for the chart).
- Web version: also needs `flask`.

```bash
pip install -r requirements.txt
```
