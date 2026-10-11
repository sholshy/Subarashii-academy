import os
import json
import csv
from database import get_connection, init_db

def migrate():
    # Initialize schema
    init_db()
    conn = get_connection()
    cursor = conn.cursor()

    data_dir = "data"
    stores_file = os.path.join(data_dir, "stores.json")
    global_players_db = "players_db.csv"

    # 1. Migrate stores
    stores_list = ["Tienda Principal"]
    active_store = "Tienda Principal"
    if os.path.exists(stores_file):
        with open(stores_file, "r", encoding="utf-8") as f:
            raw = json.load(f)
            if isinstance(raw, dict):
                stores_list = raw.get("stores", [])
                active_store = raw.get("active_store", stores_list[0] if stores_list else "Tienda Principal")
            else:
                stores_list = raw

    store_name_to_id = {}
    for s_name in stores_list:
        cursor.execute("INSERT OR IGNORE INTO stores (name, is_active) VALUES (?, ?)", (s_name, s_name == active_store))
        cursor.execute("SELECT id FROM stores WHERE name = ?", (s_name,))
        store_name_to_id[s_name] = cursor.fetchone()['id']

    # 2. Migrate global players (from players_db.csv)
    # We will track names to player_ids to help league profiles map to the right player
    name_to_player_id = {}

    if os.path.exists(global_players_db):
        with open(global_players_db, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 2:
                    name = row[0].strip()
                    k_id = row[1].strip()
                    if not name:
                        continue
                    if not k_id:
                        k_id = None
                    phone = row[2].strip() if len(row) > 2 else ""
                    email = row[3].strip() if len(row) > 3 else ""

                    try:
                        cursor.execute(
                            "INSERT INTO players (konami_id, name, phone, email) VALUES (?, ?, ?, ?)",
                            (k_id, name, phone, email)
                        )
                        player_id = cursor.lastrowid
                        name_to_player_id[name.lower()] = player_id
                    except sqlite3.IntegrityError:
                        # If Konami ID already exists, fetch it
                        cursor.execute("SELECT id FROM players WHERE konami_id = ?", (k_id,))
                        row = cursor.fetchone()
                        if row:
                            name_to_player_id[name.lower()] = row['id']

    # 3. Migrate league profiles and history
    for s_name in stores_list:
        s_id = store_name_to_id[s_name]
        league_file = os.path.join(data_dir, "stores", s_name, "league_data.json")
        
        if not os.path.exists(league_file):
            continue
            
        with open(league_file, "r", encoding="utf-8") as f:
            try:
                raw_data = json.load(f)
            except:
                continue

            # In newer structure, we have "GOAT": {"players": [...]}, etc.
            # In older, it might just be "players": [...]
            formats_to_process = {}
            if "players" in raw_data:
                formats_to_process["GOAT"] = raw_data.get("players", [])
            else:
                for fmt in ["GOAT", "EDISON", "Speed Duel"]:
                    formats_to_process[fmt] = raw_data.get(fmt, {}).get("players", [])

            for fmt_name, players in formats_to_process.items():
                for p_data in players:
                    p_name = p_data.get("name", "").strip()
                    if not p_name:
                        continue

                    p_name_lower = p_name.lower()
                    
                    # Ensure player exists globally
                    if p_name_lower not in name_to_player_id:
                        p_phone = p_data.get("phone", "")
                        p_email = p_data.get("email", "")
                        cursor.execute("INSERT INTO players (name, phone, email) VALUES (?, ?, ?)", (p_name, p_phone, p_email))
                        name_to_player_id[p_name_lower] = cursor.lastrowid
                        
                    p_id = name_to_player_id[p_name_lower]

                    deck = p_data.get("deck_name", "")
                    signature = p_data.get("signature_card", "")

                    # Create League Profile
                    cursor.execute('''
                        INSERT OR IGNORE INTO league_profiles (player_id, store_id, format_name, deck_name, signature_card)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (p_id, s_id, fmt_name, deck, signature))
                    
                    cursor.execute('''
                        SELECT id FROM league_profiles WHERE player_id = ? AND store_id = ? AND format_name = ?
                    ''', (p_id, s_id, fmt_name))
                    lp_row = cursor.fetchone()
                    if not lp_row: continue
                    lp_id = lp_row['id']

                    # Migrate history
                    history = p_data.get("history", [])
                    # Fallback for bingo history if stored separately
                    bingo_history = p_data.get("bingo_history", [])

                    for idx, week in enumerate(history):
                        date_str = week.get("date", f"Week {idx+1}")
                        match_pts = week.get("match_points", 0)
                        placement_pts = week.get("placement_points", 0)
                        attendance = bool(week.get("attendance", True))
                        
                        bingo_grid = week.get("bingo_grid")
                        if not bingo_grid and idx < len(bingo_history):
                            bingo_grid = bingo_history[idx].get("bingo_grid")
                            
                        bingo_json = json.dumps(bingo_grid) if bingo_grid else None
                        
                        # Create a generic tournament for this week if not exists
                        cursor.execute('''
                            SELECT id FROM tournaments WHERE store_id = ? AND format_name = ? AND date = ?
                        ''', (s_id, fmt_name, date_str))
                        t_row = cursor.fetchone()
                        
                        if not t_row:
                            cursor.execute('''
                                INSERT INTO tournaments (store_id, format_name, date, mode) VALUES (?, ?, ?, ?)
                            ''', (s_id, fmt_name, date_str, "swiss"))
                            t_id = cursor.lastrowid
                        else:
                            t_id = t_row['id']
                            
                        # Insert tournament result
                        cursor.execute('''
                            INSERT OR IGNORE INTO tournament_results 
                            (tournament_id, league_profile_id, match_points, placement_points, attendance, bingo_grid)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (t_id, lp_id, match_pts, placement_pts, attendance, bingo_json))

    conn.commit()
    conn.close()
    print("Migración completada exitosamente.")

if __name__ == "__main__":
    import sqlite3
    migrate()
