"""
Glicko-2 (Mark Glickman, http://www.glicko.net/glicko/glicko2.pdf).

Implementación propia siguiendo la especificación, con la misma API conceptual
que sublee/glicko2 (https://github.com/sublee/glicko2, BSD): rating, desviación (RD)
y volatilidad. Se usa como rating complementario al ELO oficial de AcademyEngine:
la RD indica cuán confiable es el rating de un jugador (reemplaza los K provisionales).
"""
import math

MU = 1500.0
PHI = 350.0
SIGMA = 0.06
TAU = 0.5
EPSILON = 0.000001
Q = math.log(10) / 400  # 173.7178 = 1/Q


class Glicko2Rating:
    def __init__(self, mu=MU, phi=PHI, sigma=SIGMA):
        self.mu = mu
        self.phi = phi
        self.sigma = sigma

    @property
    def interval(self):
        """Intervalo de confianza ~95%."""
        return (self.mu - 2 * self.phi, self.mu + 2 * self.phi)

    def __repr__(self):
        return f"Glicko2Rating(mu={self.mu:.2f}, phi={self.phi:.2f}, sigma={self.sigma:.5f})"


class Glicko2:
    def __init__(self, mu=MU, phi=PHI, sigma=SIGMA, tau=TAU):
        self.mu, self.phi, self.sigma, self.tau = mu, phi, sigma, tau

    def create_rating(self, mu=None, phi=None, sigma=None):
        return Glicko2Rating(self.mu if mu is None else mu,
                             self.phi if phi is None else phi,
                             self.sigma if sigma is None else sigma)

    @staticmethod
    def _g(phi):
        return 1 / math.sqrt(1 + 3 * phi ** 2 / math.pi ** 2)

    @staticmethod
    def _expect(mu, mu_j, phi_j):
        return 1 / (1 + math.exp(-Glicko2._g(phi_j) * (mu - mu_j)))

    def expected_score(self, rating, other):
        """Probabilidad esperada de que `rating` gane a `other` (escala Glicko-2 interna)."""
        return self._expect((rating.mu - 1500) * Q, (other.mu - 1500) * Q, other.phi * Q)

    def rate(self, rating, series):
        """
        series: lista de (score, rival_rating); score 1 / 0.5 / 0.
        Devuelve un nuevo Glicko2Rating. Sin partidas: solo aumenta la RD.
        """
        mu = (rating.mu - 1500) * Q
        phi = rating.phi * Q
        sigma = rating.sigma

        if not series:
            phi_new = math.sqrt(phi ** 2 + sigma ** 2)
            return Glicko2Rating(rating.mu, phi_new / Q, sigma)

        v_inv = 0.0
        delta_sum = 0.0
        for score, opp in series:
            mu_j = (opp.mu - 1500) * Q
            phi_j = opp.phi * Q
            g = self._g(phi_j)
            e = self._expect(mu, mu_j, phi_j)
            v_inv += g ** 2 * e * (1 - e)
            delta_sum += g * (score - e)
        v = 1 / v_inv
        delta = v * delta_sum

        # Nueva volatilidad (algoritmo de Illinois)
        a = math.log(sigma ** 2)

        def f(x):
            ex = math.exp(x)
            return (ex * (delta ** 2 - phi ** 2 - v - ex) / (2 * (phi ** 2 + v + ex) ** 2)
                    - (x - a) / self.tau ** 2)

        A = a
        if delta ** 2 > phi ** 2 + v:
            B = math.log(delta ** 2 - phi ** 2 - v)
        else:
            k = 1
            while f(a - k * self.tau) < 0:
                k += 1
            B = a - k * self.tau
        fA, fB = f(A), f(B)
        while abs(B - A) > EPSILON:
            C = A + (A - B) * fA / (fB - fA)
            fC = f(C)
            if fC * fB <= 0:
                A, fA = B, fB
            else:
                fA /= 2
            B, fB = C, fC
        sigma_new = math.exp(A / 2)

        phi_star = math.sqrt(phi ** 2 + sigma_new ** 2)
        phi_new = 1 / math.sqrt(1 / phi_star ** 2 + 1 / v)
        mu_new = mu + phi_new ** 2 * delta_sum

        return Glicko2Rating(mu_new * (1 / Q) + 1500, phi_new / Q, sigma_new)

    def rate_1vs1(self, a, b, drawn=False):
        """a vence a b (o empate). Devuelve (nuevo_a, nuevo_b)."""
        sa, sb = (0.5, 0.5) if drawn else (1.0, 0.0)
        return self.rate(a, [(sa, b)]), self.rate(b, [(sb, a)])
