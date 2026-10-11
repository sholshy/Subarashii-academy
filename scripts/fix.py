import sys
import os

with open('tournament_ui.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = """        for i, (rank, p) in enumerate(ranked):
            tree.insert("", "end", values=(rank, p.name, p.points, f"{getattr(p, '_omw', 0):.4f}", f"{getattr(p, '_oomw', 0):.4f}", self.friendly_tiebreaker_note(notes.get(p, ""))))
            initialfile = f"{store_str}_{fmt_str}_standing_final.png"
            filepath = filedialog.asksaveasfilename(
                initialfile=initialfile,
                defaultextension=".png",
                filetypes=[("PNG", "*.png")]
            )
            if not filepath:
                return

            img = generate_standings_image(self.manager, active_store, date_val)
            img.save(filepath)
            messagebox.showinfo("Standing exportado", f"Imagen guardada:\\n{os.path.basename(filepath)}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo exportar la imagen del standing: {e}")"""

replacement = """        for i, (rank, p) in enumerate(ranked):
            tree.insert("", "end", values=(rank, p.name, p.points, f"{getattr(p, '_omw', 0):.4f}", f"{getattr(p, '_oomw', 0):.4f}", self.friendly_tiebreaker_note(notes.get(p, ""))))

        for widget in self.content_frame.winfo_children():
            if widget != buf:
                widget.destroy()
        buf.pack(fill="both", expand=True)

    def export_standings_image(self):
        standings = self.manager.get_standings()
        if not standings:
            messagebox.showwarning("Atención", "No hay resultados disponibles para exportar.")
            return

        try:
            active_store = self.store_manager.get_active_store()
            import datetime
            from datetime import datetime
            date_val = getattr(self, "date_var", tk.StringVar(value=datetime.now().strftime("%d-%m-%y"))).get()
            fmt_str = self.manager.format_name.lower().replace(" ", "_")
            store_str = active_store.lower().replace(" ", "_")
            initialfile = f"{store_str}_{fmt_str}_standing_final.png"
            filepath = filedialog.asksaveasfilename(
                initialfile=initialfile,
                defaultextension=".png",
                filetypes=[("PNG", "*.png")]
            )
            if not filepath:
                return

            img = generate_standings_image(self.manager, active_store, date_val)
            img.save(filepath)
            messagebox.showinfo("Standing exportado", f"Imagen guardada:\\n{os.path.basename(filepath)}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo exportar la imagen del standing: {e}")"""

if target in content:
    content = content.replace(target, replacement)
    with open('tournament_ui.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fixed!")
else:
    print("Target not found.")
