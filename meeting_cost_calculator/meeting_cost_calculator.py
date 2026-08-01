"""
meeting_cost_calculator.py -- core calculation logic (no UI dependencies).

The basic idea behind every "meeting cost calculator" online is simple
and well established: multiply headcount by average hourly pay by
duration. That part is just arithmetic.

The more interesting -- and usually ignored -- question is: does a
meeting's *duration* itself depend on how many people are in it? Two
well-known findings from organisational research say yes:

- Brooks's Law (Fred Brooks, "The Mythical Man-Month", 1975): the
  number of communication *channels* between people in a group grows
  as n(n-1)/2 -- quadratically, not linearly. More people means more
  pairwise cross-talk, tangents, and re-explaining.
- Bain & Company's decision-effectiveness research (widely cited,
  e.g. Rogers & Blenko, "Who Has the D?", Harvard Business Review,
  2006): each person added to a decision-making group beyond about 7
  reduces decision quality/speed by roughly 10%, and effectiveness
  collapses well before 20 people. This is part of why Amazon's
  famous "two-pizza rule" caps team/meeting size at 6-10 people.

This module turns that qualitative finding ("bigger meetings are
disproportionately less efficient") into a simple, adjustable,
*honestly labelled* model rather than a fake precise formula:

    total duration = fixed agenda time
                    + (attendees x average turn length x overhead factor)

    overhead factor = 1 + growth_rate x (attendees - 1)

`growth_rate` is a slider the user controls -- it is a heuristic
knob, not a measured constant. The point isn't the exact number; it's
making the well-established "bigger groups are less efficient, not
just more expensive" effect visible and adjustable, instead of the
usual meeting-cost calculator that (wrongly) assumes duration is
independent of headcount.

No cross-tool dependencies -- fully self-contained, like every other
tool in this repository.
"""

from __future__ import annotations

from dataclasses import dataclass, field

DEFAULT_CORE_MINUTES = 15.0
DEFAULT_TURN_MINUTES = 2.0
DEFAULT_OVERHEAD_GROWTH_PCT = 5.0     # % longer each person's average turn
                                       # gets per additional attendee
DEFAULT_BENEFITS_MULTIPLIER = 1.3     # "fully loaded" cost incl. benefits,
                                       # payroll tax, etc. -- a common
                                       # finance/HR rule of thumb (1.25-1.4x)
DEFAULT_WORKING_HOURS_PER_YEAR = 2080  # 52 weeks x 40 hours
DEFAULT_ATTENDEES = 6
DEFAULT_CURVE_MAX_ATTENDEES = 15
MAX_CURVE_ATTENDEES_CAP = 100  # sanity ceiling, even if a user types something huge

RECURRENCE_PER_YEAR = {
    "none": 0,
    "daily": 250,      # ~working days/year
    "weekly": 52,
    "biweekly": 26,
    "monthly": 12,
}


@dataclass
class MeetingInputs:
    attendees: int
    avg_annual_salary: float
    core_minutes: float = DEFAULT_CORE_MINUTES
    round_robin: bool = True
    turn_minutes: float = DEFAULT_TURN_MINUTES
    overhead_growth_pct: float = DEFAULT_OVERHEAD_GROWTH_PCT
    benefits_multiplier: float = DEFAULT_BENEFITS_MULTIPLIER
    working_hours_per_year: float = DEFAULT_WORKING_HOURS_PER_YEAR
    recurrence: str = "none"
    curve_max_attendees: int = DEFAULT_CURVE_MAX_ATTENDEES
    hourly_cost_override: float | None = None  # if set, used directly as the
                                                 # fully-loaded hourly cost,
                                                 # bypassing the salary/benefits/
                                                 # working-hours derivation below


@dataclass
class CurvePoint:
    attendees: int
    minutes: float
    cost: float


@dataclass
class MeetingResult:
    hourly_cost_per_person: float
    core_minutes: float
    discussion_minutes: float
    total_minutes: float
    core_cost: float
    discussion_cost: float
    total_cost: float
    overhead_factor: float          # multiplier applied to each person's turn
    naive_cost: float               # cost if duration ignored group-size effect
                                     # (i.e. discussion time stayed at n x base turn,
                                     # no overhead growth) -- the "hidden cost" delta
    per_occurrence_cost: float
    occurrences_per_year: int
    annual_cost: float | None       # None if recurrence == "none"
    curve: list[CurvePoint] = field(default_factory=list)


def hourly_cost(annual_salary: float, benefits_multiplier: float, working_hours_per_year: float) -> float:
    """Fully-loaded hourly cost of one person: salary grossed up for
    benefits/payroll overhead, spread across working hours in a year."""
    if working_hours_per_year <= 0:
        return 0.0
    return (annual_salary * benefits_multiplier) / working_hours_per_year


def meeting_duration_minutes(
    attendees: int,
    core_minutes: float,
    round_robin: bool,
    turn_minutes: float,
    overhead_growth_pct: float,
) -> tuple[float, float, float]:
    """Returns (total_minutes, discussion_minutes, overhead_factor)."""
    if not round_robin or attendees <= 0:
        return core_minutes, 0.0, 1.0
    overhead_factor = 1 + (overhead_growth_pct / 100) * (attendees - 1)
    discussion_minutes = attendees * turn_minutes * overhead_factor
    return core_minutes + discussion_minutes, discussion_minutes, overhead_factor


def calculate_meeting(inputs: MeetingInputs) -> MeetingResult:
    if inputs.hourly_cost_override is not None:
        rate = inputs.hourly_cost_override
    else:
        rate = hourly_cost(inputs.avg_annual_salary, inputs.benefits_multiplier, inputs.working_hours_per_year)

    total_minutes, discussion_minutes, overhead_factor = meeting_duration_minutes(
        inputs.attendees, inputs.core_minutes, inputs.round_robin,
        inputs.turn_minutes, inputs.overhead_growth_pct,
    )
    core_cost = inputs.attendees * rate * (inputs.core_minutes / 60)
    discussion_cost = inputs.attendees * rate * (discussion_minutes / 60)
    total_cost = core_cost + discussion_cost

    # "Naive" comparison: what the meeting would cost if extra attendees
    # didn't make each person's turn take longer (overhead_factor pinned
    # to 1) -- isolates the "hidden cost" of group-size inefficiency,
    # separate from the (unavoidable) cost of just inviting more people.
    if inputs.round_robin and inputs.attendees > 0:
        naive_discussion_minutes = inputs.attendees * inputs.turn_minutes
    else:
        naive_discussion_minutes = 0.0
    naive_total_minutes = inputs.core_minutes + naive_discussion_minutes
    naive_cost = inputs.attendees * rate * (naive_total_minutes / 60)

    occurrences_per_year = RECURRENCE_PER_YEAR.get(inputs.recurrence, 0)
    annual_cost = total_cost * occurrences_per_year if occurrences_per_year else None

    curve = []
    curve_max = max(1, min(inputs.curve_max_attendees, MAX_CURVE_ATTENDEES_CAP))
    for n in range(1, curve_max + 1):
        m, _, _ = meeting_duration_minutes(
            n, inputs.core_minutes, inputs.round_robin,
            inputs.turn_minutes, inputs.overhead_growth_pct,
        )
        c = n * rate * (m / 60)
        curve.append(CurvePoint(n, m, c))

    return MeetingResult(
        hourly_cost_per_person=rate,
        core_minutes=inputs.core_minutes,
        discussion_minutes=discussion_minutes,
        total_minutes=total_minutes,
        core_cost=core_cost,
        discussion_cost=discussion_cost,
        total_cost=total_cost,
        overhead_factor=overhead_factor,
        naive_cost=naive_cost,
        per_occurrence_cost=total_cost,
        occurrences_per_year=occurrences_per_year,
        annual_cost=annual_cost,
        curve=curve,
    )


def build_curve_figure(result: MeetingResult, inputs: MeetingInputs):
    """Matplotlib chart: attendees (x) vs. cost (y), used by the CLI."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    xs = [p.attendees for p in result.curve]
    ys = [p.cost for p in result.curve]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(xs, ys, color="#2F6F52", linewidth=2.5)
    ax.axvline(inputs.attendees, color="#B3402F", linestyle="--", linewidth=1, alpha=0.7)
    ax.scatter([inputs.attendees], [result.total_cost], color="#B3402F", zorder=5, s=60)
    ax.set_xlabel("Attendees")
    ax.set_ylabel("Meeting cost")
    ax.set_title("Meeting cost vs. headcount")
    ax.grid(True, linestyle="--", alpha=0.4)
    fig.tight_layout()
    return fig


def _fmt_minutes(m: float) -> str:
    h, mm = divmod(round(m), 60)
    return f"{h}h {mm}m" if h else f"{mm}m"


def _run_cli() -> None:
    print("Meeting Cost Calculator")
    print("=" * 60)

    inputs = MeetingInputs(
        attendees=DEFAULT_ATTENDEES,
        avg_annual_salary=90000,
        recurrence="weekly",
    )
    result = calculate_meeting(inputs)

    print(f"Attendees: {inputs.attendees}  |  Avg salary: {inputs.avg_annual_salary:,.0f}/yr  |  "
          f"Hourly cost/person: {result.hourly_cost_per_person:,.2f}\n")
    print(f"Core (fixed) time:        {_fmt_minutes(result.core_minutes)}")
    print(f"Discussion time:          {_fmt_minutes(result.discussion_minutes)} "
          f"(overhead factor {result.overhead_factor:.2f}x)")
    print(f"Total duration:           {_fmt_minutes(result.total_minutes)}\n")
    print(f"Total cost this meeting:  {result.total_cost:,.0f}")
    print(f"  ...vs. if group size didn't slow discussion down: {result.naive_cost:,.0f}")
    print(f"  ...hidden cost of group-size inefficiency: {result.total_cost - result.naive_cost:,.0f}")
    if result.annual_cost:
        print(f"\nRecurs {inputs.recurrence} ({result.occurrences_per_year}x/year): "
              f"{result.annual_cost:,.0f}/year")

    try:
        fig = build_curve_figure(result, inputs)
        fig.savefig("meeting_cost_curve.png", dpi=150)
        print("\nChart saved to meeting_cost_curve.png")
    except ImportError:
        print("\n(matplotlib not installed -- skipping chart)")


if __name__ == "__main__":
    _run_cli()
