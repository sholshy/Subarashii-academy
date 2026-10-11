import tkinter as tk
import customtkinter as ctk
from prize_calculator_ui import PrizeCalculator

root = ctk.CTk()
try:
    calc = PrizeCalculator(root, None)
    print("PrizeCalculator initialized successfully")
except Exception as e:
    import traceback
    traceback.print_exc()
