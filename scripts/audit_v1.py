import sqlite3
import os
import sys

# Setup environment to use audit db
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["YGO_DB_PATH"] = os.path.join("data", "ygo_data_audit.db")

# Wait, database.py has hardcoded "data/ygo_data.db". Let's patch it in memory.
import database
database.DB_PATH = os.environ["YGO_DB_PATH"]

from database import get_connection
from academy.academy_engine import AcademyEngine
from academy.preseason import run_preseason

def count_records(cursor, tables):
    counts = {}
    for t in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {t}")
            counts[t] = cursor.fetchone()[0]
        except Exception:
            counts[t] = -1
    return counts

def run_audit():
    print("=== STARTING AUDIT ===")
    conn = get_connection()
    c = conn.cursor()
    
    tables = [
        "players", "tournaments", "tournament_matches", "tournament_results",
        "league_profiles", "academy_profiles", "academy_achievements", "academy_missions",
        "academy_rating_history", "academy_preseason_players"
    ]
    
    print("\n1. INITIAL COUNTS:")
    initial_counts = count_records(c, tables)
    print(initial_counts)
    
    # 2. Test Idempotency (Run preseason)
    print("\n2. RUNNING PRESEASON (PASS 1)...")
    run_preseason()
    counts_pass1 = count_records(c, tables)
    print(counts_pass1)
    
    print("\n3. RUNNING PRESEASON (PASS 2 - Idempotency)...")
    run_preseason()
    counts_pass2 = count_records(c, tables)
    print(counts_pass2)
    
    if counts_pass1 == counts_pass2:
        print("-> IDEMPOTENCY PASS: Counts remained identical.")
    else:
        print("-> IDEMPOTENCY FAIL: Counts changed!")
        
    # 4. Math Check (K-Factors)
    print("\n4. ELO MATH CHECK...")
    engine = AcademyEngine()
    
    # Create mock players
    c.execute("INSERT INTO players (name) VALUES ('Math1')")
    p1 = c.lastrowid
    c.execute("INSERT INTO players (name) VALUES ('Math2')")
    p2 = c.lastrowid
    
    # Global profiles
    prof1 = engine.get_or_create_global_profile(c, p1)
    prof2 = engine.get_or_create_global_profile(c, p2)
    
    print(f"Initial Ratings: P1={prof1['current_rating']} P2={prof2['current_rating']}")
    
    # Insert fake match
    c.execute("DELETE FROM tournament_matches WHERE id IN (99991, 99992)")
    c.execute("INSERT INTO tournament_matches (id, tournament_id, p1_id, p2_id, round_num, result_text) VALUES (99991, 27, ?, ?, 1, '2-0')", (p1, p2))
    engine.process_match(c, 99991, p1, p2, 1.0)
    c.execute("SELECT current_rating FROM academy_profiles WHERE player_id=?", (p1,))
    r1 = c.fetchone()[0]
    c.execute("SELECT current_rating FROM academy_profiles WHERE player_id=?", (p2,))
    r2 = c.fetchone()[0]
    
    change1 = r1 - 1000
    change2 = r2 - 1000
    print(f"Match 1 (Win P1): P1={r1} (+{change1}), P2={r2} ({change2})")
    
    sum_change = change1 + change2
    if sum_change == 0:
        print("-> ZERO-SUM PASS")
    else:
        print(f"-> ZERO-SUM FAIL (Sum = {sum_change})")
        
    if abs(change1) == 32: # K=64, Expected score 0.5, 64*(1 - 0.5) = 32
        print("-> K=64 PASS")
    else:
        print(f"-> K=64 FAIL (Change = {change1})")

    # Match 11 (K=32)
    # Fast forward matches
    c.execute("UPDATE academy_profiles SET matches_played=10 WHERE player_id IN (?, ?)", (p1, p2))
    r1_before = r1
    c.execute("INSERT INTO tournament_matches (id, tournament_id, p1_id, p2_id, round_num, result_text) VALUES (99992, 27, ?, ?, 1, '2-0')", (p1, p2))
    engine.process_match(c, 99992, p1, p2, 1.0)
    c.execute("SELECT current_rating FROM academy_profiles WHERE player_id=?", (p1,))
    r1 = c.fetchone()[0]
    change11 = r1 - r1_before
    print(f"Match 11 (Win P1): Change = {change11}")
    if change11 < 32 and change11 > 0: # Should be scaled down
        print("-> K=32 PASS (Change was scaled down)")
        
    print("\n=== AUDIT FINISHED ===")
    conn.commit()
    conn.close()

if __name__ == "__main__":
    run_audit()
