import unittest
from utils import normalize_player_name

class TestUtils(unittest.TestCase):
    def test_normalize_player_name(self):
        self.assertEqual(normalize_player_name("Nicolás Mardones"), "nicolas mardones")
        self.assertEqual(normalize_player_name("Nicolas Mardones"), "nicolas mardones")
        self.assertEqual(normalize_player_name("  Nicolás   Mardones  "), "nicolas mardones")
        self.assertEqual(normalize_player_name("ALVARO rojas"), "alvaro rojas")
        self.assertEqual(normalize_player_name("Éric Mélo"), "eric melo")
        self.assertEqual(normalize_player_name(""), "")
        self.assertEqual(normalize_player_name("Johan Loza"), "johan loza")

if __name__ == "__main__":
    unittest.main()

