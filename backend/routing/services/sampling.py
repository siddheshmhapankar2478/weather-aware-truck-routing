"""Checkpoints placed every N miles along a route, with the truck's ETA at each.

ETAs come from OSRM's per-segment durations, so a checkpoint after a slow
city stretch gets a later time than a constant-speed estimate would give.

Each checkpoint "covers" the stretch of road closer to it than to its
neighbours; those covered miles are what the risk summary adds up.
"""

from bisect import bisect_right
from dataclasses import dataclass

from .geo import LatLon, cumulative, lerp
from .routing import Route


@dataclass
class Checkpoint:
    lat: float
    lon: float
    mile: float
    elapsed_s: float
    start_mile: float  # covered stretch
    end_mile: float

    @property
    def covered_mi(self) -> float:
        return self.end_mile - self.start_mile


class RouteTrack:
    """Position and elapsed time at any mile along a route."""

    def __init__(self, route: Route):
        self.coords = route.coords
        self.miles = cumulative(route.seg_distance_mi)
        self.seconds = cumulative(route.seg_duration_s)
        self.total_mi = self.miles[-1]

    def _locate(self, mile: float) -> tuple[int, float]:
        mile = min(max(mile, 0.0), self.total_mi)
        i = min(max(bisect_right(self.miles, mile) - 1, 0), len(self.miles) - 2)
        span = self.miles[i + 1] - self.miles[i]
        return i, (mile - self.miles[i]) / span if span > 0 else 0.0

    def point_at(self, mile: float) -> LatLon:
        i, t = self._locate(mile)
        return lerp(self.coords[i], self.coords[i + 1], t)

    def elapsed_at(self, mile: float) -> float:
        i, t = self._locate(mile)
        return self.seconds[i] + t * (self.seconds[i + 1] - self.seconds[i])

    def slice(self, start_mile: float, end_mile: float) -> list[LatLon]:
        """Polyline between two miles, including interpolated end points."""
        i, _ = self._locate(start_mile)
        j, _ = self._locate(end_mile)
        inner = [self.coords[k] for k in range(i + 1, j + 1) if start_mile < self.miles[k] < end_mile]
        return [self.point_at(start_mile), *inner, self.point_at(end_mile)]


def checkpoint_miles(total_mi: float, interval_mi: float) -> list[float]:
    count = int(total_mi // interval_mi)
    miles = [k * interval_mi for k in range(count + 1)]
    if total_mi - miles[-1] > 0.01:
        miles.append(total_mi)
    return miles


def sample_checkpoints(track: RouteTrack, interval_mi: float) -> list[Checkpoint]:
    miles = checkpoint_miles(track.total_mi, interval_mi)
    checkpoints = []
    for k, mile in enumerate(miles):
        start = 0.0 if k == 0 else (miles[k - 1] + mile) / 2
        end = track.total_mi if k == len(miles) - 1 else (mile + miles[k + 1]) / 2
        lat, lon = track.point_at(mile)
        checkpoints.append(
            Checkpoint(
                lat=lat,
                lon=lon,
                mile=mile,
                elapsed_s=track.elapsed_at(mile),
                start_mile=start,
                end_mile=end,
            )
        )
    return checkpoints
