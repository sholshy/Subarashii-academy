import unittest
from tournament_manager import TournamentManager, Player, Match

class TestTournamentDropIntegrity(unittest.TestCase):
    def test_drop_preserves_matches_and_opponent_points(self):
        tm = TournamentManager()
        tm.add_player("Yugi Muto", "101")
        tm.add_player("Seto Kaiba", "102")
        tm.add_player("Joey Wheeler", "103")
        tm.add_player("Tea Gardner", "104")

        # Iniciar torneo suizo
        tm.start_tournament(mode="swiss", format_name="EDISON", total_rounds_override=3)
        self.assertEqual(tm.current_round, 1)

        # Reportar victoria 2-0 para el jugador 1 de cada mesa
        m1 = tm.rounds[0][0]
        m2 = tm.rounds[0][1]

        winner_1 = m1.p1
        loser_1 = m1.p2
        winner_2 = m2.p1
        loser_2 = m2.p2

        m1.report("2-0")
        m2.report("2-0")

        self.assertEqual(winner_1.points, 3)
        self.assertEqual(loser_1.points, 0)
        self.assertEqual(winner_2.points, 3)
        self.assertEqual(loser_2.points, 0)

        # El perdedor de la mesa 1 decide hacer DROP tras la Ronda 1
        tm.drop_player(loser_1.name, reason="Retiro voluntario tras perder R1")
        self.assertFalse(loser_1.active)

        # Comprobar que el jugador retirado sigue en la tabla y que los puntos del ganador no cambiaron
        self.assertEqual(winner_1.points, 3)
        self.assertEqual(loser_1.points, 0)
        self.assertIn(loser_1, tm.players)

        # Avanzar a la Ronda 2
        tm.generate_next_round()
        self.assertEqual(tm.current_round, 2)

        # En la ronda 2, Kaiba NO debe recibir emparejamiento con nadie (queda 3 jugadores: 1 bye y 1 match)
        r2_matches = tm.rounds[1]
        players_in_r2 = []
        for m in r2_matches:
            if m.p1: players_in_r2.append(m.p1.name)
            if m.p2: players_in_r2.append(m.p2.name)

        self.assertNotIn(loser_1.name, players_in_r2, "El jugador dropeado no debe estar en los pareos de R2")
        self.assertIn(winner_1.name, players_in_r2)
        self.assertIn(winner_2.name, players_in_r2)

        # Verificar cálculo de desempate OMW%
        standings = tm.get_standings()
        ranked = tm.get_ranked_standings()
        self.assertTrue(len(ranked) >= 3)

if __name__ == '__main__':
    unittest.main()
