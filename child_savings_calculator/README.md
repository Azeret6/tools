# Child Savings Calculator

Set a monthly contribution and a horizon, and see what it could grow
into by the time it's needed - typically by a child's 18th birthday,
though the horizon works for anything.

The horizon can be entered either directly in years, or as the child's
current age (years + months) and a savings end age (default 18) - the
tool converts the age pair into a month count itself.

Two scenarios are compared side by side, both compounding at the same
expected nominal return:

- **Flat** - the same nominal contribution every month for the whole
  horizon. Its real (inflation-adjusted) value erodes a little every
  year.
- **Rising with inflation** - the contribution is bumped up once a year
  by the inflation rate, so it keeps the same purchasing power
  throughout instead of shrinking in real terms.

For both scenarios the tool also reports a **theoretical monthly
income** the final balance could support, using a withdrawal rate you
set (4% by default - the classic "4% rule" figure). This is not
financial advice or a real drawdown plan, just a way to translate a
lump sum into a more intuitive "per month" number.

Final balances and the theoretical monthly income are shown two ways:
in nominal terms (the actual number that will be in the account /
be withdrawn at that future date) and deflated back to today's
purchasing power, so a horizon of 10-18 years doesn't give a misleading
sense of scale.

This tool is standalone: it does not import anything from
`fire_calculator`, `savings_target_calculator`, or any other tool in
this repo - the math above is fully self-contained in
`child_savings_calculator.py`.

Use whichever interface suits you - both share the same calculation
code, so results are always identical:

- **Command line** (`child_savings_calculator.py`) - no installation
  beyond Python itself.
- **Browser** (`app.py`) - a small local Flask app with sliders for the
  adjustable assumptions and a live interactive chart comparing both
  scenarios.

## Command-line usage

```bash
python3 child_savings_calculator.py
```

You'll be prompted for the monthly contribution, whether to specify the
horizon by years or by the child's age, anything already saved, and the
three assumption percentages (return, inflation, withdrawal rate - all
default to the same values used across this repo's other calculators:
8% / 3% / 4%). It prints both scenarios' final balance, contributions,
investment growth, and theoretical monthly income.

## Web interface

```bash
pip install -r requirements.txt
python3 app.py
```

Then open **http://127.0.0.1:5000** in your browser. Toggle between
"Number of years" and "Child's age" for the horizon; every change to
any field recalculates the comparison table and chart immediately - no
submit button needed (though one is there too).

`app.py` has no calculation logic of its own - it calls the exact same
functions in `child_savings_calculator.py` as the command-line version,
so both interfaces always agree.

To open this alongside the other tools in this repo from one page, see
`../hub`.

## Requirements

Python 3.9+. The core calculation has no external dependencies; the web
interface needs `flask` (see `requirements.txt`).

```bash
pip install -r requirements.txt
```
