import sys

# 1. store_manager.py
with open('store_manager.py', 'r', encoding='utf-8') as f:
    content = f.read()

target1 = """    def get_league_db_path(self, store_name):
        return "data/ygo_data.db"\n\n"""
content = content.replace(target1, "")

with open('store_manager.py', 'w', encoding='utf-8') as f:
    f.write(content)

# 2. league_ui.py
with open('league_ui.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("m, a, mi, _ = p.get_points_composition()", "m, a, _, _ = p.get_points_composition()")

with open('league_ui.py', 'w', encoding='utf-8') as f:
    f.write(content)

# 3. store_ui.py
with open('store_ui.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("        import matplotlib.pyplot as plt\n", "")

with open('store_ui.py', 'w', encoding='utf-8') as f:
    f.write(content)

# 4. make_yugioh_wav.py
with open('make_yugioh_wav.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("for loop in range(4): # 4 repetitions", "for _ in range(4): # 4 repetitions")

with open('make_yugioh_wav.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Cleanup patch applied")
