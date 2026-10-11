import sys

with open('tournament_ui.py', 'r', encoding='utf-8') as f:
    content = f.read()

target_rb = """        ctk.CTkRadioButton(format_frame, text="GOAT (2005)", variable=self.format_var, value="GOAT", font=UI_FONT_SMALL).pack(side="left", padx=10)
        ctk.CTkRadioButton(format_frame, text="EDISON (2010)", variable=self.format_var, value="EDISON", font=UI_FONT_SMALL).pack(side="left", padx=10)
        ctk.CTkRadioButton(format_frame, text="Speed Duel", variable=self.format_var, value="Speed Duel", font=UI_FONT_SMALL).pack(side="left", padx=10)"""

replacement_rb = """        ctk.CTkRadioButton(format_frame, text="GOAT (2005)", variable=self.format_var, value="GOAT", command=self.on_format_changed, font=UI_FONT_SMALL).pack(side="left", padx=10)
        ctk.CTkRadioButton(format_frame, text="EDISON (2010)", variable=self.format_var, value="EDISON", command=self.on_format_changed, font=UI_FONT_SMALL).pack(side="left", padx=10)
        ctk.CTkRadioButton(format_frame, text="Speed Duel", variable=self.format_var, value="Speed Duel", command=self.on_format_changed, font=UI_FONT_SMALL).pack(side="left", padx=10)"""

content = content.replace(target_rb, replacement_rb)

target_def = """    def start_tournament(self):"""

replacement_def = """    def on_format_changed(self):
        format_val = self.format_var.get()
        if format_val == "Speed Duel":
            self.round_minutes_var.set("30")
        else:
            self.round_minutes_var.set("50")

    def start_tournament(self):"""

content = content.replace(target_def, replacement_def)

with open('tournament_ui.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patch applied")
