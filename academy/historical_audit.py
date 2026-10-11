import os
import sys
import json
import sqlite3
from collections import defaultdict

# Add parent to path to import database
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_connection
from utils import normalize_player_name

def audit_database():
    print("="*50)
    print("AUDITORÍA HISTÓRICA - SUBARASHII YGO")
    print("="*50)
    
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 1. Jugadores únicos
    cursor.execute("SELECT COUNT(*) as c FROM players")
    total_players = cursor.fetchone()['c']
    
    # Posibles duplicados
    cursor.execute("SELECT id, name FROM players")
    all_players = cursor.fetchall()
    normalized_map = defaultdict(list)
    for p in all_players:
        norm = normalize_player_name(p['name'])
        normalized_map[norm].append(p['name'])
        
    duplicates = {k: v for k, v in normalized_map.items() if len(v) > 1}
    
    # Jugadores sin resultados (que no están en p1_id ni p2_id ni en tournament_results)
    cursor.execute("""
        SELECT COUNT(id) as c FROM players 
        WHERE id NOT IN (SELECT p1_id FROM tournament_matches WHERE p1_id IS NOT NULL)
        AND id NOT IN (SELECT p2_id FROM tournament_matches WHERE p2_id IS NOT NULL)
        AND id NOT IN (SELECT player_id FROM league_profiles)
    """)
    players_no_results = cursor.fetchone()['c']
    
    # 2. Torneos y participaciones
    cursor.execute("SELECT COUNT(*) as c FROM tournaments")
    total_tournaments = cursor.fetchone()['c']
    
    cursor.execute("SELECT COUNT(*) as c FROM tournament_results")
    total_participations = cursor.fetchone()['c']
    
    cursor.execute("SELECT format_name, COUNT(*) as c FROM tournaments GROUP BY format_name")
    formats = cursor.fetchall()
    
    cursor.execute("SELECT MIN(date) as min_d, MAX(date) as max_d FROM tournaments")
    dates = cursor.fetchone()
    
    # Torneos duplicados (misma fecha y formato)
    cursor.execute("SELECT date, format_name, COUNT(*) as c FROM tournaments GROUP BY date, format_name HAVING c > 1")
    dup_tournaments = cursor.fetchall()
    
    # 3. Matches
    cursor.execute("SELECT COUNT(*) as c FROM tournament_matches")
    total_matches = cursor.fetchone()['c']
    
    # BYE y Drops
    cursor.execute("SELECT COUNT(*) as c FROM tournament_matches WHERE p2_id IS NULL AND result_text = 'BYE'")
    total_byes = cursor.fetchone()['c']
    
    cursor.execute("SELECT COUNT(*) as c FROM tournament_matches WHERE result_text LIKE '%Drop%'")
    total_drops = cursor.fetchone()['c']
    
    # Matches incompletos / rotos
    cursor.execute("SELECT COUNT(*) as c FROM tournament_matches WHERE p1_id IS NULL AND p2_id IS NULL")
    broken_matches = cursor.fetchone()['c']
    
    print("\n--- RESUMEN GENERAL ---")
    print(f"Jugadores Únicos: {total_players}")
    print(f"Jugadores sin historial competitivo: {players_no_results}")
    print(f"Posibles jugadores duplicados (similitud de nombre): {len(duplicates)}")
    if duplicates:
        for k, v in duplicates.items():
            print(f"  - {v}")
            
    print(f"\nTorneos: {total_tournaments}")
    print(f"Participaciones totales: {total_participations}")
    print(f"Fechas: {dates['min_d']} a {dates['max_d']}")
    print("Formatos:")
    for f in formats:
        print(f"  - {f['format_name']}: {f['c']} torneos")
        
    if dup_tournaments:
        print("\n¡ALERTA! Posibles torneos duplicados (misma fecha y formato):")
        for dt in dup_tournaments:
            print(f"  - Fecha: {dt['date']}, Formato: {dt['format_name']} ({dt['c']} instancias)")
    
    print(f"\n--- MATCHES ---")
    print(f"Matches totales: {total_matches}")
    print(f"BYEs (Jugadores impares): {total_byes}")
    print(f"Drops reportados: {total_drops}")
    print(f"Matches rotos (Sin jugadores): {broken_matches}")
    
    print("\n--- AUDITORÍA VS JSON HISTÓRICOS ---")
    history_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "history")
    
    if not os.path.exists(history_dir):
        print("No se encontró directorio data/history/ para comparar.")
        return
        
    json_files = [f for f in os.listdir(history_dir) if f.endswith(".json")]
    print(f"Archivos JSON encontrados: {len(json_files)}")
    
    json_tournaments = 0
    json_matches = 0
    
    for jf in json_files:
        path = os.path.join(history_dir, jf)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                json_tournaments += 1
                manager = data.get("manager", {})
                rounds = manager.get("rounds", [])
                for rnd in rounds:
                    json_matches += len(rnd)
        except Exception as e:
            print(f"Error leyendo {jf}: {e}")
            
    print(f"Torneos en JSON: {json_tournaments} | Torneos en SQLite: {total_tournaments}")
    print(f"Matches en JSON: {json_matches} | Matches en SQLite: {total_matches}")
    
    if json_tournaments != total_tournaments:
        print(">> DISCREPANCIA: La cantidad de torneos no coincide.")
    else:
        print(">> INTEGRIDAD: Todos los torneos parecen estar importados.")
        
    if json_matches != total_matches:
        print(">> DISCREPANCIA: La cantidad de matches en JSON difiere de SQLite.")
        print("   (Nota: SQLite puede omitir matches vacíos o sin terminar del JSON).")
    else:
        print(">> INTEGRIDAD MATCHES: OK.")
        
    conn.close()
    
    return {
        "total_players": total_players,
        "total_matches": total_matches,
        "total_tournaments": total_tournaments,
        "discrepancies": json_tournaments != total_tournaments
    }

if __name__ == "__main__":
    audit_database()
