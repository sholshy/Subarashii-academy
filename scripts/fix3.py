import sys
import os

with open('tournament_ui.py', 'r', encoding='utf-8') as f:
    content = f.read()

# We need to replace the old_widgets cleanup block with the explicit frame cleanup block
# in show_setup_view, show_round_view, show_standings_view.

# First, find where buf = ctk.CTkFrame(self.content_frame, fg_color="transparent") is.
# We will replace it with:
# if getattr(self, "current_view_frame", None):
#     old = self.current_view_frame
#     self.after(20, lambda o=old: o.destroy() if o.winfo_exists() else None)
# self.current_view_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
# buf = self.current_view_frame

target_create = 'buf = ctk.CTkFrame(self.content_frame, fg_color="transparent")'
replacement_create = '''if getattr(self, "current_view_frame", None):
            old = self.current_view_frame
            self.after(20, lambda o=old: o.destroy() if o.winfo_exists() else None)
        self.current_view_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        buf = self.current_view_frame'''

content = content.replace(target_create, replacement_create)

# Then remove the old_widgets cleanup block at the end of the functions.
target_cleanup = """        old_widgets = [w for w in self.content_frame.winfo_children() if w != buf]
        def cleanup():
            for w in old_widgets:
                try:
                    w.destroy()
                except Exception:
                    pass
        self.after(20, cleanup)
        buf.pack(fill="both", expand=True)"""

replacement_cleanup = """        buf.pack(fill="both", expand=True)"""

content = content.replace(target_cleanup, replacement_cleanup)

with open('tournament_ui.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed logic!")
