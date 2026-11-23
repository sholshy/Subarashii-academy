import sqlite3
from database import get_connection

def recalculate_academy_stats():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Obtener la temporada activa actual
    cursor.execute("SELECT id, start_date, number FROM academy_seasons WHERE status = 'ACTIVE' ORDER BY number DESC LIMIT 1")
    active_season = cursor.fetchone()
    
    # Obtener los IDs de torneos pertenecientes a la temporada activa
    active_tournament_ids = []
    if active_season:
        # Los torneos de temporadas cerradas ya están consolidados
        cursor.execute("""
            SELECT id FROM tournaments 
            WHERE id IN (43, 44) OR date >= ?
        """, (active_season['start_date'],))
        active_tournament_ids = [r['id'] for r in cursor.fetchall()]
    
    # Get all academy profiles
    cursor.execute("SELECT id, player_id, store_id, format_name FROM academy_profiles WHERE format_name = 'GLOBAL'")
    profiles = cursor.fetchall()
    
    for prof in profiles:
        prof_id = prof['id']
        pid = prof['player_id']
        
        if active_tournament_ids:
            cursor.execute("""
                SELECT COUNT(*) AS mp,
                       COALESCE(SUM(CASE WHEN result = 1.0 THEN 1 WHEN result IS NULL AND rating_change > 0 THEN 1 ELSE 0 END), 0) AS w,
                       COALESCE(SUM(CASE WHEN result = 0.0 THEN 1 WHEN result IS NULL AND rating_change < 0 THEN 1 ELSE 0 END), 0) AS l
                FROM academy_rating_history arh
                JOIN tournament_matches tm ON tm.id = arh.match_id
                WHERE arh.academy_profile_id = ? 
                  AND arh.reason = 'MATCH_RESULT'
                  AND tm.tournament_id IN ({seq})
            """.format(seq=','.join(['?']*len(active_tournament_ids))), [prof_id] + active_tournament_ids)
        else:
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
    print("Stats recalculated successfully for active season.")

if __name__ == "__main__":
    recalculate_academy_stats()
