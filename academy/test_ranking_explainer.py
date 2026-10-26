import unittest
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from academy.academy_engine import AcademyEngine
from academy.ranking_explainer import explain_player, format_explanation
from database import init_db, get_connection


class TestRankingExplainer(unittest.TestCase):
    def setUp(self):
        self.db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "test_explainer.db")
        import database
        database.DB_PATH = self.db_path
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        init_db()
        self.conn = get_connection()
        self.cur = self.conn.cursor()
        self.cur.execute("DELETE FROM academy_profiles")
        self.cur.execute("DELETE FROM players")
        self.cur.execute("INSERT INTO stores (name) VALUES ('S')")
        store = self.cur.lastrowid
        self.cur.execute("INSERT INTO players (name, slug) VALUES ('Ana', 'ana')")
        self.ana = self.cur.lastrowid
        self.cur.execute("INSERT INTO players (name, slug) VALUES ('Beto', 'beto')")
        self.beto = self.cur.lastrowid
        self.cur.execute("INSERT INTO tournaments (store_id, format_name, date) VALUES (?, 'GLOBAL', '2026-08-12')", (store,))
        t = self.cur.lastrowid
        self.engine = AcademyEngine(store_id=store)
        # Ana gana 3 duelos, pierde 1
        for i, res in enumerate([1, 1, 0, 1], 1):
            self.cur.execute("INSERT INTO tournament_matches (tournament_id, p1_id, p2_id, round_num, result_text) VALUES (?, ?, ?, ?, 'x')",
                             (t, self.ana, self.beto, i))
            self.engine.process_match(self.cur, self.cur.lastrowid, self.ana, self.beto, res, timestamp=f"2026-08-1{i}")
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_rating_breakdown_reconciles(self):
        e = explain_player(self.cur, self.ana)
        b = e['rating_breakdown']
        self.assertEqual(b['base'] + b['from_duels'] + b['other_adjustments'], e['rating'])
        self.assertEqual(b['other_adjustments'], 0)
        self.assertEqual(e['duels_total'], 4)
        self.assertEqual(e['duels'][0]['opponent'], 'Beto')
        self.assertEqual(e['position'], 1)

    def test_xp_is_fully_traced(self):
        e = explain_player(self.cur, self.ana)
        # 4 duelos * 5 + 3 victorias * 10 = 50 por duelos
        # + logros del catálogo: ACH_FIRST_MATCH (50) + ACH_FIRST_WIN (50) = 100
        self.assertEqual(e['xp'], 150)
        self.assertEqual(e['xp_by_source']['MATCH']['xp'], 50)
        self.assertEqual(e['xp_by_source']['ACHIEVEMENT']['xp'], 100)
        self.assertEqual(e['xp_unlogged'], 0)

    def test_glicko_parallel_and_rd_shrinks(self):
        e = explain_player(self.cur, self.ana)
        self.assertGreater(e['glicko']['rating'], 1500)
        self.assertLess(e['glicko']['rd'], 350)
        # El ELO oficial no depende de Glicko
        self.assertEqual(self.engine.get_or_create_global_profile(self.cur, self.ana)['current_rating'], e['rating'])

    def test_legacy_data_is_backfilled(self):
        """Simula datos viejos: sin rival, K, Glicko ni log de XP, y verifica la reconstrucción."""
        before = explain_player(self.cur, self.ana)
        self.cur.execute("""UPDATE academy_rating_history SET opponent_id=NULL, opponent_rating=NULL,
                            expected_score=NULL, k_factor=NULL, result=NULL, glicko_mu=NULL, glicko_phi=NULL""")
        self.cur.execute("UPDATE academy_profiles SET glicko_mu=1500, glicko_phi=350, glicko_sigma=0.06")
        self.cur.execute("DELETE FROM academy_xp_log")
        from database import migrate_academy_schema
        migrate_academy_schema(self.cur)

        after = explain_player(self.cur, self.ana)
        self.assertTrue(all(d['opponent'] == 'Beto' for d in after['duels']))
        self.assertEqual([d['expected_win_pct'] for d in after['duels']],
                         [d['expected_win_pct'] for d in before['duels']])
        self.assertEqual([d['k_factor'] for d in after['duels']], [d['k_factor'] for d in before['duels']])
        self.assertLess(after['glicko']['rd'], 350)
        self.assertAlmostEqual(after['glicko']['rd'], before['glicko']['rd'], places=1)
        self.assertEqual(after['xp_by_source']['MATCH']['xp'], 50)
        self.assertEqual(after['xp_unlogged'], 0)

    def test_text_output(self):
        txt = format_explanation(explain_player(self.cur, self.ana))
        self.assertIn("Ana", txt)
        self.assertIn("vs Beto", txt)


if __name__ == '__main__':
    unittest.main()
