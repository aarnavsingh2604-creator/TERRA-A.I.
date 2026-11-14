import unittest
from terra_dev2.scoring import (
    DEFAULT_WEIGHTS, score_candidate, rank_candidates, validate_weights
)

class ScoringTests(unittest.TestCase):
    def test_example_formula(self):
        result = score_candidate(
            {"site_id": "A"},
            {"visual": 100, "terrain": 80, "geology": 70, "climate": 60, "water": 50},
            DEFAULT_WEIGHTS,
            {"status": "pass"}
        )
        expected = 28 + 20 + 14 + 10.2 + 5
        self.assertAlmostEqual(result["ranking_index"], expected, places=3)
        self.assertEqual(result["ranking_index_label"], "complete")

    def test_missing_is_not_zero(self):
        result = score_candidate(
            {"site_id": "B"},
            {"visual": 80, "terrain": 60},
            DEFAULT_WEIGHTS,
            {"status": "unknown"}
        )
        self.assertAlmostEqual(result["ranking_index"], (28*80 + 25*60)/(28+25), places=3)
        self.assertEqual(result["missing_dimensions"], ["geology", "climate", "water"])
        self.assertEqual(result["ranking_index_label"], "partial")

    def test_ecology_gate_separate(self):
        result = score_candidate(
            {"site_id": "C"},
            {"visual": 80, "terrain": 80, "geology": 80, "climate": 80, "water": 80},
            DEFAULT_WEIGHTS,
            {"status": "reject"}
        )
        self.assertEqual(result["ranking_index"], 80)
        self.assertEqual(result["recommendation_status"], "excluded_by_ecological_gate")

    def test_weights_normalize(self):
        weights = validate_weights({"visual": 2, "terrain": 2, "geology": 2, "climate": 2, "water": 2})
        self.assertAlmostEqual(sum(weights.values()), 100)

    def test_rank(self):
        rows = [
            {"site_id": "low", "dimensions": {"visual": 30}, "ecology": {"status": "pass"}},
            {"site_id": "high", "dimensions": {"visual": 90}, "ecology": {"status": "pass"}}
        ]
        ranked = rank_candidates(rows, DEFAULT_WEIGHTS)
        self.assertEqual(ranked[0]["site_id"], "high")

if __name__ == "__main__":
    unittest.main()
