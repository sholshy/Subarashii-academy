import sqlite3, os
conn = sqlite3.connect(os.path.expandvars(r'%APPDATA%\YGO_Tools\data\ygo_data.db'))
cur = conn.cursor()
cur.execute("DELETE FROM tournament_matches WHERE tournament_id=40 AND result_text='Pendiente'")
conn.commit()
print('Deleted dummy matches')
