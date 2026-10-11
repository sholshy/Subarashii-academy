import tkinter as tk
import customtkinter as ctk
import custom_alerts as messagebox
from PIL import Image, ImageTk
import os
import time

from ygo_api import YgoApi

UI_FONT = ("Roboto", 13)
UI_FONT_BIG = ("Orbitron Black", 24)
UI_FONT_SMALL = ("Roboto", 11)

class DeckEditorUI(ctk.CTkFrame):
    def __init__(self, parent, go_back_callback, on_confirm_callback):
        super().__init__(parent, fg_color="#0f172a")
        self.go_back_callback = go_back_callback
        self.on_confirm_callback = on_confirm_callback
        
        self.current_format = tk.StringVar(value="GOAT")
        self.db_cards = []
        self.filtered_cards = []
        
        # Decks: lists of card dicts
        self.main_deck = []
        self.extra_deck = []
        self.side_deck = []
        
        # Active target (Main, Extra, Side) - usually auto-detected, but useful for forcing
        self.active_zone = "Main" 

        # Image cache references so they don't get garbage collected
        self.image_refs = {}
        
        self.setup_ui()
        self.load_database()
        
    def setup_ui(self):
        # --- TOP BAR ---
        top_bar = ctk.CTkFrame(self, fg_color="transparent", height=50)
        top_bar.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkButton(top_bar, text="< VOLVER", width=80, font=UI_FONT, command=self.go_back_callback).pack(side="left")
        
        ctk.CTkLabel(top_bar, text="DECK EDITOR", font=UI_FONT_BIG, text_color="#60a5fa").pack(side="left", expand=True)
        
        ctk.CTkButton(top_bar, text="APLICAR DECK", width=120, font=UI_FONT, fg_color="#22c55e", hover_color="#16a34a", command=self.confirm_deck).pack(side="right")
        
        # --- MAIN PANELS ---
        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Left Panel (Preview)
        self.left_frame = ctk.CTkFrame(main_container, width=250, fg_color="#1e293b")
        self.left_frame.pack(side="left", fill="y", padx=(0, 5))
        self.left_frame.pack_propagate(False)
        
        format_menu = ctk.CTkOptionMenu(self.left_frame, variable=self.current_format, values=["GOAT", "Edison", "Speed Duel", "Genesys", "Perfect Circle"], command=self.on_format_change)
        format_menu.pack(pady=10, padx=10, fill="x")
        
        self.preview_image_label = ctk.CTkLabel(self.left_frame, text="Sin selección", text_color="#64748b")
        self.preview_image_label.pack(pady=10, padx=10)
        
        self.preview_text_box = ctk.CTkTextbox(self.left_frame, wrap="word", font=UI_FONT_SMALL, fg_color="#0f172a", text_color="#cbd5e1")
        self.preview_text_box.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Middle Panel (Deck Zones)
        self.middle_frame = ctk.CTkFrame(main_container, fg_color="#1e293b")
        self.middle_frame.pack(side="left", fill="both", expand=True, padx=5)
        
        # Main Deck section
        self.lbl_main_count = ctk.CTkLabel(self.middle_frame, text="MAIN DECK: 0", font=UI_FONT, text_color="white")
        self.lbl_main_count.pack(anchor="w", padx=10, pady=(5,0))
        self.main_grid = ctk.CTkScrollableFrame(self.middle_frame, fg_color="#0f172a", orientation="horizontal", height=240)
        self.main_grid.pack(fill="x", padx=10, pady=5)
        
        # Extra Deck section
        self.lbl_extra_count = ctk.CTkLabel(self.middle_frame, text="EXTRA DECK: 0", font=UI_FONT, text_color="white")
        self.lbl_extra_count.pack(anchor="w", padx=10, pady=(10,0))
        self.extra_grid = ctk.CTkScrollableFrame(self.middle_frame, fg_color="#0f172a", orientation="horizontal", height=120)
        self.extra_grid.pack(fill="x", padx=10, pady=5)
        
        # Side Deck section
        self.lbl_side_count = ctk.CTkLabel(self.middle_frame, text="SIDE DECK: 0", font=UI_FONT, text_color="white")
        self.lbl_side_count.pack(anchor="w", padx=10, pady=(10,0))
        self.side_grid = ctk.CTkScrollableFrame(self.middle_frame, fg_color="#0f172a", orientation="horizontal", height=120)
        self.side_grid.pack(fill="x", padx=10, pady=5)
        
        # Right Panel (Search & List)
        self.right_frame = ctk.CTkFrame(main_container, width=280, fg_color="#1e293b")
        self.right_frame.pack(side="right", fill="y", padx=(5, 0))
        self.right_frame.pack_propagate(False)
        
        search_top = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        search_top.pack(fill="x", padx=10, pady=10)
        
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self.on_search_type)
        self.search_entry = ctk.CTkEntry(search_top, textvariable=self.search_var, placeholder_text="Buscar carta...", font=UI_FONT)
        self.search_entry.pack(side="left", fill="x", expand=True)
        
        self.btn_dest = ctk.CTkButton(search_top, text="A Side", width=60, font=UI_FONT_SMALL, command=self.toggle_dest)
        self.btn_dest.pack(side="right", padx=(5,0))
        
        self.results_scroll = ctk.CTkScrollableFrame(self.right_frame, fg_color="#0f172a")
        self.results_scroll.pack(fill="both", expand=True, padx=10, pady=(0,10))
        
    def toggle_dest(self):
        if self.active_zone == "Main":
            self.active_zone = "Side"
            self.btn_dest.configure(text="A Main")
        else:
            self.active_zone = "Main"
            self.btn_dest.configure(text="A Side")

    def on_format_change(self, choice):
        self.load_database()
        
    def load_database(self):
        fmt = self.current_format.get()
        self.db_cards = []
        self.filtered_cards = []
        self.banlist_dict = {}
        
        # Load local banlist if exists
        import os, json
        filename = f"{fmt.lower().replace(' ', '_')}_banlist.json"
        if os.path.exists(filename):
            try:
                with open(filename, "r", encoding="utf-8") as bf:
                    self.banlist_dict = json.load(bf)
            except Exception as e:
                print(f"Error loading local banlist for {fmt}: {e}")

        self.refresh_results_ui([])
        self.preview_text_box.delete("1.0", "end")
        self.preview_text_box.insert("1.0", f"Cargando base de datos para {fmt}...")
        
        def on_loaded(data):
            self.db_cards = data
            if data:
                self.preview_text_box.delete("1.0", "end")
                self.preview_text_box.insert("1.0", f"Base de datos {fmt} cargada ({len(data)} cartas).\n¡Busca cartas a la derecha!")
                self.on_search_type() # trigger filter
            else:
                self.preview_text_box.delete("1.0", "end")
                self.preview_text_box.insert("1.0", f"Error cargando base de datos {fmt}.")
        
        YgoApi.fetch_database(fmt, callback=lambda d: self.after(0, lambda: on_loaded(d)))

    def on_search_type(self, *args):
        query = self.search_var.get().lower().strip()
        if not query:
            # show first 50
            self.filtered_cards = self.db_cards[:50]
        else:
            self.filtered_cards = [c for c in self.db_cards if query in c.get("name", "").lower()][:50]
        
        self.refresh_results_ui(self.filtered_cards)

    def refresh_results_ui(self, cards):
        for widget in self.results_scroll.winfo_children():
            widget.destroy()
            
        for c in cards:
            card_frame = ctk.CTkFrame(self.results_scroll, fg_color="transparent")
            card_frame.pack(fill="x", pady=2)
            
            name = c.get("name", "Unknown")
            lbl = ctk.CTkLabel(card_frame, text=name, font=UI_FONT_SMALL, text_color="white", cursor="hand2")
            lbl.pack(side="left", padx=5)
            
            # Events
            lbl.bind("<Enter>", lambda e, card=c: self.show_preview(card))
            lbl.bind("<Button-1>", lambda e, card=c: self.add_card_to_deck(card))

    def show_preview(self, card):
        name = card.get("name", "Unknown")
        desc = card.get("desc", "")
        atk = card.get("atk", "?")
        def_ = card.get("def", "?")
        lvl = card.get("level", "?")
        type_ = card.get("type", "")
        
        text = f"{name}\n{type_}"
        if "Monster" in type_:
            text += f"\nNivel: {lvl} | ATK: {atk} | DEF: {def_}"
        text += f"\n\n{desc}"
        
        self.preview_text_box.delete("1.0", "end")
        self.preview_text_box.insert("1.0", text)
        
        # Load image
        images = card.get("card_images", [])
        if images:
            img_url = images[0].get("image_url")
            card_id = card.get("id")
            
            def on_img_loaded(path):
                if not path: return
                try:
                    img = Image.open(path)
                    photo = ctk.CTkImage(light_image=img, dark_image=img, size=(220, 320))
                    self.preview_image_label.configure(image=photo, text="")
                    self.preview_image_label.image = photo
                except Exception as e:
                    print("Error displaying preview image:", e)
                    
            path = YgoApi.get_image_path(card_id, img_url, size="large", callback=lambda p: self.after(0, lambda: on_img_loaded(p)))
            if not path:
                self.preview_image_label.configure(image=None, text="Cargando...")

    def get_card_limit(self, card):
        name = card.get("name", "").lower()
        fmt = self.current_format.get().lower()
        
        # Local Banlist Dictionary Check
        if hasattr(self, 'banlist_dict') and self.banlist_dict:
            status = self.banlist_dict.get(name)
            if status == "Forbidden": return 0
            if status == "Limited": return 1
            if status == "Semi-Limited": return 2
            return 3
            
        # API Banlist check (e.g. GOAT which uses API ban_goat field)
        ban_info = card.get("banlist_info", {})
        status = ban_info.get(f"ban_{fmt}", "")
        if status == "Banned": return 0
        if status == "Limited": return 1
        if status == "Semi-Limited": return 2
        return 3

    def add_card_to_deck(self, card):
        name = card.get("name", "")
        
        count = sum(1 for c in self.main_deck + self.extra_deck + self.side_deck if c.get("name") == name)
        limit = self.get_card_limit(card)
        
        if count >= limit:
            self.bell()
            return

        type_ = card.get("type", "")
        is_extra = "Fusion" in type_ or "Synchro" in type_ or "XYZ" in type_ or "Link" in type_
        
        if self.active_zone == "Side":
            if len(self.side_deck) < 15:
                self.side_deck.append(card)
        else:
            if is_extra:
                if len(self.extra_deck) < 15:
                    self.extra_deck.append(card)
            else:
                if len(self.main_deck) < 60:
                    self.main_deck.append(card)
        
        self.refresh_deck_grids()

    def remove_from_deck(self, zone, index):
        if zone == "main":
            self.main_deck.pop(index)
        elif zone == "extra":
            self.extra_deck.pop(index)
        elif zone == "side":
            self.side_deck.pop(index)
        self.refresh_deck_grids()

    def refresh_deck_grids(self):
        self.lbl_main_count.configure(text=f"MAIN DECK: {len(self.main_deck)}")
        self.lbl_extra_count.configure(text=f"EXTRA DECK: {len(self.extra_deck)}")
        self.lbl_side_count.configure(text=f"SIDE DECK: {len(self.side_deck)}")
        
        self._fill_grid(self.main_grid, self.main_deck, "main")
        self._fill_grid(self.extra_grid, self.extra_deck, "extra")
        self._fill_grid(self.side_grid, self.side_deck, "side")
        
    def _fill_grid(self, container, deck_list, zone_name):
        for w in container.winfo_children():
            w.destroy()
            
        # Optional: pack them nicely
        for i, card in enumerate(deck_list):
            card_id = card.get("id")
            images = card.get("card_images", [])
            img_url_small = images[0].get("image_url_small") if images else None
            
            lbl = ctk.CTkLabel(container, text="[IMG]", cursor="hand2", width=40, height=58, fg_color="#334155")
            lbl.pack(side="left", padx=2, pady=2)
            lbl.bind("<Button-1>", lambda e, z=zone_name, idx=i: self.remove_from_deck(z, idx))
            lbl.bind("<Enter>", lambda e, c=card: self.show_preview(c))
            
            if img_url_small:
                def on_loaded(path, label=lbl, cid=card_id):
                    if not path: return
                    try:
                        if label.winfo_exists():
                            img = Image.open(path)
                            photo = ctk.CTkImage(light_image=img, dark_image=img, size=(40, 58))
                            label.configure(image=photo, text="")
                            self.image_refs[f"{zone_name}_{cid}_{time.time()}"] = photo
                    except Exception as e:
                        print("Error loading thumbnail:", e)
                
                path = YgoApi.get_image_path(card_id, img_url_small, size="small", callback=lambda p, l=lbl: self.after(0, lambda: on_loaded(p, l)))

    def confirm_deck(self):
        lines = ["#created by App", "#main"]
        for c in self.main_deck: lines.append(str(c.get("id")))
        lines.append("#extra")
        for c in self.extra_deck: lines.append(str(c.get("id")))
        lines.append("!side")
        for c in self.side_deck: lines.append(str(c.get("id")))
        
        ydk_text = "\\n".join(lines)
        self.on_confirm_callback(ydk_text)
