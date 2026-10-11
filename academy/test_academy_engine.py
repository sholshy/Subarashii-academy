import unittest
import sqlite3
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from academy.academy_engine import AcademyEngine
from database import init_db, get_connection

class TestAcademyEngine(unittest.TestCase):
    def setUp(self):
        self.db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "test_engine.db")
        # Override the database path for tests
        import database
        database.DB_PATH = self.db_path
        
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
            
        init_db()
        self.conn = get_connection()
        self.cursor = self.conn.cursor()
        
        # Insert test players
        self.cursor.execute("INSERT INTO players (name, slug) VALUES ('Player 1', 'p1')")
        self.p1_id = self.cursor.lastrowid
        self.cursor.execute("INSERT INTO players (name, slug) VALUES ('Player 2', 'p2')")
        self.p2_id = self.cursor.lastrowid
        
        # Insert store
        self.cursor.execute("INSERT INTO stores (name) VALUES ('Test Store')")
        self.store_id = self.cursor.lastrowid
        
        # Insert dummy tournament and match
        self.cursor.execute("INSERT INTO tournaments (store_id, format_name, date) VALUES (?, 'GLOBAL', '2026-08-12')", (self.store_id,))
        self.tournament_id = self.cursor.lastrowid
        self.cursor.execute("INSERT INTO tournament_matches (tournament_id, p1_id, p2_id, round_num, result_text) VALUES (?, ?, ?, 1, 'p1 win')", (self.tournament_id, self.p1_id, self.p2_id))
        self.match_id = self.cursor.lastrowid
        
        self.engine = AcademyEngine(store_id=self.store_id)
        
    def tearDown(self):
        self.conn.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
            
    def test_global_profile_creation(self):
        prof = self.engine.get_or_create_global_profile(self.cursor, self.p1_id)
        self.assertEqual(prof['current_rating'], 1000)
        self.assertEqual(prof['xp'], 0)
        self.assertEqual(prof['level'], 1)
        
        # Should not create duplicate
        prof2 = self.engine.get_or_create_global_profile(self.cursor, self.p1_id)
        self.assertEqual(prof['id'], prof2['id'])
        
        self.cursor.execute("SELECT count(*) as c FROM academy_profiles WHERE player_id = ? AND format_name = 'GLOBAL'", (self.p1_id,))
        self.assertEqual(self.cursor.fetchone()['c'], 1)
        
    def test_process_match(self):
        self.engine.process_match(self.cursor, self.match_id, self.p1_id, self.p2_id, 1) # p1 wins
        self.conn.commit()
        
        prof1 = self.engine.get_or_create_global_profile(self.cursor, self.p1_id)
        prof2 = self.engine.get_or_create_global_profile(self.cursor, self.p2_id)
        
        # K=64, both are 1000 ELO -> expected = 0.5 -> delta = 64 * 0.5 = 32
        self.assertEqual(prof1['current_rating'], 1032)
        self.assertEqual(prof2['current_rating'], 968)
        
        self.assertEqual(prof1['matches_played'], 1)
        self.assertEqual(prof2['matches_played'], 1)
        
        # XP: p1 wins -> 5 (match) + 10 (win) = 15 XP
        # + logros ACH_FIRST_MATCH (50) + ACH_FIRST_WIN (50) = 115
        # p2 loses -> 5 (match) + ACH_FIRST_MATCH (50) = 55
        self.assertEqual(prof1['xp'], 115)
        self.assertEqual(prof2['xp'], 55)

if __name__ == '__main__':
    unittest.main()
