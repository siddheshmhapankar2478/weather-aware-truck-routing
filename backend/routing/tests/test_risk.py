from django.test import SimpleTestCase

from routing.services.risk import RiskLevel, assess, classify_rain, classify_snow, classify_wind, wind_level_for_load

L = RiskLevel


class ThresholdTests(SimpleTestCase):
    def test_wind_boundaries(self):
        cases = [(0, L.LOW), (24.9, L.LOW), (25, L.MODERATE), (34.9, L.MODERATE), (35, L.HIGH),
                 (44.9, L.HIGH), (45, L.SEVERE), (54.9, L.SEVERE), (55, L.NO_TRAVEL), (80, L.NO_TRAVEL)]
        for mph, expected in cases:
            self.assertEqual(classify_wind(mph), expected, mph)

    def test_rain_boundaries(self):
        cases = [(0.09, L.LOW), (0.10, L.MODERATE), (0.24, L.MODERATE), (0.25, L.HIGH), (0.49, L.HIGH),
                 (0.50, L.SEVERE), (1.00, L.SEVERE), (1.01, L.NO_TRAVEL)]
        for rate, expected in cases:
            self.assertEqual(classify_rain(rate), expected, rate)

    def test_snow_boundaries(self):
        cases = [(0.49, L.LOW), (0.5, L.MODERATE), (1.0, L.HIGH), (1.99, L.HIGH), (2.0, L.SEVERE),
                 (3.0, L.SEVERE), (3.01, L.NO_TRAVEL)]
        for rate, expected in cases:
            self.assertEqual(classify_snow(rate), expected, rate)


class LoadRuleTests(SimpleTestCase):
    def test_55_mph_is_no_travel_for_any_load(self):
        self.assertEqual(wind_level_for_load(55, 0), (L.NO_TRAVEL, False))

    def test_severe_wind_with_heavy_load_is_no_travel(self):
        self.assertEqual(wind_level_for_load(50, 30_001), (L.NO_TRAVEL, True))
        self.assertEqual(wind_level_for_load(50, 30_000), (L.SEVERE, False))

    def test_high_wind_with_very_heavy_load_is_severe(self):
        self.assertEqual(wind_level_for_load(40, 40_001), (L.SEVERE, True))
        self.assertEqual(wind_level_for_load(40, 40_000), (L.HIGH, False))

    def test_load_does_not_change_lower_winds(self):
        self.assertEqual(wind_level_for_load(30, 80_000), (L.MODERATE, False))


class AssessTests(SimpleTestCase):
    def test_worst_factor_wins(self):
        result = assess(wind_mph=10, rain_in_hr=0.3, snow_in_hr=1.5, load_lb=20_000)
        self.assertEqual(result.level, L.HIGH)
        self.assertEqual((result.wind, result.rain, result.snow), (L.LOW, L.HIGH, L.HIGH))
        self.assertEqual(len(result.reasons), 2)

    def test_load_rule_is_explained(self):
        result = assess(wind_mph=47, rain_in_hr=0, snow_in_hr=0, load_lb=35_000)
        self.assertEqual(result.level, L.NO_TRAVEL)
        self.assertIn("35,000 lb", result.reasons[0])

    def test_calm_weather_is_low_with_no_reasons(self):
        result = assess(5, 0, 0, 45_000)
        self.assertEqual(result.level, L.LOW)
        self.assertEqual(result.reasons, [])
