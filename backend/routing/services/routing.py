"""Route options from OSRM.

OSRM often returns fewer alternatives than asked for (Denver → Chicago gives 2).
When that happens we ask for routes through detour waypoints placed to either
side of the trip and keep the ones that are distinct and not absurdly long.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from django.conf import settings

from .geo import (
    METERS_PER_MILE,
    LatLon,
    PointIndex,
    bearing_deg,
    destination_point,
    haversine_mi,
    lerp,
    resample,
)
from .http import UpstreamError, get_json

logger = logging.getLogger(__name__)

# A candidate counts as a duplicate when this share of it lies on an existing route.
DUPLICATE_OVERLAP = 0.85
# Detours longer than this multiple of the fastest route are not worth offering.
MAX_DETOUR_RATIO = 1.5


class NoRouteError(Exception):
    """No drivable route exists between the two points."""


@dataclass
class Route:
    coords: list[LatLon]
    distance_mi: float
    duration_s: float
    seg_distance_mi: list[float]  # one entry per pair of consecutive coords
    seg_duration_s: list[float]
    summary: str = ""
    via: LatLon | None = None
    _index: PointIndex | None = field(default=None, repr=False)

    def index(self) -> PointIndex:
        if self._index is None:
            self._index = PointIndex(resample(self.coords, 1.0))
        return self._index


def _parse_route(raw: dict, via: LatLon | None = None) -> Route:
    coords = [(lat, lon) for lon, lat in raw["geometry"]["coordinates"]]
    seg_m, seg_s = [], []
    for leg in raw["legs"]:
        annotation = leg.get("annotation") or {}
        seg_m.extend(annotation.get("distance", []))
        seg_s.extend(annotation.get("duration", []))

    factor = settings.TRUCK_DURATION_FACTOR
    duration_s = raw["duration"] * factor

    if len(seg_m) == len(coords) - 1 and len(seg_s) == len(coords) - 1:
        seg_mi = [m / METERS_PER_MILE for m in seg_m]
    else:
        # Annotations missing or misaligned: fall back to geometry + constant speed.
        seg_mi = [haversine_mi(a, b) for a, b in zip(coords, coords[1:])]
        seg_s = seg_mi

    # Scale segment times so they add up exactly to the route's total time.
    total = sum(seg_s) or 1.0
    seg_s = [s / total * duration_s for s in seg_s]

    roads: list[str] = []
    for leg in raw["legs"]:
        for name in (leg.get("summary") or "").split(", "):
            if name and name not in roads:
                roads.append(name)
    summary = ", ".join(roads)
    return Route(
        coords=coords,
        distance_mi=raw["distance"] / METERS_PER_MILE,
        duration_s=duration_s,
        seg_distance_mi=seg_mi,
        seg_duration_s=seg_s,
        summary=summary,
        via=via,
    )


def _request_routes(points: list[LatLon], alternatives: int = 0, via: LatLon | None = None) -> list[Route]:
    coord_str = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in points)
    data = get_json(
        f"{settings.OSRM_URL}/route/v1/driving/{coord_str}",
        {
            "alternatives": str(alternatives) if alternatives else "false",
            "overview": "full",
            "geometries": "geojson",
            "annotations": "distance,duration",
            "steps": "true",  # needed for the road-name summary
        },
        timeout=30,
        service="Routing",
    )
    if data.get("code") == "NoRoute":
        raise NoRouteError("No drivable route was found between these locations.")
    if data.get("code") != "Ok":
        raise UpstreamError(data.get("message") or "Routing service returned an error.")
    return [_parse_route(raw, via) for raw in data.get("routes", [])]


def _overlap_ratio(candidate: Route, existing: Route, tolerance_mi: float = 1.5) -> float:
    samples = resample(candidate.coords, 2.0)
    index = existing.index()
    hits = sum(1 for p in samples if index.has_point_within(p, tolerance_mi))
    return hits / len(samples)


def _is_distinct(candidate: Route, chosen: list[Route]) -> bool:
    return all(_overlap_ratio(candidate, r) < DUPLICATE_OVERLAP for r in chosen)


def _detour_waypoints(origin: LatLon, destination: LatLon) -> list[LatLon]:
    """Points left and right of the trip's midpoint, at two offsets."""
    straight = haversine_mi(origin, destination)
    mid = lerp(origin, destination, 0.5)
    heading = bearing_deg(origin, destination)
    points = []
    for share in (0.15, 0.3):
        offset = min(150.0, max(10.0, straight * share))
        for side in (90, -90):
            points.append(destination_point(mid, heading + side, offset))
    return points


def find_route_options(origin: LatLon, destination: LatLon, count: int = 3) -> list[Route]:
    """Up to `count` distinct routes, fastest first."""
    options: list[Route] = []
    for route in _request_routes([origin, destination], alternatives=count):
        if _is_distinct(route, options):
            options.append(route)

    if len(options) < count and options:
        vias = _detour_waypoints(origin, destination)

        def fetch(via):
            try:
                return _request_routes([origin, via, destination], via=via)
            except (UpstreamError, NoRouteError) as exc:
                logger.info("Detour via %s skipped: %s", via, exc)
                return []

        with ThreadPoolExecutor(max_workers=len(vias)) as pool:
            detours = [r for batch in pool.map(fetch, vias) for r in batch]

        limit = options[0].distance_mi * MAX_DETOUR_RATIO
        for route in sorted(detours, key=lambda r: r.duration_s):
            if len(options) >= count:
                break
            if route.distance_mi <= limit and _is_distinct(route, options):
                options.append(route)

    if not options:
        raise NoRouteError("No drivable route was found between these locations.")
    return sorted(options, key=lambda r: r.duration_s)[:count]
