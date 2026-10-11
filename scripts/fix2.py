import sys
import os

with open('tournament_ui.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = """        for widget in self.content_frame.winfo_children():
            if widget != buf:
                widget.destroy()
        buf.pack(fill="both", expand=True)"""

replacement = """        old_widgets = [w for w in self.content_frame.winfo_children() if w != buf]
        def cleanup():
            for w in old_widgets:
                try:
                    w.destroy()
                except Exception:
                    pass
        self.after(20, cleanup)
        buf.pack(fill="both", expand=True)"""

if target in content:
    content = content.replace(target, replacement)
    with open('tournament_ui.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fixed!")
else:
    print("Target not found.")
