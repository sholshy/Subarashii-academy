import tkinter as tk
import customtkinter as ctk
import math

UI_FONT = ("Roboto", 14)
UI_FONT_BIG = ("Orbitron Black", 24)
UI_FONT_SMALL = ("Roboto", 12)

class PrizeCalculatorUI(ctk.CTkFrame):
    def __init__(self, parent, go_back_callback):
        super().__init__(parent, fg_color="transparent")
        self.go_back_callback = go_back_callback
        self.prize_groups = None
        
        self.setup_ui()
        
    def setup_ui(self):
        # Top Bar
        top_bar = ctk.CTkFrame(self, fg_color="transparent")
        top_bar.pack(fill="x", padx=20, pady=10)
        
        back_btn = ctk.CTkButton(top_bar, text="< VOLVER AL MENÚ", command=self.go_back_callback, font=UI_FONT, width=150)
        back_btn.pack(side="left")
        
        self.return_to_tournament_btn = ctk.CTkButton(top_bar, text="VOLVER AL TORNEO >", font=UI_FONT, width=150)
        
        title = ctk.CTkLabel(top_bar, text="Calculadora de Premios", font=UI_FONT_BIG, text_color="#60a5fa")
        title.place(relx=0.5, rely=0.5, anchor="center")
        
        # Main Layout
        content_frame = ctk.CTkFrame(self, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Left Panel - Inputs
        left_panel = ctk.CTkFrame(content_frame, fg_color="#0f172a")
        left_panel.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        input_title = ctk.CTkLabel(left_panel, text="Parámetros del Evento", font=("Roboto", 18, "bold"), text_color="#60a5fa")
        input_title.pack(pady=15)
        
        # Helper to create inputs
        self.inputs = {}
        def create_input(parent, label_text, default_val):
            frame = ctk.CTkFrame(parent, fg_color="transparent")
            frame.pack(fill="x", padx=20, pady=5)
            lbl = ctk.CTkLabel(frame, text=label_text, font=UI_FONT, text_color="#cbd5e1", width=200, anchor="w")
            lbl.pack(side="left")
            entry = ctk.CTkEntry(frame, font=UI_FONT, width=150)
            entry.insert(0, str(default_val))
            entry.pack(side="right")
            
            # Bind key release to update calculations automatically
            entry.bind("<KeyRelease>", lambda e: self.calculate_prizes())
            
            return entry
            
        self.inputs['paid_players'] = create_input(left_panel, "Jugadores que Pagaron:", 20)
        self.inputs['invited_players'] = create_input(left_panel, "Jugadores Invitados:", 2)
        self.inputs['entry_fee'] = create_input(left_panel, "Costo de Entrada ($):", 2000)
        self.inputs['iva_pct'] = create_input(left_panel, "IVA Incluido (%):", 19)
        self.inputs['commission_pct'] = create_input(left_panel, "Comisión del Evento (%):", 5)
        self.inputs['box_cost'] = create_input(left_panel, "Costo de Caja de Sobres ($):", 70000)
        self.inputs['packs_per_box'] = create_input(left_panel, "Sobres por Caja:", 24)
        self.inputs['profit_margin_pct'] = create_input(left_panel, "Margen de Ganancia (%):", 40)
        
        # Right Panel - Results
        right_panel = ctk.CTkFrame(content_frame, fg_color="#1e293b")
        right_panel.pack(side="right", fill="both", expand=True, padx=(10, 0))
        
        res_title = ctk.CTkLabel(right_panel, text="Resultados y Distribución", font=("Roboto", 18, "bold"), text_color="#60a5fa")
        res_title.pack(pady=15)
        
        # Variables for results
        self.res_gross = ctk.StringVar(value="$0")
        self.res_net = ctk.StringVar(value="$0")
        self.res_packs = ctk.StringVar(value="0")
        self.res_total_players = ctk.StringVar(value="0")
        
        def create_result_lbl(parent, label_text, str_var, color="white"):
            frame = ctk.CTkFrame(parent, fg_color="transparent")
            frame.pack(fill="x", padx=20, pady=5)
            lbl = ctk.CTkLabel(frame, text=label_text, font=UI_FONT, text_color="#94a3b8", width=200, anchor="w")
            lbl.pack(side="left")
            val = ctk.CTkLabel(frame, textvariable=str_var, font=("Roboto", 16, "bold"), text_color=color)
            val.pack(side="right")
            
        create_result_lbl(right_panel, "Total Jugadores:", self.res_total_players)
        create_result_lbl(right_panel, "Ingreso Bruto:", self.res_gross)
        create_result_lbl(right_panel, "Ingreso Neto (Pozo):", self.res_net, color="#4ade80")
        create_result_lbl(right_panel, "Total Sobres a Repartir:", self.res_packs, color="#60a5fa")
        
        dist_frame = ctk.CTkFrame(right_panel, fg_color="#0f172a")
        dist_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        dist_title = ctk.CTkLabel(dist_frame, text="Sugerencia de Distribución", font=("Roboto", 16, "bold"), text_color="#60a5fa")
        dist_title.pack(pady=10)
        
        self.res_dist_1 = ctk.StringVar(value="1er Lugar: 0 sobres")
        self.res_dist_2 = ctk.StringVar(value="2do Lugar: 0 sobres")
        self.res_dist_3 = ctk.StringVar(value="3er Lugar: 0 sobres")
        
        ctk.CTkLabel(dist_frame, textvariable=self.res_dist_1, font=("Roboto", 20, "bold"), text_color="#fbbf24").pack(pady=5)
        ctk.CTkLabel(dist_frame, textvariable=self.res_dist_2, font=("Roboto", 18, "bold"), text_color="#9ca3af").pack(pady=5)
        ctk.CTkLabel(dist_frame, textvariable=self.res_dist_3, font=("Roboto", 16, "bold"), text_color="#b45309").pack(pady=5)
        
        pack_price_frame = ctk.CTkFrame(right_panel, fg_color="#334155")
        pack_price_frame.pack(fill="x", padx=20, pady=(0, 20))
        self.res_pack_price = ctk.StringVar(value="Precio Sugerido Venta 1 Sobre: $0")
        ctk.CTkLabel(pack_price_frame, textvariable=self.res_pack_price, font=("Roboto", 14, "bold"), text_color="#2dd4bf").pack(pady=10)

        self.assign_btn = ctk.CTkButton(right_panel, text="ASIGNAR GANANCIA AL TORNEO", command=self.assign_profit, font=UI_FONT, fg_color="#eab308", hover_color="#ca8a04", text_color="black")
        self.assign_btn.pack(pady=20)
        
        # Initial calc
        self.calculate_prizes()

    def assign_profit(self):
        import custom_alerts as messagebox
        try:
            total_net = float(self.res_net.get().replace("$","").replace(",",""))
            box_cost = self.get_val('box_cost', float, 0.0)
            packs_per_box = max(self.get_val('packs_per_box', int, 1), 1)
            base_pack_cost = box_cost / packs_per_box
            total_packs = int(self.res_packs.get().split()[0])
            profit = total_net - (base_pack_cost * total_packs)
            
            if not messagebox.askyesno("Confirmar", f"¿Asignar ganancia de ${int(profit):,} y {total_packs} sobres al torneo?"):
                return
                
            from database import get_connection
            from store_manager import StoreManager
            import os
            import json
            
            msg_parts = []
            
            # 1. Update in-memory tournament if active
            manager = None
            if hasattr(self.master, 'tournament_frame') and self.master.tournament_frame:
                manager = getattr(self.master.tournament_frame, 'manager', None)
                
            if manager and len(manager.players) > 0:
                manager.tournament_profit = profit
                manager.total_packs_given = total_packs
                msg_parts.append("- Asignado al torneo en curso (recuerda finalizarlo).")
            else:
                # If no active tournament, try to update the LAST JSON in history
                history_dir = os.path.join("data", "history")
                if os.path.exists(history_dir):
                    files = [f for f in os.listdir(history_dir) if f.endswith(".json")]
                    if files:
                        files.sort(key=lambda x: os.path.getmtime(os.path.join(history_dir, x)), reverse=True)
                        last_file = os.path.join(history_dir, files[0])
                        try:
                            with open(last_file, "r", encoding="utf-8") as f:
                                data = json.load(f)
                            if "manager" in data:
                                data["manager"]["tournament_profit"] = profit
                                data["manager"]["total_packs_given"] = total_packs
                            with open(last_file, "w", encoding="utf-8") as f:
                                json.dump(data, f, ensure_ascii=False, indent=2)
                            msg_parts.append("- Actualizado en el historial (último torneo).")
                        except Exception as e:
                            print("Error updating json:", e)
                            
            # 2. Update DB for the active store
            sm = StoreManager()
            store_name = sm.get_active_store()
            if store_name:
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT id FROM stores WHERE name=?", (store_name,))
                    row = cursor.fetchone()
                    if row:
                        store_id = row['id']
                        cursor.execute("UPDATE tournaments SET profit = ? WHERE id = (SELECT id FROM tournaments WHERE store_id = ? ORDER BY id DESC LIMIT 1)", (profit, store_id))
                        conn.commit()
                        msg_parts.append(f"- Guardado en la base de datos de la tienda '{store_name}'.")
                    conn.close()
                except Exception as e:
                    print("Error DB:", e)
            else:
                msg_parts.append("- (No hay tienda activa para guardar en BD).")
                
            final_msg = "Éxito al asignar ganancias:\n\n" + "\n".join(msg_parts)
            messagebox.showinfo("Éxito", final_msg)
            
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo calcular la ganancia: {e}")
    def set_return_callback(self, cb):
        if cb:
            self.return_to_tournament_btn.configure(command=cb)
            self.return_to_tournament_btn.pack(side="right")
        else:
            self.return_to_tournament_btn.pack_forget()

    def set_players(self, total_players, invited_players=None):
        invited = invited_players if invited_players is not None else (1 if total_players > 0 else 0)
        paid = total_players - invited if total_players > 0 else 0
        
        self.inputs['paid_players'].delete(0, 'end')
        self.inputs['paid_players'].insert(0, str(paid))
        
        self.inputs['invited_players'].delete(0, 'end')
        self.inputs['invited_players'].insert(0, str(invited))
        
        self.calculate_prizes()

    def set_prize_groups(self, prize_groups=None):
        self.prize_groups = prize_groups
        self.calculate_prizes()

    def get_val(self, key, type_func=float, default=0.0):
        try:
            val = self.inputs[key].get().strip()
            if not val:
                return default
            return type_func(val)
        except ValueError:
            return default

    def calculate_prizes(self):
        paid = self.get_val('paid_players', int, 0)
        invited = self.get_val('invited_players', int, 0)
        fee = self.get_val('entry_fee', float, 0.0)
        iva = self.get_val('iva_pct', float, 0.0)
        comm = self.get_val('commission_pct', float, 0.0)
        box_cost = self.get_val('box_cost', float, 0.0)
        packs_per_box = self.get_val('packs_per_box', int, 1)
        profit_margin = self.get_val('profit_margin_pct', float, 0.0)
        if packs_per_box < 1:
            packs_per_box = 1
            
        total_players = paid + invited
        gross_income = paid * fee
        
        # Calc Neto per entry
        # Net = Gross / (1 + IVA/100) - Gross * (Comm/100)
        net_from_iva = fee / (1 + (iva / 100))
        comm_cost = fee * (comm / 100)
        net_fee = net_from_iva - comm_cost
        
        total_net_income = net_fee * paid
        
        base_pack_cost = box_cost / packs_per_box
        pack_cost = base_pack_cost * (1 + (profit_margin / 100))
        
        if pack_cost > 0:
            raw_packs = total_net_income / pack_cost
            total_packs = math.ceil(max(0, raw_packs))
        else:
            total_packs = 0
            
        # Update strings
        self.res_total_players.set(f"{total_players} ({paid} pagaron, {invited} inv.)")
        self.res_gross.set(f"${int(gross_income):,}")
        self.res_net.set(f"${int(total_net_income):,}")
        self.res_packs.set(f"{total_packs} sobres")
        
        target_net = base_pack_cost * (1 + (profit_margin / 100))
        divisor = (1 / (1 + (iva / 100))) - (comm / 100)
        
        if divisor > 0 and target_net > 0:
            suggested_price_raw = target_net / divisor
            suggested_price = math.ceil(suggested_price_raw / 500.0) * 500
        else:
            suggested_price = 0
        self.res_pack_price.set(f"Precio Sugerido Venta 1 Sobre: ${int(suggested_price):,}")
        
        # Distribution
        # 1-2 sobres: 100% 1st
        # 3-5 sobres: 60% 1st / 40% 2nd
        # 6+ sobres: 50% / 30% / 20%
        
        p1 = p2 = p3 = 0
        if total_packs <= 2:
            p1 = total_packs
        elif total_packs <= 5:
            p1 = math.ceil(total_packs * 0.6)
            p2 = total_packs - p1
        else:
            p1 = round(total_packs * 0.5)
            p2 = round(total_packs * 0.3)
            p3 = total_packs - p1 - p2
            if p3 < 1 and total_packs >= 6:
                p2 -= 1
                p3 += 1
            if p3 < 0:
                p3 = 0
                p2 = total_packs - p1

        position_prizes = [p1, p2, p3]

        if self.prize_groups:
            self.apply_grouped_distribution(position_prizes)
        else:
            self.res_dist_1.set(f"1er Lugar: {p1} sobres" if p1 > 0 else "1er Lugar: 0 sobres")
            self.res_dist_2.set(f"2do Lugar: {p2} sobres" if p2 > 0 else "")
            self.res_dist_3.set(f"3er Lugar: {p3} sobres" if p3 > 0 else "")

    def apply_grouped_distribution(self, position_prizes):
        lines = []
        assigned_slots = 0

        for group in self.prize_groups[:3]:
            rank = int(group.get("rank", assigned_slots + 1))
            count = max(1, int(group.get("count", 1)))
            start = rank - 1
            end = start + count
            pool = sum(position_prizes[start:end])
            per_player = math.ceil(pool / count) if pool > 0 else 0

            if count == 1:
                lines.append(f"{self.ordinal(rank)} Lugar: {per_player} sobres")
            else:
                lines.append(f"{self.ordinal(rank)} Lugar ({count} empatados): {per_player} sobres c/u")

            assigned_slots += count

        while len(lines) < 3:
            lines.append("")

        self.res_dist_1.set(lines[0] or "1er Lugar: 0 sobres")
        self.res_dist_2.set(lines[1])
        self.res_dist_3.set(lines[2])

    def ordinal(self, rank):
        if rank == 1:
            return "1er"
        if rank == 2:
            return "2do"
        if rank == 3:
            return "3er"
        return f"{rank}to"
