import unittest
from unittest.mock import patch
import sqlite3
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from academy.competitive_analyzer import CompetitiveAnalyzer
from academy.rating_simulator import RatingSimulator, ClassicEloStrategy

class TestHistoricalAnalysis(unittest.TestCase):
    def setUp(self):
        # Create an in-memory database for testing
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        self._create_schema()
        self._seed_data()
        
        # Patch get_connection
        self.patcher1 = patch('academy.competitive_analyzer.get_connection', return_value=self.conn)
        self.patcher2 = patch('academy.rating_simulator.get_connection', return_value=self.conn)
        self.patcher1.start()
        self.patcher2.start()

    def tearDown(self):
        self.patcher1.stop()
        self.patcher2.stop()
        self.conn.close()
        
    def _create_schema(self):
        cursor = self.conn.cursor()
        cursor.execute("CREATE TABLE players (id INTEGER PRIMARY KEY, name TEXT)")
        cursor.execute("CREATE TABLE tournaments (id INTEGER PRIMARY KEY, format_name TEXT, date TEXT)")
        cursor.execute("CREATE TABLE league_profiles (id INTEGER PRIMARY KEY, player_id INTEGER)")
        cursor.execute("CREATE TABLE tournament_results (id INTEGER PRIMARY KEY, tournament_id INTEGER, league_profile_id INTEGER, placement_points INTEGER DEFAULT 0)")
        cursor.execute("CREATE TABLE tournament_matches (id INTEGER PRIMARY KEY, tournament_id INTEGER, p1_id INTEGER, p2_id INTEGER, result_text TEXT, round_num INTEGER)")
        self.conn.commit()
        
    def _seed_data(self):
        cursor = self.conn.cursor()
        cursor.executemany("INSERT INTO players (id, name) VALUES (?, ?)", [(1, "P1"), (2, "P2"), (3, "P3")])
        cursor.execute("INSERT INTO tournaments (id, format_name, date) VALUES (1, 'GOAT', '2026-08-01')")
        cursor.executemany("INSERT INTO league_profiles (id, player_id) VALUES (?, ?)", [(1, 1), (2, 2)])
        cursor.executemany("INSERT INTO tournament_results (tournament_id, league_profile_id, placement_points) VALUES (?, ?, ?)", [(1, 1, 10), (1, 2, 5)])
        
        # P1 vs P2 (P1 Wins)
        cursor.execute("INSERT INTO tournament_matches (tournament_id, p1_id, p2_id, result_text, round_num) VALUES (1, 1, 2, 'P1_WIN', 1)")
        # P1 vs P3 (DRAW)
        cursor.execute("INSERT INTO tournament_matches (tournament_id, p1_id, p2_id, result_text, round_num) VALUES (1, 1, 3, 'DRAW', 2)")
        # P2 vs BYE
        cursor.execute("INSERT INTO tournament_matches (tournament_id, p1_id, p2_id, result_text, round_num) VALUES (1, 2, NULL, 'BYE', 2)")
        
        self.conn.commit()

    def test_competitive_analyzer_stats(self):
        analyzer = CompetitiveAnalyzer()
        
        stats_p1 = analyzer.get_player_stats(1)
        self.assertEqual(stats_p1['total_matches'], 2)
        self.assertEqual(stats_p1['wins'], 1)
        self.assertEqual(stats_p1['draws'], 1)
        self.assertEqual(stats_p1['losses'], 0)
        self.assertEqual(stats_p1['win_rate'], 50.0)
        self.assertEqual(stats_p1['championships'], 1)
        
        stats_p2 = analyzer.get_player_stats(2)
        # Match against BYE shouldn't count
        self.assertEqual(stats_p2['total_matches'], 1)
        self.assertEqual(stats_p2['losses'], 1)
        self.assertEqual(stats_p2['win_rate'], 0.0)
        self.assertEqual(stats_p2['finals'], 1)
        
    def test_head_to_head(self):
        analyzer = CompetitiveAnalyzer()
        h2h = analyzer.get_head_to_head(1)
        
        self.assertEqual(len(h2h), 2)
        
        p2_match = next(m for m in h2h if m['opponent_id'] == 2)
        self.assertEqual(p2_match['wins'], 1)
        self.assertEqual(p2_match['total'], 1)
        
        p3_match = next(m for m in h2h if m['opponent_id'] == 3)
        self.assertEqual(p3_match['draws'], 1)
        self.assertEqual(p3_match['total'], 1)
        
    def test_rating_simulator_classic(self):
        strategy = ClassicEloStrategy(initial_rating=1000, K=32)
        sim = RatingSimulator(strategy)
        players, history = sim.simulate()
        
        # P1 should gain points, P2 should lose points
        p1 = players[1]
        p2 = players[2]
        
        self.assertGreater(p1['current_rating'], 1000)
        self.assertLess(p2['current_rating'], 1000)
        
        # P3 drew against P1 (who had higher rating), so P3 should gain a tiny bit of points
        p3 = players[3]
        self.assertGreater(p3['current_rating'], 1000)
        
    def test_rating_simulator_v2(self):
        from academy.rating_simulator import V2EloStrategy
        strategy = V2EloStrategy()
        sim = RatingSimulator(strategy)
        players, history = sim.simulate()
        
        # P1 has 2 matches (W, D)
        # P2 has 1 match (L)
        # P3 has 1 match (D)
        
        p1 = players[1]
        self.assertEqual(p1['matches_played'], 2)
        self.assertGreater(p1['current_rating'], 1000)
        
        # For first 10 matches, K should be 64
        self.assertEqual(strategy.get_k_factor(p1), 64)
        
        p1_stats_dummy = {'matches_played': 10}
        self.assertEqual(strategy.get_k_factor(p1_stats_dummy), 32)
        
        p1_stats_dummy = {'matches_played': 30}
        self.assertEqual(strategy.get_k_factor(p1_stats_dummy), 24)

    def test_rating_simulator_v3(self):
        from academy.rating_simulator import V3EloStrategy16, V3EloStrategy24, V3EloStrategyConsolidated
        
        s16 = V3EloStrategy16()
        s24 = V3EloStrategy24()
        sCon = V3EloStrategyConsolidated()
        
        # Test bounds
        self.assertEqual(s16.get_k_factor({'matches_played': 0}), 64)
        self.assertEqual(s16.get_k_factor({'matches_played': 15}), 32)
        self.assertEqual(s16.get_k_factor({'matches_played': 35}), 16)
        
        self.assertEqual(s24.get_k_factor({'matches_played': 0}), 64)
        self.assertEqual(s24.get_k_factor({'matches_played': 15}), 32)
        self.assertEqual(s24.get_k_factor({'matches_played': 35}), 24)
        
        self.assertEqual(sCon.get_k_factor({'matches_played': 0}), 64)
        self.assertEqual(sCon.get_k_factor({'matches_played': 15}), 32)
        self.assertEqual(sCon.get_k_factor({'matches_played': 35}), 32)
        
if __name__ == '__main__':
    unittest.main()
