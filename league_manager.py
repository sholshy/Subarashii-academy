import json
import sqlite3
from database import get_connection

class LeaguePlayer:
    def __init__(self, name, deck_name="", signature_card="", phone="", email="", history=None):
        self.name = name
        self.deck_name = deck_name
import json
import sqlite3
from database import get_connection

class LeaguePlayer:
    def __init__(self, name, deck_name="", signature_card="", phone="", email="", history=None):
        self.name = name
        self.deck_name = deck_name
        self.signature_card = signature_card
        self.phone = phone
        self.email = email
        self.history = history if history else []

    def get_points_composition(self, include_missions=True, include_attendance=True):
        placement_points = 0
        attendance_points = 0
        mission_points = 0
        bingo_count = 0

        for week in self.history:
            placement_points += week.get('placement_points', 0)
            
            if include_attendance and week.get('attendance'):
                attendance_points += 5
                
            if 'bingo_grid' in week and week['bingo_grid']:
                grid = week['bingo_grid']
                lines = 0
                if all(grid[0:3]): lines += 1
                if all(grid[3:6]): lines += 1
                if all(grid[6:9]): lines += 1
                if grid[0] and grid[3] and grid[6]: lines += 1
                if grid[1] and grid[4] and grid[7]: lines += 1
                if grid[2] and grid[5] and grid[8]: lines += 1
                if grid[0] and grid[4] and grid[8]: lines += 1
                if grid[2] and grid[4] and grid[6]: lines += 1
                mission_points += lines * 3
                if all(grid):
                    mission_points += 5
                    bingo_count += 1
                    
        if not include_missions:
            mission_points = 0
            bingo_count = 0

        return placement_points, attendance_points, mission_points, bingo_count

    def get_total_points(self, include_missions=True, include_attendance=True):
        p, a, miss, _ = self.get_points_composition(include_missions, include_attendance)
        return p + a + miss

class LeagueManager:
    def __init__(self, db_path=None, current_format="GOAT"):
        self.current_format = current_format
        self.db_path = db_path
        self.conn = get_connection()
        self.cursor = self.conn.cursor()
        
    @property
    def players(self):
        self.cursor.execute("SELECT id FROM stores WHERE is_active = 1")
        row = self.cursor.fetchone()
        if not row: return []
        store_id = row['id']
        
        self.cursor.execute('''
            SELECT p.name, p.phone, p.email, lp.id as lp_id, lp.deck_name, lp.signature_card 
            FROM league_profiles lp
            JOIN players p ON lp.player_id = p.id
            WHERE lp.store_id = ? AND lp.format_name = ?
        ''', (store_id, self.current_format))
        
        profiles = self.cursor.fetchall()
        players_list = []
        for prof in profiles:
            lp_id = prof['lp_id']
            self.cursor.execute('''
                SELECT t.id as t_id, t.date, tr.match_points, tr.placement_points, tr.attendance, tr.bingo_grid
                FROM tournament_results tr
                JOIN tournaments t ON tr.tournament_id = t.id
                WHERE tr.league_profile_id = ?
                ORDER BY t.date ASC
            ''', (lp_id,))
            history_rows = self.cursor.fetchall()
            history = []
            for h in history_rows:
                bg = h['bingo_grid']
                history.append({
                    "tournament_id": h['t_id'],
                    "date": h['date'],
                    "match_points": h['match_points'],
                    "placement_points": h['placement_points'],
                    "attendance": bool(h['attendance']),
                    "bingo_grid": json.loads(bg) if bg else [False]*9
                })
            
            p_obj = LeaguePlayer(
                name=prof['name'],
                deck_name=prof['deck_name'] or "",
                signature_card=prof['signature_card'] or "",
                phone=prof['phone'] or "",
                email=prof['email'] or "",
                history=history
            )
            players_list.append(p_obj)
            
        return players_list

    def reset_league(self):
        self.cursor.execute("SELECT id FROM stores WHERE is_active = 1")
        store_row = self.cursor.fetchone()
        if not store_row: return
        store_id = store_row['id']

        self.cursor.execute('''
            DELETE FROM tournament_results 
            WHERE tournament_id IN (
                SELECT id FROM tournaments WHERE store_id = ? AND format_name = ?
            )
        ''', (store_id, self.current_format))
        
        self.cursor.execute('''
            DELETE FROM tournaments 
            WHERE store_id = ? AND format_name = ?
        ''', (store_id, self.current_format))
        
        self.conn.commit()

    def update_player_info(self, name, deck_name, signature_card, phone="", email=""):
        self.cursor.execute("SELECT id FROM stores WHERE is_active = 1")
        store_id = self.cursor.fetchone()['id']
        
        self.cursor.execute("SELECT id FROM players WHERE name = ?", (name,))
        p_row = self.cursor.fetchone()
        if not p_row:
            self.cursor.execute("INSERT INTO players (name, phone, email) VALUES (?, ?, ?)", (name, phone, email))
            p_id = self.cursor.lastrowid
        else:
            p_id = p_row['id']
            self.cursor.execute("UPDATE players SET phone = ?, email = ? WHERE id = ?", (phone, email, p_id))
            
        self.cursor.execute('''
            INSERT INTO league_profiles (player_id, store_id, format_name, deck_name, signature_card)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(player_id, store_id, format_name) 
            DO UPDATE SET deck_name=excluded.deck_name, signature_card=excluded.signature_card
        ''', (p_id, store_id, self.current_format, deck_name, signature_card))
        
        self.conn.commit()

    def remove_player(self, name):
        self.cursor.execute("SELECT id FROM stores WHERE is_active = 1")
        store_row = self.cursor.fetchone()
        if not store_row: return
        store_id = store_row['id']

        self.cursor.execute("SELECT id FROM players WHERE name = ?", (name,))
        p_row = self.cursor.fetchone()
        if not p_row: return
        
        self.cursor.execute('''
            DELETE FROM league_profiles WHERE player_id = ? AND store_id = ? AND format_name = ?
        ''', (p_row['id'], store_id, self.current_format))
        self.conn.commit()

    def get_player(self, name):
        for p in self.players:
            if p.name.lower() == name.lower():
                return p
        return None

    def export_tournament_results(self, date_str, results_list, profit=0.0):
        self.cursor.execute("SELECT id FROM stores WHERE is_active = 1")
        store_row = self.cursor.fetchone()
        if not store_row: return
        store_id = store_row['id']
        
        self.cursor.execute('''
            INSERT INTO tournaments (store_id, format_name, date, mode, profit)
            VALUES (?, ?, ?, 'swiss', ?)
        ''', (store_id, self.current_format, date_str, profit))
        tournament_id = self.cursor.lastrowid
        
        for res in results_list:
            name = res['name']
            self.cursor.execute("SELECT id FROM league_profiles WHERE player_id IN (SELECT id FROM players WHERE name = ?) AND format_name = ? AND store_id = ?", (name, self.current_format, store_id))
            prof = self.cursor.fetchone()
            if not prof:
                self.cursor.execute("SELECT id FROM players WHERE name = ?", (name,))
                player_row = self.cursor.fetchone()
                if not player_row:
                    self.cursor.execute("INSERT INTO players (name, phone, email) VALUES (?, ?, ?)", (name, res.get('phone',''), res.get('email','')))
                    player_id = self.cursor.lastrowid
                else:
                    player_id = player_row['id']
                    if res.get('phone') or res.get('email'):
                        self.cursor.execute("UPDATE players SET phone=COALESCE(?, phone), email=COALESCE(?, email) WHERE id=?", (res.get('phone') or None, res.get('email') or None, player_id))
                
                self.cursor.execute("INSERT INTO league_profiles (player_id, store_id, format_name) VALUES (?, ?, ?)", (player_id, store_id, self.current_format))
                profile_id = self.cursor.lastrowid
            else:
                profile_id = prof['id']
                if res.get('phone') or res.get('email'):
                    self.cursor.execute('''
                        UPDATE players SET phone=COALESCE(?, phone), email=COALESCE(?, email) 
                        WHERE id = (SELECT player_id FROM league_profiles WHERE id = ?)
                    ''', (res.get('phone') or None, res.get('email') or None, profile_id))
            
            self.cursor.execute('''
                INSERT INTO tournament_results (tournament_id, league_profile_id, match_points, placement_points, attendance)
                VALUES (?, ?, ?, ?, 1)
            ''', (tournament_id, profile_id, res['match_pts'], res['placement_points']))
            
        self.conn.commit()

    def update_tournament_missions(self, name, history_index, bingo_grid):
        self.cursor.execute("SELECT id FROM stores WHERE is_active = 1")
        store_id = self.cursor.fetchone()['id']
        
        self.cursor.execute('''
            SELECT lp.id FROM league_profiles lp
            JOIN players p ON p.id = lp.player_id
            WHERE p.name = ? AND lp.store_id = ? AND lp.format_name = ?
        ''', (name, store_id, self.current_format))
        lp_row = self.cursor.fetchone()
        if not lp_row: raise ValueError("Jugador no válido")
        lp_id = lp_row['id']
        
        self.cursor.execute('''
            SELECT tr.id FROM tournament_results tr
            JOIN tournaments t ON t.id = tr.tournament_id
            WHERE tr.league_profile_id = ?
            ORDER BY t.date ASC
        ''', (lp_id,))
        results = self.cursor.fetchall()
        if history_index < 0 or history_index >= len(results):
            raise ValueError("Índice de torneo inválido")
            
        tr_id = results[history_index]['id']
        bg_json = json.dumps(bingo_grid)
        self.cursor.execute("UPDATE tournament_results SET bingo_grid = ? WHERE id = ?", (bg_json, tr_id))
        self.conn.commit()

    def get_global_tournaments(self):
        self.cursor.execute("SELECT id FROM stores WHERE is_active = 1")
        store_row = self.cursor.fetchone()
        if not store_row: return []
        self.cursor.execute('''
            SELECT id, date FROM tournaments 
            WHERE store_id = ? AND format_name = ?
            ORDER BY date ASC, id ASC
        ''', (store_row['id'], self.current_format))
        return self.cursor.fetchall()

    def get_standings(self, include_missions=True, include_attendance=True):
        def sort_key(player):
            placement_pts, att_pts, miss_pts, bingo_count = player.get_points_composition(include_missions, include_attendance)
            total = placement_pts + att_pts + miss_pts
            return (total, placement_pts, att_pts, bingo_count)

        # Solo incluir jugadores que hayan participado al menos en un torneo (history > 0)
        active_players = [p for p in self.players if len(p.history) > 0]
        return sorted(active_players, key=sort_key, reverse=True)

    def get_ranked_standings(self, include_missions=True, include_attendance=True):
        ranked = []
        previous_total = None
        current_rank = 0

        for index, player in enumerate(self.get_standings(include_missions, include_attendance), start=1):
            total = player.get_total_points(include_missions, include_attendance)
            if total != previous_total:
                current_rank = index
                previous_total = total
            ranked.append((current_rank, player))

        return ranked
