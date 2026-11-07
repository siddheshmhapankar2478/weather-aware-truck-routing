from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from routing.services.geocoding import Place
from routing.services.weather import HourlySeries, snap

from .test_sampling import straight_route


def future(hours=2):
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def fake_weather(points, start, end):
    """Calm everywhere except a windy band north of latitude 0.5°."""
    start_ts = int(start.replace(minute=0, second=0, microsecond=0).timestamp())
    times = [start_ts + h * 3600 for h in range(int((end - start).total_seconds() // 3600) + 3)]
    n = len(times)
    out = {}
    for p in points:
        wind = 48.0 if p[0] > 0.5 else 5.0
        out[snap(p)] = HourlySeries(times, [wind] * n, [wind] * n, [0.0] * n, [0.0] * n, [50.0] * n, [0] * n)
    return out


@override_settings(ALLOWED_HOSTS=["testserver"])
class PlanEndpointTests(SimpleTestCase):
    def post(self, **overrides):
        body = {"origin": "A", "destination": "B", "departure": future(), "load_lb": 35_000, "interval_mi": 10}
        body.update(overrides)
        return self.client.post("/api/plan", body, content_type="application/json")

    def test_rejects_bad_interval(self):
        response = self.post(interval_mi=15)
        self.assertEqual(response.status_code, 400)
        self.assertIn("10, 25 or 50", response.json()["error"])

    def test_rejects_past_departure(self):
        self.assertEqual(self.post(departure=future(-5)).status_code, 400)

    def test_rejects_negative_load(self):
        self.assertEqual(self.post(load_lb=-1).status_code, 400)

    @patch("routing.services.planner.fetch_hourly", side_effect=fake_weather)
    @patch("routing.services.planner.find_route_options")
    @patch("routing.services.planner.resolve_place", side_effect=lambda v: Place(str(v), 0, 0))
    def test_heavy_load_in_wind_prefers_calm_route(self, _place, routes, _weather):
        # Route A is fast but runs into the windy band; route B stays south of it.
        fast_windy = straight_route([60], [3600])  # reaches lat ~0.87
        slow_calm = straight_route([30], [7200])  # stays below lat 0.44
        routes.return_value = [fast_windy, slow_calm]

        data = self.post().json()

        self.assertEqual(data["recommendation"]["route_id"], "B")
        route_a = data["routes"][0]
        # 48 mph is Severe; with 35,000 lb the load rule makes it No Travel.
        self.assertGreater(route_a["risk"]["miles"]["no_travel"], 0)
        self.assertEqual(route_a["risk"]["max_level"], "no_travel")
        self.assertEqual(data["routes"][1]["risk"]["max_level"], "low")
        self.assertIn("No Travel", data["recommendation"]["reason"])
