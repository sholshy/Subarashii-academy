import os
import json
import sqlite3
from datetime import datetime
from database import get_connection
from utils import normalize_player_name

def migrate_history(db_path=None, specific_file=None):
    print("Starting historical migration...")
    conn = get_connection() if not db_path else sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    history_dir = os.path.join("data", "history")
    if not os.path.exists(history_dir):
        print("No historical data found.")
        return
        
    # Get active store (fallback to first if none active)
    cursor.execute("SELECT id FROM stores WHERE is_active = 1")
    store_row = cursor.fetchone()
    if not store_row:
        cursor.execute("SELECT id FROM stores LIMIT 1")
        store_row = cursor.fetchone()
        
    if not store_row:
        print("No stores found in DB. Please create a store first.")
        return
        
    store_id = store_row['id']
    
    if specific_file:
        files = [specific_file]
    else:
        files = [f for f in os.listdir(history_dir) if f.endswith(".json")]
    print(f"Found {len(files)} historical tournament files.")
    
    for filename in sorted(files):
        file_path = os.path.join(history_dir, filename)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"Error reading {filename}: {e}")
            continue
            
        manager_data = data.get('manager', {})
        ui_data = data.get('ui', {})
        
        # Determine format and date
        format_name = ui_data.get('format') or manager_data.get('format_name', 'GOAT')
        date_str = ui_data.get('date', '')
        
        # Check if this tournament already exists based on date and format to avoid duplicates.
        # This is basic, might need a better unique identifier in the future.
        cursor.execute("SELECT id FROM tournaments WHERE date = ? AND format_name = ?", (date_str, format_name))
        existing_tournament = cursor.fetchone()
        if existing_tournament:
            print(f"Tournament {filename} ({date_str} - {format_name}) might already be imported. Skipping.")
            continue
            
        print(f"Importing {filename}...")
        
        # 1. Register Tournament
        cursor.execute('''
            INSERT INTO tournaments (store_id, format_name, date, mode, profit)
            VALUES (?, ?, ?, ?, ?)
        ''', (store_id, format_name, date_str, manager_data.get('mode', 'swiss'), manager_data.get('tournament_profit', 0.0)))
        
        tournament_id = cursor.lastrowid
        
        # 2. Register/Map Players
        players_data = manager_data.get('players', [])
        player_id_map = {} # Maps json player index to db player id
        
        for idx, p_data in enumerate(players_data):
            raw_name = p_data.get('name', '')
            norm_name = normalize_player_name(raw_name)
            if not norm_name:
                continue
                
            konami_id = p_data.get('konami_id', '')
            if not konami_id:
                konami_id = None
            
            # Find existing player
            cursor.execute("SELECT id FROM players WHERE LOWER(REPLACE(name, ' ', '')) = ?", (norm_name.replace(' ', ''),))
            existing_player = cursor.fetchone()
            
            if existing_player:
                p_id = existing_player['id']
            else:
                cursor.execute("INSERT INTO players (name, konami_id) VALUES (?, ?)", (raw_name, konami_id))
                p_id = cursor.lastrowid
                
            player_id_map[idx] = p_id
            
            # Ensure league profile exists
            cursor.execute("SELECT id FROM league_profiles WHERE player_id = ? AND store_id = ? AND format_name = ?", 
                           (p_id, store_id, format_name))
            profile = cursor.fetchone()
            if not profile:
                cursor.execute("INSERT INTO league_profiles (player_id, store_id, format_name) VALUES (?, ?, ?)",
                               (p_id, store_id, format_name))
                profile_id = cursor.lastrowid
            else:
                profile_id = profile['id']
                
            # Add tournament result entry
            try:
                cursor.execute('''
                    INSERT INTO tournament_results (tournament_id, league_profile_id, match_points)
                    VALUES (?, ?, ?)
                ''', (tournament_id, profile_id, p_data.get('points', 0)))
            except sqlite3.IntegrityError:
                pass # Already inserted
        
        # 3. Register Matches
        rounds = manager_data.get('rounds', [])
        for round_idx, round_matches in enumerate(rounds):
            round_num = round_idx + 1
            for match in round_matches:
                p1_idx = match.get('p1')
                p2_idx = match.get('p2')
                
                p1_id = player_id_map.get(p1_idx)
                p2_id = player_id_map.get(p2_idx)
                
                result_text = match.get('result_text', '')
                note = match.get('note', '')
                
                cursor.execute('''
                    INSERT INTO tournament_matches (tournament_id, p1_id, p2_id, round_num, result_text, note)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (tournament_id, p1_id, p2_id, round_num, result_text, note))
                
        conn.commit()
        if specific_file:
            conn.close()
            return tournament_id
        
    print("Migration completed.")
    conn.close()

if __name__ == "__main__":
    migrate_history()
