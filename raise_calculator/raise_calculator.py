"""
Raise Calculator
=================

Models the long-term impact of a net pay raise on your investable net
worth, comparing three scenarios:

    1. Current path        -- no raise; savings stay the same.
    2. Raise kept as cash   -- you get the raise, but don't invest it. It
                               still adds to your net worth, but it earns
                               no investment return. Since every amount in
                               this tool is tracked in today's money (real
                               terms), idle cash also loses purchasing
                               power to inflation over time -- it doesn't
                               just sit still in real terms, it slowly
                               shrinks.
    3. Raise fully invested -- the entire raise is added to monthly
                               savings/investments.

All amounts should be entered as NET (take-home) figures, in the same
currency, in today's money (real terms). Working in net, real terms
avoids having to model any country-specific tax system.

Optionally, you can provide a FIRE target (via annual expenses and a
withdrawal rate) to see how many years sooner -- if any -- investing the
raise gets you there, compared to spending it or letting it sit as cash.

This tool has no dependency on any other tool in this repository and can
be copied and used entirely on its own.

Default assumptions (overridable by the user):
------------------------------------------------
- Nominal annual investment return: 8.0%
- Annual inflation rate: 3.0%
- Safe withdrawal rate (SWR), used only if a FIRE target is requested: 4.0%

These mirror the defaults used elsewhere in this repository (see
fire_calculator for the underlying reasoning and sources).

Note on the real return calculation:
    real_return = (1 + nominal_return) / (1 + inflation) - 1
This is the Fisher equation, used consistently across this repository
(see fire_calculator). The same formula is applied to idle cash: its
nominal return is 0%, so its real return is `1/(1+inflation) - 1`,
i.e. it loses value at slightly less than the raw inflation rate (the
Fisher equation's compounding correction applies here too).

After computing the result, this script opens a chart (via matplotlib)
comparing net worth growth across the three scenarios. Requires
matplotlib (`pip install matplotlib`); the core calculation itself has no
external dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

# ---------------------------------------------------------------------------
# Default assumptions (see module docstring for sources/reasoning)
# ---------------------------------------------------------------------------

DEFAULT_NOMINAL_RETURN_PCT = 8.0
DEFAULT_INFLATION_PCT = 3.0
DEFAULT_WITHDRAWAL_RATE_PCT = 4.0
DEFAULT_PROJECTION_YEARS = 30

# Recommended (not enforced) sane range for the withdrawal rate.
WITHDRAWAL_RATE_MIN_PCT = 3.0
WITHDRAWAL_RATE_MAX_PCT = 5.0

# Cap for the numeric years-to-target search, regardless of chart horizon.
MAX_SOLVER_YEARS = 100


def real_return_pct_from(nominal_pct: float, inflation_pct: float) -> float:
    """Real annual return implied by a nominal return and an inflation
    rate, via the Fisher equation: (1+nominal)/(1+inflation) - 1.
    Mirrors the identically-named helper in fire_calculator.py, kept
    here too since this tool has no dependency on that module.
    """
    return ((1 + nominal_pct / 100) / (1 + inflation_pct / 100) - 1) * 100



@dataclass
class RaiseInputs:
    """All user-provided inputs for the raise impact calculation."""

    current_monthly_savings: float     # Amount currently invested each month
    raise_amount: float                # Net monthly raise (take-home increase)
    current_net_worth: float = 0.0     # Starting balance; assumed invested
    nominal_return_pct: float = DEFAULT_NOMINAL_RETURN_PCT
    inflation_pct: float = DEFAULT_INFLATION_PCT
    projection_years: int = DEFAULT_PROJECTION_YEARS

    # Optional FIRE target -- leave both None to skip the comparison entirely.
    annual_expenses: float | None = None
    withdrawal_rate_pct: float = DEFAULT_WITHDRAWAL_RATE_PCT
    fire_target: float | None = None   # Direct override; takes precedence
                                        # over annual_expenses if both are set.


@dataclass
class ScenarioResult:
    """Projected outcome for a single scenario."""

    key: str                                    # Stable identifier
    label: str                                  # Human-readable name
    invested_monthly: float                     # Amount actually invested each month
    cash_monthly: float                         # Amount kept as idle cash each month
    net_worth_by_year: list[tuple[int, float]]  # (year offset, net worth)
    years_to_target: float | None = None        # None if no target / unreachable


@dataclass
class RaiseComparisonResult:
    """Output of the full scenario comparison."""

    real_return_pct: float       # Real return on invested money
    cash_real_return_pct: float  # Real return on idle cash (0% nominal, via Fisher)
    fire_target: float | None
    horizon_years: int
    scenarios: list[ScenarioResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Core calculation (kept free of any input()/print() so it can be reused
# later -- e.g. from a web UI, tests, or other tools in this repo).
# ---------------------------------------------------------------------------

def calculate_raise_scenarios(inputs: RaiseInputs) -> RaiseComparisonResult:
    """Compute net worth trajectories for the three raise scenarios.

    Raises:
        ValueError: if current_monthly_savings or raise_amount is negative.
    """
    if inputs.current_monthly_savings < 0:
        raise ValueError("current_monthly_savings cannot be negative.")
    if inputs.raise_amount < 0:
        raise ValueError("raise_amount cannot be negative.")

    # Real return via the Fisher equation (see module docstring).
    real_return_pct = real_return_pct_from(inputs.nominal_return_pct, inputs.inflation_pct)
    monthly_rate = (1 + real_return_pct / 100) ** (1 / 12) - 1

    # Idle cash earns 0% nominal -- the Fisher equation still applies.
    cash_real_return_pct = real_return_pct_from(0.0, inputs.inflation_pct)
    cash_monthly_rate = (1 + cash_real_return_pct / 100) ** (1 / 12) - 1

    target = _resolve_target(inputs)

    baseline_savings = inputs.current_monthly_savings
    invested_savings = inputs.current_monthly_savings + inputs.raise_amount

    def make_balance_fn(invested_monthly: float, cash_monthly: float) -> Callable[[int], float]:
        def balance_fn(month: int) -> float:
            invested = _balance_at_month(
                month, inputs.current_net_worth, invested_monthly, monthly_rate
            )
            cash = (
                _balance_at_month(month, 0.0, cash_monthly, cash_monthly_rate)
                if cash_monthly else 0.0
            )
            return invested + cash
        return balance_fn

    scenario_defs = [
        ("current_path", "Current path (no raise)", baseline_savings, 0.0),
        ("raise_uninvested", "Raise kept as cash (not invested)", baseline_savings, inputs.raise_amount),
        ("raise_invested", "Raise fully invested", invested_savings, 0.0),
    ]

    balance_fns = {
        key: make_balance_fn(invested_monthly, cash_monthly)
        for key, _, invested_monthly, cash_monthly in scenario_defs
    }

    years_to_target = {
        key: (_years_to_reach_target(fn, target) if target is not None else None)
        for key, fn in balance_fns.items()
    }

    horizon_years = _resolve_horizon(inputs.projection_years, *years_to_target.values())

    scenarios = [
        ScenarioResult(
            key=key,
            label=label,
            invested_monthly=invested_monthly,
            cash_monthly=cash_monthly,
            net_worth_by_year=[
                (year, balance_fns[key](year * 12)) for year in range(horizon_years + 1)
            ],
            years_to_target=years_to_target[key],
        )
        for key, label, invested_monthly, cash_monthly in scenario_defs
    ]

    return RaiseComparisonResult(
        real_return_pct=real_return_pct,
        cash_real_return_pct=cash_real_return_pct,
        fire_target=target,
        horizon_years=horizon_years,
        scenarios=scenarios,
    )


def _resolve_target(inputs: RaiseInputs) -> float | None:
    """Determine the FIRE target net worth, if any was requested.
    A direct `fire_target` takes precedence over `annual_expenses`."""
    if inputs.fire_target is not None:
        return inputs.fire_target
    if inputs.annual_expenses is not None:
        return inputs.annual_expenses / (inputs.withdrawal_rate_pct / 100)
    return None


def _resolve_horizon(projection_years: int, *years_to_target: float | None) -> int:
    """Pick a chart horizon long enough to show every reachable target
    being hit, without letting an unreachable scenario drag it out forever."""
    reachable = [y for y in years_to_target if y is not None]
    if not reachable:
        return projection_years
    needed = max(reachable)
    import math
    return max(projection_years, min(math.ceil(needed) + 2, 80))


def _balance_at_month(
    month: int,
    starting_balance: float,
    monthly_contribution: float,
    monthly_rate: float,
) -> float:
    """Projected balance after `month` months of compounding plus a fixed
    monthly contribution, at a constant monthly rate of return. Works for
    positive, negative, or zero rates."""
    if abs(monthly_rate) < 1e-12:
        return starting_balance + monthly_contribution * month
    growth = (1 + monthly_rate) ** month
    return starting_balance * growth + monthly_contribution * ((growth - 1) / monthly_rate)


def _years_to_reach_target(
    balance_fn: Callable[[int], float],
    target: float,
    max_years: int = MAX_SOLVER_YEARS,
) -> float | None:
    """Find the number of years needed for `balance_fn(month)` to reach
    `target`, via binary search over months. Works for any scenario whose
    balance is non-decreasing in time -- including ones that combine an
    invested component and a separately-rated idle-cash component, which
    don't have a simple closed-form solution.

    Returns None if the target isn't reached within `max_years`.
    """
    if balance_fn(0) >= target:
        return 0.0

    max_months = max_years * 12
    if balance_fn(max_months) < target:
        return None

    lo, hi = 0, max_months
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if balance_fn(mid) >= target:
            hi = mid
        else:
            lo = mid

    # Linear interpolation between the two bracketing months for a smoother
    # fractional-year estimate.
    balance_lo, balance_hi = balance_fn(lo), balance_fn(hi)
    frac = 0.0 if balance_hi == balance_lo else (target - balance_lo) / (balance_hi - balance_lo)
    return (lo + frac) / 12


# ---------------------------------------------------------------------------
# Visualization
# ---------------------------------------------------------------------------

def build_comparison_figure(result: RaiseComparisonResult):
    """Build (but do not display) a matplotlib Figure comparing the three
    scenarios' net worth over time, with an optional FIRE target line.

    Returns the Figure, so callers can either display it (CLI, via
    `plot_scenarios`) or save it to a buffer/file.

    Requires matplotlib (imported lazily so the rest of the module has no
    hard dependency on it).
    """
    import matplotlib.pyplot as plt

    style = {
        "current_path": "#475569",      # slate -- nothing changes
        "raise_uninvested": "#d97706",  # amber -- idle cash
        "raise_invested": "#16a34a",    # green -- growth
    }

    fig, ax = plt.subplots(figsize=(10, 6))

    finals = []
    for scenario in result.scenarios:
        color = style.get(scenario.key, "#2563eb")
        years = [y for y, _ in scenario.net_worth_by_year]
        values = [v for _, v in scenario.net_worth_by_year]
        ax.plot(years, values, color=color, linewidth=2, label=scenario.label)

        final_year, final_value = scenario.net_worth_by_year[-1]
        ax.scatter([final_year], [final_value], color=color, zorder=5, s=20)
        finals.append({"color": color, "x": final_year, "value": final_value})

        if scenario.years_to_target is not None and scenario.years_to_target <= result.horizon_years:
            ax.scatter([scenario.years_to_target], [result.fire_target], color=color, zorder=5)
            ax.annotate(
                f"{scenario.years_to_target:.1f}y",
                xy=(scenario.years_to_target, result.fire_target),
                xytext=(8, 8),
                textcoords="offset points",
                fontsize=9,
                color=color,
            )

    if result.fire_target is not None:
        ax.axhline(
            result.fire_target,
            color="red",
            linestyle="--",
            linewidth=1.5,
            label=f"FIRE target: {result.fire_target:,.0f}",
        )

    # Label the final net worth at the end of the horizon, so scenarios can
    # be compared on "how much" at a fixed point in time, not just on "how
    # soon" to a target. If two or more scenarios end up close together,
    # stack the labels vertically rather than letting them overlap.
    y_min, y_max = ax.get_ylim()
    min_gap = (y_max - y_min) * 0.045
    finals.sort(key=lambda d: d["value"])
    stacked_y: list[float] = []
    for d in finals:
        y = d["value"]
        if stacked_y and y - stacked_y[-1] < min_gap:
            y = stacked_y[-1] + min_gap
        stacked_y.append(y)
        d["label_y"] = y

    label_x = result.horizon_years * 1.03
    for d in finals:
        needs_leader = abs(d["label_y"] - d["value"]) > min_gap * 0.5
        ax.annotate(
            f"{d['value']:,.0f}",
            xy=(d["x"], d["value"]),
            xytext=(label_x, d["label_y"]),
            textcoords="data",
            fontsize=9,
            color=d["color"],
            fontweight="bold",
            va="center",
            arrowprops=dict(arrowstyle="-", color=d["color"], alpha=0.4, lw=0.8) if needs_leader else None,
        )

    # Extra room on the right so the final-value labels aren't clipped.
    ax.set_xlim(-0.5, result.horizon_years * 1.3)

    ax.set_title(f"Net Worth: Impact of a Raise (after {result.horizon_years} years)")
    ax.set_xlabel("Years from now")
    ax.set_ylabel("Net worth")
    ax.legend(loc="lower right", fontsize=9)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return fig


def plot_scenarios(result: RaiseComparisonResult) -> None:
    """Open a window displaying the chart built by `build_comparison_figure`.
    Used by the CLI. Requires matplotlib; see `build_comparison_figure`."""
    try:
        fig = build_comparison_figure(result)
    except ImportError:
        print(
            "\n(Skipping chart: matplotlib is not installed. "
            "Install it with 'pip install matplotlib' to see the graph.)"
        )
        return

    import matplotlib.pyplot as plt
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


def _prompt_float_optional(label: str, min_value: float | None = None) -> float | None:
    """Ask the user for a number, where pressing Enter with no input means
    'skip' (returns None) rather than falling back to a default."""
    while True:
        raw = input(f"{label}: ").strip().replace(",", ".")
        if raw == "":
            return None

        try:
            value = float(raw)
        except ValueError:
            print("  Please enter a valid number, or press Enter to skip.")
            continue

        if min_value is not None and value < min_value:
            print(f"  Value must be at least {min_value}.")
            continue

        return value


def run_cli() -> None:
    print("=" * 60)
    print("Raise Calculator - Impact of a Pay Raise on Your Net Worth")
    print("=" * 60)
    print(
        "Enter all amounts as NET (take-home) figures, in the same "
        "currency, in today's money (real terms).\n"
    )

    current_monthly_savings = _prompt_float(
        "Current monthly savings (amount invested each month)", min_value=0
    )
    raise_amount = _prompt_float(
        "Net monthly raise amount", min_value=0.01
    )
    current_net_worth = _prompt_float(
        "Current net worth / invested assets", default=0.0, min_value=0
    )

    print(
        "\nOptionally, compare these scenarios against a FIRE target. "
        "Press Enter to skip this entirely.\n"
    )
    annual_expenses = _prompt_float_optional(
        "Annual expenses in retirement (today's money)", min_value=0.01
    )
    withdrawal_rate_pct = DEFAULT_WITHDRAWAL_RATE_PCT
    if annual_expenses is not None:
        withdrawal_rate_pct = _prompt_float(
            f"Safe withdrawal rate (%) [recommended range "
            f"{WITHDRAWAL_RATE_MIN_PCT}-{WITHDRAWAL_RATE_MAX_PCT}]",
            default=DEFAULT_WITHDRAWAL_RATE_PCT,
            min_value=0.5,
            max_value=10,
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
    projection_years = int(_prompt_float(
        "Chart horizon in years (extended automatically if needed to reach "
        "a FIRE target)",
        default=DEFAULT_PROJECTION_YEARS,
        min_value=1,
        max_value=80,
    ))

    inputs = RaiseInputs(
        current_monthly_savings=current_monthly_savings,
        raise_amount=raise_amount,
        current_net_worth=current_net_worth,
        nominal_return_pct=nominal_return_pct,
        inflation_pct=inflation_pct,
        projection_years=projection_years,
        annual_expenses=annual_expenses,
        withdrawal_rate_pct=withdrawal_rate_pct,
    )

    try:
        result = calculate_raise_scenarios(inputs)
    except ValueError as exc:
        print(f"\nError: {exc}")
        return

    print("\n" + "-" * 60)
    print("RESULTS")
    print("-" * 60)
    print(f"Real return on invested money: {result.real_return_pct:.2f}%")
    print(f"Real return on idle cash:      {result.cash_real_return_pct:.2f}%")
    if result.fire_target is not None:
        print(f"FIRE target (target net worth): {result.fire_target:,.2f}")
    print()

    for scenario in result.scenarios:
        print(f"{scenario.label}:")
        print(f"  Invested monthly:     {scenario.invested_monthly:,.2f}")
        if scenario.cash_monthly:
            print(f"  Kept as cash monthly: {scenario.cash_monthly:,.2f}")
            print(
                "  (This cash earns no investment return, and loses "
                "purchasing power to inflation over time.)"
            )

        if scenario.years_to_target is not None:
            years_part = int(scenario.years_to_target)
            months_part = round((scenario.years_to_target - years_part) * 12)
            print(f"  Time to FIRE target:  {years_part}y {months_part}m")
        else:
            final_year, final_value = scenario.net_worth_by_year[-1]
            print(f"  Net worth after {final_year} years: {final_value:,.2f}")
        print()

    if result.fire_target is not None:
        by_key = {s.key: s for s in result.scenarios}
        current = by_key["current_path"]
        uninvested = by_key["raise_uninvested"]
        invested = by_key["raise_invested"]

        def _print_diff(label: str, slower, faster) -> None:
            if slower.years_to_target is None or faster.years_to_target is None:
                return
            diff_years = slower.years_to_target - faster.years_to_target
            if diff_years > 0.05:
                years_part = int(diff_years)
                months_part = round((diff_years - years_part) * 12)
                print(f"{label}: {years_part}y {months_part}m sooner.")

        _print_diff("Investing the raise vs. the current path", current, invested)
        _print_diff("Investing the raise vs. keeping it as cash", uninvested, invested)
        print()

    plot_scenarios(result)


if __name__ == "__main__":
    run_cli()
