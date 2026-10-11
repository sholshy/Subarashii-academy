import sqlite3
import os
import sys
import math
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_connection
from academy.glicko2 import Glicko2, Glicko2Rating

class AcademyEngine:
    """
    Motor oficial de Subarashii Duel Academy V1.0.
    Maneja el perfil GLOBAL de cada jugador, aplicando ELO V3, XP, Niveles y Dormitorios.
    """
    
    def __init__(self, store_id=1):
        self.store_id = store_id
        # K-Factors de V3 Comunitario 24
        self.k_prov_high = 64
        self.k_prov_med = 32
        self.k_std = 24
        
        # Glicko-2 en paralelo al ELO (explica la confiabilidad del rating)
        self._glicko = Glicko2()
        self._schema_ok = False
        
        # Dormitory Thresholds
        self.DORM_SLIFER = "Slifer Red"
        self.DORM_RA = "Ra Yellow"
        self.DORM_OBELISK = "Obelisk Blue"
        
    def _calculate_expected_score(self, rating_a, rating_b):
        return 1 / (1 + math.pow(10, (rating_b - rating_a) / 400))
        
    def _get_k_factor(self, matches_played):
        if matches_played < 10:
            return self.k_prov_high
        elif matches_played < 30:
            return self.k_prov_med
        else:
            return self.k_std
            
    def calculate_level(self, xp):
        """
        Nivel 1: 0 XP
        Nivel 2: 100 XP
        Sube progresivamente, según especificación.
        Simplificación algorítmica: Nivel = int(sqrt(XP / 100)) + 1 (Aproximación, ajustar a tabla real si se requiere)
        """
        if xp < 100: return 1
        elif xp < 300: return 2
        elif xp < 600: return 3
        elif xp < 1000: return 4
        elif xp < 1500: return 5
        elif xp < 2100: return 6
        elif xp < 2800: return 7
        elif xp < 3600: return 8
        elif xp < 4500: return 9
        elif xp < 5500: return 10
        elif xp < 6600: return 11
        elif xp < 7800: return 12
        elif xp < 9100: return 13
        elif xp < 10500: return 14
        elif xp < 12000: return 15
        elif xp < 13600: return 16
        elif xp < 15300: return 17
        elif xp < 17100: return 18
        elif xp < 19000: return 19
        else: return 20

    def get_dormitory(self, rating):
        if rating >= 1120:
            return self.DORM_OBELISK
        elif rating >= 1050:
            return self.DORM_RA
        else:
            return self.DORM_SLIFER
            
    def get_or_create_global_profile(self, cursor, player_id):
        cursor.execute('''
            SELECT id, current_rating, matches_played, xp, level, dorm 
            FROM academy_profiles 
            WHERE player_id = ? AND store_id = ? AND format_name = 'GLOBAL'
        ''', (player_id, self.store_id))
        
        row = cursor.fetchone()
        if row:
            return dict(row)
            
        # Create it (provisional < 10 duelos: Estudiante de Intercambio)
        cursor.execute('''
            INSERT INTO academy_profiles (player_id, store_id, format_name, current_rating, highest_rating, dorm, xp, level, matches_played)
            VALUES (?, ?, 'GLOBAL', 1000, 1000, 'Estudiante de Intercambio', 0, 1, 0)
        ''', (player_id, self.store_id))
        
        new_id = cursor.lastrowid
        return {
            'id': new_id,
            'current_rating': 1000,
            'matches_played': 0,
            'xp': 0,
            'level': 1,
            'dorm': 'Estudiante de Intercambio'
        }
        
    def ensure_schema(self, cursor):
        """Aplica (una vez por instancia) la migración de columnas Glicko / trazabilidad / log de XP."""
        if not self._schema_ok:
            from database import migrate_academy_schema
            migrate_academy_schema(cursor)
            self._schema_ok = True

    def _get_glicko(self, cursor, profile_id):
        cursor.execute("SELECT glicko_mu, glicko_phi, glicko_sigma FROM academy_profiles WHERE id = ?", (profile_id,))
        row = cursor.fetchone()
        if not row or row['glicko_mu'] is None:
            return self._glicko.create_rating()
        return Glicko2Rating(row['glicko_mu'], row['glicko_phi'], row['glicko_sigma'])

    def add_xp(self, cursor, profile_id, current_xp, xp_gained, source='OTHER', ref_id=None,
               description=None, timestamp=None):
        """Suma XP y deja registro de su origen (MATCH, MISSION, ACHIEVEMENT, TOURNAMENT...)."""
        self.ensure_schema(cursor)
        new_xp = current_xp + xp_gained
        new_level = self.calculate_level(new_xp)
        cursor.execute('''
            UPDATE academy_profiles 
            SET xp = ?, level = ? 
            WHERE id = ?
        ''', (new_xp, new_level, profile_id))
        cursor.execute('''
            INSERT INTO academy_xp_log (academy_profile_id, source, ref_id, xp, description, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (profile_id, source, None if ref_id is None else str(ref_id), xp_gained, description,
              timestamp or datetime.now().isoformat()))
        return new_xp, new_level

    def process_match(self, cursor, match_id, p1_id, p2_id, result_p1, timestamp=None):
        """
        result_p1: 1 (p1 wins), 0 (p1 loses), 0.5 (draw)

        El ELO sigue siendo el rating oficial. En paralelo se calcula Glicko-2
        (rating + RD + volatilidad) y se guarda, por cada duelo, el rival, la
        expectativa y el K usado, para poder explicar el rating de cada jugador.
        """
        if not timestamp:
            timestamp = datetime.now().isoformat()
            
        self.ensure_schema(cursor)
        p1_prof = self.get_or_create_global_profile(cursor, p1_id)
        p2_prof = self.get_or_create_global_profile(cursor, p2_id)
        
        r1 = p1_prof['current_rating']
        r2 = p2_prof['current_rating']
        
        e1 = self._calculate_expected_score(r1, r2)
        e2 = self._calculate_expected_score(r2, r1)
        
        k1 = self._get_k_factor(p1_prof['matches_played'])
        k2 = self._get_k_factor(p2_prof['matches_played'])
        
        delta1 = int(round(k1 * (result_p1 - e1)))
        delta2 = int(round(k2 * ((1 - result_p1) - e2)))
        
        new_r1 = r1 + delta1
        new_r2 = r2 + delta2

        # Glicko-2 en paralelo (ambos se calculan con los valores previos al duelo)
        g1, g2 = self._get_glicko(cursor, p1_prof['id']), self._get_glicko(cursor, p2_prof['id'])
        ng1 = self._glicko.rate(g1, [(result_p1, g2)])
        ng2 = self._glicko.rate(g2, [(1 - result_p1, g1)])
        
        # Update Profiles
        for prof, new_r, delta, opp_id, opp_r, expected, k, score, ng in [
            (p1_prof, new_r1, delta1, p2_id, r2, e1, k1, result_p1, ng1),
            (p2_prof, new_r2, delta2, p1_id, r1, e2, k2, 1 - result_p1, ng2),
        ]:
            is_win = score == 1
            is_loss = score == 0
            
            cursor.execute('''
                UPDATE academy_profiles 
                SET current_rating = ?, 
                    highest_rating = MAX(highest_rating, ?), 
                    matches_played = matches_played + 1,
                    wins = wins + ?,
                    losses = losses + ?,
                    glicko_mu = ?, glicko_phi = ?, glicko_sigma = ?
                WHERE id = ?
            ''', (new_r, new_r, 1 if is_win else 0, 1 if is_loss else 0,
                  ng.mu, ng.phi, ng.sigma, prof['id']))
            
            # Insert History
            cursor.execute('''
                INSERT INTO academy_rating_history (academy_profile_id, match_id, previous_rating, new_rating, rating_change, timestamp, reason,
                                                    opponent_id, opponent_rating, expected_score, k_factor, result, glicko_mu, glicko_phi)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (prof['id'], match_id, prof['current_rating'], new_r, delta, timestamp, 'MATCH_RESULT',
                  opp_id, opp_r, expected, k, score, ng.mu, ng.phi))
            
            # Update Dormitory automatically upon reaching 10 matches
            new_mp = prof['matches_played'] + 1
            new_dorm = self.get_dormitory(new_r) if new_mp >= 10 else "Estudiante de Intercambio"
            cursor.execute("UPDATE academy_profiles SET dorm = ? WHERE id = ?", (new_dorm, prof['id']))

            # Match XP (+5) + Win XP (+10 if win)
            xp_gain = 5 + (10 if is_win else 0)
            self.add_xp(cursor, prof['id'], prof['xp'], xp_gain, source='MATCH', ref_id=match_id,
                        description=f"Duelo {'ganado' if is_win else 'perdido' if is_loss else 'empatado'}"
                                    f" (+5 jugar{' +10 ganar' if is_win else ''})",
                        timestamp=timestamp)

            # Evaluate match-level achievements
            self.evaluate_match_achievements(cursor, prof['id'], is_win, prof['current_rating'], new_r)

            # Evaluate match-level missions
            self.evaluate_match_missions(cursor, prof['id'], is_win)

    def evaluate_match_achievements(self, cursor, profile_id, is_win, old_rating, new_rating):
        import json
        cat_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "achievements", "catalog.json")
        if not os.path.exists(cat_path): return
        
        with open(cat_path, 'r', encoding='utf-8') as f:
            catalog = json.load(f).get("achievements", [])
            
        cursor.execute("SELECT achievement_id FROM academy_achievements WHERE academy_profile_id=?", (profile_id,))
        unlocked = set(r['achievement_id'] for r in cursor.fetchall())
        
        # Get profile stats
        cursor.execute("SELECT matches_played, wins, current_rating FROM academy_profiles WHERE id=?", (profile_id,))
        p_row = cursor.fetchone()
        if not p_row: return
        
        for ach in catalog:
            aid = ach["id"]
            if aid in unlocked: continue
            
            # Simple condition evaluator
            ctype = ach.get("condition_type")
            cfg = ach.get("condition_config", {})
            
            unlocked_now = False
            if ctype == "STAT_CHECK":
                stat = cfg.get("stat")
                val = cfg.get("value")
                op = cfg.get("operator")
                
                actual = p_row[stat] if stat in p_row.keys() else 0
                if stat == "wins" and is_win:
                    actual += 1 # we might not have updated 'wins' explicitly in DB yet, actually we don't track global wins in academy_profiles yet!
                    # Wait, we need to track wins if we want to use them.
                    pass
                
                if op == ">=" and actual >= val: 
                    unlocked_now = True
                    
                if unlocked_now and cfg.get("requires_graduation"):
                    if ("matches_played" in p_row.keys() and p_row["matches_played"] < 10):
                        unlocked_now = False
                
            if unlocked_now:
                self.unlock_achievement(cursor, profile_id, aid, ach["xp_reward"])

    def unlock_achievement(self, cursor, profile_id, achievement_id, xp_reward):
        timestamp = datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO academy_achievements (academy_profile_id, achievement_id, unlocked_at) 
            VALUES (?, ?, ?)
        ''', (profile_id, achievement_id, timestamp))
        
        # Add XP
        cursor.execute("SELECT xp FROM academy_profiles WHERE id=?", (profile_id,))
        xp = cursor.fetchone()['xp']
        self.add_xp(cursor, profile_id, xp, xp_reward, source='ACHIEVEMENT', ref_id=achievement_id,
                    description=f"Logro desbloqueado: {achievement_id}")

    def evaluate_tournament_achievements(self, cursor, profile_id, placement):
        import json
        cat_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "achievements", "catalog.json")
        if not os.path.exists(cat_path): return
        
        with open(cat_path, 'r', encoding='utf-8') as f:
            catalog = json.load(f).get("achievements", [])
            
        cursor.execute("SELECT achievement_id FROM academy_achievements WHERE academy_profile_id=?", (profile_id,))
        unlocked = set(r['achievement_id'] for r in cursor.fetchall())
        
        for ach in catalog:
            aid = ach["id"]
            if aid in unlocked: continue
            
            ctype = ach.get("condition_type")
            cfg = ach.get("condition_config", {})
            
            if ctype == "EVENT_CHECK" and cfg.get("event") == "TOURNAMENT_PLACEMENT":
                # Valid placement > 0, otherwise they didn't place
                if placement > 0 and placement <= cfg.get("value", 1):
                    self.unlock_achievement(cursor, profile_id, aid, ach["xp_reward"])

    def _get_current_xp(self, cursor, profile_id):
        cursor.execute("SELECT xp FROM academy_profiles WHERE id=?", (profile_id,))
        row = cursor.fetchone()
        return row['xp'] if row else 0

    def evaluate_match_missions(self, cursor, profile_id, is_win):
        import json
        cat_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "missions", "catalog.json")
        if not os.path.exists(cat_path): return
        
        with open(cat_path, 'r', encoding='utf-8') as f:
            catalog = json.load(f).get("missions", [])
            
        now = datetime.now().isoformat()
        cursor.execute("SELECT id, mission_id, progress FROM academy_missions WHERE academy_profile_id=? AND completed=0 AND (expires_at IS NULL OR expires_at > ?)", (profile_id, now))
        active = {r['mission_id']: dict(r) for r in cursor.fetchall()}
        
        for msn in catalog:
            mid = msn["id"]
            if mid not in active: continue
            
            ctype = msn.get("condition_type")
            current_progress = active[mid]['progress']
            target = msn.get("target_value", 1)
            
            progress_made = False
            if ctype == "WIN_COUNT" and is_win:
                current_progress += 1
                progress_made = True
            elif ctype == "MATCH_COUNT":
                current_progress += 1
                progress_made = True
                
            if progress_made:
                completed = current_progress >= target
                if completed:
                    cursor.execute("UPDATE academy_missions SET progress=?, completed=1, completed_at=? WHERE id=?", (current_progress, now, active[mid]['id']))
                    self.add_xp(cursor, profile_id, self._get_current_xp(cursor, profile_id), msn["xp_reward"],
                                source='MISSION', ref_id=mid, description=f"Misión completada: {msn.get('name', mid)}")
                else:
                    cursor.execute("UPDATE academy_missions SET progress=? WHERE id=?", (current_progress, active[mid]['id']))

    def evaluate_tournament_missions(self, cursor, profile_id):
        import json
        cat_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "missions", "catalog.json")
        if not os.path.exists(cat_path): return
        
        with open(cat_path, 'r', encoding='utf-8') as f:
            catalog = json.load(f).get("missions", [])
            
        now = datetime.now().isoformat()
        cursor.execute("SELECT id, mission_id, progress FROM academy_missions WHERE academy_profile_id=? AND completed=0 AND (expires_at IS NULL OR expires_at > ?)", (profile_id, now))
        active = {r['mission_id']: dict(r) for r in cursor.fetchall()}
        
        for msn in catalog:
            mid = msn["id"]
            if mid not in active: continue
            
            ctype = msn.get("condition_type")
            current_progress = active[mid]['progress']
            target = msn.get("target_value", 1)
            
            if ctype == "TOURNAMENT_COUNT":
                current_progress += 1
                completed = current_progress >= target
                if completed:
                    cursor.execute("UPDATE academy_missions SET progress=?, completed=1, completed_at=? WHERE id=?", (current_progress, now, active[mid]['id']))
                    self.add_xp(cursor, profile_id, self._get_current_xp(cursor, profile_id), msn["xp_reward"],
                                source='MISSION', ref_id=mid, description=f"Misión completada: {msn.get('name', mid)}")
                else:
                    cursor.execute("UPDATE academy_missions SET progress=? WHERE id=?", (current_progress, active[mid]['id']))

    def assign_weekly_missions(self, cursor, profile_id):
        import json
        from datetime import timedelta
        cat_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "missions", "catalog.json")
        if not os.path.exists(cat_path): return
        
        with open(cat_path, 'r', encoding='utf-8') as f:
            catalog = json.load(f).get("missions", [])
            
        now = datetime.now()
        expires = (now + timedelta(days=7)).isoformat()
        
        # We assign all WEEKLY missions that are not already active
        cursor.execute("SELECT mission_id FROM academy_missions WHERE academy_profile_id=? AND completed=0 AND (expires_at IS NULL OR expires_at > ?)", (profile_id, now.isoformat()))
        active = set(r['mission_id'] for r in cursor.fetchall())
        
        for msn in catalog:
            if msn["type"] == "WEEKLY" and msn["id"] not in active:
                cursor.execute('''
                    INSERT INTO academy_missions (academy_profile_id, mission_id, progress, completed, expires_at)
                    VALUES (?, ?, 0, 0, ?)
                ''', (profile_id, msn["id"], expires))

    def process_tournament(self, cursor, tournament_id, timestamp=None):
        if not timestamp:
            timestamp = datetime.now().isoformat()
            
        self.ensure_schema(cursor)
        # Before processing, snapshot the current ranks into previous_rank
        cursor.execute("""
            SELECT id FROM academy_profiles 
            WHERE format_name = 'GLOBAL' 
            ORDER BY current_rating DESC, xp DESC
        """)
        current_standings = cursor.fetchall()
        for rank, row in enumerate(current_standings, 1):
            cursor.execute("UPDATE academy_profiles SET previous_rank = ? WHERE id = ?", (rank, row['id']))
            
        # Get tournament date
        cursor.execute("SELECT date FROM tournaments WHERE id=?", (tournament_id,))
        t_row = cursor.fetchone()
        t_date = t_row['date'] if t_row else timestamp

        # Process matches
        cursor.execute("""
            SELECT id, p1_id, p2_id, result_text 
            FROM tournament_matches 
            WHERE tournament_id = ? AND p1_id IS NOT NULL AND p2_id IS NOT NULL
            ORDER BY round_num ASC, id ASC
        """, (tournament_id,))
        matches = cursor.fetchall()
        
        for m in matches:
            res = m['result_text']
            if 'BYE' in res or 'Drop' in res: continue
            
            if res == 'P1_WIN': p1_score = 1.0
            elif res == 'P2_WIN': p1_score = 0.0
            elif res == 'DRAW': p1_score = 0.5
            else: continue
            
            self.process_match(cursor, m['id'], m['p1_id'], m['p2_id'], p1_score, timestamp=t_date)

        # Process tournament participation/placements
        cursor.execute("""
            SELECT league_profile_id, placement_points
            FROM tournament_results 
            WHERE tournament_id = ?
        """, (tournament_id,))
        results = cursor.fetchall()
        
        for r in results:
            # Get player_id from league_profile
            cursor.execute("SELECT player_id FROM league_profiles WHERE id=?", (r['league_profile_id'],))
            lp_row = cursor.fetchone()
            if not lp_row: continue
            
            player_id = lp_row['player_id']
            prof = self.get_or_create_global_profile(cursor, player_id)
            
            xp_gain = 25
            pos = r['placement_points']
            if pos == 1: xp_gain += 150
            elif pos == 2: xp_gain += 100
            elif pos in [3, 4]: xp_gain += 75
            elif 5 <= pos <= 8: xp_gain += 50
            
            placement_txt = f", puesto {pos}" if pos and pos > 0 else ""
            self.add_xp(cursor, prof['id'], prof['xp'], xp_gain, source='TOURNAMENT',
                        ref_id=tournament_id,
                        description=f"Participación en torneo #{tournament_id}{placement_txt}",
                        timestamp=timestamp)
            
            if pos > 0:
                self.evaluate_tournament_achievements(cursor, prof['id'], pos)
                
            self.evaluate_tournament_missions(cursor, prof['id'])
            
            # Re-evaluate Dormitory based on new rating
            cursor.execute("SELECT current_rating, matches_played FROM academy_profiles WHERE id=?", (prof['id'],))
            p_stats = cursor.fetchone()
            if p_stats['matches_played'] >= 10:
                new_dorm = self.get_dormitory(p_stats['current_rating'])
                cursor.execute("UPDATE academy_profiles SET dorm=? WHERE id=?", (new_dorm, prof['id']))
