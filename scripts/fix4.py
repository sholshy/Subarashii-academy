import sys

with open('tournament_ui.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = """        for widget in self.content_frame.winfo_children():
            widget.destroy()
        buf.pack(fill="both", expand=True)"""

replacement = """        buf.pack(fill="both", expand=True)"""

if target in content:
    content = content.replace(target, replacement)
    with open('tournament_ui.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fixed sync loops!")
else:
    print("Target not found.")
