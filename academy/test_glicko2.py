import pytest
from academy.glicko2 import Glicko2, Glicko2Rating


def test_glickman_paper_example():
    """Ejemplo numérico del paper de Glickman (tau=0.5)."""
    env = Glicko2()
    p = Glicko2Rating(1500, 200, 0.06)
    series = [
        (1, Glicko2Rating(1400, 30, 0.06)),
        (0, Glicko2Rating(1550, 100, 0.06)),
        (0, Glicko2Rating(1700, 300, 0.06)),
    ]
    r = env.rate(p, series)
    assert r.mu == pytest.approx(1464.06, abs=0.05)
    assert r.phi == pytest.approx(151.52, abs=0.05)
    assert r.sigma == pytest.approx(0.05999, abs=0.0001)


def test_winner_gains_loser_drops_and_rd_shrinks():
    env = Glicko2()
    a, b = env.create_rating(), env.create_rating()
    na, nb = env.rate_1vs1(a, b)
    assert na.mu > 1500 > nb.mu
    assert na.phi < a.phi and nb.phi < b.phi


def test_inactivity_increases_rd():
    env = Glicko2()
    r = Glicko2Rating(1600, 80, 0.06)
    assert env.rate(r, []).phi > 80
