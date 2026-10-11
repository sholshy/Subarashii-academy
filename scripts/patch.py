import sys

with open('tournament_ui.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. on_db_player_select calls add_player()
target_1 = """            self.email_entry.delete(0, tk.END)
            self.email_entry.insert(0, data.get("email", ""))"""

replacement_1 = """            self.email_entry.delete(0, tk.END)
            self.email_entry.insert(0, data.get("email", ""))
            self.add_player()"""

content = content.replace(target_1, replacement_1)

# 2. Bindings for player_listbox
target_2 = """        self.player_listbox.bind("<Double-1>", self.on_enrolled_player_select)"""
replacement_2 = """        self.player_listbox.bind("<<ListboxSelect>>", self.on_enrolled_player_select)
        self.player_listbox.bind("<KeyPress-i>", self.toggle_enrolled_invited_key)
        self.player_listbox.bind("<KeyPress-p>", self.toggle_enrolled_paid_key)
        self.player_listbox.bind("<KeyPress-I>", self.toggle_enrolled_invited_key)
        self.player_listbox.bind("<KeyPress-P>", self.toggle_enrolled_paid_key)"""
content = content.replace(target_2, replacement_2)

# 3. Add toggle_enrolled_paid_key and toggle_enrolled_invited_key methods
target_3 = """    def toggle_enrolled_paid(self):"""
replacement_3 = """    def toggle_enrolled_paid_key(self, event):
        self.toggle_enrolled_paid()

    def toggle_enrolled_invited_key(self, event):
        self.toggle_enrolled_invited()

    def toggle_enrolled_paid(self):"""
content = content.replace(target_3, replacement_3)

# 4. In update_player_list, save and restore curselection AND activate index
target_4_1 = """    def update_player_list(self):
        if not hasattr(self, "player_listbox"): return
        yv = self.player_listbox.yview()"""
replacement_4_1 = """    def update_player_list(self):
        if not hasattr(self, "player_listbox"): return
        yv = self.player_listbox.yview()
        selection = self.player_listbox.curselection()"""

target_4_2 = """        self.player_listbox.yview_moveto(yv[0])"""
replacement_4_2 = """        self.player_listbox.yview_moveto(yv[0])
        if selection:
            self.player_listbox.selection_set(selection[0])
            self.player_listbox.activate(selection[0])"""

content = content.replace(target_4_1, replacement_4_1)
content = content.replace(target_4_2, replacement_4_2)

# Ensure toggle_enrolled_paid sets active correctly (already fixed by update_player_list, but we can do it explicitly)
target_5_1 = """        self.player_listbox.selection_set(index)"""
replacement_5_1 = """        self.player_listbox.selection_set(index)
        self.player_listbox.activate(index)"""
content = content.replace(target_5_1, replacement_5_1)

with open('tournament_ui.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patch applied.")
