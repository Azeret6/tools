#!/usr/bin/env python3
"""
FIRE Calculator (v1)
=====================

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
    real_return = nominal_return - inflation
    This is the same simplified approach used by most popular FIRE
    calculators (rather than the more precise Fisher equation). It is
    accurate enough for long-term planning purposes.

This is intentionally a simple, evolving tool. Already supported:
loading a personal "savings diary" CSV (columns: `date`, `net_worth`;
dates in YYYY-MM-DD format) to show real recorded history alongside the
projection -- this is entirely optional and the tool works the same as
before if you don't have one.

Planned future improvements include: variable/glide-path returns,
current age and target retirement age, Coast FIRE, salary growth, taxes,
one-off cash flows (inheritance, big purchases), and Monte Carlo
simulation.

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

# Recommended (not enforced) sane range for the withdrawal rate.
WITHDRAWAL_RATE_MIN_PCT = 3.0
WITHDRAWAL_RATE_MAX_PCT = 5.0


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


@dataclass
class FireResult:
    """Output of the FIRE calculation."""

    annual_expenses: float
    fire_number: float
    real_return_pct: float
    months_to_fire: float | None   # None if the target is unreachable
    years_part: int = 0
    months_part: int = 0
    fire_date: _dt.date | None = None


# ---------------------------------------------------------------------------
# Core calculation (kept free of any input()/print() so it can be reused
# later -- e.g. from a web UI, tests, or other tools in this repo).
# ---------------------------------------------------------------------------

def calculate_fire(inputs: FireInputs) -> FireResult:
    """Compute the FIRE number and the time needed to reach it.

    Raises:
        ValueError: if monthly savings are so high that they would imply
            zero or negative living expenses (i.e. monthly_savings * 12
            >= annual_income).
    """
    annual_savings = inputs.monthly_savings * 12
    annual_expenses = inputs.annual_income - annual_savings

    if annual_expenses <= 0:
        raise ValueError(
            "Monthly savings imply zero or negative annual expenses "
            "(monthly_savings * 12 >= annual_income). Please check your "
            "income and savings amount."
        )

    withdrawal_rate = inputs.withdrawal_rate_pct / 100
    fire_number = annual_expenses / withdrawal_rate

    # Simplified real return: nominal minus inflation (see module docstring).
    real_return_pct = inputs.nominal_return_pct - inputs.inflation_pct
    annual_real_return = real_return_pct / 100

    months_to_fire = _months_to_reach_target(
        starting_balance=inputs.current_net_worth,
        monthly_contribution=inputs.monthly_savings,
        annual_return=annual_real_return,
        target=fire_number,
    )

    years_part, months_part = (0, 0)
    fire_date = None
    if months_to_fire is not None:
        years_part, months_part = divmod(round(months_to_fire), 12)
        fire_date = _add_months(inputs.as_of_date, round(months_to_fire))

    return FireResult(
        annual_expenses=annual_expenses,
        fire_number=fire_number,
        real_return_pct=real_return_pct,
        months_to_fire=months_to_fire,
        years_part=years_part,
        months_part=months_part,
        fire_date=fire_date,
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


def _add_months(start: _dt.date, months: int) -> _dt.date:
    """Add `months` calendar months to a date (day is clamped to 28)."""
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start.day, 28)
    return _dt.date(year, month, day)


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

def load_savings_history(path: str) -> list[tuple[_dt.date, float]]:
    """Load a savings-diary CSV with `date` and `net_worth` columns
    (dates in YYYY-MM-DD format).

    Rows that can't be parsed are skipped (with a warning printed to the
    console) rather than aborting the whole load. The returned list is
    sorted by date, ascending.

    Raises:
        FileNotFoundError: if `path` does not exist.
        ValueError: if the file doesn't have the expected columns.
    """
    import csv

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
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


# ---------------------------------------------------------------------------
# Chart: projected net worth vs. the FIRE target
# ---------------------------------------------------------------------------

def plot_projection(
    inputs: "FireInputs",
    result: "FireResult",
    history: list[tuple[_dt.date, float]] | None = None,
) -> None:
    """Open a window showing projected net worth over time (a smooth curve
    starting from `inputs.current_net_worth` as of `inputs.as_of_date`,
    growing with compounding + monthly contributions), together with a
    horizontal reference line for the FIRE target.

    If `history` is provided (a list of (date, net_worth) entries from a
    savings diary), it is plotted as well, so real recorded history and
    the future projection appear side by side on the same chart.

    Requires matplotlib (imported lazily so the rest of the module has no
    hard dependency on it).
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print(
            "\n(Skipping chart: matplotlib is not installed. "
            "Install it with 'pip install matplotlib' to see the graph.)"
        )
        return

    monthly_rate = (1 + result.real_return_pct / 100) ** (1 / 12) - 1

    if result.months_to_fire is not None:
        # A little extra room past the FIRE date so the crossing is visible.
        horizon_months = max(round(result.months_to_fire * 1.15), round(result.months_to_fire) + 6)
    else:
        horizon_months = 40 * 12  # Default 40-year horizon if unreachable.

    anchor_date = inputs.as_of_date
    months = list(range(0, horizon_months + 1))
    dates = [_add_months(anchor_date, m) for m in months]
    balances = [
        _balance_at_month(m, inputs.current_net_worth, inputs.monthly_savings, monthly_rate)
        for m in months
    ]

    fig, ax = plt.subplots(figsize=(10, 6))

    if history:
        hist_dates = [d for d, _ in history]
        hist_values = [v for _, v in history]
        ax.plot(
            hist_dates,
            hist_values,
            color="#16a34a",
            marker="o",
            markersize=4,
            linewidth=2,
            label="Recorded history",
        )

    ax.plot(dates, balances, color="#2563eb", linewidth=2, label="Projected net worth")
    ax.axhline(
        result.fire_number,
        color="red",
        linestyle="--",
        linewidth=1.5,
        label=f"FIRE target: {result.fire_number:,.0f}",
    )

    if result.months_to_fire is not None and result.fire_date is not None:
        ax.scatter([result.fire_date], [result.fire_number], color="red", zorder=5)
        ax.annotate(
            f"{result.fire_date.strftime('%B %Y')}\n({result.years_part}y {result.months_part}m)",
            xy=(result.fire_date, result.fire_number),
            xytext=(10, 12),
            textcoords="offset points",
            fontsize=9,
            color="red",
        )
    else:
        ax.text(
            0.02,
            0.95,
            "Target not reached within the shown horizon at these assumptions.",
            transform=ax.transAxes,
            fontsize=9,
            color="red",
            va="top",
        )

    ax.set_title("Net Worth vs. FIRE Target")
    ax.set_xlabel("Date")
    ax.set_ylabel("Net worth")
    ax.legend(loc="lower right")
    ax.grid(True, alpha=0.3)
    fig.autofmt_xdate()
    plt.tight_layout()
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
    )

    try:
        result = calculate_fire(inputs)
    except ValueError as exc:
        print(f"\nError: {exc}")
        return

    print("\n" + "-" * 60)
    print("RESULTS")
    print("-" * 60)
    print(f"Estimated annual expenses:     {result.annual_expenses:,.2f}")
    print(f"Real (inflation-adjusted) return: {result.real_return_pct:.2f}%")
    print(f"FIRE number (target net worth): {result.fire_number:,.2f}")

    if result.months_to_fire is None:
        print(
            "\nWith these inputs, financial independence is not reachable "
            "(savings/return are too low relative to the target). Try "
            "increasing monthly savings or expected return, or lowering "
            "expenses / the withdrawal rate target."
        )
        print("Opening a chart to visualize the projection anyway...")
        plot_projection(inputs, result, history=history)
        return

    print(
        f"\nTime to financial independence: "
        f"{result.years_part} years and {result.months_part} months"
    )
    if result.fire_date:
        print(f"Estimated date: {result.fire_date.strftime('%B %Y')}")

    print("\nOpening a chart of your projected net worth...")
    plot_projection(inputs, result, history=history)


if __name__ == "__main__":
    run_cli()
