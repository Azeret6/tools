# Raise Calculator

Shows what a pay raise is actually worth, long-term, by comparing three
scenarios:

1. **Current path** -- no raise; your savings stay the same.
2. **Raise spent** -- you get the raise, but lifestyle inflation absorbs
   all of it; your savings rate doesn't change. (This scenario plays out
   identically to "Current path" -- it's included to make the cost of
   lifestyle inflation visible side by side with the alternative below.)
3. **Raise invested** -- the entire raise is added to your monthly
   savings/investments.

Optionally, you can compare all three against a FIRE target, to see how
many years sooner -- if any -- investing the raise gets you there.

This tool is self-contained and has no dependency on any other tool in
this repository.

## Usage

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
README for the underlying reasoning and sources). Real return is computed
as `nominal_return - inflation`, a simplified approximation used
consistently across this repository.

## Requirements

Python 3.10+. The core calculation has no external dependencies; the
chart requires `matplotlib` (see `requirements.txt`).
