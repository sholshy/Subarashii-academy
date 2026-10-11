import sqlite3
import os

conn = sqlite3.connect(os.path.join("data", "ygo_data.db"))
c = conn.cursor()

c.execute("DELETE FROM academy_preseason_players")
c.execute("DELETE FROM academy_achievements")
c.execute("DELETE FROM academy_rating_history")
c.execute("DELETE FROM academy_profiles WHERE format_name='GLOBAL'")
conn.commit()
print("Reset OK")
