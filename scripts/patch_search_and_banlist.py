import sys

# Patch deck_editor_ui.py
with open('deck_editor_ui.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Remove [:25] truncation
target_trunc = 'lbl = ctk.CTkLabel(card_frame, text=name[:25], font=UI_FONT_SMALL, text_color="white", cursor="hand2")'
replacement_trunc = 'lbl = ctk.CTkLabel(card_frame, text=name, font=UI_FONT_SMALL, text_color="white", cursor="hand2")'
content = content.replace(target_trunc, replacement_trunc)

# 2. Change messagebox to self.bell()
target_bell = """        if count >= limit:
            import tkinter.messagebox as messagebox
            if limit == 0:
                messagebox.showwarning("Prohibida", f"'{name}' está Prohibida y no se puede jugar en este formato.")
            else:
                messagebox.showwarning("Límite", f"No puedes agregar más de {limit} copia(s) de '{name}'.")
            return"""
replacement_bell = """        if count >= limit:
            self.bell()
            return"""
content = content.replace(target_bell, replacement_bell)

with open('deck_editor_ui.py', 'w', encoding='utf-8') as f:
    f.write(content)


# Patch deck_generator_ui.py
with open('deck_generator_ui.py', 'r', encoding='utf-8') as f:
    gen_content = f.read()

# 3. Add Banned check
target_ban = 'if status == "Forbidden":'
replacement_ban = 'if status in ["Forbidden", "Banned"]:'
gen_content = gen_content.replace(target_ban, replacement_ban)

with open('deck_generator_ui.py', 'w', encoding='utf-8') as f:
    f.write(gen_content)

print("Patch applied")
