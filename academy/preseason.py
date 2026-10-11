import os
import sys
import sqlite3

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_connection
from academy.academy_engine import AcademyEngine

def run_preseason():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    engine = AcademyEngine()

    print("Iniciando procesamiento de Pretemporada...")

    # Obtener todos los torneos cronológicamente (soportando DD-MM-YY y YYYY-MM-DD)
    cursor.execute("""
        SELECT id, date, format_name FROM tournaments
        WHERE id IN (SELECT DISTINCT tournament_id FROM tournament_matches WHERE result_text IN ('P1_WIN', 'P2_WIN', 'DRAW'))
          AND id NOT IN (SELECT DISTINCT tournament_id FROM tournament_matches WHERE result_text = 'Pendiente')
        ORDER BY
            CASE WHEN substr(date, 3, 1) = '-' AND substr(date, 6, 1) = '-'
                 THEN '20' || substr(date, 7, 2) || '-' || substr(date, 4, 2) || '-' || substr(date, 1, 2)
                 ELSE date END ASC,
            id ASC
    """)
    tournaments = cursor.fetchall()

    for t in tournaments:
        t_id = t['id']
        print(f"Procesando Torneo ID {t_id} (Fecha: {t['date']})...")

        # Empezar transacción para el torneo
        cursor.execute("BEGIN TRANSACTION")
        try:
            # Obtener matches del torneo
            cursor.execute("""
                SELECT id, p1_id, p2_id, result_text 
                FROM tournament_matches 
                WHERE tournament_id = ? AND p1_id IS NOT NULL AND p2_id IS NOT NULL
                ORDER BY round_num ASC, id ASC
            """, (t_id,))
            matches = cursor.fetchall()

            for m in matches:
                p1_id = m['p1_id']
                p2_id = m['p2_id']
                m_id = m['id']
                res = m['result_text']
                
                # Ignorar BYEs y Drops que no son partidas reales
                if 'BYE' in res or 'Drop' in res:
                    continue

                # Parse result
                if res == 'P1_WIN':
                    p1_score = 1.0
                elif res == 'P2_WIN':
                    p1_score = 0.0
                elif res == 'DRAW':
                    p1_score = 0.5
                else:
                    continue
                    
                # Verificar idempotencia a nivel de torneo para ambos jugadores
                # Si el jugador ya tiene el torneo marcado como procesado, omitimos sus updates.
                # Para ello, lo ideal es verificar al procesar el match si ya se procesó.
                
                # Check p1
                cursor.execute("SELECT id FROM academy_preseason_players WHERE tournament_id=? AND player_id=?", (t_id, p1_id))
                p1_processed = cursor.fetchone() is not None
                
                # Check p2
                cursor.execute("SELECT id FROM academy_preseason_players WHERE tournament_id=? AND player_id=?", (t_id, p2_id))
                p2_processed = cursor.fetchone() is not None
                
                # Si ambos están procesados, skip match
                if p1_processed and p2_processed:
                    continue
                    
                # Si no están procesados, procesamos el match y la XP
                # En Preseason asimilamos que ELO afecta a ambos. Si uno ya fue procesado (raro, a menos que haya un error), 
                # saltamos ELO para no desbalancear. Lo mejor es asegurar que procesamos por torneos enteros.
                if not p1_processed and not p2_processed:
                    engine.process_match(cursor, m_id, p1_id, p2_id, p1_score, timestamp=t['date'])

            # Otorgar recompensas de posición del torneo y marcar como procesados
            # Para esto necesitamos los resultados del torneo
            cursor.execute("""
                SELECT league_profile_id, placement_points, attendance 
                FROM tournament_results 
                WHERE tournament_id = ?
            """, (t_id,))
            results = cursor.fetchall()

            for r in results:
                lp_id = r['league_profile_id']
                
                # Obtener player_id
                cursor.execute("SELECT player_id FROM league_profiles WHERE id=?", (lp_id,))
                lp_row = cursor.fetchone()
                if not lp_row: continue
                player_id = lp_row['player_id']
                
                # Verificar si ya fue procesado
                cursor.execute("SELECT id FROM academy_preseason_players WHERE tournament_id=? AND player_id=?", (t_id, player_id))
                if cursor.fetchone():
                    continue # Ya se le dio XP y recompensas
                    
                prof = engine.get_or_create_global_profile(cursor, player_id)
                
                # XP por participación
                xp_gain = 25
                
                # XP por posición
                pos = r['placement_points'] # Asumimos placement_points = ranking
                if pos == 1: xp_gain += 150
                elif pos == 2: xp_gain += 100
                elif pos in [3, 4]: xp_gain += 75
                elif 5 <= pos <= 8: xp_gain += 50
                
                engine.add_xp(cursor, prof['id'], prof['xp'], xp_gain, source='TOURNAMENT', ref_id=t_id,
                              description=f"Participación en torneo #{t_id} (pretemporada)" + (f", puesto {pos}" if pos and pos > 0 else ""))
                
                if pos > 0:
                    engine.evaluate_tournament_achievements(cursor, prof['id'], pos)
                    
                engine.evaluate_tournament_missions(cursor, prof['id'])
                
                # Marcar como procesado en Preseason
                cursor.execute("INSERT INTO academy_preseason_players (tournament_id, player_id, processed) VALUES (?, ?, 1)", (t_id, player_id))

            cursor.execute("COMMIT")
            print(f"Torneo {t_id} procesado y guardado exitosamente.")
        except Exception as e:
            cursor.execute("ROLLBACK")
            print(f"Error procesando el torneo {t_id}: {e}")
            raise e
            
    # Al final, iterar sobre todos los perfiles globales y asignar el Dormitorio oficial basado en el ELO
    cursor.execute("SELECT id, current_rating, matches_played FROM academy_profiles WHERE format_name='GLOBAL'")
    profiles = cursor.fetchall()
    
    print("Asignando dormitorios finales de Pretemporada y Logros Retroactivos...")
    for p in profiles:
        matches = p['matches_played']
        rating = p['current_rating']
        
        # Estado de clasificación: 0-9 matches = ESTUDIANTE DE INTERCAMBIO
        if matches < 10:
            dorm = "Estudiante de Intercambio"
        else:
            dorm = engine.get_dormitory(rating)
            
        cursor.execute("UPDATE academy_profiles SET dorm=? WHERE id=?", (dorm, p['id']))
        
        # Retroactive achievements check
        # We can just call evaluate_match_achievements with dummy data to force a check
        engine.evaluate_match_achievements(cursor, p['id'], is_win=False, old_rating=rating, new_rating=rating)
        
    conn.commit()
    conn.close()
    print("Pretemporada finalizada exitosamente. Todos los datos históricos están asegurados.")


def rebuild_all_academy(sync_and_publish=True):
    """
    Reconstruye desde cero todos los datos de Academy en orden cronológico real:
    - Fusiona jugadores duplicados conocidos (ej. Jhoan Loza -> Johan Loza).
    - Limpia perfiles/historial/logros/misiones/XP de Academy y reprocesa todos los
      torneos finalizados (sin partidas 'Pendiente') ordenados por fecha real.
    - Deja ELO, Glicko-2, K-factors, dormitorios y XP 100% consistentes.
    """
    from database import merge_players_db, migrate_academy_schema

    conn = get_connection()
    cursor = conn.cursor()
    migrate_academy_schema(cursor)

    # 1. Fusionar duplicado Jhoan Loza (72) -> Johan Loza (15) si ambos existen
    cursor.execute("SELECT id FROM players WHERE id IN (15, 72)")
    ids = {r['id'] for r in cursor.fetchall()}
    conn.close()
    if 15 in ids and 72 in ids:
        merge_players_db(15, [72])

    # 2. Limpiar tablas derivadas de Academy para reprocesar en orden cronológico exacto
    conn = get_connection()
    cursor = conn.cursor()
    for tbl in (
        "academy_xp_log",
        "academy_rating_history",
        "academy_achievements",
        "academy_missions",
        "academy_preseason_players",
        "academy_profiles",
    ):
        cursor.execute(f"DELETE FROM {tbl}")
    conn.commit()
    conn.close()

    # 3. Reprocesar todos los torneos válidos en orden cronológico
    run_preseason()

    # 4. Opcionalmente regenerar y publicar el snapshot web
    if sync_and_publish:
        from academy.sync_manager import SyncManager
        conn = get_connection()
        sync = SyncManager()
        sync.generate_snapshot_and_manifest(conn.cursor())
        conn.commit()
        conn.close()
        sync.publish()


if __name__ == "__main__":
    run_preseason()
