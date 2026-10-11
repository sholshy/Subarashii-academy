import sqlite3
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_connection
from academy.academy_engine import AcademyEngine

conn = get_connection()
conn.row_factory = sqlite3.Row
c = conn.cursor()
e = AcademyEngine()

c.execute("SELECT id FROM academy_profiles WHERE format_name='GLOBAL'")
ids = [r['id'] for r in c.fetchall()]

for pid in ids:
    e.assign_weekly_missions(c, pid)
    
conn.commit()

c.execute("SELECT COUNT(*) FROM academy_missions")
print("Missions assigned:", c.fetchone()[0])
conn.close()
