from django.test import SimpleTestCase

from routing.services.recommendation import RouteScore, explain, rank_routes


def score(route_id, no_travel=0, severe=0, high=0, avg=0.0, hours=10.0):
    return RouteScore(route_id, no_travel, severe, high, avg, hours * 3600)


class RankingTests(SimpleTestCase):
    def ids(self, scores):
        return [s.route_id for s in rank_routes(scores)]

    def test_fewest_severe_miles_beats_faster_route(self):
        self.assertEqual(self.ids([score("A", severe=40, hours=8), score("B", hours=12)]), ["B", "A"])

    def test_no_travel_ranks_below_severe(self):
        self.assertEqual(self.ids([score("A", no_travel=10), score("B", severe=200)]), ["B", "A"])

    def test_high_miles_break_severe_tie(self):
        self.assertEqual(self.ids([score("A", severe=20, high=50), score("B", severe=20, high=10)]), ["B", "A"])

    def test_average_risk_breaks_high_tie(self):
        self.assertEqual(self.ids([score("A", avg=0.8), score("B", avg=0.3, hours=11)]), ["B", "A"])

    def test_time_decides_when_risk_is_equal(self):
        self.assertEqual(self.ids([score("A", hours=11), score("B", hours=10), score("C", hours=12)]), ["B", "A", "C"])

    def test_tiny_risk_differences_are_ties(self):
        self.assertEqual(self.ids([score("A", avg=0.02, hours=10), score("B", avg=0.0, hours=12)]), ["A", "B"])


class ExplainTests(SimpleTestCase):
    def test_mentions_deciding_criterion(self):
        text = explain(score("B", severe=0), score("A", severe=45))
        self.assertIn("Severe miles", text)
        self.assertIn("45 mi", text)

    def test_time_reason(self):
        self.assertIn("faster", explain(score("A", hours=9), score("B", hours=10)))
