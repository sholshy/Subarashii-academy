import sys
import re
import os

path = 'c:/Users/shols/PycharmProjects/PythonProject3/public_web.py'
content = open(path, encoding='utf8').read()

new_index = '''@app.route('/')
def index():
    data = get_snapshot_data()
    if not data:
        return "Snapshot no encontrado. Ejecuta el SyncManager primero.", 500
        
    leaderboard = data.get("leaderboard", [])
    official = [p for p in leaderboard if p.get("matches_played", 0) >= 10]
    
    # Sort official by rank just in case
    official.sort(key=lambda x: x.get("rank", 999))
    top_players = official[:3]
    
    # Calculate stats
    total_players = data.get("player_count", len(leaderboard))
    total_ranked = len(official)
    
    tournaments_map = data.get("tournaments_map", {})
    unique_tournaments = set()
    total_matches = 0
    for pid, t_list in tournaments_map.items():
        for t in t_list:
            unique_tournaments.add(t.get("tournament_id"))
    
    # we can approximate matches by summing up matches_played / 2
    for p in leaderboard:
        total_matches += p.get("matches_played", 0)
    total_matches = total_matches // 2
    
    total_tournaments = len(unique_tournaments)
    
    stats = {
        "total_players": total_players,
        "total_ranked": total_ranked,
        "total_tournaments": total_tournaments,
        "total_matches": total_matches
    }
    
    # Ultimates Logros
    all_achievements = []
    ach_map = data.get("achievements_map", {})
    # Need to match player names
    id_to_name = {str(p["profile_id"]): p["name"] for p in leaderboard}
    
    for pid, achs in ach_map.items():
        pname = id_to_name.get(str(pid), "Desconocido")
        for a in achs:
            all_achievements.append({
                "player_name": pname,
                "achievement_id": a.get("id"),
                "date": a.get("date", "")
            })
            
    # Sort by date desc
    all_achievements.sort(key=lambda x: x["date"], reverse=True)
    latest_achievements = all_achievements[:5]
    
    # Match achievement names from catalog
    base_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        import json
        with open(os.path.join(base_dir, "data", "achievements", "catalog.json"), 'r', encoding='utf-8') as f:
            cat_ach = {a["id"]: a for a in json.load(f).get("achievements", [])}
            for la in latest_achievements:
                la["name"] = cat_ach.get(la["achievement_id"], {}).get("name", la["achievement_id"])
                la["icon"] = cat_ach.get(la["achievement_id"], {}).get("icon", "🏆")
    except:
        for la in latest_achievements:
            la["name"] = la["achievement_id"]
            la["icon"] = "🏆"
            
    # Ultimo torneo
    latest_tournament = None
    all_t_events = []
    for pid, t_list in tournaments_map.items():
        all_t_events.extend(t_list)
        
    if all_t_events:
        all_t_events.sort(key=lambda x: x.get("tournament_id", 0), reverse=True)
        t_id = all_t_events[0].get("tournament_id")
        t_date = all_t_events[0].get("date")
        t_fmt = all_t_events[0].get("format_name")
        
        # find winner (rank 1)
        winner_name = ""
        participants = 0
        for pid, t_list in tournaments_map.items():
            for t in t_list:
                if t.get("tournament_id") == t_id:
                    participants += 1
                    if t.get("rank") == 1:
                        # find name
                        real_pid = None
                        for p in leaderboard:
                            if str(p["player_id"]) == str(pid):
                                winner_name = p["name"]
                                break
                                
        latest_tournament = {
            "id": t_id,
            "date": t_date,
            "format_name": t_fmt,
            "winner": winner_name,
            "participants": participants
        }

    return render_template('index.html', 
                           top_players=top_players, 
                           stats=stats,
                           latest_achievements=latest_achievements,
                           latest_tournament=latest_tournament,
                           generated_at=data.get("generated_at"))

@app.route('/ranking')
def ranking():
    data = get_snapshot_data()
    if not data:
        return "Snapshot no encontrado.", 500
        
    leaderboard = data.get("leaderboard", [])
    official = []
    provisional = []
    
    for p in leaderboard:
        if p.get("matches_played", 0) >= 10:
            official.append(p)
        else:
            provisional.append(p)
            
    # Assign provisional ranks (just order by rating)
    provisional.sort(key=lambda x: x.get("current_rating", 0), reverse=True)
    for i, p in enumerate(provisional, 1):
        p["prov_rank"] = f"P{i}"
        
    return render_template('ranking.html', official=official, provisional=provisional)'''

content = re.sub(r'@app\.route\(\'/\'\).*?(?=@app\.route\(\'/torneo/<slug>\'\))', new_index + '\n', content, flags=re.DOTALL)
open(path, 'w', encoding='utf8').write(content)
print('Updated public_web.py')
