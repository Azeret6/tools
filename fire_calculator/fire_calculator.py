#!/usr/bin/env python3
"""
FIRE Calculator
===============

A simple command-line calculator that estimates how long it will take to
reach Financial Independence (FI), based on the FIRE (Financial
Independence, Retire Early) movement's standard math:

    FIRE number      = annual_expenses / withdrawal_rate
    months to FI      = the point at which your invested assets,
                         growing with compound returns and regular monthly
                         contributions, reach the FIRE number.

All amounts are assumed to be in "today's money" (real terms) and in a
single, consistent currency of the user's choice -- the currency itself
does not matter for the math, as long as everything is entered in the
same one.

Default assumptions (overridable by the user):
------------------------------------------------
- Nominal annual investment return: 8.0%
    A blended, conservative approximation between the long-run historical
    nominal return of the S&P 500 (~10%) and a globally diversified index
    such as the FTSE All-World (~7-8% since inception). Many popular FIRE
    calculators use a similarly conservative default (commonly 7%).
- Annual inflation rate: 3.0%
    Long-run historical average inflation rate commonly used as a default
    in FIRE / retirement calculators.
- Safe withdrawal rate (SWR): 4.0%
    The widely cited "4% rule", based on the Trinity Study, which found a
    4% withdrawal rate sustainable over a 30-year retirement (with a
    50/50 stock/bond portfolio). A reasonable adjustable range is roughly
    3-5%.

Note on the real return calculation:
    real_return = (1 + nominal_return) / (1 + inflation) - 1
    This is the Fisher equation, which correctly accounts for the
    compounding interaction between nominal returns and inflation
    (rather than the simpler nominal-minus-inflation approximation used
    by some calculators). All real-return math in this repository uses
    this same formula for consistency.

This is intentionally a simple, evolving tool. Already supported:

- Loading a personal "savings diary" CSV (columns: `date`, `net_worth`;
  dates in YYYY-MM-DD format) to show real recorded history alongside
  the projection -- entirely optional, the tool works the same as
  before if you don't have one.
- "Partial FIRE": instead of targeting full expense coverage, target
  just enough to sustainably withdraw a specific monthly amount (in
  today's money) -- e.g. for a pension top-up rather than full
  retirement.
- A reference table showing, purely for illustration, how years-to-FIRE
  changes with savings rate (independent of income), at your current
  return/inflation/withdrawal-rate assumptions.

After computing the result, this script opens a chart (via matplotlib)
showing the projected net worth over time alongside the FIRE target as a
reference line. Requires matplotlib (`pip install matplotlib`); the core
calculation itself has no external dependencies.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Default assumptions (see module docstring for sources/reasoning)
# ---------------------------------------------------------------------------

DEFAULT_NOMINAL_RETURN_PCT = 8.0
DEFAULT_INFLATION_PCT = 3.0
DEFAULT_WITHDRAWAL_RATE_PCT = 4.0
DEFAULT_SAVINGS_GROWTH_PCT = 0.0   # 0 = disabled (no annual savings increase)

# Recommended (not enforced) sane range for the withdrawal rate.
WITHDRAWAL_RATE_MIN_PCT = 3.0
WITHDRAWAL_RATE_MAX_PCT = 5.0


def real_return_pct_from(nominal_pct: float, inflation_pct: float) -> float:
    """Real annual return implied by a nominal return and an inflation
    rate, via the Fisher equation: (1+nominal)/(1+inflation) - 1.

    Used everywhere in this module that a real return needs deriving
    from nominal + inflation, so the two call sites can't drift apart.
    """
    return ((1 + nominal_pct / 100) / (1 + inflation_pct / 100) - 1) * 100



@dataclass
class FireInputs:
    """All user-provided inputs for the FIRE calculation."""

    current_net_worth: float       # Current invested assets / starting balance
    annual_income: float           # Net (take-home) annual income
    monthly_savings: float         # Amount invested every month
    nominal_return_pct: float = DEFAULT_NOMINAL_RETURN_PCT
    inflation_pct: float = DEFAULT_INFLATION_PCT
    withdrawal_rate_pct: float = DEFAULT_WITHDRAWAL_RATE_PCT
    # The date `current_net_worth` is as of. Defaults to today, but if
    # current_net_worth comes from a savings-diary CSV, this should be the
    # date of that entry instead, so projections start from the right point.
    as_of_date: _dt.date = field(default_factory=_dt.date.today)
    # Partial FIRE: instead of targeting full expense coverage, target
    # just enough to sustainably withdraw `desired_monthly_income` (in
    # TODAY's money) per month via the withdrawal rate. Useful for
    # someone who doesn't expect/want to fully retire, but wants to know
    # when they could afford a specific monthly amount of "side income"
    # (e.g. a pension top-up).
    partial_fire: bool = False
    desired_monthly_income: float | None = None  # Today's money; only used if partial_fire=True
    # Optional: nominal annual % by which the monthly savings amount grows each year.
    # 0 (the default) means constant savings, preserving the original closed-form behaviour.
    # Positive values cause the solver to use a month-by-month simulation instead.
    savings_growth_pct: float = DEFAULT_SAVINGS_GROWTH_PCT
    # Coast FIRE: the earliest point where, even if you stopped saving completely,
    # compound growth alone would reach your FIRE number by `retirement_age`.
    # Both fields must be set for the Coast FIRE calculation to run.
    coast_fire: bool = False
    current_age: int | None = None
    retirement_age: int | None = None


@dataclass
class FireResult:
    """Output of the FIRE calculation."""

    annual_expenses: float
    fire_number: float              # the target actually used (full or partial)
    real_return_pct: float
    real_savings_growth_pct: float = 0.0   # derived from inputs.savings_growth_pct via Fisher
    months_to_fire: float | None = None    # None if the target is unreachable
    years_part: int = 0
    months_part: int = 0
    fire_date: _dt.date | None = None
    savings_rate_pct: float = 0.0
    is_partial: bool = False
    # Only set when is_partial=True:
    desired_monthly_income_today: float | None = None
    desired_monthly_income_future: float | None = None
    # Coast FIRE (only set when inputs.coast_fire=True and both ages provided):
    coast_fire_number: float | None = None
    already_coast: bool = False          # current_net_worth >= coast_fire_number
    months_to_coast: float | None = None
    years_coast: int = 0
    months_coast: int = 0
    coast_date: _dt.date | None = None


# ---------------------------------------------------------------------------
# Core calculation (kept free of any input()/print() so it can be reused
# later -- e.g. from a web UI, tests, or other tools in this repo).
# ---------------------------------------------------------------------------

def calculate_fire(inputs: FireInputs) -> FireResult:
    """Compute the FIRE number and the time needed to reach it.

    Normally, the target is full financial independence: enough to cover
    `annual_expenses` (derived as income minus savings) via the
    withdrawal rate. If `inputs.partial_fire` is set, the target instead
    becomes just enough to sustainably withdraw
    `inputs.desired_monthly_income` (today's money) per month -- e.g. for
    a pension top-up rather than full retirement.

    Raises:
        ValueError: if monthly savings are so high that they would imply
            zero or negative living expenses (i.e. monthly_savings * 12
            >= annual_income), or if partial FIRE is requested without a
            positive `desired_monthly_income`.
    """
    annual_savings = inputs.monthly_savings * 12
    annual_expenses = inputs.annual_income - annual_savings

    if annual_expenses <= 0:
        raise ValueError(
            "Monthly savings imply zero or negative annual expenses "
            "(monthly_savings * 12 >= annual_income). Please check your "
            "income and savings amount."
        )

    savings_rate_pct = (
        (annual_savings / inputs.annual_income) * 100 if inputs.annual_income else 0.0
    )

    withdrawal_rate = inputs.withdrawal_rate_pct / 100

    is_partial = bool(inputs.partial_fire and inputs.desired_monthly_income)
    if is_partial:
        if inputs.desired_monthly_income <= 0:
            raise ValueError("Desired monthly income for partial FIRE must be positive.")
        fire_number = (inputs.desired_monthly_income * 12) / withdrawal_rate
    else:
        fire_number = annual_expenses / withdrawal_rate

    # Real return via the Fisher equation (see module docstring).
    real_return_pct = real_return_pct_from(inputs.nominal_return_pct, inputs.inflation_pct)
    annual_real_return = real_return_pct / 100

    # Real annual growth rate for the savings amount.
    # 0% input → real growth = 0 (constant savings in real terms, backward-compatible).
    # Any positive nominal rate X is converted via Fisher equation, which typically
    # yields a slightly negative real rate when X < inflation (e.g. 2% nominal with
    # 3% inflation → −0.97% real, meaning savings keep up less than fully with inflation).
    if abs(inputs.savings_growth_pct) < 1e-9:
        real_savings_growth_pct = 0.0
    else:
        real_savings_growth_pct = real_return_pct_from(inputs.savings_growth_pct, inputs.inflation_pct)
    annual_real_savings_growth = real_savings_growth_pct / 100

    # Choose solver: closed-form when savings are constant, simulation when
    # they grow (the closed-form assumes a fixed monthly contribution).
    if abs(annual_real_savings_growth) < 1e-9:
        months_to_fire = _months_to_reach_target(
            starting_balance=inputs.current_net_worth,
            monthly_contribution=inputs.monthly_savings,
            annual_return=annual_real_return,
            target=fire_number,
        )
    else:
        months_to_fire = _simulate_to_target(
            starting_balance=inputs.current_net_worth,
            monthly_savings=inputs.monthly_savings,
            annual_real_return=annual_real_return,
            target=fire_number,
            annual_real_savings_growth=annual_real_savings_growth,
        )

    years_part, months_part = (0, 0)
    fire_date = None
    desired_monthly_income_future = None
    if months_to_fire is not None:
        years_part, months_part = divmod(round(months_to_fire), 12)
        fire_date = _add_months(inputs.as_of_date, round(months_to_fire))
        if is_partial:
            years_elapsed = months_to_fire / 12
            desired_monthly_income_future = inputs.desired_monthly_income * (
                (1 + inputs.inflation_pct / 100) ** years_elapsed
            )

    # -----------------------------------------------------------------------
    # Coast FIRE (optional): the portfolio value at which compound growth
    # alone -- with zero further contributions -- reaches `fire_number` by
    # `retirement_age`.
    # -----------------------------------------------------------------------
    coast_fire_number = None
    already_coast = False
    months_to_coast = None
    years_coast = months_coast = 0
    coast_date = None

    if (
        inputs.coast_fire
        and inputs.current_age is not None
        and inputs.retirement_age is not None
        and inputs.retirement_age > inputs.current_age
    ):
        years_to_retirement = inputs.retirement_age - inputs.current_age
        coast_fire_number = fire_number / (1 + annual_real_return) ** years_to_retirement

        if inputs.current_net_worth >= coast_fire_number:
            already_coast = True
        else:
            # Time needed to reach coast_fire_number (savings growth applies here too).
            if abs(annual_real_savings_growth) < 1e-9:
                months_to_coast = _months_to_reach_target(
                    starting_balance=inputs.current_net_worth,
                    monthly_contribution=inputs.monthly_savings,
                    annual_return=annual_real_return,
                    target=coast_fire_number,
                )
            else:
                months_to_coast = _simulate_to_target(
                    starting_balance=inputs.current_net_worth,
                    monthly_savings=inputs.monthly_savings,
                    annual_real_return=annual_real_return,
                    target=coast_fire_number,
                    annual_real_savings_growth=annual_real_savings_growth,
                )
            if months_to_coast is not None:
                years_coast, months_coast = divmod(round(months_to_coast), 12)
                coast_date = _add_months(inputs.as_of_date, round(months_to_coast))

    return FireResult(
        annual_expenses=annual_expenses,
        fire_number=fire_number,
        real_return_pct=real_return_pct,
        real_savings_growth_pct=real_savings_growth_pct,
        months_to_fire=months_to_fire,
        years_part=years_part,
        months_part=months_part,
        fire_date=fire_date,
        savings_rate_pct=savings_rate_pct,
        is_partial=is_partial,
        desired_monthly_income_today=inputs.desired_monthly_income if is_partial else None,
        desired_monthly_income_future=desired_monthly_income_future,
        coast_fire_number=coast_fire_number,
        already_coast=already_coast,
        months_to_coast=months_to_coast,
        years_coast=years_coast,
        months_coast=months_coast,
        coast_date=coast_date,
    )


def _months_to_reach_target(
    starting_balance: float,
    monthly_contribution: float,
    annual_return: float,
    target: float,
) -> float | None:
    """Solve for the number of months needed to reach `target`, given a
    starting balance, a fixed monthly contribution, and a constant annual
    rate of return (compounded monthly).

    Returns None if the target can never be reached (no growth and
    contributions are not enough -- or balance is shrinking).
    """
    if starting_balance >= target:
        return 0.0

    # Convert annual rate to an equivalent monthly compounding rate.
    monthly_rate = (1 + annual_return) ** (1 / 12) - 1

    if abs(monthly_rate) < 1e-12:
        # No real growth: purely linear accumulation from contributions.
        if monthly_contribution <= 0:
            return None
        return (target - starting_balance) / monthly_contribution

    # Closed-form solution for n in:
    # target = balance*(1+r)^n + contribution * (((1+r)^n - 1) / r)
    numerator = target * monthly_rate + monthly_contribution
    denominator = starting_balance * monthly_rate + monthly_contribution

    if denominator <= 0 or numerator <= 0:
        return None

    ratio = numerator / denominator
    if ratio <= 1:
        # Already there or contributions/return are negative relative to target.
        return 0.0

    import math
    n_months = math.log(ratio) / math.log(1 + monthly_rate)
    return n_months


def _simulate_to_target(
    starting_balance: float,
    monthly_savings: float,
    annual_real_return: float,
    target: float,
    annual_real_savings_growth: float,
    max_years: int = 100,
) -> float | None:
    """Month-by-month simulation: find the first month where the balance
    reaches `target`, given a savings amount that grows at
    `annual_real_savings_growth` per year (in real / inflation-adjusted
    terms).

    Used when `annual_real_savings_growth != 0`, because the closed-form
    solution in `_months_to_reach_target` assumes constant contributions.

    Returns the month number (as float) when target is first reached, or
    None if not reached within `max_years`.
    """
    if starting_balance >= target:
        return 0.0

    monthly_rate = (1 + annual_real_return) ** (1 / 12) - 1
    monthly_savings_growth = (1 + annual_real_savings_growth) ** (1 / 12) - 1

    balance = starting_balance
    savings = monthly_savings

    for month in range(1, max_years * 12 + 1):
        balance = balance * (1 + monthly_rate) + savings
        savings = savings * (1 + monthly_savings_growth)
        if balance >= target:
            return float(month)

    return None


def _add_months(start: _dt.date, months: int) -> _dt.date:
    """Add `months` calendar months to a date (day is clamped to 28)."""
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start.day, 28)
    return _dt.date(year, month, day)


# Illustrative savings rates for the reference table in `savings_rate_reference_table`.
ILLUSTRATIVE_SAVINGS_RATES_PCT = [10, 15, 20, 25, 30, 35, 40, 50, 60, 70, 80, 90]


def savings_rate_reference_table(
    nominal_return_pct: float,
    inflation_pct: float,
    withdrawal_rate_pct: float,
) -> list[dict]:
    """For a range of illustrative savings rates, compute years to reach
    full FIRE, starting from zero net worth.

    This reproduces a well-known relationship popularized in the FIRE
    community (e.g. Mr. Money Mustache's "The Shockingly Simple Math
    Behind Early Retirement"): starting from zero, the time to reach FI
    depends only on your savings RATE, not your absolute income -- which
    is why the table below works for everyone regardless of how much
    they earn. The numbers here are computed independently with this
    module's own formula (at the given return/inflation/withdrawal-rate
    assumptions), not copied from any external table.

    Returns a list of dicts: {"savings_rate_pct": ..., "years": ... or None}.
    `years` is None if that savings rate never reaches the target.
    """
    real_return_pct = real_return_pct_from(nominal_return_pct, inflation_pct)
    annual_real_return = real_return_pct / 100
    withdrawal_rate = withdrawal_rate_pct / 100

    rows = []
    for rate_pct in ILLUSTRATIVE_SAVINGS_RATES_PCT:
        rate = rate_pct / 100
        # An arbitrary income base of 100 -- it cancels out completely,
        # only the savings RATE affects the result.
        annual_income = 100.0
        annual_savings = annual_income * rate
        annual_expenses = annual_income - annual_savings

        months = None
        if annual_expenses > 0:
            target = annual_expenses / withdrawal_rate
            months = _months_to_reach_target(
                starting_balance=0.0,
                monthly_contribution=annual_savings / 12,
                annual_return=annual_real_return,
                target=target,
            )

        rows.append({
            "savings_rate_pct": rate_pct,
            "years": (months / 12) if months is not None else None,
        })
    return rows


def _balance_at_month(
    month: int,
    starting_balance: float,
    monthly_contribution: float,
    monthly_rate: float,
) -> float:
    """Projected balance after `month` months of compounding plus a fixed
    monthly contribution. Shared by the time-to-FIRE solver's curve and the
    chart in `plot_projection`."""
    if abs(monthly_rate) < 1e-12:
        return starting_balance + monthly_contribution * month
    growth = (1 + monthly_rate) ** month
    return starting_balance * growth + monthly_contribution * ((growth - 1) / monthly_rate)


# ---------------------------------------------------------------------------
# Savings diary: load a personal history of (date, net_worth) entries
# ---------------------------------------------------------------------------

def parse_savings_csv(file_obj) -> list[tuple[_dt.date, float]]:
    """Parse an already-open, text-mode file-like object with `date` and
    `net_worth` columns (dates in YYYY-MM-DD format).

    Shared by `load_savings_history` (reading a CSV from disk for the
    CLI) and the web UI (parsing an uploaded file directly from memory,
    without writing it to disk first).

    Rows that can't be parsed are skipped (with a warning printed to the
    console) rather than aborting the whole load. The returned list is
    sorted by date, ascending.

    Raises:
        ValueError: if the file doesn't have the expected columns.
    """
    import csv

    reader = csv.DictReader(file_obj)
    if not reader.fieldnames:
        raise ValueError("The CSV file appears to be empty.")

    normalized = {name.strip().lower(): name for name in reader.fieldnames}
    if "date" not in normalized or "net_worth" not in normalized:
        raise ValueError(
            "Expected a CSV with 'date' and 'net_worth' columns "
            f"(found: {reader.fieldnames})."
        )
    date_key = normalized["date"]
    net_worth_key = normalized["net_worth"]

    entries: list[tuple[_dt.date, float]] = []
    for line_number, row in enumerate(reader, start=2):  # header = line 1
        raw_date = (row.get(date_key) or "").strip()
        raw_value = (row.get(net_worth_key) or "").strip()
        try:
            entry_date = _dt.date.fromisoformat(raw_date)
            entry_value = float(raw_value)
        except (ValueError, TypeError):
            print(
                f"  Skipping line {line_number}: could not parse "
                f"date='{raw_date}' net_worth='{raw_value}'."
            )
            continue
        entries.append((entry_date, entry_value))

    entries.sort(key=lambda pair: pair[0])
    return entries


def load_savings_history(path: str) -> list[tuple[_dt.date, float]]:
    """Load a savings-diary CSV file from disk (see `parse_savings_csv`
    for the expected format).

    Raises:
        FileNotFoundError: if `path` does not exist.
        ValueError: if the file doesn't have the expected columns.
    """
    with open(path, newline="", encoding="utf-8") as f:
        return parse_savings_csv(f)


# ---------------------------------------------------------------------------
# Chart: projected net worth vs. the FIRE target
# ---------------------------------------------------------------------------

def compute_projection_series(
    inputs: "FireInputs",
    result: "FireResult",
) -> tuple[list[_dt.date], list[float]]:
    """Compute the (dates, balances) series for the projection curve.

    When `result.real_savings_growth_pct` is non-zero, a month-by-month
    simulation is used; otherwise the closed-form `_balance_at_month` is
    used.  The horizon is extended to show both the FIRE crossing and the
    Coast FIRE crossing (if applicable).
    """
    monthly_rate = (1 + result.real_return_pct / 100) ** (1 / 12) - 1

    if result.months_to_fire is not None:
        horizon_months = max(round(result.months_to_fire * 1.15), round(result.months_to_fire) + 6)
    else:
        horizon_months = 40 * 12

    # Extend horizon to show Coast FIRE crossing point if it falls later.
    if result.months_to_coast is not None:
        horizon_months = max(horizon_months, round(result.months_to_coast) + 6)

    anchor_date = inputs.as_of_date
    n = horizon_months + 1

    if abs(result.real_savings_growth_pct) > 1e-9:
        monthly_savings_growth = (1 + result.real_savings_growth_pct / 100) ** (1 / 12) - 1
        balances = []
        balance = inputs.current_net_worth
        savings = inputs.monthly_savings
        balances.append(balance)
        for _ in range(horizon_months):
            balance = balance * (1 + monthly_rate) + savings
            savings = savings * (1 + monthly_savings_growth)
            balances.append(balance)
    else:
        balances = [
            _balance_at_month(m, inputs.current_net_worth, inputs.monthly_savings, monthly_rate)
            for m in range(n)
        ]

    dates = [_add_months(anchor_date, m) for m in range(n)]
    return dates, balances


def build_projection_figure(
    inputs: "FireInputs",
    result: "FireResult",
    history: list[tuple[_dt.date, float]] | None = None,
):
    """Build (but do not display) a matplotlib Figure showing projected
    net worth over time, together with a horizontal reference line for
    the FIRE target.

    If `history` is provided (a list of (date, net_worth) entries from a
    savings diary), it is plotted as well, so real recorded history and
    the future projection appear side by side on the same chart.

    Returns the Figure, so callers can either display it (CLI, via
    `plot_projection`) or save it to a buffer/file.

    Requires matplotlib (imported lazily so the rest of the module has no
    hard dependency on it).
    """
    import matplotlib.pyplot as plt

    dates, balances = compute_projection_series(inputs, result)

    fig, ax = plt.subplots(figsize=(10, 6))

    if history:
        hist_dates = [d for d, _ in history]
        hist_values = [v for _, v in history]
        ax.plot(
            hist_dates,
            hist_values,
            color="#2F6F52",
            marker="o",
            markersize=4,
            linewidth=2,
            label="Recorded history",
        )

    ax.plot(dates, balances, color="#3B6EA5", linewidth=2, label="Projected net worth")
    ax.axhline(
        result.fire_number,
        color="#B3402F",
        linestyle="--",
        linewidth=1.5,
        label=f"FIRE target: {result.fire_number:,.0f}",
    )

    if result.coast_fire_number is not None:
        ax.axhline(
            result.coast_fire_number,
            color="#C07A20",
            linestyle=":",
            linewidth=1.5,
            label=f"Coast FIRE: {result.coast_fire_number:,.0f}",
        )
        if result.already_coast:
            ax.scatter([dates[0]], [result.coast_fire_number], color="#C07A20", zorder=5)
            ax.annotate(
                "Already Coast FIRE!",
                xy=(dates[0], result.coast_fire_number),
                xytext=(10, 12),
                textcoords="offset points",
                fontsize=9,
                color="#C07A20",
            )
        elif result.coast_date is not None:
            ax.scatter([result.coast_date], [result.coast_fire_number], color="#C07A20", zorder=5)
            ax.annotate(
                f"Coast FIRE: {result.coast_date.strftime('%B %Y')}\n({result.years_coast}y {result.months_coast}m)",
                xy=(result.coast_date, result.coast_fire_number),
                xytext=(10, 12),
                textcoords="offset points",
                fontsize=9,
                color="#C07A20",
            )

    if result.months_to_fire is not None and result.fire_date is not None:
        ax.scatter([result.fire_date], [result.fire_number], color="#B3402F", zorder=5)
        ax.annotate(
            f"{result.fire_date.strftime('%B %Y')}\n({result.years_part}y {result.months_part}m)",
            xy=(result.fire_date, result.fire_number),
            xytext=(10, 12),
            textcoords="offset points",
            fontsize=9,
            color="#B3402F",
        )
    else:
        ax.text(
            0.02,
            0.95,
            "Target not reached within the shown horizon at these assumptions.",
            transform=ax.transAxes,
            fontsize=9,
            color="#B3402F",
            va="top",
        )

    ax.set_title("Net Worth vs. FIRE Target")
    ax.set_xlabel("Date")
    ax.set_ylabel("Net worth")
    ax.legend(loc="lower right")
    ax.grid(True, alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()
    return fig


def plot_projection(
    inputs: "FireInputs",
    result: "FireResult",
    history: list[tuple[_dt.date, float]] | None = None,
) -> None:
    """Open a window displaying the chart built by `build_projection_figure`.
    Used by the CLI. Requires matplotlib; see `build_projection_figure`."""
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print(
            "\n(Skipping chart: matplotlib is not installed. "
            "Install it with 'pip install matplotlib' to see the graph.)"
        )
        return

    build_projection_figure(inputs, result, history=history)
    plt.show()


# ---------------------------------------------------------------------------
# Simple interactive command-line interface
# ---------------------------------------------------------------------------

def _prompt_float(
    label: str,
    default: float | None = None,
    min_value: float | None = None,
    max_value: float | None = None,
) -> float:
    """Ask the user for a number, with an optional default value and an
    optional (advisory, non-blocking outside hard bounds) valid range."""
    while True:
        suffix = f" [default: {default}]" if default is not None else ""
        raw = input(f"{label}{suffix}: ").strip().replace(",", ".")

        if raw == "" and default is not None:
            return default

        try:
            value = float(raw)
        except ValueError:
            print("  Please enter a valid number.")
            continue

        if min_value is not None and value < min_value:
            print(f"  Value must be at least {min_value}.")
            continue
        if max_value is not None and value > max_value:
            print(f"  Value must be at most {max_value}.")
            continue

        return value


def run_cli() -> None:
    print("=" * 60)
    print("FIRE Calculator - Financial Independence Time Estimator")
    print("=" * 60)
    print(
        "Enter all amounts in the same currency. All values represent "
        "today's money (real terms).\n"
    )

    print(
        "If you keep a savings diary (a CSV file with 'date' and "
        "'net_worth' columns), I can use it to show your real history "
        "alongside the projection."
    )
    csv_path = input(
        "Path to your savings diary CSV (press Enter to skip): "
    ).strip()

    history: list[tuple[_dt.date, float]] | None = None
    as_of_date = _dt.date.today()
    current_net_worth: float | None = None

    if csv_path:
        try:
            history = load_savings_history(csv_path)
        except FileNotFoundError:
            print(f"  Could not find a file at '{csv_path}'. ")
            history = None
        except ValueError as exc:
            print(f"  {exc}")
            history = None

        if history:
            as_of_date, current_net_worth = history[-1]
            print(
                f"  Loaded {len(history)} entries. Using your most recent "
                f"recorded net worth: {current_net_worth:,.2f} as of "
                f"{as_of_date.isoformat()}.\n"
            )
        else:
            print("  No valid entries found -- I'll ask for it manually instead.\n")

    if current_net_worth is None:
        current_net_worth = _prompt_float(
            "Current net worth / invested assets", min_value=0
        )

    annual_income = _prompt_float(
        "Annual net (take-home) income", min_value=0.01
    )
    monthly_savings = _prompt_float(
        "Monthly savings (amount invested each month)", min_value=0
    )

    print(
        "\nBy default this calculates full financial independence (enough "
        "to cover all your expenses). If instead you want to know when "
        "you could afford a specific extra monthly amount -- e.g. a "
        "pension top-up, without necessarily fully retiring -- you can "
        "calculate 'partial FIRE' instead.\n"
    )
    partial_choice = input(
        "Calculate partial FIRE for a specific monthly amount instead? [y/N]: "
    ).strip().lower()
    partial_fire = partial_choice in ("y", "yes")
    desired_monthly_income = None
    if partial_fire:
        desired_monthly_income = _prompt_float(
            "Desired extra monthly amount (today's money)", min_value=0.01
        )

    print(
        "\nThe next values have sensible defaults based on long-term "
        "historical averages. Press Enter to accept the default, or type "
        "your own value.\n"
    )

    nominal_return_pct = _prompt_float(
        "Expected nominal annual investment return (%)",
        default=DEFAULT_NOMINAL_RETURN_PCT,
        min_value=0,
        max_value=30,
    )
    inflation_pct = _prompt_float(
        "Expected annual inflation rate (%)",
        default=DEFAULT_INFLATION_PCT,
        min_value=0,
        max_value=20,
    )
    withdrawal_rate_pct = _prompt_float(
        f"Safe withdrawal rate (%) [recommended range "
        f"{WITHDRAWAL_RATE_MIN_PCT}-{WITHDRAWAL_RATE_MAX_PCT}]",
        default=DEFAULT_WITHDRAWAL_RATE_PCT,
        min_value=0.5,
        max_value=10,
    )

    inputs = FireInputs(
        current_net_worth=current_net_worth,
        annual_income=annual_income,
        monthly_savings=monthly_savings,
        nominal_return_pct=nominal_return_pct,
        inflation_pct=inflation_pct,
        withdrawal_rate_pct=withdrawal_rate_pct,
        as_of_date=as_of_date,
        partial_fire=partial_fire,
        desired_monthly_income=desired_monthly_income,
    )

    try:
        result = calculate_fire(inputs)
    except ValueError as exc:
        print(f"\nError: {exc}")
        return

    print("\n" + "-" * 60)
    print("RESULTS")
    print("-" * 60)
    print(f"Savings rate:                   {result.savings_rate_pct:.1f}%")
    print(f"Estimated annual expenses:     {result.annual_expenses:,.2f}")
    print(f"Real (inflation-adjusted) return: {result.real_return_pct:.2f}%")
    if result.is_partial:
        print(f"Partial FIRE target (today's money, {desired_monthly_income:,.2f}/mo): {result.fire_number:,.2f}")
    else:
        print(f"FIRE number (target net worth): {result.fire_number:,.2f}")

    if result.months_to_fire is None:
        print(
            "\nWith these inputs, the target is not reachable "
            "(savings/return are too low relative to it). Try increasing "
            "monthly savings or expected return, or lowering the target."
        )
        print("Opening a chart to visualize the projection anyway...")
        plot_projection(inputs, result, history=history)
        return

    label = "partial financial independence" if result.is_partial else "financial independence"
    print(f"\nTime to {label}: {result.years_part} years and {result.months_part} months")
    if result.fire_date:
        print(f"Estimated date: {result.fire_date.strftime('%B %Y')}")

    if result.is_partial and result.desired_monthly_income_future is not None:
        print(
            f"\nYour target of {result.desired_monthly_income_today:,.2f}/month (today's money) "
            f"will be equivalent to about {result.desired_monthly_income_future:,.2f}/month "
            f"in {result.fire_date.strftime('%Y')} prices (after "
            f"{result.years_part}y {result.months_part}m of inflation)."
        )

    print("\n" + "-" * 60)
    print(
        f"For comparison: years to FULL FIRE by savings rate, at your "
        f"current assumptions (return {nominal_return_pct:.1f}%, inflation "
        f"{inflation_pct:.1f}%, withdrawal rate {withdrawal_rate_pct:.1f}%), "
        f"starting from zero net worth:"
    )
    for row in savings_rate_reference_table(nominal_return_pct, inflation_pct, withdrawal_rate_pct):
        years_str = f"{row['years']:.1f} years" if row["years"] is not None else "not reachable"
        print(f"  {row['savings_rate_pct']:>3}% saved  ->  {years_str}")

    print("\nOpening a chart of your projected net worth...")
    plot_projection(inputs, result, history=history)


if __name__ == "__main__":
    run_cli()
