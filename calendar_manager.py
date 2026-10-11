"""
Gestor de Calendario y Programación de Torneos para Subarashii Duel Academy & Gestor de Torneos.

Funcionalidades:
- Programar torneos individuales con fecha, hora, formato, modo, premio y notas.
- Programar ciclos de ligas completas (ej. 4 u 8 domingos consecutivos con premio Ultimate Rare).
- Detectar si hay un torneo programado para el día de hoy o fecha seleccionada.
- Vincular torneos programados con el torneo real iniciado en el Gestor de Torneos.
- Suministrar los eventos al SyncManager para visualización en la Web Pública.
"""

import os
from datetime import datetime, timedelta
import sqlite3

from database import get_connection, migrate_calendar_and_leagues_schema

DAYS_ES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
MONTHS_ES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]


def parse_date_flexible(d_str):
    if not d_str:
        return None
    d_clean = str(d_str).strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y", "%d/%m/%y"):
        try:
            return datetime.strptime(d_clean, fmt)
        except ValueError:
            pass
    return None


def to_iso_date(d_str):
    dt = parse_date_flexible(d_str)
    if dt:
        return dt.strftime("%Y-%m-%d")
    return d_str


def to_display_date(d_str):
    dt = parse_date_flexible(d_str)
    if not dt:
        return str(d_str)
    day_name = DAYS_ES[dt.weekday()]
    return f"{day_name} {dt.strftime('%d-%m-%Y')}"


class CalendarManager:
    def __init__(self, conn=None):
        self._conn = conn

    def _get_cursor(self):
        if self._conn:
            return self._conn.cursor()
        conn = get_connection()
        return conn.cursor()

    def schedule_tournament(self, title, format_name, date, time="16:00", mode="swiss",
                            store_id=None, entry_fee=0.0, prize_description="", notes="", league_id=None):
        """
        Programa un torneo en la base de datos.
        """
        cursor = self._get_cursor()
        migrate_calendar_and_leagues_schema(cursor)
        iso_date = to_iso_date(date)
        now_str = datetime.now().isoformat()

        cursor.execute("""
            INSERT INTO scheduled_tournaments (
                title, format_name, date, time, mode, store_id, entry_fee,
                prize_description, notes, status, league_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PROGRAMADO', ?, ?)
        """, (
            title.strip(), format_name.strip(), iso_date, time.strip() if time else "16:00",
            mode.strip() if mode else "swiss", store_id, float(entry_fee or 0.0),
            prize_description.strip() if prize_description else "", notes.strip() if notes else "",
            league_id, now_str
        ))
        scheduled_id = cursor.lastrowid
        if hasattr(cursor, 'connection') and cursor.connection:
            cursor.connection.commit()

        return self.get_scheduled_tournament_by_id(scheduled_id)

    def get_scheduled_tournament_by_id(self, scheduled_id):
        cursor = self._get_cursor()
        cursor.execute("SELECT * FROM scheduled_tournaments WHERE id = ?", (scheduled_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_scheduled_tournaments(self, include_finished=True, format_filter=None):
        """
        Retorna la lista de torneos programados ordenados cronológicamente.
        """
        cursor = self._get_cursor()
        migrate_calendar_and_leagues_schema(cursor)

        query = "SELECT st.*, s.name as store_name FROM scheduled_tournaments st LEFT JOIN stores s ON st.store_id = s.id WHERE 1=1"
        params = []

        if not include_finished:
            query += " AND st.status IN ('PROGRAMADO', 'EN_CURSO')"

        if format_filter and format_filter != "TODOS":
            query += " AND UPPER(st.format_name) = UPPER(?)"
            params.append(format_filter)

        query += " ORDER BY st.date ASC, st.time ASC"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        result = []
        for r in rows:
            d = dict(r)
            d['display_date'] = to_display_date(d['date'])
            result.append(d)
        return result

    def get_tournaments_for_date(self, target_date=None):
        """
        Busca torneos programados para una fecha específica (por defecto hoy).
        Acepta tanto YYYY-MM-DD como DD-MM-YY / DD-MM-YYYY.
        """
        cursor = self._get_cursor()
        migrate_calendar_and_leagues_schema(cursor)

        if not target_date:
            dt_target = datetime.now()
        else:
            dt_target = parse_date_flexible(target_date) or datetime.now()

        iso_target = dt_target.strftime("%Y-%m-%d")
        dmy_target = dt_target.strftime("%d-%m-%y")
        dmy_full = dt_target.strftime("%d-%m-%Y")

        cursor.execute("""
            SELECT st.*, s.name as store_name 
            FROM scheduled_tournaments st
            LEFT JOIN stores s ON st.store_id = s.id
            WHERE (st.date = ? OR st.date = ? OR st.date = ?)
              AND st.status != 'CANCELADO'
            ORDER BY st.time ASC
        """, (iso_target, dmy_target, dmy_full))

        rows = cursor.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d['display_date'] = to_display_date(d['date'])
            result.append(d)
        return result

    def get_upcoming_tournaments(self, limit=10):
        """
        Retorna los próximos torneos futuros programados a partir de hoy.
        """
        cursor = self._get_cursor()
        migrate_calendar_and_leagues_schema(cursor)

        today_iso = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("""
            SELECT st.*, s.name as store_name
            FROM scheduled_tournaments st
            LEFT JOIN stores s ON st.store_id = s.id
            WHERE st.date >= ? AND st.status IN ('PROGRAMADO', 'EN_CURSO')
            ORDER BY st.date ASC, st.time ASC
            LIMIT ?
        """, (today_iso, limit))

        rows = cursor.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d['display_date'] = to_display_date(d['date'])
            result.append(d)
        return result

    def update_scheduled_status(self, scheduled_id, status, tournament_id=None):
        cursor = self._get_cursor()
        if tournament_id is not None:
            cursor.execute("""
                UPDATE scheduled_tournaments
                SET status = ?, tournament_id = ?
                WHERE id = ?
            """, (status, tournament_id, scheduled_id))
        else:
            cursor.execute("""
                UPDATE scheduled_tournaments
                SET status = ?
                WHERE id = ?
            """, (status, scheduled_id))

        if hasattr(cursor, 'connection') and cursor.connection:
            cursor.connection.commit()

    def delete_scheduled_tournament(self, scheduled_id):
        cursor = self._get_cursor()
        cursor.execute("DELETE FROM scheduled_tournaments WHERE id = ?", (scheduled_id,))
        if hasattr(cursor, 'connection') and cursor.connection:
            cursor.connection.commit()

    def schedule_league_cycle(self, league_name, format_name, start_date, num_stops=8,
                              prize_title="Carta Ultimate Rare", prize_description="",
                              entry_fee=3000.0, store_id=None, time="16:00"):
        """
        Programa de forma automatizada un ciclo completo de Liga (ej. 4 u 8 domingos).
        Crea el registro de la Liga y todos los torneos dominicales correspondientes en el calendario.
        """
        cursor = self._get_cursor()
        migrate_calendar_and_leagues_schema(cursor)

        dt_start = parse_date_flexible(start_date) or datetime.now()
        now_str = datetime.now().isoformat()

        # Calcular fecha fin
        dt_end = dt_start + timedelta(weeks=num_stops - 1)

        cursor.execute("""
            INSERT INTO leagues (
                name, format_name, start_date, end_date, frequency, total_stops,
                store_id, prize_title, prize_description, points_system, status, created_at
            ) VALUES (?, ?, ?, ?, 'DOMINGOS', ?, ?, ?, ?, 'STANDARD', 'PREPARADA', ?)
        """, (
            league_name.strip(), format_name.strip(), dt_start.strftime("%Y-%m-%d"),
            dt_end.strftime("%Y-%m-%d"), num_stops, store_id, prize_title.strip(),
            prize_description.strip() if prize_description else f"Premio al Campeón: {prize_title}",
            now_str
        ))
        league_id = cursor.lastrowid

        time_clean = time.strip() if (time and str(time).strip()) else "16:00"

        # Generar las paradas dominicales (1 parada por semana)
        created_stops = []
        for stop_idx in range(1, num_stops + 1):
            stop_date = dt_start + timedelta(weeks=stop_idx - 1)
            stop_date_iso = stop_date.strftime("%Y-%m-%d")
            stop_title = f"{league_name} - Fecha #{stop_idx}"

            cursor.execute("""
                INSERT INTO scheduled_tournaments (
                    title, format_name, date, time, mode, store_id, entry_fee,
                    prize_description, notes, status, league_id, created_at
                ) VALUES (?, ?, ?, ?, 'swiss', ?, ?, ?, ?, 'PROGRAMADO', ?, ?)
            """, (
                stop_title, format_name.strip(), stop_date_iso, time_clean, store_id,
                float(entry_fee or 0.0), f"Puntos de Liga + Pozo para {prize_title}",
                f"Parada oficial #{stop_idx} de {num_stops} de la {league_name}",
                league_id, now_str
            ))
            sched_id = cursor.lastrowid

            cursor.execute("""
                INSERT INTO league_stops (league_id, stop_number, scheduled_tournament_id, date, status)
                VALUES (?, ?, ?, ?, 'PROGRAMADO')
            """, (league_id, stop_idx, sched_id, stop_date_iso))

            created_stops.append({
                "stop_number": stop_idx,
                "scheduled_id": sched_id,
                "date": stop_date_iso,
                "display_date": to_display_date(stop_date_iso),
                "title": stop_title
            })

        if hasattr(cursor, 'connection') and cursor.connection:
            cursor.connection.commit()

        return {
            "league_id": league_id,
            "name": league_name,
            "format": format_name,
            "total_stops": num_stops,
            "stops": created_stops
        }
