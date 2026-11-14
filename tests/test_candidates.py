import unittest
from terra_dev1.candidates import generate_candidates

class CandidateTests(unittest.TestCase):
    def test_candidate_generation(self):
        result = generate_candidates("moon", [
            {"latitude": 1, "longitude": 2}
        ], [{"latitude": 1, "longitude": 2, "similarity": 0.8}])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["visual_similarity"], 0.8)
        self.assertEqual(result[0]["scientific_suitability"], "not_assessed")

if __name__ == "__main__":
    unittest.main()
