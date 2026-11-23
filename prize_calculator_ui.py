import tkinter as tk
import customtkinter as ctk
import math
import os
import json
from accessories_manager import AccessoriesManager

UI_FONT = ("Roboto", 13)
UI_FONT_BOLD = ("Roboto", 13, "bold")
UI_FONT_BIG = ("Orbitron Black", 22)
UI_FONT_SMALL = ("Roboto", 11)

class PrizeCalculatorUI(ctk.CTkFrame):
    def __init__(self, parent, go_back_callback):
        super().__init__(parent, fg_color="transparent")
        self.go_back_callback = go_back_callback
        self.prize_groups = None
        self.acc_manager = AccessoriesManager()
        
        # State
        self.top_cut_mode = ctk.StringVar(value="Automático")
        self.slot_accessory_vars = {}  # slot_idx -> ctk.StringVar (item_id or 'none')
        self.slot_widgets = []
        self.updating_ui = False
        
        self.setup_ui()

    def setup_ui(self):
        # Top Bar
        top_bar = ctk.CTkFrame(self, fg_color="transparent")
        top_bar.pack(fill="x", padx=20, pady=(10, 5))
        
        back_btn = ctk.CTkButton(top_bar, text="< VOLVER AL MENÚ", command=self.go_back_callback, font=UI_FONT, width=150)
        back_btn.pack(side="left")
        
        self.return_to_tournament_btn = ctk.CTkButton(top_bar, text="VOLVER AL TORNEO >", font=UI_FONT, width=150)
        
        title = ctk.CTkLabel(top_bar, text="Calculadora de Premios y Accesorios", font=UI_FONT_BIG, text_color="#60a5fa")
        title.place(relx=0.5, rely=0.5, anchor="center")
        
        # Main Layout
        content_frame = ctk.CTkFrame(self, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Left Panel - Inputs & Accessories Inventory Control
        left_panel = ctk.CTkScrollableFrame(content_frame, fg_color="#0f172a", width=380)
        left_panel.pack(side="left", fill="both", padx=(0, 10))
        
        input_title = ctk.CTkLabel(left_panel, text="Parámetros del Evento", font=("Roboto", 16, "bold"), text_color="#60a5fa")
        input_title.pack(pady=(10, 10))
        
        self.inputs = {}
        def create_input(parent, label_text, default_val):
            frame = ctk.CTkFrame(parent, fg_color="transparent")
            frame.pack(fill="x", padx=10, pady=4)
            lbl = ctk.CTkLabel(frame, text=label_text, font=UI_FONT_SMALL, text_color="#cbd5e1", width=180, anchor="w")
            lbl.pack(side="left")
            entry = ctk.CTkEntry(frame, font=UI_FONT_SMALL, width=130)
            entry.insert(0, str(default_val))
            entry.pack(side="right")
            entry.bind("<KeyRelease>", lambda e: self.calculate_prizes())
            return entry
            
        self.inputs['paid_players'] = create_input(left_panel, "Jugadores que Pagaron:", 16)
        self.inputs['invited_players'] = create_input(left_panel, "Jugadores Invitados:", 0)
        self.inputs['entry_fee'] = create_input(left_panel, "Costo de Entrada ($):", 5000)
        self.inputs['iva_pct'] = create_input(left_panel, "IVA Incluido (%):", 19)
        self.inputs['commission_pct'] = create_input(left_panel, "Comisión Pasarela/TB (%):", 2.9)
        self.inputs['profit_margin_pct'] = create_input(left_panel, "Margen Deseado (%):", 40)

        # Pack Selection from Inventory
        pack_select_frame = ctk.CTkFrame(left_panel, fg_color="#1e293b", corner_radius=8)
        pack_select_frame.pack(fill="x", padx=10, pady=(12, 4))

        ctk.CTkLabel(pack_select_frame, text="Sobre de Premios (del Inventario)", font=("Roboto", 13, "bold"), text_color="#a78bfa").pack(anchor="w", padx=12, pady=(8, 2))

        self.selected_pack_var = ctk.StringVar(value="")
        self.pack_option_menu = ctk.CTkOptionMenu(
            pack_select_frame,
            values=["(Cargando sobres...)"],
            variable=self.selected_pack_var,
            command=lambda v: self.on_pack_selected(v),
            font=UI_FONT_SMALL,
            height=30
        )
        self.pack_option_menu.pack(fill="x", padx=12, pady=(2, 4))

        self.pack_info_lbl = ctk.CTkLabel(pack_select_frame, text="", font=("Roboto", 11), text_color="#94a3b8", justify="left")
        self.pack_info_lbl.pack(anchor="w", padx=12, pady=(0, 8))

        # Inventory Management Section
        inv_frame = ctk.CTkFrame(left_panel, fg_color="#1e293b", corner_radius=8)
        inv_frame.pack(fill="x", padx=10, pady=(10, 8))
        
        ctk.CTkLabel(inv_frame, text="Inventario de Productos y Sobres", font=("Roboto", 13, "bold"), text_color="#38bdf8").pack(pady=(8, 4))
        self.inv_summary_lbl = ctk.CTkLabel(inv_frame, text="Cargando stock...", font=UI_FONT_SMALL, text_color="#94a3b8")
        self.inv_summary_lbl.pack(pady=2)
        
        btn_manage_inv = ctk.CTkButton(
            inv_frame, 
            text="📦 GESTIONAR PRODUCTOS Y STOCK", 
            command=self.open_inventory_modal, 
            font=UI_FONT_SMALL, 
            fg_color="#0284c7", 
            hover_color="#0369a1",
            height=32
        )
        btn_manage_inv.pack(fill="x", padx=12, pady=10)

        # Suggested Pack Price Box
        pack_price_frame = ctk.CTkFrame(left_panel, fg_color="#1e293b", corner_radius=8)
        pack_price_frame.pack(fill="x", padx=10, pady=(4, 10))
        self.res_pack_price = ctk.StringVar(value="Sobre de Premios: Cargando...")
        ctk.CTkLabel(pack_price_frame, textvariable=self.res_pack_price, font=UI_FONT_SMALL, text_color="#2dd4bf").pack(pady=8)
        
        # Right Panel - Financial Summary & Top Prizes Distribution
        right_panel = ctk.CTkFrame(content_frame, fg_color="#1e293b")
        right_panel.pack(side="right", fill="both", expand=True)
        
        # Upper Right - Financial Balance Dashboard
        fin_frame = ctk.CTkFrame(right_panel, fg_color="#0f172a", corner_radius=8)
        fin_frame.pack(fill="x", padx=15, pady=(15, 10))
        
        ctk.CTkLabel(fin_frame, text="Balance Financiero del Torneo", font=("Roboto", 15, "bold"), text_color="#60a5fa").pack(anchor="w", padx=15, pady=(10, 5))
        
        # Metric StringVars
        self.res_total_players = ctk.StringVar(value="0")
        self.res_gross = ctk.StringVar(value="$0")
        self.res_net = ctk.StringVar(value="$0")
        self.res_budget = ctk.StringVar(value="$0")
        self.res_acc_sale = ctk.StringVar(value="$0")
        self.res_acc_cost = ctk.StringVar(value="$0")
        self.res_acc_profit = ctk.StringVar(value="+$0")
        self.res_packs = ctk.StringVar(value="0 sobres")
        self.res_packs_cost = ctk.StringVar(value="$0")
        self.res_packs_profit = ctk.StringVar(value="+$0")
        self.res_total_prize_cost = ctk.StringVar(value="$0")
        self.res_real_profit = ctk.StringVar(value="$0 (0%)")
        self.res_alert = ctk.StringVar(value="")

        # Grid of metrics
        grid_frame = ctk.CTkFrame(fin_frame, fg_color="transparent")
        grid_frame.pack(fill="x", padx=15, pady=5)
        grid_frame.columnconfigure((0, 1, 2, 3), weight=1)

        def add_metric_card(parent, row, col, title, str_var, val_color="white"):
            card = ctk.CTkFrame(parent, fg_color="#1e293b", corner_radius=6)
            card.grid(row=row, column=col, padx=5, pady=4, sticky="nsew")
            ctk.CTkLabel(card, text=title, font=("Roboto", 10), text_color="#94a3b8").pack(anchor="w", padx=8, pady=(4, 0))
            ctk.CTkLabel(card, textvariable=str_var, font=("Roboto", 13, "bold"), text_color=val_color).pack(anchor="w", padx=8, pady=(0, 4))

        add_metric_card(grid_frame, 0, 0, "Total Jugadores", self.res_total_players, "#f8fafc")
        add_metric_card(grid_frame, 0, 1, "Ingreso Bruto", self.res_gross, "#f8fafc")
        add_metric_card(grid_frame, 0, 2, "Pozo Neto Disponible", self.res_net, "#4ade80")
        add_metric_card(grid_frame, 0, 3, "Presupuesto Premios", self.res_budget, "#38bdf8")

        add_metric_card(grid_frame, 1, 0, "Valor Accesorios (Venta)", self.res_acc_sale, "#38bdf8")
        add_metric_card(grid_frame, 1, 1, "Costo Real Accesorios", self.res_acc_cost, "#fbbf24")
        add_metric_card(grid_frame, 1, 2, "Ganancia en Accesorios", self.res_acc_profit, "#4ade80")
        add_metric_card(grid_frame, 1, 3, "Sobres Asignados", self.res_packs, "#a78bfa")

        add_metric_card(grid_frame, 2, 0, "Costo Real Sobres", self.res_packs_cost, "#a78bfa")
        add_metric_card(grid_frame, 2, 1, "Ganancia en Sobres", self.res_packs_profit, "#4ade80")
        add_metric_card(grid_frame, 2, 2, "Costo Real Premios", self.res_total_prize_cost, "#f87171")
        add_metric_card(grid_frame, 2, 3, "Ganancia Real Tienda", self.res_real_profit, "#4ade80")

        # Alert banner
        self.alert_lbl = ctk.CTkLabel(fin_frame, textvariable=self.res_alert, font=UI_FONT_SMALL, text_color="#f59e0b", wraplength=700, justify="left")
        self.alert_lbl.pack(anchor="w", padx=15, pady=(2, 8))

        # Backward compatibility strings for 1st, 2nd, 3rd
        self.res_dist_1 = ctk.StringVar(value="")
        self.res_dist_2 = ctk.StringVar(value="")
        self.res_dist_3 = ctk.StringVar(value="")

        # Middle Right - Top Positions Configuration and Dynamic Slots
        top_ctrl_frame = ctk.CTkFrame(right_panel, fg_color="transparent")
        top_ctrl_frame.pack(fill="x", padx=15, pady=(5, 5))
        
        ctk.CTkLabel(top_ctrl_frame, text="Premios del Top y Asignación de Accesorios", font=("Roboto", 15, "bold"), text_color="#60a5fa").pack(side="left")
        
        ctk.CTkLabel(top_ctrl_frame, text="Corte del Top:", font=UI_FONT_SMALL, text_color="#cbd5e1").pack(side="left", padx=(25, 6))
        
        self.top_cut_menu = ctk.CTkOptionMenu(
            top_ctrl_frame,
            values=["Automático", "Top 2", "Top 3", "Top 4", "Top 8"],
            variable=self.top_cut_mode,
            command=lambda v: self.calculate_prizes(),
            font=UI_FONT_SMALL,
            width=130,
            height=28
        )
        self.top_cut_menu.pack(side="left")

        # Scrollable container for dynamic Top Slots
        self.slots_container = ctk.CTkScrollableFrame(right_panel, fg_color="#0f172a", corner_radius=8)
        self.slots_container.pack(fill="both", expand=True, padx=15, pady=5)

        # Bottom Action Button
        action_bar = ctk.CTkFrame(right_panel, fg_color="transparent")
        action_bar.pack(fill="x", padx=15, pady=10)
        
        self.assign_btn = ctk.CTkButton(
            action_bar, 
            text="ASIGNAR GANANCIA Y DESCONTAR STOCK DEL TORNEO", 
            command=self.assign_profit, 
            font=UI_FONT_BOLD, 
            fg_color="#eab308", 
            hover_color="#ca8a04", 
            text_color="black",
            height=38
        )
        self.assign_btn.pack(fill="x")

        # Initial render
        self.refresh_accessories_summary()
        self.calculate_prizes()

    def refresh_accessories_summary(self):
        items = self.acc_manager.load_accessories()
        total_items = len(items)
        total_stock = sum(it.get("stock", 0) for it in items)
        self.inv_summary_lbl.configure(text=f"{total_items} tipos de productos | Stock total: {total_stock} un.")
        self.refresh_pack_options()

    def refresh_pack_options(self):
        accessories = self.acc_manager.load_accessories()
        packs = [a for a in accessories if a.get("category") in ["Sobres", "Sobre"]]
        if not packs:
            packs = accessories

        options = []
        for p in packs:
            s_val = float(p.get("sale_price", p.get("cost", 0.0)))
            c_val = float(p.get("cost", 0.0))
            g_val = s_val - c_val
            g_str = f" (+${int(g_val):,} gan.)" if g_val > 0 else ""
            options.append(f"{p['name']} (Venta: ${int(s_val):,}{g_str} | Costo: ${int(c_val):,}) [Stock: {p.get('stock', 0)}]")

        self.pack_option_menu.configure(values=options)

        curr_selection = self.selected_pack_var.get()
        matched = False
        for opt in options:
            if opt == curr_selection:
                matched = True
                break
        
        if not matched and options:
            self.selected_pack_var.set(options[0])

    def get_selected_pack_item(self):
        accessories = self.acc_manager.load_accessories()
        curr = self.selected_pack_var.get()
        if not curr:
            packs = [a for a in accessories if a.get("category") in ["Sobres", "Sobre"]]
            return packs[0] if packs else (accessories[0] if accessories else None)

        for a in accessories:
            if a.get("name") in curr:
                return a
        
        packs = [a for a in accessories if a.get("category") in ["Sobres", "Sobre"]]
        return packs[0] if packs else (accessories[0] if accessories else None)

    def on_pack_selected(self, val):
        self.calculate_prizes()

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

    def determine_top_count(self, total_players):
        mode = self.top_cut_mode.get()
        if mode == "Top 2":
            return 2
        elif mode == "Top 3":
            return 3
        elif mode == "Top 4":
            return 4
        elif mode == "Top 8":
            return 8
        
        # Automático dinámico según jugadores:
        # Menos de 16 jugadores: Top 3 (o Top 2 si son <= 4)
        # 16 o más jugadores: Top 4 (o Top 8 si son >= 32)
        if total_players <= 4:
            return 2
        elif total_players < 16:
            return 3
        elif total_players < 32:
            return 4
        else:
            return 8

    def get_top_weights(self, count):
        if count == 2:
            return [0.70, 0.30]
        elif count == 3:
            return [0.50, 0.30, 0.20]
        elif count == 4:
            return [0.45, 0.25, 0.15, 0.15]
        elif count == 8:
            return [0.35, 0.20, 0.13, 0.12, 0.05, 0.05, 0.05, 0.05]
        else:
            return [1.0 / count] * count

    def distribute_packs(self, total_packs, weights):
        if total_packs <= 0 or not weights:
            return [0] * len(weights)
        if total_packs == 1:
            res = [0] * len(weights)
            res[0] = 1
            return res
        
        raw = [total_packs * w for w in weights]
        floors = [math.floor(r) for r in raw]
        remainder = total_packs - sum(floors)
        remainders = [(raw[i] - floors[i], i) for i in range(len(weights))]
        remainders.sort(key=lambda x: x[0], reverse=True)
        for k in range(remainder):
            floors[remainders[k][1]] += 1
        return floors

    def calculate_prizes(self):
        if self.updating_ui:
            return
            
        paid = self.get_val('paid_players', int, 0)
        invited = self.get_val('invited_players', int, 0)
        fee = self.get_val('entry_fee', float, 0.0)
        iva = self.get_val('iva_pct', float, 0.0)
        comm = self.get_val('commission_pct', float, 0.0)
        profit_margin = self.get_val('profit_margin_pct', float, 40.0)

        total_players = paid + invited
        gross_income = paid * fee

        # Net per entry: Entry / (1 + IVA/100) - Entry * (Comm/100)
        net_from_iva = fee / (1.0 + (iva / 100.0))
        comm_cost = fee * (comm / 100.0)
        net_fee = max(0.0, net_from_iva - comm_cost)
        total_net_income = net_fee * paid

        # Target profit & Prize budget
        desired_profit = total_net_income * (profit_margin / 100.0)
        prize_budget = max(0.0, total_net_income - desired_profit)

        # Selected pack item from inventory
        pack_item = self.get_selected_pack_item()
        if pack_item:
            pack_cost = float(pack_item.get("cost", 0.0))
            pack_sale = float(pack_item.get("sale_price", pack_cost))
            pack_stock = int(pack_item.get("stock", 0))
            pack_profit_unit = pack_sale - pack_cost
            pack_name = pack_item.get("name", "Sobre")
        else:
            pack_cost = 0.0
            pack_sale = 0.0
            pack_stock = 0
            pack_profit_unit = 0.0
            pack_name = "Sobre"

        if hasattr(self, 'pack_info_lbl'):
            self.pack_info_lbl.configure(
                text=f"Venta: ${int(pack_sale):,} | Costo: ${int(pack_cost):,} | Ganancia: +${int(pack_profit_unit):,} c/u\nStock disponible: {pack_stock} sobres"
            )

        # Determine Top Slots Count
        top_count = self.determine_top_count(total_players)

        # Build / Rebuild top slot UI widgets if count changed
        self.rebuild_top_slots(top_count)

        # Load inventory accessories
        accessories = self.acc_manager.load_accessories()
        acc_dict = {a["id"]: a for a in accessories}

        # Calculate cost and sale value of selected accessories
        total_acc_cost = 0.0
        total_acc_sale = 0.0
        selected_counts = {}
        for idx in range(top_count):
            item_id = self.slot_accessory_vars.get(idx, ctk.StringVar(value="none")).get()
            if item_id and item_id != "none" and item_id in acc_dict:
                acc_it = acc_dict[item_id]
                c_val = float(acc_it.get("cost", 0.0))
                s_val = float(acc_it.get("sale_price", c_val))
                total_acc_cost += c_val
                total_acc_sale += s_val
                selected_counts[item_id] = selected_counts.get(item_id, 0) + 1

        total_acc_profit = total_acc_sale - total_acc_cost

        # El presupuesto del evento descuenta los accesorios a su PRECIO DE VENTA
        remaining_budget = max(0.0, prize_budget - total_acc_sale)

        # Cantidad de sobres financiada por el presupuesto remanente (al valor de venta comercial del sobre)
        if pack_sale > 0:
            total_packs = math.floor(remaining_budget / pack_sale)
        elif pack_cost > 0:
            total_packs = math.floor(remaining_budget / pack_cost)
        else:
            total_packs = 0

        total_packs_cost = total_packs * pack_cost
        total_packs_profit = total_packs * pack_profit_unit
        total_real_prize_cost = total_acc_cost + total_packs_cost
        real_profit = total_net_income - total_real_prize_cost
        real_profit_pct = (real_profit / total_net_income * 100.0) if total_net_income > 0 else 0.0

        # Update metrics display
        self.res_total_players.set(f"{total_players} ({paid} pag., {invited} inv.)")
        self.res_gross.set(f"${int(round(gross_income)):,}")
        self.res_net.set(f"${int(round(total_net_income)):,}")
        self.res_budget.set(f"${int(round(prize_budget)):,}")
        self.res_acc_sale.set(f"${int(round(total_acc_sale)):,}")
        self.res_acc_cost.set(f"${int(round(total_acc_cost)):,}")
        self.res_acc_profit.set(f"+${int(round(total_acc_profit)):,}")
        self.res_packs.set(f"{total_packs} sobres")
        self.res_packs_cost.set(f"${int(round(total_packs_cost)):,}")
        self.res_packs_profit.set(f"+${int(round(total_packs_profit)):,}")
        self.res_total_prize_cost.set(f"${int(round(total_real_prize_cost)):,}")
        self.res_real_profit.set(f"${int(round(real_profit)):,} ({real_profit_pct:.1f}%)")

        # Retail Pack Price suggestion from inventory
        self.res_pack_price.set(f"Sobre: {pack_name} | Venta: ${int(pack_sale):,} | Costo: ${int(pack_cost):,} (Margen: +${int(pack_profit_unit):,})")

        # Distribute remaining packs among top positions
        weights = self.get_top_weights(top_count)
        packs_distribution = self.distribute_packs(total_packs, weights)

        # Warnings / Alerts
        alerts = []
        if total_acc_sale > prize_budget:
            diff = total_acc_sale - prize_budget
            alerts.append(f"⚠️ El valor venta de los accesorios (${int(round(total_acc_sale)):,}) excede el presupuesto por ${int(round(diff)):,}. La ganancia de la tienda bajará a {real_profit_pct:.1f}%.")
        
        # Stock check for packs
        if pack_item and total_packs > pack_stock:
            alerts.append(f"⚠️ Stock insuficiente de sobres: Se requieren {total_packs} sobres de '{pack_name}', pero solo hay {pack_stock} en inventario.")

        # Stock check for accessories
        for item_id, requested_qty in selected_counts.items():
            item = acc_dict.get(item_id)
            if item:
                curr_stock = item.get("stock", 0)
                if requested_qty > curr_stock:
                    alerts.append(f"⚠️ Stock insuficiente: '{item.get('name')}' seleccionado {requested_qty} vez/veces (Stock disponible: {curr_stock}).")

        if not alerts:
            if total_packs > 0:
                alerts.append(f"✅ Presupuesto cubierto. Saldo remanente asigna {total_packs} sobres extras ({pack_name}) entre el Top.")
            else:
                alerts.append("✅ Premios calculados dentro del presupuesto y margen objetivo.")

        self.res_alert.set(" | ".join(alerts))
        self.alert_lbl.configure(text_color="#f59e0b" if any("⚠️" in a for a in alerts) else "#4ade80")
        
        # Stock check
        for item_id, requested_qty in selected_counts.items():
            item = acc_dict.get(item_id)
            if item:
                curr_stock = item.get("stock", 0)
                if requested_qty > curr_stock:
                    alerts.append(f"⚠️ Stock insuficiente: '{item.get('name')}' seleccionado {requested_qty} vez/veces (Stock disponible: {curr_stock}).")

        if not alerts:
            if total_packs > 0:
                alerts.append(f"✅ Presupuesto cubierto. Saldo remanente asigna {total_packs} sobres extras entre el Top.")
            else:
                alerts.append("✅ Premios calculados dentro del presupuesto y margen objetivo.")

        self.res_alert.set(" | ".join(alerts))
        self.alert_lbl.configure(text_color="#f59e0b" if any("⚠️" in a for a in alerts) else "#4ade80")

        # Update Slot Widgets
        top_descriptions = []
        for idx in range(top_count):
            packs_for_slot = packs_distribution[idx] if idx < len(packs_distribution) else 0
            item_id = self.slot_accessory_vars.get(idx, ctk.StringVar(value="none")).get()
            item = acc_dict.get(item_id) if (item_id in acc_dict and item_id != "none") else None

            # Combined string
            parts = []
            if item:
                s_val = float(item.get("sale_price", item.get("cost", 0.0)))
                c_val = float(item.get("cost", 0.0))
                g_val = s_val - c_val
                gain_info = f" (+${int(g_val):,} gan.)" if g_val > 0 else ""
                parts.append(f"{item['name']} [Valor Venta: ${int(s_val):,}{gain_info}]")
            if packs_for_slot > 0:
                parts.append(f"{packs_for_slot} sobre{'s' if packs_for_slot > 1 else ''}")
            
            prize_txt = " + ".join(parts) if parts else "Sin premio adicional"
            top_descriptions.append(f"{self.ordinal(idx+1)} Lugar: {prize_txt}")

            if idx < len(self.slot_widgets):
                w = self.slot_widgets[idx]
                w['packs_lbl'].configure(text=f"+ {packs_for_slot} Sobres" if packs_for_slot > 0 else "")
                w['summary_lbl'].configure(text=prize_txt)

        # Backward compatibility strings
        self.res_dist_1.set(top_descriptions[0] if len(top_descriptions) > 0 else "")
        self.res_dist_2.set(top_descriptions[1] if len(top_descriptions) > 1 else "")
        self.res_dist_3.set(top_descriptions[2] if len(top_descriptions) > 2 else "")

        if self.prize_groups:
            self.apply_grouped_distribution(packs_distribution)

    def format_accessory_menu_label(self, a):
        sale = float(a.get("sale_price", a.get("cost", 0.0)))
        cost = float(a.get("cost", 0.0))
        stock = a.get("stock", 0)
        profit = sale - cost
        profit_str = f" (+${int(profit):,} gan.)" if profit > 0 else ""
        return f"{a['name']} (Venta: ${int(sale):,}{profit_str} | Costo: ${int(cost):,}) [Stock: {stock}]"

    def rebuild_top_slots(self, top_count):
        if len(self.slot_widgets) == top_count:
            # Just refresh option menus in case stock or accessories changed
            self.refresh_slot_options()
            return

        # Clear existing
        for widget_dict in self.slot_widgets:
            widget_dict['frame'].destroy()
        self.slot_widgets.clear()

        # Build accessories menu options
        accessories = self.acc_manager.load_accessories()
        options = ["(Ninguno - Solo Sobres)"]
        for a in accessories:
            options.append(self.format_accessory_menu_label(a))

        for idx in range(top_count):
            rank = idx + 1
            if idx not in self.slot_accessory_vars:
                self.slot_accessory_vars[idx] = ctk.StringVar(value="none")

            row_frame = ctk.CTkFrame(self.slots_container, fg_color="#1e293b", corner_radius=6)
            row_frame.pack(fill="x", padx=10, pady=4)

            # Rank label with badge styling
            badge_color = "#fbbf24" if rank == 1 else ("#9ca3af" if rank == 2 else ("#b45309" if rank == 3 else "#38bdf8"))
            rank_lbl = ctk.CTkLabel(row_frame, text=f"{self.ordinal(rank)} Lugar", font=("Roboto", 13, "bold"), text_color=badge_color, width=90, anchor="w")
            rank_lbl.pack(side="left", padx=(10, 5), pady=8)

            # OptionMenu for Accessory
            opt_menu = ctk.CTkOptionMenu(
                row_frame,
                values=options,
                command=lambda val, slot=idx: self.on_accessory_selected(slot, val),
                font=UI_FONT_SMALL,
                width=290,
                height=28
            )
            opt_menu.pack(side="left", padx=5, pady=8)

            # Packs label
            packs_lbl = ctk.CTkLabel(row_frame, text="", font=UI_FONT_BOLD, text_color="#a78bfa", width=85, anchor="w")
            packs_lbl.pack(side="left", padx=5)

            # Summary label
            summary_lbl = ctk.CTkLabel(row_frame, text="", font=UI_FONT_SMALL, text_color="#cbd5e1", anchor="w")
            summary_lbl.pack(side="left", padx=10, fill="x", expand=True)

            self.slot_widgets.append({
                'frame': row_frame,
                'opt_menu': opt_menu,
                'packs_lbl': packs_lbl,
                'summary_lbl': summary_lbl,
                'rank': rank
            })

            # Set current value if previously chosen
            curr_item_id = self.slot_accessory_vars[idx].get()
            self.set_menu_to_item(opt_menu, curr_item_id, accessories)

    def refresh_slot_options(self):
        accessories = self.acc_manager.load_accessories()
        options = ["(Ninguno - Solo Sobres)"]
        for a in accessories:
            options.append(self.format_accessory_menu_label(a))

        for idx, w in enumerate(self.slot_widgets):
            w['opt_menu'].configure(values=options)
            curr_item_id = self.slot_accessory_vars.get(idx, ctk.StringVar(value="none")).get()
            self.set_menu_to_item(w['opt_menu'], curr_item_id, accessories)

    def set_menu_to_item(self, menu, item_id, accessories):
        if not item_id or item_id == "none":
            menu.set("(Ninguno - Solo Sobres)")
            return
        for a in accessories:
            if a.get("id") == item_id:
                menu.set(self.format_accessory_menu_label(a))
                return
        menu.set("(Ninguno - Solo Sobres)")

    def on_accessory_selected(self, slot_idx, display_value):
        if display_value == "(Ninguno - Solo Sobres)":
            self.slot_accessory_vars[slot_idx].set("none")
        else:
            accessories = self.acc_manager.load_accessories()
            found_id = "none"
            for a in accessories:
                if self.format_accessory_menu_label(a) == display_value or a['name'] in display_value:
                    found_id = a['id']
                    break
            self.slot_accessory_vars[slot_idx].set(found_id)
        
        self.calculate_prizes()

    def open_inventory_modal(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Inventario de Accesorios (HunterCard TCG) - Costos y Precios de Venta")
        dialog.geometry("900x640")
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.focus_set()
        dialog.attributes('-topmost', True)

        ctk.CTkLabel(dialog, text="Gestión de Accesorios, Costos y Precios de Venta", font=("Roboto", 18, "bold"), text_color="#38bdf8").pack(pady=(12, 2))
        ctk.CTkLabel(dialog, text="Define el precio de costo y venta. La ganancia en accesorios incrementa el margen final de la tienda.", font=UI_FONT_SMALL, text_color="#94a3b8").pack(pady=(0, 10))

        # Encabezado de la tabla
        header_frame = ctk.CTkFrame(dialog, fg_color="#1e293b", corner_radius=6, height=32)
        header_frame.pack(fill="x", padx=20, pady=(0, 4))
        
        ctk.CTkLabel(header_frame, text="Nombre del Producto", font=("Roboto", 11, "bold"), text_color="#94a3b8", width=220, anchor="w").pack(side="left", padx=10)
        ctk.CTkLabel(header_frame, text="Categoría", font=("Roboto", 11, "bold"), text_color="#94a3b8", width=95, anchor="w").pack(side="left", padx=5)
        ctk.CTkLabel(header_frame, text="Costo ($)", font=("Roboto", 11, "bold"), text_color="#94a3b8", width=75, anchor="e").pack(side="left", padx=5)
        ctk.CTkLabel(header_frame, text="Venta ($)", font=("Roboto", 11, "bold"), text_color="#94a3b8", width=75, anchor="e").pack(side="left", padx=5)
        ctk.CTkLabel(header_frame, text="Ganancia", font=("Roboto", 11, "bold"), text_color="#94a3b8", width=95, anchor="e").pack(side="left", padx=5)
        ctk.CTkLabel(header_frame, text="Stock", font=("Roboto", 11, "bold"), text_color="#94a3b8", width=120, anchor="center").pack(side="left", padx=5)
        ctk.CTkLabel(header_frame, text="Acciones", font=("Roboto", 11, "bold"), text_color="#94a3b8", width=85, anchor="center").pack(side="right", padx=10)

        list_frame = ctk.CTkScrollableFrame(dialog, fg_color="#0f172a", height=280)
        list_frame.pack(fill="x", padx=20, pady=2)

        def open_edit_dialog(item):
            edit_win = ctk.CTkToplevel(dialog)
            edit_win.title(f"Editar - {item.get('name')}")
            edit_win.geometry("450x420")
            edit_win.resizable(False, False)
            edit_win.grab_set()
            edit_win.focus_set()
            edit_win.attributes('-topmost', True)

            ctk.CTkLabel(edit_win, text="Modificar Precios y Stock", font=("Roboto", 16, "bold"), text_color="#38bdf8").pack(pady=12)

            form_box = ctk.CTkFrame(edit_win, fg_color="#1e293b", corner_radius=8)
            form_box.pack(fill="both", expand=True, padx=20, pady=5)

            def add_form_row(parent, label_text):
                f = ctk.CTkFrame(parent, fg_color="transparent")
                f.pack(fill="x", padx=12, pady=4)
                lbl = ctk.CTkLabel(f, text=label_text, font=UI_FONT_SMALL, text_color="#cbd5e1", width=110, anchor="w")
                lbl.pack(side="left")
                entry = ctk.CTkEntry(f, font=UI_FONT_SMALL)
                entry.pack(side="left", fill="x", expand=True)
                return entry

            e_name = add_form_row(form_box, "Nombre:")
            e_name.insert(0, item.get('name', ''))

            # Categoría
            f_cat = ctk.CTkFrame(form_box, fg_color="transparent")
            f_cat.pack(fill="x", padx=12, pady=4)
            ctk.CTkLabel(f_cat, text="Categoría:", font=UI_FONT_SMALL, text_color="#cbd5e1", width=110, anchor="w").pack(side="left")
            e_cat = ctk.CTkOptionMenu(f_cat, values=["Sobres", "Carpetas", "Deck Box", "Porta Playmat", "Protectores", "Otro"], font=UI_FONT_SMALL)
            if item.get('category') in ["Sobres", "Carpetas", "Deck Box", "Porta Playmat", "Protectores", "Otro"]:
                e_cat.set(item.get('category'))
            e_cat.pack(side="left", fill="x", expand=True)

            e_cost = add_form_row(form_box, "Precio Costo ($):")
            e_cost.insert(0, str(int(item.get('cost', 0))))

            curr_sale = item.get('sale_price', item.get('cost', 0))
            e_sale = add_form_row(form_box, "Precio Venta ($):")
            e_sale.insert(0, str(int(curr_sale)))

            e_stock = add_form_row(form_box, "Stock disponible:")
            e_stock.insert(0, str(int(item.get('stock', 0))))

            preview_lbl = ctk.CTkLabel(form_box, text="", font=UI_FONT_BOLD, text_color="#4ade80")
            preview_lbl.pack(pady=8)

            def update_edit_preview(*args):
                try:
                    c_txt = e_cost.get().strip().replace("$", "").replace(".", "").replace(",", "")
                    s_txt = e_sale.get().strip().replace("$", "").replace(".", "").replace(",", "")
                    c = float(c_txt) if c_txt else 0.0
                    s = float(s_txt) if s_txt else c
                    profit = s - c
                    margin = (profit / s * 100.0) if s > 0 else 0.0
                    if profit >= 0:
                        preview_lbl.configure(text=f"Ganancia: +${int(round(profit)):,} ({margin:.1f}% margen)", text_color="#4ade80")
                    else:
                        preview_lbl.configure(text=f"Pérdida: -${int(round(abs(profit))):,} (Venta bajo costo)", text_color="#f87171")
                except Exception:
                    preview_lbl.configure(text="")

            e_cost.bind("<KeyRelease>", update_edit_preview)
            e_sale.bind("<KeyRelease>", update_edit_preview)
            update_edit_preview()

            def save_edit():
                try:
                    name = e_name.get().strip() or item.get('name')
                    cat = e_cat.get()
                    c = float(e_cost.get().strip().replace("$", "").replace(".", "").replace(",", ""))
                    s = float(e_sale.get().strip().replace("$", "").replace(".", "").replace(",", ""))
                    stk = int(e_stock.get().strip())
                    self.acc_manager.update_accessory(item['id'], name=name, cost=c, sale_price=s, stock=stk, category=cat)
                    edit_win.destroy()
                    render_inventory_list()
                    self.refresh_accessories_summary()
                    self.refresh_slot_options()
                    self.calculate_prizes()
                except Exception as ex:
                    print("Error saving item edit:", ex)

            btn_box = ctk.CTkFrame(edit_win, fg_color="transparent")
            btn_box.pack(fill="x", padx=20, pady=10)
            ctk.CTkButton(btn_box, text="Guardar Cambios", fg_color="#10b981", hover_color="#059669", font=UI_FONT_BOLD, command=save_edit).pack(side="left", fill="x", expand=True, padx=4)
            ctk.CTkButton(btn_box, text="Cancelar", fg_color="#475569", font=UI_FONT_SMALL, command=edit_win.destroy).pack(side="right", padx=4)

        def render_inventory_list():
            for child in list_frame.winfo_children():
                child.destroy()

            accessories = self.acc_manager.load_accessories()
            if not accessories:
                ctk.CTkLabel(list_frame, text="No hay accesorios registrados.", text_color="#94a3b8").pack(pady=20)
                return

            for item in accessories:
                row = ctk.CTkFrame(list_frame, fg_color="#1e293b", corner_radius=6)
                row.pack(fill="x", pady=2, padx=5)

                name_lbl = ctk.CTkLabel(row, text=item.get('name', ''), font=UI_FONT_BOLD, width=220, anchor="w")
                name_lbl.pack(side="left", padx=10, pady=6)

                cat_lbl = ctk.CTkLabel(row, text=f"[{item.get('category', 'Accesorios')}]", font=UI_FONT_SMALL, text_color="#38bdf8", width=95, anchor="w")
                cat_lbl.pack(side="left", padx=5)

                cost_val = float(item.get('cost', 0))
                sale_val = float(item.get('sale_price', cost_val))
                profit_val = sale_val - cost_val

                cost_lbl = ctk.CTkLabel(row, text=f"${int(cost_val):,}", font=UI_FONT_SMALL, text_color="#cbd5e1", width=75, anchor="e")
                cost_lbl.pack(side="left", padx=5)

                sale_lbl = ctk.CTkLabel(row, text=f"${int(sale_val):,}", font=UI_FONT_BOLD, text_color="#38bdf8", width=75, anchor="e")
                sale_lbl.pack(side="left", padx=5)

                profit_color = "#4ade80" if profit_val > 0 else ("#94a3b8" if profit_val == 0 else "#f87171")
                profit_txt = f"+${int(profit_val):,}" if profit_val > 0 else (f"-${int(abs(profit_val)):,}" if profit_val < 0 else "$0")
                profit_lbl = ctk.CTkLabel(row, text=profit_txt, font=UI_FONT_BOLD, text_color=profit_color, width=95, anchor="e")
                profit_lbl.pack(side="left", padx=5)

                stock_val = ctk.StringVar(value=f"{item.get('stock', 0)}")
                
                def make_adjust(i_id, delta, s_var):
                    new_s = self.acc_manager.adjust_stock(i_id, delta)
                    if new_s is not None:
                        s_var.set(f"{new_s}")
                    self.refresh_accessories_summary()
                    self.refresh_slot_options()
                    self.calculate_prizes()

                stock_frame = ctk.CTkFrame(row, fg_color="transparent", width=120)
                stock_frame.pack(side="left", padx=5)

                btn_minus = ctk.CTkButton(stock_frame, text="-", width=24, height=24, fg_color="#334155", 
                                          command=lambda i_id=item['id'], s_var=stock_val: make_adjust(i_id, -1, s_var))
                btn_minus.pack(side="left", padx=2)

                stock_lbl = ctk.CTkLabel(stock_frame, textvariable=stock_val, font=UI_FONT_BOLD, text_color="#fbbf24", width=35)
                stock_lbl.pack(side="left", padx=2)

                btn_plus = ctk.CTkButton(stock_frame, text="+", width=24, height=24, fg_color="#334155",
                                         command=lambda i_id=item['id'], s_var=stock_val: make_adjust(i_id, 1, s_var))
                btn_plus.pack(side="left", padx=2)

                # Acciones a la derecha
                act_frame = ctk.CTkFrame(row, fg_color="transparent")
                act_frame.pack(side="right", padx=8)

                def delete_item(i_id):
                    self.acc_manager.delete_accessory(i_id)
                    render_inventory_list()
                    self.refresh_accessories_summary()
                    self.refresh_slot_options()
                    self.calculate_prizes()

                btn_del = ctk.CTkButton(act_frame, text="✕", width=26, height=26, fg_color="#ef4444", hover_color="#dc2626",
                                        command=lambda i_id=item['id']: delete_item(i_id))
                btn_del.pack(side="right", padx=2)

                btn_edit = ctk.CTkButton(act_frame, text="✏️", width=28, height=26, fg_color="#3b82f6", hover_color="#2563eb",
                                         command=lambda it=item: open_edit_dialog(it))
                btn_edit.pack(side="right", padx=4)

        render_inventory_list()

        # Add New Item Form
        form_frame = ctk.CTkFrame(dialog, fg_color="#1e293b", corner_radius=8)
        form_frame.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(form_frame, text="Agregar Nuevo Accesorio al Inventario", font=("Roboto", 13, "bold"), text_color="#60a5fa").pack(anchor="w", padx=12, pady=(8, 2))

        fields_row = ctk.CTkFrame(form_frame, fg_color="transparent")
        fields_row.pack(fill="x", padx=12, pady=4)

        name_entry = ctk.CTkEntry(fields_row, placeholder_text="Nombre (ej. Deck Box Premium)", font=UI_FONT_SMALL, width=210)
        name_entry.pack(side="left", padx=(0, 4))

        cost_entry = ctk.CTkEntry(fields_row, placeholder_text="Costo ($)", font=UI_FONT_SMALL, width=90)
        cost_entry.pack(side="left", padx=4)

        sale_entry = ctk.CTkEntry(fields_row, placeholder_text="Venta ($)", font=UI_FONT_SMALL, width=90)
        sale_entry.pack(side="left", padx=4)

        stock_entry = ctk.CTkEntry(fields_row, placeholder_text="Stock", font=UI_FONT_SMALL, width=60)
        stock_entry.insert(0, "1")
        stock_entry.pack(side="left", padx=4)

        cat_entry = ctk.CTkOptionMenu(fields_row, values=["Sobres", "Carpetas", "Deck Box", "Porta Playmat", "Protectores", "Otro"], font=UI_FONT_SMALL, width=115)
        cat_entry.pack(side="left", padx=4)

        profit_preview_lbl = ctk.CTkLabel(form_frame, text="Ganancia estimada: +$0", font=UI_FONT_SMALL, text_color="#4ade80")
        profit_preview_lbl.pack(anchor="w", padx=12, pady=(0, 6))

        def update_add_preview(*args):
            try:
                c_str = cost_entry.get().strip().replace("$", "").replace(".", "").replace(",", "")
                s_str = sale_entry.get().strip().replace("$", "").replace(".", "").replace(",", "")
                c = float(c_str) if c_str else 0.0
                s = float(s_str) if s_str else c
                profit = s - c
                margin = (profit / s * 100.0) if s > 0 else 0.0
                if profit > 0:
                    profit_preview_lbl.configure(text=f"Ganancia estimada: +${int(round(profit)):,} ({margin:.1f}% margen para la tienda)", text_color="#4ade80")
                elif profit == 0:
                    profit_preview_lbl.configure(text="Ganancia estimada: $0 (Venta al mismo costo)", text_color="#94a3b8")
                else:
                    profit_preview_lbl.configure(text=f"⚠️ Venta bajo costo: -${int(round(abs(profit))):,}", text_color="#f87171")
            except Exception:
                profit_preview_lbl.configure(text="")

        cost_entry.bind("<KeyRelease>", update_add_preview)
        sale_entry.bind("<KeyRelease>", update_add_preview)

        def add_new():
            name = name_entry.get().strip()
            if not name:
                return
            try:
                cost = float(cost_entry.get().strip().replace("$", "").replace(".", "").replace(",", ""))
            except ValueError:
                cost = 0.0
            try:
                sale = float(sale_entry.get().strip().replace("$", "").replace(".", "").replace(",", ""))
            except ValueError:
                sale = cost
            try:
                stock = int(stock_entry.get().strip())
            except ValueError:
                stock = 1
            cat = cat_entry.get()

            self.acc_manager.add_accessory(name, cost, sale_price=sale, stock=stock, category=cat)
            name_entry.delete(0, 'end')
            cost_entry.delete(0, 'end')
            sale_entry.delete(0, 'end')
            stock_entry.delete(0, 'end')
            stock_entry.insert(0, "1")
            update_add_preview()

            render_inventory_list()
            self.refresh_accessories_summary()
            self.refresh_slot_options()
            self.calculate_prizes()

        btn_add = ctk.CTkButton(fields_row, text="➕ Agregar", font=UI_FONT_SMALL, fg_color="#10b981", hover_color="#059669", width=85, command=add_new)
        btn_add.pack(side="left", padx=4)

        close_btn = ctk.CTkButton(dialog, text="Cerrar", font=UI_FONT_SMALL, width=120, command=dialog.destroy)
        close_btn.pack(pady=(4, 10))

    def assign_profit(self):
        import custom_alerts as messagebox
        try:
            total_net_str = self.res_net.get().replace("$","").replace(".","").replace(",","")
            total_net = float(total_net_str) if total_net_str else 0.0

            real_profit_str = self.res_real_profit.get().split()[0].replace("$","").replace(".","").replace(",","")
            real_profit = float(real_profit_str) if real_profit_str else 0.0

            packs_str = self.res_packs.get().split()[0]
            total_packs = int(packs_str) if packs_str.isdigit() else 0

            # Gather selected accessories to deduct
            accessories = self.acc_manager.load_accessories()
            acc_dict = {a["id"]: a for a in accessories}
            
            selected_ids = []
            selected_summary = []
            selected_details = []
            total_acc_sale = 0.0
            total_acc_cost = 0.0

            top_count = len(self.slot_widgets)
            for idx in range(top_count):
                i_id = self.slot_accessory_vars.get(idx, ctk.StringVar(value="none")).get()
                if i_id and i_id != "none" and i_id in acc_dict:
                    acc_it = acc_dict[i_id]
                    c_val = float(acc_it.get("cost", 0.0))
                    s_val = float(acc_it.get("sale_price", c_val))
                    g_val = s_val - c_val
                    total_acc_cost += c_val
                    total_acc_sale += s_val
                    selected_ids.append(i_id)
                    selected_summary.append(f"{self.ordinal(idx+1)} Lugar: {acc_it['name']}")
                    gain_str = f" (+${int(g_val):,} gan.)" if g_val > 0 else ""
                    selected_details.append(f"  • {self.ordinal(idx+1)} Lugar: {acc_it['name']} [Venta: ${int(s_val):,}{gain_str} | Costo: ${int(c_val):,}]")

            total_acc_profit = total_acc_sale - total_acc_cost

            pack_item = self.get_selected_pack_item()
            pack_stock = int(pack_item.get("stock", 0)) if pack_item else 0
            pack_name = pack_item.get("name", "Sobre") if pack_item else "Sobre"
            packs_cost_str = self.res_packs_cost.get().replace("$","").replace(".","").replace(",","")
            packs_cost = float(packs_cost_str) if packs_cost_str else 0.0
            packs_profit_str = self.res_packs_profit.get().replace("$","").replace(".","").replace(",","").replace("+","")
            packs_profit = float(packs_profit_str) if packs_profit_str else 0.0

            confirm_msg = (
                f"¿Confirmar entrega de premios y balance financiero del torneo?\n\n"
                f"📊 BALANCE FINANCIERO:\n"
                f"• Pozo Neto: ${int(round(total_net)):,}\n"
                f"• Valor Comercial Accesorios (Venta): ${int(round(total_acc_sale)):,}\n"
                f"• Costo Real Accesorios: ${int(round(total_acc_cost)):,}\n"
                f"• Ganancia Tienda por Accesorios: +${int(round(total_acc_profit)):,}\n"
                f"• Sobres Extras Asignados: {total_packs} sobres ({pack_name})\n"
                f"• Costo Real Sobres: ${int(round(packs_cost)):,}\n"
                f"• Ganancia Tienda en Sobres: +${int(round(packs_profit)):,}\n"
                f"• Costo Real Total Premios: ${int(round(total_acc_cost + packs_cost)):,}\n"
                f"💰 GANANCIA FINAL REAL TIENDA: ${int(round(real_profit)):,}\n\n"
            )
            if selected_details:
                confirm_msg += f"📦 Accesorios a descontar del stock ({len(selected_ids)} un.):\n" + "\n".join(selected_details) + "\n"
            else:
                confirm_msg += "📦 Sin accesorios asignados (solo sobres).\n"
            if total_packs > 0 and pack_item:
                confirm_msg += f"🃏 Sobres a descontar del stock: {total_packs} un. de '{pack_name}' (Stock restante: {max(0, pack_stock - total_packs)})\n"

            if not messagebox.askyesno("Confirmar Entrega de Premios", confirm_msg):
                return

            # Deduct accessories from inventory
            if selected_ids:
                self.acc_manager.deduct_accessories(selected_ids)

            # Deduct packs from inventory
            if total_packs > 0 and pack_item:
                self.acc_manager.adjust_stock(pack_item["id"], -total_packs)

            self.refresh_accessories_summary()
            self.refresh_slot_options()

            from database import get_connection
            from store_manager import StoreManager
            import json

            msg_parts = []

            # 1. Update in-memory tournament if active
            manager = None
            if hasattr(self.master, 'tournament_frame') and self.master.tournament_frame:
                manager = getattr(self.master.tournament_frame, 'manager', None)

            if manager and len(manager.players) > 0:
                manager.tournament_profit = real_profit
                manager.total_packs_given = total_packs
                manager.total_acc_sale = total_acc_sale
                manager.total_acc_cost = total_acc_cost
                manager.total_acc_profit = total_acc_profit
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
                                data["manager"]["tournament_profit"] = real_profit
                                data["manager"]["total_packs_given"] = total_packs
                                data["manager"]["total_acc_sale"] = total_acc_sale
                                data["manager"]["total_acc_cost"] = total_acc_cost
                                data["manager"]["total_acc_profit"] = total_acc_profit
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
                        cursor.execute("UPDATE tournaments SET profit = ? WHERE id = (SELECT id FROM tournaments WHERE store_id = ? ORDER BY id DESC LIMIT 1)", (real_profit, store_id))
                        conn.commit()
                        msg_parts.append(f"- Guardado en la base de datos de la tienda '{store_name}'.")
                    conn.close()
                except Exception as e:
                    print("Error DB:", e)
            else:
                msg_parts.append("- (No hay tienda activa para guardar en BD).")

            if selected_ids:
                msg_parts.append(f"- Descontados {len(selected_ids)} accesorio(s) del stock.")
            if total_packs > 0 and pack_item:
                msg_parts.append(f"- Descontados {total_packs} sobre(s) de '{pack_name}' del stock.")

            final_msg = "Éxito al asignar ganancias y premios:\n\n" + "\n".join(msg_parts)
            messagebox.showinfo("Éxito", final_msg)
            self.calculate_prizes()

        except Exception as e:
            messagebox.showerror("Error", f"No se pudo asignar la ganancia: {e}")

    def apply_grouped_distribution(self, position_prizes):
        lines = []
        assigned_slots = 0

        for group in self.prize_groups[:3]:
            rank = int(group.get("rank", assigned_slots + 1))
            count = max(1, int(group.get("count", 1)))
            start = rank - 1
            end = start + count
            pool = sum(position_prizes[start:end]) if end <= len(position_prizes) else 0
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
        if rank == 4:
            return "4to"
        if rank == 5:
            return "5to"
        if rank == 6:
            return "6to"
        if rank == 7:
            return "7mo"
        if rank == 8:
            return "8vo"
        return f"{rank}to"

# Backward compatibility alias
PrizeCalculator = PrizeCalculatorUI
