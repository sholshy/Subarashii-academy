from flask import Flask, render_template_string, request, send_file
from PIL import Image, ImageDraw, ImageFont
import requests
import os
from datetime import datetime

app = Flask(__name__)

# =========================================
# CONFIG
# =========================================

WIDTH = 1600
HEIGHT = 1600

CACHE_DIR = "cache"
OUTPUT_DIR = "output"

API_URL = "https://db.ygoprodeck.com/api/v7/cardinfo.php"

os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# =========================================
# HTML
# =========================================

HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>YGO Deck Post Generator</title>

    <style>

        body {
            background: #020617;
            color: white;
            font-family: Arial;
            padding: 30px;
        }

        textarea {
            width: 700px;
            height: 350px;
            background: #0f172a;
            color: white;
            border: 1px solid #334155;
            padding: 15px;
            font-size: 14px;
        }

        input {
            width: 350px;
            background: #0f172a;
            color: white;
            border: 1px solid #334155;
            padding: 10px;
            margin-bottom: 10px;
        }

        button {
            background: #2563eb;
            color: white;
            border: none;
            padding: 14px 22px;
            cursor: pointer;
            font-size: 16px;
        }

        img {
            margin-top: 30px;
            border: 1px solid #334155;
            width: 900px;
        }

        .download {
            display: inline-block;
            margin-top: 20px;
            color: white;
            text-decoration: none;
            background: #16a34a;
            padding: 12px 20px;
        }

    </style>

</head>

<body>

<h1>YGO Deck Post Generator</h1>

<form method="POST">

<input
    type="text"
    name="winner"
    placeholder="Ganador"
><br>

<input
    type="text"
    name="event"
    placeholder="Evento"
><br>

<textarea
    name="decklist"
    placeholder="3 Cyber Dragon
2 Book of Moon
1 Jinzo

Extra Deck
1 Thousand-Eyes Restrict

Side Deck
2 Dust Tornado"
></textarea>

<br><br>

<button type="submit">
Generar Diseño
</button>

</form>

{% if image_path %}

<hr>

<img src="{{ image_path }}">

<br>

<a class="download" href="/download">
Descargar PNG
</a>

{% endif %}

</body>
</html>
"""

# =========================================
# PARSER
# =========================================

def parse_decklist(text):

    sections = {
        "main": [],
        "extra": [],
        "side": []
    }

    current = "main"

    lines = [
        l.strip()
        for l in text.splitlines()
        if l.strip()
    ]

    for line in lines:

        upper = line.upper()

        if "EXTRA" in upper:
            current = "extra"
            continue

        if "SIDE" in upper:
            current = "side"
            continue

        if (
            "MONSTER" in upper or
            "SPELL" in upper or
            "TRAP" in upper
        ):
            continue

        parts = line.split(" ", 1)

        if len(parts) < 2:
            continue

        try:

            qty = int(
                parts[0]
                .replace("x", "")
                .replace("X", "")
            )

            name = parts[1]

        except:

            qty = 1
            name = line

        for _ in range(qty):
            sections[current].append(name)

    return sections

# =========================================
# DOWNLOAD CARD
# =========================================

def download_card(name):

    safe_name = (
        name
        .replace("/", "_")
        .replace("\\", "_")
        .replace(":", "_")
    )

    filepath = os.path.join(
        CACHE_DIR,
        f"{safe_name}.jpg"
    )

    if os.path.exists(filepath):
        return filepath

    try:

        print("Buscando:", name)

        res = requests.get(
            API_URL,
            params={"name": name},
            timeout=15
        )

        data = res.json()

        if "data" not in data:

            print("No encontrada:", name)
            return None

        img_url = (
            data["data"][0]
            ["card_images"][0]
            ["image_url_small"]
        )

        img_res = requests.get(
            img_url,
            timeout=15
        )

        with open(filepath, "wb") as f:
            f.write(img_res.content)

        print("OK:", name)

        return filepath

    except Exception as e:

        print("ERROR:", name, e)

        return None

# =========================================
# DRAW SECTION
# =========================================

def draw_section(
    canvas,
    names,
    x,
    y,
    cols,
    card_width,
    gap=8
):

    if not names:
        return

    card_height = int(card_width * 1.45)

    for i, card_name in enumerate(names):

        col = i % cols
        row = i // cols

        dx = x + col * (card_width + gap)
        dy = y + row * (card_height + gap)

        path = download_card(card_name)

        if not path:
            continue

        try:

            img = Image.open(path).convert("RGB")

            img = img.resize(
                (card_width, card_height)
            )

            canvas.paste(img, (dx, dy))

        except Exception as e:

            print("Render ERROR:", e)

# =========================================
# DRAW TITLE
# =========================================

def draw_header(draw, winner, event):

    try:

        title_font = ImageFont.truetype(
            "arial.ttf",
            110
        )

        subtitle_font = ImageFont.truetype(
            "arial.ttf",
            40
        )

    except:

        title_font = ImageFont.load_default()
        subtitle_font = ImageFont.load_default()

    draw.text(
        (60, 40),
        event.upper(),
        fill="#3b82f6",
        font=subtitle_font
    )

    draw.text(
        (60, 90),
        winner.upper(),
        fill="white",
        font=title_font
    )

    date_str = datetime.now().strftime("%d-%m-%Y")

    draw.text(
        (60, 240),
        date_str,
        fill="#64748b",
        font=subtitle_font
    )

# =========================================
# MAIN ROUTE
# =========================================

@app.route("/", methods=["GET", "POST"])
def index():

    image_path = None

    if request.method == "POST":

        winner = request.form.get(
            "winner",
            "CHAMPION"
        )

        event = request.form.get(
            "event",
            "YGO EVENT"
        )

        decklist = request.form.get(
            "decklist",
            ""
        )

        sections = parse_decklist(decklist)

        # ==============================
        # CREATE IMAGE
        # ==============================

        img = Image.new(
            "RGB",
            (WIDTH, HEIGHT),
            "#020617"
        )

        draw = ImageDraw.Draw(img)

        draw_header(
            draw,
            winner,
            event
        )

        # ==============================
        # MAIN DECK
        # ==============================

        draw_section(
            img,
            sections["main"],
            x=60,
            y=320,
            cols=10,
            card_width=100,
            gap=8
        )

        # ==============================
        # EXTRA DECK
        # ==============================

        draw_section(
            img,
            sections["extra"],
            x=60,
            y=1120,
            cols=5,
            card_width=95,
            gap=8
        )

        # ==============================
        # SIDE DECK
        # ==============================

        draw_section(
            img,
            sections["side"],
            x=620,
            y=1120,
            cols=5,
            card_width=95,
            gap=8
        )

        # ==============================
        # SAVE
        # ==============================

        image_path = os.path.join(
            OUTPUT_DIR,
            "ygo_post.png"
        )

        img.save(image_path)

    return render_template_string(
        HTML,
        image_path=image_path
    )

# =========================================
# DOWNLOAD
# =========================================

@app.route("/download")
def download():

    return send_file(
        "output/ygo_post.png",
        as_attachment=True
    )

# =========================================
# START
# =========================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )