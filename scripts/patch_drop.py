import sys

# 1. Patch tournament_manager.py
with open('tournament_manager.py', 'r', encoding='utf-8') as f:
    mgr_content = f.read()

target_standings = "        standings = sorted(self.players, key=lambda x: (x.points, x._omw, x._oomw), reverse=True)"
replacement_standings = "        standings = sorted(self.players, key=lambda x: (x.active, x.points, x._omw, x._oomw), reverse=True)"
mgr_content = mgr_content.replace(target_standings, replacement_standings)

target_key = "    def standings_key(self, player):\\n        return (player.points, round(player._omw, 4), round(player._oomw, 4))"
replacement_key = "    def standings_key(self, player):\\n        return (player.active, player.points, round(player._omw, 4), round(player._oomw, 4))"
mgr_content = mgr_content.replace(target_key, replacement_key)

with open('tournament_manager.py', 'w', encoding='utf-8') as f:
    f.write(mgr_content)


# 2. Patch tournament_ui.py
with open('tournament_ui.py', 'r', encoding='utf-8') as f:
    ui_content = f.read()

target_ui = """        for rank, p in ranked:
            self.tree.insert("", "end", values=(rank, p.name, p.points, f"{getattr(p, '_omw', 0):.4f}", f"{getattr(p, '_oomw', 0):.4f}", self.friendly_tiebreaker_note(notes.get(p, ""))))"""

replacement_ui = """        for rank, p in ranked:
            name_display = p.name if p.active else f"{p.name} (Drop)"
            self.tree.insert("", "end", values=(rank, name_display, p.points, f"{getattr(p, '_omw', 0):.4f}", f"{getattr(p, '_oomw', 0):.4f}", self.friendly_tiebreaker_note(notes.get(p, ""))))"""

ui_content = ui_content.replace(target_ui, replacement_ui)

with open('tournament_ui.py', 'w', encoding='utf-8') as f:
    f.write(ui_content)


# 3. Patch tournament_graphics.py
with open('tournament_graphics.py', 'r', encoding='utf-8') as f:
    gfx_content = f.read()

target_gfx = '        name = player.name.upper()'
replacement_gfx = '        name = player.name.upper() if getattr(player, "active", True) else f"{player.name.upper()} (DROP)"'
gfx_content = gfx_content.replace(target_gfx, replacement_gfx)

with open('tournament_graphics.py', 'w', encoding='utf-8') as f:
    f.write(gfx_content)

print("Patch applied")
