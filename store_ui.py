import tkinter as tk
from tkinter import ttk, filedialog
import customtkinter as ctk
import custom_alerts as messagebox
from store_manager import StoreManager
import os
import threading
from PIL import ImageTk

UI_FONT = ("Roboto", 13)
UI_FONT_BIG = ("Orbitron Black", 24)
UI_FONT_SMALL = ("Roboto", 11)

class StoreUI(ctk.CTkFrame):
    def __init__(self, parent, go_back_callback):
        super().__init__(parent, fg_color="transparent")
        self.go_back_callback = go_back_callback
        self.manager = StoreManager()
        self.setup_ui()

    def setup_ui(self):
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", pady=10)

        back_btn = ctk.CTkButton(header_frame, text="< VOLVER AL MENÚ", command=self.go_back_callback, font=UI_FONT)
        back_btn.pack(side="left", padx=20)

        title = ctk.CTkLabel(header_frame, text="Gestor de Tiendas", font=UI_FONT_BIG, text_color="#60a5fa")
        title.place(relx=0.5, rely=0.5, anchor="center")
        
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=20)
        
        self.tab_manage = self.tabview.add("Gestión de Tiendas")
        self.tab_stats = self.tabview.add("Analíticas")
        self.tab_history = self.tabview.add("Historial de Torneos")
        
        self.setup_manage_tab()
        self.setup_stats_tab()
        self.setup_history_tab()
        self.refresh_list()

    def setup_manage_tab(self):
        content_frame = self.tab_manage

        left_frame = ctk.CTkFrame(content_frame, fg_color="#0f172a")
        left_frame.pack(side="left", fill="y", padx=(0, 10), pady=20, ipadx=20, ipady=20)

        ctk.CTkLabel(left_frame, text="Añadir Nueva Tienda", font=UI_FONT, text_color="#60a5fa").pack(pady=(20, 10), padx=20)
        
        self.store_name_entry = ctk.CTkEntry(left_frame, font=UI_FONT, width=250)
        self.store_name_entry.pack(pady=(0, 10), padx=20)
        
        ctk.CTkButton(left_frame, text="AÑADIR TIENDA", command=self.add_store, font=UI_FONT).pack(pady=10, padx=20)

        danger_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        danger_frame.pack(side="bottom", pady=20, padx=20)
        ctk.CTkButton(danger_frame, text="⚠️ Reiniciar Toda la Base de Datos ⚠️", command=self.factory_reset, font=UI_FONT_SMALL, fg_color="#7f1d1d", hover_color="#991b1b").pack()

        right_frame = ctk.CTkFrame(content_frame, fg_color="#0f172a")
        right_frame.pack(side="left", fill="both", expand=True, pady=20, ipadx=20, ipady=20)

        ctk.CTkLabel(right_frame, text="Tiendas Registradas", font=UI_FONT, text_color="#60a5fa").pack(pady=(20, 10), padx=20)

        self.active_store_var = tk.StringVar()
        ctk.CTkLabel(right_frame, textvariable=self.active_store_var, font=UI_FONT_SMALL, text_color="#60a5fa").pack(pady=(0, 10), padx=20)

        self.store_listbox = tk.Listbox(right_frame, font=UI_FONT, bg="#1e293b", fg="white", selectbackground="#3b82f6", relief="flat", borderwidth=0, highlightthickness=0)
        self.store_listbox.pack(fill="both", expand=True, pady=(0, 10), padx=20)
        self.store_listbox.bind("<Double-1>", lambda event: self.set_active_store())

        btn_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        ctk.CTkButton(btn_frame, text="Eliminar Seleccionada", command=self.delete_store, font=UI_FONT_SMALL, fg_color="#ef4444", hover_color="#b91c1c").pack(side="right", padx=5)
        ctk.CTkButton(btn_frame, text="Renombrar Seleccionada", command=self.rename_store, font=UI_FONT_SMALL).pack(side="right", padx=5)
        ctk.CTkButton(btn_frame, text="Usar Seleccionada", command=self.set_active_store, font=UI_FONT_SMALL, fg_color="#22c55e", hover_color="#16a34a").pack(side="right", padx=5)

    def setup_stats_tab(self):
        left_frame = ctk.CTkFrame(self.tab_stats, fg_color="#0f172a")
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 10), pady=20, ipadx=20, ipady=20)
        
        ctk.CTkLabel(left_frame, text="Estadísticas de la Tienda Activa", font=UI_FONT_BIG, text_color="#60a5fa").pack(pady=(10, 30))
        
        self.lbl_tot_tournaments = ctk.CTkLabel(left_frame, text="Torneos realizados: 0", font=UI_FONT, text_color="white")
        self.lbl_tot_tournaments.pack(anchor="w", padx=20, pady=5)
        
        self.lbl_unique_players = ctk.CTkLabel(left_frame, text="Jugadores únicos: 0", font=UI_FONT, text_color="white")
        self.lbl_unique_players.pack(anchor="w", padx=20, pady=5)
        
        ctk.CTkLabel(left_frame, text="Actividad por Formato:", font=UI_FONT, text_color="#94a3b8").pack(anchor="w", padx=20, pady=(15, 5))
        
        self.format_stats_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        self.format_stats_frame.pack(anchor="w", fill="x", padx=30)
        
        ctk.CTkLabel(left_frame, text="Top 3 Jugadores Frecuentes:", font=UI_FONT, text_color="#94a3b8").pack(anchor="w", padx=20, pady=(15, 5))
        
        self.top_players_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        self.top_players_frame.pack(anchor="w", fill="x", padx=30)
        
        ctk.CTkLabel(left_frame, text="Ganancia Acumulada:", font=UI_FONT_BIG, text_color="#60a5fa").pack(anchor="w", padx=20, pady=(20, 10))
        
        profit_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        profit_frame.pack(anchor="w", fill="x", padx=20)
        
        self.month_var = ctk.StringVar(value="Todos")
        self.month_selector = ctk.CTkOptionMenu(profit_frame, variable=self.month_var, values=["Todos"], font=UI_FONT_SMALL, command=self.update_profit_display)
        self.month_selector.pack(side="left", padx=(0, 10))
        
        self.format_filter_var = ctk.StringVar(value="Todos")
        self.format_filter_selector = ctk.CTkOptionMenu(profit_frame, variable=self.format_filter_var, values=["Todos"], font=UI_FONT_SMALL, command=self.update_profit_display)
        self.format_filter_selector.pack(side="left", padx=(0, 10))
        
        self.lbl_monthly_profit = ctk.CTkLabel(profit_frame, text="$0", font=("Orbitron Black", 24), text_color="#eab308")
        self.lbl_monthly_profit.pack(side="left", padx=(10, 0))
        
        right_frame = ctk.CTkFrame(self.tab_stats, fg_color="#0f172a")
        right_frame.pack(side="left", fill="both", expand=True, pady=20, ipadx=20, ipady=20)
        
        ctk.CTkLabel(right_frame, text="Gráfica de Actividad", font=UI_FONT_BIG, text_color="#60a5fa").pack(pady=(10, 20))
        
        self.chart_container = ctk.CTkFrame(right_frame, fg_color="#020617")
        self.chart_container.pack(fill="both", expand=True, padx=20, pady=10)
        
        btns_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
        btns_frame.pack(pady=10)
        
        ctk.CTkButton(btns_frame, text="Generar y Exportar Gráfico PNG", command=self.export_chart, font=UI_FONT).pack()

    def update_stats(self):
        store_name = self.manager.get_active_store()
        if not store_name: return
        
        stats = self.manager.get_store_stats(store_name)
        
        self.lbl_tot_tournaments.configure(text=f"Torneos realizados: {stats.get('total_tournaments', 0)}")
        self.lbl_unique_players.configure(text=f"Jugadores únicos: {stats.get('unique_players', 0)}")
        
        for widget in self.format_stats_frame.winfo_children():
            widget.destroy()
            
        by_format = stats.get('by_format', {})
        if not by_format:
            ctk.CTkLabel(self.format_stats_frame, text="Sin datos", font=UI_FONT_SMALL, text_color="#64748b").pack(anchor="w")
        else:
            for fmt, count in by_format.items():
                ctk.CTkLabel(self.format_stats_frame, text=f"• {fmt}: {count} torneos", font=UI_FONT_SMALL, text_color="white").pack(anchor="w", pady=2)
                
        for widget in self.top_players_frame.winfo_children():
            widget.destroy()
            
        top_players = stats.get('top_players', [])
        if not top_players:
            ctk.CTkLabel(self.top_players_frame, text="Sin datos", font=UI_FONT_SMALL, text_color="#64748b").pack(anchor="w")
        else:
            for i, p in enumerate(top_players):
                ctk.CTkLabel(self.top_players_frame, text=f"{i+1}. {p['name']} ({p['count']} torneos)", font=UI_FONT_SMALL, text_color="white").pack(anchor="w", pady=2)
                
        self.profits_data = self.manager.get_monthly_profits(store_name)
        
        months = ["Todos"] + sorted(list(set(d["month"] for d in self.profits_data)))
        formats = ["Todos"] + sorted(list(set(d["format_name"] for d in self.profits_data)))
        
        self.month_selector.configure(values=months)
        if self.month_var.get() not in months:
            self.month_var.set("Todos")
            
        self.format_filter_selector.configure(values=formats)
        if self.format_filter_var.get() not in formats:
            self.format_filter_var.set("Todos")
            
        self.update_profit_display()
        
        self.update_matplotlib_chart(store_name)
        
    def update_profit_display(self, *_):
        if not hasattr(self, 'profits_data'): return
        m = self.month_var.get()
        f = self.format_filter_var.get()
        
        total = 0.0
        for d in self.profits_data:
            if m != "Todos" and d["month"] != m: continue
            if f != "Todos" and d["format_name"] != f: continue
            total += d["profit"]
            
        self.lbl_monthly_profit.configure(text=f"${int(total):,}")
        
    def update_matplotlib_chart(self, store_name):
        timeline_data = self.manager.get_attendance_timeline(store_name)
        
        for widget in self.chart_container.winfo_children():
            widget.destroy()
            
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
        from matplotlib.figure import Figure
        from datetime import datetime
        
        fig = Figure(figsize=(6, 4), dpi=100)
        fig.patch.set_facecolor('#0f172a')
        
        ax = fig.add_subplot(111)
        ax.set_facecolor('#020617')
        ax.tick_params(colors='white')
        for spine in ax.spines.values():
            spine.set_edgecolor('#334155')
            
        ax.set_title(f"Actividad de Ligas: {store_name}", color='white')
        
        if not timeline_data:
            ax.text(0.5, 0.5, "No hay datos de torneos para graficar.", 
                    color="#94a3b8", ha='center', va='center', transform=ax.transAxes)
        else:
            def uniform_date(date_str):
                for fmt in ("%Y-%m-%d", "%d-%m-%y", "%d/%m/%Y", "%d-%m-%Y", "%y-%m-%d"):
                    try:
                        return datetime.strptime(date_str, fmt).strftime("%d/%m/%Y")
                    except ValueError:
                        pass
                return date_str
                
            formats_data = {}
            dates = []
            
            for row in timeline_data:
                fmt = row['format_name']
                d = uniform_date(row['date'])
                c = row['player_count']
                
                if d not in dates:
                    dates.append(d)
                if fmt not in formats_data:
                    formats_data[fmt] = {}
                # sum if multiple tournaments of same format on same day
                formats_data[fmt][d] = formats_data[fmt].get(d, 0) + c
                
            def safe_parse_date(date_str):
                try:
                    return datetime.strptime(date_str, "%d/%m/%Y")
                except ValueError:
                    return datetime.min

            dates.sort(key=safe_parse_date)
            
            ax.set_xlabel("Fecha de Torneo", color='white')
            ax.set_ylabel("Cantidad de Participantes", color='white')
            
            import numpy as np
            x_indices = np.arange(len(dates))
            num_formats = len(formats_data)
            
            if num_formats > 0:
                # Calculate bar width and overlap
                bar_width = 0.8 / num_formats
                # Slightly wider width so they overlap a little bit as requested
                visual_width = bar_width * 1.2 
                
                for i, (fmt, data_dict) in enumerate(formats_data.items()):
                    y_vals = [data_dict.get(d, 0) for d in dates]
                    offset = (i - num_formats / 2 + 0.5) * bar_width
                    ax.bar(x_indices + offset, y_vals, width=visual_width, label=fmt, alpha=0.9)
            
            ax.set_xticks(x_indices)
            ax.set_xticklabels(dates)
            
            ax.legend(facecolor='#0f172a', labelcolor='white')
            fig.autofmt_xdate()
            
        self.current_fig = fig
        canvas = FigureCanvasTkAgg(fig, master=self.chart_container)
        canvas.draw()
        
        toolbar = NavigationToolbar2Tk(canvas, self.chart_container)
        toolbar.update()
        toolbar.pack(side="bottom", fill="x")
        
        canvas.get_tk_widget().pack(side="top", fill="both", expand=True)
                
    def export_chart(self):
        store_name = self.manager.get_active_store()
        if not store_name: return
        
        initialfile = f"{store_name.lower().replace(' ', '_')}_actividad.png"
        import tkinter.filedialog as filedialog
        path = filedialog.asksaveasfilename(defaultextension=".png", initialfile=initialfile, title="Exportar Gráfico")
        if path:
            try:
                if hasattr(self, 'current_fig'):
                    self.current_fig.savefig(path, facecolor=self.current_fig.get_facecolor(), bbox_inches='tight', dpi=200)
                    from tkinter import messagebox
                    messagebox.showinfo("Éxito", f"Gráfico exportado a:\n{path}")
                else:
                    from tkinter import messagebox
                    messagebox.showwarning("Atención", "No hay gráfico generado para exportar.")
            except Exception as e:
                from tkinter import messagebox
                messagebox.showerror("Error", f"No se pudo exportar: {e}")

    def refresh_list(self):
        self.store_listbox.delete(0, tk.END)
        active_store = self.manager.get_active_store()
        self.active_store_var.set(f"Tienda activa: {active_store}")
        for store in self.manager.stores:
            prefix = "* " if store == active_store else "  "
            self.store_listbox.insert(tk.END, f"{prefix}{store}")
        self.update_stats()

    def _selected_store_name(self):
        selection = self.store_listbox.curselection()
        if not selection:
            return None
        return self.store_listbox.get(selection[0]).strip().lstrip("*").strip()

    def set_active_store(self):
        store_name = self._selected_store_name()
        if not store_name:
            messagebox.showwarning("Atencion", "Selecciona una tienda primero.")
            return
        try:
            self.manager.set_active_store(store_name)
            self.refresh_list()
            messagebox.showinfo("Exito", f"Tienda activa: {store_name}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def add_store(self):
        name = self.store_name_entry.get().strip()
        if not name:
            messagebox.showwarning("Error", "El nombre no puede estar vacío.")
            return
            
        try:
            self.manager.add_store(name)
            self.store_name_entry.delete(0, tk.END)
            self.refresh_list()
            messagebox.showinfo("Éxito", f"Tienda '{name}' añadida correctamente.")
        except Exception as e:
            import custom_alerts as messagebox
            messagebox.showerror("Error", str(e))

    def factory_reset(self):
        import custom_alerts as messagebox
        if not messagebox.askyesno("PELIGRO - Reinicio de Fábrica", "ESTÁS A PUNTO DE BORRAR TODO.\n\nEsto eliminará permanentemente todas las tiendas, jugadores, ganancias y el historial de torneos completo.\n\n¿Estás ABSOLUTAMENTE seguro de que deseas empezar desde cero?"):
            return
            
        top = ctk.CTkToplevel(self)
        top.title("Validación Mística")
        top.geometry("500x550")
        top.attributes('-topmost', True)
        top.grab_set()
        
        ctk.CTkLabel(top, text="Para enviar los datos al Reino de las Sombras,\ndebes reunir las 5 partes de Exodia.", text_color="#ef4444", font=UI_FONT).pack(pady=(15, 10))
        
        cards_data = [
            ("Exodia", "Exodia the Forbidden One.jpg"),
            ("Brazo Der", "Right Arm of the Forbidden One.jpg"),
            ("Brazo Izq", "Left Arm of the Forbidden One.jpg"),
            ("Pierna Der", "Right Leg of the Forbidden One.jpg"),
            ("Pierna Izq", "Left Leg of the Forbidden One.jpg"),
            ("Mago Oscuro", "Dark Magician.jpg"),
            ("Dragón Blanco", "Blue-Eyes White Dragon.jpg"),
            ("Olla de la Codicia", "Pot of Greed.jpg"),
            ("Kuriboh", "Kuriboh.jpg"),
            ("Fuerza de Espejo", "Mirror Force.jpg"),
            ("Renace el Monstruo", "Monster Reborn.jpg"),
            ("Jinzo", "Jinzo.jpg"),
            ("Tifón Místico", "Mystical Space Typhoon.jpg"),
            ("Llamada", "Call of the Haunted.jpg"),
            ("Tormenta", "Heavy Storm.jpg")
        ]
        
        import random, os
        from PIL import Image
        random.shuffle(cards_data)
        
        scroll = ctk.CTkScrollableFrame(top, width=420, height=350)
        scroll.pack(pady=10)
        
        self.selected_pieces = set()
        
        def toggle_card(name, btn):
            if name in self.selected_pieces:
                self.selected_pieces.remove(name)
                btn.configure(border_width=0)
            else:
                self.selected_pieces.add(name)
                btn.configure(border_width=4, border_color="#eab308")
                
        row, col = 0, 0
        for name, filename in cards_data:
            path = os.path.join("Cache", filename)
            img = None
            if os.path.exists(path):
                try:
                    pil_img = Image.open(path)
                    img = ctk.CTkImage(pil_img, size=(75, 110))
                except Exception:
                    pass
                
            btn = ctk.CTkButton(scroll, image=img, text="" if img else name, 
                              width=75, height=110, fg_color="transparent", 
                              hover_color="#1e293b", border_width=0, corner_radius=0)
            btn.configure(command=lambda n=name, b=btn: toggle_card(n, b))
            btn.grid(row=row, column=col, padx=8, pady=8)
            
            col += 1
            if col > 3:
                col = 0
                row += 1
        
        def on_confirm():
            exodia_pieces = {"Exodia", "Brazo Der", "Brazo Izq", "Pierna Der", "Pierna Izq"}
            if self.selected_pieces == exodia_pieces:
                from database import factory_reset
                factory_reset()
                
                from store_manager import StoreManager
                self.manager = StoreManager()
                self.refresh_list()
                top.destroy()
                messagebox.showinfo("¡Exterminio Exitoso!", "¡EXODIA HA OBLITERADO LA BASE DE DATOS!\n\nTodos los datos han sido enviados al Reino de las Sombras. Empiezas desde cero.")
            else:
                messagebox.showerror("Invocación Fallida", "No has reunido las piezas correctas o incluiste cartas adicionales. Exodia no responde a tu llamado.")
                
        ctk.CTkButton(top, text="💥 INVOCAR Y OBLITERAR 💥", command=on_confirm, fg_color="#7f1d1d", hover_color="#991b1b", font=UI_FONT).pack(pady=15)

    def delete_store(self):
        selection = self.store_listbox.curselection()
        if not selection:
            messagebox.showwarning("Atención", "Selecciona una tienda primero.")
            return
            
        store_name = self._selected_store_name()
        
        if len(self.manager.stores) <= 1:
            messagebox.showwarning("Error", "Debe haber al menos una tienda registrada.")
            return

        if messagebox.askyesno("Confirmar", f"¿Seguro que deseas eliminar la tienda '{store_name}'?\n(Los archivos no se borrarán del disco duro por seguridad)."):
            self.manager.remove_store(store_name)
            self.refresh_list()

    def rename_store(self):
        selection = self.store_listbox.curselection()
        if not selection:
            messagebox.showwarning("Atención", "Selecciona una tienda primero.")
            return
            
        old_name = self._selected_store_name()
        
        top = ctk.CTkToplevel(self)
        top.title("Renombrar Tienda")
        top.geometry("300x150")
        top.attributes('-topmost', True)
        top.grab_set()
        
        ctk.CTkLabel(top, text=f"Renombrar '{old_name}' a:", text_color="#60a5fa", font=UI_FONT_SMALL).pack(pady=10)
        new_name_entry = ctk.CTkEntry(top, font=UI_FONT)
        new_name_entry.pack(pady=5)
        
        def save():
            new_name = new_name_entry.get().strip()
            try:
                self.manager.rename_store(old_name, new_name)
                self.refresh_list()
                top.destroy()
            except Exception as e:
                messagebox.showerror("Error", str(e))
                
        ctk.CTkButton(top, text="Guardar", command=save, font=UI_FONT_SMALL).pack(pady=10)

    def setup_history_tab(self):
        history_dir = os.path.join("data", "history")
        if not os.path.exists(history_dir):
            os.makedirs(history_dir)
            
        content_frame = self.tab_history
        
        split = tk.PanedWindow(content_frame, orient="horizontal", bg="#0f172a", sashwidth=4)
        split.pack(fill="both", expand=True)
        
        list_frame = ctk.CTkFrame(split, fg_color="#0f172a")
        split.add(list_frame, minsize=250)
        
        details_frame = ctk.CTkFrame(split, fg_color="transparent")
        split.add(details_frame, minsize=400)
        
        header_frame = ctk.CTkFrame(list_frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=10)
        ctk.CTkLabel(header_frame, text="Torneos Guardados", font=UI_FONT_BIG, text_color="#60a5fa").pack(side="left", padx=10)
        ctk.CTkButton(header_frame, text="📊 Estadísticas", command=lambda: self.show_history_metrics(history_dir), font=UI_FONT_SMALL, width=100, fg_color="#3b82f6").pack(side="right", padx=10)

        history_listbox = tk.Listbox(list_frame, font=UI_FONT_SMALL, bg="#1e293b", fg="white", selectbackground="#3b82f6", relief="flat", borderwidth=0, highlightthickness=0)
        history_listbox.pack(fill="both", expand=True, padx=10, pady=10)
        
        import json
        def load_list():
            history_listbox.delete(0, tk.END)
            curr_files = [f for f in os.listdir(history_dir) if f.endswith(".json")]
            curr_files.sort(key=lambda x: os.path.getmtime(os.path.join(history_dir, x)), reverse=True)
            loaded_tournaments = []
            for file in curr_files:
                filepath = os.path.join(history_dir, file)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        data['_filename'] = file
                        loaded_tournaments.append(data)
                        saved_at = data.get("saved_at", "Desconocido")
                        format_name = data.get("manager", {}).get("format_name", data.get("ui", {}).get("format", "Desconocido"))
                        history_listbox.insert(tk.END, f"{saved_at} - {format_name}")
                except:
                    pass
            return loaded_tournaments
            
        self.tournaments_data = load_list()
        
        def on_select(event):
            selection = history_listbox.curselection()
            if not selection: return
            idx = selection[0]
            data = self.tournaments_data[idx]
            
            for widget in details_frame.winfo_children():
                widget.destroy()
                
            saved_at = data.get("saved_at", "Desconocido")
            manager_data = data.get("manager", {})
            players_data = manager_data.get("players", [])
            rounds_data = manager_data.get("rounds", [])
            format_name = data.get("manager", {}).get("format_name", data.get("ui", {}).get("format", "Desconocido"))
            profit = manager_data.get("tournament_profit", 0.0)
            packs = manager_data.get("total_packs_given", 0)
            
            ctk.CTkLabel(details_frame, text=f"Torneo del {saved_at}", font=UI_FONT_BIG, text_color="#60a5fa").pack(pady=10)
            ctk.CTkLabel(details_frame, text=f"Formato: {format_name} | Jugadores: {len(players_data)} | Rondas: {len(rounds_data)}", font=UI_FONT).pack()
            
            stats_text = f"Ganancia Asignada: ${int(profit):,} | Sobres Entregados: {packs}"
            ctk.CTkLabel(details_frame, text=stats_text, font=UI_FONT_SMALL, text_color="#4ade80").pack(pady=5)
            
            btns_frame = ctk.CTkFrame(details_frame, fg_color="transparent")
            btns_frame.pack(pady=5)
            
            def delete_tournament():
                if messagebox.askyesno("Confirmar", f"¿Estás seguro de que quieres eliminar este torneo del historial?"):
                    try:
                        os.remove(os.path.join(history_dir, data['_filename']))
                        self.tournaments_data = load_list()
                        for widget in details_frame.winfo_children():
                            widget.destroy()
                        self.update_stats()
                    except Exception as e:
                        messagebox.showerror("Error", f"No se pudo eliminar: {e}")
            
            ctk.CTkButton(btns_frame, text="Eliminar Torneo", command=delete_tournament, fg_color="#ef4444", hover_color="#dc2626", font=UI_FONT_SMALL).pack(side="left", padx=5)
            
            def export_png():
                from tournament_manager import TournamentManager
                from tournament_graphics import generate_standings_image
                try:
                    historical_manager = TournamentManager.from_dict(manager_data)
                except Exception as e:
                    messagebox.showerror("Error", f"No se pudo reconstruir el torneo histórico:\n{e}")
                    return
                
                store = data.get("ui", {}).get("store_name", self.manager.get_active_store() or "Tienda")
                date_val = data.get("ui", {}).get("date", "Desconocido")
                
                fmt_str = historical_manager.format_name.lower().replace(" ", "_")
                store_str = store.lower().replace(" ", "_")
                initialfile = f"{store_str}_{fmt_str}_standing_historico.png"
                
                filepath = filedialog.asksaveasfilename(
                    initialfile=initialfile,
                    defaultextension=".png",
                    title="Exportar Standing a PNG",
                    filetypes=[("PNG", "*.png")]
                )
                if not filepath:
                    return
                try:
                    img = generate_standings_image(historical_manager, store, date_val)
                    img.save(filepath)
                    messagebox.showinfo("Éxito", f"Standing exportado exitosamente a:\n{filepath}")
                except Exception as e:
                    messagebox.showerror("Error", f"Hubo un error al exportar la imagen:\n{e}")

            ctk.CTkButton(btns_frame, text="Exportar Standing a PNG", command=export_png, fg_color="#22c55e", hover_color="#16a34a", font=UI_FONT_SMALL).pack(side="left", padx=5)

            def export_instagram():
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
                    messagebox.showinfo("Exportado a Instagram", f"Imagen guardada en {img_path}.\n\n¡El texto descriptivo ha sido copiado al portapapeles! Listo para pegar en Instagram.")
                except Exception as e:
                    messagebox.showerror("Error", f"No se pudo exportar para Instagram:\n{e}")

            ctk.CTkButton(btns_frame, text="Exportar a Instagram", command=export_instagram, fg_color="#d946ef", hover_color="#c026d3", font=UI_FONT_SMALL).pack(side="left", padx=5)
            
            tree_frame = ctk.CTkFrame(details_frame, fg_color="transparent")
            tree_frame.pack(fill="both", expand=True, padx=20, pady=20)
            
            cols = ("Pos", "Jugador", "Puntos", "Estado", "Premios")
            tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=15)
            for c in cols:
                tree.heading(c, text=c)
            tree.column("Pos", width=40, anchor="center")
            tree.column("Jugador", width=150, anchor="w")
            tree.column("Puntos", width=60, anchor="center")
            tree.column("Estado", width=80, anchor="center")
            tree.column("Premios", width=100, anchor="center")
            
            scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=scroll.set)
            scroll.pack(side="right", fill="y")
            tree.pack(side="left", fill="both", expand=True)
            
            sorted_players = sorted(players_data, key=lambda x: x.get("points", 0), reverse=True)
            
            import math
            p1 = p2 = p3 = 0
            if packs <= 2:
                p1 = packs
            elif packs <= 5:
                p1 = math.ceil(packs * 0.6)
                p2 = packs - p1
            else:
                p1 = round(packs * 0.5)
                p2 = round(packs * 0.3)
                p3 = packs - p1 - p2
                if p3 < 1 and packs >= 6:
                    p2 -= 1
                    p3 += 1
                if p3 < 0:
                    p3 = 0
                    p2 = packs - p1
            prizes = [p1, p2, p3]
            
            for i, p in enumerate(sorted_players):
                estado = "Activo" if p.get("active", True) else "Dropeó"
                prize_str = f"{prizes[i]} sobres" if i < 3 and prizes[i] > 0 else ""
                tree.insert("", "end", values=(i+1, p.get("name", "Unknown"), p.get("points", 0), estado, prize_str))
                
        history_listbox.bind("<<ListboxSelect>>", on_select)

    def show_history_metrics(self, history_dir):
        import json
        files = [f for f in os.listdir(history_dir) if f.endswith(".json")]
        if not files:
            messagebox.showinfo("Aviso", "No hay datos para calcular métricas.")
            return

        tournaments = []
        for file in files:
            try:
                with open(os.path.join(history_dir, file), "r", encoding="utf-8") as f:
                    tournaments.append(json.load(f))
            except:
                pass

        formats = {"Global"}
        for t in tournaments:
            fmt = t.get("ui", {}).get("format")
            if fmt:
                formats.add(f"Formato: {fmt}")
        
        dialog = ctk.CTkToplevel(self)
        dialog.title("Métricas Globales")
        dialog.geometry("400x350")
        dialog.grab_set()
        
        ctk.CTkLabel(dialog, text="Filtro de Métricas", font=UI_FONT_BIG, text_color="#60a5fa").pack(pady=10)
        
        filter_var = ctk.StringVar(value="Global")
        filter_combo = ctk.CTkComboBox(dialog, values=sorted(list(formats)), variable=filter_var, font=UI_FONT, state="readonly")
        filter_combo.pack(pady=10)
        
        stats_frame = ctk.CTkFrame(dialog, fg_color="#1e293b")
        stats_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        lbl_count = ctk.CTkLabel(stats_frame, text="Torneos Jugados: 0", font=UI_FONT)
        lbl_count.pack(pady=10)
        
        lbl_profit = ctk.CTkLabel(stats_frame, text="Ganancia Total: $0", font=UI_FONT, text_color="#4ade80")
        lbl_profit.pack(pady=10)
        
        lbl_packs = ctk.CTkLabel(stats_frame, text="Sobres Entregados: 0", font=UI_FONT, text_color="#fbbf24")
        lbl_packs.pack(pady=10)
        
        def update_metrics(*args):
            sel_filter = filter_var.get()
            count = 0
            total_profit = 0.0
            total_packs = 0
            
            for t in tournaments:
                fmt = t.get("ui", {}).get("format", "")
                manager = t.get("manager", {})
                
                if sel_filter != "Global":
                    if sel_filter.startswith("Formato: ") and fmt != sel_filter.replace("Formato: ", ""):
                        continue
                
                count += 1
                total_profit += manager.get("tournament_profit", 0.0)
                total_packs += manager.get("total_packs_given", 0)
                
            lbl_count.configure(text=f"Torneos Jugados: {count}")
            lbl_profit.configure(text=f"Ganancia Total: ${int(total_profit):,}")
            lbl_packs.configure(text=f"Sobres Entregados: {total_packs}")
            
        filter_var.trace_add("write", update_metrics)
        update_metrics()
