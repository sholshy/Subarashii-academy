import os
import json
import uuid
import random
import string
from datetime import datetime
import sqlite3

from database import get_connection, migrate_calendar_and_leagues_schema

def migrate_rooms_schema(cursor):
    """
    Crea las tablas para el sistema interactivo de Salas de Torneo (Check-in QR, Lobby y Pareos Móviles).
    """
    try:
        migrate_calendar_and_leagues_schema(cursor)
    except Exception:
        pass

    # Tablas base necesarias para integridad referencial (Foreign Keys) en Render o BDs limpias
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            konami_id TEXT UNIQUE,
            name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            slug TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS academy_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            store_id INTEGER,
            format_name TEXT NOT NULL,
            current_rating INTEGER DEFAULT 1000,
            highest_rating INTEGER DEFAULT 1000,
            dorm TEXT DEFAULT 'Slifer Red',
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            matches_played INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            title TEXT,
            FOREIGN KEY(player_id) REFERENCES players(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scheduled_tournaments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            format_name TEXT NOT NULL,
            event_date TEXT NOT NULL,
            start_time TEXT,
            description TEXT,
            max_players INTEGER,
            status TEXT DEFAULT 'UPCOMING',
            created_at TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tournament_rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_code TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            format_name TEXT NOT NULL,
            scheduled_tournament_id INTEGER,
            status TEXT DEFAULT 'LOBBY',
            current_round INTEGER DEFAULT 0,
            live_data_json TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY(scheduled_tournament_id) REFERENCES scheduled_tournaments(id) ON DELETE SET NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS room_checkins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            session_token TEXT NOT NULL,
            player_id INTEGER,
            player_name TEXT NOT NULL,
            konami_id TEXT,
            dorm TEXT DEFAULT 'Estudiante de Intercambio',
            deck_archetype TEXT,
            payment_status TEXT DEFAULT 'PENDING',
            status TEXT DEFAULT 'CONFIRMED',
            checked_in_at TEXT,
            FOREIGN KEY(room_id) REFERENCES tournament_rooms(id) ON DELETE CASCADE,
            FOREIGN KEY(player_id) REFERENCES players(id) ON DELETE SET NULL,
            UNIQUE(room_id, session_token)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS room_trade_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            player_name TEXT NOT NULL,
            session_token TEXT,
            post_type TEXT NOT NULL DEFAULT 'BUSCO',
            card_name TEXT NOT NULL,
            card_id INTEGER,
            card_image_url TEXT,
            rarity TEXT,
            language TEXT,
            edition TEXT,
            notes TEXT,
            created_at TEXT,
            FOREIGN KEY(room_id) REFERENCES tournament_rooms(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS room_match_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            round_num INTEGER NOT NULL,
            table_num INTEGER NOT NULL,
            reported_by TEXT NOT NULL,
            p1_name TEXT NOT NULL,
            p2_name TEXT NOT NULL,
            score_p1 INTEGER NOT NULL,
            score_p2 INTEGER NOT NULL,
            result_type TEXT NOT NULL,
            status TEXT DEFAULT 'PENDING_CONFIRMATION',
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY(room_id) REFERENCES tournament_rooms(id) ON DELETE CASCADE,
            UNIQUE(room_id, round_num, table_num)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS room_player_drops (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            player_name TEXT NOT NULL,
            session_token TEXT,
            round_num INTEGER NOT NULL,
            dropped_at TEXT NOT NULL,
            status TEXT DEFAULT 'CONFIRMED',
            FOREIGN KEY(room_id) REFERENCES tournament_rooms(id) ON DELETE CASCADE,
            UNIQUE(room_id, player_name)
        )
    ''')

    try:
        cursor.execute("SELECT COUNT(*) FROM players")
        row = cursor.fetchone()
        if not row or row[0] == 0:
            seed_players_from_snapshot(cursor)
    except Exception:
        pass

def seed_players_from_snapshot(cursor=None):
    """
    Popula las tablas players y academy_profiles con los datos del último snapshot publicado.
    Garantiza que la búsqueda en vivo y check-in por celular reconozca a todos los duelistas oficiales
    incluso en entornos cloud sin base de datos SQLite preexistente.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    manifest_path = os.path.join(base_dir, "mock_server", "public_api", "manifest.json")
    if not os.path.exists(manifest_path):
        return
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        snapshot_filename = manifest.get("latest_snapshot")
        if not snapshot_filename:
            return
        snapshot_path = os.path.join(base_dir, "mock_server", "public_api", snapshot_filename)
        if not os.path.exists(snapshot_path):
            return
        with open(snapshot_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        leaderboard = data.get("leaderboard", [])
        if not leaderboard:
            return

        from database import get_connection
        should_commit = False
        if cursor is None:
            conn = get_connection()
            cursor = conn.cursor()
            should_commit = True
        else:
            conn = getattr(cursor, 'connection', None)

        cursor.execute("CREATE TABLE IF NOT EXISTS stores (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, is_active BOOLEAN DEFAULT 0)")
        cursor.execute("INSERT OR IGNORE INTO stores (id, name, is_active) VALUES (1, 'Subarashii Chile', 1)")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                konami_id TEXT UNIQUE,
                name TEXT NOT NULL,
                phone TEXT,
                email TEXT,
                slug TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS academy_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER NOT NULL,
                store_id INTEGER,
                format_name TEXT NOT NULL,
                current_rating INTEGER DEFAULT 1000,
                highest_rating INTEGER DEFAULT 1000,
                dorm TEXT DEFAULT 'Slifer Red',
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                matches_played INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                title TEXT,
                FOREIGN KEY(player_id) REFERENCES players(id) ON DELETE CASCADE
            )
        ''')

        for p in leaderboard:
            p_id = p.get("player_id")
            name = p.get("name")
            if not name or not name.strip():
                continue
            name_clean = name.strip()
            slug = p.get("slug")
            dorm = p.get("dorm") or "Slifer Red"
            rating = p.get("current_rating", 1000)
            highest = p.get("highest_rating", rating)
            level = p.get("level", 1)
            xp = p.get("xp", 0)
            matches = p.get("matches_played", 0)
            wins = p.get("wins", 0)
            losses = p.get("losses", 0)
            kid = p.get("konami_id")

            # Insert or update player
            cursor.execute("SELECT id FROM players WHERE id = ? OR LOWER(name) = LOWER(?)", (p_id, name_clean))
            row = cursor.fetchone()
            if not row:
                cursor.execute("""
                    INSERT INTO players (id, konami_id, name, slug)
                    VALUES (?, ?, ?, ?)
                """, (p_id, kid, name_clean, slug))
                actual_pid = cursor.lastrowid or p_id
            else:
                actual_pid = row[0]
                cursor.execute("""
                    UPDATE players SET name = ?, slug = COALESCE(?, slug), konami_id = COALESCE(?, konami_id)
                    WHERE id = ?
                """, (name_clean, slug, kid, actual_pid))

            # Insert or update academy profile
            cursor.execute("SELECT id FROM academy_profiles WHERE player_id = ? AND format_name = 'GLOBAL'", (actual_pid,))
            ap_row = cursor.fetchone()
            if not ap_row:
                cursor.execute("""
                    INSERT INTO academy_profiles (
                        player_id, store_id, format_name, current_rating, highest_rating,
                        dorm, xp, level, matches_played, wins, losses
                    ) VALUES (?, 1, 'GLOBAL', ?, ?, ?, ?, ?, ?, ?, ?)
                """, (actual_pid, rating, highest, dorm, xp, level, matches, wins, losses))
            else:
                cursor.execute("""
                    UPDATE academy_profiles SET
                        current_rating = ?, highest_rating = ?, dorm = ?,
                        xp = ?, level = ?, matches_played = ?, wins = ?, losses = ?
                    WHERE id = ?
                """, (rating, highest, dorm, xp, level, matches, wins, losses, ap_row[0]))

        if should_commit and conn:
            conn.commit()
    except Exception as e:
        print(f"[SeedPlayers] Notice: {e}")

class TournamentRoomManager:
    def __init__(self, conn=None):
        self._external_conn = conn

    def _get_cursor(self):
        if self._external_conn:
            return self._external_conn.cursor()
        conn = get_connection()
        return conn.cursor()

    def _generate_room_code(self, length=4):
        """Genera un código PIN corto y fácil de tipear (4 dígitos o letras)."""
        chars = string.digits
        return "".join(random.choices(chars, k=length))

    def create_or_get_room(self, title, format_name="EDISON", scheduled_id=None, room_code=None):
        """
        Crea una nueva sala interactiva para un torneo o recupera una existente.
        """
        cursor = self._get_cursor()
        migrate_rooms_schema(cursor)

        now_str = datetime.now().isoformat()

        # Si ya existe una sala activa para este scheduled_id
        if scheduled_id:
            cursor.execute("""
                SELECT * FROM tournament_rooms 
                WHERE scheduled_tournament_id = ? AND status IN ('LOBBY', 'RUNNING')
                ORDER BY id DESC LIMIT 1
            """, (scheduled_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)

        # Si se proporcionó un código específico, recuperar si ya existe
        code = room_code.upper().strip() if room_code else None
        if code:
            existing = self.get_room_by_code(code)
            if existing:
                if (format_name and existing.get('format_name') != format_name.strip()) or (title and existing.get('title') != title.strip()):
                    cursor.execute("""
                        UPDATE tournament_rooms 
                        SET format_name = ?, title = ?, updated_at = ? 
                        WHERE UPPER(room_code) = ?
                    """, (format_name.strip(), title.strip(), now_str, code))
                    if hasattr(cursor, 'connection') and cursor.connection:
                        cursor.connection.commit()
                    existing = self.get_room_by_code(code)
                return existing

        if not code:
            for _ in range(20):
                candidate = self._generate_room_code(4)
                cursor.execute("SELECT id FROM tournament_rooms WHERE room_code = ?", (candidate,))
                if not cursor.fetchone():
                    code = candidate
                    break
            if not code:
                code = str(random.randint(1000, 9999))

        cursor.execute("""
            INSERT INTO tournament_rooms (
                room_code, title, format_name, scheduled_tournament_id, status,
                current_round, live_data_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'LOBBY', 0, '{}', ?, ?)
        """, (code, title.strip(), format_name.strip(), scheduled_id, now_str, now_str))

        if hasattr(cursor, 'connection') and cursor.connection:
            cursor.connection.commit()

        return self.get_room_by_code(code)

    def get_room_by_code(self, room_code):
        if not room_code:
            return None
        cursor = self._get_cursor()
        migrate_rooms_schema(cursor)
        cursor.execute("SELECT * FROM tournament_rooms WHERE UPPER(room_code) = UPPER(?)", (room_code.strip(),))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_latest_active_room(self):
        """Retorna la sala más reciente que esté en LOBBY o RUNNING."""
        cursor = self._get_cursor()
        migrate_rooms_schema(cursor)
        cursor.execute("""
            SELECT * FROM tournament_rooms 
            WHERE status IN ('LOBBY', 'RUNNING')
            ORDER BY id DESC LIMIT 1
        """)
        row = cursor.fetchone()
        return dict(row) if row else None

    def update_room_status(self, room_code, status, current_round=None, live_data_json=None, format_name=None, title=None):
        cursor = self._get_cursor()
        migrate_rooms_schema(cursor)
        now_str = datetime.now().isoformat()

        fields = ["status = ?", "updated_at = ?"]
        params = [status, now_str]

        if current_round is not None:
            fields.append("current_round = ?")
            params.append(int(current_round))

        if format_name:
            fields.append("format_name = ?")
            params.append(format_name.strip())

        if title:
            fields.append("title = ?")
            params.append(title.strip())

        if live_data_json is not None:
            fields.append("live_data_json = ?")
            params.append(live_data_json if isinstance(live_data_json, str) else json.dumps(live_data_json))

        params.append(room_code.upper().strip())

        query = f"UPDATE tournament_rooms SET {', '.join(fields)} WHERE UPPER(room_code) = ?"
        cursor.execute(query, params)

        if hasattr(cursor, 'connection') and cursor.connection:
            cursor.connection.commit()

    def register_player(self, room_code, player_name, konami_id="", deck_archetype="", session_token=None):
        """
        Registra a un jugador en la sala mediante su teléfono celular.
        """
        room = self.get_room_by_code(room_code)
        if not room:
            return False, "La sala de torneo no existe o ya expiró."

        clean_name = player_name.strip()
        if not clean_name:
            return False, "Debes ingresar tu nombre o apodo."

        token = session_token.strip() if session_token else str(uuid.uuid4())
        cursor = self._get_cursor()
        migrate_rooms_schema(cursor)

        # 1. Verificar si este session_token ya está registrado en la sala
        cursor.execute("""
            SELECT * FROM room_checkins WHERE room_id = ? AND session_token = ?
        """, (room['id'], token))
        existing_token = cursor.fetchone()
        if existing_token:
            return True, {
                "message": "Ya estás inscrito en este torneo.",
                "session_token": token,
                "player_name": existing_token['player_name'],
                "dorm": existing_token['dorm'],
                "room_code": room['room_code']
            }

        # 2. Verificar si el nombre ya fue registrado en esta misma sala
        cursor.execute("""
            SELECT * FROM room_checkins WHERE room_id = ? AND LOWER(player_name) = LOWER(?)
        """, (room['id'], clean_name))
        existing_name = cursor.fetchone()
        if existing_name:
            # Reutilizar sesión para ese mismo jugador
            return True, {
                "message": "Registro recuperado.",
                "session_token": existing_name['session_token'],
                "player_name": existing_name['player_name'],
                "dorm": existing_name['dorm'],
                "room_code": room['room_code']
            }

        # 3. Intentar vincular con perfil oficial de la academia para heredar Casa (Dorm)
        player_id = None
        dorm = "Estudiante de Intercambio"
        kid = konami_id.strip() if konami_id else None

        try:
            cursor.execute("""
                SELECT p.id, p.konami_id, a.dorm 
                FROM players p
                LEFT JOIN academy_profiles a ON a.player_id = p.id AND a.format_name = 'GLOBAL'
                WHERE LOWER(p.name) = LOWER(?) OR (p.konami_id IS NOT NULL AND p.konami_id = ?)
                LIMIT 1
            """, (clean_name, kid or "---"))
            p_row = cursor.fetchone()
            if p_row:
                player_id = p_row['id']
                if p_row['dorm']:
                    dorm = p_row['dorm']
                if not kid and p_row['konami_id']:
                    kid = p_row['konami_id']
        except Exception:
            pass

        if not player_id:
            try:
                base_dir = os.path.dirname(os.path.abspath(__file__))
                manifest_path = os.path.join(base_dir, "mock_server", "public_api", "manifest.json")
                if os.path.exists(manifest_path):
                    with open(manifest_path, 'r', encoding='utf-8') as f:
                        m = json.load(f)
                    snap_name = m.get("latest_snapshot")
                    if snap_name:
                        with open(os.path.join(base_dir, "mock_server", "public_api", snap_name), 'r', encoding='utf-8') as f:
                            snap_data = json.load(f)
                        for p in snap_data.get("leaderboard", []):
                            if p.get("name", "").strip().lower() == clean_name.lower():
                                player_id = p.get("player_id")
                                if p.get("dorm"):
                                    dorm = p.get("dorm")
                                break
            except Exception:
                pass

        now_str = datetime.now().isoformat()
        try:
            cursor.execute("""
                INSERT INTO room_checkins (
                    room_id, session_token, player_id, player_name, konami_id,
                    dorm, deck_archetype, payment_status, status, checked_in_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING', 'CONFIRMED', ?)
            """, (room['id'], token, player_id, clean_name, kid, dorm, deck_archetype.strip(), now_str))
        except Exception as insert_err:
            # Si falla la restricción de integridad referencial o similar, intentar con player_id=None
            cursor.execute("""
                INSERT INTO room_checkins (
                    room_id, session_token, player_id, player_name, konami_id,
                    dorm, deck_archetype, payment_status, status, checked_in_at
                ) VALUES (?, ?, NULL, ?, ?, ?, ?, 'PENDING', 'CONFIRMED', ?)
            """, (room['id'], token, clean_name, kid, dorm, deck_archetype.strip(), now_str))

        if hasattr(cursor, 'connection') and cursor.connection:
            cursor.connection.commit()

        return True, {
            "message": "¡Inscripción exitosa!",
            "session_token": token,
            "player_name": clean_name,
            "dorm": dorm,
            "room_code": room['room_code']
        }

    def get_room_players(self, room_code):
        """Retorna la lista de jugadores inscritos en la sala."""
        room = self.get_room_by_code(room_code)
        if not room:
            return []
        cursor = self._get_cursor()
        migrate_rooms_schema(cursor)
        cursor.execute("""
            SELECT * FROM room_checkins 
            WHERE room_id = ? AND status = 'CONFIRMED'
            ORDER BY id ASC
        """, (room['id'],))
        return [dict(r) for r in cursor.fetchall()]

    def search_academy_players(self, query):
        """Búsqueda rápida de autocompletado para jugadores registrados en la Academia."""
        if not query or len(query.strip()) < 2:
            return []
        cursor = self._get_cursor()
        migrate_rooms_schema(cursor)
        q_clean = query.strip().lower()
        results = []

        try:
            q = f"%{q_clean}%"
            cursor.execute("""
                SELECT p.id, p.name, p.konami_id, 
                       COALESCE(a.dorm, 'Estudiante de Intercambio') as dorm,
                       COALESCE(a.current_rating, 1000) as rating,
                       COALESCE(a.level, 1) as level
                FROM players p
                LEFT JOIN academy_profiles a ON a.player_id = p.id AND a.format_name = 'GLOBAL'
                WHERE LOWER(p.name) LIKE ? OR (p.konami_id IS NOT NULL AND LOWER(p.konami_id) LIKE ?)
                ORDER BY a.current_rating DESC
                LIMIT 8
            """, (q, q))
            results = [dict(r) for r in cursor.fetchall()]
        except Exception:
            results = []

        # Fallback y complemento directo desde el último snapshot de la Academia
        if len(results) < 8:
            try:
                base_dir = os.path.dirname(os.path.abspath(__file__))
                manifest_path = os.path.join(base_dir, "mock_server", "public_api", "manifest.json")
                if os.path.exists(manifest_path):
                    with open(manifest_path, 'r', encoding='utf-8') as f:
                        m = json.load(f)
                    snap_name = m.get("latest_snapshot")
                    if snap_name:
                        with open(os.path.join(base_dir, "mock_server", "public_api", snap_name), 'r', encoding='utf-8') as f:
                            snap_data = json.load(f)
                        existing_names = {r["name"].strip().lower() for r in results}
                        for p in snap_data.get("leaderboard", []):
                            p_name = p.get("name", "").strip()
                            p_kid = str(p.get("konami_id") or "").strip()
                            if q_clean in p_name.lower() or (p_kid and q_clean in p_kid.lower()):
                                if p_name.lower() not in existing_names:
                                    results.append({
                                        "id": p.get("player_id"),
                                        "name": p_name,
                                        "konami_id": p.get("konami_id"),
                                        "dorm": p.get("dorm") or "Estudiante de Intercambio",
                                        "rating": p.get("current_rating", 1000),
                                        "level": p.get("level", 1)
                                    })
                                    existing_names.add(p_name.lower())
                                    if len(results) >= 8:
                                        break
            except Exception:
                pass

        return results

    def sync_tournament_to_room(self, room_code, manager, time_left=None, timer_running=False):
        """
        Sincroniza el estado en vivo de un TournamentManager con la Sala Web.
        Empaqueta pareos de la ronda actual, número de mesas, slugs de perfil de academia,
        tiempo restante del reloj y standings.
        """
        room = self.get_room_by_code(room_code)
        if not room:
            return False

        cursor = self._get_cursor()

        # Cache de slugs, dorms y ratings de la Academia
        slug_map = {}
        dorm_map = {}
        rating_map = {}
        try:
            cursor.execute("""
                SELECT p.name, p.slug, a.dorm, a.current_rating
                FROM players p
                LEFT JOIN academy_profiles a ON a.player_id = p.id AND a.format_name = 'GLOBAL'
            """)
            for row in cursor.fetchall():
                p_name_lower = row['name'].strip().lower()
                slug_map[p_name_lower] = row['slug'] or p_name_lower.replace(' ', '')
                dorm_map[p_name_lower] = row['dorm'] or 'Estudiante de Intercambio'
                rating_map[p_name_lower] = row['current_rating'] or 1000
        except Exception:
            pass

        # Standings
        standings = []
        try:
            sorted_players = sorted(
                manager.players,
                key=lambda p: (p.points, getattr(p, '_omw', 0.33), getattr(p, '_oomw', 0.33)),
                reverse=True
            )
            for idx, p in enumerate(sorted_players, 1):
                p_lower = p.name.strip().lower()
                standings.append({
                    "rank": idx,
                    "name": p.name,
                    "slug": slug_map.get(p_lower),
                    "dorm": dorm_map.get(p_lower, "Estudiante de Intercambio"),
                    "points": p.points,
                    "matches_played": p.matches_played,
                    "omw": f"{getattr(p, '_omw', 0.3333) * 100:.1f}%",
                    "had_bye": getattr(p, 'had_bye', False)
                })
        except Exception as e:
            print("[RoomManager] Error calculando standings:", e)

        # Reportes pendientes o confirmados de esta ronda
        reports_map = {}
        try:
            cursor.execute("""
                SELECT * FROM room_match_reports 
                WHERE room_id = ? AND round_num = ?
            """, (room['id'], manager.current_round))
            for r in cursor.fetchall():
                reports_map[r['table_num']] = dict(r)
        except Exception:
            pass

        # Pareos de la ronda actual
        current_round_matches = []
        if manager.rounds and 0 < manager.current_round <= len(manager.rounds):
            round_matches = manager.rounds[manager.current_round - 1]
            for table_num, m in enumerate(round_matches, 1):
                p1_name = m.p1.name if m.p1 else "BYE"
                p2_name = m.p2.name if m.p2 else "BYE"
                p1_lower = p1_name.strip().lower()
                p2_lower = p2_name.strip().lower()

                # Si hay un reporte formal y confirmado en la base de datos de salas
                rep = reports_map.get(table_num)
                match_reported = m.reported or (rep and rep['status'] == 'CONFIRMED')
                res_txt = m.result_text
                if rep and rep['status'] == 'CONFIRMED':
                    res_txt = f"{rep['score_p1']} - {rep['score_p2']}"

                current_round_matches.append({
                    "table": table_num,
                    "p1": p1_name,
                    "p2": p2_name,
                    "p1_slug": slug_map.get(p1_lower),
                    "p2_slug": slug_map.get(p2_lower),
                    "p1_dorm": dorm_map.get(p1_lower, "Estudiante de Intercambio"),
                    "p2_dorm": dorm_map.get(p2_lower, "Estudiante de Intercambio"),
                    "p1_rating": rating_map.get(p1_lower, 1000),
                    "p2_rating": rating_map.get(p2_lower, 1000),
                    "reported": match_reported,
                    "result_text": res_txt,
                    "is_bye": (m.p1 is None or m.p2 is None),
                    "report": rep
                })

        live_data = {
            "title": room['title'],
            "format": room['format_name'],
            "status": manager.status,
            "current_round": manager.current_round,
            "total_rounds": manager.total_rounds,
            "players_count": len(manager.players),
            "matches": current_round_matches,
            "standings": standings,
            "time_left": time_left,
            "timer_running": bool(timer_running),
            "synced_at": datetime.now().strftime("%H:%M:%S")
        }

        new_status = "RUNNING" if manager.status == "running" else ("FINISHED" if manager.status == "finished" else "LOBBY")
        self.update_room_status(
            room_code,
            status=new_status,
            current_round=manager.current_round,
            live_data_json=live_data
        )
        return True

    def get_player_match_info(self, room_code, player_name):
        room = self.get_room_by_code(room_code)
        if not room or not room.get('live_data_json'):
            return None

        try:
            live = json.loads(room['live_data_json'])
        except Exception:
            return None

        matches = live.get("matches", [])
        clean_name = player_name.strip().lower()

        for m in matches:
            p1_clean = m['p1'].lower()
            p2_clean = m['p2'].lower()
            if clean_name == p1_clean:
                return {
                    "table": m['table'],
                    "role": "p1",
                    "player": m['p1'],
                    "player_dorm": m.get('p1_dorm'),
                    "opponent": m['p2'],
                    "opponent_dorm": m.get('p2_dorm'),
                    "opponent_slug": m.get('p2_slug'),
                    "opponent_rating": m.get('p2_rating'),
                    "is_bye": m['is_bye'],
                    "reported": m['reported'],
                    "result_text": m['result_text'],
                    "report": m.get('report'),
                    "current_round": live.get("current_round", 1)
                }
            elif clean_name == p2_clean:
                return {
                    "table": m['table'],
                    "role": "p2",
                    "player": m['p2'],
                    "player_dorm": m.get('p2_dorm'),
                    "opponent": m['p1'],
                    "opponent_dorm": m.get('p1_dorm'),
                    "opponent_slug": m.get('p1_slug'),
                    "opponent_rating": m.get('p1_rating'),
                    "is_bye": m['is_bye'],
                    "reported": m['reported'],
                    "result_text": m['result_text'],
                    "report": m.get('report'),
                    "current_round": live.get("current_round", 1)
                }

        return None

    # =========================================================================
    # TABLÓN DE CARTAS (BUSCO / VENDO / CAMBIO CON YGOPRODECK)
    # =========================================================================
    def search_cards_ygo(self, query):
        """Busca cartas oficiales en la API de YGOPRODeck."""
        import requests
        if not query or len(query.strip()) < 2:
            return []
        q = query.strip()
        url = f"https://db.ygoprodeck.com/api/v7/cardinfo.php?fname={requests.utils.quote(q)}&num=10&offset=0"
        try:
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                data = res.json().get('data', [])
                results = []
                for c in data:
                    c_id = c.get('id')
                    c_name = c.get('name')
                    imgs = c.get('card_images', [{}])
                    img_url = imgs[0].get('image_url_small') or imgs[0].get('image_url') or ""
                    
                    sets = c.get('card_sets', [])
                    rarities = sorted(list({s.get('set_rarity') for s in sets if s.get('set_rarity')}))
                    
                    results.append({
                        "id": c_id,
                        "name": c_name,
                        "image_url": img_url,
                        "type": c.get('type', ''),
                        "rarities": rarities
                    })
                return results
            return []
        except Exception as e:
            print("[RoomManager] Error buscando cartas en YGOPRODeck:", e)
            return []

    def create_trade_post(self, room_code, player_name, post_type, card_name, card_id=None,
                          card_image_url=None, rarity="", language="", edition="", notes="", session_token=None):
        room = self.get_room_by_code(room_code)
        if not room:
            return False, "La sala no existe."

        clean_card = card_name.strip()
        if not clean_card:
            return False, "Debes indicar el nombre de la carta."

        cursor = self._get_cursor()
        migrate_rooms_schema(cursor)
        now_str = datetime.now().isoformat()

        cursor.execute("""
            INSERT INTO room_trade_posts (
                room_id, player_name, session_token, post_type, card_name, card_id,
                card_image_url, rarity, language, edition, notes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            room['id'], player_name.strip(), session_token, post_type.upper().strip(),
            clean_card, card_id, card_image_url, rarity.strip(), language.strip(),
            edition.strip(), notes.strip(), now_str
        ))
        if hasattr(cursor, 'connection') and cursor.connection:
            cursor.connection.commit()
        return True, "Publicación creada con éxito."

    def get_trade_posts(self, room_code):
        room = self.get_room_by_code(room_code)
        if not room:
            return []
        cursor = self._get_cursor()
        migrate_rooms_schema(cursor)
        cursor.execute("""
            SELECT * FROM room_trade_posts
            WHERE room_id = ?
            ORDER BY id DESC LIMIT 50
        """, (room['id'],))
        return [dict(r) for r in cursor.fetchall()]

    def delete_trade_post(self, post_id, session_token=None, is_admin=False):
        cursor = self._get_cursor()
        migrate_rooms_schema(cursor)
        if is_admin:
            cursor.execute("DELETE FROM room_trade_posts WHERE id = ?", (post_id,))
        else:
            cursor.execute("DELETE FROM room_trade_posts WHERE id = ? AND session_token = ?", (post_id, session_token))
        if hasattr(cursor, 'connection') and cursor.connection:
            cursor.connection.commit()
        return True

    # =========================================================================
    # FASE 2: AUTO-REPORTE DE RESULTADOS Y CONFIRMACIÓN MUTUA
    # =========================================================================
    def submit_match_report(self, room_code, round_num, table_num, reporter_name, score_p1, score_p2):
        room = self.get_room_by_code(room_code)
        if not room:
            return False, "Sala no existe."

        s1 = int(score_p1)
        s2 = int(score_p2)
        if s1 > s2:
            result_type = "P1_WIN"
        elif s2 > s1:
            result_type = "P2_WIN"
        elif s1 == s2 and s1 > 0:
            result_type = "DRAW"
        else:
            result_type = "DOUBLE_LOSS"

        live = json.loads(room.get('live_data_json') or '{}')
        matches = live.get('matches', [])
        current_match = next((m for m in matches if m.get('table') == int(table_num)), None)
        if not current_match:
            return False, "Mesa no encontrada en esta ronda."

        p1_name = current_match['p1']
        p2_name = current_match['p2']
        now_str = datetime.now().isoformat()

        cursor = self._get_cursor()
        migrate_rooms_schema(cursor)

        cursor.execute("""
            INSERT INTO room_match_reports (
                room_id, round_num, table_num, reported_by, p1_name, p2_name,
                score_p1, score_p2, result_type, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING_CONFIRMATION', ?, ?)
            ON CONFLICT(room_id, round_num, table_num) DO UPDATE SET
                reported_by = excluded.reported_by,
                score_p1 = excluded.score_p1,
                score_p2 = excluded.score_p2,
                result_type = excluded.result_type,
                status = 'PENDING_CONFIRMATION',
                updated_at = excluded.updated_at
        """, (
            room['id'], int(round_num), int(table_num), reporter_name.strip(),
            p1_name, p2_name, s1, s2, result_type, now_str, now_str
        ))
        if hasattr(cursor, 'connection') and cursor.connection:
            cursor.connection.commit()

        # Actualizar live_data_json de inmediato para feedback instantáneo
        rep_dict = {
            "round_num": int(round_num),
            "table_num": int(table_num),
            "reported_by": reporter_name.strip(),
            "p1_name": p1_name,
            "p2_name": p2_name,
            "score_p1": s1,
            "score_p2": s2,
            "result_type": result_type,
            "status": "PENDING_CONFIRMATION",
            "updated_at": now_str
        }
        for m in matches:
            if m.get('table') == int(table_num):
                m['report'] = rep_dict
                break
        self.update_room_status(room_code, status=room['status'], current_round=room['current_round'], live_data_json=live)

        return True, {
            "table_num": table_num,
            "result_type": result_type,
            "status": "PENDING_CONFIRMATION",
            "score": f"{s1} - {s2}",
            "report": rep_dict
        }

    def confirm_match_report(self, room_code, round_num, table_num, confirmer_name):
        room = self.get_room_by_code(room_code)
        if not room:
            return False, "Sala no existe."

        cursor = self._get_cursor()
        migrate_rooms_schema(cursor)
        now_str = datetime.now().isoformat()

        cursor.execute("""
            SELECT * FROM room_match_reports
            WHERE room_id = ? AND round_num = ? AND table_num = ?
        """, (room['id'], int(round_num), int(table_num)))
        report = cursor.fetchone()
        if not report:
            return False, "No hay reporte pendiente para esta mesa."

        cursor.execute("""
            UPDATE room_match_reports
            SET status = 'CONFIRMED', updated_at = ?
            WHERE id = ?
        """, (now_str, report['id']))
        if hasattr(cursor, 'connection') and cursor.connection:
            cursor.connection.commit()

        try:
            live = json.loads(room.get('live_data_json') or '{}')
            matches = live.get('matches', [])
            for m in matches:
                if m.get('table') == int(table_num):
                    m['reported'] = True
                    m['result_text'] = f"{report['score_p1']} - {report['score_p2']}"
                    if 'report' in m and m['report']:
                        m['report']['status'] = 'CONFIRMED'
                        m['report']['score_p1'] = report['score_p1']
                        m['report']['score_p2'] = report['score_p2']
                    else:
                        m['report'] = {
                            'status': 'CONFIRMED',
                            'score_p1': report['score_p1'],
                            'score_p2': report['score_p2']
                        }
                    break
            self.update_room_status(room_code, status=room['status'], current_round=room['current_round'], live_data_json=live)
        except Exception as e:
            print("[RoomManager] Error updating live matches after confirm:", e)

        return True, "Resultado confirmado oficialmente."

    def dispute_match_report(self, room_code, round_num, table_num, disputer_name):
        room = self.get_room_by_code(room_code)
        if not room:
            return False, "Sala no existe."

        cursor = self._get_cursor()
        migrate_rooms_schema(cursor)
        now_str = datetime.now().isoformat()

        cursor.execute("""
            UPDATE room_match_reports
            SET status = 'DISPUTED', updated_at = ?
            WHERE room_id = ? AND round_num = ? AND table_num = ?
        """, (now_str, room['id'], int(round_num), int(table_num)))
        if hasattr(cursor, 'connection') and cursor.connection:
            cursor.connection.commit()

        try:
            live = json.loads(room.get('live_data_json') or '{}')
            matches = live.get('matches', [])
            for m in matches:
                if m.get('table') == int(table_num):
                    if 'report' in m and m['report']:
                        m['report']['status'] = 'DISPUTED'
                    else:
                        m['report'] = {'status': 'DISPUTED'}
                    break
            self.update_room_status(room_code, status=room['status'], current_round=room['current_round'], live_data_json=live)
        except Exception as e:
            print("[RoomManager] Error updating live matches after dispute:", e)

        return True, "Disputa registrada. Un juez o el organizador revisará tu mesa."

    # =========================================================================
    # GESTIÓN DE DROPS (RETIRO VOLUNTARIO DE DUELISTAS)
    # =========================================================================
    def drop_player_from_room(self, room_code, player_name, session_token=None, round_num=1):
        """
        Registra el retiro voluntario (Drop) de un duelista del torneo.
        Actualiza el estado en room_checkins y room_player_drops.
        """
        room = self.get_room_by_code(room_code)
        if not room:
            return False, "La sala no existe."

        clean_name = player_name.strip()
        cursor = self._get_cursor()
        migrate_rooms_schema(cursor)
        now_str = datetime.now().isoformat()

        # 1. Actualizar checkin
        cursor.execute("""
            UPDATE room_checkins 
            SET status = 'DROPPED'
            WHERE room_id = ? AND LOWER(player_name) = LOWER(?)
        """, (room['id'], clean_name))

        # 2. Registrar en room_player_drops
        cursor.execute("""
            INSERT INTO room_player_drops (room_id, player_name, session_token, round_num, dropped_at, status)
            VALUES (?, ?, ?, ?, ?, 'CONFIRMED')
            ON CONFLICT(room_id, player_name) DO UPDATE SET
                round_num = excluded.round_num,
                dropped_at = excluded.dropped_at,
                status = 'CONFIRMED'
        """, (room['id'], clean_name, session_token, int(round_num), now_str))

        if hasattr(cursor, 'connection') and cursor.connection:
            cursor.connection.commit()

        # 3. Actualizar live_data_json con la lista de jugadores retirados
        try:
            live = json.loads(room.get('live_data_json') or '{}')
            dropped_list = live.get('dropped_players', [])
            if clean_name not in dropped_list:
                dropped_list.append(clean_name)
            live['dropped_players'] = dropped_list

            # Marcar en standings si está presente
            for s in live.get('standings', []):
                if s.get('name', '').lower() == clean_name.lower():
                    s['dropped'] = True
                    s['active'] = False

            self.update_room_status(room_code, status=room['status'], current_round=room['current_round'], live_data_json=live)
        except Exception as e:
            print("[RoomManager] Error actualizando live_data tras drop:", e)

        return True, "Te has retirado del torneo exitosamente. No serás emparejado en las rondas siguientes."

    def get_room_dropped_players(self, room_code):
        """Retorna la lista de jugadores que han dropeado en la sala."""
        room = self.get_room_by_code(room_code)
        if not room:
            return []
        cursor = self._get_cursor()
        migrate_rooms_schema(cursor)
        cursor.execute("""
            SELECT player_name, round_num, dropped_at FROM room_player_drops
            WHERE room_id = ? AND status = 'CONFIRMED'
        """, (room['id'],))
        return [dict(r) for r in cursor.fetchall()]

    def get_room_match_reports(self, room_code, round_num=None):
        """Retorna los reportes de partidas registrados en la sala."""
        room = self.get_room_by_code(room_code)
        if not room:
            return []
        cursor = self._get_cursor()
        migrate_rooms_schema(cursor)
        if round_num is not None:
            cursor.execute("""
                SELECT * FROM room_match_reports
                WHERE room_id = ? AND round_num = ?
                ORDER BY table_num ASC
            """, (room['id'], int(round_num)))
        else:
            cursor.execute("""
                SELECT * FROM room_match_reports
                WHERE room_id = ?
                ORDER BY round_num ASC, table_num ASC
            """, (room['id'],))
        return [dict(r) for r in cursor.fetchall()]

