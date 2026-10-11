import sys

with open('deck_editor_ui.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix empty string image warning
content = content.replace('image=""', 'image=None')

# Fix PhotoImage in preview
target_preview = """                    img = Image.open(path)
                    img = img.resize((220, 320), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    self.preview_image_label.configure(image=photo, text="")
                    self.preview_image_label.image = photo"""

replacement_preview = """                    img = Image.open(path)
                    photo = ctk.CTkImage(light_image=img, dark_image=img, size=(220, 320))
                    self.preview_image_label.configure(image=photo, text="")
                    self.preview_image_label.image = photo"""

content = content.replace(target_preview, replacement_preview)

# Fix PhotoImage in grid thumbnails
target_thumbnail = """                            img = Image.open(path)
                            img = img.resize((40, 58), Image.Resampling.LANCZOS)
                            photo = ImageTk.PhotoImage(img)
                            label.configure(image=photo, text="")
                            self.image_refs[f"{zone_name}_{cid}_{time.time()}"] = photo"""

replacement_thumbnail = """                            img = Image.open(path)
                            photo = ctk.CTkImage(light_image=img, dark_image=img, size=(40, 58))
                            label.configure(image=photo, text="")
                            self.image_refs[f"{zone_name}_{cid}_{time.time()}"] = photo"""

content = content.replace(target_thumbnail, replacement_thumbnail)

with open('deck_editor_ui.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed CTkImage warnings")
