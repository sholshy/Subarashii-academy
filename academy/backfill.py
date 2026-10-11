"""
Reconstrucción de la trazabilidad para datos procesados ANTES de que existieran
rival / expectativa / K / Glicko-2 / log de XP.

Todo se deriva de tablas que ya existen (tournament_matches, academy_rating_history,
academy_achievements, academy_missions, tournament_results), usando las mismas reglas
que AcademyEngine. Es idempotente: solo toca filas que aún no tienen los datos.
"""
import json
import math
import os

from academy.glicko2 import Glicko2, Glicko2Rating

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _k(matches_before):
    return 64 if matches_before < 10 else 32 if matches_before < 30 else 24


def _expected(ra, rb):
    return 1 / (1 + math.pow(10, (rb - ra) / 400))


def _load_catalog(kind, key):
    path = os.path.join(_BASE, "data", kind, "catalog.json")
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return {x["id"]: x for x in json.load(f).get(key, [])}


def _match_groups(cursor, where):
    cursor.execute(f"""
        SELECT h.id, h.academy_profile_id AS pid, h.match_id, h.previous_rating, h.rating_change,
               h.timestamp, a.player_id
        FROM academy_rating_history h JOIN academy_profiles a ON a.id = h.academy_profile_id
        WHERE h.reason = 'MATCH_RESULT' AND h.match_id IS NOT NULL AND {where}
        ORDER BY h.id ASC
    """)
    groups = {}
    for r in cursor.fetchall():
        groups.setdefault(r['match_id'], []).append(dict(r))
    return groups


def _backfill_duels(cursor):
    # Nº de duelo real de cada fila dentro de su perfil (por id ASC, no por fecha DD-MM-YY)
    cursor.execute("""SELECT id, academy_profile_id, k_factor FROM academy_rating_history
                      WHERE reason = 'MATCH_RESULT' ORDER BY id ASC""")
    counter, idx = {}, {}
    for r in cursor.fetchall():
        idx[r['id']] = counter.get(r['academy_profile_id'], 0)
        counter[r['academy_profile_id']] = idx[r['id']] + 1
        expected_k = _k(idx[r['id']])
        if r['k_factor'] != expected_k:
            cursor.execute("UPDATE academy_rating_history SET k_factor = ? WHERE id = ?", (expected_k, r['id']))

    groups = _match_groups(cursor, "h.opponent_id IS NULL")
    if not groups:
        return

    cursor.execute("SELECT id, p1_id, p2_id, result_text FROM tournament_matches")
    matches = {r['id']: dict(r) for r in cursor.fetchall()}

    for mid, rows in groups.items():
        m = matches.get(mid)
        if not m:
            continue
        for row in rows:
            if row['player_id'] == m['p1_id']:
                opp_player, is_p1 = m['p2_id'], True
            elif row['player_id'] == m['p2_id']:
                opp_player, is_p1 = m['p1_id'], False
            else:
                continue
            res_txt = m['result_text']
            if res_txt == 'P1_WIN':
                score = 1.0 if is_p1 else 0.0
            elif res_txt == 'P2_WIN':
                score = 0.0 if is_p1 else 1.0
            elif res_txt == 'DRAW':
                score = 0.5
            else:
                score = 1.0 if row['rating_change'] > 0 else 0.0 if row['rating_change'] < 0 else 0.5
            opp_row = next((o for o in rows if o['player_id'] == opp_player), None)
            opp_rating = opp_row['previous_rating'] if opp_row else None
            expected = _expected(row['previous_rating'], opp_rating) if opp_rating is not None else None
            cursor.execute("""
                UPDATE academy_rating_history
                SET opponent_id = ?, opponent_rating = ?, expected_score = ?, k_factor = ?, result = ?
                WHERE id = ?
            """, (opp_player, opp_rating, expected, _k(idx[row['id']]), score, row['id']))


def _backfill_glicko(cursor):
    """Reproduce cronológicamente los duelos antiguos para obtener Glicko-2 / RD."""
    groups = _match_groups(cursor, "h.glicko_phi IS NULL")
    if not groups:
        return

    # Perfiles elegibles: ninguno de sus duelos tiene Glicko calculado aún
    cursor.execute("""SELECT DISTINCT academy_profile_id AS pid FROM academy_rating_history
                      WHERE reason = 'MATCH_RESULT' AND glicko_phi IS NOT NULL""")
    already = {r['pid'] for r in cursor.fetchall()}

    env = Glicko2()
    state = {}

    def get(pid):
        if pid not in state:
            cursor.execute("SELECT glicko_mu, glicko_phi, glicko_sigma FROM academy_profiles WHERE id = ?", (pid,))
            r = cursor.fetchone()
            if pid in already and r and r['glicko_mu'] is not None:
                state[pid] = Glicko2Rating(r['glicko_mu'], r['glicko_phi'], r['glicko_sigma'])
            else:
                state[pid] = env.create_rating()
        return state[pid]

    cursor.execute("""SELECT id, opponent_id, result FROM academy_rating_history WHERE reason='MATCH_RESULT'""")
    info = {r['id']: dict(r) for r in cursor.fetchall()}

    ordered = sorted(groups.items(), key=lambda kv: kv[1][0]['id'])
    touched = set()
    for mid, rows in ordered:
        if len(rows) != 2 or rows[0]['pid'] == rows[1]['pid']:
            continue
        a, b = rows
        ia, ib = info[a['id']], info[b['id']]
        if ia['result'] is None or ib['result'] is None:
            continue
        ga, gb = get(a['pid']), get(b['pid'])
        na = env.rate(ga, [(ia['result'], gb)]) if a['pid'] not in already else ga
        nb = env.rate(gb, [(ib['result'], ga)]) if b['pid'] not in already else gb
        for row, new in ((a, na), (b, nb)):
            state[row['pid']] = new
            touched.add(row['pid'])
            cursor.execute("UPDATE academy_rating_history SET glicko_mu = ?, glicko_phi = ? WHERE id = ?",
                           (new.mu, new.phi, row['id']))
    for pid in touched:
        if pid in already:
            continue
        s = state[pid]
        cursor.execute("UPDATE academy_profiles SET glicko_mu = ?, glicko_phi = ?, glicko_sigma = ? WHERE id = ?",
                       (s.mu, s.phi, s.sigma, pid))


def _backfill_xp(cursor):
    """Reconstruye el origen del XP de perfiles históricos."""
    ach_cat = _load_catalog("achievements", "achievements")
    msn_cat = _load_catalog("missions", "missions")

    # Torneos que realmente fueron procesados en Academy (tienen partidas registradas en el historial)
    cursor.execute("""SELECT DISTINCT tm.tournament_id FROM academy_rating_history h
                      JOIN tournament_matches tm ON tm.id = h.match_id WHERE h.match_id IS NOT NULL""")
    processed_tournaments = {r['tournament_id'] for r in cursor.fetchall()}

    cursor.execute("""SELECT a.id, a.player_id, a.xp,
                             COALESCE((SELECT SUM(xp) FROM academy_xp_log WHERE academy_profile_id = a.id), 0) AS logged
                      FROM academy_profiles a WHERE a.xp > 0""")
    profiles = [dict(r) for r in cursor.fetchall() if r['logged'] == 0]

    def log(pid, source, ref, xp, desc, ts):
        cursor.execute("""INSERT INTO academy_xp_log (academy_profile_id, source, ref_id, xp, description, timestamp)
                          VALUES (?, ?, ?, ?, ?, ?)""", (pid, source, None if ref is None else str(ref), xp, desc, ts))

    for p in profiles:
        pid, total = p['id'], 0

        cursor.execute("""SELECT match_id, timestamp, rating_change, result FROM academy_rating_history
                          WHERE academy_profile_id = ? AND reason = 'MATCH_RESULT' ORDER BY id ASC""", (pid,))
        for h in cursor.fetchall():
            win = (h['result'] == 1) if h['result'] is not None else h['rating_change'] > 0
            xp = 5 + (10 if win else 0)
            log(pid, 'MATCH', h['match_id'], xp, f"Duelo {'ganado' if win else 'jugado'} (reconstruido)", h['timestamp'])
            total += xp

        cursor.execute("SELECT achievement_id, unlocked_at FROM academy_achievements WHERE academy_profile_id = ?", (pid,))
        for a in cursor.fetchall():
            c = ach_cat.get(a['achievement_id'])
            if c:
                log(pid, 'ACHIEVEMENT', a['achievement_id'], c['xp_reward'],
                    f"Logro desbloqueado: {c.get('name', a['achievement_id'])}", a['unlocked_at'])
                total += c['xp_reward']

        cursor.execute("SELECT mission_id, completed_at FROM academy_missions WHERE academy_profile_id = ? AND completed = 1", (pid,))
        for m in cursor.fetchall():
            c = msn_cat.get(m['mission_id'])
            if c:
                log(pid, 'MISSION', m['mission_id'], c['xp_reward'],
                    f"Misión completada: {c.get('name', m['mission_id'])}", m['completed_at'] or '')
                total += c['xp_reward']

        cursor.execute("""
            SELECT t.id, t.date, tr.placement_points AS pos
            FROM tournament_results tr
            JOIN tournaments t ON t.id = tr.tournament_id
            JOIN league_profiles lp ON lp.id = tr.league_profile_id
            WHERE lp.player_id = ?
            ORDER BY t.id ASC""", (p['player_id'],))
        for t in cursor.fetchall():
            if processed_tournaments and t['id'] not in processed_tournaments:
                continue
            pos = t['pos'] or 0
            xp = 25 + (150 if pos == 1 else 100 if pos == 2 else 75 if pos in (3, 4) else 50 if 5 <= pos <= 8 else 0)
            if total + xp <= p['xp']:
                log(pid, 'TOURNAMENT', t['id'], xp,
                    f"Participación en torneo #{t['id']}" + (f", puesto {pos}" if pos > 0 else "") + " (reconstruido)", t['date'])
                total += xp


def backfill_traceability(cursor):
    _backfill_duels(cursor)
    _backfill_glicko(cursor)
    _backfill_xp(cursor)
