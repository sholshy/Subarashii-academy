import sqlite3
from database import get_connection

def recalculate_academy_stats():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get all academy profiles
    cursor.execute("SELECT id, player_id, store_id, format_name FROM academy_profiles")
    profiles = cursor.fetchall()
    
    for prof in profiles:
        prof_id = prof['id']
        pid = prof['player_id']
        
        # Count directly from academy_rating_history (matches actually processed in Academy)
        cursor.execute("""
            SELECT COUNT(*) AS mp,
                   COALESCE(SUM(CASE WHEN result = 1.0 THEN 1 WHEN result IS NULL AND rating_change > 0 THEN 1 ELSE 0 END), 0) AS w,
                   COALESCE(SUM(CASE WHEN result = 0.0 THEN 1 WHEN result IS NULL AND rating_change < 0 THEN 1 ELSE 0 END), 0) AS l
            FROM academy_rating_history
            WHERE academy_profile_id = ? AND reason = 'MATCH_RESULT'
        """, (prof_id,))
        row = cursor.fetchone()
        matches_played, wins, losses = row['mp'], row['w'], row['l']
        
        cursor.execute("UPDATE academy_profiles SET matches_played=?, wins=?, losses=? WHERE id=?", (matches_played, wins, losses, prof_id))
    
    conn.commit()
    print("Stats recalculated successfully.")

if __name__ == "__main__":
    recalculate_academy_stats()
