import sys

with open('store_ui.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = """                        os.remove(os.path.join(history_dir, data['_filename']))
                        self.tournaments_data = load_list()
                        for widget in details_frame.winfo_children():
                            widget.destroy()"""

replacement = """                        os.remove(os.path.join(history_dir, data['_filename']))
                        self.tournaments_data = load_list()
                        for widget in details_frame.winfo_children():
                            widget.destroy()
                        self.update_stats()"""

content = content.replace(target, replacement)

with open('store_ui.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patch applied")
