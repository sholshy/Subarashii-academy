import sys

with open('prize_calculator_ui.py', 'r', encoding='utf-8') as f:
    content = f.read()

target_ui = """        self.assign_btn = ctk.CTkButton(right_panel, text="ASIGNAR GANANCIA AL TORNEO", command=self.assign_profit, font=UI_FONT, fg_color="#eab308", hover_color="#ca8a04", text_color="black")
        self.assign_btn.pack(pady=20)"""

replacement_ui = """        pack_price_frame = ctk.CTkFrame(right_panel, fg_color="#334155")
        pack_price_frame.pack(fill="x", padx=20, pady=(0, 20))
        self.res_pack_price = ctk.StringVar(value="Precio Sugerido Venta 1 Sobre: $0")
        ctk.CTkLabel(pack_price_frame, textvariable=self.res_pack_price, font=("Roboto", 14, "bold"), text_color="#2dd4bf").pack(pady=10)

        self.assign_btn = ctk.CTkButton(right_panel, text="ASIGNAR GANANCIA AL TORNEO", command=self.assign_profit, font=UI_FONT, fg_color="#eab308", hover_color="#ca8a04", text_color="black")
        self.assign_btn.pack(pady=20)"""

content = content.replace(target_ui, replacement_ui)

target_calc = """        self.res_packs.set(f"{total_packs} sobres")"""

replacement_calc = """        self.res_packs.set(f"{total_packs} sobres")
        
        target_net = base_pack_cost * (1 + (profit_margin / 100))
        divisor = (1 / (1 + (iva / 100))) - (comm / 100)
        import math
        if divisor > 0 and target_net > 0:
            suggested_price_raw = target_net / divisor
            suggested_price = math.ceil(suggested_price_raw / 500.0) * 500
        else:
            suggested_price = 0
        self.res_pack_price.set(f"Precio Sugerido Venta 1 Sobre: ${int(suggested_price):,}")"""

content = content.replace(target_calc, replacement_calc)

with open('prize_calculator_ui.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patch applied")
