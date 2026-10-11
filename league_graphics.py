import os
import requests
import re
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime

CACHE_DIR = "cache"
API_URL = "https://db.ygoprodeck.com/api/v7/cardinfo.php"
TITLE_FONT_FILE = "Orbitron-Black.ttf"

def download_card_image(name):
    """Descarga la carta de YGOPRODECK si no existe en caché."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    safe_name = re.sub(r'[\\/*?:"<>|]', "_", name).strip()
    filepath = os.path.join(CACHE_DIR, f"{safe_name}.jpg")

    if os.path.exists(filepath):
        try:
            with Image.open(filepath) as test:
                test.verify()
            return filepath
        except Exception:
            try: os.remove(filepath)
            except OSError: pass

    try:
        res = requests.get(API_URL, params={"name": name}, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if data.get("data"):
                card_data = data["data"][0]
                if card_data.get("card_images"):
                    img_url = card_data["card_images"][0].get("image_url_small", card_data["card_images"][0]["image_url"])
                    img_res = requests.get(img_url, timeout=10)
                    if img_res.status_code == 200:
                        with open(filepath, "wb") as f:
                            f.write(img_res.content)
                        return filepath
    except Exception as e:
        print(f"Error downloading {name}: {e}")
    return None

def load_font(size):
    try:
        return ImageFont.truetype(TITLE_FONT_FILE, size)
    except Exception:
        return ImageFont.load_default()

def draw_text_shadow(draw, x, y, text, font, fill, shadow_color=(0, 0, 0), shadow_offset=4):
    draw.text((x + shadow_offset, y + shadow_offset), text, fill=shadow_color, font=font)
    draw.text((x, y), text, fill=fill, font=font)

def generate_top8_standings(league_manager, include_missions=True, include_attendance=True):
    WIDTH, HEIGHT = 1080, 1080
    img = Image.new("RGBA", (WIDTH, HEIGHT), "#020617")
    draw = ImageDraw.Draw(img)

    # Header
    title_font = load_font(60)
    sub_font = load_font(25)
    
    draw_text_shadow(draw, 50, 40, f"LIGA {league_manager.current_format.upper()}", title_font, fill="#f8fafc")
    if not include_attendance:
        draw_text_shadow(draw, 780, 110, "SIN ASISTENCIA", sub_font, fill="#eab308")
    draw_text_shadow(draw, 50, 110, f"TOP 8 POSICIONES  •  {datetime.now().strftime('%d-%m-%Y')}", sub_font, fill="#60a5fa")

    ranked_standings = league_manager.get_ranked_standings(include_missions, include_attendance)[:8]
    rank_colors = {
        1: "#b7791f",  # Gold
        2: "#64748b",  # Silver
        3: "#92400e",  # Bronze
    }
    rank_accent_colors = {
        1: "#facc15",
        2: "#e2e8f0",
        3: "#f97316",
    }
    
    start_y = 170
    row_height = 95
    
    for i, (rank, player) in enumerate(ranked_standings):
        y = start_y + i * (row_height + 15)
        # Row background
        bg_color = "#1e293b" if i % 2 == 0 else "#0f172a"
        bg_color = rank_colors.get(rank, bg_color)
        accent_color = rank_accent_colors.get(rank, "#facc15")
        
        draw.rectangle([50, y, WIDTH - 50, y + row_height], fill=bg_color)
        
        # Rank
        draw_text_shadow(draw, 70, y + 25, f"#{rank}", load_font(40), fill="white")
        
        # Icon
        icon_path = download_card_image(player.signature_card) if player.signature_card else None
        if icon_path:
            try:
                icon_img = Image.open(icon_path).convert("RGBA")
                iw, ih = icon_img.size
                # Proporciones exactas de la ilustración en una carta de YGO
                art_left = int(iw * 0.118)
                art_top = int(ih * 0.179)
                art_right = int(iw * 0.882)
                art_size = art_right - art_left
                art_bottom = art_top + art_size
                
                icon_size = row_height - 16
                icon_img = icon_img.crop((art_left, art_top, art_right, art_bottom)).resize((icon_size, icon_size))
                
                # Mask circle
                mask = Image.new('L', (icon_size, icon_size), 0)
                ImageDraw.Draw(mask).ellipse((0, 0, icon_size-1, icon_size-1), fill=255)
                
                # Golden border
                ImageDraw.Draw(icon_img).ellipse((0, 0, icon_size-1, icon_size-1), outline=accent_color, width=3)
                
                img.paste(icon_img, (180, y + 8), mask)
            except Exception as e:
                print("Error drawing icon:", e)
                
        # Player Info
        draw_text_shadow(draw, 280, y + 15, player.name.upper(), load_font(35), fill="white")
        draw_text_shadow(draw, 280, y + 60, player.deck_name, load_font(18), fill="#94a3b8")
        
        # Points
        pts = player.get_total_points(include_missions, include_attendance)
        text = f"{pts} PTS"
        font = load_font(45)
        try:
            text_width = draw.textlength(text, font=font)
        except AttributeError:
            try: text_width = font.getsize(text)[0]
            except AttributeError: text_width = 180
            
        x_pos = (WIDTH - 50) - text_width - 30 # 30px padding from the right edge
        draw_text_shadow(draw, x_pos, y + 20, text, font, fill=accent_color)
        
    return img.convert("RGB")

def generate_trend_chart(league_manager, include_missions=True, include_attendance=True):
    WIDTH, HEIGHT = 1080, 1080
    img = Image.new("RGBA", (WIDTH, HEIGHT), "#020617")
    draw = ImageDraw.Draw(img)

    title_font = load_font(60)
    sub_font = load_font(25)
    
    draw_text_shadow(draw, 50, 40, f"LIGA {league_manager.current_format.upper()}", title_font, fill="#f8fafc")
    if not include_attendance:
        draw_text_shadow(draw, 780, 110, "SIN ASISTENCIA", sub_font, fill="#eab308")
    draw_text_shadow(draw, 50, 110, f"COMPOSICIÓN DE PUNTOS  •  {datetime.now().strftime('%d-%m-%Y')}", sub_font, fill="#60a5fa")

    ranked_standings = league_manager.get_ranked_standings(include_missions, include_attendance)[:10] # Top 10 max
    
    # Legend
    legend_y = 160
    draw.rectangle([50, legend_y, 80, legend_y+25], fill="#3b82f6") # Match
    draw.text((95, legend_y), "Puntos de Match", fill="white", font=sub_font)
    
    if include_attendance:
        draw.rectangle([350, legend_y, 380, legend_y+25], fill="#22c55e") # Attendance
        draw.text((395, legend_y), "Asistencia", fill="white", font=sub_font)
    
    if include_missions:
        missions_x = 550 if include_attendance else 350
        draw.rectangle([missions_x, legend_y, missions_x+30, legend_y+25], fill="#eab308") # Missions
        draw.text((missions_x+45, legend_y), "Misiones (Bingo)", fill="white", font=sub_font)

    start_y = 220
    row_height = 65
    max_pts = max([p.get_total_points(include_missions, include_attendance) for _, p in ranked_standings]) if ranked_standings else 1
    if max_pts == 0: max_pts = 1
    
    bar_start_x = 450
    bar_max_width = WIDTH - bar_start_x - 50
    
    for i, (rank, player) in enumerate(ranked_standings):
        y = start_y + i * (row_height + 15)
        draw_text_shadow(draw, 50, y + 15, f"#{rank} {player.name[:20]}", load_font(30), fill="white")
        
        m_pts, a_pts, mi_pts, _ = player.get_points_composition(include_missions, include_attendance)
        total_pts = m_pts + a_pts + mi_pts
        
        if total_pts > 0:
            m_w = int((m_pts / max_pts) * bar_max_width)
            a_w = int((a_pts / max_pts) * bar_max_width)
            mi_w = int((mi_pts / max_pts) * bar_max_width)
            
            bar_x = bar_start_x
            if m_w > 0:
                draw.rectangle([bar_x, y + 8, bar_x + m_w, y + row_height - 8], fill="#3b82f6")
                bar_x += m_w
            if a_w > 0:
                draw.rectangle([bar_x, y + 8, bar_x + a_w, y + row_height - 8], fill="#22c55e")
                bar_x += a_w
            if mi_w > 0:
                draw.rectangle([bar_x, y + 8, bar_x + mi_w, y + row_height - 8], fill="#eab308")
                
            total_w = m_w + a_w + mi_w
            text = str(total_pts)
            font = load_font(35)
            try:
                bbox = draw.textbbox((0,0), text, font=font)
                text_width = bbox[2] - bbox[0]
            except AttributeError:
                try: text_width = draw.textlength(text, font=font)
                except AttributeError: text_width = 60
                
            if total_w > text_width + 40:
                x_pos = bar_start_x + total_w - text_width - 15
            else:
                x_pos = bar_start_x + total_w + 15
                
            draw_text_shadow(draw, x_pos, y + 12, text, font, fill="white")

    return img.convert("RGB")
