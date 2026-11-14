import unittest
from terra_dev1.spatial import generate_screen_grid

class SpatialTests(unittest.TestCase):
    def test_generates_points(self):
        points = generate_screen_grid("mars",
            {"west": -2, "south": -2, "east": 2, "north": 2}, 100)
        self.assertTrue(points)
        self.assertTrue(all(p["planet"] == "mars" for p in points))

    def test_rejects_bad_planet(self):
        with self.assertRaises(ValueError):
            generate_screen_grid("earth",
                {"west": -2, "south": -2, "east": 2, "north": 2}, 100)

if __name__ == "__main__":
    unittest.main()
