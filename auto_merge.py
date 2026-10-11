import sqlite3
import os
import sys
from utils import normalize_player_name
from database import merge_players_db, get_connection

path = os.path.expandvars(r'%APPDATA%\YGO_Tools\data\ygo_data.db')
conn = sqlite3.connect(path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Update slugs for existing players
cur.execute('SELECT id, name FROM players')
for row in cur.fetchall():
    slug = normalize_player_name(row['name'])
    cur.execute('UPDATE players SET slug = ? WHERE id = ?', (slug, row['id']))
conn.commit()

# Get all players
cur.execute('SELECT id, name, slug FROM players')
players = cur.fetchall()

slug_map = {}
for p in players:
    slug = p['slug']
    if slug not in slug_map:
        slug_map[slug] = []
    slug_map[slug].append(p['id'])

merged_count = 0
for slug, ids in slug_map.items():
    if len(ids) > 1:
        ids.sort()
        primary_id = ids[0]
        secondary_ids = ids[1:]
        print(f'Merging {slug}: {secondary_ids} into {primary_id}')
        merge_players_db(primary_id, secondary_ids)
        merged_count += 1

print(f'Merged {merged_count} groups of duplicated players.')
conn.close()
