import sqlite3

conn = sqlite3.connect('data/ygo_data.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

c.execute("SELECT id, name FROM players WHERE name LIKE 'Nicol_s Mardones'")
players = c.fetchall()
for p in players:
    pid = p['id']
    print(f"Player: {p['name']} (ID: {pid})")
    
    c.execute("SELECT format_name, matches_played, wins, losses FROM academy_profiles WHERE player_id=?", (pid,))
    profiles = c.fetchall()
    for prof in profiles:
        print(f"  Format: {prof['format_name']} -> {prof['matches_played']} matches, {prof['wins']} W / {prof['losses']} L")

conn.close()
