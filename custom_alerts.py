import customtkinter as ctk

UI_FONT = ("Roboto", 13)
UI_FONT_SMALL = ("Roboto", 12)

def _create_custom_dialog(title, message, buttons, icon_text, icon_color):
    dialog = ctk.CTkToplevel()
    dialog.title(title)
    dialog.geometry("500x250")
    dialog.resizable(False, False)
    
    dialog.grab_set()
    dialog.focus_set()
    dialog.attributes('-topmost', True)

    content_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    content_frame.pack(fill="both", expand=True, padx=20, pady=20)

    icon_lbl = ctk.CTkLabel(content_frame, text=icon_text, font=("Orbitron Black", 36), text_color=icon_color)
    icon_lbl.pack(side="left", padx=(0, 20), anchor="n")

    msg_label = ctk.CTkLabel(content_frame, text=message, font=UI_FONT_SMALL, text_color="white", justify="left", wraplength=400)
    msg_label.pack(side="left", fill="both", expand=True, pady=(10, 0))

    btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    btn_frame.pack(side="bottom", fill="x", padx=20, pady=(0, 20))

    result = [None]

    def on_click(res):
        result[0] = res
        dialog.destroy()

    for text, res, style in buttons:
        btn = ctk.CTkButton(btn_frame, text=text, command=lambda r=res: on_click(r), font=UI_FONT_SMALL)
        btn.pack(side="right", padx=5)

    dialog.wait_window(dialog)
    return result[0]

def showinfo(title, message):
    _create_custom_dialog(title, message, [("OK", None, "Small.TButton")], "i", "#3b82f6")

def showwarning(title, message):
    _create_custom_dialog(title, message, [("Aceptar", None, "Small.TButton")], "!", "#eab308")

def showerror(title, message):
    _create_custom_dialog(title, message, [("Cerrar", None, "Small.TButton")], "X", "#ef4444")

def askyesno(title, message):
    return _create_custom_dialog(title, message, [
        ("No", False, "Small.TButton"),
        ("Sí", True, "Small.TButton")
    ], "?", "#60a5fa")
