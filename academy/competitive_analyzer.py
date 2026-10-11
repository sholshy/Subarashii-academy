import sqlite3
import os
import sys
from collections import defaultdict

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_connection

class CompetitiveAnalyzer:
    def __init__(self, format_name=None):
        self.format_name = format_name
        self.conn = get_connection()
        self.conn.row_factory = sqlite3.Row

    def _get_matches_query(self, extra_where=""):
        q = """
            SELECT m.id, m.tournament_id, m.p1_id, m.p2_id, m.result_text, t.format_name, t.date
            FROM tournament_matches m
            JOIN tournaments t ON m.tournament_id = t.id
            WHERE m.p1_id IS NOT NULL AND m.p2_id IS NOT NULL
        """
        if self.format_name:
            q += f" AND t.format_name = '{self.format_name}'"
        if extra_where:
            q += f" AND {extra_where}"
        return q

    def get_player_stats(self, player_id):
        cursor = self.conn.cursor()
        
        # Tournaments played
        t_query = """
            SELECT COUNT(DISTINCT t.id) as count
            FROM tournament_results r
            JOIN tournaments t ON r.tournament_id = t.id
            JOIN league_profiles lp ON r.league_profile_id = lp.id
            WHERE lp.player_id = ?
        """
        if self.format_name:
            t_query += f" AND t.format_name = '{self.format_name}'"
        cursor.execute(t_query, (player_id,))
        tournaments_played = cursor.fetchone()['count']
        
        # Matches logic
        q = self._get_matches_query(f"(m.p1_id = {player_id} OR m.p2_id = {player_id})")
        q += " ORDER BY t.date ASC, m.id ASC"
        cursor.execute(q)
        matches = cursor.fetchall()
        
        wins = 0
        losses = 0
        draws = 0
        
        current_win_streak = 0
        max_win_streak = 0
        current_loss_streak = 0
        max_loss_streak = 0
        
        for m in matches:
            if m['result_text'] == 'BYE' or 'Drop' in m['result_text']:
                continue
                
            # Determine if player won
            is_p1 = (m['p1_id'] == player_id)
            
            won = False
            lost = False
            drawn = False
            
            res_text = m['result_text']
            if res_text == 'P1_WIN':
                if is_p1: won = True
                else: lost = True
            elif res_text == 'P2_WIN':
                if is_p1: lost = True
                else: won = True
            elif res_text == 'DRAW':
                drawn = True
            else:
                continue
                
            if won:
                wins += 1
                current_win_streak += 1
                current_loss_streak = 0
                if current_win_streak > max_win_streak: max_win_streak = current_win_streak
            elif lost:
                losses += 1
                current_loss_streak += 1
                current_win_streak = 0
                if current_loss_streak > max_loss_streak: max_loss_streak = current_loss_streak
            elif drawn:
                draws += 1
                current_win_streak = 0
                current_loss_streak = 0
                
        total_matches = wins + losses + draws
        win_rate = (wins / total_matches * 100) if total_matches > 0 else 0
        
        # Championships & Finals (using placement_points: 10 = Winner, 5 = Runner-up)
        cursor.execute(f"""
            SELECT SUM(CASE WHEN r.placement_points = 10 THEN 1 ELSE 0 END) as championships,
                   SUM(CASE WHEN r.placement_points = 5 THEN 1 ELSE 0 END) as runner_ups
            FROM tournament_results r
            JOIN tournaments t ON r.tournament_id = t.id
            JOIN league_profiles lp ON r.league_profile_id = lp.id
            WHERE lp.player_id = ? {f"AND t.format_name = '{self.format_name}'" if self.format_name else ""}
        """, (player_id,))
        champs_row = cursor.fetchone()
        championships = champs_row['championships'] or 0
        finals = championships + (champs_row['runner_ups'] or 0)
        
        return {
            "player_id": player_id,
            "tournaments_played": tournaments_played,
            "total_matches": total_matches,
            "wins": wins,
            "losses": losses,
            "draws": draws,
            "win_rate": round(win_rate, 2),
            "max_win_streak": max_win_streak,
            "max_loss_streak": max_loss_streak,
            "championships": championships,
            "finals": finals
        }

    def get_head_to_head(self, player_id):
        cursor = self.conn.cursor()
        q = self._get_matches_query(f"(m.p1_id = {player_id} OR m.p2_id = {player_id})")
        cursor.execute(q)
        matches = cursor.fetchall()
        
        h2h = defaultdict(lambda: {"wins": 0, "losses": 0, "draws": 0, "total": 0})
        
        for m in matches:
            if m['result_text'] == 'BYE' or 'Drop' in m['result_text']:
                continue
            
            is_p1 = (m['p1_id'] == player_id)
            opponent_id = m['p2_id'] if is_p1 else m['p1_id']
            
            h2h[opponent_id]["total"] += 1
            res_text = m['result_text']
            
            if res_text == 'P1_WIN':
                if is_p1: h2h[opponent_id]["wins"] += 1
                else: h2h[opponent_id]["losses"] += 1
            elif res_text == 'P2_WIN':
                if is_p1: h2h[opponent_id]["losses"] += 1
                else: h2h[opponent_id]["wins"] += 1
            elif res_text == 'DRAW':
                h2h[opponent_id]["draws"] += 1
                
        # Resolve names
        if not h2h:
            return []
            
        opps = list(h2h.keys())
        placeholders = ",".join(["?"] * len(opps))
        cursor.execute(f"SELECT id, name FROM players WHERE id IN ({placeholders})", opps)
        names = {r['id']: r['name'] for r in cursor.fetchall()}
        
        results = []
        for opp_id, stats in h2h.items():
            wr = (stats["wins"] / stats["total"] * 100) if stats["total"] > 0 else 0
            results.append({
                "opponent_id": opp_id,
                "opponent_name": names.get(opp_id, "Unknown"),
                "total": stats["total"],
                "wins": stats["wins"],
                "losses": stats["losses"],
                "draws": stats["draws"],
                "win_rate": round(wr, 2)
            })
            
        results.sort(key=lambda x: x['total'], reverse=True)
        return results

    def get_ranking(self, min_matches=10):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, name FROM players")
        players = cursor.fetchall()
        
        ranking = []
        for p in players:
            stats = self.get_player_stats(p['id'])
            if stats['total_matches'] >= min_matches:
                stats['name'] = p['name']
                ranking.append(stats)
                
        ranking.sort(key=lambda x: (x['win_rate'], x['total_matches']), reverse=True)
        return ranking
        
    def __del__(self):
        try:
            self.conn.close()
        except:
            pass

if __name__ == "__main__":
    analyzer = CompetitiveAnalyzer(format_name=None)
    rank = analyzer.get_ranking(min_matches=1)
    print(f"Top Players (All Formats, Min 1 Match):")
    for r in rank[:5]:
        print(f"{r['name']}: {r['win_rate']}% WR ({r['wins']}-{r['losses']}-{r['draws']}) | Torneos: {r['tournaments_played']} | Campeonatos: {r['championships']}")
