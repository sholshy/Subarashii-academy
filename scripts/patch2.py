import sys

with open('tournament_ui.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = """    def update_player_list(self):
        yv = self.player_listbox.yview()"""

replacement = """    def update_player_list(self):
        yv = self.player_listbox.yview()
        selection = self.player_listbox.curselection()"""

content = content.replace(target, replacement)

with open('tournament_ui.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patch 2 applied.")
