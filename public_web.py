import os
import json
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, abort, request, jsonify, redirect, url_for, session, render_template_string

app = Flask(__name__, template_folder="templates/public", static_folder="static")
app.secret_key = os.environ.get("SECRET_KEY", "subarashii_academy_secret_key_change_in_production_2026")

ORGANIZER_API_KEY = os.environ.get("ORGANIZER_API_KEY", "subarashii_secret_organizer_key_2026")
ORGANIZER_ADMIN_PASSWORD = os.environ.get("ORGANIZER_ADMIN_PASSWORD", "subarashii2026")

def organizer_auth_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        token = ""
        if auth_header.startswith("Bearer "):
            token = auth_header.split("Bearer ", 1)[1].strip()
        elif request.headers.get("X-Organizer-Key"):
            token = request.headers.get("X-Organizer-Key", "").strip()
        elif request.args.get("api_key"):
            token = request.args.get("api_key", "").strip()

        is_session_auth = session.get("is_organizer_admin", False)

        if (token and token == ORGANIZER_API_KEY) or is_session_auth:
            return f(*args, **kwargs)

        return jsonify({
            "success": False,
            "error": "Acceso no autorizado. Se requiere token o API Key válida de organizador."
        }), 401
    return decorated_function

def get_snapshot_data():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    manifest_path = os.path.join(base_dir, "mock_server", "public_api", "manifest.json")
    if not os.path.exists(manifest_path):
        return None
        
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)
        
    snapshot_filename = manifest.get("latest_snapshot")
    if not snapshot_filename:
        return None
        
    snapshot_path = os.path.join(base_dir, "mock_server", "public_api", snapshot_filename)
    if not os.path.exists(snapshot_path):
        return None
        
    with open(snapshot_path, 'r', encoding='utf-8') as f:
        return json.load(f)

@app.route('/')
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
        
    return render_template('ranking.html', official=official, provisional=provisional)
@app.route('/torneo/<slug>')
@app.route('/perfil/<slug>')
@app.route('/jugador/<slug>')
def profile(slug):
    data = get_snapshot_data()
    if not data:
        return "Snapshot no encontrado.", 500
        
    leaderboard = data.get("leaderboard", [])
    player = next((p for p in leaderboard if p.get("slug") == slug), None)
    if not player:
        abort(404)
        
    pid = str(player["profile_id"])
    
    achievements = data.get("achievements_map", {}).get(pid, [])
    missions = data.get("missions_map", {}).get(pid, [])
    history = data.get("rating_history_map", {}).get(pid, [])
    formats = data.get("format_stats_map", {}).get(str(player["player_id"]), {})
    tournaments = data.get("tournaments_map", {}).get(str(player["player_id"]), [])
    
    # Load catalog for achievement names if possible, but actually the web should have a public catalog endpoint/file.
    # We will simulate having a catalog available.
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cat_ach, cat_msn = {}, {}
    try:
        with open(os.path.join(base_dir, "data", "achievements", "catalog.json"), 'r', encoding='utf-8') as f:
            for a in json.load(f).get("achievements", []):
                cat_ach[a["id"]] = a
    except: pass
    try:
        with open(os.path.join(base_dir, "data", "missions", "catalog.json"), 'r', encoding='utf-8') as f:
            for m in json.load(f).get("missions", []):
                cat_msn[m["id"]] = m
    except: pass
    
    for a in achievements:
        c = cat_ach.get(a["id"], {})
        a["name"] = c.get("name", a["id"])
        a["description"] = c.get("description", "")
        a["rarity"] = c.get("rarity", "Común")

    explanation = data.get("explanations_map", {}).get(pid)

    dorms_meta = {
        "Slifer Red": {
            "god_name": "Slifer the Sky Dragon",
            "god_img": "/static/public/img/dorms/slifer_god.jpg",
            "god_banner": "/static/public/img/dorms/slifer_banner.jpg",
            "motto": "Pasión indomable, instinto audaz y fuego ascendente",
            "house_title": "CASA SLIFER RED",
            "god_desc": "El Dragón del Cielo — Dios Egipcio del Trueno Carmesí",
            "color": "#ef4444",
            "border_color": "#dc2626",
            "badge_class": "dorm-slifer-red"
        },
        "Ra Yellow": {
            "god_name": "The Winged Dragon of Ra",
            "god_img": "/static/public/img/dorms/ra_god.jpg",
            "god_banner": "/static/public/img/dorms/ra_banner.jpg",
            "motto": "Estrategia milimétrica, sabiduría solar y disciplina férrea",
            "house_title": "CASA RA YELLOW",
            "god_desc": "El Dragón Alado de Ra — Dios Egipcio del Sol Dorado",
            "color": "#eab308",
            "border_color": "#d97706",
            "badge_class": "dorm-ra-yellow"
        },
        "Obelisk Blue": {
            "god_name": "Obelisk the Tormentor",
            "god_img": "/static/public/img/dorms/obelisk_god.jpg",
            "god_banner": "/static/public/img/dorms/obelisk_banner.jpg",
            "motto": "Poder absoluto, maestría técnica y supremacía inquebrantable",
            "house_title": "CASA OBELISK BLUE",
            "god_desc": "Obelisk el Atormentador — Dios Egipcio del Puño Titánico",
            "color": "#38bdf8",
            "border_color": "#2563eb",
            "badge_class": "dorm-obelisk-blue"
        },
        "Estudiante de Intercambio": {
            "god_name": "Subarashii Academy",
            "god_img": "/static/public/img/dorms/academy_crest.jpg",
            "god_banner": "/static/public/img/dorms/academy_banner.jpg",
            "motto": "Etapa fundacional de calibración oficial de ELO (10 matches)",
            "house_title": "ESTUDIANTE DE INTERCAMBIO",
            "god_desc": "Aspirante a la Academia de Duelos",
            "color": "#f8fafc",
            "border_color": "#94a3b8",
            "badge_class": "dorm-estudiante-de-intercambio"
        }
    }
    dorm_meta = dorms_meta.get(player.get("dorm"), dorms_meta["Estudiante de Intercambio"])

    return render_template('profile.html', 
                           player=player, 
                           achievements=achievements,
                           missions=missions,
                           history=history,
                           formats=formats,
                           tournaments=tournaments,
                           explanation=explanation,
                           dorm_meta=dorm_meta)

@app.route('/temporadas')
def seasons():
    data = get_snapshot_data()
    seasons_data = data.get("seasons_data", {}) if data else {}
    return render_template('seasons.html', seasons_data=seasons_data)

@app.route('/logros')
def achievements_catalog():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    catalog = []
    try:
        with open(os.path.join(base_dir, "data", "achievements", "catalog.json"), 'r', encoding='utf-8') as f:
            catalog = json.load(f).get("achievements", [])
    except: pass
    return render_template('achievements.html', catalog=catalog)

@app.route('/calendario')
def calendar_view():
    data = get_snapshot_data()
    all_events = data.get("calendar", []) if data else []
    
    # Fallback directo a la base de datos si no hay snapshot aún
    if not all_events:
        try:
            from calendar_manager import CalendarManager
            cm = CalendarManager()
            all_events = cm.get_scheduled_tournaments(include_finished=True)
        except Exception:
            all_events = []
            
    from datetime import datetime
    today_iso = datetime.now().strftime("%Y-%m-%d")
    
    upcoming_events = [e for e in all_events if e.get('date', '') >= today_iso and e.get('status') in ('PROGRAMADO', 'EN_CURSO')]
    
    return render_template('calendar.html', all_events=all_events, upcoming_events=upcoming_events)

@app.route('/hall-of-fame')
def hall_of_fame():
    return render_template('hall_of_fame.html')

# =========================================================================
# SALAS DE TORNEO INTERACTIVAS (CHECK-IN QR, LOBBY Y PAREOS EN VIVO)
# =========================================================================
@app.route('/unirse')
@app.route('/unirse/<room_code>')
def join_tournament_room(room_code=None):
    from tournament_room_manager import TournamentRoomManager
    trm = TournamentRoomManager()
    
    if not room_code:
        active_room = trm.get_latest_active_room()
        room = active_room if active_room else None
    else:
        room = trm.get_room_by_code(room_code)

    return render_template('join.html', room=room)

@app.route('/sala/<room_code>')
@app.route('/live/<room_code>')
def view_tournament_room(room_code):
    from tournament_room_manager import TournamentRoomManager
    trm = TournamentRoomManager()
    room = trm.get_room_by_code(room_code)
    if not room:
        abort(404)
        
    players = trm.get_room_players(room_code)
    return render_template('room_live.html', room=room, players=players)

@app.route('/api/room/<room_code>/join', methods=['POST'])
def api_room_join(room_code):
    from tournament_room_manager import TournamentRoomManager
    trm = TournamentRoomManager()
    data = request.get_json() or {}
    
    player_name = data.get('player_name', '').strip()
    konami_id = data.get('konami_id', '').strip()
    deck = data.get('deck', '').strip()
    session_token = data.get('session_token', '').strip()
    
    ok, res = trm.register_player(
        room_code=room_code,
        player_name=player_name,
        konami_id=konami_id,
        deck_archetype=deck,
        session_token=session_token
    )
    if ok:
        return jsonify({"success": True, "data": res})
    else:
        return jsonify({"success": False, "message": str(res)}), 400

@app.route('/api/room/<room_code>/status')
def api_room_status(room_code):
    from tournament_room_manager import TournamentRoomManager
    trm = TournamentRoomManager()
    room = trm.get_room_by_code(room_code)
    if not room:
        return jsonify({"success": False, "message": "Sala no encontrada"}), 404
        
    players = trm.get_room_players(room_code)
    dropped_players = trm.get_room_dropped_players(room_code)
    
    live_data = {}
    if room.get('live_data_json'):
        try:
            live_data = json.loads(room['live_data_json'])
        except Exception:
            live_data = {}
            
    return jsonify({
        "success": True,
        "data": {
            "room_code": room['room_code'],
            "title": room['title'],
            "format_name": room['format_name'],
            "status": room['status'],
            "current_round": room['current_round'],
            "players": players,
            "dropped_players": dropped_players,
            "live_data": live_data,
            "updated_at": room['updated_at']
        }
    })

@app.route('/api/search_players')
def api_search_players():
    from tournament_room_manager import TournamentRoomManager
    trm = TournamentRoomManager()
    q = request.args.get('q', '').strip()
    results = trm.search_academy_players(q)
    return jsonify(results)

# =========================================================================
# TABLÓN DE CARTAS & BÚSQUEDA YGOPRODECK
# =========================================================================
@app.route('/api/cards/search')
def api_cards_search():
    from tournament_room_manager import TournamentRoomManager
    trm = TournamentRoomManager()
    q = request.args.get('q', '').strip()
    results = trm.search_cards_ygo(q)
    return jsonify(results)

@app.route('/api/room/<room_code>/trades', methods=['GET', 'POST'])
def api_room_trades(room_code):
    from tournament_room_manager import TournamentRoomManager
    trm = TournamentRoomManager()
    
    if request.method == 'GET':
        posts = trm.get_trade_posts(room_code)
        return jsonify({"success": True, "trades": posts})
        
    data = request.get_json() or {}
    player_name = data.get('player_name', '').strip()
    post_type = data.get('post_type', 'BUSCO').strip()
    card_name = data.get('card_name', '').strip()
    card_id = data.get('card_id')
    card_image_url = data.get('card_image_url', '').strip()
    rarity = data.get('rarity', '').strip()
    language = data.get('language', '').strip()
    edition = data.get('edition', '').strip()
    notes = data.get('notes', '').strip()
    session_token = data.get('session_token', '').strip()
    
    ok, msg = trm.create_trade_post(
        room_code=room_code,
        player_name=player_name,
        post_type=post_type,
        card_name=card_name,
        card_id=card_id,
        card_image_url=card_image_url,
        rarity=rarity,
        language=language,
        edition=edition,
        notes=notes,
        session_token=session_token
    )
    if ok:
        return jsonify({"success": True, "message": msg})
    return jsonify({"success": False, "message": msg}), 400

@app.route('/api/room/<room_code>/trades/<int:post_id>', methods=['DELETE'])
def api_room_delete_trade(room_code, post_id):
    from tournament_room_manager import TournamentRoomManager
    trm = TournamentRoomManager()
    token = request.args.get('token', '').strip()
    trm.delete_trade_post(post_id, session_token=token)
    return jsonify({"success": True})

# =========================================================================
# FASE 2: AUTO-REPORTE DE RESULTADOS Y CONFIRMACIÓN MUTUA
# =========================================================================
@app.route('/api/room/<room_code>/report', methods=['POST'])
def api_room_report_match(room_code):
    from tournament_room_manager import TournamentRoomManager
    trm = TournamentRoomManager()
    data = request.get_json() or {}
    
    round_num = data.get('round_num')
    table_num = data.get('table_num')
    reporter_name = data.get('reporter_name', '').strip()
    score_p1 = data.get('score_p1', 0)
    score_p2 = data.get('score_p2', 0)
    
    ok, res = trm.submit_match_report(
        room_code=room_code,
        round_num=round_num,
        table_num=table_num,
        reporter_name=reporter_name,
        score_p1=score_p1,
        score_p2=score_p2
    )
    if ok:
        return jsonify({"success": True, "data": res})
    return jsonify({"success": False, "message": str(res)}), 400

@app.route('/api/room/<room_code>/confirm_report', methods=['POST'])
def api_room_confirm_match(room_code):
    from tournament_room_manager import TournamentRoomManager
    trm = TournamentRoomManager()
    data = request.get_json() or {}
    
    round_num = data.get('round_num')
    table_num = data.get('table_num')
    confirmer_name = data.get('confirmer_name', '').strip()
    
    ok, res = trm.confirm_match_report(
        room_code=room_code,
        round_num=round_num,
        table_num=table_num,
        confirmer_name=confirmer_name
    )
    if ok:
        return jsonify({"success": True, "message": res})
    return jsonify({"success": False, "message": str(res)}), 400

@app.route('/api/room/<room_code>/dispute_report', methods=['POST'])
def api_room_dispute_match(room_code):
    from tournament_room_manager import TournamentRoomManager
    trm = TournamentRoomManager()
    data = request.get_json() or {}
    
    round_num = data.get('round_num')
    table_num = data.get('table_num')
    disputer_name = data.get('disputer_name', '').strip()
    
    ok, res = trm.dispute_match_report(
        room_code=room_code,
        round_num=round_num,
        table_num=table_num,
        disputer_name=disputer_name
    )
    if ok:
        return jsonify({"success": True, "message": res})
    return jsonify({"success": False, "message": str(res)}), 400

@app.route('/api/room/<room_code>/drop', methods=['POST'])
def api_room_drop_player(room_code):
    from tournament_room_manager import TournamentRoomManager
    trm = TournamentRoomManager()
    data = request.get_json() or {}
    
    player_name = data.get('player_name', '').strip()
    session_token = data.get('session_token', '').strip()
    round_num = data.get('round_num')
    
    if not player_name or not session_token:
        return jsonify({"success": False, "message": "Faltan credenciales del jugador (nombre o sesión)."}), 400
        
    ok, msg = trm.drop_player_from_room(
        room_code=room_code,
        player_name=player_name,
        session_token=session_token,
        round_num=round_num
    )
    if ok:
        return jsonify({"success": True, "message": msg})
    return jsonify({"success": False, "message": msg}), 400

@app.route('/api/room/<room_code>/dropped_players', methods=['GET'])
def api_room_get_drops(room_code):
    from tournament_room_manager import TournamentRoomManager
    trm = TournamentRoomManager()
    drops = trm.get_room_dropped_players(room_code)
    return jsonify({"success": True, "drops": drops})

# ==========================================
# ENDPOINTS AUTENTICADOS PARA EL ORGANIZADOR
# ==========================================

@app.route('/api/organizer/ping', methods=['GET'])
@organizer_auth_required
def api_organizer_ping():
    return jsonify({
        "success": True,
        "message": "Conexión autenticada establecida con el servidor remoto.",
        "server_time": datetime.now().isoformat()
    })

@app.route('/api/organizer/sync', methods=['POST'])
@organizer_auth_required
def api_organizer_sync():
    """Recibe un payload de snapshot o datos del torneo desde la app de escritorio y lo guarda en el hosting."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Cuerpo de solicitud JSON vacío."}), 400

        base_dir = os.path.dirname(os.path.abspath(__file__))
        mock_api_dir = os.path.join(base_dir, "mock_server", "public_api")
        os.makedirs(mock_api_dir, exist_ok=True)

        snapshot_type = data.get("type", "full_snapshot")
        
        if snapshot_type == "full_snapshot" and "snapshot" in data:
            snapshot_content = data["snapshot"]
            filename = data.get("filename", f"snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            snapshot_path = os.path.join(mock_api_dir, filename)
            with open(snapshot_path, "w", encoding="utf-8") as f:
                json.dump(snapshot_content, f, indent=2, ensure_ascii=False)

            manifest_path = os.path.join(mock_api_dir, "manifest.json")
            manifest = {
                "latest_snapshot": filename,
                "updated_at": datetime.now().isoformat()
            }
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2, ensure_ascii=False)

            return jsonify({
                "success": True,
                "message": f"Snapshot {filename} sincronizado y publicado con éxito.",
                "latest_snapshot": filename
            })
            
        elif snapshot_type == "room_sync":
            from tournament_room_manager import TournamentRoomManager
            trm = TournamentRoomManager()
            room_code = data.get("room_code")
            title = data.get("title", "Torneo Sincronizado")
            current_round = data.get("current_round", 1)
            pairings = data.get("pairings", [])
            standings = data.get("standings", [])
            timer_data = data.get("timer", {})
            
            # Buscar o crear sala
            existing = trm.get_room_by_code(room_code)
            if not existing:
                trm.create_or_get_room(title=title, room_code=room_code)
                
            live_data = {
                "title": title,
                "current_round": current_round,
                "matches": pairings,
                "standings": standings,
                "time_left": timer_data.get("time_left"),
                "timer_running": (timer_data.get("status") == "running"),
                "synced_at": datetime.now().strftime("%H:%M:%S")
            }
            trm.update_room_status(
                room_code=room_code,
                status="RUNNING",
                current_round=current_round,
                live_data_json=live_data
            )
            return jsonify({"success": True, "message": f"Sala {room_code} actualizada en el servidor remoto."})

        return jsonify({"success": False, "error": f"Tipo de sincronización '{snapshot_type}' no soportado."}), 400

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/organizer/events/<room_code>', methods=['GET'])
@organizer_auth_required
def api_organizer_events(room_code):
    """Devuelve reportes y drops de una sala para que la app de escritorio los procese."""
    from tournament_room_manager import TournamentRoomManager
    trm = TournamentRoomManager()
    
    room = trm.get_room_by_code(room_code)
    if not room:
        return jsonify({"success": False, "error": "Sala no encontrada."}), 404
        
    reports = trm.get_room_match_reports(room_code)
    drops = trm.get_room_dropped_players(room_code)
    
    return jsonify({
        "success": True,
        "room_code": room_code,
        "round": room.get("current_round", 1),
        "reports": reports,
        "drops": drops
    })

# ==========================================
# VISTAS WEB DEL PANEL DEL ORGANIZADOR
# ==========================================

@app.route('/organizer/login', methods=['GET', 'POST'])
def organizer_login():
    if request.method == 'POST':
        password = request.form.get("password", "")
        if password == ORGANIZER_ADMIN_PASSWORD:
            session["is_organizer_admin"] = True
            return redirect(url_for('organizer_panel'))
        else:
            return render_template_string(ORGANIZER_LOGIN_HTML, error="Contraseña de administrador incorrecta.")
    return render_template_string(ORGANIZER_LOGIN_HTML, error=None)

@app.route('/organizer/logout')
def organizer_logout():
    session.pop("is_organizer_admin", None)
    return redirect(url_for('organizer_login'))

@app.route('/organizer/panel')
def organizer_panel():
    if not session.get("is_organizer_admin", False):
        return redirect(url_for('organizer_login'))
    
    from tournament_room_manager import TournamentRoomManager
    trm = TournamentRoomManager()
    rooms = trm.get_active_rooms()
    return render_template_string(ORGANIZER_PANEL_HTML, rooms=rooms, api_key=ORGANIZER_API_KEY)

ORGANIZER_LOGIN_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Acceso Organizador - Subarashii Academy</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen flex items-center justify-center p-4">
    <div class="max-w-md w-full bg-slate-900 border border-slate-800 rounded-2xl p-8 shadow-2xl">
        <div class="text-center mb-6">
            <span class="text-4xl">👑</span>
            <h1 class="text-2xl font-black text-amber-400 mt-2">Panel del Organizador</h1>
            <p class="text-xs text-slate-400">Subarashii Academy / Duelorapido.cl</p>
        </div>
        {% if error %}
        <div class="bg-rose-950/80 border border-rose-500/50 text-rose-300 text-xs rounded-xl p-3 mb-4 text-center">
            {{ error }}
        </div>
        {% endif %}
        <form method="POST" class="space-y-4">
            <div>
                <label class="block text-xs font-bold text-slate-300 mb-1">Contraseña de Administrador</label>
                <input type="password" name="password" required autofocus placeholder="••••••••••••"
                       class="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-3 text-sm focus:border-amber-400 focus:outline-none">
            </div>
            <button type="submit" class="w-full bg-amber-500 hover:bg-amber-400 text-slate-950 font-black py-3 rounded-xl transition duration-200">
                Iniciar Sesión
            </button>
        </form>
        <div class="mt-6 text-center">
            <a href="/" class="text-xs text-slate-500 hover:text-slate-300 underline">Volver a la Academia</a>
        </div>
    </div>
</body>
</html>
"""

ORGANIZER_PANEL_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Panel de Control - Organizador</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen p-6">
    <div class="max-w-4xl mx-auto space-y-6">
        <div class="flex items-center justify-between border-b border-slate-800 pb-4">
            <div>
                <h1 class="text-2xl font-black text-amber-400 flex items-center gap-2">
                    <span>👑</span> Panel Central de Torneos
                </h1>
                <p class="text-xs text-slate-400">Servidor Cloud / Duelorapido.cl</p>
            </div>
            <div class="flex gap-2">
                <a href="/" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-xs rounded-lg font-bold">Ver Web Pública</a>
                <a href="/organizer/logout" class="px-4 py-2 bg-rose-900/60 hover:bg-rose-800 text-rose-300 text-xs rounded-lg font-bold">Cerrar Sesión</a>
            </div>
        </div>

        <div class="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-3">
            <h2 class="text-sm font-bold text-slate-300 uppercase tracking-wider">Credenciales de Conexión Local</h2>
            <p class="text-xs text-slate-400">Usa esta clave en la app de escritorio (Tournament Manager) para sincronizar torneos y recibir reportes en tiempo real:</p>
            <div class="flex items-center gap-2 bg-slate-950 p-3 rounded-xl border border-slate-800">
                <code class="text-xs text-amber-300 font-mono flex-1 select-all">{{ api_key }}</code>
                <span class="text-[10px] bg-slate-800 text-slate-400 px-2 py-1 rounded">API Key</span>
            </div>
        </div>

        <div class="space-y-4">
            <h2 class="text-base font-bold text-slate-200">Salas Activas en el Servidor</h2>
            {% if rooms %}
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                {% for r in rooms %}
                    <div class="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-3">
                        <div class="flex justify-between items-start">
                            <div>
                                <span class="text-xs font-mono font-bold text-amber-400">PIN: {{ r.room_code }}</span>
                                <h3 class="font-bold text-sm text-white">{{ r.title }}</h3>
                            </div>
                            <span class="text-xs px-2 py-1 rounded bg-emerald-950 border border-emerald-500/40 text-emerald-400 font-bold">Ronda {{ r.current_round }}</span>
                        </div>
                        <div class="flex gap-2 pt-2">
                            <a href="/sala/{{ r.room_code }}" target="_blank" class="flex-1 text-center bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold py-2 rounded-xl">Abrir Vista Sala</a>
                        </div>
                    </div>
                {% endfor %}
                </div>
            {% else %}
                <div class="bg-slate-900/50 border border-slate-800 rounded-2xl p-8 text-center text-slate-500 text-sm">
                    No hay salas activas en este momento. Lanza un torneo desde la app de escritorio con sincronización activa.
                </div>
            {% endif %}
        </div>
    </div>
</body>
</html>
"""

if __name__ == '__main__':
    print("Iniciando servidor web local de Duelorapido.cl (Subarashii Academy)...")
    app.run(port=8000, debug=True)

