import sys

with open('deck_generator_ui.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = """        self.text_box = ctk.CTkTextbox(
            self.editor_frame, width=800, height=200, font=("Consolas", 14),
            fg_color="#0f172a", text_color="#60a5fa"
        )"""

replacement = """        editor_btn = ctk.CTkButton(
            self.editor_frame, text="ARMAR DECK EN EL EDITOR INTERACTIVO", font=UI_FONT_BIG,
            fg_color="#8b5cf6", hover_color="#7c3aed", command=self.open_deck_editor
        )
        editor_btn.pack(side="top", pady=10)

        self.text_box = ctk.CTkTextbox(
            self.editor_frame, width=800, height=200, font=("Consolas", 14),
            fg_color="#0f172a", text_color="#60a5fa"
        )"""

content = content.replace(target, replacement)

target2 = """    def prefill_event_info(self,"""
replacement2 = """    def open_deck_editor(self):
        self.editor_frame.pack_forget()
        from deck_editor_ui import DeckEditorUI
        import tkinter as tk
        
        def on_confirm(ydk_text):
            self.deck_editor_frame.pack_forget()
            self.deck_editor_frame.destroy()
            self.editor_frame.pack(fill="both", expand=True)
            self.text_box.delete("1.0", tk.END)
            self.text_box.insert("1.0", ydk_text)
            
        def on_back():
            self.deck_editor_frame.pack_forget()
            self.deck_editor_frame.destroy()
            self.editor_frame.pack(fill="both", expand=True)

        self.deck_editor_frame = DeckEditorUI(self, on_back, on_confirm)
        self.deck_editor_frame.pack(fill="both", expand=True)

    def prefill_event_info(self,"""

content = content.replace(target2, replacement2)

with open('deck_generator_ui.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patch applied")
