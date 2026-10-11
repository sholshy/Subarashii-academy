import sys

with open('store_ui.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = """            ctk.CTkButton(btns_frame, text="Exportar Standing a PNG", command=export_png, fg_color="#22c55e", hover_color="#16a34a", font=UI_FONT_SMALL).pack(side="left", padx=5)"""

replacement = """            ctk.CTkButton(btns_frame, text="Exportar Standing a PNG", command=export_png, fg_color="#22c55e", hover_color="#16a34a", font=UI_FONT_SMALL).pack(side="left", padx=5)

            def export_instagram():
                from tournament_manager import TournamentManager
                try:
                    from instagram_exporter import generate_instagram_post
                except ImportError:
                    import tkinter.messagebox as messagebox
                    messagebox.showerror("Error", "No se encontro el exportador de instagram")
                    return
                import os
                import tkinter.messagebox as messagebox
                try:
                    historical_manager = TournamentManager.from_dict(manager_data)
                    standings = historical_manager.get_standings()
                    if not standings:
                        messagebox.showwarning("Atención", "No hay resultados en el historial.")
                        return
                    
                    date_val = data.get("ui", {}).get("date", "Desconocido")
                    fmt_str = historical_manager.format_name
                    
                    img_path, caption = generate_instagram_post(standings, fmt_str, date_val)
                    
                    self.clipboard_clear()
                    self.clipboard_append(caption)
                    
                    os.startfile(os.path.abspath(img_path))
                    messagebox.showinfo("Exportado a Instagram", f"Imagen guardada en {img_path}.\\n\\n¡El texto descriptivo ha sido copiado al portapapeles! Listo para pegar en Instagram.")
                except Exception as e:
                    messagebox.showerror("Error", f"No se pudo exportar para Instagram:\\n{e}")

            ctk.CTkButton(btns_frame, text="Exportar a Instagram", command=export_instagram, fg_color="#d946ef", hover_color="#c026d3", font=UI_FONT_SMALL).pack(side="left", padx=5)"""

content = content.replace(target, replacement)

with open('store_ui.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patch applied to store_ui.py")
