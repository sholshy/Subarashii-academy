import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk
import sqlite3
import json
import os
from datetime import datetime, timedelta

from database import get_connection, migrate_academy_schema
from academy.ranking_explainer import explain_player, format_explanation
from academy.season_manager import SeasonManager, _parse_custom_date
from academy.sync_manager import SyncManager
from calendar_manager import CalendarManager, to_display_date, parse_date_flexible
import custom_alerts

UI_FONT = ("Roboto", 13)
UI_FONT_SMALL = ("Roboto", 11)
UI_FONT_BIG = ("Orbitron Black", 24)

class AcademyUI:
    def __init__(self, master_frame, app):
        self.master_frame = master_frame
        self.app = app
        self.conn = get_connection()
        self.conn.row_factory = sqlite3.Row
        migrate_academy_schema(self.conn.cursor())
        self.conn.commit()
        
        self.season_manager = SeasonManager()
        self.sync_manager = SyncManager()
        self.calendar_manager = CalendarManager(self.conn)
        
        # Load Catalogs
        self.load_catalogs()
        
        self.build_ui()

    def load_catalogs(self):
        self.achievements_catalog = {}
        self.missions_catalog = {}
        
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
        ach_path = os.path.join(base_dir, "data", "achievements", "catalog.json")
        if os.path.exists(ach_path):
            with open(ach_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for a in data.get("achievements", []):
                    self.achievements_catalog[a["id"]] = a
                    
        msn_path = os.path.join(base_dir, "data", "missions", "catalog.json")
        if os.path.exists(msn_path):
            with open(msn_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for m in data.get("missions", []):
                    self.missions_catalog[m["id"]] = m

    def build_ui(self):
        # Top Bar
        top_bar = ctk.CTkFrame(self.master_frame, fg_color="transparent")
        top_bar.pack(fill="x", pady=(0, 10))
        
        ctk.CTkButton(top_bar, text="< Volver al Menú Principal", command=self.app.open_main_menu, font=UI_FONT_SMALL, width=150, fg_color="#ef4444", hover_color="#dc2626").pack(side="left", padx=(0, 20))
        ctk.CTkLabel(top_bar, text="Subarashii Duel Academy", font=UI_FONT_BIG, text_color="#60a5fa").pack(side="left")
        
        # Main Tabview: Leaderboard vs Season Configuration vs Calendar
        self.main_tabview = ctk.CTkTabview(self.master_frame)
        self.main_tabview.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.tab_leaderboard = self.main_tabview.add("🏆 Clasificación")
        self.tab_season = self.main_tabview.add("⚙️ Configuración de Temporada")
        self.tab_calendar = self.main_tabview.add("📅 Calendario y Torneos")
        
        # Main Content PanedWindow inside Tab 1
        self.paned = ttk.PanedWindow(self.tab_leaderboard, orient=tk.HORIZONTAL)
        self.paned.pack(fill="both", expand=True)
        
        # Left Panel (Leaderboard)
        self.left_panel = ctk.CTkFrame(self.paned, fg_color="#0f172a")
        self.paned.add(self.left_panel, weight=2)
        
        # Right Panel (Player Details)
        self.right_panel = ctk.CTkFrame(self.paned, fg_color="#1e293b")
        self.paned.add(self.right_panel, weight=1)
        
        self.build_leaderboard()
        self.build_details_panel()
        self.build_season_tab()
        self.build_calendar_tab()
        
        self.refresh_leaderboard()
        self.refresh_season_tab()
        self.refresh_calendar_tab()

    def build_leaderboard(self):
        cols = ("Rank", "Trend", "Jugador", "Dormitorio", "Nivel", "XP", "ELO", "Win Rate")
        self.tree = ttk.Treeview(self.left_panel, columns=cols, show="headings", selectmode="browse")
        
        self.tree.heading("Rank", text="#")
        self.tree.heading("Trend", text="")
        self.tree.heading("Jugador", text="Jugador")
        self.tree.heading("Dormitorio", text="Dormitorio")
        self.tree.heading("Nivel", text="Nivel")
        self.tree.heading("XP", text="XP")
        self.tree.heading("ELO", text="ELO (Rating)")
        self.tree.heading("Win Rate", text="Win Rate")
        
        self.tree.column("Rank", width=40, anchor="center")
        self.tree.column("Trend", width=30, anchor="center")
        self.tree.column("Jugador", width=160, anchor="w")
        self.tree.column("Dormitorio", width=140, anchor="center")
        self.tree.column("Nivel", width=50, anchor="center")
        self.tree.column("XP", width=60, anchor="center")
        self.tree.column("ELO", width=100, anchor="center")
        self.tree.column("Win Rate", width=80, anchor="center")
        
        vsb = ttk.Scrollbar(self.left_panel, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        
        self.tree.bind("<<TreeviewSelect>>", self.on_player_select)

    def build_details_panel(self):
        self.details_title = ctk.CTkLabel(self.right_panel, text="Perfil del Duelista", font=("Orbitron", 18), text_color="#38bdf8")
        self.details_title.pack(pady=(10, 5))
        
        self.details_stats = ctk.CTkLabel(self.right_panel, text="Selecciona un jugador", font=UI_FONT_SMALL, text_color="#94a3b8", justify="left")
        self.details_stats.pack(fill="x", padx=10, pady=5)
        
        # Tabs for Achievements and Missions
        self.tabview = ctk.CTkTabview(self.right_panel)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.tab_achievements = self.tabview.add("Logros")
        self.tab_missions = self.tabview.add("Misiones")
        
        # Achievements Listbox
        self.ach_list = tk.Listbox(self.tab_achievements, bg="#0f172a", fg="white", font=UI_FONT_SMALL, borderwidth=0, highlightthickness=0)
        self.ach_list.pack(fill="both", expand=True)
        
        # Missions Listbox
        self.msn_list = tk.Listbox(self.tab_missions, bg="#0f172a", fg="white", font=UI_FONT_SMALL, borderwidth=0, highlightthickness=0)
        self.msn_list.pack(fill="both", expand=True)

        # Explanation tab (por qué tiene este ranking)
        self.tab_explain = self.tabview.add("¿Por qué?")
        self.explain_box = ctk.CTkTextbox(self.tab_explain, fg_color="#0f172a", text_color="white",
                                          font=("Consolas", 11), wrap="word")
        self.explain_box.pack(fill="both", expand=True)
        self.explain_box.insert("1.0", "Selecciona un jugador para ver cómo se calculó su ranking.")
        self.explain_box.configure(state="disabled")

    def refresh_leaderboard(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
            
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT a.id, a.player_id, p.name, a.current_rating, a.highest_rating, 
                   a.dorm, a.xp, a.level, a.matches_played, a.wins, a.losses, a.previous_rank
            FROM academy_profiles a
            JOIN players p ON a.player_id = p.id
            WHERE a.format_name = 'GLOBAL'
            ORDER BY a.current_rating DESC, a.xp DESC
        """)
        
        players = cursor.fetchall()
        
        self.players_map = {}
        for idx, row in enumerate(players):
            rank = idx + 1
            mp = row['matches_played']
            wins = row['wins']
            wr = f"{(wins/mp*100):.1f}%" if mp > 0 else "0%"
            
            prev_rank = row['previous_rank']
            if not prev_rank or prev_rank == 0:
                trend_symbol = "▬"
                trend_tag = "eq"
            elif rank < prev_rank:
                trend_symbol = "▲"
                trend_tag = "up"
            elif rank > prev_rank:
                trend_symbol = "▼"
                trend_tag = "down"
            else:
                trend_symbol = "▬"
                trend_tag = "eq"
            
            # Map values
            self.players_map[row['id']] = dict(row)
            
            iid = self.tree.insert("", "end", values=(
                rank,
                trend_symbol,
                row['name'],
                row['dorm'],
                row['level'],
                row['xp'],
                row['current_rating'],
                wr
            ), tags=(trend_tag,))
            
            # Configure tag colors
            self.tree.tag_configure("up", foreground="#22c55e")
            self.tree.tag_configure("down", foreground="#ef4444")
            self.tree.tag_configure("eq", foreground="#eab308")
            
            # Sub-id to profile_id map for event click
            self.players_map[iid] = row['id']
            
    def on_player_select(self, event):
        selection = self.tree.selection()
        if not selection:
            return
            
        iid = selection[0]
        profile_id = self.players_map.get(iid)
        if not profile_id: return
        
        p = self.players_map[profile_id]
        
        mp = p['matches_played']
        wr = f"{(p['wins']/mp*100):.1f}%" if mp > 0 else "0%"
        
        stats_text = (
            f"Dormitorio: {p['dorm']}\n"
            f"Nivel: {p['level']} (XP: {p['xp']})\n"
            f"ELO Actual: {p['current_rating']}\n"
            f"ELO Máximo: {p['highest_rating']}\n\n"
            f"Partidas Jugadas: {mp}\n"
            f"Victorias/Derrotas: {p['wins']} - {p['losses']} ({wr})\n"
        )
        
        self.details_title.configure(text=p['name'])
        self.details_stats.configure(text=stats_text)
        
        self.load_player_achievements(profile_id)
        self.load_player_missions(profile_id)
        self.load_player_explanation(p['player_id'])

    def load_player_explanation(self, player_id):
        """Pestaña '¿Por qué?': desglose de duelos, XP por origen, desempate y confiabilidad."""
        try:
            text = format_explanation(explain_player(self.conn.cursor(), player_id))
        except Exception as e:
            text = f"No se pudo generar la explicación: {e}"
        self.explain_box.configure(state="normal")
        self.explain_box.delete("1.0", "end")
        self.explain_box.insert("1.0", text)
        self.explain_box.configure(state="disabled")

    def load_player_achievements(self, profile_id):
        self.ach_list.delete(0, tk.END)
        
        cursor = self.conn.cursor()
        cursor.execute("SELECT achievement_id, unlocked_at FROM academy_achievements WHERE academy_profile_id=?", (profile_id,))
        unlocked = {r['achievement_id']: r['unlocked_at'] for r in cursor.fetchall()}
        
        if not unlocked:
            self.ach_list.insert(tk.END, "Ningún logro desbloqueado aún.")
            return
            
        self.ach_list.insert(tk.END, f"--- {len(unlocked)} LOGROS DESBLOQUEADOS ---")
        
        for aid, date_str in unlocked.items():
            cat = self.achievements_catalog.get(aid)
            name = cat["name"] if cat else aid
            desc = cat["description"] if cat else ""
            date_short = date_str[:10] if date_str else ""
            self.ach_list.insert(tk.END, f"⭐ {name} ({date_short})")
            if desc:
                self.ach_list.insert(tk.END, f"   └ {desc}")
            self.ach_list.insert(tk.END, "")

    def load_player_missions(self, profile_id):
        self.msn_list.delete(0, tk.END)
        
        cursor = self.conn.cursor()
        cursor.execute("SELECT mission_id, progress, completed FROM academy_missions WHERE academy_profile_id=?", (profile_id,))
        missions = cursor.fetchall()
        
        if not missions:
            self.msn_list.insert(tk.END, "Sin misiones asignadas.")
            return
            
        for r in missions:
            mid = r['mission_id']
            prog = r['progress']
            comp = r['completed']
            
            cat = self.missions_catalog.get(mid)
            name = cat["name"] if cat else mid
            target = cat["target_value"] if cat else 1
            
            status = "✅ Completada" if comp else f"⏳ {prog}/{target}"
            
            self.msn_list.insert(tk.END, f"📜 {name}")
            self.msn_list.insert(tk.END, f"   └ Progreso: {status}")
            self.msn_list.insert(tk.END, "")

    # =========================================================================
    # PESTAÑA: CONFIGURACIÓN Y GESTIÓN DE TEMPORADA
    # =========================================================================
    def build_season_tab(self):
        self.season_scroll = ctk.CTkScrollableFrame(self.tab_season, fg_color="transparent")
        self.season_scroll.pack(fill="both", expand=True, padx=10, pady=10)

        # -----------------------------------------------------------------
        # 1. TARJETA DE ESTADO Y MÉTRICAS CALCULADAS
        # -----------------------------------------------------------------
        status_card = ctk.CTkFrame(self.season_scroll, fg_color="#1e293b", corner_radius=10)
        status_card.pack(fill="x", pady=(0, 15), padx=5, ipady=8)

        header_top = ctk.CTkFrame(status_card, fg_color="transparent")
        header_top.pack(fill="x", padx=15, pady=(10, 5))

        self.season_status_title = ctk.CTkLabel(header_top, text="Temporada Activa", font=("Orbitron", 18), text_color="#38bdf8")
        self.season_status_title.pack(side="left")

        self.season_badge = ctk.CTkLabel(header_top, text="🟢 EN CURSO", font=("Roboto", 11, "bold"),
                                          text_color="#22c55e", fg_color="#14532d", corner_radius=6, padx=10, pady=3)
        self.season_badge.pack(side="right")

        self.season_dates_lbl = ctk.CTkLabel(status_card, text="", font=UI_FONT_SMALL, text_color="#94a3b8")
        self.season_dates_lbl.pack(anchor="w", padx=15, pady=(0, 10))

        # Cuadrícula de 4 Métricas Calculadas
        metrics_grid = ctk.CTkFrame(status_card, fg_color="transparent")
        metrics_grid.pack(fill="x", padx=15, pady=5)
        metrics_grid.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # Métrica 1: Días transcurridos
        m1 = ctk.CTkFrame(metrics_grid, fg_color="#0f172a", corner_radius=8)
        m1.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        ctk.CTkLabel(m1, text="⏱️ TIEMPO TRANSCURRIDO", font=("Roboto", 10, "bold"), text_color="#94a3b8").pack(pady=(10, 2))
        self.metric_days_val = ctk.CTkLabel(m1, text="-", font=("Orbitron", 18), text_color="#60a5fa")
        self.metric_days_val.pack()
        self.metric_days_sub = ctk.CTkLabel(m1, text="-", font=UI_FONT_SMALL, text_color="#64748b")
        self.metric_days_sub.pack(pady=(0, 10))

        # Métrica 2: Torneos jugados
        m2 = ctk.CTkFrame(metrics_grid, fg_color="#0f172a", corner_radius=8)
        m2.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
        ctk.CTkLabel(m2, text="🏆 TORNEOS JUGADOS", font=("Roboto", 10, "bold"), text_color="#94a3b8").pack(pady=(10, 2))
        self.metric_tourneys_val = ctk.CTkLabel(m2, text="-", font=("Orbitron", 18), text_color="#34d399")
        self.metric_tourneys_val.pack()
        self.metric_tourneys_sub = ctk.CTkLabel(m2, text="-", font=UI_FONT_SMALL, text_color="#64748b")
        self.metric_tourneys_sub.pack(pady=(0, 10))

        # Métrica 3: Partidas disputadas
        m3 = ctk.CTkFrame(metrics_grid, fg_color="#0f172a", corner_radius=8)
        m3.grid(row=0, column=2, padx=5, pady=5, sticky="nsew")
        ctk.CTkLabel(m3, text="⚔️ DUELOS DISPUTADOS", font=("Roboto", 10, "bold"), text_color="#94a3b8").pack(pady=(10, 2))
        self.metric_matches_val = ctk.CTkLabel(m3, text="-", font=("Orbitron", 18), text_color="#f472b6")
        self.metric_matches_val.pack()
        self.metric_matches_sub = ctk.CTkLabel(m3, text="Partidas válidas", font=UI_FONT_SMALL, text_color="#64748b")
        self.metric_matches_sub.pack(pady=(0, 10))

        # Métrica 4: Duelistas activos
        m4 = ctk.CTkFrame(metrics_grid, fg_color="#0f172a", corner_radius=8)
        m4.grid(row=0, column=3, padx=5, pady=5, sticky="nsew")
        ctk.CTkLabel(m4, text="👥 DUELISTAS ACTIVOS", font=("Roboto", 10, "bold"), text_color="#94a3b8").pack(pady=(10, 2))
        self.metric_players_val = ctk.CTkLabel(m4, text="-", font=("Orbitron", 18), text_color="#fbbf24")
        self.metric_players_val.pack()
        self.metric_players_sub = ctk.CTkLabel(m4, text="En competencia", font=UI_FONT_SMALL, text_color="#64748b")
        self.metric_players_sub.pack(pady=(0, 10))

        # Banner de Estado del Criterio de Cierre
        self.season_progress_banner = ctk.CTkLabel(status_card, text="", font=UI_FONT, fg_color="#0f172a",
                                                   text_color="#38bdf8", corner_radius=8, pady=8)
        self.season_progress_banner.pack(fill="x", padx=15, pady=(10, 5))

        # -----------------------------------------------------------------
        # 2. TARJETA DE CONFIGURACIÓN DEL CICLO DE TEMPORADA
        # -----------------------------------------------------------------
        config_card = ctk.CTkFrame(self.season_scroll, fg_color="#1e293b", corner_radius=10)
        config_card.pack(fill="x", pady=(0, 15), padx=5, ipady=10)

        ctk.CTkLabel(config_card, text="⚙️ Configurar Inicio y Criterio de Cierre de Temporada",
                     font=("Orbitron", 15), text_color="#38bdf8").pack(anchor="w", padx=15, pady=(10, 15))

        form_frame = ctk.CTkFrame(config_card, fg_color="transparent")
        form_frame.pack(fill="x", padx=15)

        # Fila 1: Nombre de la temporada y Fecha de inicio
        row1 = ctk.CTkFrame(form_frame, fg_color="transparent")
        row1.pack(fill="x", pady=5)
        
        ctk.CTkLabel(row1, text="Nombre de la Temporada:", font=UI_FONT, width=190, anchor="w").pack(side="left")
        self.season_name_entry = ctk.CTkEntry(row1, font=UI_FONT, width=220)
        self.season_name_entry.pack(side="left", padx=(0, 30))

        ctk.CTkLabel(row1, text="Fecha de Inicio:", font=UI_FONT, width=120, anchor="w").pack(side="left")
        self.season_start_entry = ctk.CTkEntry(row1, font=UI_FONT, width=140)
        self.season_start_entry.pack(side="left")

        # Fila 2: Selector de Criterio de Cierre
        row2 = ctk.CTkFrame(form_frame, fg_color="transparent")
        row2.pack(fill="x", pady=(15, 5))

        ctk.CTkLabel(row2, text="Modo de Cierre:", font=UI_FONT, width=190, anchor="w").pack(side="left")
        self.close_type_var = ctk.StringVar(value="DATE")
        
        rb_date = ctk.CTkRadioButton(row2, text="📅 Por Fecha Límite / Meses",
                                     variable=self.close_type_var, value="DATE",
                                     command=self.on_close_type_changed, font=UI_FONT)
        rb_date.pack(side="left", padx=(0, 25))

        rb_tourneys = ctk.CTkRadioButton(row2, text="🏆 Por Cantidad de Torneos",
                                         variable=self.close_type_var, value="TOURNAMENT_COUNT",
                                         command=self.on_close_type_changed, font=UI_FONT)
        rb_tourneys.pack(side="left")

        # Fila 3: Entrada de Meta y Presets
        self.target_frame = ctk.CTkFrame(form_frame, fg_color="#0f172a", corner_radius=8)
        self.target_frame.pack(fill="x", pady=10, ipady=8, ipadx=10)

        target_input_row = ctk.CTkFrame(self.target_frame, fg_color="transparent")
        target_input_row.pack(fill="x", padx=10, pady=(5, 5))

        self.target_label = ctk.CTkLabel(target_input_row, text="Fecha límite (DD-MM-AAAA):", font=UI_FONT, width=220, anchor="w")
        self.target_label.pack(side="left")

        self.target_entry = ctk.CTkEntry(target_input_row, font=UI_FONT, width=180)
        self.target_entry.pack(side="left", padx=(0, 15))
        self.target_entry.bind("<KeyRelease>", lambda e: self.update_target_calc_feedback())

        # Presets para Fechas
        self.date_presets_frame = ctk.CTkFrame(self.target_frame, fg_color="transparent")
        self.date_presets_frame.pack(fill="x", padx=10, pady=(0, 5))
        ctk.CTkLabel(self.date_presets_frame, text="Duración sugerida:", font=UI_FONT_SMALL, text_color="#94a3b8").pack(side="left", padx=(0, 10))
        ctk.CTkButton(self.date_presets_frame, text="+1 Mes", width=70, font=UI_FONT_SMALL, fg_color="#334155", hover_color="#475569",
                      command=lambda: self.apply_date_preset(30)).pack(side="left", padx=3)
        ctk.CTkButton(self.date_presets_frame, text="+2 Meses", width=70, font=UI_FONT_SMALL, fg_color="#334155", hover_color="#475569",
                      command=lambda: self.apply_date_preset(60)).pack(side="left", padx=3)
        ctk.CTkButton(self.date_presets_frame, text="+3 Meses", width=70, font=UI_FONT_SMALL, fg_color="#334155", hover_color="#475569",
                      command=lambda: self.apply_date_preset(90)).pack(side="left", padx=3)
        ctk.CTkButton(self.date_presets_frame, text="+6 Meses", width=70, font=UI_FONT_SMALL, fg_color="#334155", hover_color="#475569",
                      command=lambda: self.apply_date_preset(180)).pack(side="left", padx=3)

        # Presets para Torneos
        self.tourney_presets_frame = ctk.CTkFrame(self.target_frame, fg_color="transparent")
        ctk.CTkLabel(self.tourney_presets_frame, text="Metas sugeridas:", font=UI_FONT_SMALL, text_color="#94a3b8").pack(side="left", padx=(0, 10))
        ctk.CTkButton(self.tourney_presets_frame, text="10 torneos", width=85, font=UI_FONT_SMALL, fg_color="#334155", hover_color="#475569",
                      command=lambda: self.apply_tourney_preset(10)).pack(side="left", padx=3)
        ctk.CTkButton(self.tourney_presets_frame, text="15 torneos", width=85, font=UI_FONT_SMALL, fg_color="#334155", hover_color="#475569",
                      command=lambda: self.apply_tourney_preset(15)).pack(side="left", padx=3)
        ctk.CTkButton(self.tourney_presets_frame, text="20 torneos", width=85, font=UI_FONT_SMALL, fg_color="#334155", hover_color="#475569",
                      command=lambda: self.apply_tourney_preset(20)).pack(side="left", padx=3)
        ctk.CTkButton(self.tourney_presets_frame, text="25 torneos", width=85, font=UI_FONT_SMALL, fg_color="#334155", hover_color="#475569",
                      command=lambda: self.apply_tourney_preset(25)).pack(side="left", padx=3)

        # Cálculo dinámico en tiempo real
        self.target_calc_lbl = ctk.CTkLabel(self.target_frame, text="", font=UI_FONT_SMALL, text_color="#94a3b8", justify="left")
        self.target_calc_lbl.pack(anchor="w", padx=10, pady=(5, 0))

        # Botones de acción de configuración
        actions_row = ctk.CTkFrame(config_card, fg_color="transparent")
        actions_row.pack(fill="x", padx=15, pady=(15, 5))

        ctk.CTkButton(actions_row, text="💾 Guardar y Sincronizar Reglas", command=self.save_season_config,
                      font=UI_FONT, fg_color="#2563eb", hover_color="#1d4ed8", width=220, height=36).pack(side="left", padx=(0, 15))

        ctk.CTkButton(actions_row, text="🔄 Recalcular Métricas", command=self.refresh_season_tab,
                      font=UI_FONT, fg_color="#475569", hover_color="#334155", width=170, height=36).pack(side="left")

        # -----------------------------------------------------------------
        # 3. TARJETA DE CIERRE DE TEMPORADA
        # -----------------------------------------------------------------
        close_card = ctk.CTkFrame(self.season_scroll, fg_color="#0f172a", border_width=1, border_color="#eab308", corner_radius=10)
        close_card.pack(fill="x", pady=(0, 15), padx=5, ipady=12)

        ctk.CTkLabel(close_card, text="🏁 Finalizar y Archivar Temporada", font=("Orbitron", 15), text_color="#f59e0b").pack(anchor="w", padx=15, pady=(10, 5))

        close_info = (
            "Al cerrar la temporada:\n"
            "• Se congelará de forma definitiva la posición, rating ELO, nivel y dormitorios de los duelistas en el histórico.\n"
            "• La temporada actual quedará registrada como CERRADA con su conteo total de torneos y duelistas.\n"
            "• Se iniciará de forma automática la siguiente temporada activa.\n"
            "• Se publicará un snapshot de sincronización para que la plataforma web refleje el nuevo ciclo al instante."
        )
        ctk.CTkLabel(close_card, text=close_info, font=UI_FONT_SMALL, text_color="#cbd5e1", justify="left").pack(anchor="w", padx=15, pady=(0, 12))

        close_btn_row = ctk.CTkFrame(close_card, fg_color="transparent")
        close_btn_row.pack(fill="x", padx=15)

        ctk.CTkButton(close_btn_row, text="🏆 CERRAR TEMPORADA ACTUAL Y COMENZAR SIGUIENTE",
                      command=self.close_current_season, font=("Roboto", 13, "bold"),
                      fg_color="#f59e0b", hover_color="#d97706", text_color="#0f172a", height=42).pack(side="left")

        self.btn_revert_season = ctk.CTkButton(
            close_btn_row, text="↩️ Revertir Cierre de Temporada",
            command=self.revert_last_season_close, font=UI_FONT_SMALL,
            fg_color="#334155", hover_color="#475569", text_color="#f8fafc", height=42
        )
        self.btn_revert_season.pack(side="left", padx=(12, 0))

        # -----------------------------------------------------------------
        # 4. TARJETA DE HISTORIAL DE TEMPORADAS
        # -----------------------------------------------------------------
        history_card = ctk.CTkFrame(self.season_scroll, fg_color="#1e293b", corner_radius=10)
        history_card.pack(fill="x", pady=(0, 15), padx=5, ipady=10)

        ctk.CTkLabel(history_card, text="📜 Historial de Temporadas", font=("Orbitron", 15), text_color="#38bdf8").pack(anchor="w", padx=15, pady=(10, 10))

        hist_cols = ("num", "name", "start", "end", "tourneys", "players", "status")
        self.history_tree = ttk.Treeview(history_card, columns=hist_cols, show="headings", height=5, selectmode="browse")

        self.history_tree.heading("num", text="N°")
        self.history_tree.heading("name", text="Temporada")
        self.history_tree.heading("start", text="Inicio")
        self.history_tree.heading("end", text="Fin")
        self.history_tree.heading("tourneys", text="Torneos")
        self.history_tree.heading("players", text="Duelistas")
        self.history_tree.heading("status", text="Estado")

        self.history_tree.column("num", width=40, anchor="center")
        self.history_tree.column("name", width=160, anchor="w")
        self.history_tree.column("start", width=100, anchor="center")
        self.history_tree.column("end", width=100, anchor="center")
        self.history_tree.column("tourneys", width=90, anchor="center")
        self.history_tree.column("players", width=90, anchor="center")
        self.history_tree.column("status", width=100, anchor="center")

        self.history_tree.pack(fill="x", padx=15, pady=(0, 10))

    def on_close_type_changed(self):
        close_type = self.close_type_var.get()
        if close_type == "TOURNAMENT_COUNT":
            self.target_label.configure(text="Meta de torneos jugados:")
            self.date_presets_frame.pack_forget()
            self.tourney_presets_frame.pack(fill="x", padx=10, pady=(0, 5))
            cur = self.target_entry.get().strip()
            if not cur.isdigit():
                self.target_entry.delete(0, tk.END)
                self.target_entry.insert(0, "15")
        else:
            self.target_label.configure(text="Fecha límite (DD-MM-AAAA):")
            self.tourney_presets_frame.pack_forget()
            self.date_presets_frame.pack(fill="x", padx=10, pady=(0, 5))
            cur = self.target_entry.get().strip()
            if cur.isdigit() or not cur:
                self.target_entry.delete(0, tk.END)
                self.target_entry.insert(0, (datetime.now() + timedelta(days=30)).strftime("%d-%m-%Y"))
        self.update_target_calc_feedback()

    def apply_date_preset(self, days):
        target_dt = datetime.now() + timedelta(days=days)
        self.target_entry.delete(0, tk.END)
        self.target_entry.insert(0, target_dt.strftime("%d-%m-%Y"))
        self.update_target_calc_feedback()

    def apply_tourney_preset(self, count):
        self.target_entry.delete(0, tk.END)
        self.target_entry.insert(0, str(count))
        self.update_target_calc_feedback()

    def update_target_calc_feedback(self):
        close_type = self.close_type_var.get()
        val = self.target_entry.get().strip()
        metrics = getattr(self, '_current_metrics', None)
        if not metrics:
            return

        if close_type == "TOURNAMENT_COUNT":
            if val.isdigit():
                target_cnt = int(val)
                played = metrics['tournaments_count']
                diff = target_cnt - played
                if diff > 0:
                    text = f"📊 Meta: {target_cnt} torneos. Se han jugado {played} hasta ahora. Faltan {diff} torneo(s) para alcanzar la meta."
                    color = "#38bdf8"
                elif diff == 0:
                    text = f"✅ Meta alcanzada: Se han completado los {target_cnt} torneos programados. ¡Lista para cerrar!"
                    color = "#22c55e"
                else:
                    text = f"⚠️ Meta superada: {played} torneos jugados (la meta era {target_cnt}). ¡Lista para cerrar!"
                    color = "#f59e0b"
            else:
                text = "Ingresa un número entero de torneos (ej: 10, 15)."
                color = "#94a3b8"
        else:
            dt = _parse_custom_date(val)
            if dt:
                now = datetime.now()
                days_left = (dt - now).days
                if days_left > 0:
                    months = round(days_left / 30.4, 1)
                    text = f"📅 Cierre programado: {val} (quedan {days_left} días / ~{months} meses)."
                    color = "#38bdf8"
                elif days_left == 0:
                    text = f"🔔 Cierre programado para HOY ({val}). ¡Lista para cerrar!"
                    color = "#22c55e"
                else:
                    text = f"⚠️ La fecha ({val}) venció hace {abs(days_left)} días. ¡Lista para cerrar!"
                    color = "#f59e0b"
            else:
                text = "Ingresa la fecha en formato DD-MM-AAAA (ej: 31-12-2026)."
                color = "#94a3b8"

        self.target_calc_lbl.configure(text=text, text_color=color)

    def refresh_season_tab(self):
        cursor = self.conn.cursor()
        metrics = self.season_manager.get_season_metrics(cursor)
        self._current_metrics = metrics
        season = metrics['season']

        self.season_status_title.configure(text=f"Temporada Activa: {season['name']}")
        self.season_dates_lbl.configure(
            text=f"ID: {season['id']}   |   Fecha de Inicio: {season['start_date']}   |   Estado: {season['status']}"
        )

        # Actualizar valores de tarjetas
        days_el = metrics['days_elapsed']
        months_el = round(days_el / 30.4, 1)
        self.metric_days_val.configure(text=f"{days_el} días")
        self.metric_days_sub.configure(text=f"(~{months_el} meses desde el inicio)")

        t_cnt = metrics['tournaments_count']
        self.metric_tourneys_val.configure(text=f"{t_cnt} torneos")
        self.metric_tourneys_sub.configure(
            text=f"1er: {metrics['first_tournament_date']} | Último: {metrics['last_tournament_date']}"
        )

        self.metric_matches_val.configure(text=f"{metrics['total_matches']} partidas")
        self.metric_players_val.configure(text=f"{metrics['active_players']} duelistas")

        # Banner de progreso
        rule_name = "Por Cantidad de Torneos" if season.get('close_type') == 'TOURNAMENT_COUNT' else "Por Fecha"
        t_val = season.get('target_value') or "Sin meta fija"
        if metrics['is_ready_to_close']:
            banner_txt = f"🔔 ¡CONDICIÓN DE CIERRE ALCANZADA! [{rule_name}: {t_val}] • {metrics['progress_text']} • Ya puedes finalizar la temporada."
            self.season_progress_banner.configure(text=banner_txt, fg_color="#14532d", text_color="#4ade80")
        else:
            banner_txt = f"📌 Regla Activa: [{rule_name}: {t_val}] • {metrics['progress_text'] or 'Sin fecha/meta establecida'}"
            self.season_progress_banner.configure(text=banner_txt, fg_color="#0f172a", text_color="#38bdf8")

        # Rellenar campos de formulario
        self.season_name_entry.delete(0, tk.END)
        self.season_name_entry.insert(0, season['name'])

        self.season_start_entry.delete(0, tk.END)
        self.season_start_entry.insert(0, season['start_date'])

        c_type = season.get('close_type') or 'DATE'
        self.close_type_var.set(c_type)

        self.target_entry.delete(0, tk.END)
        if season.get('target_value'):
            self.target_entry.insert(0, str(season['target_value']))

        self.on_close_type_changed()
        self.load_seasons_history()

        # Actualizar estado de botón de revertir
        if hasattr(self, 'btn_revert_season'):
            can_rev, prev_s = self.season_manager.can_revert_last_season(cursor)
            if can_rev and prev_s:
                self.btn_revert_season.configure(
                    state="normal",
                    text=f"↩️ Reabrir {prev_s['name']}",
                    fg_color="#475569",
                    hover_color="#334155"
                )
            else:
                self.btn_revert_season.configure(
                    state="disabled",
                    text="↩️ Revertir Cierre (No disponible)",
                    fg_color="#1e293b"
                )

    def save_season_config(self):
        name = self.season_name_entry.get().strip()
        start_date = self.season_start_entry.get().strip()
        close_type = self.close_type_var.get()
        target_val = self.target_entry.get().strip()

        if not name:
            messagebox.showwarning("Atención", "Debes ingresar un nombre para la temporada.")
            return

        if not start_date:
            messagebox.showwarning("Atención", "Debes ingresar una fecha de inicio.")
            return

        if close_type == "TOURNAMENT_COUNT" and target_val:
            if not target_val.isdigit() or int(target_val) <= 0:
                messagebox.showwarning("Atención", "La meta de torneos debe ser un número entero positivo.")
                return

        if close_type == "DATE" and target_val:
            if not _parse_custom_date(target_val):
                messagebox.showwarning("Atención", "La fecha límite debe ser una fecha válida (ej: DD-MM-AAAA).")
                return

        cursor = self.conn.cursor()
        self.season_manager.update_season_config(cursor, name, start_date, close_type, target_val or None)
        self.conn.commit()

        # Generar snapshot y sincronizar
        try:
            self.sync_manager.generate_snapshot_and_manifest(self.conn)
            self.sync_manager.publish()
        except Exception as e:
            print(f"[AcademyUI] Error al sincronizar: {e}")

        self.refresh_season_tab()
        custom_alerts.showinfo("Configuración Guardada",
                               f"Se guardaron correctamente las reglas de la '{name}'.\nLos datos fueron sincronizados con la web pública.")

    def close_current_season(self):
        metrics = getattr(self, '_current_metrics', None)
        if not metrics:
            return
        season = metrics['season']
        
        confirm = custom_alerts.askyesno(
            "Confirmar Cierre de Temporada",
            f"¿Estás seguro de cerrar la '{season['name']}'?\n\n"
            f"• Se archivarán las estadísticas de {metrics['active_players']} duelistas.\n"
            f"• Torneos jugados: {metrics['tournaments_count']}.\n"
            f"• Partidas disputadas: {metrics['total_matches']}.\n\n"
            f"Se iniciará automáticamente la siguiente temporada y se sincronizará con la web pública.\n\n"
            f"¿Deseas continuar?"
        )
        if not confirm:
            return

        cursor = self.conn.cursor()
        closed, new_s = self.season_manager.close_season(cursor)
        self.conn.commit()

        # Sincronizar
        try:
            self.sync_manager.generate_snapshot_and_manifest(self.conn)
            self.sync_manager.publish()
        except Exception as e:
            print(f"[AcademyUI] Error sincronizando cierre: {e}")

        self.refresh_season_tab()
        self.refresh_leaderboard()

        new_name = new_s['name'] if new_s else "Nueva Temporada"
        custom_alerts.showinfo("Temporada Cerrada",
                               f"La '{closed['name']}' ha sido cerrada exitosamente.\n"
                               f"Se ha iniciado la '{new_name}'.\n"
                               f"El historial y la web pública se han actualizado.")

    def revert_last_season_close(self):
        cursor = self.conn.cursor()
        can_rev, prev_s = self.season_manager.can_revert_last_season(cursor)
        if not can_rev or not prev_s:
            custom_alerts.showwarning("Atención", "No hay ninguna temporada anterior cerrada disponible para revertir.")
            return

        confirm = custom_alerts.askyesno(
            "Revertir Cierre de Temporada",
            f"¿Deseas revertir el cierre de la '{prev_s['name']}'?\n\n"
            f"• Se cancelará la temporada actual recién creada.\n"
            f"• La '{prev_s['name']}' volverá a quedar como ACTIVA.\n"
            f"• Se limpiará su archivo histórico temporal.\n"
            f"• La web pública volverá a mostrar la '{prev_s['name']}'.\n\n"
            f"¿Estás seguro de continuar?"
        )
        if not confirm:
            return

        try:
            reopened = self.season_manager.revert_last_season_close(cursor)
            self.conn.commit()

            try:
                self.sync_manager.generate_snapshot_and_manifest(self.conn)
                self.sync_manager.publish()
            except Exception as e:
                print(f"[AcademyUI] Error al sincronizar tras revertir: {e}")

            self.refresh_season_tab()
            self.refresh_leaderboard()
            custom_alerts.showinfo(
                "Cierre Revertido",
                f"¡La '{reopened['name']}' ha sido reabierta exitosamente y vuelve a estar ACTIVA!\n"
                f"La web pública y el sistema han sido sincronizados."
            )
        except Exception as e:
            custom_alerts.showerror("Error", f"No se pudo revertir el cierre de la temporada:\n{e}")

    def load_seasons_history(self):
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)

        cursor = self.conn.cursor()
        history = self.season_manager.get_all_seasons_history(cursor)
        for s in history:
            status_text = "🟢 ACTIVA" if s['status'] == 'ACTIVE' else "🏁 CERRADA"
            end_d = s['end_date'] if s['end_date'] else "-"
            t_cnt = s['tournaments_count'] if s['tournaments_count'] is not None else "-"
            p_cnt = s['archived_players'] if s['archived_players'] > 0 else (s['players_count'] or "-")

            self.history_tree.insert("", "end", values=(
                f"#{s['number']}",
                s['name'],
                s['start_date'],
                end_d,
                f"{t_cnt}",
                f"{p_cnt}",
                status_text
            ))

    # =========================================================================
    # PESTAÑA: CALENDARIO Y PROGRAMACIÓN DE TORNEOS / LIGAS
    # =========================================================================
    def build_calendar_tab(self):
        cal_paned = ttk.PanedWindow(self.tab_calendar, orient=tk.HORIZONTAL)
        cal_paned.pack(fill="both", expand=True, padx=5, pady=5)

        # -------------------------------------------------------------
        # PANEL IZQUIERDO: AGENDA DE EVENTOS PROGRAMADOS
        # -------------------------------------------------------------
        left_cal = ctk.CTkFrame(cal_paned, fg_color="#0f172a")
        cal_paned.add(left_cal, weight=3)

        top_bar = ctk.CTkFrame(left_cal, fg_color="transparent")
        top_bar.pack(fill="x", padx=15, pady=(15, 10))

        ctk.CTkLabel(top_bar, text="📅 Agenda de Torneos Oficiales", font=("Orbitron", 16), text_color="#38bdf8").pack(side="left")

        # Filtros
        filters_bar = ctk.CTkFrame(left_cal, fg_color="transparent")
        filters_bar.pack(fill="x", padx=15, pady=(0, 10))

        ctk.CTkLabel(filters_bar, text="Formato:", font=UI_FONT_SMALL, text_color="#94a3b8").pack(side="left", padx=(0, 5))
        self.cal_filter_format = ctk.StringVar(value="TODOS")
        cb_fmt = ctk.CTkComboBox(filters_bar, variable=self.cal_filter_format,
                                 values=["TODOS", "EDISON", "GOAT", "TCG", "Tengu", "H.A.T.", "Speed Duel"],
                                 width=120, font=UI_FONT_SMALL, command=lambda v: self.refresh_calendar_tab())
        cb_fmt.pack(side="left", padx=(0, 15))

        self.cal_show_finished = ctk.BooleanVar(value=True)
        chk_fin = ctk.CTkCheckBox(filters_bar, text="Mostrar finalizados", variable=self.cal_show_finished,
                                  font=UI_FONT_SMALL, command=self.refresh_calendar_tab)
        chk_fin.pack(side="left", padx=(0, 15))

        ctk.CTkButton(filters_bar, text="🔄 Refrescar", font=UI_FONT_SMALL, width=90, fg_color="#334155",
                      hover_color="#475569", command=self.refresh_calendar_tab).pack(side="left")

        # Treeview de torneos programados
        cols = ("Fecha", "Hora", "Evento", "Formato", "Modo", "Premio", "Estado")
        tree_container = ctk.CTkFrame(left_cal, fg_color="transparent")
        tree_container.pack(fill="both", expand=True, padx=15, pady=5)

        self.cal_tree = ttk.Treeview(tree_container, columns=cols, show="headings", selectmode="browse")

        self.cal_tree.heading("Fecha", text="Fecha")
        self.cal_tree.heading("Hora", text="Hora")
        self.cal_tree.heading("Evento", text="Evento")
        self.cal_tree.heading("Formato", text="Formato")
        self.cal_tree.heading("Modo", text="Modo")
        self.cal_tree.heading("Premio", text="Premio")
        self.cal_tree.heading("Estado", text="Estado")

        self.cal_tree.column("Fecha", width=140, anchor="center")
        self.cal_tree.column("Hora", width=60, anchor="center")
        self.cal_tree.column("Evento", width=180, anchor="w")
        self.cal_tree.column("Formato", width=80, anchor="center")
        self.cal_tree.column("Modo", width=70, anchor="center")
        self.cal_tree.column("Premio", width=160, anchor="w")
        self.cal_tree.column("Estado", width=95, anchor="center")

        tree_scroll = ttk.Scrollbar(tree_container, orient="vertical", command=self.cal_tree.yview)
        self.cal_tree.configure(yscrollcommand=tree_scroll.set)

        self.cal_tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

        # Barra de botones de acción
        cal_actions = ctk.CTkFrame(left_cal, fg_color="transparent")
        cal_actions.pack(fill="x", padx=15, pady=15)

        ctk.CTkButton(cal_actions, text="⚡ Iniciar en Gestor de Torneos", font=("Roboto", 12, "bold"),
                      fg_color="#22c55e", hover_color="#16a34a", text_color="#0f172a",
                      command=self.on_start_scheduled_tournament, height=36).pack(side="left", padx=(0, 10))

        ctk.CTkButton(cal_actions, text="🗑️ Cancelar / Eliminar", font=UI_FONT_SMALL,
                      fg_color="#ef4444", hover_color="#dc2626",
                      command=self.on_delete_scheduled_tournament, height=36).pack(side="left", padx=(0, 10))

        ctk.CTkButton(cal_actions, text="🌐 Sincronizar con Web", font=UI_FONT_SMALL,
                      fg_color="#3b82f6", hover_color="#2563eb",
                      command=self.on_sync_calendar_web, height=36).pack(side="right")

        # -------------------------------------------------------------
        # PANEL DERECHO: FORMULARIOS DE PROGRAMACIÓN
        # -------------------------------------------------------------
        right_cal = ctk.CTkFrame(cal_paned, fg_color="#1e293b")
        cal_paned.add(right_cal, weight=2)

        ctk.CTkLabel(right_cal, text="✍️ Programar Torneos y Ligas", font=("Orbitron", 15), text_color="#38bdf8").pack(padx=15, pady=(15, 5), anchor="w")

        self.prog_tabs = ctk.CTkTabview(right_cal)
        self.prog_tabs.pack(fill="both", expand=True, padx=10, pady=5)

        tab_single = self.prog_tabs.add("➕ Torneo Individual")
        tab_league = self.prog_tabs.add("🏆 Ciclo de Liga (Domingos)")

        # Formulario Torneo Individual
        f_single = ctk.CTkScrollableFrame(tab_single, fg_color="transparent")
        f_single.pack(fill="both", expand=True)

        ctk.CTkLabel(f_single, text="Título del Evento:", font=UI_FONT_SMALL, text_color="#94a3b8").pack(anchor="w", pady=(5, 2))
        self.single_title_entry = ctk.CTkEntry(f_single, font=UI_FONT, placeholder_text="ej. Torneo Edison Dominical")
        self.single_title_entry.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(f_single, text="Fecha (DD-MM-AAAA):", font=UI_FONT_SMALL, text_color="#94a3b8").pack(anchor="w", pady=(0, 2))
        self.single_date_entry = ctk.CTkEntry(f_single, font=UI_FONT)
        self.single_date_entry.insert(0, datetime.now().strftime("%d-%m-%Y"))
        self.single_date_entry.pack(fill="x", pady=(0, 5))

        # Botones rápidos de fecha
        quick_dates = ctk.CTkFrame(f_single, fg_color="transparent")
        quick_dates.pack(fill="x", pady=(0, 10))
        ctk.CTkButton(quick_dates, text="Hoy", width=60, font=UI_FONT_SMALL, fg_color="#334155",
                      command=lambda: self._set_quick_date(self.single_date_entry, "today")).pack(side="left", padx=2)
        ctk.CTkButton(quick_dates, text="Próx. Domingo", width=105, font=UI_FONT_SMALL, fg_color="#334155",
                      command=lambda: self._set_quick_date(self.single_date_entry, "sunday")).pack(side="left", padx=2)
        ctk.CTkButton(quick_dates, text="+7 Días", width=70, font=UI_FONT_SMALL, fg_color="#334155",
                      command=lambda: self._set_quick_date(self.single_date_entry, "plus7")).pack(side="left", padx=2)

        # Hora y Formato
        hf_row = ctk.CTkFrame(f_single, fg_color="transparent")
        hf_row.pack(fill="x", pady=(0, 10))

        h_col = ctk.CTkFrame(hf_row, fg_color="transparent")
        h_col.pack(side="left", fill="x", expand=True, padx=(0, 5))
        ctk.CTkLabel(h_col, text="Hora:", font=UI_FONT_SMALL, text_color="#94a3b8").pack(anchor="w")
        self.single_time_entry = ctk.CTkEntry(h_col, font=UI_FONT)
        self.single_time_entry.insert(0, "16:00")
        self.single_time_entry.pack(fill="x")

        fmt_col = ctk.CTkFrame(hf_row, fg_color="transparent")
        fmt_col.pack(side="left", fill="x", expand=True, padx=(5, 0))
        ctk.CTkLabel(fmt_col, text="Formato:", font=UI_FONT_SMALL, text_color="#94a3b8").pack(anchor="w")
        self.single_fmt_var = ctk.StringVar(value="EDISON")
        self.single_fmt_cb = ctk.CTkComboBox(fmt_col, variable=self.single_fmt_var,
                                             values=["EDISON", "GOAT", "TCG", "Tengu", "H.A.T.", "Speed Duel"])
        self.single_fmt_cb.pack(fill="x")

        # Modo
        ctk.CTkLabel(f_single, text="Modalidad:", font=UI_FONT_SMALL, text_color="#94a3b8").pack(anchor="w", pady=(0, 2))
        self.single_mode_var = ctk.StringVar(value="swiss")
        mode_row = ctk.CTkFrame(f_single, fg_color="transparent")
        mode_row.pack(fill="x", pady=(0, 10))
        ctk.CTkRadioButton(mode_row, text="Suizo", variable=self.single_mode_var, value="swiss", font=UI_FONT_SMALL).pack(side="left", padx=(0, 15))
        ctk.CTkRadioButton(mode_row, text="Moledoras (Eliminación)", variable=self.single_mode_var, value="grinder", font=UI_FONT_SMALL).pack(side="left")

        # Premio y Costo
        ctk.CTkLabel(f_single, text="Premio a destacar:", font=UI_FONT_SMALL, text_color="#94a3b8").pack(anchor="w", pady=(0, 2))
        self.single_prize_entry = ctk.CTkEntry(f_single, font=UI_FONT, placeholder_text="ej. Carta Ultimate Rare / Sobres")
        self.single_prize_entry.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(f_single, text="Inscripción ($):", font=UI_FONT_SMALL, text_color="#94a3b8").pack(anchor="w", pady=(0, 2))
        self.single_fee_entry = ctk.CTkEntry(f_single, font=UI_FONT)
        self.single_fee_entry.insert(0, "3000")
        self.single_fee_entry.pack(fill="x", pady=(0, 15))

        ctk.CTkButton(f_single, text="📅 Programar Este Torneo", font=("Roboto", 13, "bold"),
                      fg_color="#38bdf8", hover_color="#0284c7", text_color="#0f172a", height=38,
                      command=self.on_schedule_single_tournament).pack(fill="x", pady=5)

        # Formulario Ciclo de Liga
        f_league = ctk.CTkScrollableFrame(tab_league, fg_color="transparent")
        f_league.pack(fill="both", expand=True)

        ctk.CTkLabel(f_league, text="Nombre de la Liga:", font=UI_FONT_SMALL, text_color="#94a3b8").pack(anchor="w", pady=(5, 2))
        self.league_name_entry = ctk.CTkEntry(f_league, font=UI_FONT, placeholder_text="ej. Liga de Verano Edison 2026")
        self.league_name_entry.insert(0, "Liga Edison 2026 - Copa Ultimate")
        self.league_name_entry.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(f_league, text="Formato de la Liga:", font=UI_FONT_SMALL, text_color="#94a3b8").pack(anchor="w", pady=(0, 2))
        self.league_fmt_var = ctk.StringVar(value="EDISON")
        ctk.CTkComboBox(f_league, variable=self.league_fmt_var,
                        values=["EDISON", "GOAT", "TCG", "Tengu"]).pack(fill="x", pady=(0, 10))

        # Fecha y Hora del Ciclo
        dt_row = ctk.CTkFrame(f_league, fg_color="transparent")
        dt_row.pack(fill="x", pady=(0, 2))

        d_col = ctk.CTkFrame(dt_row, fg_color="transparent")
        d_col.pack(side="left", fill="x", expand=True, padx=(0, 5))
        ctk.CTkLabel(d_col, text="Fecha 1er Domingo (DD-MM-AAAA):", font=UI_FONT_SMALL, text_color="#94a3b8").pack(anchor="w", pady=(0, 2))
        self.league_start_entry = ctk.CTkEntry(d_col, font=UI_FONT)
        self.league_start_entry.pack(fill="x")
        self._set_quick_date(self.league_start_entry, "sunday")

        t_col = ctk.CTkFrame(dt_row, fg_color="transparent")
        t_col.pack(side="left", fill="x", expand=True, padx=(5, 0))
        ctk.CTkLabel(t_col, text="Hora del Evento Repetitivo (HH:MM):", font=UI_FONT_SMALL, text_color="#94a3b8").pack(anchor="w", pady=(0, 2))
        self.league_time_entry = ctk.CTkEntry(t_col, font=UI_FONT)
        self.league_time_entry.insert(0, "16:00")
        self.league_time_entry.pack(fill="x")

        # Botones de accesos rápidos para Fecha y Hora
        quick_bar = ctk.CTkFrame(f_league, fg_color="transparent")
        quick_bar.pack(fill="x", pady=(4, 10))

        ctk.CTkButton(quick_bar, text="Próx. Dom", width=75, font=UI_FONT_SMALL, fg_color="#334155",
                      command=lambda: self._set_quick_date(self.league_start_entry, "sunday")).pack(side="left", padx=2)
        ctk.CTkButton(quick_bar, text="+7 Días", width=60, font=UI_FONT_SMALL, fg_color="#334155",
                      command=lambda: self._set_quick_date(self.league_start_entry, "plus7")).pack(side="left", padx=2)

        ctk.CTkLabel(quick_bar, text=" | Hora: ", font=UI_FONT_SMALL, text_color="#64748b").pack(side="left", padx=4)

        for q_time in ["14:00", "15:00", "15:30", "16:00", "17:00", "18:00"]:
            ctk.CTkButton(quick_bar, text=q_time, width=46, font=UI_FONT_SMALL, fg_color="#334155",
                          command=lambda t=q_time: self._set_quick_time(self.league_time_entry, t)).pack(side="left", padx=2)

        ctk.CTkLabel(f_league, text="Duración (Cantidad de Domingos):", font=UI_FONT_SMALL, text_color="#94a3b8").pack(anchor="w", pady=(0, 2))
        self.league_duration_var = ctk.StringVar(value="8 Domingos (2 Meses)")
        ctk.CTkOptionMenu(f_league, variable=self.league_duration_var,
                          values=["4 Domingos (1 Mes)", "8 Domingos (2 Meses)", "6 Domingos (1.5 Meses)"]).pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(f_league, text="Carta / Premio Mayor (Ultimate Rare):", font=UI_FONT_SMALL, text_color="#94a3b8").pack(anchor="w", pady=(0, 2))
        self.league_prize_entry = ctk.CTkEntry(f_league, font=UI_FONT)
        self.league_prize_entry.insert(0, "Cyber Dragon (Ultimate Rare 1st Edition)")
        self.league_prize_entry.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(f_league, text="Cuota de Entrada por Parada ($):", font=UI_FONT_SMALL, text_color="#94a3b8").pack(anchor="w", pady=(0, 2))
        self.league_fee_entry = ctk.CTkEntry(f_league, font=UI_FONT)
        self.league_fee_entry.insert(0, "3000")
        self.league_fee_entry.pack(fill="x", pady=(0, 15))

        ctk.CTkButton(f_league, text="🏆 Generar y Programar Ciclo de Liga", font=("Roboto", 13, "bold"),
                      fg_color="#f59e0b", hover_color="#d97706", text_color="#0f172a", height=38,
                      command=self.on_schedule_league_cycle).pack(fill="x", pady=5)

    def _set_quick_date(self, entry, mode):
        today = datetime.now()
        if mode == "today":
            dt_str = today.strftime("%d-%m-%Y")
        elif mode == "sunday":
            days_ahead = 6 - today.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            dt_str = (today + timedelta(days=days_ahead)).strftime("%d-%m-%Y")
        elif mode == "plus7":
            dt_str = (today + timedelta(days=7)).strftime("%d-%m-%Y")
        else:
            dt_str = today.strftime("%d-%m-%Y")
        entry.delete(0, tk.END)
        entry.insert(0, dt_str)

    def _set_quick_time(self, entry, time_str):
        entry.delete(0, tk.END)
        entry.insert(0, time_str)

    def refresh_calendar_tab(self):
        for item in self.cal_tree.get_children():
            self.cal_tree.delete(item)

        fmt_filter = self.cal_filter_format.get() if hasattr(self, 'cal_filter_format') else "TODOS"
        inc_fin = self.cal_show_finished.get() if hasattr(self, 'cal_show_finished') else True

        events = self.calendar_manager.get_scheduled_tournaments(
            include_finished=inc_fin, format_filter=fmt_filter
        )

        self._cal_items_map = {}
        for ev in events:
            status_txt = ev['status']
            if status_txt == "PROGRAMADO":
                tag = "sched"
            elif status_txt == "EN_CURSO":
                tag = "running"
            elif status_txt == "FINALIZADO":
                tag = "finished"
            else:
                tag = "cancelled"

            prize_short = ev.get('prize_description', '')
            if len(prize_short) > 28:
                prize_short = prize_short[:25] + "..."

            mode_txt = "Suizo" if ev.get('mode') == 'swiss' else "Moledoras"

            iid = self.cal_tree.insert("", "end", values=(
                ev.get('display_date', ev['date']),
                ev.get('time', '16:00'),
                ev['title'],
                ev['format_name'],
                mode_txt,
                prize_short,
                status_txt
            ), tags=(tag,))

            self._cal_items_map[iid] = ev['id']

        self.cal_tree.tag_configure("sched", foreground="#38bdf8")
        self.cal_tree.tag_configure("running", foreground="#fbbf24")
        self.cal_tree.tag_configure("finished", foreground="#22c55e")
        self.cal_tree.tag_configure("cancelled", foreground="#94a3b8")

    def on_schedule_single_tournament(self):
        title = self.single_title_entry.get().strip()
        date_str = self.single_date_entry.get().strip()
        time_str = self.single_time_entry.get().strip() or "16:00"
        fmt = self.single_fmt_var.get()
        mode = self.single_mode_var.get()
        prize = self.single_prize_entry.get().strip()
        fee_str = self.single_fee_entry.get().strip()
        try:
            fee = float(fee_str)
        except ValueError:
            fee = 3000.0

        if not title:
            custom_alerts.showwarning("Atención", "Debes ingresar un título para el evento.")
            return

        if not parse_date_flexible(date_str):
            custom_alerts.showwarning("Atención", "Ingresa una fecha válida (DD-MM-AAAA).")
            return

        self.calendar_manager.schedule_tournament(
            title=title, format_name=fmt, date=date_str, time=time_str,
            mode=mode, entry_fee=fee, prize_description=prize
        )

        try:
            self.sync_manager.generate_snapshot_and_manifest(self.conn)
            self.sync_manager.publish()
        except Exception as e:
            print("[AcademyUI] Sync error:", e)

        self.single_title_entry.delete(0, tk.END)
        self.single_prize_entry.delete(0, tk.END)
        self.refresh_calendar_tab()
        custom_alerts.showinfo("Torneo Programado", f"El torneo '{title}' ({fmt}) ha sido programado y sincronizado exitosamente.")

    def on_schedule_league_cycle(self):
        name = self.league_name_entry.get().strip()
        fmt = self.league_fmt_var.get()
        start_date = self.league_start_entry.get().strip()
        time_str = self.league_time_entry.get().strip() if hasattr(self, 'league_time_entry') else "16:00"
        if not time_str:
            time_str = "16:00"
        dur_str = self.league_duration_var.get()
        num_stops = 8 if "8" in dur_str else (4 if "4" in dur_str else 6)
        prize = self.league_prize_entry.get().strip() or "Carta Ultimate Rare"
        fee_str = self.league_fee_entry.get().strip()
        try:
            fee = float(fee_str)
        except ValueError:
            fee = 3000.0

        if not name or not start_date:
            custom_alerts.showwarning("Atención", "Debes ingresar nombre y fecha de inicio para la liga.")
            return

        res = self.calendar_manager.schedule_league_cycle(
            league_name=name, format_name=fmt, start_date=start_date,
            num_stops=num_stops, prize_title=prize, entry_fee=fee,
            time=time_str
        )

        try:
            self.sync_manager.generate_snapshot_and_manifest(self.conn)
            self.sync_manager.publish()
        except Exception as e:
            print("[AcademyUI] Sync error:", e)

        self.refresh_calendar_tab()
        custom_alerts.showinfo(
            "Liga Programada",
            f"¡Se programó exitosamente la '{name}'!\n\n"
            f"• Formato: {fmt}\n"
            f"• Duración: {num_stops} Domingos\n"
            f"• Hora de cada Parada: {time_str} hrs\n"
            f"• Premio Mayor: {prize}\n"
            f"• Todas las fechas dominicales fueron añadidas a la agenda y a la web pública con su horario correspondiente."
        )

    def on_start_scheduled_tournament(self):
        sel = self.cal_tree.selection()
        if not sel:
            custom_alerts.showwarning("Atención", "Selecciona un torneo programado de la lista.")
            return
        item_id = sel[0]
        sched_id = getattr(self, '_cal_items_map', {}).get(item_id)
        if not sched_id:
            return
        sched = self.calendar_manager.get_scheduled_tournament_by_id(sched_id)
        if not sched:
            return

        confirm = custom_alerts.askyesno(
            "Iniciar Torneo",
            f"¿Deseas abrir el Gestor de Torneos con la configuración de:\n'{sched['title']}' ({sched['format_name']})?"
        )
        if confirm:
            if hasattr(self.app, 'open_tournament'):
                self.app.open_tournament(sched)

    def on_delete_scheduled_tournament(self):
        sel = self.cal_tree.selection()
        if not sel:
            custom_alerts.showwarning("Atención", "Selecciona un torneo de la lista para eliminar.")
            return
        item_id = sel[0]
        sched_id = getattr(self, '_cal_items_map', {}).get(item_id)
        if not sched_id:
            return
        sched = self.calendar_manager.get_scheduled_tournament_by_id(sched_id)
        if not sched:
            return

        confirm = custom_alerts.askyesno(
            "Eliminar Torneo",
            f"¿Estás seguro de cancelar y eliminar el torneo programado:\n'{sched['title']}'?"
        )
        if confirm:
            self.calendar_manager.delete_scheduled_tournament(sched_id)
            try:
                self.sync_manager.generate_snapshot_and_manifest(self.conn)
                self.sync_manager.publish()
            except Exception as e:
                pass
            self.refresh_calendar_tab()

    def on_sync_calendar_web(self):
        try:
            self.sync_manager.generate_snapshot_and_manifest(self.conn)
            self.sync_manager.publish()
            custom_alerts.showinfo("Sincronización Exitosa", "El calendario de torneos ha sido sincronizado y publicado en la página web pública.")
        except Exception as e:
            custom_alerts.showerror("Error", f"No se pudo sincronizar: {e}")
