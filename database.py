import sqlite3
import os

from utils import get_appdata_dir

DB_PATH = os.environ.get("DATABASE_PATH") or os.path.join(get_appdata_dir(), "data", "ygo_data.db")

def get_connection():
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10.0)
    conn.row_factory = sqlite3.Row
    # Enable foreign keys and WAL mode for high concurrency
    conn.execute("PRAGMA foreign_keys = 1")
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 5000")
    except Exception:
        pass
    return conn

def factory_reset():
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
        except:
            pass
    init_db()

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Stores table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            is_active BOOLEAN DEFAULT 0
        )
    ''')
    
    # Users table for Web Authentication
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'admin'
        )
    ''')
    
    # Global Players Table (Uses Konami ID as optional unique key)
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
    
    # League Profiles (Specific configuration of a player per store and format)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS league_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            store_id INTEGER NOT NULL,
            format_name TEXT NOT NULL,
            deck_name TEXT,
            signature_card TEXT,
            FOREIGN KEY(player_id) REFERENCES players(id) ON DELETE CASCADE,
            FOREIGN KEY(store_id) REFERENCES stores(id) ON DELETE CASCADE,
            UNIQUE(player_id, store_id, format_name)
        )
    ''')
    
    # Tournaments (A specific tournament instance)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tournaments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store_id INTEGER NOT NULL,
            format_name TEXT NOT NULL,
            date TEXT NOT NULL,
            mode TEXT,
            profit REAL DEFAULT 0.0,
            FOREIGN KEY(store_id) REFERENCES stores(id) ON DELETE CASCADE
        )
    ''')
    
    # Tournament Results (Link between player profile and tournament, storing their result and missions)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tournament_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tournament_id INTEGER NOT NULL,
            league_profile_id INTEGER NOT NULL,
            match_points INTEGER DEFAULT 0,
            placement_points INTEGER DEFAULT 0,
            attendance BOOLEAN DEFAULT 1,
            bingo_grid TEXT,
            FOREIGN KEY(tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
            FOREIGN KEY(league_profile_id) REFERENCES league_profiles(id) ON DELETE CASCADE,
            UNIQUE(tournament_id, league_profile_id)
        )
    ''')

    # Tournament Matches (The actual pairings and results of a tournament)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tournament_matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tournament_id INTEGER NOT NULL,
            p1_id INTEGER,
            p2_id INTEGER,
            round_num INTEGER NOT NULL,
            result_text TEXT NOT NULL,
            note TEXT,
            FOREIGN KEY(tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
            FOREIGN KEY(p1_id) REFERENCES players(id) ON DELETE SET NULL,
            FOREIGN KEY(p2_id) REFERENCES players(id) ON DELETE SET NULL
        )
    ''')

    # Academy Profiles (A player's competitive profile for a format/store)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS academy_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            store_id INTEGER NOT NULL,
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
            FOREIGN KEY(player_id) REFERENCES players(id) ON DELETE CASCADE,
            FOREIGN KEY(store_id) REFERENCES stores(id) ON DELETE CASCADE,
            UNIQUE(player_id, store_id, format_name)
        )
    ''')

    # Academy Rating History
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS academy_rating_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            academy_profile_id INTEGER NOT NULL,
            match_id INTEGER,
            previous_rating INTEGER NOT NULL,
            new_rating INTEGER NOT NULL,
            rating_change INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            reason TEXT,
            FOREIGN KEY(academy_profile_id) REFERENCES academy_profiles(id) ON DELETE CASCADE,
            FOREIGN KEY(match_id) REFERENCES tournament_matches(id) ON DELETE SET NULL
        )
    ''')

    # Academy Achievements (Future-proof structure for achievements)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS academy_achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            academy_profile_id INTEGER NOT NULL,
            achievement_id TEXT NOT NULL,
            unlocked_at TEXT NOT NULL,
            FOREIGN KEY(academy_profile_id) REFERENCES academy_profiles(id) ON DELETE CASCADE,
            UNIQUE(academy_profile_id, achievement_id)
        )
    ''')

    # Academy V1.0 New Tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS academy_missions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            academy_profile_id INTEGER NOT NULL,
            mission_id TEXT NOT NULL,
            progress INTEGER DEFAULT 0,
            completed BOOLEAN DEFAULT 0,
            completed_at TEXT,
            expires_at TEXT,
            FOREIGN KEY(academy_profile_id) REFERENCES academy_profiles(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mission_catalog (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            target_value INTEGER,
            xp_reward INTEGER,
            type TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS academy_seasons (
            id TEXT PRIMARY KEY,
            number INTEGER,
            start_date TEXT NOT NULL,
            end_date TEXT,
            status TEXT DEFAULT 'ACTIVE'
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS academy_season_players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            season_id TEXT NOT NULL,
            academy_profile_id INTEGER NOT NULL,
            final_rating INTEGER,
            final_dorm TEXT,
            matches_played INTEGER,
            wins INTEGER,
            FOREIGN KEY(season_id) REFERENCES academy_seasons(id) ON DELETE CASCADE,
            FOREIGN KEY(academy_profile_id) REFERENCES academy_profiles(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reward_catalog (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            type TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_rewards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            academy_profile_id INTEGER NOT NULL,
            reward_id TEXT NOT NULL,
            status TEXT DEFAULT 'LOCKED',
            unlocked_at TEXT,
            claimed_at TEXT,
            FOREIGN KEY(academy_profile_id) REFERENCES academy_profiles(id) ON DELETE CASCADE,
            FOREIGN KEY(reward_id) REFERENCES reward_catalog(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS academy_publications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version INTEGER NOT NULL UNIQUE,
            timestamp TEXT NOT NULL,
            tournament_id INTEGER,
            checksum TEXT,
            status TEXT DEFAULT 'PENDING',
            FOREIGN KEY(tournament_id) REFERENCES tournaments(id) ON DELETE SET NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS academy_public_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            publication_id INTEGER NOT NULL,
            path TEXT NOT NULL,
            FOREIGN KEY(publication_id) REFERENCES academy_publications(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS academy_preseason_players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tournament_id INTEGER NOT NULL,
            player_id INTEGER NOT NULL,
            processed BOOLEAN DEFAULT 1,
            FOREIGN KEY(tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
            FOREIGN KEY(player_id) REFERENCES players(id) ON DELETE CASCADE,
            UNIQUE(tournament_id, player_id)
        )
    ''')
    
    migrate_academy_schema(cursor)
    migrate_calendar_and_leagues_schema(cursor)
    from tournament_room_manager import migrate_rooms_schema
    migrate_rooms_schema(cursor)
    
    conn.commit()
    conn.close()

def _add_column_if_missing(cursor, table, column, ddl):
    cursor.execute(f"PRAGMA table_info({table})")
    if column not in [r[1] for r in cursor.fetchall()]:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

def migrate_academy_schema(cursor):
    """
    Migración idempotente (segura para BDs existentes) del módulo Academy:
    - Rating Glicko-2 en paralelo al ELO (mu / phi=RD / sigma).
    - Trazabilidad de cada duelo (rival, esperado, K, resultado) para explicar el ranking.
    - Log de XP por origen (duelos, misiones, logros, torneos).
    """
    for col, ddl in [
        ("previous_rank", "INTEGER"),
        ("glicko_mu", "REAL DEFAULT 1500"),
        ("glicko_phi", "REAL DEFAULT 350"),
        ("glicko_sigma", "REAL DEFAULT 0.06"),
    ]:
        _add_column_if_missing(cursor, "academy_profiles", col, ddl)

    for col, ddl in [
        ("name", "TEXT"),
        ("close_type", "TEXT"),  # 'DATE' o 'TOURNAMENT_COUNT'
        ("target_value", "TEXT"),  # fecha objetivo o número objetivo de torneos
        ("tournaments_count", "INTEGER DEFAULT 0"),
        ("players_count", "INTEGER DEFAULT 0"),
    ]:
        _add_column_if_missing(cursor, "academy_seasons", col, ddl)

    for col, ddl in [
        ("opponent_id", "INTEGER"),
        ("opponent_rating", "INTEGER"),
        ("expected_score", "REAL"),
        ("k_factor", "INTEGER"),
        ("result", "REAL"),
        ("glicko_mu", "REAL"),
        ("glicko_phi", "REAL"),
    ]:
        _add_column_if_missing(cursor, "academy_rating_history", col, ddl)

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS academy_xp_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            academy_profile_id INTEGER NOT NULL,
            source TEXT NOT NULL,
            ref_id TEXT,
            xp INTEGER NOT NULL,
            description TEXT,
            timestamp TEXT NOT NULL,
            FOREIGN KEY(academy_profile_id) REFERENCES academy_profiles(id) ON DELETE CASCADE
        )
    ''')

    # Reconstruye rival / K / Glicko-2 / origen del XP de datos anteriores a esta migración
    from academy.backfill import backfill_traceability
    backfill_traceability(cursor)

def migrate_calendar_and_leagues_schema(cursor):
    """
    Migración para el sistema de Calendario de Torneos y Fundación de Ligas Competitivas.
    """
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scheduled_tournaments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            format_name TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT DEFAULT '16:00',
            mode TEXT DEFAULT 'swiss',
            store_id INTEGER,
            entry_fee REAL DEFAULT 0.0,
            prize_description TEXT,
            notes TEXT,
            status TEXT DEFAULT 'PROGRAMADO',
            tournament_id INTEGER,
            league_id INTEGER,
            created_at TEXT,
            FOREIGN KEY(store_id) REFERENCES stores(id) ON DELETE SET NULL,
            FOREIGN KEY(tournament_id) REFERENCES tournaments(id) ON DELETE SET NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leagues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            format_name TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT,
            frequency TEXT DEFAULT 'DOMINGOS',
            total_stops INTEGER DEFAULT 8,
            store_id INTEGER,
            prize_title TEXT,
            prize_description TEXT,
            points_system TEXT DEFAULT 'STANDARD',
            status TEXT DEFAULT 'PREPARADA',
            season_id TEXT,
            created_at TEXT,
            FOREIGN KEY(store_id) REFERENCES stores(id) ON DELETE SET NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS league_stops (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            league_id INTEGER NOT NULL,
            stop_number INTEGER NOT NULL,
            scheduled_tournament_id INTEGER,
            tournament_id INTEGER,
            date TEXT NOT NULL,
            status TEXT DEFAULT 'PROGRAMADO',
            FOREIGN KEY(league_id) REFERENCES leagues(id) ON DELETE CASCADE,
            FOREIGN KEY(scheduled_tournament_id) REFERENCES scheduled_tournaments(id) ON DELETE SET NULL,
            FOREIGN KEY(tournament_id) REFERENCES tournaments(id) ON DELETE SET NULL
        )
    ''')

    try:
        cursor.execute("ALTER TABLE players ADD COLUMN nickname TEXT")
    except Exception:
        pass

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            alias TEXT NOT NULL UNIQUE,
            created_at TEXT,
            FOREIGN KEY(player_id) REFERENCES players(id) ON DELETE CASCADE
        )
    ''')

def resolve_player(cursor, name_or_alias: str = None, konami_id: str = None):
    """
    Resuelve de forma unificada y canónica un jugador a partir de su Konami ID,
    nombre real, apodo/nickname, slug o alias registrado.
    Evita la duplicación garantizando que 'Tio Zombie' -> 'Maximiliano Candia',
    'Kame' -> 'Esteban Ocompley', etc.
    """
    from utils import normalize_player_name

    # 1. Búsqueda directa por Konami ID
    if konami_id:
        kid = str(konami_id).strip()
        if kid:
            cursor.execute("SELECT * FROM players WHERE konami_id = ?", (kid,))
            row = cursor.fetchone()
            if row:
                return dict(row)

    if not name_or_alias:
        return None

    raw = str(name_or_alias).strip()
    if not raw:
        return None
    norm = normalize_player_name(raw)

    # 2. Búsqueda en tabla de alias unificados
    try:
        cursor.execute("""
            SELECT p.* FROM players p
            JOIN player_aliases pa ON pa.player_id = p.id
            WHERE LOWER(pa.alias) = LOWER(?) OR LOWER(REPLACE(pa.alias, ' ', '')) = ?
            LIMIT 1
        """, (raw, norm.replace(' ', '')))
        row = cursor.fetchone()
        if row:
            return dict(row)
    except Exception:
        pass

    # 3. Búsqueda por Apodo / Nickname directo
    try:
        cursor.execute("SELECT * FROM players WHERE LOWER(nickname) = LOWER(?)", (raw,))
        row = cursor.fetchone()
        if row:
            return dict(row)
    except Exception:
        pass

    # 4. Búsqueda por Slug
    try:
        cursor.execute("SELECT * FROM players WHERE LOWER(slug) = LOWER(?) OR LOWER(slug) = LOWER(?)", (raw, norm))
        row = cursor.fetchone()
        if row:
            return dict(row)
    except Exception:
        pass

    # 5. Búsqueda por coincidencia de nombre normalizado (independiente de tildes/espacios)
    try:
        cursor.execute("SELECT * FROM players")
        for p in cursor.fetchall():
            if normalize_player_name(p['name']) == norm:
                return dict(p)
            if p['nickname'] and normalize_player_name(p['nickname']) == norm:
                return dict(p)
    except Exception:
        pass

    return None

def link_player_alias(cursor, player_id: int, alias: str, is_nickname: bool = False):
    """Registra un alias o apodo para un jugador."""
    if not alias or len(alias.strip()) < 2:
        return
    clean_alias = alias.strip()
    try:
        cursor.execute("""
            INSERT INTO player_aliases (player_id, alias, created_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(alias) DO UPDATE SET player_id = excluded.player_id
        """, (player_id, clean_alias))
    except Exception:
        pass
    if is_nickname:
        try:
            cursor.execute("UPDATE players SET nickname = ? WHERE id = ? AND (nickname IS NULL OR nickname = '')", (clean_alias, player_id))
        except Exception:
            pass

def merge_players_db(primary_id: int, secondary_ids: list, nickname: str = None):
    """
    Fusiona limpiamente jugadores duplicados en un único jugador canónico.
    Migra partidas, check-ins, perfiles de liga y academia, transfiere konami_id / teléfono / email,
    establece el nickname si corresponde y registra todos los nombres previos como alias.
    """
    if not secondary_ids or primary_id in secondary_ids:
        return
        
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT * FROM players WHERE id = ?", (primary_id,))
        prim_row = cursor.fetchone()
        if not prim_row:
            return
        prim = dict(prim_row)
        
        best_kid = prim.get('konami_id')
        best_phone = prim.get('phone')
        best_email = prim.get('email')
        best_nick = prim.get('nickname') or nickname

        aliases_to_add = set()
        if prim.get('name'): aliases_to_add.add(prim['name'].strip())
        if prim.get('slug'): aliases_to_add.add(prim['slug'].strip())
        if best_nick: aliases_to_add.add(best_nick.strip())

        for sid in secondary_ids:
            cursor.execute("SELECT * FROM players WHERE id = ?", (sid,))
            s_row = cursor.fetchone()
            if not s_row: continue
            sec = dict(s_row)
            if not best_kid and sec.get('konami_id'): best_kid = sec['konami_id']
            if not best_phone and sec.get('phone'): best_phone = sec['phone']
            if not best_email and sec.get('email'): best_email = sec['email']
            if not best_nick and sec.get('nickname'): best_nick = sec['nickname']
            if sec.get('name'): aliases_to_add.add(sec['name'].strip())
            if sec.get('slug'): aliases_to_add.add(sec['slug'].strip())

            # 1. Update tournament_matches
            cursor.execute("UPDATE tournament_matches SET p1_id = ? WHERE p1_id = ?", (primary_id, sid))
            cursor.execute("UPDATE tournament_matches SET p2_id = ? WHERE p2_id = ?", (primary_id, sid))
            
            # 2. Update room_checkins
            try:
                cursor.execute("UPDATE room_checkins SET player_id = ? WHERE player_id = ?", (primary_id, sid))
            except Exception:
                pass

            # 3. Merge league_profiles
            cursor.execute("SELECT id, store_id, format_name FROM league_profiles WHERE player_id = ?", (primary_id,))
            primary_profiles = cursor.fetchall()
            primary_lookup = {(r['store_id'], r['format_name']): r['id'] for r in primary_profiles}
            
            cursor.execute("SELECT id, store_id, format_name FROM league_profiles WHERE player_id = ?", (sid,))
            secondary_profiles = cursor.fetchall()
            
            for sec_prof in secondary_profiles:
                store_id = sec_prof['store_id']
                format_name = sec_prof['format_name']
                sec_prof_id = sec_prof['id']
                
                if (store_id, format_name) in primary_lookup:
                    prim_prof_id = primary_lookup[(store_id, format_name)]
                    cursor.execute("SELECT tournament_id FROM tournament_results WHERE league_profile_id = ?", (prim_prof_id,))
                    existing_tids = [r['tournament_id'] for r in cursor.fetchall()]
                    
                    cursor.execute("SELECT id, tournament_id, match_points, placement_points FROM tournament_results WHERE league_profile_id = ?", (sec_prof_id,))
                    sec_results = cursor.fetchall()
                    
                    for s_res in sec_results:
                        t_id = s_res['tournament_id']
                        if t_id in existing_tids:
                            cursor.execute("DELETE FROM tournament_results WHERE id = ?", (s_res['id'],))
                        else:
                            cursor.execute("UPDATE tournament_results SET league_profile_id = ? WHERE id = ?", (prim_prof_id, s_res['id']))
                    
                    cursor.execute("DELETE FROM league_profiles WHERE id = ?", (sec_prof_id,))
                else:
                    cursor.execute("UPDATE league_profiles SET player_id = ? WHERE id = ?", (primary_id, sec_prof_id))
                    primary_lookup[(store_id, format_name)] = sec_prof_id
                        
            # 4. Merge academy_profiles
            cursor.execute("SELECT id, store_id, format_name FROM academy_profiles WHERE player_id = ?", (primary_id,))
            prim_acad_profiles = cursor.fetchall()
            acad_lookup = {(r['store_id'], r['format_name']): r['id'] for r in prim_acad_profiles}
            
            cursor.execute("SELECT id, store_id, format_name FROM academy_profiles WHERE player_id = ?", (sid,))
            sec_acad_profiles = cursor.fetchall()
            
            for sec_acad in sec_acad_profiles:
                store_id = sec_acad['store_id']
                format_name = sec_acad['format_name']
                sec_acad_id = sec_acad['id']
                
                if (store_id, format_name) in acad_lookup:
                    prim_acad_id = acad_lookup[(store_id, format_name)]
                    cursor.execute("UPDATE academy_rating_history SET academy_profile_id = ? WHERE academy_profile_id = ?", (prim_acad_id, sec_acad_id))
                    cursor.execute("UPDATE OR IGNORE academy_achievements SET academy_profile_id = ? WHERE academy_profile_id = ?", (prim_acad_id, sec_acad_id))
                    cursor.execute("DELETE FROM academy_achievements WHERE academy_profile_id = ?", (sec_acad_id,))
                    cursor.execute("DELETE FROM academy_profiles WHERE id = ?", (sec_acad_id,))
                else:
                    cursor.execute("UPDATE academy_profiles SET player_id = ? WHERE id = ?", (primary_id, sec_acad_id))
                    acad_lookup[(store_id, format_name)] = sec_acad_id
                        
            # 5. Delete the secondary player
            cursor.execute("DELETE FROM players WHERE id = ?", (sid,))
            
        # Update primary player data
        cursor.execute("""
            UPDATE players 
            SET konami_id = ?, phone = ?, email = ?, nickname = ?
            WHERE id = ?
        """, (best_kid, best_phone, best_email, best_nick, primary_id))

        # Add aliases
        for a in aliases_to_add:
            if not a or len(a.strip()) < 2: continue
            try:
                cursor.execute("""
                    INSERT INTO player_aliases (player_id, alias, created_at)
                    VALUES (?, ?, datetime('now'))
                    ON CONFLICT(alias) DO UPDATE SET player_id = excluded.player_id
                """, (primary_id, a.strip()))
            except Exception:
                pass

        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def auto_deduplicate_all_players():
    """
    Detecta automáticamente duplicados de nombres o apodos conocidos y los fusiona
    en el perfil principal de forma limpia e irreversiblemente segura.
    """
    from utils import normalize_player_name
    conn = get_connection()
    conn.row_factory = __import__('sqlite3').Row
    cur = conn.cursor()

    # 1. Fusiones de apodos conocidos explícitos
    known_merges = [
        ("Maximiliano Candia", "Tío Zombie"),
        ("Esteban Ocompley", "Kame")
    ]
    for real_name, nick in known_merges:
        real_p = resolve_player(cur, real_name)
        nick_p = resolve_player(cur, nick)
        if real_p and nick_p and real_p['id'] != nick_p['id']:
            merge_players_db(real_p['id'], [nick_p['id']], nickname=nick)

    # 2. Fusiones por coincidencia de nombre normalizado
    cur.execute("SELECT id, name, konami_id, slug FROM players ORDER BY id ASC")
    all_players = [dict(r) for r in cur.fetchall()]

    from collections import defaultdict
    grouped = defaultdict(list)
    for p in all_players:
        norm = normalize_player_name(p['name'])
        grouped[norm].append(p)

    merged_count = 0
    for norm, p_list in grouped.items():
        if len(p_list) > 1:
            prim_id = min(p['id'] for p in p_list)
            sec_ids = [p['id'] for p in p_list if p['id'] != prim_id]
            merge_players_db(prim_id, sec_ids)
            merged_count += len(sec_ids)

    conn.close()
    return merged_count

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
