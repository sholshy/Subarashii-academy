"""
Gestor de Temporadas para Subarashii Duel Academy.

Permite:
- Obtener el estado de la temporada activa o crear una por defecto (Temporada 1).
- Calcular métricas desde la última temporada hasta la fecha:
    * Días transcurridos y fechas min/max.
    * Cantidad de torneos finalizados jugados en la temporada.
    * Cantidad de partidas oficiales disputadas.
    * Proyección de cierre si se configuró por fecha o por cantidad de torneos.
- Configurar reglas de cierre (por FECHA o por CANTIDAD DE TORNEOS).
- Cerrar formalmente la temporada actual:
    * Toma un snapshot en `academy_season_players` con el rating, dormitorio, W/L y partidas finales.
    * Actualiza `academy_seasons` a status='CLOSED'.
    * Crea la siguiente temporada activa.
"""
from datetime import datetime
import os
import sys

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BASE not in sys.path:
    sys.path.insert(0, _BASE)

from database import get_connection, migrate_academy_schema


def _parse_custom_date(d_str):
    if not d_str:
        return None
    for fmt in ("%d-%m-%y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(d_str.strip(), fmt)
        except ValueError:
            pass
    return None


class SeasonManager:
    def __init__(self):
        pass

    def get_or_create_active_season(self, cursor):
        migrate_academy_schema(cursor)
        cursor.execute("SELECT * FROM academy_seasons WHERE status = 'ACTIVE' ORDER BY number DESC LIMIT 1")
        row = cursor.fetchone()
        if row:
            return dict(row)

        # Buscar última temporada cerrada para saber el número siguiente
        cursor.execute("SELECT number, end_date FROM academy_seasons WHERE status = 'CLOSED' ORDER BY number DESC LIMIT 1")
        last_closed = cursor.fetchone()

        if last_closed:
            next_num = (last_closed['number'] or 1) + 1
            start_date = last_closed['end_date'] or datetime.now().strftime("%Y-%m-%d")
        else:
            next_num = 1
            # Fecha del primer torneo registrado si existe
            cursor.execute("""
                SELECT date FROM tournaments
                WHERE id NOT IN (SELECT DISTINCT tournament_id FROM tournament_matches WHERE result_text = 'Pendiente')
                ORDER BY
                    CASE WHEN substr(date, 3, 1) = '-' AND substr(date, 6, 1) = '-'
                         THEN '20' || substr(date, 7, 2) || '-' || substr(date, 4, 2) || '-' || substr(date, 1, 2)
                         ELSE date END ASC,
                    id ASC LIMIT 1
            """)
            first_t = cursor.fetchone()
            start_date = first_t['date'] if first_t else datetime.now().strftime("%d-%m-%y")

        season_id = f"SEASON_{next_num}"
        season_name = f"Temporada {next_num}"

        cursor.execute("""
            INSERT INTO academy_seasons (id, number, name, start_date, status, close_type, target_value)
            VALUES (?, ?, ?, ?, 'ACTIVE', 'DATE', NULL)
        """, (season_id, next_num, season_name, start_date))
        if hasattr(cursor, 'connection') and cursor.connection:
            cursor.connection.commit()

        cursor.execute("SELECT * FROM academy_seasons WHERE id = ?", (season_id,))
        return dict(cursor.fetchone())

    def get_season_metrics(self, cursor):
        """
        Calcula el progreso en tiempo real de la temporada activa:
        - Días transcurridos desde el inicio de temporada hasta hoy.
        - Cantidad de torneos finalizados jugados en la temporada.
        - Partidas oficiales jugadas y jugadores activos.
        - Fechas extremas de los torneos jugados.
        """
        active = self.get_or_create_active_season(cursor)
        season_start = active['start_date']
        dt_start = _parse_custom_date(season_start) or datetime.now()
        dt_now = datetime.now()
        days_elapsed = max(0, (dt_now - dt_start).days)

        # Buscar torneos finalizados
        # Para que sea preciso, contamos torneos desde la fecha de inicio
        cursor.execute("""
            SELECT t.id, t.date, t.format_name,
                   (SELECT COUNT(*) FROM tournament_results tr WHERE tr.tournament_id = t.id) as players_cnt
            FROM tournaments t
            WHERE t.id NOT IN (SELECT DISTINCT tournament_id FROM tournament_matches WHERE result_text = 'Pendiente')
              AND (
                  SELECT COUNT(*) FROM tournament_matches tm
                  WHERE tm.tournament_id = t.id AND tm.result_text IN ('P1_WIN', 'P2_WIN', 'DRAW')
              ) > 0
            ORDER BY
                CASE WHEN substr(t.date, 3, 1) = '-' AND substr(t.date, 6, 1) = '-'
                     THEN '20' || substr(t.date, 7, 2) || '-' || substr(t.date, 4, 2) || '-' || substr(t.date, 1, 2)
                     ELSE t.date END ASC,
                t.id ASC
        """)
        all_tourneys = [dict(r) for r in cursor.fetchall()]

        # Filtrar torneos correspondientes a esta temporada (posteriores o iguales a season_start)
        season_tourneys = []
        for t in all_tourneys:
            dt_t = _parse_custom_date(t['date'])
            if not dt_t or dt_t >= dt_start.replace(hour=0, minute=0, second=0):
                season_tourneys.append(t)

        # Si no hubo filtro de fecha estricto porque los torneos iniciales definen la temporada 1:
        if not season_tourneys and all_tourneys:
            season_tourneys = all_tourneys

        tournaments_count = len(season_tourneys)
        t_ids = [t['id'] for t in season_tourneys]

        total_matches = 0
        if t_ids:
            placeholders = ",".join("?" * len(t_ids))
            cursor.execute(f"""
                SELECT COUNT(*) as c FROM tournament_matches
                WHERE tournament_id IN ({placeholders}) AND result_text IN ('P1_WIN', 'P2_WIN', 'DRAW')
            """, t_ids)
            total_matches = cursor.fetchone()['c']

        cursor.execute("SELECT COUNT(*) as c FROM academy_profiles WHERE format_name = 'GLOBAL' AND matches_played > 0")
        active_players = cursor.fetchone()['c']

        min_t_date = season_tourneys[0]['date'] if season_tourneys else season_start
        max_t_date = season_tourneys[-1]['date'] if season_tourneys else season_start

        # Revisar criterio de cierre
        close_type = active.get('close_type') or 'DATE'
        target_val = active.get('target_value') or ''
        is_ready_to_close = False
        progress_text = ""

        if close_type == 'TOURNAMENT_COUNT' and target_val.isdigit():
            target_int = int(target_val)
            is_ready_to_close = tournaments_count >= target_int
            progress_text = f"{tournaments_count} / {target_int} torneos jugados"
        elif close_type == 'DATE' and target_val:
            dt_target = _parse_custom_date(target_val)
            if dt_target:
                is_ready_to_close = dt_now >= dt_target
                days_left = (dt_target - dt_now).days
                if days_left >= 0:
                    progress_text = f"Faltan {days_left} días para el cierre ({target_val})"
                else:
                    progress_text = f"Fecha de cierre alcanzada ({abs(days_left)} días atrás)"

        return {
            'season': active,
            'days_elapsed': days_elapsed,
            'tournaments_count': tournaments_count,
            'total_matches': total_matches,
            'active_players': active_players,
            'first_tournament_date': min_t_date,
            'last_tournament_date': max_t_date,
            'is_ready_to_close': is_ready_to_close,
            'progress_text': progress_text,
            'tournaments_list': season_tourneys,
        }

    def update_season_config(self, cursor, name, start_date, close_type, target_value):
        active = self.get_or_create_active_season(cursor)
        cursor.execute("""
            UPDATE academy_seasons
            SET name = ?, start_date = ?, close_type = ?, target_value = ?
            WHERE id = ?
        """, (name, start_date, close_type, target_value, active['id']))
        if hasattr(cursor, 'connection') and cursor.connection:
            cursor.connection.commit()

    def close_season(self, cursor, end_date=None, auto_start_next=True):
        """
        Cierra formalmente la temporada actual:
        1. Guarda el estado final de todos los duelistas en academy_season_players.
        2. Marca academy_seasons como 'CLOSED'.
        3. Abre la siguiente temporada si auto_start_next es True.
        """
        active = self.get_or_create_active_season(cursor)
        actual_end_date = end_date or datetime.now().strftime("%Y-%m-%d")

        # Snapshot de duelistas
        cursor.execute("""
            SELECT id, current_rating, dorm, matches_played, wins
            FROM academy_profiles
            WHERE format_name = 'GLOBAL'
        """)
        profiles = cursor.fetchall()
        for p in profiles:
            cursor.execute("""
                INSERT INTO academy_season_players (season_id, academy_profile_id, final_rating, final_dorm, matches_played, wins)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (active['id'], p['id'], p['current_rating'], p['dorm'], p['matches_played'], p['wins']))

        # Contar torneos de la temporada
        cursor.execute("""
            SELECT COUNT(DISTINCT tournament_id) as cnt FROM tournament_matches
            WHERE result_text IN ('P1_WIN', 'P2_WIN', 'DRAW')
        """)
        t_cnt = cursor.fetchone()['cnt']

        cursor.execute("""
            UPDATE academy_seasons
            SET status = 'CLOSED', end_date = ?, tournaments_count = ?, players_count = ?
            WHERE id = ?
        """, (actual_end_date, t_cnt, len(profiles), active['id']))

        new_season = None
        if auto_start_next:
            new_num = (active['number'] or 1) + 1
            new_id = f"SEASON_{new_num}"
            new_name = f"Temporada {new_num}"
            cursor.execute("""
                INSERT INTO academy_seasons (id, number, name, start_date, status, close_type, target_value)
                VALUES (?, ?, ?, ?, 'ACTIVE', 'DATE', NULL)
            """, (new_id, new_num, new_name, actual_end_date))
            cursor.execute("SELECT * FROM academy_seasons WHERE id = ?", (new_id,))
            new_season = dict(cursor.fetchone())

        if hasattr(cursor, 'connection') and cursor.connection:
            cursor.connection.commit()

        return active, new_season

    def get_all_seasons_history(self, cursor):
        cursor.execute("""
            SELECT s.*,
                   (SELECT COUNT(*) FROM academy_season_players WHERE season_id = s.id) as archived_players
            FROM academy_seasons s
            ORDER BY s.number DESC
        """)
        return [dict(r) for r in cursor.fetchall()]

    def can_revert_last_season(self, cursor):
        """
        Retorna (True, prev_season_dict) si es posible revertir el cierre de la temporada anterior.
        Solo se permite revertir si la temporada activa actual es posterior a la 1
        y existe la temporada inmediatamente anterior en estado CLOSED.
        """
        active = self.get_or_create_active_season(cursor)
        if not active or (active.get('number', 1) <= 1):
            return False, None

        prev_num = (active.get('number') or 2) - 1
        cursor.execute("SELECT * FROM academy_seasons WHERE number = ? AND status = 'CLOSED'", (prev_num,))
        row = cursor.fetchone()
        if not row:
            return False, None

        return True, dict(row)

    def revert_last_season_close(self, cursor):
        """
        Revierte el cierre de la última temporada:
        1. Elimina la temporada actual vacía que se creó automáticamente.
        2. Elimina los registros archivados de academy_season_players de la temporada anterior.
        3. Reactiva la temporada anterior dejándola nuevamente como 'ACTIVE'.
        """
        can_revert, prev_season = self.can_revert_last_season(cursor)
        if not can_revert or not prev_season:
            raise ValueError("No hay temporadas anteriores en estado cerrado que se puedan revertir.")

        active = self.get_or_create_active_season(cursor)

        # 1. Eliminar la temporada actual recién creada
        cursor.execute("DELETE FROM academy_seasons WHERE id = ?", (active['id'],))

        # 2. Eliminar el snapshot de jugadores de la temporada que se reabre
        cursor.execute("DELETE FROM academy_season_players WHERE season_id = ?", (prev_season['id'],))

        # 3. Restaurar la temporada anterior como ACTIVA
        cursor.execute("""
            UPDATE academy_seasons
            SET status = 'ACTIVE', end_date = NULL, tournaments_count = NULL, players_count = NULL
            WHERE id = ?
        """, (prev_season['id'],))

        if hasattr(cursor, 'connection') and cursor.connection:
            cursor.connection.commit()

        cursor.execute("SELECT * FROM academy_seasons WHERE id = ?", (prev_season['id'],))
        return dict(cursor.fetchone())
