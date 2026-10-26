import unittest
import math
from academy.glicko2 import Glicko2, Glicko2Rating


class TestGlicko2(unittest.TestCase):
    def test_glickman_paper_example(self):
        """Ejemplo numérico del paper de Glickman (tau=0.5)."""
        env = Glicko2()
        p = Glicko2Rating(1500, 200, 0.06)
        series = [
            (1, Glicko2Rating(1400, 30, 0.06)),
            (0, Glicko2Rating(1550, 100, 0.06)),
            (0, Glicko2Rating(1700, 300, 0.06)),
        ]
        r = env.rate(p, series)
        self.assertAlmostEqual(r.mu, 1464.06, delta=0.05)
        self.assertAlmostEqual(r.phi, 151.52, delta=0.05)
        self.assertAlmostEqual(r.sigma, 0.05999, delta=0.0001)

    def test_winner_gains_loser_drops_and_rd_shrinks(self):
        env = Glicko2()
        a, b = env.create_rating(), env.create_rating()
        na, nb = env.rate_1vs1(a, b)
        self.assertTrue(na.mu > 1500 > nb.mu)
        self.assertTrue(na.phi < a.phi and nb.phi < b.phi)


if __name__ == '__main__':
    unittest.main()
