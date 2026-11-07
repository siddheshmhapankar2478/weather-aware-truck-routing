"""Pick the best route.

Routes are compared criterion by criterion, in the brief's order:
  1. fewest Severe miles   2. fewest High miles
  3. lowest average risk   4. shortest travel time
No Travel miles are checked before all of these, since they are worse than
Severe. Small differences (within the tolerance) count as a tie so that, for
example, 0.01 of average risk doesn't outweigh three hours of driving.
"""

from dataclasses import dataclass
from functools import cmp_to_key


@dataclass(frozen=True)
class Criterion:
    field: str
    tolerance: float
    label: str


CRITERIA = (
    Criterion("no_travel_mi", 0.5, "No Travel miles"),
    Criterion("severe_mi", 0.5, "Severe miles"),
    Criterion("high_mi", 0.5, "High-risk miles"),
    Criterion("avg_risk", 0.05, "average risk"),
    Criterion("duration_s", 60, "travel time"),
)


@dataclass
class RouteScore:
    route_id: str
    no_travel_mi: float
    severe_mi: float
    high_mi: float
    avg_risk: float  # mile-weighted, 0 (Low) .. 4 (No Travel)
    duration_s: float


def _deciding_criterion(a: RouteScore, b: RouteScore) -> tuple[Criterion | None, float]:
    for criterion in CRITERIA:
        diff = getattr(a, criterion.field) - getattr(b, criterion.field)
        if abs(diff) > criterion.tolerance:
            return criterion, diff
    return None, 0.0


def _compare(a: RouteScore, b: RouteScore) -> int:
    _, diff = _deciding_criterion(a, b)
    return (diff > 0) - (diff < 0)


def rank_routes(scores: list[RouteScore]) -> list[RouteScore]:
    return sorted(scores, key=cmp_to_key(_compare))


def _format(criterion: Criterion, value: float) -> str:
    if criterion.field == "duration_s":
        hours, minutes = divmod(round(value / 60), 60)
        return f"{hours}h {minutes:02d}m"
    if criterion.field == "avg_risk":
        return f"{value:.2f}"
    return f"{value:.0f} mi"


def explain(best: RouteScore, runner_up: RouteScore | None) -> str:
    if runner_up is None:
        return "Only one route was available."
    criterion, _ = _deciding_criterion(best, runner_up)
    if criterion is None:
        return f"Route {best.route_id} and Route {runner_up.route_id} are effectively tied on risk and time."
    ours = _format(criterion, getattr(best, criterion.field))
    theirs = _format(criterion, getattr(runner_up, criterion.field))
    if criterion.field == "duration_s":
        prefix = "Weather risk is similar, so the faster route wins"
        return f"{prefix}: {ours} vs {theirs} on Route {runner_up.route_id}."
    return f"Fewest {criterion.label}: {ours} vs {theirs} on Route {runner_up.route_id}."
