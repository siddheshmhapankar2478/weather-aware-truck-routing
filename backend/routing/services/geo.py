"""Small spherical-geometry helpers. Points are (lat, lon) tuples in degrees."""

import math
from collections import defaultdict

EARTH_RADIUS_MI = 3958.7613
METERS_PER_MILE = 1609.344

LatLon = tuple[float, float]


def haversine_mi(a: LatLon, b: LatLon) -> float:
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_MI * math.asin(min(1.0, math.sqrt(h)))


def lerp(a: LatLon, b: LatLon, t: float) -> LatLon:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def bearing_deg(a: LatLon, b: LatLon) -> float:
    lat1, lat2 = math.radians(a[0]), math.radians(b[0])
    dlon = math.radians(b[1] - a[1])
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def destination_point(origin: LatLon, bearing: float, distance_mi: float) -> LatLon:
    """Point reached by travelling `distance_mi` from `origin` on `bearing`."""
    lat1, lon1 = math.radians(origin[0]), math.radians(origin[1])
    brg = math.radians(bearing)
    d = distance_mi / EARTH_RADIUS_MI
    lat2 = math.asin(math.sin(lat1) * math.cos(d) + math.cos(lat1) * math.sin(d) * math.cos(brg))
    lon2 = lon1 + math.atan2(math.sin(brg) * math.sin(d) * math.cos(lat1), math.cos(d) - math.sin(lat1) * math.sin(lat2))
    return (math.degrees(lat2), (math.degrees(lon2) + 540) % 360 - 180)


def cumulative(values) -> list[float]:
    """[0, v0, v0+v1, ...] — running totals with a leading zero."""
    out = [0.0]
    for v in values:
        out.append(out[-1] + v)
    return out


def resample(coords: list[LatLon], step_mi: float) -> list[LatLon]:
    """Points spaced every `step_mi` along a polyline (always includes both ends)."""
    if len(coords) < 2:
        return list(coords)
    out = [coords[0]]
    carried = 0.0  # distance travelled since the last emitted point
    for a, b in zip(coords, coords[1:]):
        seg = haversine_mi(a, b)
        pos = step_mi - carried
        while seg > 0 and pos <= seg:
            out.append(lerp(a, b, pos / seg))
            pos += step_mi
        carried = (carried + seg) % step_mi if seg > 0 else carried
    if out[-1] != coords[-1]:
        out.append(coords[-1])
    return out


class PointIndex:
    """Grid hash for fast "is there a point within X miles?" checks."""

    def __init__(self, points: list[LatLon], cell_deg: float = 0.05):
        self.cell = cell_deg
        self.grid: dict[tuple[int, int], list[LatLon]] = defaultdict(list)
        for p in points:
            self.grid[self._key(p)].append(p)

    def _key(self, p: LatLon) -> tuple[int, int]:
        return (int(math.floor(p[0] / self.cell)), int(math.floor(p[1] / self.cell)))

    def has_point_within(self, p: LatLon, radius_mi: float) -> bool:
        ki, kj = self._key(p)
        reach = 1 + int(radius_mi / (self.cell * 69 * max(0.2, math.cos(math.radians(p[0])))))
        for di in range(-reach, reach + 1):
            for dj in range(-reach, reach + 1):
                for q in self.grid.get((ki + di, kj + dj), ()):
                    if haversine_mi(p, q) <= radius_mi:
                        return True
        return False


def simplify(coords: list[LatLon], tolerance_deg: float) -> list[LatLon]:
    """Ramer–Douglas–Peucker simplification (iterative, planar approximation)."""
    n = len(coords)
    if n < 3:
        return list(coords)
    keep = [False] * n
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    tol2 = tolerance_deg * tolerance_deg
    while stack:
        start, end = stack.pop()
        ax, ay = coords[start]
        bx, by = coords[end]
        dx, dy = bx - ax, by - ay
        seg_len2 = dx * dx + dy * dy
        best_i, best_d2 = -1, tol2
        for i in range(start + 1, end):
            px, py = coords[i]
            if seg_len2 == 0:
                d2 = (px - ax) ** 2 + (py - ay) ** 2
            else:
                t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg_len2))
                d2 = (px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2
            if d2 > best_d2:
                best_i, best_d2 = i, d2
        if best_i != -1:
            keep[best_i] = True
            stack.append((start, best_i))
            stack.append((best_i, end))
    return [c for c, k in zip(coords, keep) if k]
