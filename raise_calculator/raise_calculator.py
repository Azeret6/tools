"""
Raise Calculator
=================

Models the long-term impact of a net pay raise on your investable net
worth, comparing three scenarios:

    1. Current path     -- no raise; savings stay the same.
    2. Raise spent       -- you get the raise, but it's absorbed into
                            lifestyle spending; savings stay the same as
                            scenario 1 (the two are mathematically
                            identical -- shown side by side to make the
                            cost of lifestyle inflation visible).
    3. Raise invested    -- the entire raise is added to monthly
                            savings/investments.

All amounts should be entered as NET (take-home) figures, in the same
currency, in today's money (real terms). Working in net, real terms
avoids having to model any country-specific tax system.

Optionally, you can provide a FIRE target (via annual expenses and a
withdrawal rate) to see how many years sooner -- if any -- investing the
raise gets you there. Leaving this out, the tool simply compares net
worth growth across the three scenarios over a fixed horizon.

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
    real_return = nominal_return - inflation
This is a simplified approximation (rather than the Fisher equation),
consistent with the rest of this repository.

After computing the result, this script opens a chart (via matplotlib)
comparing net worth growth across the three scenarios. Requires
matplotlib (`pip install matplotlib`); the core calculation itself has no
external dependencies.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

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


@dataclass
class RaiseInputs:
    """All user-provided inputs for the raise impact calculation."""

    current_monthly_savings: float     # Amount currently invested each month
    raise_amount: float                # Net monthly raise (take-home increase)
    current_net_worth: float = 0.0     # Starting balance, shared by all scenarios
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
    monthly_savings: float
    net_worth_by_year: list[tuple[int, float]]  # (year offset, net worth)
    years_to_target: float | None = None        # None if no target / unreachable


@dataclass
class RaiseComparisonResult:
    """Output of the full scenario comparison."""

    real_return_pct: float
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

    real_return_pct = inputs.nominal_return_pct - inputs.inflation_pct
    monthly_rate = (1 + real_return_pct / 100) ** (1 / 12) - 1

    target = _resolve_target(inputs)

    baseline_savings = inputs.current_monthly_savings
    invested_savings = inputs.current_monthly_savings + inputs.raise_amount

    baseline_years_to_target = (
        _years_to_reach_target(inputs.current_net_worth, baseline_savings, monthly_rate, target)
        if target is not None else None
    )
    invested_years_to_target = (
        _years_to_reach_target(inputs.current_net_worth, invested_savings, monthly_rate, target)
        if target is not None else None
    )

    horizon_years = _resolve_horizon(
        inputs.projection_years, baseline_years_to_target, invested_years_to_target
    )

    baseline_series = _project_net_worth(
        inputs.current_net_worth, baseline_savings, monthly_rate, horizon_years
    )
    invested_series = _project_net_worth(
        inputs.current_net_worth, invested_savings, monthly_rate, horizon_years
    )

    scenarios = [
        ScenarioResult(
            key="current_path",
            label="Current path (no raise)",
            monthly_savings=baseline_savings,
            net_worth_by_year=baseline_series,
            years_to_target=baseline_years_to_target,
        ),
        ScenarioResult(
            key="raise_spent",
            label="Raise spent (lifestyle inflation)",
            monthly_savings=baseline_savings,
            net_worth_by_year=baseline_series,
            years_to_target=baseline_years_to_target,
        ),
        ScenarioResult(
            key="raise_invested",
            label="Raise fully invested",
            monthly_savings=invested_savings,
            net_worth_by_year=invested_series,
            years_to_target=invested_years_to_target,
        ),
    ]

    return RaiseComparisonResult(
        real_return_pct=real_return_pct,
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
    return max(projection_years, min(math.ceil(needed) + 2, 80))


def _project_net_worth(
    starting_balance: float,
    monthly_contribution: float,
    monthly_rate: float,
    horizon_years: int,
) -> list[tuple[int, float]]:
    """Year-by-year projected net worth, from year 0 (today) to
    `horizon_years`, given a constant monthly contribution and a constant
    monthly rate of return (compounded monthly)."""
    return [
        (year, _balance_at_month(year * 12, starting_balance, monthly_contribution, monthly_rate))
        for year in range(horizon_years + 1)
    ]


def _balance_at_month(
    month: int,
    starting_balance: float,
    monthly_contribution: float,
    monthly_rate: float,
) -> float:
    """Projected balance after `month` months of compounding plus a fixed
    monthly contribution."""
    if abs(monthly_rate) < 1e-12:
        return starting_balance + monthly_contribution * month
    growth = (1 + monthly_rate) ** month
    return starting_balance * growth + monthly_contribution * ((growth - 1) / monthly_rate)


def _years_to_reach_target(
    starting_balance: float,
    monthly_contribution: float,
    monthly_rate: float,
    target: float,
) -> float | None:
    """Solve for the number of years needed to reach `target`, given a
    starting balance, a fixed monthly contribution, and a constant monthly
    rate of return (compounded monthly).

    Returns None if the target can never be reached (no growth and
    contributions are not enough -- or balance is shrinking).
    """
    if starting_balance >= target:
        return 0.0

    if abs(monthly_rate) < 1e-12:
        # No real growth: purely linear accumulation from contributions.
        if monthly_contribution <= 0:
            return None
        return (target - starting_balance) / monthly_contribution / 12

    # Closed-form solution for n in:
    # target = balance*(1+r)^n + contribution * (((1+r)^n - 1) / r)
    numerator = target * monthly_rate + monthly_contribution
    denominator = starting_balance * monthly_rate + monthly_contribution

    if denominator <= 0 or numerator <= 0:
        return None

    ratio = numerator / denominator
    if ratio <= 1:
        # Already there, or contributions/return are negative relative to target.
        return 0.0

    n_months = math.log(ratio) / math.log(1 + monthly_rate)
    return n_months / 12


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

    # Color/style per scenario. Scenarios 1 and 2 ("current path" / "raise
    # spent") share an identical trajectory by construction, so they're
    # drawn once below, with a combined legend label, rather than as two
    # overlapping lines.
    style = {
        "current_path": ("#475569", "-"),    # slate
        "raise_spent": ("#475569", "-"),
        "raise_invested": ("#16a34a", "-"),  # green
    }

    fig, ax = plt.subplots(figsize=(10, 6))

    plotted_series: set[int] = set()
    for scenario in result.scenarios:
        series_id = id(scenario.net_worth_by_year)
        if series_id in plotted_series:
            continue
        plotted_series.add(series_id)

        sharing_labels = [
            s.label for s in result.scenarios if id(s.net_worth_by_year) == series_id
        ]
        color, linestyle = style.get(scenario.key, ("#2563eb", "-"))

        years = [y for y, _ in scenario.net_worth_by_year]
        values = [v for _, v in scenario.net_worth_by_year]
        ax.plot(
            years, values,
            color=color, linestyle=linestyle, linewidth=2,
            label=" / ".join(sharing_labels),
        )

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

    ax.set_title("Net Worth: Impact of a Raise")
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
    print(f"Real (inflation-adjusted) return: {result.real_return_pct:.2f}%")
    if result.fire_target is not None:
        print(f"FIRE target (target net worth):   {result.fire_target:,.2f}")
    print()

    for scenario in result.scenarios:
        print(f"{scenario.label}:")
        print(f"  Monthly savings:      {scenario.monthly_savings:,.2f}")

        if scenario.key == "raise_spent":
            print(
                "  (Same trajectory as 'Current path' -- the raise is "
                "absorbed into spending, so it doesn't change your "
                "savings rate.)"
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
        baseline = result.scenarios[0]
        invested = result.scenarios[2]
        if baseline.years_to_target is not None and invested.years_to_target is not None:
            diff_years = baseline.years_to_target - invested.years_to_target
            if diff_years > 0.05:
                years_part = int(diff_years)
                months_part = round((diff_years - years_part) * 12)
                print(
                    f"Investing the raise gets you to your FIRE target "
                    f"{years_part}y {months_part}m sooner than the current path.\n"
                )

    plot_scenarios(result)


if __name__ == "__main__":
    run_cli()
