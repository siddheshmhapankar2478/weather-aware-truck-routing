from django.test import SimpleTestCase

from routing.services.geo import haversine_mi
from routing.services.heatmap import corridor_grid
from routing.services.risk import condition_scores

from .test_sampling import straight_route


class ConditionScoreTests(SimpleTestCase):
    def test_whole_part_matches_discrete_level(self):
        wind, rain, snow = condition_scores(30, 0.3, 2.5, load_lb=10_000)
        self.assertEqual((int(wind), int(rain), int(snow)), (1, 2, 3))

    def test_fraction_moves_through_band(self):
        self.assertAlmostEqual(condition_scores(30, 0, 0, 0)[0], 1.5)  # halfway 25→35

    def test_load_rules_raise_wind_score(self):
        self.assertEqual(condition_scores(50, 0, 0, 35_000)[0], 4.0)  # Severe → No Travel
        self.assertAlmostEqual(condition_scores(40, 0, 0, 45_000)[0], 3.5)  # High → Severe
        self.assertAlmostEqual(condition_scores(40, 0, 0, 20_000)[0], 2.5)

    def test_calm_is_near_zero(self):
        self.assertEqual(condition_scores(0, 0, 0, 0), (0.0, 0.0, 0.0))


class CorridorGridTests(SimpleTestCase):
    def test_grid_is_capped_and_covers_route(self):
        route = straight_route([600], [36000])
        points, spacing = corridor_grid([route], max_points=120)
        self.assertLessEqual(len(points), 120)
        # Every point along the route has a grid point nearby.
        for k in range(0, 601, 50):
            here = (k / 69.09, 0.0)
            self.assertTrue(any(haversine_mi(here, p) <= spacing for p in points), k)

    def test_overlapping_routes_are_deduplicated(self):
        route = straight_route([300], [18000])
        single, _ = corridor_grid([route])
        double, _ = corridor_grid([route, route])
        self.assertEqual(len(single), len(double))
