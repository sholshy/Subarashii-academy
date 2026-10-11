import tkinter as tk
from tkinter import ttk, filedialog
import customtkinter as ctk
import custom_alerts as messagebox
from league_manager import LeagueManager
from league_graphics import generate_top8_standings, generate_trend_chart
from store_manager import StoreManager
import os
import threading
from datetime import datetime
from PIL import ImageTk

UI_FONT = ("Roboto", 13)
UI_FONT_BIG = ("Orbitron Black", 24)
UI_FONT_SMALL = ("Roboto", 11)

class LeagueUI(ctk.CTkFrame):
    def __init__(self, parent, go_back_callback):
        super().__init__(parent, fg_color="transparent")
        self.go_back_callback = go_back_callback
        self.store_manager = StoreManager()
        self.manager = LeagueManager(db_path=self.store_manager.get_active_league_db_path())
        self.setup_ui()

    def setup_ui(self):
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", pady=10)

        back_btn = ctk.CTkButton(header_frame, text="< VOLVER AL MENÚ", command=self.go_back_callback, font=UI_FONT)
        back_btn.pack(side="left", padx=20)

        self.title_label = ctk.CTkLabel(header_frame, text="Gestor de Liga GOAT", font=UI_FONT_BIG, text_color="#60a5fa")
        self.title_label.pack(side="left", expand=True)

        format_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        format_frame.pack(side="right", padx=20)
        
        ctk.CTkButton(format_frame, text="REINICIAR LIGA", command=self.reset_league, font=UI_FONT_SMALL, width=100, fg_color="#ef4444", hover_color="#b91c1c").pack(side="left", padx=10)
        
        ctk.CTkLabel(format_frame, text="Formato:", text_color="#60a5fa", font=UI_FONT_SMALL).pack(side="left", padx=5)
        self.format_var = ctk.StringVar(value="GOAT")
        self.format_cb = ctk.CTkComboBox(
            format_frame, variable=self.format_var, 
            values=["GOAT", "EDISON", "Tengu", "H.A.T.", "Speed Duel", "Perfect Circle", "TCG"], 
            font=UI_FONT_SMALL, width=150, command=self.on_format_change
        )
        self.format_cb.pack(side="left")
        
        # Bind events for custom formats typed manually
        self.format_cb.bind("<Return>", lambda e: self.on_format_change(self.format_var.get()))
        self.format_cb.bind("<FocusOut>", lambda e: self.on_format_change(self.format_var.get()))

        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=10)

        self.tab_players = self.tabview.add("Directorio de Jugadores")
        self.tab_matches = self.tabview.add("Misiones de Bingo")
        self.tab_graphics = self.tabview.add("Generador Visuales (IG)")

        self.setup_players_tab()
        self.setup_matches_tab()
        self.setup_graphics_tab()
        self.refresh_players_list()

    def on_format_change(self, value):
        self.manager.current_format = self.format_var.get()
        self.refresh_players_list()

    def set_format(self, format_name):
        self.format_var.set(format_name)
        self.manager.current_format = format_name
        self.refresh_players_list()

    def setup_players_tab(self):
        left_frame = ctk.CTkFrame(self.tab_players, fg_color="#0f172a")
        left_frame.pack(side="left", fill="y", padx=10, pady=10, ipadx=20, ipady=20)

        ctk.CTkLabel(left_frame, text="Editar Info del Jugador", font=UI_FONT, text_color="#60a5fa").pack(pady=(10, 10))
        ctk.CTkLabel(left_frame, text="(Los jugadores se registran al importar desde un Torneo)", text_color="#94a3b8", font=UI_FONT_SMALL).pack(pady=(0, 20))

        ctk.CTkLabel(left_frame, text="Jugador Seleccionado:", text_color="#60a5fa", font=UI_FONT_SMALL).pack(anchor="w")
        self.edit_name_var = ctk.StringVar()
        self.edit_name_lbl = ctk.CTkLabel(left_frame, textvariable=self.edit_name_var, text_color="#60a5fa", font=UI_FONT)
        self.edit_name_lbl.pack(pady=(0, 10), anchor="w")

        ctk.CTkLabel(left_frame, text="Nombre del Mazo:", text_color="#60a5fa", font=UI_FONT_SMALL).pack(anchor="w")
        self.reg_deck = ctk.CTkEntry(left_frame, font=UI_FONT, width=250)
        self.reg_deck.pack(pady=(0, 10))

        ctk.CTkLabel(left_frame, text="Carta Insignia (Exacto en inglés):", text_color="#60a5fa", font=UI_FONT_SMALL).pack(anchor="w")
        self.reg_card = ctk.CTkEntry(left_frame, font=UI_FONT, width=250)
        self.reg_card.pack(pady=(0, 10))

        ctk.CTkLabel(left_frame, text="Teléfono:", text_color="#60a5fa", font=UI_FONT_SMALL).pack(anchor="w")
        self.reg_phone = ctk.CTkEntry(left_frame, font=UI_FONT, width=250)
        self.reg_phone.pack(pady=(0, 10))
        
        ctk.CTkLabel(left_frame, text="Correo Electrónico:", text_color="#60a5fa", font=UI_FONT_SMALL).pack(anchor="w")
        self.reg_email = ctk.CTkEntry(left_frame, font=UI_FONT, width=250)
        self.reg_email.pack(pady=(0, 10))

        ctk.CTkButton(left_frame, text="ACTUALIZAR", command=self.update_player, font=UI_FONT).pack(pady=10)

        right_frame = ctk.CTkFrame(self.tab_players, fg_color="#0f172a")
        right_frame.pack(side="left", fill="both", expand=True, padx=10, pady=10, ipadx=10, ipady=10)

        ctk.CTkLabel(right_frame, text="Jugadores Inscritos", font=UI_FONT, text_color="#60a5fa").pack(pady=(10, 10))

        cols = ("Rank", "Name", "Deck", "Signature", "Total Pts", "Matches", "Attendance")
        self.players_tree = ttk.Treeview(right_frame, columns=cols, show="headings", height=15)
        for c in cols:
            self.players_tree.heading(c, text=c)
        self.players_tree.pack(fill="both", expand=True)
        self.players_tree.bind("<<TreeviewSelect>>", self.on_player_select)
        
        ctk.CTkButton(right_frame, text="Eliminar Seleccionado", command=self.remove_player, font=UI_FONT_SMALL, fg_color="#ef4444", hover_color="#b91c1c").pack(pady=10)

    def on_player_select(self, event):
        selected = self.players_tree.selection()
        if not selected: return
        item = self.players_tree.item(selected[0])
        name = item["values"][1]
        deck = item["values"][2]
        card = item["values"][3]
        
        self.edit_name_var.set(name)
        self.reg_deck.delete(0, tk.END)
        self.reg_deck.insert(0, deck if deck else "")
        self.reg_card.delete(0, tk.END)
        self.reg_card.insert(0, card if card else "")
        
        p = self.manager.get_player(name)
        if p:
            self.reg_phone.delete(0, tk.END)
            self.reg_phone.insert(0, getattr(p, 'phone', ''))
            self.reg_email.delete(0, tk.END)
            self.reg_email.insert(0, getattr(p, 'email', ''))

    def update_player(self):
        name = self.edit_name_var.get()
        if not name:
            messagebox.showwarning("Error", "Selecciona un jugador de la tabla primero.")
            return

        deck = self.reg_deck.get().strip()
        card = self.reg_card.get().strip()
        phone = self.reg_phone.get().strip()
        email = self.reg_email.get().strip()
        
        try:
            self.manager.update_player_info(name, deck, card, phone, email)
            self.refresh_players_list()
            messagebox.showinfo("Éxito", f"Información actualizada para {name}.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def remove_player(self):
        selected = self.players_tree.selection()
        if not selected: return
        item = self.players_tree.item(selected[0])
        name = item["values"][1]
        if messagebox.askyesno("Confirmar", f"¿Eliminar a {name} de la liga?"):
            self.manager.remove_player(name)
            self.refresh_players_list()
            self.refresh_matches_combo()

    def reset_league(self):
        if messagebox.askyesno("PELIGRO", f"Esto borrará el historial de torneos y misiones de TODOS los jugadores de {self.format_var.get()} para empezar una nueva temporada. (Los jugadores no serán eliminados). ¿Confirmar?"):
            self.manager.reset_league()
            self.refresh_players_list()
            messagebox.showinfo("Liga Reiniciada", "Los historiales de la liga han sido borrados con éxito. Los jugadores se han mantenido en la base de datos.")

    def refresh_players_list(self):
        self.store_manager = StoreManager()
        active_store = self.store_manager.get_active_store()
        active_db_path = self.store_manager.get_active_league_db_path()
        if self.manager.db_path != active_db_path:
            self.manager = LeagueManager(db_path=active_db_path, current_format=self.format_var.get())
        self.title_label.configure(text=f"Gestor de Liga {self.format_var.get().upper()} - {active_store}")

        # Reload to ensure we have fresh data exported from tournaments
        for row in self.players_tree.get_children():
            self.players_tree.delete(row)
        for rank, p in self.manager.get_ranked_standings():
            m, a, _, _ = p.get_points_composition()
            self.players_tree.insert("", "end", values=(f"#{rank}", p.name, p.deck_name, p.signature_card, p.get_total_points(), m, a))
        self.refresh_matches_combo()

    def setup_matches_tab(self):
        frame = ctk.CTkFrame(self.tab_matches, fg_color="#0f172a")
        frame.pack(fill="both", expand=True, padx=40, pady=20, ipadx=20, ipady=20)

        ctk.CTkLabel(frame, text="Registrar Misiones de Bingo", font=UI_FONT_BIG, text_color="#60a5fa").pack(pady=(10, 20))

        ctk.CTkLabel(frame, text="Seleccionar Jugador:", text_color="#60a5fa", font=UI_FONT).pack()
        self.match_player_var = ctk.StringVar()
        self.match_player_cb = ctk.CTkOptionMenu(frame, variable=self.match_player_var, font=UI_FONT, width=300, command=self.on_bingo_player_select)
        self.match_player_cb.pack(pady=(0, 10))

        ctk.CTkLabel(frame, text="Seleccionar Torneo/Semana:", text_color="#60a5fa", font=UI_FONT).pack()
        self.week_var = ctk.StringVar()
        self.week_cb = ctk.CTkOptionMenu(frame, variable=self.week_var, font=UI_FONT, width=300, command=self.on_week_select)
        self.week_cb.pack(pady=(0, 20))

        ctk.CTkLabel(frame, text="Misiones completadas del torneo seleccionado (+3 pts x linea, +5 pts carton lleno):", text_color="#eab308", font=UI_FONT_SMALL).pack(pady=(10, 5))
        
        grid_frame = ctk.CTkFrame(frame, fg_color="#0f172a")
        grid_frame.pack(pady=10)
        
        headers = ["JUEGO", "TIENDA", "COMUNIDAD"]
        for i, h in enumerate(headers):
            ctk.CTkLabel(grid_frame, text=h, font=UI_FONT_SMALL, text_color="#60a5fa").grid(row=0, column=i, padx=10, pady=5)
            
        self.bingo_vars = []
        for i in range(9):
            var = tk.BooleanVar()
            self.bingo_vars.append(var)
            cb = ctk.CTkCheckBox(grid_frame, text="", width=24, variable=var, onvalue=True, offvalue=False)
            cb.grid(row=(i//3)+1, column=i%3, padx=10, pady=5)

        ctk.CTkButton(frame, text="GUARDAR MISIONES", command=self.save_missions, font=UI_FONT).pack(pady=30)

    def refresh_matches_combo(self):
        names = sorted([p.name for p in self.manager.players], key=str.lower)
        if names:
            self.match_player_cb.configure(values=names)
            current_selection = self.match_player_var.get()
            if current_selection not in names:
                current_selection = names[0]
                self.match_player_cb.set(current_selection)
            self.on_bingo_player_select(current_selection)
        else:
            self.match_player_cb.configure(values=[""])
            self.match_player_cb.set("")

    def on_bingo_player_select(self, name):
        p = self.manager.get_player(name)
        if p:
            global_tournaments = self.manager.get_global_tournaments()
            t_id_to_week = {t['id']: i + 1 for i, t in enumerate(global_tournaments)}
            
            tournaments = []
            for idx, week in enumerate(p.history):
                date = week.get("date", "sin fecha")
                t_id = week.get("tournament_id")
                week_num = t_id_to_week.get(t_id, idx + 1)
                
                placement_pts = week.get("placement_points", 0)
                total_pts = placement_pts + (5 if week.get("attendance") else 0)
                tournaments.append(f"Semana {week_num} - {date} - {total_pts} pts")

            if tournaments:
                self.week_cb.configure(values=tournaments)
                self.week_cb.set(tournaments[-1])
                self.on_week_select(tournaments[-1])
            else:
                self.week_cb.configure(values=[""])
                self.week_cb.set("")
                for var in self.bingo_vars:
                    var.set(False)
        else:
            self.week_cb.configure(values=[""])
            self.week_cb.set("")

    def on_week_select(self, month_str):
        name = self.match_player_var.get()
        if not name or not month_str: return
        
        # Need to find index
        try:
            values = self.week_cb._values
            idx = values.index(month_str)
        except ValueError:
            idx = -1
            
        p = self.manager.get_player(name)
        if p:
            if 0 <= idx < len(p.history):
                grid = p.history[idx].get("bingo_grid", [False] * 9)
                for i in range(9):
                    self.bingo_vars[i].set(bool(grid[i]) if i < len(grid) else False)
            else:
                for var in self.bingo_vars:
                    var.set(False)

    def save_missions(self):
        name = self.match_player_var.get()
        try:
            values = self.week_cb._values
            month_str = self.week_var.get()
            idx = values.index(month_str)
        except ValueError:
            idx = -1
            
        if not name or idx < 0:
            messagebox.showwarning("Error", "Selecciona un jugador y un torneo valido.")
            return
            
        grid_vals = [var.get() for var in self.bingo_vars]

        try:
            self.manager.update_tournament_missions(name, idx, grid_vals)
            messagebox.showinfo("Éxito", f"Misiones actualizadas para {name}.")
            self.refresh_players_list()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def setup_graphics_tab(self):
        self.current_graphic = None
        self.current_filename = ""
        
        frame = ctk.CTkFrame(self.tab_graphics, fg_color="#0f172a")
        frame.pack(fill="both", expand=True, padx=40, pady=20, ipadx=20, ipady=20)

        ctk.CTkLabel(frame, text="Generador de Output (Instagram)", font=UI_FONT_BIG, text_color="#60a5fa").pack(pady=(10, 10))

        btns_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btns_frame.pack(pady=10)

        self.include_missions_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(btns_frame, text="Incluir Puntos de Misiones", variable=self.include_missions_var, font=UI_FONT).pack(side="left", padx=(0, 20))
        self.include_attendance_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(btns_frame, text="Incluir Puntos de Asistencia", variable=self.include_attendance_var, font=UI_FONT).pack(side="left", padx=(0, 20))
        ctk.CTkButton(btns_frame, text="Generar Preview Top 8", command=self.export_top8, font=UI_FONT).pack(side="left", padx=10)
        ctk.CTkButton(btns_frame, text="Generar Preview Tendencia", command=self.export_trend, font=UI_FONT).pack(side="left", padx=10)

        self.status_lbl = ctk.CTkLabel(frame, text="", text_color="#94a3b8", font=UI_FONT_SMALL)
        self.status_lbl.pack(pady=5)
        
        self.preview_label = tk.Label(frame, bg="#020617")
        self.preview_label.pack(pady=10, fill="both", expand=True)
        
        self.save_btn = ctk.CTkButton(frame, text="GUARDAR GRÁFICA", command=self.save_graphic, font=UI_FONT)
        self.save_btn.pack(pady=10)
        self.save_btn.pack_forget()

    def run_graphic_task(self, task_func, filename_prefix):
        def worker():
            self.after(0, lambda: self.status_lbl.configure(text="Generando preview, por favor espera...", text_color="#eab308"))
            try:
                img = task_func()
                self.current_graphic = img
                self.current_filename = filename_prefix
                
                preview = img.copy()
                preview.thumbnail((500, 500))
                
                self.after(0, self.show_preview, preview)
            except Exception as e:
                self.after(0, lambda: self.status_lbl.configure(text=f"Error: {e}", text_color="#ef4444"))
        threading.Thread(target=worker, daemon=True).start()

    def show_preview(self, preview_img):
        tk_img = ImageTk.PhotoImage(preview_img)
        self.preview_label.config(image=tk_img)
        self.preview_label.image = tk_img
        self.status_lbl.configure(text="Preview listo. Haz clic en Guardar Gráfica para exportar.", text_color="#22c55e")
        self.save_btn.pack(pady=10)

    def save_graphic(self):
        if not self.current_graphic: return
        filepath = filedialog.asksaveasfilename(
            initialfile=f"{self.current_filename}.png",
            defaultextension=".png",
            filetypes=[("PNG", "*.png")]
        )
        if filepath:
            self.current_graphic.save(filepath)
            self.status_lbl.configure(text=f"Guardado exitosamente en: {os.path.basename(filepath)}", text_color="#22c55e")
            self.save_btn.pack_forget()
            self.preview_label.config(image="")
            self.preview_label.image = None


    def export_top8(self):
        # Reload before exporting to ensure latest scores
        date_str = datetime.now().strftime('%d%m%y')
        fmt_str = self.manager.current_format.lower().replace(' ', '_')
        suffix = "" if self.include_attendance_var.get() else "_sin_asistencia"
        self.run_graphic_task(
            lambda: generate_top8_standings(
                self.manager,
                include_missions=self.include_missions_var.get(),
                include_attendance=self.include_attendance_var.get()
            ),
            f"{fmt_str}_top8{suffix}_{date_str}"
        )

    def export_trend(self):
        date_str = datetime.now().strftime('%d%m%y')
        fmt_str = self.manager.current_format.lower().replace(' ', '_')
        suffix = "" if self.include_attendance_var.get() else "_sin_asistencia"
        self.run_graphic_task(
            lambda: generate_trend_chart(
                self.manager,
                include_missions=self.include_missions_var.get(),
                include_attendance=self.include_attendance_var.get()
            ),
            f"{fmt_str}_trend{suffix}_{date_str}"
        )

