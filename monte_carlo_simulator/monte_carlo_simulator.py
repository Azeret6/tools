"""
monte_carlo_simulator.py -- core calculation logic (no UI dependencies).

Every other calculator in this repo shows you ONE version of the future:
`fire_calculator` assumes one constant return, `historical_backtest`
replays the *actual* historical sequences that really happened. Neither
answers the question "given how volatile markets really are, what's the
realistic SPREAD of outcomes I should expect?"

That's what Monte Carlo simulation is for: generate thousands of
randomly generated possible futures (each year's return drawn from a
distribution, not fixed), and look at the resulting spread of outcomes
-- not a single number, but a probability band.

This is NOT the same thing as `historical_backtest`, which is worth
being explicit about:

- historical_backtest: replays the ~96 sequences that *actually
  happened*, in the order they actually happened. Deterministic,
  grounded in real history, but limited to the handful of sequences
  history happened to produce.
- monte_carlo_simulator (this tool): generates thousands of
  *synthetic* sequences by drawing each year's return at random from a
  distribution (mean + standard deviation you control). Not grounded in
  any specific real history, but gives a much smoother, larger-sample
  picture of "how much does luck/timing matter, statistically speaking".

The two are complementary, not interchangeable.

No cross-tool dependencies -- fully self-contained, like every other
tool in this repository.
"""

from __future__ import annotations

import random
import statistics
from dataclasses import dataclass, field

DEFAULT_WITHDRAWAL_RATE_PCT = 4.0
WITHDRAWAL_RATE_MIN_PCT = 3.0
WITHDRAWAL_RATE_MAX_PCT = 5.0
DEFAULT_HORIZON_YEARS = 30
MAX_HORIZON_YEARS = 50

# Defaults roughly match the *geometric* real-return mean and annual
# volatility of US stock market history (see historical_backtest.py's
# data for the same broad picture) -- reasonable starting assumptions,
# not a guarantee of future results.
DEFAULT_MEAN_RETURN_PCT = 6.5
DEFAULT_RETURN_STD_DEV_PCT = 18.0

DEFAULT_NUM_SIMULATIONS = 1000
MAX_NUM_SIMULATIONS = 5000

PERCENTILES = (10, 25, 50, 75, 90)


@dataclass
class SimulationInputs:
    savings_rate_pct: float          # % of income saved -- income normalised
                                      # to 1 unit, same trick as
                                      # savings_rate_explorer / historical_backtest.
    withdrawal_rate_pct: float = DEFAULT_WITHDRAWAL_RATE_PCT
    horizon_years: int = DEFAULT_HORIZON_YEARS
    mean_return_pct: float = DEFAULT_MEAN_RETURN_PCT       # annual real return, mean
    return_std_dev_pct: float = DEFAULT_RETURN_STD_DEV_PCT  # annual real return, std dev
    num_simulations: int = DEFAULT_NUM_SIMULATIONS
    random_seed: int | None = None   # set for reproducible results (e.g. tests)


@dataclass
class SimulationResult:
    target: float
    monthly_contribution: float
    success_rate_pct: float
    median_years: float | None                  # among simulations that succeeded
    percentile_years: dict[int, float | None]    # percentile -> years to FIRE (successes only)
    # Fan-chart data: for each year 0..horizon, the balance at each requested
    # percentile across ALL simulations (successes and failures alike).
    percentile_paths: dict[int, list[float]] = field(default_factory=dict)
    num_simulations: int = 0


def _simulate_one_path(
    monthly_rate_sampler,
    monthly_contribution: float,
    target: float,
    horizon_months: int,
) -> tuple[float | None, list[float]]:
    """Runs one random simulation. Returns (months_to_fire_or_None,
    year_end_balances) -- year_end_balances always has horizon_years+1
    entries (including the starting balance at year 0), regardless of
    whether/when the target was reached, so every path contributes a
    full-length row to the percentile fan chart."""
    balance = 0.0
    months_to_fire = None
    year_end_balances = [0.0]

    month = 0
    while month < horizon_months:
        annual_rate = monthly_rate_sampler()
        monthly_rate = (1 + annual_rate) ** (1 / 12) - 1
        for _ in range(12):
            if month >= horizon_months:
                break
            balance = balance * (1 + monthly_rate) + monthly_contribution
            month += 1
            if months_to_fire is None and balance >= target:
                months_to_fire = float(month)
        year_end_balances.append(balance)

    return months_to_fire, year_end_balances


def run_simulation(inputs: SimulationInputs) -> SimulationResult:
    rng = random.Random(inputs.random_seed)

    rate = inputs.savings_rate_pct / 100
    annual_expenses = 1 - rate
    target = annual_expenses / (inputs.withdrawal_rate_pct / 100)
    monthly_contribution = rate / 12

    mean = inputs.mean_return_pct / 100
    std_dev = max(inputs.return_std_dev_pct, 0) / 100

    def sample_annual_return() -> float:
        return rng.gauss(mean, std_dev)

    num_sims = max(1, min(inputs.num_simulations, MAX_NUM_SIMULATIONS))
    horizon_months = inputs.horizon_years * 12

    all_years_to_fire: list[float] = []
    all_paths: list[list[float]] = []

    for _ in range(num_sims):
        months_to_fire, path = _simulate_one_path(
            sample_annual_return, monthly_contribution, target, horizon_months
        )
        all_paths.append(path)
        if months_to_fire is not None:
            all_years_to_fire.append(months_to_fire / 12)

    success_rate_pct = 100 * len(all_years_to_fire) / num_sims if num_sims else 0.0
    median_years = statistics.median(all_years_to_fire) if all_years_to_fire else None

    def _percentile(values: list[float], pct: float) -> float:
        if not values:
            return 0.0
        s = sorted(values)
        k = (len(s) - 1) * (pct / 100)
        f, c = int(k), min(int(k) + 1, len(s) - 1)
        if f == c:
            return s[f]
        return s[f] + (s[c] - s[f]) * (k - f)

    percentile_years = {}
    for p in PERCENTILES:
        percentile_years[p] = _percentile(all_years_to_fire, p) if all_years_to_fire else None

    # Fan chart: percentile balance at each year mark, across ALL paths
    # (not just successes) -- this is what shows the "cone of uncertainty"
    # widening over time.
    percentile_paths: dict[int, list[float]] = {p: [] for p in PERCENTILES}
    num_year_marks = inputs.horizon_years + 1
    for year_idx in range(num_year_marks):
        values_at_year = [path[year_idx] for path in all_paths]
        for p in PERCENTILES:
            percentile_paths[p].append(_percentile(values_at_year, p))

    return SimulationResult(
        target=target,
        monthly_contribution=monthly_contribution,
        success_rate_pct=success_rate_pct,
        median_years=median_years,
        percentile_years=percentile_years,
        percentile_paths=percentile_paths,
        num_simulations=num_sims,
    )


def build_fan_chart_figure(result: SimulationResult, inputs: SimulationInputs):
    """Matplotlib fan chart: shaded percentile band + median line, used
    by the CLI."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    years = list(range(inputs.horizon_years + 1))
    p10 = result.percentile_paths[10]
    p25 = result.percentile_paths[25]
    p50 = result.percentile_paths[50]
    p75 = result.percentile_paths[75]
    p90 = result.percentile_paths[90]

    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.fill_between(years, p10, p90, color="#2F6F52", alpha=0.12, label="10th-90th percentile")
    ax.fill_between(years, p25, p75, color="#2F6F52", alpha=0.25, label="25th-75th percentile")
    ax.plot(years, p50, color="#1F5A40", linewidth=2.5, label="Median")
    ax.axhline(result.target, color="#B3402F", linestyle="--", linewidth=1.5, label="FIRE target")
    ax.set_xlabel("Years")
    ax.set_ylabel("Balance")
    ax.set_title(
        f"Monte Carlo -- {inputs.savings_rate_pct:.0f}% savings rate, "
        f"{inputs.num_simulations} simulations, "
        f"{result.success_rate_pct:.0f}% reached FIRE"
    )
    ax.legend(fontsize=8)
    ax.grid(True, linestyle="--", alpha=0.3)
    fig.tight_layout()
    return fig


def _run_cli() -> None:
    print("Monte Carlo FIRE Simulator")
    print("=" * 60)

    inputs = SimulationInputs(savings_rate_pct=25, withdrawal_rate_pct=4.0, horizon_years=30)
    result = run_simulation(inputs)

    print(f"Savings rate: {inputs.savings_rate_pct:.0f}%  |  "
          f"Withdrawal rate: {inputs.withdrawal_rate_pct:.1f}%  |  "
          f"Horizon: {inputs.horizon_years}y  |  "
          f"Assumed return: {inputs.mean_return_pct:.1f}% +/- {inputs.return_std_dev_pct:.1f}%\n")
    print(f"Simulations run: {result.num_simulations}")
    print(f"Reached FIRE within horizon: {result.success_rate_pct:.1f}%\n")

    if result.median_years is not None:
        print("Years to FIRE, by percentile (among simulations that succeeded):")
        for p in PERCENTILES:
            val = result.percentile_years[p]
            label = f"{val:.1f}y" if val is not None else "n/a"
            print(f"  {p:>2}th percentile: {label}")
    else:
        print("No simulations reached the target within the horizon.")

    try:
        fig = build_fan_chart_figure(result, inputs)
        fig.savefig("monte_carlo_fan_chart.png", dpi=150)
        print("\nChart saved to monte_carlo_fan_chart.png")
    except ImportError:
        print("\n(matplotlib not installed -- skipping chart)")


if __name__ == "__main__":
    _run_cli()
