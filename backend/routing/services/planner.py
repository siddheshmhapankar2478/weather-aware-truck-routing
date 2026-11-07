"""Builds a full trip plan: routes → checkpoints → weather → risk → recommendation."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .geo import simplify
from .heatmap import corridor_grid
from .geocoding import resolve_place
from .recommendation import RouteScore, explain, rank_routes
from .risk import RiskLevel, assess
from .routing import Route, find_route_options
from .sampling import RouteTrack, sample_checkpoints
from .weather import FORECAST_HORIZON, fetch_hourly, snap

ALLOWED_INTERVALS = (10, 25, 50)
MAX_LOAD_LB = 120_000
MAX_DEPARTURE_AHEAD = timedelta(days=7)
GEOMETRY_TOLERANCE_DEG = 0.0005  # ~50 m, keeps payloads small


class PlanError(ValueError):
    """The request can't be planned (bad input or out-of-range dates)."""


def parse_departure(raw) -> datetime:
    try:
        departure = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError as exc:
        raise PlanError("Departure must be an ISO 8601 date/time.") from exc
    if departure.tzinfo is None:
        departure = departure.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    if departure < now - timedelta(hours=1):
        raise PlanError("Departure time is in the past.")
    if departure > now + MAX_DEPARTURE_AHEAD:
        raise PlanError("Departure must be within the next 7 days (forecast range).")
    return departure


def parse_load(raw) -> float:
    try:
        load_lb = float(raw)
    except (TypeError, ValueError) as exc:
        raise PlanError("Load weight must be a number of pounds.") from exc
    if not 0 <= load_lb <= MAX_LOAD_LB:
        raise PlanError(f"Load weight must be between 0 and {MAX_LOAD_LB:,} lb.")
    return load_lb


@dataclass
class PlanRequest:
    origin: object
    destination: object
    departure: datetime
    load_lb: float
    interval_mi: int

    @classmethod
    def from_json(cls, body: dict) -> "PlanRequest":
        if not body.get("origin") or not body.get("destination"):
            raise PlanError("Origin and destination are required.")

        departure = parse_departure(body.get("departure"))
        load_lb = parse_load(body.get("load_lb"))

        try:
            interval = int(body.get("interval_mi", 25))
        except (TypeError, ValueError) as exc:
            raise PlanError("Sampling interval must be 10, 25 or 50 miles.") from exc
        if interval not in ALLOWED_INTERVALS:
            raise PlanError("Sampling interval must be 10, 25 or 50 miles.")

        return cls(body["origin"], body["destination"], departure.astimezone(timezone.utc), load_lb, interval)


def _round_coords(coords):
    return [[round(lat, 5), round(lon, 5)] for lat, lon in coords]


def _risk_segments(track: RouteTrack, checkpoints, levels: list[RiskLevel]) -> list[dict]:
    """Route geometry split into runs of equal risk, for colouring the line."""
    segments = []
    run_start = 0
    for k in range(1, len(checkpoints) + 1):
        if k == len(checkpoints) or levels[k] != levels[run_start]:
            coords = track.slice(checkpoints[run_start].start_mile, checkpoints[k - 1].end_mile)
            segments.append(
                {"level": levels[run_start].key, "coords": _round_coords(simplify(coords, GEOMETRY_TOLERANCE_DEG))}
            )
            run_start = k
    return segments


def _evaluate_route(route_id: str, route: Route, track: RouteTrack, checkpoints, series, request: PlanRequest):
    miles_by_level = {level: 0.0 for level in RiskLevel}
    levels = []
    checkpoint_out = []
    for cp in checkpoints:
        eta = request.departure + timedelta(seconds=cp.elapsed_s)
        weather = series[snap((cp.lat, cp.lon))].at(eta)
        result = assess(weather.wind_mph, weather.rain_in_hr, weather.snow_in_hr, request.load_lb)
        miles_by_level[result.level] += cp.covered_mi
        levels.append(result.level)
        checkpoint_out.append(
            {
                "mile": round(cp.mile, 1),
                "lat": round(cp.lat, 5),
                "lon": round(cp.lon, 5),
                "eta": eta.isoformat(),
                "elapsed_s": round(cp.elapsed_s),
                "level": result.level.key,
                "factors": {"wind": result.wind.key, "rain": result.rain.key, "snow": result.snow.key},
                "reasons": result.reasons,
                "weather": weather.to_dict(),
            }
        )

    total = track.total_mi or 1.0
    avg_risk = sum(level * miles for level, miles in miles_by_level.items()) / total
    score = RouteScore(
        route_id=route_id,
        no_travel_mi=miles_by_level[RiskLevel.NO_TRAVEL],
        severe_mi=miles_by_level[RiskLevel.SEVERE],
        high_mi=miles_by_level[RiskLevel.HIGH],
        avg_risk=avg_risk,
        duration_s=route.duration_s,
    )
    payload = {
        "id": route_id,
        "summary": route.summary,
        "distance_mi": round(route.distance_mi, 1),
        "duration_s": round(route.duration_s),
        "arrival": (request.departure + timedelta(seconds=route.duration_s)).isoformat(),
        "risk": {
            "miles": {level.key: round(miles, 1) for level, miles in miles_by_level.items()},
            "average": round(avg_risk, 3),
            "max_level": max(levels).key,
        },
        "geometry": _round_coords(simplify(route.coords, GEOMETRY_TOLERANCE_DEG)),
        "segments": _risk_segments(track, checkpoints, levels),
        "checkpoints": checkpoint_out,
    }
    return score, payload


def build_plan(request: PlanRequest) -> dict:
    origin = resolve_place(request.origin)
    destination = resolve_place(request.destination)
    routes = find_route_options((origin.lat, origin.lon), (destination.lat, destination.lon))

    longest = max(r.duration_s for r in routes)
    trip_end = request.departure + timedelta(seconds=longest)
    if trip_end > datetime.now(timezone.utc) + FORECAST_HORIZON:
        raise PlanError("This trip ends beyond the 15-day forecast window. Choose an earlier departure.")

    tracks = [RouteTrack(r) for r in routes]
    sampled = [sample_checkpoints(t, request.interval_mi) for t in tracks]
    points = [(cp.lat, cp.lon) for cps in sampled for cp in cps]
    series = fetch_hourly(points, request.departure, trip_end)

    scores, payloads = [], {}
    for k, (route, track, checkpoints) in enumerate(zip(routes, tracks, sampled)):
        route_id = chr(ord("A") + k)
        score, payload = _evaluate_route(route_id, route, track, checkpoints, series, request)
        scores.append(score)
        payloads[route_id] = payload

    ranked = rank_routes(scores)
    best = ranked[0]
    for position, score in enumerate(ranked, start=1):
        payloads[score.route_id]["rank"] = position

    warning = None
    if best.no_travel_mi > 0:
        warning = "Every route crosses No Travel conditions. Consider delaying departure."
    elif best.severe_mi > 0:
        warning = "Every route crosses Severe conditions. Drive with extra caution or delay departure."

    return {
        "origin": origin.to_dict(),
        "destination": destination.to_dict(),
        "departure": request.departure.isoformat(),
        "load_lb": request.load_lb,
        "interval_mi": request.interval_mi,
        "recommendation": {
            "route_id": best.route_id,
            "reason": explain(best, ranked[1] if len(ranked) > 1 else None),
            "warning": warning,
        },
        "routes": [payloads[chr(ord("A") + k)] for k in range(len(routes))],
        "heatmap_grid": dict(zip(("points", "spacing_mi"), corridor_grid(routes))),
    }
