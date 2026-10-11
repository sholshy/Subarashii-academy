import sqlite3
import os

conn = sqlite3.connect(os.path.join("data", "ygo_data.db"))
c = conn.cursor()

print("History:", c.execute("SELECT COUNT(*) FROM academy_rating_history").fetchone()[0])
print("Profiles:", c.execute("SELECT COUNT(*) FROM academy_profiles WHERE format_name='GLOBAL'").fetchone()[0])
print("Preseason:", c.execute("SELECT COUNT(*) FROM academy_preseason_players").fetchone()[0])

c.execute("SELECT player_id, current_rating, xp, level, dorm FROM academy_profiles WHERE format_name='GLOBAL' ORDER BY current_rating DESC LIMIT 5")
for r in c.fetchall():
    print(r)
