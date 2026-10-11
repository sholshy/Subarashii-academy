import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
import os
import winsound
from PIL import Image, ImageTk

from tournament_ui import TournamentUI
from league_ui import LeagueUI
from deck_generator_ui import DeckGeneratorUI
from store_ui import StoreUI
from prize_calculator_ui import PrizeCalculatorUI
from database import init_db

UI_FONT = ("Roboto", 13)
UI_FONT_SMALL = ("Roboto", 11)

APP_VERSION = "v1.1.0"

# Initialize SQLite database
init_db()

class YgoToolsApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"YGO Tools by Sholshy - {APP_VERSION}")
        self.geometry("1280x980")
        self.maximize_window()
        
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.setup_styles()
        
        self.main_menu_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.generator_frame = None
        self.tournament_frame = None
        self.league_frame = None
        self.store_frame = None
        self.prize_calculator_frame = None
        self.academy_frame = None
        
        self.music_muted = True
        
        self.setup_main_menu()
        self.open_main_menu()
        self.after(100, self.maximize_window)

    def maximize_window(self):
        try:
            self.state("zoomed")
        except tk.TclError:
            self.attributes("-zoomed", True)

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        
        # Treeview Styles (Still needed since CTk doesn't have Treeview)
        style.configure(
            "Treeview",
            background="#0f172a",
            foreground="white",
            fieldbackground="#0f172a",
            borderwidth=0,
            rowheight=35,
            font=UI_FONT_SMALL
        )
        style.map("Treeview", background=[("selected", "#3b82f6")])
        style.configure(
            "Treeview.Heading",
            background="#1e293b",
            foreground="#60a5fa",
            relief="flat",
            font=UI_FONT_SMALL,
            padding=(5, 10)
        )
        style.map("Treeview.Heading", background=[("active", "#2563eb")])

        # Scrollbar Style
        style.configure(
            "Vertical.TScrollbar",
            background="#1e293b",
            troughcolor="#020617",
            bordercolor="#020617",
            arrowcolor="white",
            relief="flat"
        )

    def setup_main_menu(self):
        self.scroll_frame = ctk.CTkScrollableFrame(self.main_menu_frame, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True)

        title = ctk.CTkLabel(self.scroll_frame, text="YGO Tools by Sholshy", font=("Orbitron Black", 48), text_color="#60a5fa")
        title.pack(pady=(100, 50))
        
        btn_stores = ctk.CTkButton(self.scroll_frame, text="Gestor de Tiendas", command=self.open_stores, font=UI_FONT, height=50, width=300)
        btn_stores.pack(pady=20)
        
        btn_tournament = ctk.CTkButton(self.scroll_frame, text="Gestor de Torneos", command=self.open_tournament, font=UI_FONT, height=50, width=300)
        btn_tournament.pack(pady=20)
        
        btn_league = ctk.CTkButton(self.scroll_frame, text="Gestor de Ligas", command=self.open_league, font=UI_FONT, height=50, width=300)
        btn_league.pack(pady=20)
        
        btn_prize_calc = ctk.CTkButton(self.scroll_frame, text="Calculadora de Premios", command=self.open_prize_calculator, font=UI_FONT, height=50, width=300)
        btn_prize_calc.pack(pady=20)
        
        btn_academy = ctk.CTkButton(self.scroll_frame, text="Subarashii Duel Academy", command=self.open_academy, font=UI_FONT, height=50, width=300, fg_color="#8b5cf6", hover_color="#7c3aed")
        btn_academy.pack(pady=20)
        
        btn_web = ctk.CTkButton(self.scroll_frame, text="Abrir Academia Web", command=self.open_web_academy, font=UI_FONT, height=50, width=300, fg_color="#f59e0b", hover_color="#d97706")
        btn_web.pack(pady=20)
        
        btn_generator = ctk.CTkButton(self.scroll_frame, text="YGO Deck Post Generator", command=self.open_generator, font=UI_FONT, height=50, width=300)
        btn_generator.pack(pady=20)
        
        # Elementos estáticos en main_menu_frame
        self.gif_label = tk.Label(self.main_menu_frame, bg="#242424")
        self.gif_label.place(relx=1.0, rely=1.0, anchor="se", x=-20, y=-40)
        
        credit_label = ctk.CTkLabel(self.main_menu_frame, text="Dancing GIF by Mewtwo365", font=("Roboto", 10), text_color="#475569")
        credit_label.place(relx=1.0, rely=1.0, anchor="se", x=-20, y=-15)
        
        icon = "🔇" if self.music_muted else "🔊"
        self.music_btn = ctk.CTkButton(self.main_menu_frame, text=icon, command=self.toggle_music, font=("Segoe UI Emoji", 24), width=40, fg_color="transparent", hover_color="#0f172a")
        self.music_btn.place(relx=0.05, rely=0.95, anchor="sw")
        
        self.load_gif()

    def load_gif(self):
        self.frames = []
        self.current_frame = 0
        try:
            from utils import get_resource_path
            gif_path = get_resource_path("yugi_dance.gif")
            if os.path.exists(gif_path):
                im = Image.open(gif_path)
                w, h = im.size
                new_h = 150
                new_w = int(w * (new_h / h))
                for i in range(im.n_frames):
                    im.seek(i)
                    frame_img = im.copy().convert("RGBA")
                    frame_img = frame_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                    self.frames.append(ImageTk.PhotoImage(frame_img))
                self.animate_gif()
        except Exception as e:
            print("Error loading gif:", e)

    def animate_gif(self):
        if self.frames:
            if self.main_menu_frame.winfo_viewable():
                self.gif_label.config(image=self.frames[self.current_frame])
                self.current_frame = (self.current_frame + 1) % len(self.frames)
            self.after(80, self.animate_gif)
        
    def play_music(self):
        from utils import get_resource_path
        music_path = get_resource_path("keygen.wav")
        if not self.music_muted and os.path.exists(music_path):
            winsound.PlaySound(music_path, winsound.SND_ASYNC | winsound.SND_LOOP)
            
    def stop_music(self):
        winsound.PlaySound(None, winsound.SND_PURGE)
        
    def toggle_music(self):
        self.music_muted = not self.music_muted
        if self.music_muted:
            self.music_btn.configure(text="🔇")
            self.stop_music()
        else:
            self.music_btn.configure(text="🔊")
            self.play_music()

    def hide_all_frames(self):
        self.main_menu_frame.pack_forget()
        if self.generator_frame:
            self.generator_frame.pack_forget()
        if self.tournament_frame:
            self.tournament_frame.pack_forget()
        if self.league_frame:
            self.league_frame.pack_forget()
        if self.store_frame:
            self.store_frame.pack_forget()
        if self.prize_calculator_frame:
            self.prize_calculator_frame.pack_forget()
        if self.academy_frame:
            self.academy_frame.pack_forget()

    def open_main_menu(self):
        self.hide_all_frames()
        self.main_menu_frame.pack(fill="both", expand=True)
        self.play_music()
        
    def open_tournament(self, scheduled_tournament=None):
        self.hide_all_frames()
        self.stop_music()
        if not self.tournament_frame:
            self.tournament_frame = TournamentUI(self, self.open_main_menu)
        if scheduled_tournament and hasattr(self.tournament_frame, 'load_scheduled_event'):
            self.tournament_frame.load_scheduled_event(scheduled_tournament)
        self.tournament_frame.pack(fill="both", expand=True)
        
    def open_league(self, format_name=None):
        self.hide_all_frames()
        self.stop_music()
        if not self.league_frame:
            self.league_frame = LeagueUI(self, self.open_main_menu)
        if format_name:
            self.league_frame.set_format(format_name)
        else:
            self.league_frame.refresh_players_list()
        self.league_frame.pack(fill="both", expand=True)
        
    def open_generator(self, event_info=None):
        self.hide_all_frames()
        self.stop_music()
        if not self.generator_frame:
            self.generator_frame = DeckGeneratorUI(self, self.open_main_menu)
        if event_info:
            self.generator_frame.prefill_event_info(**event_info)
        self.generator_frame.pack(fill="both", expand=True)

    def open_stores(self):
        self.hide_all_frames()
        self.stop_music()
        if not self.store_frame:
            self.store_frame = StoreUI(self, self.open_main_menu)
        else:
            self.store_frame.refresh_list()
        self.store_frame.pack(fill="both", expand=True)

    def open_prize_calculator(self, total_players=None, prize_groups=None, invited_players=None, return_callback=None):
        self.hide_all_frames()
        self.stop_music()
        if not self.prize_calculator_frame:
            self.prize_calculator_frame = PrizeCalculatorUI(self, self.open_main_menu)
        if total_players is not None:
            self.prize_calculator_frame.set_players(total_players, invited_players)
        self.prize_calculator_frame.set_prize_groups(prize_groups)
        self.prize_calculator_frame.set_return_callback(return_callback)
        self.prize_calculator_frame.pack(fill="both", expand=True)

    def open_analysis(self):
        from academy.analysis_ui import AnalysisUI
        AnalysisUI(self)

    def open_web_academy(self):
        import os
        import webbrowser
        import sys
        import threading
        
        try:
            if getattr(sys, 'frozen', False):
                # Running as compiled PyInstaller executable
                from public_web import app
                threading.Thread(target=lambda: app.run(port=8000, debug=False, use_reloader=False), daemon=True).start()
                self.after(2000, lambda: webbrowser.open("http://localhost:8000"))
            else:
                # Running in development
                os.startfile("Start_Academy_Web.bat")
                self.after(2000, lambda: webbrowser.open("http://localhost:8000"))
        except Exception as e:
            print(f"Error al abrir la academia web: {e}")

    def open_academy(self):
        self.hide_all_frames()
        self.stop_music()
        if not self.academy_frame:
            from academy_ui import AcademyUI
            self.academy_frame = ctk.CTkFrame(self, fg_color="transparent")
            AcademyUI(self.academy_frame, self)
        else:
            # Need to find the AcademyUI instance to refresh it, but it's okay, 
            # I'll just re-instantiate it for simplicity, or we can just pack it.
            self.academy_frame.destroy()
            self.academy_frame = ctk.CTkFrame(self, fg_color="transparent")
            from academy_ui import AcademyUI
            AcademyUI(self.academy_frame, self)
            
        self.academy_frame.pack(fill="both", expand=True)


if __name__ == "__main__":
    app = YgoToolsApp()
    app.mainloop()
