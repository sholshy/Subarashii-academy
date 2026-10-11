import sqlite3
import os
import sys
import csv
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from academy.rating_simulator import RatingSimulator, ClassicEloStrategy, CommunityEloStrategy, V2EloStrategy, ProvisionalEloStrategy
from database import get_connection

class SimulationV2Runner:
    def __init__(self, output_dir="academy/sim_results"):
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

    def _save_csv(self, filename, headers, rows):
        path = os.path.join(self.output_dir, filename)
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)
        return path

    def run_all(self):
        print("Ejecutando Simulación 1: Estabilidad...")
        self.sim1_stability()
        print("Ejecutando Simulación 2: Trayectorias y Oponentes...")
        self.sim2_trajectories()
        print("Ejecutando Simulación 3: Comparación de Motores...")
        self.sim3_engine_comparison()
        print("Ejecutando Simulación 4: Recuperación...")
        self.sim4_recovery()
        print("Ejecutando Simulación 5: Influencia del Volumen...")
        self.sim5_volume()
        print("Ejecutando Simulación 8 y 9: Dormitorios...")
        self.sim8_dorms()
        print("Simulaciones completadas. Resultados en:", self.output_dir)

    def sim1_stability(self):
        # We need to simulate chronologically and snapshot at 5, 10, 15, 20 matches.
        # This requires hacking the simulator or rewriting a quick chronological loop.
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, name FROM players")
        players = {r['id']: {'name': r['name'], 'rating': 1000, 'matches': 0, 'history_5': None, 'history_10': None, 'history_15': None, 'history_20': None} for r in cursor.fetchall()}
        
        q = """
            SELECT m.id, m.p1_id, m.p2_id, m.result_text
            FROM tournament_matches m
            JOIN tournaments t ON m.tournament_id = t.id
            WHERE m.p1_id IS NOT NULL AND m.p2_id IS NOT NULL
            ORDER BY t.date ASC, m.id ASC
        """
        cursor.execute(q)
        matches = cursor.fetchall()
        
        strategy = V2EloStrategy()
        
        def update_player(p_id, score, opp_rating):
            p = players[p_id]
            e = strategy.calculate_expected_score(p['rating'], opp_rating)
            k = strategy.get_k_factor({'matches_played': p['matches']})
            p['rating'] += k * (score - e)
            p['matches'] += 1
            if p['matches'] == 5: p['history_5'] = p['rating']
            if p['matches'] == 10: p['history_10'] = p['rating']
            if p['matches'] == 15: p['history_15'] = p['rating']
            if p['matches'] == 20: p['history_20'] = p['rating']

        for m in matches:
            if m['result_text'] == 'BYE' or 'Drop' in m['result_text']: continue
            p1_id = m['p1_id']
            p2_id = m['p2_id']
            r1 = players[p1_id]['rating']
            r2 = players[p2_id]['rating']
            
            res = m['result_text']
            if res == 'P1_WIN':
                update_player(p1_id, 1.0, r2)
                update_player(p2_id, 0.0, r1)
            elif res == 'P2_WIN':
                update_player(p1_id, 0.0, r2)
                update_player(p2_id, 1.0, r1)
            elif res == 'DRAW':
                update_player(p1_id, 0.5, r2)
                update_player(p2_id, 0.5, r1)
                
        conn.close()
        
        # Rankings at each snapshot
        def get_rank(players_dict, snapshot_key):
            # Only players who reached that snapshot
            valid = [p for p in players_dict.values() if p[snapshot_key] is not None]
            valid.sort(key=lambda x: x[snapshot_key], reverse=True)
            ranks = {}
            for i, p in enumerate(valid):
                ranks[p['name']] = i + 1
            return ranks
            
        r5 = get_rank(players, 'history_5')
        r10 = get_rank(players, 'history_10')
        r15 = get_rank(players, 'history_15')
        r20 = get_rank(players, 'history_20')
        
        rows = []
        for p in players.values():
            if p['history_5'] is not None:
                rows.append([
                    p['name'],
                    round(p['history_5']) if p['history_5'] else '-',
                    r5.get(p['name'], '-'),
                    round(p['history_10']) if p['history_10'] else '-',
                    r10.get(p['name'], '-'),
                    round(p['history_15']) if p['history_15'] else '-',
                    r15.get(p['name'], '-'),
                    round(p['history_20']) if p['history_20'] else '-',
                    r20.get(p['name'], '-')
                ])
                
        self._save_csv("sim1_stability.csv", ["Jugador", "Rating 5M", "Rank 5M", "Rating 10M", "Rank 10M", "Rating 15M", "Rank 15M", "Rating 20M", "Rank 20M"], rows)

    def sim2_trajectories(self):
        strategy = V2EloStrategy()
        
        # Scenarios: W/L sequences
        # A: 5-5 (W L W L W L W L W L)
        # B: 7-3 (W W W L W W L W W L)
        # C: 9-1 (W W W W W W W W W L)
        # D: 10-0 (W * 10)
        # E: 2-5 then 8-2 (L L W L L L W then W W W W W W W L W L)
        
        scenarios = {
            "A_Mediocre_5_5": [1,0,1,0,1,0,1,0,1,0],
            "B_Bueno_7_3": [1,1,1,0,1,1,0,1,1,0],
            "C_MuyBueno_9_1": [1,1,1,1,1,1,1,1,1,0],
            "D_Excelente_10_0": [1,1,1,1,1,1,1,1,1,1],
            "E_Mejora_10_7": [0,0,1,0,0,0,1, 1,1,1,1,1,1,1,0,1,0]
        }
        
        opponents = [900, 1000, 1100, 1200]
        rows = []
        
        for name, seq in scenarios.items():
            for opp_rating in opponents:
                rating = 1000
                matches = 0
                for match_idx, score in enumerate(seq):
                    matches += 1
                    e = strategy.calculate_expected_score(rating, opp_rating)
                    k = strategy.get_k_factor({'matches_played': matches - 1})
                    delta = k * (score - e)
                    rating += delta
                    rows.append([name, opp_rating, matches, score, round(rating, 2), round(delta, 2), k])
                    
        self._save_csv("sim2_trajectories.csv", ["Escenario", "Oponente_Fijo", "Match_Num", "Resultado", "Rating_Final", "Cambio", "K"], rows)

    def sim3_engine_comparison(self):
        engines = {
            "Clásico (K=32)": ClassicEloStrategy(),
            "Comunitario (K=64/32/16)": CommunityEloStrategy(),
            "V2 (K=64/32/24)": V2EloStrategy()
        }
        
        # Phantom player going 15-5 against 1000 ELO (W W W L W * 4)
        seq = [1,1,1,0,1] * 4
        
        rows = []
        for name, strategy in engines.items():
            rating = 1000
            for matches, score in enumerate(seq):
                e = strategy.calculate_expected_score(rating, 1000)
                # For community strategy, we need to pass current_rating
                k = strategy.get_k_factor({'matches_played': matches, 'current_rating': rating})
                rating += k * (score - e)
                if (matches + 1) in [5, 10, 15, 20]:
                    rows.append([name, matches + 1, round(rating, 2)])
                    
        self._save_csv("sim3_engines.csv", ["Motor", "Matches", "Rating"], rows)

    def sim4_recovery(self):
        strategy = V2EloStrategy()
        # Bad start: 3L, 7W, 2L
        bad_start = [0,0,0, 1,1,1,1,1,1,1, 0,0]
        # Terrible start: 5L, 10W
        terrible_start = [0,0,0,0,0, 1,1,1,1,1,1,1,1,1,1]
        
        rows = []
        for s_name, seq in [("Mala Racha", bad_start), ("Pésima Racha", terrible_start)]:
            rating = 1000
            for m, score in enumerate(seq):
                e = strategy.calculate_expected_score(rating, 1000)
                k = strategy.get_k_factor({'matches_played': m})
                rating += k * (score - e)
                rows.append([s_name, m+1, score, round(rating, 2)])
                
        self._save_csv("sim4_recovery.csv", ["Escenario", "Match", "Resultado", "Rating"], rows)

    def sim5_volume(self):
        # 60% WR at 20, 50, 100 matches
        strategy = V2EloStrategy()
        seq_10 = [1,1,1,0,0, 1,1,1,0,0] # 6W 4L (60%)
        
        rows = []
        for target in [20, 50, 100]:
            seq = seq_10 * (target // 10)
            rating = 1000
            for m, score in enumerate(seq):
                e = strategy.calculate_expected_score(rating, 1000)
                k = strategy.get_k_factor({'matches_played': m})
                rating += k * (score - e)
            rows.append(["60% WR", target, round(rating, 2)])
            
        self._save_csv("sim5_volume.csv", ["WinRate", "Total_Matches", "Rating_Final"], rows)

    def sim8_dorms(self):
        # Based on sim1 results at current state
        sim = RatingSimulator(V2EloStrategy())
        players, _ = sim.simulate()
        
        active = [p for p in players.values() if p['matches_played'] >= 5]
        active.sort(key=lambda x: x['current_rating'], reverse=True)
        
        total = len(active)
        if total == 0: return
        
        rows = []
        
        # Modelo A: 10% / 25% / Rest
        ob_a = int(total * 0.10)
        ra_a = int(total * 0.25)
        sl_a = total - ob_a - ra_a
        
        # Modelo B: 15% / 30% / Rest
        ob_b = int(total * 0.15)
        ra_b = int(total * 0.30)
        sl_b = total - ob_b - ra_b
        
        # Modelo C: Fijo >=1120, 1050-1119, <1050
        ob_c = len([p for p in active if p['current_rating'] >= 1120])
        ra_c = len([p for p in active if 1050 <= p['current_rating'] < 1120])
        sl_c = len([p for p in active if p['current_rating'] < 1050])
        
        rows.append(["Modelo A (10/25/65)", ob_a, ra_a, sl_a])
        rows.append(["Modelo B (15/30/55)", ob_b, ra_b, sl_b])
        rows.append(["Modelo C (Fijo >1120 / >1050)", ob_c, ra_c, sl_c])
        
        self._save_csv("sim8_dorms.csv", ["Modelo", "Obelisk", "Ra", "Slifer"], rows)

if __name__ == "__main__":
    runner = SimulationV2Runner()
    runner.run_all()
