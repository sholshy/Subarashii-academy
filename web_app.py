import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_connection
import csv
import json
import os
from datetime import datetime
from io import StringIO
from flask import Response
from league_manager import LeagueManager
from store_manager import StoreManager
from tournament_manager import TournamentManager
from tournament_graphics import generate_pairings_image, generate_top8_bracket_image, generate_standings_image
from league_graphics import generate_top8_standings as generate_league_top8_standings, generate_trend_chart as generate_league_trend_chart
from store_graphics import generate_activity_chart

# Re-using logic from app.py
from app import draw_header, draw_section, parse_decklist, WIDTH, HEIGHT, OUTPUT_DIR
from PIL import Image, ImageDraw

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(24))

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, username, role):
        self.id = str(id)
        self.username = username
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    conn = get_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if user:
        return User(user['id'], user['username'], user['role'])
    return None

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_connection()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            user_obj = User(user['id'], user['username'], user['role'])
            login_user(user_obj)
            return redirect(url_for('index'))
        else:
            flash('Usuario o contraseña incorrectos.', 'danger')
            
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if os.environ.get('ALLOW_REGISTRATION') != '1':
        flash('El registro público está deshabilitado.', 'danger')
        return redirect(url_for('login'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Debes ingresar usuario y contraseña.', 'danger')
            return redirect(url_for('register'))
            
        hashed = generate_password_hash(password)
        conn = get_connection()
        try:
            conn.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, hashed))
            conn.commit()
            flash('Administrador creado exitosamente. Ya puedes iniciar sesión.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash('Ese nombre de usuario ya existe.', 'danger')
        finally:
            conn.close()
            
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/stores', methods=['GET', 'POST'])
@login_required
def stores():
    manager = StoreManager()
    
    if request.method == 'POST':
        action = request.form.get('action')
        store_name = request.form.get('store_name')
        new_name = request.form.get('new_name')
        
        try:
            if action == 'add':
                manager.add_store(store_name)
                flash(f'Tienda "{store_name}" añadida exitosamente.', 'success')
            elif action == 'set_active':
                manager.set_active_store(store_name)
                flash(f'Tienda "{store_name}" marcada como activa.', 'success')
            elif action == 'remove':
                manager.remove_store(store_name)
                flash(f'Tienda "{store_name}" eliminada.', 'success')
            elif action == 'rename':
                manager.rename_store(store_name, new_name)
                flash(f"Tienda renombrada a '{new_name}'.", "success")
        except ValueError as e:
            flash(str(e), 'danger')
            
        return redirect(url_for('stores'))
        
    conn = get_connection()
    stores_list = conn.execute("SELECT * FROM stores").fetchall()
    conn.close()
    
    # Obtener stats de cada tienda
    stores_with_stats = []
    for s in stores_list:
        stats = manager.get_store_stats(s['name'])
        stores_with_stats.append({
            'id': s['id'],
            'name': s['name'],
            'is_active': s['is_active'],
            'stats': stats
        })
        
    return render_template('stores.html', stores=stores_with_stats)

@app.route('/api/stores/export/metrics')
@login_required
def api_stores_export_metrics():
    manager = StoreManager()
    active_store = manager.get_active_store()
    if not active_store:
        flash("No hay tienda activa.", "danger")
        return redirect(url_for('stores'))
        
    timeline_data = manager.get_attendance_timeline(active_store)
    from store_graphics import generate_activity_chart
    img = generate_activity_chart(active_store, timeline_data)
    
    filename = f"metricas_{active_store.lower().replace(' ', '_')}.png"
    img.save(os.path.join(OUTPUT_DIR, filename))
    return render_template('preview.html', image_filename=filename)

@app.route('/stores/reset')
@login_required
def stores_reset():
    return render_template('exodia_reset.html')

@app.route('/api/stores/factory_reset', methods=['POST'])
@login_required
def api_stores_factory_reset():
    pieces = request.form.get('pieces', '')
    selected_pieces = set(pieces.split(','))
    exodia_pieces = {"Exodia", "Brazo Der", "Brazo Izq", "Pierna Der", "Pierna Izq"}
    
    if selected_pieces == exodia_pieces:
        from database import factory_reset
        factory_reset()
        
        # Reset current session states if any, and logout
        from flask_login import logout_user
        logout_user()
        session.clear()
        return redirect(url_for('login'))
    else:
        flash("No has reunido las piezas correctas o incluiste cartas adicionales. Exodia no responde a tu llamado.", "danger")
        return redirect(url_for('stores_reset'))

def get_tournament_autosave_path():
    return os.path.abspath(os.path.join("data", "tournament_autosave.json"))

def load_tournament_manager():
    path = get_tournament_autosave_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            return TournamentManager.from_dict(payload.get("manager", {})), payload.get("ui", {})
        except Exception:
            return TournamentManager(), {}
    return TournamentManager(), {}

def save_tournament_manager(manager, ui_state=None):
    if ui_state is None:
        ui_state = {}
    path = get_tournament_autosave_path()
    payload = {
        "version": 1,
        "saved_at": datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
        "manager": manager.to_dict(),
        "ui": ui_state
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

@app.route('/tournament')
@login_required
def tournament_index():
    manager, _ = load_tournament_manager()
    if manager.status in ["running", "finished"] and manager.rounds:
        return redirect(url_for('tournament_round'))
    return redirect(url_for('tournament_setup'))

@app.route('/tournament/setup', methods=['GET', 'POST'])
@login_required
def tournament_setup():
    manager, ui_state = load_tournament_manager()
    
    conn = get_connection()
    frequent_players = conn.execute("SELECT * FROM players ORDER BY name ASC").fetchall()
    conn.close()
    
    return render_template('tournament_setup.html', manager=manager, frequent_players=frequent_players)

@app.route('/api/tournament/add_player', methods=['POST'])
@login_required
def api_add_player():
    name = request.form.get('name')
    k_id = request.form.get('konami_id', '')
    if not name:
        flash("El nombre es obligatorio.", "danger")
        return redirect(url_for('tournament_setup'))
        
    manager, ui_state = load_tournament_manager()
    for p in manager.players:
        if p.name.lower() == name.lower() or (k_id and getattr(p, 'konami_id', '') == k_id):
            flash("Jugador duplicado en este torneo.", "danger")
            return redirect(url_for('tournament_setup'))
            
    manager.add_player(name, k_id)
    save_tournament_manager(manager, ui_state)
    flash(f"{name} añadido al torneo.", "success")
    return redirect(url_for('tournament_setup'))

@app.route('/api/tournament/remove_player', methods=['POST'])
@login_required
def api_remove_player():
    name = request.form.get('name')
    manager, ui_state = load_tournament_manager()
    manager.players = [p for p in manager.players if p.name != name]
    save_tournament_manager(manager, ui_state)
    return redirect(url_for('tournament_setup'))

@app.route('/api/tournament/start', methods=['POST'])
@login_required
def api_start_tournament():
    manager, ui_state = load_tournament_manager()
    mode = request.form.get('mode', 'swiss')
    format_name = request.form.get('format_name', 'GOAT')
    try:
        manager.start_tournament(mode=mode, format_name=format_name)
        save_tournament_manager(manager, ui_state)
        return redirect(url_for('tournament_round'))
    except Exception as e:
        flash(str(e), "danger")
        return redirect(url_for('tournament_setup'))

@app.route('/tournament/round')
@login_required
def tournament_round():
    manager, ui_state = load_tournament_manager()
    if manager.status == "setup":
        return redirect(url_for('tournament_setup'))
    if manager.status == "finished":
        return redirect(url_for('tournament_standings'))
        
    matches = manager.get_current_matches()
    standings = manager.get_standings()
    return render_template('tournament_round.html', manager=manager, matches=matches, standings=standings)

@app.route('/tournament/standings')
@login_required
def tournament_standings():
    manager, ui_state = load_tournament_manager()
    if manager.status != "finished":
        return redirect(url_for('tournament_index'))
        
    standings = manager.get_standings()
    ranked = manager.get_ranked_standings()
    notes = manager.get_tiebreaker_notes(standings)
    return render_template('tournament_standings.html', manager=manager, ranked=ranked, notes=notes)

@app.route('/api/tournament/export_league', methods=['POST'])
@login_required
def api_tournament_export_league():
    manager, ui_state = load_tournament_manager()
    if manager.status != "finished":
        return redirect(url_for('tournament_index'))
        
    if ui_state.get('exported_to_league'):
        flash("Este torneo ya fue exportado a la liga.", "warning")
        return redirect(url_for('tournament_standings'))
        
    try:
        sm = StoreManager()
        active_store = sm.get_active_store()
        
        # Obtenemos la ruta de base de datos activa según StoreManager y creamos LeagueManager con ese formato
        league_path = sm.get_active_league_db_path()
        lm = LeagueManager(db_path=league_path, current_format=manager.format_name)
        
        date_val = datetime.now().strftime("%d-%m-%y")
        standings = manager.get_standings()
        ranks = {player: rank for rank, player in manager.get_ranked_standings()}
        
        results = []
        for p in standings:
            rank = ranks.get(p, 0)
            placement_points = 0
            if rank == 1:
                placement_points = 10
            elif rank <= 4:
                placement_points = 5

            results.append({
                "name": p.name,
                "match_pts": p.points,
                "placement_points": placement_points,
                "phone": getattr(p, 'phone', ''),
                "email": getattr(p, 'email', '')
            })
            
        lm.export_tournament_results(date_val, results, profit=getattr(manager, 'tournament_profit', 0.0))
        
        ui_state['exported_to_league'] = True
        save_tournament_manager(manager, ui_state)
        flash("Resultados exportados a la Liga exitosamente.", "success")
    except Exception as e:
        flash(f"Error al exportar a liga: {str(e)}", "danger")
        
    return redirect(url_for('tournament_standings'))

@app.route('/api/tournament/report', methods=['POST'])
@login_required
def api_report_match():
    manager, ui_state = load_tournament_manager()
    p1_name = request.form.get('p1_name')
    p2_name = request.form.get('p2_name')
    result = request.form.get('result')
    
    matches = manager.get_current_matches()
    for m in matches:
        m_p1_name = m.p1.name if m.p1 else "BYE"
        m_p2_name = m.p2.name if m.p2 else "BYE"
        if m_p1_name == p1_name and m_p2_name == p2_name:
            m.report(result)
            break
            
    save_tournament_manager(manager, ui_state)
    return redirect(url_for('tournament_round'))

@app.route('/api/tournament/undo', methods=['POST'])
@login_required
def api_undo_match():
    manager, ui_state = load_tournament_manager()
    p1_name = request.form.get('p1_name')
    p2_name = request.form.get('p2_name')
    
    matches = manager.get_current_matches()
    for m in matches:
        m_p1_name = m.p1.name if m.p1 else "BYE"
        m_p2_name = m.p2.name if m.p2 else "BYE"
        if m_p1_name == p1_name and m_p2_name == p2_name:
            manager.undo_match(m)
            break
            
    save_tournament_manager(manager, ui_state)
    return redirect(url_for('tournament_round'))

@app.route('/api/tournament/next_round', methods=['POST'])
@login_required
def api_next_round():
    manager, ui_state = load_tournament_manager()
    if not manager.all_matches_reported():
        flash("Debes reportar todos los resultados primero.", "danger")
        return redirect(url_for('tournament_round'))
        
    manager.generate_next_round()
    save_tournament_manager(manager, ui_state)
    return redirect(url_for('tournament_round'))

@app.route('/api/tournament/drop_player', methods=['POST'])
@login_required
def api_drop_player():
    manager, ui_state = load_tournament_manager()
    player_name = request.form.get('player_name')
    if player_name:
        manager.drop_player(player_name)
        save_tournament_manager(manager, ui_state)
        flash(f"Jugador {player_name} ha sido retirado (Drop).", "success")
    return redirect(url_for('tournament_round'))

@app.route('/api/tournament/export/pairings')
@login_required
def api_tournament_export_pairings():
    manager, _ = load_tournament_manager()
    sm = StoreManager()
    active_store = sm.get_active_store()
    date_val = datetime.now().strftime("%d-%m-%y")
    img = generate_pairings_image(manager, active_store, date_val)
    filename = f"pareos_{manager.current_round}_{manager.format_name}.png"
    img.save(os.path.join(OUTPUT_DIR, filename))
    return render_template('preview.html', image_filename=filename)

@app.route('/api/tournament/export/bracket')
@login_required
def api_tournament_export_bracket():
    manager, _ = load_tournament_manager()
    sm = StoreManager()
    active_store = sm.get_active_store()
    date_val = datetime.now().strftime("%d-%m-%y")
    img = generate_top8_bracket_image(manager, active_store, date_val)
    filename = f"top8_{manager.format_name}.png"
    img.save(os.path.join(OUTPUT_DIR, filename))
    return render_template('preview.html', image_filename=filename)

@app.route('/api/tournament/export/standings')
@login_required
def api_tournament_export_standings():
    manager, _ = load_tournament_manager()
    sm = StoreManager()
    active_store = sm.get_active_store()
    date_val = datetime.now().strftime("%d-%m-%y")
    img = generate_standings_image(manager, active_store, date_val)
    filename = f"standings_final_{manager.format_name}.png"
    img.save(os.path.join(OUTPUT_DIR, filename))
    return render_template('preview.html', image_filename=filename)

@app.route('/api/tournament/rollback', methods=['POST'])
@login_required
def api_rollback_round():
    manager, ui_state = load_tournament_manager()
    manager.rollback_round()
    save_tournament_manager(manager, ui_state)
    return redirect(url_for('tournament_round'))

@app.route('/api/tournament/reset', methods=['POST'])
@login_required
def api_reset_tournament():
    manager, ui_state = load_tournament_manager()
    manager.rollback_to_setup()
    save_tournament_manager(manager, ui_state)
    return redirect(url_for('tournament_setup'))

@app.route('/generator', methods=['GET', 'POST'])
@login_required
def generator():
    image_filename = None
    if request.method == 'POST':
        winner = request.form.get("winner", "CHAMPION")
        event = request.form.get("event", "YGO EVENT")
        decklist = request.form.get("decklist", "")
        
        sections = parse_decklist(decklist)
        
        img = Image.new("RGB", (WIDTH, HEIGHT), "#020617")
        draw = ImageDraw.Draw(img)
        draw_header(draw, winner, event)
        
        draw_section(img, sections["main"], x=60, y=320, cols=10, card_width=100, gap=8)
        draw_section(img, sections["extra"], x=60, y=1120, cols=5, card_width=95, gap=8)
        draw_section(img, sections["side"], x=620, y=1120, cols=5, card_width=95, gap=8)
        
        filename = f"ygo_post_{current_user.username}.png"
        image_path = os.path.join(OUTPUT_DIR, filename)
        img.save(image_path)
        image_filename = filename

    return render_template('generator.html', image_filename=image_filename)

@app.route('/download_image/<filename>')
@login_required
def download_image(filename):
    from flask import send_from_directory
    return send_from_directory(OUTPUT_DIR, filename, as_attachment=True)

@app.route('/serve_image/<filename>')
@login_required
def serve_image(filename):
    from flask import send_from_directory
    return send_from_directory(OUTPUT_DIR, filename)

@app.route('/cache/<filename>')
@login_required
def cache_image(filename):
    from flask import send_from_directory
    return send_from_directory('Cache', filename)

@app.route('/prizes')
@login_required
def prizes():
    return render_template('prizes.html')

@app.route('/leagues')
@login_required
def leagues():
    format_name = request.args.get('format', 'GOAT')
    manager = LeagueManager(current_format=format_name)
    standings = manager.get_ranked_standings()
    return render_template('leagues.html', standings=standings, current_format=format_name)

@app.route('/leagues/progress', methods=['GET', 'POST'])
@login_required
def leagues_progress():
    format_name = request.args.get('format', 'GOAT')
    manager = LeagueManager(current_format=format_name)
    players = sorted([p.name for p in manager.players], key=str.lower)
    
    selected_player = request.args.get('player', players[0] if players else '')
    selected_tournament_idx = request.args.get('tournament_idx', type=int, default=-1)
    
    player_obj = manager.get_player(selected_player) if selected_player else None
    tournaments = []
    current_grid = [False] * 9
    
    if player_obj:
        global_tournaments = manager.get_global_tournaments()
        t_id_to_week = {t['id']: i + 1 for i, t in enumerate(global_tournaments)}
        
        for idx, week in enumerate(player_obj.history):
            date = week.get("date", "sin fecha")
            t_id = week.get("tournament_id")
            week_num = t_id_to_week.get(t_id, idx + 1)
            tournaments.append({'idx': idx, 'label': f"Semana {week_num} - {date}"})
            
        if selected_tournament_idx == -1 and tournaments:
            selected_tournament_idx = tournaments[-1]['idx']
            
        if 0 <= selected_tournament_idx < len(player_obj.history):
            current_grid = player_obj.history[selected_tournament_idx].get("bingo_grid", [False]*9)
            
    if request.method == 'POST':
        player_name = request.form.get('player_name')
        t_idx = request.form.get('tournament_idx', type=int)
        
        # Read the 9 checkboxes
        new_grid = []
        for i in range(9):
            val = request.form.get(f'bingo_{i}') == 'on'
            new_grid.append(val)
            
        try:
            manager.update_tournament_missions(player_name, t_idx, new_grid)
            flash(f"Misiones actualizadas para {player_name}.", "success")
        except Exception as e:
            flash(f"Error: {e}", "danger")
            
        return redirect(url_for('leagues_progress', format=format_name, player=player_name, tournament_idx=t_idx))

    return render_template('league_progress.html', 
                           current_format=format_name,
                           players=players,
                           selected_player=selected_player,
                           tournaments=tournaments,
                           selected_tournament_idx=selected_tournament_idx,
                           current_grid=current_grid)

@app.route('/leagues/export')
@login_required
def leagues_export():
    format_name = request.args.get('format', 'GOAT')
    manager = LeagueManager(current_format=format_name)
    standings = manager.get_ranked_standings()
    
    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(['Posicion', 'Jugador', 'Mazo', 'Puntos Torneo', 'Asistencia', 'Misiones', 'Bingo', 'Total', 'Fecha Exportacion', 'Formato'])
    
    for rank, p in standings:
        m, a, miss, bingo = p.get_points_composition()
        writer.writerow([
            rank, p.name, p.deck_name,
            m, a, miss, bingo,
            p.get_total_points(),
            datetime.now().strftime("%Y-%m-%d"),
            format_name
        ])
    
    return Response(
        si.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename=liga_{format_name.lower().replace(' ', '_')}.csv"}
    )

@app.route('/api/leagues/export/png')
@login_required
def api_leagues_export_png():
    format_name = request.args.get('format', 'GOAT')
    mode = request.args.get('mode', 'top8') # top8 or trend
    manager = LeagueManager(current_format=format_name)
    if mode == 'trend':
        img = generate_league_trend_chart(manager)
    else:
        img = generate_league_top8_standings(manager)
        
    filename = f"liga_{format_name}_{mode}.png"
    img.save(os.path.join(OUTPUT_DIR, filename))
    return render_template('preview.html', image_filename=filename)

# ==========================================
# ACADEMY API ENDPOINTS (Public)
# ==========================================

@app.route('/api/academy/leaderboard')
def api_academy_leaderboard():
    conn = get_connection()
    conn.row_factory = sqlite3.Row if 'sqlite3' in globals() else None
    
    import sqlite3
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT a.id as profile_id, p.id as player_id, p.name, 
               a.current_rating, a.highest_rating, a.dorm, 
               a.xp, a.level, a.matches_played, a.wins, a.losses
        FROM academy_profiles a
        JOIN players p ON a.player_id = p.id
        WHERE a.format_name = 'GLOBAL'
        ORDER BY a.current_rating DESC, a.xp DESC
    """)
    
    results = []
    for rank, row in enumerate(cursor.fetchall(), 1):
        mp = row['matches_played']
        wins = row['wins']
        wr = round((wins / mp * 100), 1) if mp > 0 else 0.0
        
        results.append({
            "rank": rank,
            "profile_id": row['profile_id'],
            "player_id": row['player_id'],
            "name": row['name'],
            "dorm": row['dorm'],
            "level": row['level'],
            "xp": row['xp'],
            "current_rating": row['current_rating'],
            "highest_rating": row['highest_rating'],
            "matches_played": mp,
            "wins": wins,
            "losses": row['losses'],
            "win_rate": wr
        })
        
    conn.close()
    return jsonify({"leaderboard": results})

@app.route('/api/academy/profile/<int:profile_id>')
def api_academy_profile(profile_id):
    import sqlite3
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Base Profile
    cursor.execute("""
        SELECT a.id as profile_id, p.id as player_id, p.name, 
               a.current_rating, a.highest_rating, a.dorm, 
               a.xp, a.level, a.matches_played, a.wins, a.losses
        FROM academy_profiles a
        JOIN players p ON a.player_id = p.id
        WHERE a.id = ? AND a.format_name = 'GLOBAL'
    """, (profile_id,))
    
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Profile not found"}), 404
        
    mp = row['matches_played']
    wins = row['wins']
    wr = round((wins / mp * 100), 1) if mp > 0 else 0.0
    
    profile_data = {
        "profile_id": row['profile_id'],
        "player_id": row['player_id'],
        "name": row['name'],
        "dorm": row['dorm'],
        "level": row['level'],
        "xp": row['xp'],
        "current_rating": row['current_rating'],
        "highest_rating": row['highest_rating'],
        "matches_played": mp,
        "wins": wins,
        "losses": row['losses'],
        "win_rate": wr
    }
    
    # Achievements
    cursor.execute("SELECT achievement_id, unlocked_at FROM academy_achievements WHERE academy_profile_id=?", (profile_id,))
    achievements = [dict(r) for r in cursor.fetchall()]
    
    # Missions
    cursor.execute("SELECT mission_id, progress, completed, completed_at, expires_at FROM academy_missions WHERE academy_profile_id=?", (profile_id,))
    missions = [dict(r) for r in cursor.fetchall()]
    
    # Load Catalogs
    ach_cat, msn_cat = {}, {}
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    try:
        with open(os.path.join(base_dir, "data", "achievements", "catalog.json"), 'r', encoding='utf-8') as f:
            for a in json.load(f).get("achievements", []):
                ach_cat[a["id"]] = a
    except: pass
    
    try:
        with open(os.path.join(base_dir, "data", "missions", "catalog.json"), 'r', encoding='utf-8') as f:
            for m in json.load(f).get("missions", []):
                msn_cat[m["id"]] = m
    except: pass
    
    # Merge catalog info
    for a in achievements:
        cat = ach_cat.get(a['achievement_id'], {})
        a['name'] = cat.get('name', a['achievement_id'])
        a['description'] = cat.get('description', '')
        
    for m in missions:
        cat = msn_cat.get(m['mission_id'], {})
        m['name'] = cat.get('name', m['mission_id'])
        m['target'] = cat.get('target_value', 1)
        
    profile_data["achievements"] = achievements
    profile_data["missions"] = missions
    
    conn.close()
    return jsonify(profile_data)

if __name__ == '__main__':
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    app.run(debug=True, port=5000)
