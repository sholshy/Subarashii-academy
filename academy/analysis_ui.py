import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox
from tkinter import ttk
import os
import csv
from datetime import datetime

from academy.historical_audit import audit_database
from academy.competitive_analyzer import CompetitiveAnalyzer
from academy.rating_simulator import RatingSimulator, ClassicEloStrategy, ProvisionalEloStrategy, CommunityEloStrategy

UI_FONT = ("Helvetica", 14)
UI_FONT_SMALL = ("Helvetica", 12)
UI_FONT_BIG = ("Helvetica", 18, "bold")

class AnalysisUI(ctk.CTkToplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("Análisis Histórico - Subarashii Duel Academy")
        self.geometry("900x600")
        self.minsize(800, 500)
        
        # Traer ventana al frente
        self.attributes('-topmost', True)
        self.after(200, lambda: self.attributes('-topmost', False))
        self.focus_force()
        
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.tab_audit = self.tabview.add("Auditoría")
        self.tab_stats = self.tabview.add("Estadísticas")
        self.tab_sim = self.tabview.add("Simulador ELO")
        self.tab_sim_v2 = self.tabview.add("Simulación V2")
        self.tab_sim_v3 = self.tabview.add("Simulación V3")
        
        self._setup_audit_tab()
        self._setup_stats_tab()
        self._setup_sim_tab()
        self._setup_sim_v2_tab()
        self._setup_sim_v3_tab()
        
    def _setup_audit_tab(self):
        btn = ctk.CTkButton(self.tab_audit, text="Ejecutar Auditoría de Integridad", command=self.run_audit, font=UI_FONT)
        btn.pack(pady=20)
        
        self.audit_text = ctk.CTkTextbox(self.tab_audit, font=("Consolas", 12))
        self.audit_text.pack(fill="both", expand=True, padx=20, pady=10)
        
    def run_audit(self):
        import sys, io
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            audit_database()
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
            
        self.audit_text.delete("1.0", tk.END)
        self.audit_text.insert(tk.END, output)

    def _setup_stats_tab(self):
        top_frame = ctk.CTkFrame(self.tab_stats, fg_color="transparent")
        top_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(top_frame, text="Formato:").pack(side="left", padx=5)
        self.stat_format_var = ctk.StringVar(value="Todos")
        ctk.CTkOptionMenu(top_frame, variable=self.stat_format_var, values=["Todos", "GOAT", "EDISON", "Speed Duel"]).pack(side="left", padx=5)
        
        ctk.CTkLabel(top_frame, text="Mín. Partidas:").pack(side="left", padx=5)
        self.stat_min_var = ctk.StringVar(value="1")
        ctk.CTkEntry(top_frame, textvariable=self.stat_min_var, width=50).pack(side="left", padx=5)
        
        ctk.CTkButton(top_frame, text="Cargar Rankings", command=self.load_stats).pack(side="left", padx=20)
        ctk.CTkButton(top_frame, text="Exportar CSV", command=self.export_stats).pack(side="right", padx=5)
        
        columns = ("Jugador", "WR %", "Victorias", "Derrotas", "Empates", "Partidas", "Torneos", "Campeonatos")
        self.tree_stats = ttk.Treeview(self.tab_stats, columns=columns, show="headings", height=15)
        for col in columns:
            self.tree_stats.heading(col, text=col)
            self.tree_stats.column(col, width=100, anchor="center")
        self.tree_stats.column("Jugador", width=150, anchor="w")
        self.tree_stats.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.current_stats = []

    def load_stats(self):
        fmt = self.stat_format_var.get()
        if fmt == "Todos": fmt = None
        
        try:
            min_matches = int(self.stat_min_var.get())
        except:
            min_matches = 1
            
        analyzer = CompetitiveAnalyzer(format_name=fmt)
        rankings = analyzer.get_ranking(min_matches=min_matches)
        
        for row in self.tree_stats.get_children():
            self.tree_stats.delete(row)
            
        self.current_stats = rankings
        for r in rankings:
            self.tree_stats.insert("", "end", values=(
                r['name'],
                f"{r['win_rate']}%",
                r['wins'],
                r['losses'],
                r['draws'],
                r['total_matches'],
                r['tournaments_played'],
                r['championships']
            ))

    def export_stats(self):
        if not self.current_stats:
            messagebox.showwarning("Exportar", "No hay datos para exportar.")
            return
            
        filename = f"rankings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Jugador", "WR %", "Victorias", "Derrotas", "Empates", "Partidas", "Torneos", "Campeonatos"])
            for r in self.current_stats:
                writer.writerow([r['name'], r['win_rate'], r['wins'], r['losses'], r['draws'], r['total_matches'], r['tournaments_played'], r['championships']])
        messagebox.showinfo("Exportar", f"Datos exportados a {filename}")

    def _setup_sim_tab(self):
        top_frame = ctk.CTkFrame(self.tab_sim, fg_color="transparent")
        top_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(top_frame, text="Sistema ELO:").pack(side="left", padx=5)
        self.sim_system_var = ctk.StringVar(value="Comunitario")
        ctk.CTkOptionMenu(top_frame, variable=self.sim_system_var, values=["Clásico", "Provisional", "Comunitario"]).pack(side="left", padx=5)
        
        ctk.CTkLabel(top_frame, text="Formato:").pack(side="left", padx=5)
        self.sim_format_var = ctk.StringVar(value="Todos")
        ctk.CTkOptionMenu(top_frame, variable=self.sim_format_var, values=["Todos", "GOAT", "EDISON", "Speed Duel"]).pack(side="left", padx=5)
        
        ctk.CTkButton(top_frame, text="Ejecutar Simulación", command=self.run_sim).pack(side="left", padx=20)
        ctk.CTkButton(top_frame, text="Exportar CSV", command=self.export_sim).pack(side="right", padx=5)
        
        columns = ("Jugador", "Rating", "WR %", "Partidas", "Victorias", "Derrotas", "Rating Máx", "Rating Mín")
        self.tree_sim = ttk.Treeview(self.tab_sim, columns=columns, show="headings", height=15)
        for col in columns:
            self.tree_sim.heading(col, text=col)
            self.tree_sim.column(col, width=100, anchor="center")
        self.tree_sim.column("Jugador", width=150, anchor="w")
        self.tree_sim.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.current_sim_report = []

    def run_sim(self):
        sys_val = self.sim_system_var.get()
        if sys_val == "Clásico":
            strategy = ClassicEloStrategy()
        elif sys_val == "Provisional":
            strategy = ProvisionalEloStrategy()
        else:
            strategy = CommunityEloStrategy()
            
        fmt = self.sim_format_var.get()
        if fmt == "Todos": fmt = None
        
        sim = RatingSimulator(strategy, format_name=fmt)
        sim.simulate()
        report = sim.get_report()
        
        for row in self.tree_sim.get_children():
            self.tree_sim.delete(row)
            
        self.current_sim_report = report
        for r in report:
            self.tree_sim.insert("", "end", values=(
                r['name'],
                r['rating'],
                f"{r['win_rate']}%",
                r['matches'],
                r['wins'],
                r['losses'],
                r['highest'],
                r['lowest']
            ))

    def export_sim(self):
        if not self.current_sim_report:
            messagebox.showwarning("Exportar", "No hay simulación para exportar.")
            return
            
        filename = f"simulacion_elo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Jugador", "Rating", "WR %", "Partidas", "Victorias", "Derrotas", "Rating Max", "Rating Min"])
            for r in self.current_sim_report:
                writer.writerow([r['name'], r['rating'], r['win_rate'], r['matches'], r['wins'], r['losses'], r['highest'], r['lowest']])
        messagebox.showinfo("Exportar", f"Datos exportados a {filename}")

    def _setup_sim_v2_tab(self):
        btn = ctk.CTkButton(self.tab_sim_v2, text="Generar Reportes Analíticos V2 (CSVs)", command=self.run_sim_v2, font=UI_FONT_BIG, height=50)
        btn.pack(pady=40)
        
        self.v2_status_lbl = ctk.CTkLabel(self.tab_sim_v2, text="Haz clic para ejecutar todas las simulaciones de la hipótesis V2.\nLos resultados se guardarán en la carpeta 'academy/sim_results/'.", font=UI_FONT, text_color="#94a3b8")
        self.v2_status_lbl.pack(pady=10)
        
    def run_sim_v2(self):
        try:
            from academy.simulation_v2 import SimulationV2Runner
            runner = SimulationV2Runner()
            runner.run_all()
            self.v2_status_lbl.configure(text=f"¡Simulaciones completadas!\nSe generaron los archivos CSV en:\n{os.path.abspath('academy/sim_results')}", text_color="#10b981")
        except Exception as e:
            self.v2_status_lbl.configure(text=f"Error durante la simulación: {e}", text_color="#ef4444")

    def _setup_sim_v3_tab(self):
        btn = ctk.CTkButton(self.tab_sim_v3, text="Generar Reportes Analíticos V3 (CSVs)", command=self.run_sim_v3, font=UI_FONT_BIG, height=50)
        btn.pack(pady=40)
        
        self.v3_status_lbl = ctk.CTkLabel(self.tab_sim_v3, text="Haz clic para ejecutar todas las simulaciones de la hipótesis V3.\nLos resultados se guardarán en la carpeta 'academy/sim_results_v3/'.", font=UI_FONT, text_color="#94a3b8")
        self.v3_status_lbl.pack(pady=10)
        
    def run_sim_v3(self):
        try:
            from academy.simulation_v3 import SimulationV3Runner
            runner = SimulationV3Runner()
            runner.run_all()
            self.v3_status_lbl.configure(text=f"¡Simulaciones completadas!\nSe generaron los archivos CSV en:\n{os.path.abspath('academy/sim_results_v3')}", text_color="#10b981")
        except Exception as e:
            self.v3_status_lbl.configure(text=f"Error durante la simulación: {e}", text_color="#ef4444")
