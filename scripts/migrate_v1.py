import sqlite3
import os
import sys
import re

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_connection

def generate_slug(name, existing_slugs):
    # Basic normalization: Nicolas Mardones -> nmardones
    # Remove accents
    import unicodedata
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('utf-8')
    name = name.lower()
    
    parts = name.split()
    if len(parts) >= 2:
        base_slug = parts[0][0] + parts[1]
    else:
        base_slug = parts[0]
        
    base_slug = re.sub(r'[^a-z0-9]', '', base_slug)
    
    slug = base_slug
    counter = 1
    while slug in existing_slugs:
        slug = f"{base_slug}{counter}"
        counter += 1
        
    return slug

def add_column_if_not_exists(cursor, table_name, column_name, column_def):
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row['name'] for row in cursor.fetchall()]
    if column_name not in columns:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")
        print(f"Added column {column_name} to {table_name}.")
        return True
    return False

def migrate_v1():
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. PLAYERS: Add slug
    added = add_column_if_not_exists(cursor, 'players', 'slug', 'TEXT')
    if added:
        cursor.execute("SELECT id, name FROM players WHERE slug IS NULL")
        players = cursor.fetchall()
        
        cursor.execute("SELECT slug FROM players WHERE slug IS NOT NULL")
        existing_slugs = set(row['slug'] for row in cursor.fetchall())
        
        for p in players:
            slug = generate_slug(p['name'], existing_slugs)
            existing_slugs.add(slug)
            cursor.execute("UPDATE players SET slug = ? WHERE id = ?", (slug, p['id']))
            print(f"Generated slug '{slug}' for player '{p['name']}'.")
            
        # We can't add UNIQUE constraint directly in sqlite ALTER TABLE, 
        # but we enforce it in code or by recreating the table. For now, just code enforcement is enough.

    # 2. ACADEMY_PROFILES: Add xp and level
    add_column_if_not_exists(cursor, 'academy_profiles', 'xp', 'INTEGER DEFAULT 0')
    add_column_if_not_exists(cursor, 'academy_profiles', 'level', 'INTEGER DEFAULT 1')
    add_column_if_not_exists(cursor, 'academy_profiles', 'matches_played', 'INTEGER DEFAULT 0')
    add_column_if_not_exists(cursor, 'academy_profiles', 'wins', 'INTEGER DEFAULT 0')
    add_column_if_not_exists(cursor, 'academy_profiles', 'losses', 'INTEGER DEFAULT 0')
    add_column_if_not_exists(cursor, 'academy_profiles', 'title', 'TEXT')

    # 3. Create new tables
    tables = [
        '''
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
        ''',
        '''
        CREATE TABLE IF NOT EXISTS mission_catalog (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            target_value INTEGER,
            xp_reward INTEGER,
            type TEXT
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS academy_seasons (
            id TEXT PRIMARY KEY,
            number INTEGER,
            start_date TEXT NOT NULL,
            end_date TEXT,
            status TEXT DEFAULT 'ACTIVE'
        )
        ''',
        '''
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
        ''',
        '''
        CREATE TABLE IF NOT EXISTS reward_catalog (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            type TEXT
        )
        ''',
        '''
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
        ''',
        '''
        CREATE TABLE IF NOT EXISTS academy_publications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version INTEGER NOT NULL UNIQUE,
            timestamp TEXT NOT NULL,
            tournament_id INTEGER,
            checksum TEXT,
            status TEXT DEFAULT 'PENDING',
            FOREIGN KEY(tournament_id) REFERENCES tournaments(id) ON DELETE SET NULL
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS academy_public_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            publication_id INTEGER NOT NULL,
            path TEXT NOT NULL,
            FOREIGN KEY(publication_id) REFERENCES academy_publications(id) ON DELETE CASCADE
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS academy_preseason_players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tournament_id INTEGER NOT NULL,
            player_id INTEGER NOT NULL,
            processed BOOLEAN DEFAULT 1,
            FOREIGN KEY(tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
            FOREIGN KEY(player_id) REFERENCES players(id) ON DELETE CASCADE,
            UNIQUE(tournament_id, player_id)
        )
        '''
    ]

    for stmt in tables:
        cursor.execute(stmt)
        
    conn.commit()
    conn.close()
    print("Migración V1.0 completada exitosamente sin destrucción de datos.")

if __name__ == "__main__":
    migrate_v1()
