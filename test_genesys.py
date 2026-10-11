import tkinter as tk
import customtkinter as ctk
from deck_generator_ui import DeckGeneratorUI

root = ctk.CTk()
app = DeckGeneratorUI(root, lambda: None)

# Fake inputs
decklist = """1 Pot of Greed
1 Monster Reborn
1 Heavy Storm
"""

# Let's override update_status so it doesn't crash on cross-thread
app.update_status = lambda msg: print("STATUS:", msg)
# Override messagebox
import custom_alerts as messagebox
messagebox.showerror = lambda title, msg: print("ERROR:", title, msg)
messagebox.showwarning = lambda title, msg: print("WARNING:", title, msg)

print("Starting generation thread...")
app._generate_image_thread("Champion", "Event", decklist, "Genesys", "20-05-2026")
print("Generation thread finished.")

if app.generated_image:
    app.generated_image.save("test_genesys_output.png")
    print("Saved to test_genesys_output.png")
else:
    print("No image generated!")
