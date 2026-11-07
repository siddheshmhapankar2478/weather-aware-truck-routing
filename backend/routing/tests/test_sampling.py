from django.test import SimpleTestCase

from routing.services.geo import haversine_mi, resample
from routing.services.routing import Route
from routing.services.sampling import RouteTrack, checkpoint_miles, sample_checkpoints


def straight_route(miles_per_segment, seconds_per_segment):
    """A route heading north along a meridian (1° lat ≈ 69.09 mi)."""
    deg = [0.0]
    for m in miles_per_segment:
        deg.append(deg[-1] + m / 69.09)
    coords = [(d, 0.0) for d in deg]
    return Route(
        coords=coords,
        distance_mi=sum(miles_per_segment),
        duration_s=sum(seconds_per_segment),
        seg_distance_mi=list(miles_per_segment),
        seg_duration_s=list(seconds_per_segment),
    )


class CheckpointMilesTests(SimpleTestCase):
    def test_includes_start_and_end(self):
        self.assertEqual(checkpoint_miles(60, 25), [0, 25, 50, 60])

    def test_exact_multiple_has_no_duplicate_end(self):
        self.assertEqual(checkpoint_miles(50, 25), [0, 25, 50])


class SampleCheckpointTests(SimpleTestCase):
    def test_covered_miles_add_up_to_route_length(self):
        track = RouteTrack(straight_route([30, 40, 37], [1800, 2400, 2220]))
        cps = sample_checkpoints(track, 10)
        self.assertAlmostEqual(sum(cp.covered_mi for cp in cps), 107)
        self.assertEqual(cps[0].start_mile, 0)
        self.assertEqual(cps[-1].end_mile, 107)

    def test_eta_follows_segment_speeds(self):
        # First 50 mi at 50 mph (1 h), next 50 mi at 25 mph (2 h).
        track = RouteTrack(straight_route([50, 50], [3600, 7200]))
        cps = sample_checkpoints(track, 25)
        self.assertEqual([cp.mile for cp in cps], [0, 25, 50, 75, 100])
        self.assertEqual([round(cp.elapsed_s) for cp in cps], [0, 1800, 3600, 7200, 10800])

    def test_positions_are_on_the_route(self):
        track = RouteTrack(straight_route([100], [7200]))
        cp = sample_checkpoints(track, 25)[1]
        self.assertAlmostEqual(haversine_mi((0, 0), (cp.lat, cp.lon)), 25, delta=0.1)

    def test_slice_returns_interpolated_ends(self):
        track = RouteTrack(straight_route([10, 10, 10], [600, 600, 600]))
        part = track.slice(5, 25)
        self.assertEqual(len(part), 4)  # start, two inner vertices, end
        self.assertAlmostEqual(haversine_mi(part[0], part[-1]), 20, delta=0.05)


class ResampleTests(SimpleTestCase):
    def test_even_spacing(self):
        pts = resample([(0, 0), (1, 0)], 10)  # ~69 mi
        self.assertEqual(len(pts), 8)  # 0,10,...,60 + end
        self.assertAlmostEqual(haversine_mi(pts[0], pts[1]), 10, delta=0.01)
