import sys

# Patch tournament_ui.py
with open('tournament_ui.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = """    def export_to_instagram(self):
        standings = self.manager.get_standings()
        if not standings:
            import tkinter.messagebox as messagebox
            messagebox.showwarning("Atención", "No hay resultados disponibles para exportar.")
            return
        try:
            from instagram_exporter import generate_instagram_post
            import datetime
            import tkinter as tk
            import tkinter.messagebox as messagebox
            import os
            date_val = getattr(self, "date_var", tk.StringVar(value=datetime.datetime.now().strftime("%d-%m-%y"))).get()
            fmt_str = getattr(self.manager, "format_name", "Torneo")
            
            img_path, caption = generate_instagram_post(standings, fmt_str, date_val)
            
            self.clipboard_clear()
            self.clipboard_append(caption)
            
            os.startfile(os.path.abspath(img_path))
            messagebox.showinfo("Exportado a Instagram", f"Imagen guardada en {img_path}.\\n\\n¡El texto descriptivo ha sido copiado al portapapeles! Listo para pegar en Instagram.")
        except Exception as e:
            import tkinter.messagebox as messagebox
            messagebox.showerror("Error", f"Fallo al exportar para Instagram: {e}")"""

replacement = """    def export_to_instagram(self):
        standings = self.manager.get_standings()
        if not standings:
            import tkinter.messagebox as messagebox
            messagebox.showwarning("Atención", "No hay resultados disponibles para exportar.")
            return
        try:
            from instagram_exporter import generate_instagram_caption, save_instagram_image
            from tournament_graphics import generate_standings_image
            import datetime
            import tkinter as tk
            import tkinter.messagebox as messagebox
            import os
            
            date_val = getattr(self, "date_var", tk.StringVar(value=datetime.datetime.now().strftime("%d-%m-%y"))).get()
            fmt_str = getattr(self.manager, "format_name", "Torneo")
            active_store = "Tienda"
            if hasattr(self, "store_manager"):
                active_store = self.store_manager.get_active_store()
            
            img = generate_standings_image(self.manager, active_store, date_val)
            img_path = save_instagram_image(img)
            
            caption = generate_instagram_caption(standings, fmt_str)
            
            self.clipboard_clear()
            self.clipboard_append(caption)
            
            os.startfile(img_path)
            messagebox.showinfo("Exportado a Instagram", f"Imagen guardada en {img_path}.\\n\\n¡El texto descriptivo ha sido copiado al portapapeles! Listo para pegar en Instagram.")
        except Exception as e:
            import tkinter.messagebox as messagebox
            messagebox.showerror("Error", f"Fallo al exportar para Instagram: {e}")"""

content = content.replace(target, replacement)
with open('tournament_ui.py', 'w', encoding='utf-8') as f:
    f.write(content)

# Patch store_ui.py
with open('store_ui.py', 'r', encoding='utf-8') as f:
    content = f.read()

target2 = """            def export_instagram():
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
                    messagebox.showerror("Error", f"No se pudo exportar para Instagram:\\n{e}")"""

replacement2 = """            def export_instagram():
                from tournament_manager import TournamentManager
                try:
                    from instagram_exporter import generate_instagram_caption, save_instagram_image
                    from tournament_graphics import generate_standings_image
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
                    
                    store_val = data.get("ui", {}).get("store_name", self.manager.get_active_store() or "Tienda")
                    date_val = data.get("ui", {}).get("date", "Desconocido")
                    fmt_str = historical_manager.format_name
                    
                    img = generate_standings_image(historical_manager, store_val, date_val)
                    img_path = save_instagram_image(img)
                    caption = generate_instagram_caption(standings, fmt_str)
                    
                    self.clipboard_clear()
                    self.clipboard_append(caption)
                    
                    os.startfile(img_path)
                    messagebox.showinfo("Exportado a Instagram", f"Imagen guardada en {img_path}.\\n\\n¡El texto descriptivo ha sido copiado al portapapeles! Listo para pegar en Instagram.")
                except Exception as e:
                    messagebox.showerror("Error", f"No se pudo exportar para Instagram:\\n{e}")"""

content = content.replace(target2, replacement2)
with open('store_ui.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patch applied to both UIs")
