import sys

with open('tournament_ui.py', 'r', encoding='utf-8') as f:
    content = f.read()

target_btn = """        ctk.CTkButton(final_actions_frame, text="EXPORTAR STANDING PNG", command=self.export_standings_image, font=UI_FONT_SMALL, width=150).pack(side="left", padx=5, pady=5)"""
replacement_btn = """        ctk.CTkButton(final_actions_frame, text="EXPORTAR STANDING PNG", command=self.export_standings_image, font=UI_FONT_SMALL, width=150).pack(side="left", padx=5, pady=5)
        ctk.CTkButton(final_actions_frame, text="EXPORTAR A INSTAGRAM", command=self.export_to_instagram, font=UI_FONT_SMALL, width=170, fg_color="#d946ef", hover_color="#c026d3").pack(side="left", padx=5, pady=5)"""
content = content.replace(target_btn, replacement_btn)

target_def = """    def export_standings_image(self):"""
replacement_def = """    def export_to_instagram(self):
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
            messagebox.showerror("Error", f"Fallo al exportar para Instagram: {e}")

    def export_standings_image(self):"""
content = content.replace(target_def, replacement_def)

with open('tournament_ui.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patch applied to tournament_ui.py")
