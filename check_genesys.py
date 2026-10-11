import sqlite3, os
path = os.path.expandvars(r'%APPDATA%\YGO_Tools\data\ygo_data.db')
conn = sqlite3.connect(path)
cur = conn.cursor()
cur.execute("SELECT id, player_id, format_name FROM league_profiles WHERE format_name='Genesys'")
print('League Profiles:', cur.fetchall())
cur.execute("SELECT id, player_id, format_name FROM academy_profiles WHERE format_name='Genesys'")
print('Academy Profiles:', cur.fetchall())
