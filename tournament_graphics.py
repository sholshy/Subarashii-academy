from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

TITLE_FONT_FILE = "Orbitron-Black.ttf"


def load_font(size):
    try:
        return ImageFont.truetype(TITLE_FONT_FILE, size)
    except Exception:
        return ImageFont.load_default()


def draw_text_shadow(draw, x, y, text, font, fill, shadow_color=(0, 0, 0), shadow_offset=3):
    draw.text((x + shadow_offset, y + shadow_offset), text, fill=shadow_color, font=font)
    draw.text((x, y), text, fill=fill, font=font)


def text_width(draw, text, font):
    try:
        return draw.textlength(text, font=font)
    except AttributeError:
        try:
            return font.getsize(text)[0]
        except AttributeError:
            return len(text) * 10


def fit_text(draw, text, font_size, max_width, min_size=22):
    size = font_size
    font = load_font(size)
    while size > min_size and text_width(draw, text, font) > max_width:
        size -= 2
        font = load_font(size)
    return font


def event_subtitle(event_bits):
    return " - ".join(str(bit) for bit in event_bits if bit)


def friendly_tiebreaker_note(note):
    if note == "OMW/OOMW":
        return "Rivales / 2do"
    if note == "H2H empatado":
        return "Duelo dir. empatado"
    if note.startswith("H2H"):
        return note.replace("H2H", "Duelo dir.")
    return note


def player_name(player):
    return player.name if player else "BYE"


def generate_pairings_image(tournament_manager, store_name="", date_str=None):
    WIDTH, HEIGHT = 1080, 1080
    img = Image.new("RGBA", (WIDTH, HEIGHT), "#020617")
    draw = ImageDraw.Draw(img)

    title_font = load_font(58)
    sub_font = load_font(24)
    table_font = load_font(34)
    vs_font = load_font(28)
    footer_font = load_font(20)

    round_text = f"RONDA {tournament_manager.current_round}"
    total_rounds = getattr(tournament_manager, "total_rounds", 0)
    if total_rounds:
        round_text += f" / {total_rounds}"

    event_bits = [tournament_manager.format_name.upper(), round_text]
    if store_name:
        event_bits.insert(0, store_name.upper())

    date_label = date_str or datetime.now().strftime("%d-%m-%y")

    draw.rectangle([0, 0, WIDTH, 150], fill="#0f172a")
    draw.rectangle([0, 145, WIDTH, 150], fill="#60a5fa")
    draw_text_shadow(draw, 50, 35, "PAREOS DEL TORNEO", title_font, fill="#f8fafc")
    draw_text_shadow(draw, 52, 104, event_subtitle(event_bits), sub_font, fill="#60a5fa")
    date_w = text_width(draw, date_label, sub_font)
    draw_text_shadow(draw, WIDTH - 52 - date_w, 104, date_label, sub_font, fill="#94a3b8")

    matches = tournament_manager.get_current_matches()
    if not matches:
        draw_text_shadow(draw, 50, 250, "NO HAY PAREOS DISPONIBLES", load_font(42), fill="#f8fafc")
        return img.convert("RGB")

    start_y = 190
    available_h = 780
    gap = 12
    row_h = min(96, max(58, (available_h - gap * (len(matches) - 1)) // len(matches)))
    name_font_size = 31 if row_h >= 78 else 24
    note_font_size = 16

    for idx, match in enumerate(matches, start=1):
        y = start_y + (idx - 1) * (row_h + gap)
        bg_color = "#1e293b" if idx % 2 == 1 else "#111827"
        accent_color = "#facc15" if match.p2 is None else "#60a5fa"

        draw.rectangle([50, y, WIDTH - 50, y + row_h], fill=bg_color)
        draw.rectangle([50, y, 68, y + row_h], fill=accent_color)

        table_label = f"MESA {idx}"
        draw_text_shadow(draw, 88, y + max(11, (row_h - 34) // 2), table_label, table_font, fill="#f8fafc")

        left_x = 270
        right_x = 680
        name_y = y + max(12, (row_h - 36) // 2)

        p1 = player_name(match.p1).upper()
        p2 = player_name(match.p2).upper()
        p1_font = fit_text(draw, p1, name_font_size, 320)
        p2_font = fit_text(draw, p2, name_font_size, 320)

        draw_text_shadow(draw, left_x, name_y, p1, p1_font, fill="#f8fafc")
        draw_text_shadow(draw, 595, name_y, "VS", vs_font, fill="#94a3b8")
        draw_text_shadow(draw, right_x, name_y, p2, p2_font, fill="#f8fafc" if match.p2 else "#facc15")

        if getattr(match, "note", "") and row_h >= 86:
            draw.text((left_x, y + row_h - 24), match.note[:80], fill="#eab308", font=load_font(note_font_size))

    footer_y = HEIGHT - 72
    draw.rectangle([50, footer_y, WIDTH - 50, footer_y + 1], fill="#334155")
    footer = "Imagen generada para compartir pareos por redes sociales"
    footer_w = text_width(draw, footer, footer_font)
    draw.text(((WIDTH - footer_w) / 2, footer_y + 20), footer, fill="#64748b", font=footer_font)

    return img.convert("RGB")


def generate_standings_image(tournament_manager, store_name="", date_str=None):
    WIDTH = 1080
    standings = tournament_manager.get_standings()
    notes = tournament_manager.get_tiebreaker_notes(standings)

    row_h = 58 if len(standings) > 16 else 72
    gap = 8
    start_y = 190
    footer_space = 92
    HEIGHT = max(1080, start_y + len(standings) * (row_h + gap) + footer_space)

    img = Image.new("RGBA", (WIDTH, HEIGHT), "#020617")
    draw = ImageDraw.Draw(img)

    title_font = load_font(54)
    sub_font = load_font(24)
    rank_font = load_font(30 if row_h >= 70 else 24)
    name_font_size = 30 if row_h >= 70 else 24
    stat_font = load_font(24 if row_h >= 70 else 20)
    footer_font = load_font(20)

    event_bits = [tournament_manager.format_name.upper(), "STANDING FINAL"]
    if store_name:
        event_bits.insert(0, store_name.upper())

    date_label = date_str or datetime.now().strftime("%d-%m-%y")

    draw.rectangle([0, 0, WIDTH, 150], fill="#0f172a")
    draw.rectangle([0, 145, WIDTH, 150], fill="#60a5fa")
    draw_text_shadow(draw, 50, 35, "RESULTADOS DEL TORNEO", title_font, fill="#f8fafc")
    draw_text_shadow(draw, 52, 104, event_subtitle(event_bits), sub_font, fill="#60a5fa")
    date_w = text_width(draw, date_label, sub_font)
    draw_text_shadow(draw, WIDTH - 52 - date_w, 104, date_label, sub_font, fill="#94a3b8")

    if not standings:
        draw_text_shadow(draw, 50, 250, "NO HAY RESULTADOS DISPONIBLES", load_font(42), fill="#f8fafc")
        return img.convert("RGB")

    header_font = load_font(18)
    draw.text((64, 166), "RK", fill="#94a3b8", font=header_font)
    draw.text((170, 166), "JUGADOR", fill="#94a3b8", font=header_font)
    draw.text((610, 166), "PTS", fill="#94a3b8", font=header_font)
    draw.text((705, 166), "RIVALES", fill="#94a3b8", font=header_font)
    draw.text((825, 166), "2DO NIVEL", fill="#94a3b8", font=header_font)
    draw.text((948, 166), "NOTA", fill="#94a3b8", font=header_font)

    if hasattr(tournament_manager, "get_ranked_standings"):
        ranked = tournament_manager.get_ranked_standings()
    else:
        ranked = [(idx, player) for idx, player in enumerate(standings, start=1)]

    for idx, (current_rank, player) in enumerate(ranked, start=1):

        y = start_y + (idx - 1) * (row_h + gap)
        bg_color = "#1e293b" if idx % 2 == 1 else "#111827"
        accent_color = "#facc15" if current_rank == 1 else "#60a5fa"
        if current_rank == 1:
            bg_color = "#854d0e"
        elif current_rank == 2:
            bg_color = "#475569"
        elif current_rank == 3:
            bg_color = "#7c2d12"

        draw.rectangle([50, y, WIDTH - 50, y + row_h], fill=bg_color)
        draw.rectangle([50, y, 68, y + row_h], fill=accent_color)

        rank_text = f"#{current_rank}"
        draw_text_shadow(draw, 82, y + max(12, (row_h - 32) // 2), rank_text, rank_font, fill="#f8fafc")

        name = player.name.upper() if getattr(player, "active", True) else f"{player.name.upper()} (DROP)"
        name_font = fit_text(draw, name, name_font_size, 420, min_size=16)
        draw_text_shadow(draw, 170, y + max(10, (row_h - 34) // 2), name, name_font, fill="#f8fafc")

        stat_y = y + max(12, (row_h - 28) // 2)
        draw_text_shadow(draw, 610, stat_y, str(player.points), stat_font, fill=accent_color)
        draw_text_shadow(draw, 705, stat_y, f"{getattr(player, '_omw', 0):.3f}", stat_font, fill="#e2e8f0")
        draw_text_shadow(draw, 825, stat_y, f"{getattr(player, '_oomw', 0):.3f}", stat_font, fill="#e2e8f0")

        note = friendly_tiebreaker_note(notes.get(player, ""))
        note_font = fit_text(draw, note, 16, 105, min_size=10)
        draw.text((948, stat_y + 3), note, fill="#eab308", font=note_font)

    footer_y = HEIGHT - 72
    draw.rectangle([50, footer_y, WIDTH - 50, footer_y + 1], fill="#334155")
    footer = "Rivales = rendimiento de oponentes | 2do nivel = rendimiento de oponentes de tus oponentes"
    footer_w = text_width(draw, footer, footer_font)
    draw.text(((WIDTH - footer_w) / 2, footer_y + 20), footer, fill="#64748b", font=footer_font)

    return img.convert("RGB")


def generate_top8_bracket_image(tournament_manager, store_name='', date_str=None):
    from PIL import Image, ImageDraw, ImageFont
    import os
    WIDTH, HEIGHT = 1600, 1000
    img = Image.new('RGBA', (WIDTH, HEIGHT), '#020617')
    draw = ImageDraw.Draw(img)

    title_font = load_font(48)
    sub_font = load_font(24)
    name_font = load_font(18)
    
    # Draw header
    draw.rectangle([0, 0, WIDTH, 120], fill='#0f172a')
    draw.rectangle([0, 115, WIDTH, 120], fill='#60a5fa')
    draw_text_shadow(draw, 50, 25, 'BRACKET TOP 8 - MOLEDORA', title_font, fill='#f8fafc')
    
    event_bits = [tournament_manager.format_name.upper()]
    if store_name:
        event_bits.insert(0, store_name.upper())
    draw_text_shadow(draw, 52, 85, event_subtitle(event_bits), sub_font, fill='#60a5fa')
    
    date_label = date_str or datetime.now().strftime('%d-%m-%y')
    date_w = text_width(draw, date_label, sub_font)
    draw_text_shadow(draw, WIDTH - 52 - date_w, 85, date_label, sub_font, fill='#94a3b8')

    def draw_match(x, y_center, p1_name, p2_name, match_label, winner=None):
        width = 280
        h = 40
        y_top = y_center - h
        
        # Determine colors based on winner
        c1 = '#1e293b'
        c2 = '#111827'
        if winner == 1:
            c1 = '#065f46'
            c2 = '#3f3f46' # faded loser
        elif winner == 2:
            c1 = '#3f3f46'
            c2 = '#065f46'
            
        draw.rectangle([x, y_top, x+width, y_top+h], fill=c1, outline='#334155')
        draw.text((x+10, y_top+10), p1_name, fill='#f8fafc', font=name_font)
        
        draw.rectangle([x, y_center, x+width, y_center+h], fill=c2, outline='#334155')
        draw.text((x+10, y_center+10), p2_name, fill='#f8fafc', font=name_font)
        
        draw.text((x+5, y_top-20), match_label, fill='#60a5fa', font=load_font(14))
        return (x+width, y_center)
        
    def draw_champ(x, y_center, name):
        width = 280
        h = 60
        y_top = y_center - h//2
        if name != '':
            draw.rectangle([x, y_top, x+width, y_top+h], fill='#eab308', outline='#ca8a04')
            draw.text((x+10, y_top+20), 'CAMPEON: ' + name, fill='#000000', font=load_font(20))
        else:
            draw.rectangle([x, y_top, x+width, y_top+h], fill='#1e293b', outline='#334155')
            draw.text((x+10, y_top+20), 'CAMPEON: ', fill='#94a3b8', font=load_font(20))
        return (x, y_center)

    def connect(pt1, pt2, draw):
        x1, y1 = pt1
        x2, y2 = pt2
        mid_x = (x1 + x2) // 2
        draw.line([(x1, y1), (mid_x, y1)], fill='#64748b', width=3)
        draw.line([(mid_x, y1), (mid_x, y2)], fill='#64748b', width=3)
        draw.line([(mid_x, y2), (x2, y2)], fill='#64748b', width=3)

    # Coordinates
    x_qf = 50
    x_sf = 400
    x_f = 750
    x_c = 1100

    qf_y = [250, 450, 650, 850]
    sf_y = [350, 750]
    f_y = 550
    
    # Get tournament rounds
    rounds = tournament_manager.rounds
    
    # Draw QF
    pts_qf = []
    qf_matches = rounds[0] if len(rounds) > 0 else []
    for i in range(4):
        p1_name, p2_name = '', ''
        winner = None
        if i < len(qf_matches):
            m = qf_matches[i]
            p1_name = player_name(m.p1).upper()
            p2_name = player_name(m.p2).upper()
            if m.reported:
                if m.result_text == 'P1_WIN': winner = 1
                elif m.result_text == 'P2_WIN': winner = 2
        pt = draw_match(x_qf, qf_y[i], p1_name, p2_name, f'Cuartos {i+1}', winner)
        pts_qf.append(pt)
        
    # Draw SF
    pts_sf = []
    sf_matches = rounds[1] if len(rounds) > 1 else []
    for i in range(2):
        p1_name, p2_name = '', ''
        winner = None
        if i < len(sf_matches):
            m = sf_matches[i]
            p1_name = player_name(m.p1).upper()
            p2_name = player_name(m.p2).upper()
            if m.reported:
                if m.result_text == 'P1_WIN': winner = 1
                elif m.result_text == 'P2_WIN': winner = 2
        pt = draw_match(x_sf, sf_y[i], p1_name, p2_name, f'Semifinal {i+1}', winner)
        pts_sf.append(pt)
        connect(pts_qf[i*2], (x_sf, sf_y[i] - 20), draw)
        connect(pts_qf[i*2+1], (x_sf, sf_y[i] + 20), draw)
        
    # Draw F
    f_matches = rounds[2] if len(rounds) > 2 else []
    p1_name, p2_name = '', ''
    winner = None
    champ_name = ''
    if 0 < len(f_matches):
        m = f_matches[0]
        p1_name = player_name(m.p1).upper()
        p2_name = player_name(m.p2).upper()
        if m.reported:
            if m.result_text == 'P1_WIN': 
                winner = 1
                champ_name = p1_name
            elif m.result_text == 'P2_WIN': 
                winner = 2
                champ_name = p2_name
                
    pt_f = draw_match(x_f, f_y, p1_name, p2_name, 'Final', winner)
    connect(pts_sf[0], (x_f, f_y - 20), draw)
    connect(pts_sf[1], (x_f, f_y + 20), draw)
    
    # Draw C
    pt_c = draw_champ(x_c, f_y, champ_name)
    draw.line([pt_f, pt_c], fill='#64748b', width=3)
    
    # Add footer
    footer_font = load_font(16)
    footer_y = HEIGHT - 40
    footer = "Imagen generada para compartir el bracket por redes sociales"
    footer_w = text_width(draw, footer, footer_font)
    draw.text(((WIDTH - footer_w) / 2, footer_y), footer, fill='#64748b', font=footer_font)

    return img.convert('RGB')

