"""
Motor de Ligas Competitivas para Subarashii Duel Academy.

Diseñado para soportar ciclos de ligas dominicales de 1 a 2 meses (4 u 8 paradas)
con premio mayor acumulativo (Carta Ultimate Rare de alto valor) y vinculación total con:
1. Calendario de Torneos (scheduled_tournaments)
2. Gestor de Torneos Suizos (tournaments / tournament_results)
3. Subarashii Duel Academy (Rating ELO, Niveles y Dormitorios)
4. Tienda y Rentabilidad (Amortización del costo de la carta Ultimate)
"""

from datetime import datetime, timedelta
import sqlite3
import json

from database import get_connection, migrate_calendar_and_leagues_schema


class LeagueEngine:
    def __init__(self, conn=None):
        self._conn = conn

    def _get_cursor(self):
        if self._conn:
            return self._conn.cursor()
        conn = get_connection()
        return conn.cursor()

    def get_all_leagues(self):
        cursor = self._get_cursor()
        migrate_calendar_and_leagues_schema(cursor)
        cursor.execute("""
            SELECT l.*, s.name as store_name,
                   (SELECT COUNT(*) FROM league_stops WHERE league_id = l.id) as scheduled_stops_count,
                   (SELECT COUNT(*) FROM league_stops WHERE league_id = l.id AND status = 'FINALIZADO') as finished_stops_count
            FROM leagues l
            LEFT JOIN stores s ON l.store_id = s.id
            ORDER BY l.id DESC
        """)
        return [dict(r) for r in cursor.fetchall()]

    def get_league_by_id(self, league_id):
        cursor = self._get_cursor()
        migrate_calendar_and_leagues_schema(cursor)
        cursor.execute("""
            SELECT l.*, s.name as store_name
            FROM leagues l
            LEFT JOIN stores s ON l.store_id = s.id
            WHERE l.id = ?
        """, (league_id,))
        row = cursor.fetchone()
        if not row:
            return None
        league = dict(row)

        # Cargar paradas asociadas
        cursor.execute("""
            SELECT ls.*, st.title, st.time, st.format_name, st.entry_fee, st.status as sched_status
            FROM league_stops ls
            LEFT JOIN scheduled_tournaments st ON ls.scheduled_tournament_id = st.id
            WHERE ls.league_id = ?
            ORDER BY ls.stop_number ASC
        """, (league_id,))
        league['stops'] = [dict(r) for r in cursor.fetchall()]
        return league

    def calculate_league_standings(self, league_id, drop_worst_stop=True):
        """
        Calcula la tabla de posiciones acumulada de la liga:
        Puntuación estándar:
        - 1er Lugar: 10 pts
        - 2do Lugar: 7 pts
        - 3er - 4to Lugar: 5 pts
        - 5to - 8vo Lugar: 3 pts
        - Asistencia por fecha: +2 pts
        - Victorias en suizo: +1 pt por partida ganada
        
        Si drop_worst_stop=True y la liga tiene 6+ paradas, se descarta la peor fecha de cada duelista.
        """
        cursor = self._get_cursor()
        league = self.get_league_by_id(league_id)
        if not league:
            return []

        # Buscar todos los torneos jugados que corresponden a las paradas de la liga
        cursor.execute("""
            SELECT ls.stop_number, ls.tournament_id, t.date
            FROM league_stops ls
            JOIN tournaments t ON ls.tournament_id = t.id
            WHERE ls.league_id = ? AND ls.tournament_id IS NOT NULL
            ORDER BY ls.stop_number ASC
        """, (league_id,))
        finished_stops = [dict(r) for r in cursor.fetchall()]

        if not finished_stops:
            return []

        t_ids = [s['tournament_id'] for s in finished_stops]
        placeholders = ",".join("?" * len(t_ids))

        # Obtener resultados de jugadores en esos torneos
        cursor.execute(f"""
            SELECT tr.tournament_id, tr.placement_points, tr.match_points, tr.attendance,
                   p.id as player_id, p.name as player_name,
                   ap.dorm, ap.current_rating
            FROM tournament_results tr
            JOIN league_profiles lp ON tr.league_profile_id = lp.id
            JOIN players p ON lp.player_id = p.id
            LEFT JOIN academy_profiles ap ON ap.player_id = p.id AND ap.format_name = 'GLOBAL'
            WHERE tr.tournament_id IN ({placeholders})
        """, t_ids)

        results = cursor.fetchall()

        # Agrupar por jugador
        players_data = {}
        for r in results:
            pid = r['player_id']
            if pid not in players_data:
                players_data[pid] = {
                    'player_id': pid,
                    'name': r['player_name'],
                    'dorm': r['dorm'] or 'Slifer Red',
                    'rating': r['current_rating'] or 1000,
                    'stops_attended': 0,
                    'stop_scores': {},
                    'total_match_wins': 0,
                    'first_places': 0,
                }

            # Cálculo de puntos de esta parada:
            # placement (10/5), match_points (victorias), attendance (+2)
            pts = 0
            if r['placement_points'] == 10:
                pts += 10
                players_data[pid]['first_places'] += 1
            elif r['placement_points'] == 5:
                pts += 5
            elif r['placement_points'] > 0:
                pts += r['placement_points']

            pts += (r['match_points'] or 0)
            if r['attendance']:
                pts += 2
                players_data[pid]['stops_attended'] += 1

            tid = r['tournament_id']
            players_data[pid]['stop_scores'][tid] = pts
            players_data[pid]['total_match_wins'] += (r['match_points'] or 0)

        # Aplicar regla de descarte si corresponde (ej. descarte de la fecha con menor puntuación si se jugaron 6+ fechas)
        standings = []
        for pid, pdata in players_data.items():
            all_scores = list(pdata['stop_scores'].values())
            raw_total = sum(all_scores)

            if drop_worst_stop and len(all_scores) >= 6:
                worst_score = min(all_scores)
                net_total = raw_total - worst_score
                dropped_score = worst_score
            else:
                net_total = raw_total
                dropped_score = 0

            pdata['raw_total'] = raw_total
            pdata['net_total'] = net_total
            pdata['dropped_score'] = dropped_score
            standings.append(pdata)

        # Ordenar por puntos netos desc, primeros lugares desc, rating desc
        standings.sort(key=lambda x: (x['net_total'], x['first_places'], x['total_match_wins'], x['rating']), reverse=True)

        for idx, row in enumerate(standings, 1):
            row['rank'] = idx

        return standings

    def estimate_prize_economics(self, num_players_per_stop=12, total_stops=8, entry_fee=3000.0, card_cost=120000.0):
        """
        Proyección financiera de la Liga para amortizar la Carta Ultimate Rare:
        - Total de entradas recaudadas.
        - Porcentaje destinado a la carta Ultimate.
        - Saldo restante para sobres/premios por fecha.
        - Margen o utilidad para la tienda.
        """
        total_entries = num_players_per_stop * total_stops
        gross_income = total_entries * entry_fee
        funding_percent = (card_cost / gross_income * 100) if gross_income > 0 else 0
        remaining_pool = gross_income - card_cost
        per_stop_secondary_prizes = remaining_pool / total_stops if total_stops > 0 else 0

        return {
            "total_entries": total_entries,
            "gross_income": gross_income,
            "card_cost": card_cost,
            "funding_percent": round(funding_percent, 1),
            "remaining_pool": max(0, remaining_pool),
            "per_stop_secondary_prizes": max(0, round(per_stop_secondary_prizes, 0)),
            "is_sustainable": gross_income >= card_cost
        }
