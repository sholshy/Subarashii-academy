import sys

with open('deck_editor_ui.py', 'r', encoding='utf-8') as f:
    content = f.read()

target1 = """    def load_database(self):
        fmt = self.current_format.get()
        self.db_cards = []
        self.filtered_cards = []
        self.refresh_results_ui([])
        self.preview_text_box.delete("1.0", "end")
        self.preview_text_box.insert("1.0", f"Cargando base de datos para {fmt}...")"""

replacement1 = """    def load_database(self):
        fmt = self.current_format.get()
        self.db_cards = []
        self.filtered_cards = []
        self.banlist_dict = {}
        
        # Load local banlist if exists
        import os, json
        filename = f"{fmt.lower().replace(' ', '_')}_banlist.json"
        if os.path.exists(filename):
            try:
                with open(filename, "r", encoding="utf-8") as bf:
                    self.banlist_dict = json.load(bf)
            except Exception as e:
                print(f"Error loading local banlist for {fmt}: {e}")

        self.refresh_results_ui([])
        self.preview_text_box.delete("1.0", "end")
        self.preview_text_box.insert("1.0", f"Cargando base de datos para {fmt}...")"""

content = content.replace(target1, replacement1)

target2 = """    def add_card_to_deck(self, card):
        type_ = card.get("type", "")"""

replacement2 = """    def get_card_limit(self, card):
        name = card.get("name", "").lower()
        fmt = self.current_format.get().lower()
        
        # Local Banlist Dictionary Check
        if hasattr(self, 'banlist_dict') and self.banlist_dict:
            status = self.banlist_dict.get(name)
            if status == "Forbidden": return 0
            if status == "Limited": return 1
            if status == "Semi-Limited": return 2
            return 3
            
        # API Banlist check (e.g. GOAT which uses API ban_goat field)
        ban_info = card.get("banlist_info", {})
        status = ban_info.get(f"ban_{fmt}", "")
        if status == "Banned": return 0
        if status == "Limited": return 1
        if status == "Semi-Limited": return 2
        return 3

    def add_card_to_deck(self, card):
        name = card.get("name", "")
        
        count = sum(1 for c in self.main_deck + self.extra_deck + self.side_deck if c.get("name") == name)
        limit = self.get_card_limit(card)
        
        if count >= limit:
            import tkinter.messagebox as messagebox
            if limit == 0:
                messagebox.showwarning("Prohibida", f"'{name}' está Prohibida y no se puede jugar en este formato.")
            else:
                messagebox.showwarning("Límite", f"No puedes agregar más de {limit} copia(s) de '{name}'.")
            return

        type_ = card.get("type", "")"""

content = content.replace(target2, replacement2)

with open('deck_editor_ui.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patch applied to deck_editor_ui.py")
