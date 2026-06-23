# FIRE Calculator

A simple command-line tool that estimates how long it will take you to
reach **Financial Independence (FI)** — the point at which your invested
assets can sustainably cover your living expenses, based on the classic
FIRE-movement math:

```
FIRE number = annual expenses / withdrawal rate
```

## Usage

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
| Current net worth | Current invested assets / starting balance |
| Annual income | Net (take-home) annual income |
| Monthly savings | Amount you invest every month |
| Nominal annual return *(optional)* | Expected investment return, before inflation. Default: **8%** |
| Inflation rate *(optional)* | Expected long-term inflation. Default: **3%** |
| Withdrawal rate *(optional)* | The "safe withdrawal rate" used to size your FIRE number. Default: **4%** (recommended range: 3–5%) |

## Output

- Estimated annual expenses (derived as `income − savings × 12`)
- Real (inflation-adjusted) return used in the calculation
- **FIRE number** — the target net worth you're aiming for
- **Time to FI** — in years and months, plus an estimated calendar date
- A **chart** (opens automatically) showing your projected net worth over
  time, with the FIRE target as a horizontal reference line and the
  estimated crossing point marked

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

## Limitations (v1)

This is a first, intentionally simple version:

- Assumes constant monthly savings and a constant rate of return — no
  salary growth, lifestyle changes, or market volatility.
- Doesn't account for taxes, one-off windfalls/expenses, or changing
  spending needs in retirement.
- Single-point estimate only — no Monte Carlo simulation or
  sequence-of-returns risk modeling.
- No support for current age / target retirement age (planned for a
  later version).

## Roadmap

- ~~**v1.1** — visualize projected net worth over time, with the FIRE
  target shown as a reference line.~~ ✅ Done
- **v2** — load historical net-worth entries (a personal "savings
  diary", stored as CSV) and plot history alongside the projection.
- **v3** — web interface with adjustable sliders for the default
  assumptions.

## Requirements

Python 3.9+. The core calculation has no external dependencies; the
chart requires `matplotlib` (see `requirements.txt`).

```bash
pip install -r requirements.txt
```
