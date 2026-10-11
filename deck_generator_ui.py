import tkinter as tk
from tkinter import filedialog, ttk
import customtkinter as ctk
import custom_alerts as messagebox
from PIL import Image, ImageTk, ImageDraw, ImageFont, ImageFilter
import requests
import os
from datetime import datetime
import threading
import re
from concurrent.futures import ThreadPoolExecutor

# =====================================================
# CONFIG
# =====================================================
WIDTH = 1600
HEIGHT = 1600
from utils import get_appdata_dir, get_resource_path
CACHE_DIR = os.path.join(get_appdata_dir(), "cache")
BACKGROUND_IMAGE = get_resource_path("background.png")
TITLE_FONT_FILE = get_resource_path("Orbitron-Black.ttf")
API_URL = "https://db.ygoprodeck.com/api/v7/cardinfo.php"
MAX_NAME_LENGTH = 18

UI_FONT = ("Roboto", 13)
UI_FONT_BIG = ("Orbitron Black", 24)
UI_FONT_SMALL = ("Roboto", 11)

class DeckGeneratorUI(ctk.CTkFrame):
    def __init__(self, parent, go_back_callback):
        super().__init__(parent, fg_color="transparent")
        self.go_back_callback = go_back_callback
        
        os.makedirs(CACHE_DIR, exist_ok=True)

        self.generated_image = None
        self.is_generating = False
        self.failed_cards = set()
        self.session = requests.Session()
        self.resize_timer = None
        self.types_cache_path = os.path.join(CACHE_DIR, "types_cache.json")
        self.card_types = {}
        try:
            if os.path.exists(self.types_cache_path):
                import json
                with open(self.types_cache_path, "r", encoding="utf-8") as f:
                    self.card_types = json.load(f)
        except:
            pass

        self.setup_ui()

    def open_deck_editor(self):
        self.editor_frame.pack_forget()
        from deck_editor_ui import DeckEditorUI
        import tkinter as tk
        
        def on_confirm(ydk_text):
            self.deck_editor_frame.pack_forget()
            self.deck_editor_frame.destroy()
            self.editor_frame.pack(fill="both", expand=True)
            self.text_box.delete("1.0", tk.END)
            self.text_box.insert("1.0", ydk_text)
            
        def on_back():
            self.deck_editor_frame.pack_forget()
            self.deck_editor_frame.destroy()
            self.editor_frame.pack(fill="both", expand=True)

        self.deck_editor_frame = DeckEditorUI(self, on_back, on_confirm)
        self.deck_editor_frame.pack(fill="both", expand=True)

    def prefill_event_info(self, champion=None, event_name=None, date_str=None, format_name=None):
        if self.result_frame.winfo_viewable():
            self.result_frame.pack_forget()
            self.editor_frame.pack(fill="both", expand=True)
        self.generated_image = None

        if champion:
            self.winner_var.set(champion)

        if event_name:
            self.event_entry.delete(0, tk.END)
            self.event_entry.insert(0, event_name)

        if date_str:
            self.date_entry.delete(0, tk.END)
            self.date_entry.insert(0, date_str)

        if format_name:
            normalized = self.normalize_format_name(format_name)
            self.format_var.set(normalized)

        self.update_status("Info del torneo cargada. Pega la decklist del campeón.")

    def normalize_format_name(self, format_name):
        format_map = {
            "goat": "GOAT",
            "edison": "Edison",
            "tengu": "Tengu",
            "h.a.t.": "H.A.T.",
            "hat": "H.A.T.",
            "speed duel": "Speed Duel",
            "genesys": "H.A.T.",
            "perfect circle": "Perfect Circle",
            "tcg": "TCG",
            "ocg": "OCG",
            "sin banlist": "Sin Banlist"
        }
        key = format_name.strip().lower()
        return format_map.get(key, format_name)

    def setup_ui(self):
        # Back button
        back_btn = ctk.CTkButton(self, text="< VOLVER AL MENÚ", command=self.go_back_callback, font=UI_FONT)
        back_btn.pack(side="top", anchor="nw", padx=20, pady=10)

        # Title
        title = ctk.CTkLabel(self, text="YGO Deck Post Generator", font=UI_FONT_BIG, text_color="#60a5fa")
        title.pack(pady=10)

        # Editor Frame
        self.editor_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.editor_frame.pack(fill="both", expand=True)

        # Bottom elements packed first
        self.status_label = ctk.CTkLabel(self.editor_frame, text="ESPERANDO...", text_color="#60a5fa", font=UI_FONT)
        self.status_label.pack(side="bottom", pady=(0, 20))

        self.progress = ctk.CTkProgressBar(self.editor_frame, mode="indeterminate", width=400)
        self.progress.pack(side="bottom", pady=10)
        self.progress.set(0)

        btn_frame = ctk.CTkFrame(self.editor_frame, fg_color="transparent")
        btn_frame.pack(side="bottom", pady=10)
        self.generate_btn = ctk.CTkButton(btn_frame, text="GENERAR IMAGEN", command=self.generate_image, font=UI_FONT)
        self.generate_btn.grid(row=0, column=0, padx=10)

        # Top elements
        self.winner_var = tk.StringVar(value="Champion")
        self.winner_var.trace_add("write", self.validate_name)
        
        self.winner_entry = ctk.CTkEntry(
            self.editor_frame, textvariable=self.winner_var, width=400,
            font=UI_FONT, fg_color="#0f172a", text_color="#60a5fa"
        )
        self.winner_entry.pack(side="top", pady=5)

        self.counter_label = ctk.CTkLabel(
            self.editor_frame, text=f"{MAX_NAME_LENGTH} caracteres restantes",
            text_color="#94a3b8", font=UI_FONT_SMALL
        )
        self.counter_label.pack(side="top")

        # Event Input
        self.event_entry = ctk.CTkEntry(
            self.editor_frame, width=400, font=UI_FONT, fg_color="#0f172a",
            text_color="white"
        )
        self.event_entry.pack(side="top", pady=10)
        self.event_entry.insert(0, "YGO Event")

        # Date Input
        self.date_entry = ctk.CTkEntry(
            self.editor_frame, width=400, font=UI_FONT, fg_color="#0f172a",
            text_color="white", placeholder_text="DD-MM-YYYY"
        )
        self.date_entry.pack(side="top", pady=5)
        self.date_entry.insert(0, datetime.now().strftime('%d-%m-%Y'))

        # Format Selector
        self.format_var = ctk.StringVar(value="Sin Banlist")
        self.format_combo = ctk.CTkComboBox(
            self.editor_frame, variable=self.format_var,
            values=["Sin Banlist", "GOAT", "Edison", "Tengu", "H.A.T.", "Speed Duel", "Perfect Circle", "TCG", "OCG"],
            font=UI_FONT, width=400, fg_color="#0f172a"
        )
        self.format_combo.pack(side="top", pady=5)

        # Background Card Input
        self.bg_card_entry = ctk.CTkEntry(
            self.editor_frame, width=400, font=UI_FONT, fg_color="#0f172a",
            text_color="white", placeholder_text="Carta de fondo (Opcional)"
        )
        self.bg_card_entry.pack(side="top", pady=5)

        # Text Box expands to fill
        editor_btn = ctk.CTkButton(
            self.editor_frame, text="ARMAR DECK EN EL EDITOR INTERACTIVO", font=UI_FONT_BIG,
            fg_color="#8b5cf6", hover_color="#7c3aed", command=self.open_deck_editor
        )
        editor_btn.pack(side="top", pady=10)

        self.text_box = ctk.CTkTextbox(
            self.editor_frame, width=800, height=200, font=("Consolas", 14),
            fg_color="#0f172a", text_color="#60a5fa"
        )
        self.text_box.pack(side="top", fill="both", expand=True, padx=40, pady=10)

        # Context Menu
        self.last_clicked_widget = None
        self.context_menu = tk.Menu(self, tearoff=0, font=UI_FONT_SMALL, bg="#0f172a", fg="white", activebackground="#2563eb", activeforeground="white")
        self.context_menu.add_command(label="Cortar", command=lambda: self.last_clicked_widget.event_generate("<<Cut>>"))
        self.context_menu.add_command(label="Copiar", command=lambda: self.last_clicked_widget.event_generate("<<Copy>>"))
        self.context_menu.add_command(label="Pegar", command=lambda: self.last_clicked_widget.event_generate("<<Paste>>"))
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Vaciar", command=self.clear_text)

        self.text_box.bind("<Button-3>", self.show_context_menu)
        self.winner_entry.bind("<Button-3>", self.show_context_menu)
        self.event_entry.bind("<Button-3>", self.show_context_menu)
        self.date_entry.bind("<Button-3>", self.show_context_menu)

        # Result Frame (Hidden initially)
        self.result_frame = ctk.CTkFrame(self, fg_color="transparent")
        
        result_btn_frame = ctk.CTkFrame(self.result_frame, fg_color="transparent")
        result_btn_frame.pack(side="bottom", pady=20)
        
        self.preview_label = tk.Label(self.result_frame, bg="#020617")
        self.preview_label.pack(side="top", fill="both", expand=True, padx=20, pady=10)
        self.preview_label.bind("<Configure>", self.on_preview_resize)
        
        save_btn = ctk.CTkButton(result_btn_frame, text="GUARDAR PNG", command=self.save_image, font=UI_FONT)
        save_btn.grid(row=0, column=0, padx=10)
        
        new_btn = ctk.CTkButton(result_btn_frame, text="NUEVA IMAGEN", command=self.new_image, font=UI_FONT)
        new_btn.grid(row=0, column=1, padx=10)

    def show_context_menu(self, event):
        self.last_clicked_widget = event.widget
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def clear_text(self):
        if not self.last_clicked_widget:
            return
        if isinstance(self.last_clicked_widget, ctk.CTkTextbox):
            self.last_clicked_widget.delete("1.0", tk.END)
        elif isinstance(self.last_clicked_widget, ctk.CTkEntry):
            self.last_clicked_widget.delete(0, tk.END)

    def validate_name(self, *args):
        current = self.winner_var.get()
        if len(current) > MAX_NAME_LENGTH:
            self.winner_var.set(current[:MAX_NAME_LENGTH])
        chars_left = MAX_NAME_LENGTH - len(self.winner_var.get())
        self.counter_label.configure(text=f"{chars_left} caracteres restantes")

    def update_status(self, text):
        self.after(0, lambda: self.status_label.configure(text=text))

    def on_preview_resize(self, event):
        if self.generated_image is None or not self.result_frame.winfo_viewable():
            return
        
        if self.resize_timer is not None:
            self.after_cancel(self.resize_timer)
        self.resize_timer = self.after(200, lambda: self._resize_preview(event.width, event.height))

    def _resize_preview(self, width, height):
        if width < 100 or height < 100 or self.generated_image is None:
            return
        preview = self.generated_image.copy()
        preview.thumbnail((width, height))
        tk_img = ImageTk.PhotoImage(preview)
        self.preview_label.config(image=tk_img)
        self.preview_label.image = tk_img

    def parse_decklist(self, text):
        sections = {"main": [], "extra": [], "side": []}
        current = "main"
        lines = [l.strip() for l in text.splitlines() if l.strip()]

        for line in lines:
            upper = line.upper()
            if upper == "EXTRA":
                current = "extra"
                continue
            if upper == "SIDE":
                current = "side"
                continue
            if upper in ["MONSTER", "MONSTERS", "SPELL", "SPELLS", "TRAP", "TRAPS"]:
                continue

            match = re.match(r"(\d+)[xX]?\s+(.+)", line)
            if match:
                qty = int(match.group(1))
                name = match.group(2).strip()
            else:
                qty = 1
                name = line.strip()

            for _ in range(qty):
                sections[current].append(name)
        return sections

    def download_card(self, name):
        if name in self.failed_cards:
            return None

        safe_name = re.sub(r'[\\/*?:"<>|]', "_", name).strip()
        filepath = os.path.join(CACHE_DIR, f"{safe_name}.jpg")
        
        for ext in [".jpg", ".png", ".jpeg", ".JPG", ".PNG"]:
            alt_path = os.path.join(CACHE_DIR, f"{safe_name}{ext}")
            if os.path.exists(alt_path):
                filepath = alt_path
                break

        image_valid = False
        if os.path.exists(filepath):
            try:
                with Image.open(filepath) as test:
                    test.verify()
                image_valid = True
            except Exception:
                try:
                    os.remove(filepath)
                except OSError:
                    pass

        if image_valid and name in self.card_types:
            return filepath

        try:
            res = None
            for _ in range(3):
                try:
                    res = self.session.get(API_URL, params={"name": name}, timeout=15)
                    if res.status_code == 200:
                        break
                except requests.RequestException:
                    pass

            if not res or res.status_code != 200:
                if not image_valid:
                    self.failed_cards.add(name)
                return filepath if image_valid else None

            data = res.json()
            if not data.get("data"):
                if not image_valid:
                    self.failed_cards.add(name)
                return filepath if image_valid else None

            card_data = data["data"][0]
            self.card_types[name] = card_data.get("type", "")
            
            if not card_data.get("card_images"):
                if not image_valid:
                    self.failed_cards.add(name)
                return filepath if image_valid else None

            if not image_valid:
                img_url = card_data["card_images"][0].get("image_url_small", card_data["card_images"][0]["image_url"])
                img_res = self.session.get(img_url, timeout=15)
                
                if img_res.status_code != 200:
                    self.failed_cards.add(name)
                    return filepath if image_valid else None

                with open(filepath, "wb") as f:
                    f.write(img_res.content)
            
            return filepath
        except Exception as e:
            print(f"ERROR downloading {name}: {e}")
            if not image_valid:
                self.failed_cards.add(name)
            return filepath if image_valid else None

    def draw_text_shadow(self, draw, x, y, text, font, fill, shadow_color=(0, 0, 0), shadow_offset=5):
        draw.text((x + shadow_offset, y + shadow_offset), text, fill=shadow_color, font=font)
        draw.text((x, y), text, fill=fill, font=font)

    def get_cached_card_path(self, name):
        safe_name = re.sub(r'[\\/*?:"<>|]', "_", name).strip()
        for ext in [".jpg", ".png", ".jpeg", ".JPG", ".PNG"]:
            path = os.path.join(CACHE_DIR, f"{safe_name}{ext}")
            if os.path.exists(path):
                return path
        return os.path.join(CACHE_DIR, f"{safe_name}.jpg")

    def crop_card_art(self, card_img):
        w, h = card_img.size
        left = int(w * 0.118)
        top = int(h * 0.179)
        right = int(w * 0.882)
        bottom = int(h * 0.625)

        if right <= left or bottom <= top:
            return card_img
        return card_img.crop((left, top, right, bottom))

    def apply_background_card_art(self, canvas, card_name):
        if not card_name:
            return canvas

        path = self.get_cached_card_path(card_name)
        if not os.path.exists(path):
            return canvas

        try:
            with Image.open(path) as card_temp:
                art = self.crop_card_art(card_temp.convert("RGBA"))

            scale = max(WIDTH / art.width, HEIGHT / art.height) * 1.08
            resized = art.resize((int(art.width * scale), int(art.height * scale)), Image.Resampling.LANCZOS)
            crop_left = max(0, (resized.width - WIDTH) // 2)
            crop_top = max(0, (resized.height - HEIGHT) // 2)
            art_panel = resized.crop((crop_left, crop_top, crop_left + WIDTH, crop_top + HEIGHT))
            art_panel = art_panel.filter(ImageFilter.GaussianBlur(10))

            shade = Image.new("RGBA", (WIDTH, HEIGHT), (2, 6, 23, 55))
            art_panel = Image.alpha_composite(art_panel, shade)

            mask = Image.new("L", (WIDTH, HEIGHT), 92)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.rectangle([0, 0, WIDTH, HEIGHT], fill=92)
            mask_draw.rectangle([0, 210, int(WIDTH * 0.82), 1500], fill=126)
            mask = mask.filter(ImageFilter.GaussianBlur(90))

            canvas.paste(art_panel, (0, 0), mask)
        except Exception as e:
            print(f"Error applying background card {card_name}:", e)

        return canvas

    def draw_banlist_icon(self, canvas, dx, dy, card_width, status):
        draw = ImageDraw.Draw(canvas)
        r = max(10, int(card_width * 0.12))
        cx, cy = dx - 4, dy - 4
        
        outline_width = max(2, int(r * 0.3))
        bbox = [cx, cy, cx + 2*r, cy + 2*r]
        
        if isinstance(status, int) or (isinstance(status, str) and status.isdigit()):
            val = int(status)
            if val > 0:
                draw.ellipse(bbox, fill="#1e3a8a", outline="#60a5fa", width=outline_width)
                font_path = TITLE_FONT_FILE
                try:
                    font = ImageFont.truetype(font_path, int(r * 1.5))
                except:
                    try:
                        font = ImageFont.truetype("arialbd.ttf", int(r * 1.5))
                    except:
                        font = ImageFont.load_default()
                try:
                    draw.text((cx + r, cy + r - 1), str(val), fill="white", font=font, anchor="mm", stroke_width=1, stroke_fill="black")
                except:
                    draw.text((cx + r, cy + r - 1), str(val), fill="white", font=font, anchor="mm")
                return
        
        if status in ["Forbidden", "Banned"]:
            draw.ellipse(bbox, fill="black", outline="#e60000", width=outline_width)
            draw.line([cx + outline_width, cy + outline_width, cx + 2*r - outline_width, cy + 2*r - outline_width], fill="#e60000", width=outline_width)
        elif status.startswith("Limited") or status == "Semi-Limited":
            draw.ellipse(bbox, fill="black", outline="#e60000", width=outline_width)
            
            font_path = TITLE_FONT_FILE
            try:
                font = ImageFont.truetype(font_path, int(r * 1.5))
            except:
                try:
                    font = ImageFont.truetype("arialbd.ttf", int(r * 1.5))
                except:
                    font = ImageFont.load_default()
                    
            if status == "Limited":
                text = "1"
            elif status == "Semi-Limited":
                text = "2"
            else:
                text = "3"
                
            stroke_w = max(1, int(r * 0.15))
            draw.text((cx + r, cy + r - 1), text, fill="#ffcc00", font=font, anchor="mm", stroke_width=stroke_w, stroke_fill="#ffcc00")

    def draw_section(self, canvas, names, x, y, cols, card_width, gap=8, banlist_dict=None):
        if not names:
            return
        card_height = int(card_width * 1.45)
        
        draw = ImageDraw.Draw(canvas)
        for i, card_name in enumerate(names):
            col = i % cols
            row = i // cols
            dx = x + col * (card_width + gap)
            dy = y + row * (card_height + gap)

            safe_name = re.sub(r'[\\/*?:"<>|]', "_", card_name).strip()
            path = os.path.join(CACHE_DIR, f"{safe_name}.jpg")
            
            for ext in [".jpg", ".png", ".jpeg", ".JPG", ".PNG"]:
                alt_path = os.path.join(CACHE_DIR, f"{safe_name}{ext}")
                if os.path.exists(alt_path):
                    path = alt_path
                    break

            if not os.path.exists(path):
                draw.rectangle((dx, dy, dx + card_width, dy + card_height), fill=(120, 20, 20))
                draw.text((dx + 10, dy + 20), "ERROR", fill="white")
                continue

            try:
                with Image.open(path) as temp_img:
                    card_img = temp_img.convert("RGBA").resize((card_width, card_height))
                
                shadow = Image.new("RGBA", (card_width + 14, card_height + 14), (0, 0, 0, 110))
                shadow = shadow.filter(ImageFilter.GaussianBlur(6))
                
                canvas.paste(shadow, (dx + 6, dy + 6), shadow)
                canvas.paste(card_img, (dx, dy), card_img)

                if banlist_dict:
                    status = banlist_dict.get(card_name.lower())
                    if status:
                        self.draw_banlist_icon(canvas, dx, dy, card_width, status)
            except Exception as e:
                print(f"Render ERROR for {card_name}:", e)

    def generate_image(self):
        if self.is_generating:
            return
        self.is_generating = True
        self.generate_btn.configure(state="disabled")
        self.progress.start()
        
        winner = self.winner_entry.get().strip() or "CHAMPION"
        event = self.event_entry.get().strip() or "YGO EVENT"
        decklist = self.text_box.get("1.0", tk.END)
        format_val = self.format_var.get()
        date_val = self.date_entry.get().strip() or datetime.now().strftime('%d-%m-%Y')

        bg_card = self.bg_card_entry.get().strip()

        threading.Thread(target=self._generate_image_thread, args=(winner, event, decklist, format_val, date_val, bg_card), daemon=True).start()

    def _generate_image_thread(self, winner, event, decklist, format_val, date_val, bg_card):
        self.failed_cards.clear()
        try:
            self.update_status("Procesando decklist...")
            sections = self.parse_decklist(decklist)

            all_cards = set(sections["main"] + sections["extra"] + sections["side"])
            if bg_card:
                all_cards.add(bg_card)
                
            self.update_status("Descargando imágenes e info...")
            with ThreadPoolExecutor(max_workers=10) as executor:
                list(executor.map(self.download_card, all_cards))

            try:
                import json
                with open(self.types_cache_path, "w", encoding="utf-8") as f:
                    json.dump(self.card_types, f)
            except:
                pass

            banlist_dict = {}
            if format_val != "Sin Banlist":
                if format_val in ["Edison", "Speed Duel", "H.A.T.", "Perfect Circle"]:
                    self.update_status(f"Cargando Banlist {format_val}...")
                    import json
                    from utils import get_resource_path
                    filename = f"{format_val.lower().replace(' ', '_')}_banlist.json"
                    file_path = get_resource_path(filename)
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            banlist_dict = json.load(f)
                    except Exception as e:
                        print(f"Error loading {format_val} banlist:", e)
                else:
                    self.update_status(f"Descargando Banlist {format_val}...")
                    try:
                        res = self.session.get(API_URL, params={"banlist": format_val.lower()}, timeout=10)
                        if res.status_code == 200:
                            data = res.json().get("data", [])
                            ban_key = f"ban_{format_val.lower()}"
                            for c in data:
                                status = c.get("banlist_info", {}).get(ban_key)
                                if status:
                                    banlist_dict[c["name"].lower()] = status
                    except Exception as e:
                        print("Error fetching banlist:", e)

            sections["skill"] = []
            for sec in ["main", "extra", "side"]:
                new_sec = []
                for c in sections[sec]:
                    ctype = self.card_types.get(c, "").lower()
                    if "skill" in ctype or "[skill]" in c.lower() or banlist_dict.get(c.lower()) == "Skill":
                        sections["skill"].append(c)
                    else:
                        new_sec.append(c)
                sections[sec] = new_sec

            main_count, extra_count, side_count = len(sections["main"]), len(sections["extra"]), len(sections["side"])
            
            if format_val == "Speed Duel":
                min_main, max_main = 20, 30
                max_extra, max_side = 6, 6
            else:
                min_main, max_main = 40, 60
                max_extra, max_side = 15, 15

            if not (min_main <= main_count <= max_main):
                self.after(0, lambda: messagebox.showerror("Deck inválido", f"Main Deck inválido ({main_count} cartas. Min: {min_main}, Max: {max_main})"))
                return
            if extra_count > max_extra:
                self.after(0, lambda: messagebox.showerror("Deck inválido", f"Extra Deck inválido ({extra_count} cartas. Max: {max_extra})"))
                return
            if side_count > max_side:
                self.after(0, lambda: messagebox.showerror("Deck inválido", f"Side Deck inválido ({side_count} cartas. Max: {max_side})"))
                return

            if format_val == "Genesys":
                total_points = 0
                invalid_types = []
                for sec in ["main", "extra", "side"]:
                    for c in sections.get(sec, []):
                        cl = c.lower()
                        total_points += banlist_dict.get(cl, 0)
                        ctype = self.card_types.get(c, "").lower()
                        if "link monster" in ctype or "pendulum monster" in ctype:
                            if c not in invalid_types:
                                invalid_types.append(c)
                
                if total_points > 100:
                    self.after(0, lambda: messagebox.showerror("Deck inválido", f"El deck excede el límite de 100 puntos de Genesys ({total_points}/100)"))
                    return
                if invalid_types:
                    self.after(0, lambda: messagebox.showerror("Deck inválido", f"Genesys no permite monstruos Link ni Pendulum:\n{', '.join(invalid_types[:3])}"))
                    return

            self.update_status("Cargando fondo...")
            try:
                with Image.open(BACKGROUND_IMAGE) as bg_temp:
                    bg = bg_temp.convert("RGB").resize((WIDTH, HEIGHT))
                overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 80))
                img = Image.alpha_composite(bg.convert("RGBA"), overlay).convert("RGBA")
            except Exception:
                img = Image.new("RGBA", (WIDTH, HEIGHT), "#020617")

            img = self.apply_background_card_art(img, bg_card)
            draw = ImageDraw.Draw(img)

            try:
                title_font = ImageFont.truetype(TITLE_FONT_FILE, 110)
                subtitle_font = ImageFont.truetype(TITLE_FONT_FILE, 38)
                label_font = ImageFont.truetype(TITLE_FONT_FILE, 28)
            except Exception:
                title_font = ImageFont.load_default()
                subtitle_font = ImageFont.load_default()
                label_font = ImageFont.load_default()

            if format_val != "Sin Banlist":
                header_text = f"{event.upper()}  •  FORMATO {format_val.upper()}  •  {date_val}"
            else:
                header_text = f"{event.upper()}  •  {date_val}"
            self.draw_text_shadow(draw, 60, 40, header_text, subtitle_font, fill="#f8fafc")
            self.draw_text_shadow(draw, 60, 95, winner.upper(), title_font, fill="#f8fafc")

            LEFT_MARGIN, RIGHT_MARGIN = 40, 340
            MAIN_COLS, MAIN_GAP = 10, 8
            usable_width = WIDTH - LEFT_MARGIN - RIGHT_MARGIN
            MAIN_CARD_WIDTH = int((usable_width - ((MAIN_COLS - 1) * MAIN_GAP)) / MAIN_COLS)
            MAIN_CARD_HEIGHT = int(MAIN_CARD_WIDTH * 1.45)
            
            main_rows = max(1, (len(sections["main"]) + 9) // 10)
            main_height = (main_rows * MAIN_CARD_HEIGHT) + ((main_rows - 1) * MAIN_GAP)
            main_total_width = (10 * MAIN_CARD_WIDTH) + (9 * MAIN_GAP)
            
            if format_val == "Speed Duel":
                extra_side_cols = 10
                extra_side_gap = MAIN_GAP
                extra_card_width = MAIN_CARD_WIDTH
            else:
                extra_side_cols = 15
                extra_side_gap = 4
                extra_card_width = int((main_total_width - ((extra_side_cols - 1) * extra_side_gap)) / extra_side_cols)
            
            extra_card_height = int(extra_card_width * 1.45)
            
            MAIN_Y = 280
            used_height = main_height
            sections_count = 1
            if sections["extra"]:
                used_height += extra_card_height
                sections_count += 1
            if sections["side"]:
                used_height += extra_card_height
                sections_count += 1
                
            total_gaps = sections_count - 1
            if total_gaps > 0:
                gap = (1500 - MAIN_Y - used_height) // total_gaps
                gap = max(100, min(gap, 180))
            else:
                gap = 120

            EXTRA_Y = MAIN_Y + main_height + gap
            SIDE_Y = EXTRA_Y + extra_card_height + gap if sections["extra"] else MAIN_Y + main_height + gap

            self.update_status("Renderizando Main Deck...")
            self.draw_text_shadow(draw, LEFT_MARGIN, MAIN_Y - 45, "MAIN DECK", label_font, fill="#f8fafc")
            self.draw_section(img, sections["main"], LEFT_MARGIN, MAIN_Y, 10, MAIN_CARD_WIDTH, MAIN_GAP, banlist_dict)
            
            self.update_status("Renderizando Extra Deck...")
            if sections["extra"]:
                self.draw_text_shadow(draw, LEFT_MARGIN, EXTRA_Y - 45, "EXTRA DECK", label_font, fill="#f8fafc")
            self.draw_section(img, sections["extra"], LEFT_MARGIN, EXTRA_Y, extra_side_cols, extra_card_width, extra_side_gap, banlist_dict)
            
            self.update_status("Renderizando Side Deck...")
            if sections["side"]:
                self.draw_text_shadow(draw, LEFT_MARGIN, SIDE_Y - 45, "SIDE DECK", label_font, fill="#f8fafc")
            self.draw_section(img, sections["side"], LEFT_MARGIN, SIDE_Y, extra_side_cols, extra_card_width, extra_side_gap, banlist_dict)

            if sections.get("skill"):
                self.update_status("Renderizando Skill Card...")
                skill_width = 340
                skill_height = int(skill_width * 1.45)
                skill_x = LEFT_MARGIN + main_total_width - skill_width
                
                skill_y = EXTRA_Y
                if skill_y + skill_height > 1540:
                    skill_y = 1540 - skill_height
                
                self.draw_text_shadow(draw, skill_x, skill_y - 45, "SKILL CARD", label_font, fill="#f8fafc")
                self.draw_section(img, [sections["skill"][0]], skill_x, skill_y, 1, skill_width, 0, banlist_dict)

            self.generated_image = img.convert("RGB")
            self.update_status("Generando preview...")
            
            self.after(0, lambda: self.show_result_screen())
            
            if self.failed_cards:
                failed = "\n".join(sorted(self.failed_cards))
                self.update_status(f"Completado con errores ({len(self.failed_cards)} cartas)")
                self.after(0, lambda: messagebox.showwarning("Cartas no encontradas", failed))
            else:
                self.update_status("Completado")

        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error", str(e)))
        finally:
            self.after(0, self.finish_generation)

    def finish_generation(self):
        self.progress.stop()
        self.generate_btn.configure(state="normal")
        self.is_generating = False

    def show_result_screen(self):
        self.editor_frame.pack_forget()
        self.result_frame.pack(fill="both", expand=True, pady=10)
        
        self.update_idletasks()
        w = self.preview_label.winfo_width()
        h = self.preview_label.winfo_height()
        if w > 10 and h > 10:
            self._resize_preview(w, h)

    def save_image(self):
        if self.generated_image is None:
            messagebox.showerror("Error", "Primero genera una imagen")
            return
        
        winner_full = self.winner_entry.get().strip() or "champion"
        first_name = winner_full.split()[0].lower()
        
        format_val = self.format_var.get().lower().replace(" ", "_")
        format_str = f"_{format_val}" if format_val != "sin_banlist" else ""
        date_val = self.date_entry.get().strip()
        date_str = date_val.replace("-", "").replace("/", "") if date_val else datetime.now().strftime("%d%m%y")
        
        filepath = filedialog.asksaveasfilename(
            initialfile=f"decklist_{first_name}{format_str}_{date_str}.png",
            defaultextension=".png",
            filetypes=[("PNG", "*.png")]
        )
        if filepath:
            self.generated_image.save(filepath)
            messagebox.showinfo("Guardado", f"Imagen guardada:\n{os.path.basename(filepath)}")

    def new_image(self):
        self.preview_label.config(image="")
        self.preview_label.image = None
        self.result_frame.pack_forget()
        self.editor_frame.pack(fill="both", expand=True)
        self.update_status("Esperando...")
