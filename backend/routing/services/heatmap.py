"""Weather heatmap along the trip corridor for the next 48 hours.

The corridor is a grid of points: samples along every route plus parallel
"lanes" offset to each side, de-duplicated where routes overlap. For each
point and each hour we return continuous wind/rain/snow risk scores (0–4).
"""

from datetime import datetime, timedelta, timezone

from .geo import LatLon, PointIndex, bearing_deg, destination_point, resample
from .risk import condition_scores
from .routing import Route
from .weather import fetch_hourly, snap

HOURS = 48
MAX_POINTS = 400
SCORE_SCALE = 25  # scores are sent as ints 0–100 to keep the payload small


def corridor_grid(routes: list[Route], max_points: int = 350) -> tuple[list[LatLon], float]:
    """Evenly spaced points covering a band around all routes.

    Returns (points, spacing in miles). Lanes run parallel to each route at
    the same spacing as the samples along it, so the grid has no gaps.
    """
    longest = max(r.distance_mi for r in routes)
    half_width = min(45.0, max(15.0, longest * 0.04))  # corridor half-width in miles
    spacing = max(8.0, longest / 60)
    while True:
        lanes = max(1, round(half_width / spacing))
        points: list[LatLon] = []
        index = PointIndex([], cell_deg=max(0.05, spacing / 69))
        for route in routes:
            samples = resample(route.coords, spacing)
            for k, p in enumerate(samples):
                ahead = samples[min(k + 1, len(samples) - 1)]
                behind = samples[max(k - 1, 0)]
                heading = bearing_deg(behind, ahead) if ahead != behind else 0.0
                for lane in range(-lanes, lanes + 1):
                    q = p if lane == 0 else destination_point(p, heading + 90, lane * spacing)
                    if not index.has_point_within(q, spacing * 0.7):
                        index.add(q)
                        points.append(q)
        if len(points) <= max_points:
            return [(round(lat, 4), round(lon, 4)) for lat, lon in points], round(spacing, 2)
        spacing *= 1.15


def build_heatmap(points: list[LatLon], start: datetime, load_lb: float) -> dict:
    start = start.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    series = fetch_hourly(points, start, start + timedelta(hours=HOURS))
    hours = [start + timedelta(hours=h) for h in range(HOURS + 1)]

    wind, rain, snow = [], [], []
    for when in hours:
        w_row, r_row, s_row = [], [], []
        for p in points:
            sample = series[snap(p)].at(when)
            w, r, s = condition_scores(sample.wind_mph, sample.rain_in_hr, sample.snow_in_hr, load_lb)
            w_row.append(round(w * SCORE_SCALE))
            r_row.append(round(r * SCORE_SCALE))
            s_row.append(round(s * SCORE_SCALE))
        wind.append(w_row)
        rain.append(r_row)
        snow.append(s_row)

    return {
        "start": start.isoformat(),
        "hours": [h.isoformat() for h in hours],
        "points": [[lat, lon] for lat, lon in points],
        "scale": SCORE_SCALE,
        "scores": {"wind": wind, "rain": rain, "snow": snow},
    }
