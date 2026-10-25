import math
import random

class Player:
    def __init__(self, name, konami_id, phone="", email="", paid=False, invited=False):
        self.name = name
        self.konami_id = konami_id
        self.phone = phone
        self.email = email
        self.paid = paid
        self.invited = invited
        self.points = 0
        self.matches_played = 0
        self.opponents = []
        self.match_results = []
        self.active = True
        self.had_bye = False
        self.join_round = 0
        self._omw = 0.3333
        self._oomw = 0.3333

    @property
    def mw_percent(self):
        if self.matches_played == 0:
            return 0.3333
        pct = self.points / (self.matches_played * 3)
        return max(pct, 0.3333)

class Match:
    def __init__(self, p1, p2, round_num):
        self.p1 = p1
        self.p2 = p2
        self.round_num = round_num
        self.reported = False
        self.result_text = "Pendiente"
        self.note = ""

    def report(self, result_type):
        if self.reported:
            return
        
        self.result_text = result_type
        
        effective_type = result_type
        if isinstance(result_type, str) and "-" in result_type:
            try:
                parts = result_type.replace(" ", "").split("-")
                s1, s2 = int(parts[0]), int(parts[1])
                if s1 > s2:
                    effective_type = "P1_WIN"
                elif s2 > s1:
                    effective_type = "P2_WIN"
                elif s1 == s2 and s1 > 0:
                    effective_type = "DRAW"
                else:
                    effective_type = "DOUBLE_LOSS"
            except Exception:
                pass

        if effective_type == "P1_WIN":
            if self.p1:
                self.p1.points += 3
                self.p1.match_results.append('W')
            if self.p2:
                self.p2.points += 0
                self.p2.match_results.append('L')
                
        elif effective_type == "P2_WIN":
            if self.p1:
                self.p1.points += 0
                self.p1.match_results.append('L')
            if self.p2:
                self.p2.points += 3
                self.p2.match_results.append('W')
                
        elif effective_type == "DRAW":
            if self.p1:
                self.p1.points += 1
                self.p1.match_results.append('D')
            if self.p2:
                self.p2.points += 1
                self.p2.match_results.append('D')
                
        elif effective_type == "DOUBLE_LOSS":
            if self.p1:
                self.p1.points += 0
                self.p1.match_results.append('DL')
            if self.p2:
                self.p2.points += 0
                self.p2.match_results.append('DL')
                
        if self.p1: self.p1.matches_played += 1
        if self.p2: self.p2.matches_played += 1
        self.reported = True

class TournamentManager:
    def __init__(self):
        self.players = []
        self.rounds = []
        self.current_round = 0
        self.total_rounds = 0
        self.mode = "swiss" 
        self.status = "setup" 
        self.format_name = "GOAT"
        self.tournament_profit = 0.0
        self.total_packs_given = 0

    def _get_historical_matchups(self):
        import os, json
        history_dir = os.path.join("data", "history")
        matchups = {}
        if not os.path.exists(history_dir):
            return matchups
            
        for file in os.listdir(history_dir):
            if not file.endswith(".json"): continue
            try:
                with open(os.path.join(history_dir, file), "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
                rounds = data.get("manager", {}).get("rounds", [])
                for rnd in rounds:
                    for match in rnd:
                        p1 = match.get("p1")
                        p2 = match.get("p2")
                        if not p1 or not p2: continue
                        
                        id1 = p1.get("konami_id") or p1.get("name", "")
                        id2 = p2.get("konami_id") or p2.get("name", "")
                        if not id1 or not id2: continue
                        
                        pair = tuple(sorted([id1, id2]))
                        matchups[pair] = matchups.get(pair, 0) + 1
            except:
                pass
        return matchups

    def to_dict(self):
        player_indexes = {player: idx for idx, player in enumerate(self.players)}
        return {
            "players": [
                {
                    "name": p.name,
                    "konami_id": p.konami_id,
                    "phone": p.phone,
                    "email": p.email,
                    "paid": getattr(p, "paid", False),
                    "invited": getattr(p, "invited", False),
                    "points": p.points,
                    "matches_played": p.matches_played,
                    "opponents": [player_indexes[o] for o in p.opponents if o in player_indexes],
                    "match_results": list(p.match_results),
                    "active": p.active,
                    "had_bye": p.had_bye,
                    "join_round": p.join_round,
                    "_omw": p._omw,
                    "_oomw": p._oomw,
                }
                for p in self.players
            ],
            "rounds": [
                [
                    {
                        "p1": player_indexes.get(match.p1),
                        "p2": player_indexes.get(match.p2),
                        "round_num": match.round_num,
                        "reported": match.reported,
                        "result_text": match.result_text,
                        "note": match.note,
                    }
                    for match in round_matches
                ]
                for round_matches in self.rounds
            ],
            "current_round": self.current_round,
            "total_rounds": self.total_rounds,
            "mode": self.mode,
            "status": self.status,
            "format_name": self.format_name,
            "tournament_profit": self.tournament_profit,
            "total_packs_given": self.total_packs_given,
        }

    @classmethod
    def from_dict(cls, data):
        manager = cls()
        manager.players = []

        for player_data in data.get("players", []):
            player = Player(
                player_data.get("name", ""),
                player_data.get("konami_id", ""),
                player_data.get("phone", ""),
                player_data.get("email", ""),
                player_data.get("paid", False),
                player_data.get("invited", False),
            )
            player.points = player_data.get("points", 0)
            player.matches_played = player_data.get("matches_played", 0)
            player.match_results = list(player_data.get("match_results", []))
            player.active = player_data.get("active", True)
            player.had_bye = player_data.get("had_bye", False)
            player.join_round = player_data.get("join_round", 0)
            player._omw = player_data.get("_omw", 0.3333)
            player._oomw = player_data.get("_oomw", 0.3333)
            manager.players.append(player)

        for index, player_data in enumerate(data.get("players", [])):
            if index >= len(manager.players):
                continue
            manager.players[index].opponents = [
                manager.players[opponent_idx]
                for opponent_idx in player_data.get("opponents", [])
                if isinstance(opponent_idx, int) and 0 <= opponent_idx < len(manager.players)
            ]

        manager.rounds = []
        for round_data in data.get("rounds", []):
            round_matches = []
            for match_data in round_data:
                p1_idx = match_data.get("p1")
                p2_idx = match_data.get("p2")
                p1 = manager.players[p1_idx] if isinstance(p1_idx, int) and 0 <= p1_idx < len(manager.players) else None
                p2 = manager.players[p2_idx] if isinstance(p2_idx, int) and 0 <= p2_idx < len(manager.players) else None
                match = Match(p1, p2, match_data.get("round_num", 0))
                match.reported = match_data.get("reported", False)
                match.result_text = match_data.get("result_text", "Pendiente")
                match.note = match_data.get("note", "")
                round_matches.append(match)
            manager.rounds.append(round_matches)

        manager.current_round = data.get("current_round", 0)
        manager.total_rounds = data.get("total_rounds", 0)
        manager.mode = data.get("mode", "swiss")
        manager.status = data.get("status", "setup")
        manager.format_name = data.get("format_name", "GOAT")
        manager.tournament_profit = data.get("tournament_profit", 0.0)
        manager.total_packs_given = data.get("total_packs_given", 0)
        manager.recalculate_all_player_stats()

        return manager
        
    def add_player(self, name, konami_id, phone="", email="", paid=False, invited=False):
        player = Player(name, konami_id, phone, email, paid, invited)
        self.players.append(player)
        return player

    def find_bye_match(self):
        for match in self.get_current_matches():
            if match.p1 and match.p2 is None and match.result_text == "BYE":
                return match
        return None

    def sort_matches_for_tables(self, matches):
        def match_score(match):
            if not match.p1 or not match.p2:
                return (0, 0, 0)
            p1_points = match.p1.points
            p2_points = match.p2.points
            return (1, max(p1_points, p2_points), p1_points + p2_points)

        matches.sort(key=match_score, reverse=True)

    def build_swiss_pairings(self, sorted_players):
        for allow_rematches in (False, True):
            bye_options = self.get_bye_options(sorted_players)
            for bye_player in bye_options:
                players_to_pair = [p for p in sorted_players if p != bye_player]
                pairs = self.find_pairing_plan(players_to_pair, allow_rematches)
                if pairs is not None:
                    return pairs, bye_player

        return [], sorted_players[-1] if sorted_players else None

    def get_bye_options(self, sorted_players):
        if len(sorted_players) % 2 == 0:
            return [None]

        lowest_first = list(reversed(sorted_players))
        preferred = [p for p in lowest_first if not p.had_bye]
        fallback = [p for p in lowest_first if p.had_bye]
        return preferred + fallback

    def find_pairing_plan(self, players, allow_rematches):
        if not players:
            return []

        p1 = players[0]
        candidate_players = players[1:]
        candidate_players = sorted(
            candidate_players,
            key=lambda p2: (
                p2 in p1.opponents,
                abs(p1.points - p2.points),
                -p2.points,
                p2.name.lower(),
            )
        )

        for p2 in candidate_players:
            if not allow_rematches and p2 in p1.opponents:
                continue

            remaining = [p for p in players[1:] if p != p2]
            rest = self.find_pairing_plan(remaining, allow_rematches)
            if rest is not None:
                return [(p1, p2)] + rest

        return None

    def add_late_player(self, name, konami_id, phone="", email="", paid=False, invited=False, penalty=True):
        new_player = self.add_player(name, konami_id, phone, email, paid, invited)

        if self.status != "running" or not self.rounds:
            return new_player, "ADDED_TO_SETUP", None

        import math
        num_players = len(self.players)
        if hasattr(self, "mode"):
            if self.mode == "swiss":
                if num_players <= 8: required = 3
                elif num_players <= 16: required = 4
                elif num_players <= 32: required = 5
                elif num_players <= 64: required = 6
                elif num_players <= 128: required = 7
                else: required = 8
                if getattr(self, "total_rounds", 0) < required:
                    self.total_rounds = required
            elif self.mode == "grinder" and num_players > 0:
                required = math.ceil(math.log2(num_players))
                if getattr(self, "total_rounds", 0) < required:
                    self.total_rounds = required

        new_player.join_round = self.current_round

        bye_match = self.find_bye_match()
        if bye_match:
            self.undo_match(bye_match)
            bye_player = bye_match.p1
            bye_match.p2 = new_player
            bye_match.result_text = "Pendiente"
            bye_match.reported = False
            if penalty:
                bye_match.note = f"Ingreso atrasado (>5 min). {new_player.name} inicia el match con 1 duelo perdido."
            else:
                bye_match.note = f"Ingreso de {new_player.name} a tiempo. Emparejamiento sin penalidad."

            bye_player.opponents.append(new_player)
            new_player.opponents.append(bye_player)
            self.sort_matches_for_tables(self.rounds[-1])
            return new_player, "PAIRED_WITH_BYE", bye_match

        # Check for another late player sitting out this round
        for match in self.rounds[-1]:
            if match.result_text == "LATE_LOSS" and match.p1 is None and match.p2 is not None:
                self.undo_match(match)
                late_player = match.p2
                
                match.p1 = late_player
                match.p2 = new_player
                match.result_text = "Pendiente"
                match.reported = False
                if penalty:
                    match.note = "Emparejamiento de jugadores atrasados. Tendrán menos tiempo en la ronda y 1 duelo perdido."
                else:
                    match.note = "Emparejamiento de jugadores. Sin penalidad de tiempo ni duelo."
                
                late_player.opponents.append(new_player)
                new_player.opponents.append(late_player)
                
                self.sort_matches_for_tables(self.rounds[-1])
                return new_player, "PAIRED_WITH_LATE", match

        if penalty:
            late_loss = Match(None, new_player, self.current_round)
            late_loss.report("P1_WIN")
            late_loss.result_text = "LATE_LOSS"
            late_loss.note = "Perdida administrativa por ingreso atrasado (>5 min)."
            new_player.had_bye = True
            self.rounds[-1].append(late_loss)
            self.sort_matches_for_tables(self.rounds[-1])
            return new_player, "ROUND_LOSS", late_loss
        else:
            bye_match = Match(new_player, None, self.current_round)
            bye_match.report("P1_WIN")
            bye_match.result_text = "BYE"
            bye_match.note = "BYE asignado por ingreso impar a tiempo."
            new_player.had_bye = True
            self.rounds[-1].append(bye_match)
            self.sort_matches_for_tables(self.rounds[-1])
            return new_player, "BYE", bye_match
        
    def start_tournament(self, mode="swiss", format_name="GOAT", total_rounds_override=None):
        self.mode = mode
        self.format_name = format_name
        num_players = len(self.players)
        
        if num_players < 2:
            raise ValueError("Se necesitan al menos 2 jugadores.")
            
        if total_rounds_override is not None:
            if total_rounds_override < 1:
                raise ValueError("La cantidad de rondas debe ser al menos 1.")
            self.total_rounds = total_rounds_override
        elif mode == "swiss":
            if num_players <= 8: self.total_rounds = 3
            elif num_players <= 16: self.total_rounds = 4
            elif num_players <= 32: self.total_rounds = 5
            elif num_players <= 64: self.total_rounds = 6
            elif num_players <= 128: self.total_rounds = 7
            else: self.total_rounds = 8
        else: # Grinder
            self.total_rounds = math.ceil(math.log2(num_players))
            
        self.status = "running"
        self.current_round = 0
        self.generate_next_round()
        
    def get_standings(self):
        # Calc OMW
        for p in self.players:
            if len(p.opponents) == 0:
                p._omw = 0.3333
            else:
                p._omw = sum([max(o.mw_percent, 0.3333) for o in p.opponents]) / len(p.opponents)
                
        # Calc OOMW
        for p in self.players:
            if len(p.opponents) == 0:
                p._oomw = 0.3333
            else:
                p._oomw = sum([o._omw for o in p.opponents]) / len(p.opponents)
                
        standings = sorted(self.players, key=lambda x: (x.active, x.points, x._omw, x._oomw), reverse=True)
        standings = self.apply_head_to_head_tiebreakers(standings)
        return standings

    def recalculate_all_player_stats(self):
        """
        Recalcula limpiamente puntos, partidas jugadas, historial de resultados (W/L/D)
        y oponentes de todos los jugadores basándose en los pareos y resultados oficiales.
        Garantiza consistencia absoluta e inmunidad contra estados corruptos o puntos duplicados.
        """
        for p in self.players:
            p.points = 0
            p.matches_played = 0
            p.match_results = []
            p.opponents = []
            p.had_bye = False

        for round_matches in self.rounds:
            for match in round_matches:
                p1 = match.p1
                p2 = match.p2

                if p1 and p2:
                    p1.opponents.append(p2)
                    p2.opponents.append(p1)

                if not match.reported:
                    continue

                res = match.result_text
                effective = res
                if isinstance(res, str) and "-" in res:
                    try:
                        parts = res.replace(" ", "").split("-")
                        s1, s2 = int(parts[0]), int(parts[1])
                        if s1 > s2: effective = "P1_WIN"
                        elif s2 > s1: effective = "P2_WIN"
                        elif s1 == s2 and s1 > 0: effective = "DRAW"
                        else: effective = "DOUBLE_LOSS"
                    except Exception:
                        pass

                if effective == "BYE":
                    if p1:
                        p1.points += 3
                        p1.matches_played += 1
                        p1.had_bye = True
                        p1.match_results.append('W')
                elif effective == "LATE_LOSS":
                    if p2:
                        p2.matches_played += 1
                        p2.match_results.append('L')
                elif effective == "P1_WIN":
                    if p1:
                        p1.points += 3
                        p1.matches_played += 1
                        p1.match_results.append('W')
                    if p2:
                        p2.points += 0
                        p2.matches_played += 1
                        p2.match_results.append('L')
                elif effective == "P2_WIN":
                    if p1:
                        p1.points += 0
                        p1.matches_played += 1
                        p1.match_results.append('L')
                    if p2:
                        p2.points += 3
                        p2.matches_played += 1
                        p2.match_results.append('W')
                elif effective == "DRAW":
                    if p1:
                        p1.points += 1
                        p1.matches_played += 1
                        p1.match_results.append('D')
                    if p2:
                        p2.points += 1
                        p2.matches_played += 1
                        p2.match_results.append('D')
                elif effective == "DOUBLE_LOSS":
                    if p1:
                        p1.points += 0
                        p1.matches_played += 1
                        p1.match_results.append('DL')
                    if p2:
                        p2.points += 0
                        p2.matches_played += 1
                        p2.match_results.append('DL')

        return self.get_standings()

    def standings_key(self, player):
        return (player.points, round(player._omw, 4), round(player._oomw, 4))

    def apply_head_to_head_tiebreakers(self, standings):
        ordered = []
        i = 0
        while i < len(standings):
            group_key = self.standings_key(standings[i])
            group = []
            while i < len(standings) and self.standings_key(standings[i]) == group_key:
                group.append(standings[i])
                i += 1

            if len(group) > 1:
                ordered.extend(self.sort_group_by_head_to_head(group))
            else:
                ordered.extend(group)

        return ordered

    def sort_group_by_head_to_head(self, group):
        h2h_points = self.get_head_to_head_points(group)

        if len(set(h2h_points.values())) <= 1:
            return group

        return sorted(group, key=lambda player: h2h_points[player], reverse=True)

    def get_head_to_head_points(self, group):
        group_set = set(group)
        h2h_points = {player: 0 for player in group}

        for round_matches in self.rounds:
            for match in round_matches:
                if match.p1 not in group_set or match.p2 not in group_set:
                    continue

                if match.result_text == "P1_WIN":
                    h2h_points[match.p1] += 3
                elif match.result_text == "P2_WIN":
                    h2h_points[match.p2] += 3
                elif match.result_text == "DRAW":
                    h2h_points[match.p1] += 1
                    h2h_points[match.p2] += 1

        return h2h_points

    def get_tiebreaker_notes(self, standings=None):
        standings = standings or self.get_standings()
        notes = {player: "" for player in standings}

        point_groups = {}
        for player in standings:
            point_groups.setdefault(player.points, []).append(player)

        for group in point_groups.values():
            if len(group) <= 1:
                continue

            exact_groups = {}
            for player in group:
                exact_groups.setdefault(self.standings_key(player), []).append(player)

            for exact_group in exact_groups.values():
                if len(exact_group) > 1:
                    h2h = self.get_head_to_head_points(exact_group)
                    for player in exact_group:
                        notes[player] = f"H2H {h2h[player]} pts"

                    if len(set(h2h.values())) <= 1:
                        for player in exact_group:
                            notes[player] = "H2H empatado"

            for player in group:
                if not notes[player]:
                    notes[player] = "OMW/OOMW"

        return notes

    def get_ranked_standings(self):
        standings = self.get_standings()
        ranked = []
        i = 0

        while i < len(standings):
            group_key = self.standings_key(standings[i])
            group = []
            while i < len(standings) and self.standings_key(standings[i]) == group_key:
                group.append(standings[i])
                i += 1

            if len(group) > 1:
                h2h_points = self.get_head_to_head_points(group)
                h2h_groups = []
                for player in group:
                    if not h2h_groups or h2h_groups[-1][0] != h2h_points[player]:
                        h2h_groups.append((h2h_points[player], [player]))
                    else:
                        h2h_groups[-1][1].append(player)
            else:
                h2h_groups = [(0, group)]

            for _, tied_players in h2h_groups:
                rank = len(ranked) + 1
                for player in tied_players:
                    ranked.append((rank, player))

        return ranked

    def get_prize_groups(self):
        ranked = self.get_ranked_standings()
        groups = []
        current_rank = None

        for rank, _ in ranked:
            if rank != current_rank:
                groups.append({"rank": rank, "count": 1})
                current_rank = rank
            else:
                groups[-1]["count"] += 1

        return groups
        
    def generate_next_round(self):
        if self.current_round >= self.total_rounds:
            self.status = "finished"
            return []
            
        # In grinder mode, anyone with a Loss is eliminated
        if self.mode == "grinder":
            for p in self.players:
                if 'L' in p.match_results or 'DL' in p.match_results:
                    p.active = False
                    
        self.current_round += 1
        active_players = [p for p in self.players if p.active]
        if self.current_round == 1:
            random.shuffle(active_players)
            historical = self._get_historical_matchups()
            if historical:
                paired = set()
                new_pairing = []
                for p1 in active_players:
                    if p1 in paired: continue
                    best_p2 = None
                    min_played = float('inf')
                    
                    id1 = p1.konami_id or p1.name
                    candidates = [p for p in active_players if p != p1 and p not in paired]
                    
                    if not candidates:
                        new_pairing.append(p1)
                        break
                        
                    random.shuffle(candidates)
                    
                    for p2 in candidates:
                        id2 = p2.konami_id or p2.name
                        pair = tuple(sorted([id1, id2]))
                        played_count = historical.get(pair, 0)
                        if played_count < min_played:
                            min_played = played_count
                            best_p2 = p2
                            
                    if best_p2:
                        new_pairing.extend([p1, best_p2])
                        paired.add(p1)
                        paired.add(best_p2)
                
                active_players = new_pairing
        matches = []
        
        if self.mode == "swiss":
            sorted_players = sorted(active_players, key=lambda x: x.points, reverse=True)
            pairing_plan, bye_player = self.build_swiss_pairings(sorted_players)

            if bye_player:
                m = Match(bye_player, None, self.current_round)
                m.report("P1_WIN")
                m.result_text = "BYE"
                bye_player.had_bye = True
                matches.append(m)

            for p1, p2 in pairing_plan:
                matches.append(Match(p1, p2, self.current_round))
                p1.opponents.append(p2)
                p2.opponents.append(p1)
        else:
            # Grinder simple pairing
            sorted_players = sorted(active_players, key=lambda x: x.points, reverse=True)
            for i in range(0, len(sorted_players), 2):
                p1 = sorted_players[i]
                if i+1 < len(sorted_players):
                    p2 = sorted_players[i+1]
                    matches.append(Match(p1, p2, self.current_round))
                else:
                    m = Match(p1, None, self.current_round)
                    m.report("P1_WIN")
                    m.result_text = "BYE"
                    p1.had_bye = True
                    matches.append(m)
                
        self.sort_matches_for_tables(matches)
        self.rounds.append(matches)
        return matches
        
    def get_current_matches(self):
        if not self.rounds:
            return []
        return self.rounds[-1]
        
    def all_matches_reported(self):
        return all(m.reported for m in self.get_current_matches())

    def drop_player(self, player_name, reason=None):
        for p in self.players:
            if p.name == player_name:
                p.active = False
                p.drop_reason = reason
                for m in self.get_current_matches():
                    if not m.reported:
                        if m.p1 == p:
                            m.report("P2_WIN")
                        elif m.p2 == p:
                            m.report("P1_WIN")
                return True
        return False

    def swap_pairings(self, match1_idx, p1_is_left, match2_idx, p2_is_left):
        current_matches = self.get_current_matches()
        if (
            match1_idx < 0 or match2_idx < 0
            or match1_idx >= len(current_matches)
            or match2_idx >= len(current_matches)
        ):
            return False
            
        m1 = current_matches[match1_idx]
        m2 = current_matches[match2_idx]

        for match in (m1, m2):
            if match.reported:
                self.undo_match(match)
        
        player_a = m1.p1 if p1_is_left else m1.p2
        player_b = m2.p1 if p2_is_left else m2.p2
        
        if m1.p1 and m1.p2:
            if m1.p2 in m1.p1.opponents: m1.p1.opponents.remove(m1.p2)
            if m1.p1 in m1.p2.opponents: m1.p2.opponents.remove(m1.p1)
        if m2.p1 and m2.p2:
            if m2.p2 in m2.p1.opponents: m2.p1.opponents.remove(m2.p2)
            if m2.p1 in m2.p2.opponents: m2.p2.opponents.remove(m2.p1)
            
        if p1_is_left:
            m1.p1 = player_b
        else:
            m1.p2 = player_b
            
        if p2_is_left:
            m2.p1 = player_a
        else:
            m2.p2 = player_a

        self.refresh_match_after_pairing_edit(m1)
        self.refresh_match_after_pairing_edit(m2)
            
        return True

    def refresh_match_after_pairing_edit(self, match):
        match.note = ""

        if match.p1 is None and match.p2 is not None:
            match.p1, match.p2 = match.p2, None

        if match.p1 and match.p2:
            match.p1.opponents.append(match.p2)
            match.p2.opponents.append(match.p1)
            match.reported = False
            match.result_text = "Pendiente"
        elif match.p1:
            match.report("P1_WIN")
            match.result_text = "BYE"
            match.p1.had_bye = True
        else:
            match.reported = False
            match.result_text = "Pendiente"

    def undo_match(self, match):
        if not match.reported:
            return
            
        result_type = match.result_text
        effective_type = result_type
        if isinstance(result_type, str) and "-" in result_type:
            try:
                parts = result_type.replace(" ", "").split("-")
                s1, s2 = int(parts[0]), int(parts[1])
                if s1 > s2:
                    effective_type = "P1_WIN"
                elif s2 > s1:
                    effective_type = "P2_WIN"
                elif s1 == s2 and s1 > 0:
                    effective_type = "DRAW"
                else:
                    effective_type = "DOUBLE_LOSS"
            except Exception:
                pass

        if effective_type == "BYE":
            if match.p1:
                match.p1.points -= 3
                match.p1.had_bye = False
                if match.p1.match_results: match.p1.match_results.pop()
        elif effective_type == "LATE_LOSS":
            if match.p2:
                match.p2.had_bye = False
                if match.p2.match_results: match.p2.match_results.pop()
        elif effective_type == "P1_WIN":
            if match.p1:
                match.p1.points -= 3
                if match.p1.match_results: match.p1.match_results.pop()
            if match.p2:
                match.p2.points -= 0
                if match.p2.match_results: match.p2.match_results.pop()
        elif effective_type == "P2_WIN":
            if match.p1:
                match.p1.points -= 0
                if match.p1.match_results: match.p1.match_results.pop()
            if match.p2:
                match.p2.points -= 3
                if match.p2.match_results: match.p2.match_results.pop()
        elif effective_type == "DRAW":
            if match.p1:
                match.p1.points -= 1
                if match.p1.match_results: match.p1.match_results.pop()
            if match.p2:
                match.p2.points -= 1
                if match.p2.match_results: match.p2.match_results.pop()
        elif effective_type == "DOUBLE_LOSS":
            if match.p1:
                match.p1.points -= 0
                if match.p1.match_results: match.p1.match_results.pop()
            if match.p2:
                match.p2.points -= 0
                if match.p2.match_results: match.p2.match_results.pop()
                
        if match.p1: match.p1.matches_played -= 1
        if match.p2: match.p2.matches_played -= 1
        
        match.reported = False
        match.result_text = "Pendiente"
        self.recalculate_all_player_stats()
        
    def rollback_round(self):
        if self.current_round <= 1:
            return False
            
        if self.status == "finished":
            self.status = "running"
            
        if self.rounds:
            last_matches = self.rounds.pop()
            late_players_to_remove = set()
            for m in last_matches:
                if m.reported:
                    self.undo_match(m)
                if m.p1 and m.p2:
                    if m.p2 in m.p1.opponents: m.p1.opponents.remove(m.p2)
                    if m.p1 in m.p2.opponents: m.p2.opponents.remove(m.p1)
                for player in (m.p1, m.p2):
                    if player and player.join_round == self.current_round:
                        late_players_to_remove.add(player)

            for player in late_players_to_remove:
                if player in self.players:
                    self.players.remove(player)
                    
        self.current_round -= 1
                
        return True

    def rollback_to_setup(self):
        if self.current_round != 1 or not self.rounds:
            return False

        self.rounds = []
        self.current_round = 0
        self.total_rounds = 0
        self.status = "setup"

        for player in self.players:
            player.points = 0
            player.matches_played = 0
            player.opponents = []
            player.match_results = []
            player.active = True
            player.had_bye = False
            player.join_round = 0
            player._omw = 0.3333
            player._oomw = 0.3333

        return True
