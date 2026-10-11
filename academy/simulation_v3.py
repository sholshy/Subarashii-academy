import sqlite3
import os
import sys
import csv
import random
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from academy.rating_simulator import RatingSimulator, V3EloStrategy16, V3EloStrategy24, V3EloStrategyConsolidated
from database import get_connection

class SimulationV3Runner:
    def __init__(self, output_dir="academy/sim_results_v3"):
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        self.engines = {
            "K=16": V3EloStrategy16(),
            "K=24": V3EloStrategy24(),
            "K=Consolidado": V3EloStrategyConsolidated()
        }
        # Fixed seed for deterministic random outcomes when generating profiles
        random.seed(42)

    def _save_csv(self, filename, headers, rows):
        path = os.path.join(self.output_dir, filename)
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)
        return path
        
    def _generate_deterministic_sequence(self, win_rate, total_matches):
        seq = []
        wins = int(round(total_matches * win_rate))
        losses = total_matches - wins
        
        # We interleave to avoid huge streaks unless specified
        # but deterministic
        pool = [1] * wins + [0] * losses
        random.Random(42).shuffle(pool)
        return pool

    def run_all(self):
        print("V3: Simulación 1 y 2 - Jugadores Hipotéticos (Largo Plazo)...")
        self.sim1_and_2_long_term()
        
        print("V3: Simulación 3 - Comparación K16 vs K24...")
        self.sim3_k16_vs_k24()
        
        print("V3: Simulación 4 - Recuperación...")
        self.sim4_recovery()
        
        print("V3: Simulación 5 y 6 - Jugador Nuevo Empieza Mal/Excelente...")
        self.sim5_and_6_new_players()
        
        print("V3: Simulación 7 - Victorias contra Oponentes Fuertes...")
        self.sim7_opponents()
        
        print("V3: Simulación 8 - Volumen...")
        self.sim8_volume()
        
        print("V3: Simulación 9 - Estabilidad del Ranking...")
        self.sim9_ranking_stability()
        
        print("V3: Simulación 10 y 11 - Dormitorios y Estabilidad...")
        # Estas simulaciones se ejecutan dentro de sim9_ranking_stability porque comparten el pool de jugadores
        
        print("V3: Simulación 12 - Explotación...")
        self.sim12_exploitation()
        
        print(f"Todas las simulaciones V3 completadas en {self.output_dir}")

    def sim1_and_2_long_term(self):
        profiles = {
            "100% (Perfecto)": 1.0,
            "90% (Excelente)": 0.9,
            "80% (Muy Bueno)": 0.8,
            "70% (Bueno)": 0.7,
            "60% (Mediocre)": 0.6,
            "40% (Malo)": 0.4,
            "30% (Muy Malo)": 0.3
        }
        
        rows = []
        for p_name, wr in profiles.items():
            seq = self._generate_deterministic_sequence(wr, 100)
            
            for eng_name, strategy in self.engines.items():
                rating = 1000
                r10, r20, r30, r50, r100 = 0, 0, 0, 0, 0
                r_max = 1000
                r_min = 1000
                
                for m, result in enumerate(seq):
                    matches = m + 1
                    e = strategy.calculate_expected_score(rating, 1000) # Against static average
                    k = strategy.get_k_factor({'matches_played': m})
                    rating += k * (result - e)
                    
                    if rating > r_max: r_max = rating
                    if rating < r_min: r_min = rating
                    
                    if matches == 10: r10 = rating
                    if matches == 20: r20 = rating
                    if matches == 30: r30 = rating
                    if matches == 50: r50 = rating
                    if matches == 100: r100 = rating
                
                rows.append([
                    p_name, eng_name, 
                    round(r10, 2), round(r20, 2), round(r30, 2), round(r50, 2), round(r100, 2),
                    round(r_max, 2), round(r_min, 2)
                ])
                
        self._save_csv("long_term_rating_simulation.csv", 
            ["Jugador", "Motor", "10M", "20M", "30M", "50M", "100M", "Max", "Min"], rows)

    def sim3_k16_vs_k24(self):
        # We compare K16 and K24 exactly after 30 matches
        seq = self._generate_deterministic_sequence(0.65, 100)
        rows = []
        
        s16 = self.engines["K=16"]
        s24 = self.engines["K=24"]
        
        r16, r24 = 1000, 1000
        for m, result in enumerate(seq):
            matches = m + 1
            e16 = s16.calculate_expected_score(r16, 1000)
            e24 = s24.calculate_expected_score(r24, 1000)
            k16 = s16.get_k_factor({'matches_played': m})
            k24 = s24.get_k_factor({'matches_played': m})
            
            # Opponent is 1100 to force movement
            e16 = s16.calculate_expected_score(r16, 1100)
            e24 = s24.calculate_expected_score(r24, 1100)
            
            r16 += k16 * (result - e16)
            r24 += k24 * (result - e24)
            
            if matches in [30, 31, 50, 100]:
                rows.append([matches, result, round(r16, 2), k16, round(r24, 2), k24, round(abs(r16 - r24), 2)])
                
        self._save_csv("k16_vs_k24_comparison.csv", ["Matches", "Result", "R16", "K16", "R24", "K24", "Diferencia"], rows)

    def sim4_recovery(self):
        # Bad streak then good
        s1 = [1]*21 + [0]*9  # first 30
        s1 += [1]*5 + [0]*15 # next 20
        s1 += [1]*35 + [0]*15 # next 50
        
        # Good streak then bad
        s2 = [1]*9 + [0]*21 # first 30
        s2 += [1]*15 + [0]*5 # next 20
        s2 += [1]*40 + [0]*10 # next 50
        
        rows = []
        for eng_name, strategy in self.engines.items():
            for case_name, seq in [("Empieza Bien -> Cae -> Sube", s1), ("Empieza Mal -> Sube -> Arrasa", s2)]:
                rating = 1000
                r30, r50, r100 = 0, 0, 0
                for m, result in enumerate(seq):
                    matches = m + 1
                    e = strategy.calculate_expected_score(rating, 1000)
                    rating += strategy.get_k_factor({'matches_played': m}) * (result - e)
                    if matches == 30: r30 = rating
                    if matches == 50: r50 = rating
                    if matches == 100: r100 = rating
                rows.append([case_name, eng_name, round(r30, 2), round(r50, 2), round(r100, 2)])
                
        self._save_csv("recovery_simulation.csv", ["Caso", "Motor", "Rating 30M", "Rating 50M", "Rating 100M"], rows)

    def sim5_and_6_new_players(self):
        # Malo: 2W/8L -> 14W/6L -> 49W/21L
        malo = [1]*2 + [0]*8
        malo += [1]*14 + [0]*6
        malo += [1]*49 + [0]*21
        
        # Bueno: 9W/1L -> 14W/6L -> 42W/28L
        bueno = [1]*9 + [0]*1
        bueno += [1]*14 + [0]*6
        bueno += [1]*42 + [0]*28
        
        rows = []
        for eng_name, strategy in self.engines.items():
            for case_name, seq in [("Empieza Pésimo (Malo)", malo), ("Empieza Excelente (Bueno)", bueno)]:
                rating = 1000
                r10, r30, r50, r100 = 0, 0, 0, 0
                for m, result in enumerate(seq):
                    matches = m + 1
                    e = strategy.calculate_expected_score(rating, 1000)
                    rating += strategy.get_k_factor({'matches_played': m}) * (result - e)
                    if matches == 10: r10 = rating
                    if matches == 30: r30 = rating
                    if matches == 50: r50 = rating
                    if matches == 100: r100 = rating
                rows.append([case_name, eng_name, round(r10, 2), round(r30, 2), round(r50, 2), round(r100, 2)])
                
        self._save_csv("new_player_simulation.csv", ["Caso", "Motor", "10M", "30M", "50M", "100M"], rows)

    def sim7_opponents(self):
        # Win vs 900, 1000, 1100, etc.
        opponents = [900, 1000, 1100, 1200, 1300, 1400]
        rows = []
        strategy = self.engines["K=24"] # using standard proposed
        
        for opp in opponents:
            # Win case (K=64 since we are new)
            e_win = strategy.calculate_expected_score(1000, opp)
            delta_win = 64 * (1 - e_win)
            
            # Loss case
            e_loss = strategy.calculate_expected_score(1000, opp)
            delta_loss = 64 * (0 - e_loss)
            
            rows.append(["Victoria", 1000, opp, round(delta_win, 2)])
            rows.append(["Derrota", 1000, opp, round(delta_loss, 2)])
            
        # We can append this to exploitation or somewhere else, but I'll write it to opponents
        self._save_csv("opponents_simulation.csv", ["Resultado", "Rating Base", "Oponente", "Delta"], rows)

    def sim8_volume(self):
        rows = []
        for eng_name, strategy in self.engines.items():
            for wr in [0.6, 0.7, 0.8]:
                for target in [30, 50, 100]:
                    seq = self._generate_deterministic_sequence(wr, target)
                    rating = 1000
                    for m, result in enumerate(seq):
                        e = strategy.calculate_expected_score(rating, 1000)
                        rating += strategy.get_k_factor({'matches_played': m}) * (result - e)
                    rows.append([eng_name, f"{int(wr*100)}%", target, round(rating, 2)])
                    
        self._save_csv("volume_simulation.csv", ["Motor", "WinRate", "Matches", "Rating Final"], rows)

    def sim9_ranking_stability(self):
        # Generate 32 clones, play 100 matches each in a round robin or random pairs
        # We need a small matchmaking sim
        clones = [{'id': i, 'rating': 1000, 'matches': 0} for i in range(32)]
        strategy = self.engines["K=24"]
        
        # True skill from 800 to 1200
        for i, c in enumerate(clones):
            c['true_skill'] = 800 + (i * 12.5) # linearly distributed
            
        snapshots = {10: [], 20: [], 30: [], 50: [], 100: []}
        
        for _ in range(100):
            # Play a round
            random.Random(42 + _).shuffle(clones)
            for i in range(0, 32, 2):
                p1 = clones[i]
                p2 = clones[i+1]
                
                # Determine winner based on true skill (higher skill = higher prob)
                prob_p1 = strategy.calculate_expected_score(p1['true_skill'], p2['true_skill'])
                res_p1 = 1 if random.Random(p1['id'] + _).random() < prob_p1 else 0
                
                e_p1 = strategy.calculate_expected_score(p1['rating'], p2['rating'])
                k_p1 = strategy.get_k_factor({'matches_played': p1['matches']})
                p1['rating'] += k_p1 * (res_p1 - e_p1)
                p1['matches'] += 1
                
                res_p2 = 1 - res_p1
                e_p2 = strategy.calculate_expected_score(p2['rating'], p1['rating'])
                k_p2 = strategy.get_k_factor({'matches_played': p2['matches']})
                p2['rating'] += k_p2 * (res_p2 - e_p2)
                p2['matches'] += 1
                
            # Take snapshots if everyone reached it
            if clones[0]['matches'] in snapshots:
                clones_sorted = sorted(clones, key=lambda x: x['rating'], reverse=True)
                for rank, c in enumerate(clones_sorted):
                    snapshots[clones[0]['matches']].append({
                        'rank': rank + 1,
                        'id': c['id'],
                        'rating': c['rating']
                    })
                    
        rows = []
        for m in [10, 20, 30, 50, 100]:
            top3 = [c['id'] for c in snapshots[m] if c['rank'] <= 3]
            top5 = [c['id'] for c in snapshots[m] if c['rank'] <= 5]
            rows.append([m, str(top3), str(top5)])
            
        self._save_csv("ranking_stability.csv", ["Matches", "Top 3 IDs", "Top 5 IDs"], rows)
        
        # Dormitory simulation based on this 32-player pool
        self._sim10_11_dorms(snapshots)

    def _sim10_11_dorms(self, snapshots):
        # We evaluate Mod A, B, C over time
        # Mod A: 10% (3), 25% (8), Rest
        # Mod B: 15% (4), 30% (9), Rest
        # Mod C: >1120, 1050-1119, <1050
        
        rows_dist = []
        rows_stab = []
        
        for m in [30, 50, 100]:
            snaps = snapshots[m]
            # Mod C
            ob = len([s for s in snaps if s['rating'] >= 1120])
            ra = len([s for s in snaps if 1050 <= s['rating'] < 1120])
            sl = len([s for s in snaps if s['rating'] < 1050])
            rows_dist.append([m, ob, ra, sl])
            
        self._save_csv("dormitory_simulation.csv", ["Matches", "Obelisk", "Ra", "Slifer"], rows_dist)
        
        # Dormitory stability (How often does player X change dorm in Mod C?)
        history = {i: [] for i in range(32)}
        for m in [10, 20, 30, 50, 100]:
            for s in snapshots[m]:
                if s['rating'] >= 1120: d = "Obelisk"
                elif s['rating'] >= 1050: d = "Ra"
                else: d = "Slifer"
                history[s['id']].append(d)
                
        for pid, d_list in history.items():
            changes = 0
            for i in range(1, len(d_list)):
                if d_list[i] != d_list[i-1]: changes += 1
            rows_stab.append([pid, str(d_list), changes])
            
        self._save_csv("dormitory_stability.csv", ["Player ID", "Dorm History", "Changes"], rows_stab)

    def sim12_exploitation(self):
        strategy = self.engines["K=24"]
        
        # Exploit A: Playing only against weak players (Farm)
        # Player is True Skill 1200 (WR vs 1000 should be ~76%)
        # Let's say they play 50 matches against 900 rating
        rating = 1000
        for m in range(50):
            # WR vs 900 for a 1200 player is like 85%
            res = 1 if m % 10 < 8 else 0
            e = strategy.calculate_expected_score(rating, 900)
            rating += strategy.get_k_factor({'matches_played': m}) * (res - e)
            
        # Exploit B: Tanking first 10 matches then winning
        rating_b = 1000
        for m in range(50):
            res = 0 if m < 10 else 1 # loses first 10, wins next 40 vs 1000
            e = strategy.calculate_expected_score(rating_b, 1000)
            rating_b += strategy.get_k_factor({'matches_played': m}) * (res - e)
            
        self._save_csv("exploitation_tests.csv", ["Exploit", "Final Rating"], [
            ["Farm Weak (50 matches vs 900 ELO)", round(rating, 2)],
            ["Tanking (10L -> 40W vs 1000 ELO)", round(rating_b, 2)]
        ])

if __name__ == "__main__":
    runner = SimulationV3Runner()
    runner.run_all()
