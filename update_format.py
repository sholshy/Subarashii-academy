import sqlite3, os
path = os.path.expandvars(r'%APPDATA%\YGO_Tools\data\ygo_data.db')
conn = sqlite3.connect(path)
cur = conn.cursor()

# Update tournaments
cur.execute("UPDATE tournaments SET format_name = 'H.A.T.' WHERE format_name = 'Genesys'")

# Update league profiles
cur.execute("UPDATE league_profiles SET format_name = 'H.A.T.' WHERE format_name = 'Genesys'")

# Update academy profiles (just in case)
cur.execute("UPDATE academy_profiles SET format_name = 'H.A.T.' WHERE format_name = 'Genesys'")

conn.commit()
conn.close()
print("Updated Genesys to H.A.T.")
