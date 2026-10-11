import os
import datetime

def generate_instagram_caption(standings, format_name):
    """
    Generates the text caption for Instagram containing the Top 3 players.
    standings: list of dicts/objects with attributes: rank, name, points, wld
    """
    caption_lines = [f"¡Resultados del torneo de hoy! Formato: {format_name} 🏆\n"]
    caption_lines.append("🏆 Top 3 Jugadores:")

    top_players = standings[:3] # Max top 3
    
    for i, p in enumerate(top_players):
        if isinstance(p, dict):
            rank = str(p.get('rank', i+1))
            name = str(p.get('name', 'Unknown'))
            wld = str(p.get('wld', '0-0-0'))
        else:
            rank = str(getattr(p, 'rank', i+1))
            name = str(getattr(p, 'name', 'Unknown'))
            wld = str(getattr(p, 'wld', '0-0-0'))
            
        medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉"
        caption_lines.append(f"{medal} {rank}º Lugar: {name}")

    caption_lines.append("\n¡Gracias a todos por participar!\n")
    caption_lines.append("#duelorapido #duelorapido.cl #yugiohchile #tcgchile #yugiohtcg #ygotcg")

    return "\n".join(caption_lines)

def save_instagram_image(img):
    """
    Saves the PIL Image to the output folder and returns the path.
    """
    os.makedirs("output", exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"output/instagram_standings_{timestamp}.png"
    filepath = os.path.abspath(filename)
    img.save(filepath)
    return filepath
