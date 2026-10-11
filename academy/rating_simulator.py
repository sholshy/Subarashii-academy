import sqlite3
import os
import sys
from collections import defaultdict
import math

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_connection

class EloStrategy:
    def __init__(self, name="Abstract Strategy", initial_rating=1000):
        self.name = name
        self.initial_rating = initial_rating

    def get_k_factor(self, player_stats):
        raise NotImplementedError

    def calculate_expected_score(self, rating_a, rating_b):
        return 1 / (1 + math.pow(10, (rating_b - rating_a) / 400))

class ClassicEloStrategy(EloStrategy):
    def __init__(self, initial_rating=1000, K=32):
        super().__init__(name="Classic ELO", initial_rating=initial_rating)
        self.K = K

    def get_k_factor(self, player_stats):
        return self.K

class ProvisionalEloStrategy(EloStrategy):
    def __init__(self, initial_rating=1000, base_K=32, prov_K=64, prov_period=10):
        super().__init__(name="Provisional ELO", initial_rating=initial_rating)
        self.base_K = base_K
        self.prov_K = prov_K
        self.prov_period = prov_period

    def get_k_factor(self, player_stats):
        if player_stats['matches_played'] < self.prov_period:
            return self.prov_K
        return self.base_K
        
class CommunityEloStrategy(EloStrategy):
    """
    Variant for small communities:
    - High K initially to quickly position players.
    - Medium K normally.
    - Low K for high rating to prevent inflation.
    """
    def __init__(self, initial_rating=1000):
        super().__init__(name="Community Variant", initial_rating=initial_rating)

    def get_k_factor(self, player_stats):
        rating = player_stats['current_rating']
        matches = player_stats['matches_played']
        
        if matches < 10:
            return 64
        elif rating > 1200:
            return 16
        else:
            return 32

class V2EloStrategy(EloStrategy):
    """
    Proposed V2 Strategy:
    - K=64 for matches 1-10
    - K=32 for matches 11-30
    - K=24 after 30 matches
    No inflation, no floor.
    """
    def __init__(self, initial_rating=1000):
        super().__init__(name="V2 Proposal", initial_rating=initial_rating)

    def get_k_factor(self, player_stats):
        matches = player_stats['matches_played']
        if matches < 10:
            return 64
        elif matches < 30:
            return 32
        else:
            return 24

class V3EloStrategy16(EloStrategy):
    def __init__(self, initial_rating=1000):
        super().__init__(name="V3 Comunitario 16", initial_rating=initial_rating)

    def get_k_factor(self, player_stats):
        matches = player_stats['matches_played']
        if matches < 10: return 64
        elif matches < 30: return 32
        else: return 16

class V3EloStrategy24(EloStrategy):
    def __init__(self, initial_rating=1000):
        super().__init__(name="V3 Comunitario 24", initial_rating=initial_rating)

    def get_k_factor(self, player_stats):
        matches = player_stats['matches_played']
        if matches < 10: return 64
        elif matches < 30: return 32
        else: return 24

class V3EloStrategyConsolidated(EloStrategy):
    def __init__(self, initial_rating=1000):
        super().__init__(name="V3 Consolidado", initial_rating=initial_rating)

    def get_k_factor(self, player_stats):
        matches = player_stats['matches_played']
        if matches < 10: return 64
        else: return 32

class RatingSimulator:
    def __init__(self, strategy: EloStrategy, format_name=None):
        self.strategy = strategy
        self.format_name = format_name
        self.players = {} # {id: {'current_rating': 1000, 'matches_played': 0, 'wins': 0, 'losses': 0, 'highest': 1000, 'lowest': 1000}}
        self.history = [] # {player_id, date, opponent_id, old_rating, new_rating, rating_change}

    def _init_player(self, p_id):
        if p_id not in self.players:
            self.players[p_id] = {
                'current_rating': self.strategy.initial_rating,
                'matches_played': 0,
                'wins': 0,
                'losses': 0,
                'draws': 0,
                'highest': self.strategy.initial_rating,
                'lowest': self.strategy.initial_rating
            }

    def simulate(self):
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        q = """
            SELECT m.id, m.p1_id, m.p2_id, m.result_text, t.date, t.format_name, m.round_num
            FROM tournament_matches m
            JOIN tournaments t ON m.tournament_id = t.id
            WHERE m.p1_id IS NOT NULL AND m.p2_id IS NOT NULL
        """
        if self.format_name:
            q += f" AND t.format_name = '{self.format_name}'"
            
        q += " ORDER BY t.date ASC, m.id ASC"
        cursor.execute(q)
        matches = cursor.fetchall()
        
        for m in matches:
            if m['result_text'] == 'BYE' or 'Drop' in m['result_text']:
                continue
                
            p1_id = m['p1_id']
            p2_id = m['p2_id']
            
            res_text = m['result_text']
            
            score_p1 = 0.5
            score_p2 = 0.5
            
            if res_text == 'P1_WIN':
                score_p1 = 1.0
                score_p2 = 0.0
            elif res_text == 'P2_WIN':
                score_p1 = 0.0
                score_p2 = 1.0
            elif res_text == 'DRAW':
                score_p1 = 0.5
                score_p2 = 0.5
            else:
                continue

            self._init_player(p1_id)
            self._init_player(p2_id)
            
            r1 = self.players[p1_id]['current_rating']
            r2 = self.players[p2_id]['current_rating']
            
            e1 = self.strategy.calculate_expected_score(r1, r2)
            e2 = self.strategy.calculate_expected_score(r2, r1)
            
            k1 = self.strategy.get_k_factor(self.players[p1_id])
            k2 = self.strategy.get_k_factor(self.players[p2_id])
            
            delta1 = k1 * (score_p1 - e1)
            delta2 = k2 * (score_p2 - e2)
            
            new_r1 = r1 + delta1
            new_r2 = r2 + delta2
            
            # Update stats P1
            self.players[p1_id]['current_rating'] = new_r1
            self.players[p1_id]['matches_played'] += 1
            if score_p1 == 1.0: self.players[p1_id]['wins'] += 1
            elif score_p1 == 0.0: self.players[p1_id]['losses'] += 1
            else: self.players[p1_id]['draws'] += 1
            if new_r1 > self.players[p1_id]['highest']: self.players[p1_id]['highest'] = new_r1
            if new_r1 < self.players[p1_id]['lowest']: self.players[p1_id]['lowest'] = new_r1
            
            # Update stats P2
            self.players[p2_id]['current_rating'] = new_r2
            self.players[p2_id]['matches_played'] += 1
            if score_p2 == 1.0: self.players[p2_id]['wins'] += 1
            elif score_p2 == 0.0: self.players[p2_id]['losses'] += 1
            else: self.players[p2_id]['draws'] += 1
            if new_r2 > self.players[p2_id]['highest']: self.players[p2_id]['highest'] = new_r2
            if new_r2 < self.players[p2_id]['lowest']: self.players[p2_id]['lowest'] = new_r2
            
            # History
            self.history.append({
                'match_id': m['id'],
                'date': m['date'],
                'p1_id': p1_id,
                'p2_id': p2_id,
                'p1_delta': delta1,
                'p2_delta': delta2
            })
            
        conn.close()
        return self.players, self.history

    def get_report(self):
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, name FROM players")
        names = {r['id']: r['name'] for r in cursor.fetchall()}
        conn.close()
        
        report = []
        for pid, stats in self.players.items():
            report.append({
                'name': names.get(pid, "Unknown"),
                'rating': round(stats['current_rating']),
                'matches': stats['matches_played'],
                'wins': stats['wins'],
                'losses': stats['losses'],
                'win_rate': round((stats['wins'] / stats['matches_played'] * 100), 2) if stats['matches_played'] > 0 else 0,
                'highest': round(stats['highest']),
                'lowest': round(stats['lowest'])
            })
            
        report.sort(key=lambda x: x['rating'], reverse=True)
        return report

if __name__ == "__main__":
    sim = RatingSimulator(CommunityEloStrategy(), format_name=None)
    sim.simulate()
    rep = sim.get_report()
    print("--- SIMULACIÓN ELO COMUNITARIO ---")
    for r in rep[:10]:
        print(f"{r['name']}: {r['rating']} ELO ({r['matches']} matches, {r['win_rate']}% WR)")
