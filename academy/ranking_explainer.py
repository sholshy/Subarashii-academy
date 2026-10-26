
def format_duel_date(raw_date):
    if not raw_date:
        return "-"
    raw = str(raw_date).strip()
    if len(raw) >= 10 and raw[4] == '-' and raw[7] == '-':
        return f"{raw[8:10]}/{raw[5:7]}/{raw[:4]}"
    parts = raw.split('-')
    if len(parts) == 3:
        if len(parts[0]) == 2 and len(parts[2]) == 2:
            return f"{parts[0]}/{parts[1]}/20{parts[2]}"
        elif len(parts[0]) == 4:
            return f"{parts[2][:2]}/{parts[1]}/{parts[0]}"
    return raw.replace('-', '/')

def format_short_date(raw_date):
    if not raw_date:
        return "-"
    raw = str(raw_date).strip()
    if len(raw) >= 10 and raw[4] == '-' and raw[7] == '-':
        return f"{raw[8:10]}/{raw[5:7]}"
    parts = raw.split('-')
    if len(parts) == 3:
        if len(parts[0]) == 2:
            return f"{parts[0]}/{parts[1]}"
        elif len(parts[0]) == 4:
            return f"{parts[2][:2]}/{parts[1]}"
    return raw[:5].replace('-', '/')
"""
Explicación del ranking de un jugador de la Academy.

Responde "¿por qué esta persona tiene este ranking?" a partir de:
  - sus duelos (rival, probabilidad esperada, K aplicado, puntos ganados/perdidos),
  - su XP por origen (duelos, misiones, logros, torneos),
  - su posición y el criterio de desempate (rating DESC, luego XP DESC),
  - la confiabilidad del rating (Glicko-2: RD).
"""

BASE_RATING = 1000

SOURCE_LABELS = {
    'MATCH': 'Duelos jugados',
    'MISSION': 'Misiones cumplidas',
    'ACHIEVEMENT': 'Logros',
    'TOURNAMENT': 'Participación en torneos',
    'OTHER': 'Otros',
}


def _confidence(phi, matches):
    if matches < 10:
        return "Provisorio (menos de 10 duelos)"
    if phi < 70:
        return "Alta"
    if phi < 110:
        return "Media"
    return "Baja"


def explain_player(cursor, player_id, format_name='GLOBAL', max_duels=None):
    cursor.execute("""
        SELECT a.*, p.name AS player_name
        FROM academy_profiles a JOIN players p ON p.id = a.player_id
        WHERE a.player_id = ? AND a.format_name = ?
    """, (player_id, format_name))
    prof = cursor.fetchone()
    if not prof:
        return None
    prof = dict(prof)
    pid = prof['id']

    # Posición (mismo criterio que process_tournament: rating DESC, xp DESC)
    cursor.execute("""
        SELECT id, player_id, current_rating, xp FROM academy_profiles
        WHERE format_name = ? ORDER BY current_rating DESC, xp DESC, id ASC
    """, (format_name,))
    standings = [dict(r) for r in cursor.fetchall()]
    position = next(i for i, r in enumerate(standings, 1) if r['id'] == pid)
    ahead = standings[position - 2] if position > 1 else None
    tied = [r for r in standings if r['current_rating'] == prof['current_rating'] and r['id'] != pid]

    # Duelos
    cursor.execute("""
        SELECT h.*, op.name AS opponent_name
        FROM academy_rating_history h
        LEFT JOIN players op ON op.id = h.opponent_id
        WHERE h.academy_profile_id = ? AND h.reason = 'MATCH_RESULT'
        ORDER BY h.id ASC
    """, (pid,))
    duels = []
    for h in cursor.fetchall():
        h = dict(h)
        res = h['result']
        if res is None:
            res_txt = 'Victoria' if h['rating_change'] > 0 else 'Derrota' if h['rating_change'] < 0 else '—'
        else:
            res_txt = 'Victoria' if res == 1 else 'Derrota' if res == 0 else 'Empate'
        duels.append({
            'date': format_duel_date(h['timestamp']),
            'short_date': format_short_date(h['timestamp']),
            'raw_date': h['timestamp'],
            'opponent': h['opponent_name'],
            'opponent_rating': h['opponent_rating'],
            'result': res_txt,
            'expected_win_pct': None if h['expected_score'] is None else round(h['expected_score'] * 100, 1),
            'k_factor': h['k_factor'],
            'rating_before': h['previous_rating'],
            'rating_change': h['rating_change'],
            'rating_after': h['new_rating'],
            'glicko_rd_after': None if h['glicko_phi'] is None else round(h['glicko_phi'], 1),
        })
    match_total = sum(d['rating_change'] for d in duels)
    other_adjust = prof['current_rating'] - BASE_RATING - match_total

    # XP por origen
    cursor.execute("""
        SELECT source, SUM(xp) AS xp, COUNT(*) AS n FROM academy_xp_log
        WHERE academy_profile_id = ? GROUP BY source
    """, (pid,))
    xp_by_source = {r['source']: {'xp': r['xp'], 'count': r['n']} for r in cursor.fetchall()}
    logged_xp = sum(v['xp'] for v in xp_by_source.values())
    unlogged_xp = prof['xp'] - logged_xp  # XP anterior a la existencia del log

    cursor.execute("""
        SELECT description, xp, timestamp FROM academy_xp_log
        WHERE academy_profile_id = ? AND source = 'MISSION' ORDER BY timestamp ASC
    """, (pid,))
    missions = [dict(r) for r in cursor.fetchall()]
    cursor.execute("""
        SELECT description, xp, timestamp FROM academy_xp_log
        WHERE academy_profile_id = ? AND source = 'ACHIEVEMENT' ORDER BY timestamp ASC
    """, (pid,))
    achievements = [dict(r) for r in cursor.fetchall()]

    # Racha actual y mejor racha de victorias + Rivalidades frecuentes (Head-to-Head, estilo Rank-In)
    cur_streak = 0
    best_win_streak = 0
    running_win = 0
    h2h_map = {}
    for d in duels:
        if d['result'] == 'Victoria':
            running_win += 1
            best_win_streak = max(best_win_streak, running_win)
            cur_streak = cur_streak + 1 if cur_streak >= 0 else 1
        elif d['result'] == 'Derrota':
            running_win = 0
            cur_streak = cur_streak - 1 if cur_streak <= 0 else -1
        else:
            running_win = 0
            cur_streak = 0
        opp_name = d['opponent']
        if opp_name:
            rec = h2h_map.setdefault(opp_name, {'opponent': opp_name, 'matches': 0, 'wins': 0, 'losses': 0, 'net_elo': 0})
            rec['matches'] += 1
            if d['result'] == 'Victoria':
                rec['wins'] += 1
            elif d['result'] == 'Derrota':
                rec['losses'] += 1
            rec['net_elo'] += d['rating_change']

    rivalries = sorted(h2h_map.values(), key=lambda x: (-x['matches'], -abs(x['net_elo'])))[:5]

    phi = prof.get('glicko_phi') or 350
    mu = prof.get('glicko_mu') or 1500
    shown = duels if max_duels is None else duels[-max_duels:]

    return {
        'player': prof['player_name'],
        'rating': prof['current_rating'],
        'highest_rating': prof['highest_rating'],
        'dorm': prof['dorm'],
        'level': prof['level'],
        'xp': prof['xp'],
        'matches': prof['matches_played'],
        'wins': prof['wins'],
        'losses': prof['losses'],
        'position': position,
        'total_players': len(standings),
        'tied_on_rating': len(tied),
        'points_to_player_ahead': None if not ahead else ahead['current_rating'] - prof['current_rating'],
        'streak': {
            'current': cur_streak,
            'best_win_streak': best_win_streak,
            'label': f"{cur_streak}W" if cur_streak > 0 else f"{abs(cur_streak)}L" if cur_streak < 0 else "—",
        },
        'rivalries': rivalries,
        'glicko': {
            'rating': round(mu), 'rd': round(phi, 1),
            'interval': (round(prof['current_rating'] - 2 * phi), round(prof['current_rating'] + 2 * phi)),
            'confidence': _confidence(phi, prof['matches_played']),
        },
        'rating_breakdown': {
            'base': BASE_RATING, 'from_duels': match_total, 'other_adjustments': other_adjust,
        },
        'duels': shown,
        'duels_total': len(duels),
        'xp_by_source': xp_by_source,
        'xp_unlogged': unlogged_xp,
        'missions': missions,
        'achievements': achievements,
    }


def format_explanation(e):
    """Texto legible en español de `explain_player`."""
    if not e:
        return "Jugador sin perfil en la Academy."
    L = []
    L.append(f"=== {e['player']} — Puesto {e['position']} de {e['total_players']} ===")
    L.append(f"Rating: {e['rating']} (máx. {e['highest_rating']}) · {e['dorm']} · Nivel {e['level']} ({e['xp']} XP)")
    st = e.get('streak', {})
    streak_txt = f" · Racha: {st.get('label', '—')} (mejor: {st.get('best_win_streak', 0)}W)" if st else ""
    L.append(f"Duelos: {e['matches']} jugados, {e['wins']} ganados, {e['losses']} perdidos{streak_txt}")
    L.append("")
    L.append("¿Cómo se ordena el ranking? Por rating (ELO); si hay empate, por XP.")
    if e['tied_on_rating']:
        L.append(f"  → Hay {e['tied_on_rating']} jugador(es) con el mismo rating; se desempata por XP.")
    if e['points_to_player_ahead']:
        L.append(f"  → Le faltan {e['points_to_player_ahead']} puntos para alcanzar al jugador de arriba.")
    b = e['rating_breakdown']
    L.append("")
    L.append("De dónde sale el rating:")
    L.append(f"  {b['base']} (base) {b['from_duels']:+d} (duelos)"
             + (f" {b['other_adjustments']:+d} (otros ajustes)" if b['other_adjustments'] else "")
             + f" = {e['rating']}")
    g = e['glicko']
    L.append(f"Confiabilidad (Glicko-2): {g['confidence']} · rango probable {g['interval'][0]}–{g['interval'][1]} (RD {g['rd']})")

    if e.get('rivalries'):
        L.append("")
        L.append("Rivalidades frecuentes (Head-to-Head):")
        for rv in e['rivalries'][:3]:
            L.append(f"  vs {rv['opponent']}: {rv['wins']}W - {rv['losses']}L ({rv['matches']} duelos, balance {rv['net_elo']:+d} ELO)")

    L.append("")
    L.append(f"Duelos ({e['duels_total']}; mostrando {len(e['duels'])}):")
    for d in e['duels']:
        rival = d['opponent'] or 'rival desconocido'
        if d['expected_win_pct'] is None:
            why = ""
        else:
            why = f" · esperaba ganar {d['expected_win_pct']}% · K={d['k_factor']}"
        L.append(f"  {str(d['date'])[:10]} vs {rival} ({d['opponent_rating'] or '?'}): "
                 f"{d['result']} {d['rating_change']:+d} → {d['rating_after']}{why}")

    L.append("")
    L.append("XP (afecta nivel y desempate):")
    for src, label in SOURCE_LABELS.items():
        v = e['xp_by_source'].get(src)
        if v:
            L.append(f"  {label}: {v['xp']} XP ({v['count']})")
    if e['xp_unlogged'] > 0:
        L.append(f"  Anterior al registro detallado: {e['xp_unlogged']} XP")
    for m in e['missions']:
        L.append(f"    ✔ {m['description']} (+{m['xp']} XP)")
    for a in e['achievements']:
        L.append(f"    ★ {a['description']} (+{a['xp']} XP)")
    return "\n".join(L)
