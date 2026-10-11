import os
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
from league_graphics import load_font, draw_text_shadow

def text_width(draw, text, font):
    try:
        return draw.textlength(text, font=font)
    except AttributeError:
        return draw.textsize(text, font=font)[0]


def generate_activity_chart(store_name, timeline_data):
    WIDTH, HEIGHT = 1080, 720
    img = Image.new("RGBA", (WIDTH, HEIGHT), "#020617")
    draw = ImageDraw.Draw(img)

    title_font = load_font(48)
    sub_font = load_font(24)
    axis_font = load_font(18)
    
    # Draw header
    draw_text_shadow(draw, 50, 40, f"ACTIVIDAD DE LIGAS: {store_name.upper()}", title_font, fill="#f8fafc")
    draw_text_shadow(draw, 50, 100, f"Evolucin de Asistencia por Torneo", sub_font, fill="#60a5fa")

    if not timeline_data:
        draw_text_shadow(draw, WIDTH//2 - 200, HEIGHT//2, "No hay datos de torneos para graficar.", sub_font, fill="#94a3b8")
        return img.convert("RGB")

    # Group data by format
    formats_data = {}
    dates = []
    
    for row in timeline_data:
        fmt = row['format_name']
        d = row['date']
        c = row['player_count']
        
        if d not in dates:
            dates.append(d)
            
        if fmt not in formats_data:
            formats_data[fmt] = {}
        formats_data[fmt][d] = c
        
    dates.sort(key=lambda x: datetime.strptime(x, "%Y-%m-%d") if "-" in x else x)
    
    # Calculate chart boundaries
    margin_left = 100
    margin_bottom = 100
    margin_right = 50
    margin_top = 200
    
    chart_w = WIDTH - margin_left - margin_right
    chart_h = HEIGHT - margin_top - margin_bottom
    
    # Determine max players for Y axis
    max_players = max([c for row in timeline_data for c in (row['player_count'],)]) if timeline_data else 10
    # Round up to nearest 5 or 10
    max_players = ((max_players // 5) + 1) * 5
    if max_players < 10: max_players = 10
    
    # Draw Grid and Y-axis labels
    y_steps = 5
    for i in range(y_steps + 1):
        val = int(max_players * (i / y_steps))
        y = margin_top + chart_h - (i / y_steps) * chart_h
        draw.line([(margin_left - 10, y), (WIDTH - margin_right, y)], fill="#1e293b", width=2)
        draw.text((margin_left - 40, y - 10), str(val), fill="#94a3b8", font=axis_font)
        
    # Draw X-axis
    draw.line([(margin_left, margin_top + chart_h), (WIDTH - margin_right, margin_top + chart_h)], fill="#334155", width=3)
    
    if len(dates) == 0:
        return img.convert("RGB")
        
    x_step = chart_w / max(1, len(dates) - 1)
    for i, d in enumerate(dates):
        x = margin_left + i * x_step
        draw.line([(x, margin_top + chart_h), (x, margin_top + chart_h + 10)], fill="#334155", width=3)
        # Draw date label (rotated or small)
        dw = text_width(draw, d, axis_font)
        draw.text((x - dw/2, margin_top + chart_h + 20), d, fill="#94a3b8", font=axis_font)

    # Plot lines per format
    colors = ["#3b82f6", "#eab308", "#22c55e", "#ef4444", "#a855f7"]
    format_colors = {}
    
    color_idx = 0
    for fmt, data_dict in formats_data.items():
        color = colors[color_idx % len(colors)]
        format_colors[fmt] = color
        color_idx += 1
        
        points = []
        for i, d in enumerate(dates):
            if d in data_dict:
                x = margin_left + i * x_step
                y = margin_top + chart_h - (data_dict[d] / max_players) * chart_h
                points.append((x, y))
        
        # Draw lines and dots
        for i in range(len(points) - 1):
            draw.line([points[i], points[i+1]], fill=color, width=4)
            
        for pt in points:
            draw.ellipse([pt[0]-6, pt[1]-6, pt[0]+6, pt[1]+6], fill=color, outline="#0f172a", width=2)
            
    # Draw Legend
    leg_x = margin_left
    leg_y = HEIGHT - 40
    for fmt, color in format_colors.items():
        draw.ellipse([leg_x, leg_y, leg_x+15, leg_y+15], fill=color)
        draw.text((leg_x + 25, leg_y-2), fmt, fill="#f8fafc", font=sub_font)
        leg_x += text_width(draw, fmt, sub_font) + 60
        
    return img.convert("RGB")
