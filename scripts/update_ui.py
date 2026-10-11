import os

templates_dir = "templates/public"
static_css_dir = "static/public/css"

# 2. Index Template
index_html = """{% extends "base.html" %}
{% block content %}
<section class="hero">
    <div class="hero-content">
        <h1 class="glitch-text" data-text="SUBARASHII DUEL ACADEMY">SUBARASHII DUEL ACADEMY</h1>
        <p class="subtitle">Temporada 1 - El Despertar</p>
        <div class="hero-actions">
            <a href="/ranking" class="btn btn-primary">VER RANKING GLOBAL</a>
        </div>
    </div>
</section>

<section class="academy-stats">
    <h2>ESTADÍSTICAS DE LA ACADEMIA</h2>
    <div class="stats-grid">
        <div class="stat-box">
            <span class="label">Duelistas</span>
            <span class="value">{{ stats.total_players }}</span>
        </div>
        <div class="stat-box">
            <span class="label">Rankeados Oficiales</span>
            <span class="value">{{ stats.total_ranked }}</span>
        </div>
        <div class="stat-box">
            <span class="label">Torneos Jugados</span>
            <span class="value">{{ stats.total_tournaments }}</span>
        </div>
        <div class="stat-box">
            <span class="label">Matches Totales</span>
            <span class="value">{{ stats.total_matches }}</span>
        </div>
    </div>
</section>

<section class="top-players">
    <h2>TOP 3 — RANKING GLOBAL</h2>
    <div class="cards-grid">
        {% for p in top_players %}
        <a href="/torneo/{{ p.slug }}" class="player-card dorm-{{ p.dorm.lower().replace(' ', '-') }}">
            <div class="card-header">
                <span class="rank-badge">#{{ p.rank }}</span>
                <h3>{{ p.name }}</h3>
            </div>
            <div class="card-body">
                <div class="stat"><span class="label">ELO</span><span class="value">{{ p.current_rating }}</span></div>
                <div class="stat"><span class="label">DORM</span><span class="value">{{ p.dorm }}</span></div>
            </div>
        </a>
        {% else %}
        <p class="placeholder-text">Aún no hay suficientes duelistas rankeados para formar el Top 3.</p>
        {% endfor %}
    </div>
</section>

<div class="two-columns">
    <section class="latest-achievements">
        <h2>ÚLTIMOS LOGROS</h2>
        <div class="ach-list">
            {% for a in latest_achievements %}
            <div class="ach-item">
                <div class="ach-icon">{{ a.icon }}</div>
                <div class="ach-text">
                    <h4>{{ a.name }}</h4>
                    <p>{{ a.player_name }}</p>
                    <small>Hace poco</small>
                </div>
            </div>
            {% else %}
            <p class="placeholder-text">Aún no hay logros desbloqueados.</p>
            {% endfor %}
        </div>
    </section>
    
    <section class="latest-tournament">
        <h2>ÚLTIMO TORNEO</h2>
        {% if latest_tournament %}
        <div class="tourney-card">
            <h3>Torneo #{{ latest_tournament.id }} ({{ latest_tournament.format_name }})</h3>
            <p><strong>Fecha:</strong> {{ latest_tournament.date }}</p>
            <p><strong>Participantes:</strong> {{ latest_tournament.participants }}</p>
            <p><strong>Campeón:</strong> 🏆 {{ latest_tournament.winner }}</p>
        </div>
        {% else %}
        <p class="placeholder-text">Aún no hay torneos registrados.</p>
        {% endif %}
    </section>
</div>
{% endblock %}"""
with open(os.path.join(templates_dir, "index.html"), "w", encoding="utf-8") as f:
    f.write(index_html)

# 3. Ranking Template
ranking_html = """{% extends "base.html" %}
{% block title %}Ranking - Duelorapido.cl{% endblock %}
{% block content %}
<div class="page-header">
    <h1>RANKING GLOBAL</h1>
    <p class="subtitle">Clasificación oficial de duelistas con 10 o más matches.</p>
</div>
<div class="table-container">
    <table class="ranking-table">
        <thead>
            <tr>
                <th>Rk</th>
                <th>Duelista</th>
                <th>Dormitorio</th>
                <th>ELO Rating</th>
                <th>Nivel (XP)</th>
                <th>Estado</th>
            </tr>
        </thead>
        <tbody>
            {% for p in official %}
            <tr onclick="window.location='/torneo/{{ p.slug }}'" style="cursor:pointer;" class="dorm-row-{{ p.dorm.lower().replace(' ', '-') }}">
                <td class="rank-col">{{ p.rank }}</td>
                <td class="name-col"><strong>{{ p.name }}</strong></td>
                <td><span class="dorm-badge dorm-{{ p.dorm.lower().replace(' ', '-') }}">{{ p.dorm }}</span></td>
                <td class="elo-col">{{ p.current_rating }}</td>
                <td>LVL {{ p.level }} <span class="xp-sub">({{ p.xp }} XP)</span></td>
                <td><span class="status-badge rankeado">Rankeado</span></td>
            </tr>
            {% else %}
            <tr><td colspan="6" style="text-align:center;">No hay jugadores que cumplan los requisitos todavía.</td></tr>
            {% endfor %}
        </tbody>
    </table>
</div>

<div class="page-header" style="margin-top: 4rem;">
    <h1>ESTUDIANTES DE INTERCAMBIO</h1>
    <p class="subtitle">Duelistas en etapa de calibración. Completa 10 matches para obtener clasificación oficial.</p>
</div>
<div class="table-container">
    <table class="ranking-table provisional-table">
        <thead>
            <tr>
                <th>Pos</th>
                <th>Duelista</th>
                <th>Rating Prov.</th>
                <th>Win Rate</th>
                <th>Progreso</th>
            </tr>
        </thead>
        <tbody>
            {% for p in provisional %}
            <tr onclick="window.location='/torneo/{{ p.slug }}'" style="cursor:pointer;" class="dorm-row-intercambio">
                <td class="rank-col prov">{{ p.prov_rank }}</td>
                <td class="name-col"><strong>{{ p.name }}</strong></td>
                <td class="elo-col prov">{{ p.current_rating }}</td>
                <td>{{ p.win_rate }}%</td>
                <td>
                    <div class="progress-container">
                        <div class="progress-text">{{ p.matches_played }} / 10 MATCHES</div>
                        <div class="progress-bar-bg">
                            <div class="progress-bar-fill" style="width: {{ (p.matches_played / 10) * 100 }}%"></div>
                        </div>
                    </div>
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}"""
with open(os.path.join(templates_dir, "ranking.html"), "w", encoding="utf-8") as f:
    f.write(ranking_html)

# 4. Profile Template
profile_html = """{% extends "base.html" %}
{% block head %}
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script src="https://html2canvas.hertzen.com/dist/html2canvas.min.js"></script>
{% endblock %}
{% block content %}
<div class="profile-layout">
    <aside class="credential-sidebar">
        <!-- DIGITAL CREDENTIAL FOR INSTAGRAM -->
        <div class="digital-credential dorm-{{ player.dorm.lower().replace(' ', '-') }}">
            <div class="cred-header">
                <div class="cred-brand">DUELORAPIDO.CL</div>
                <div class="cred-academy">SUBARASHII DUEL ACADEMY</div>
            </div>
            <div class="cred-body">
                <h2 class="cred-name">{{ player.name }}</h2>
                <div class="cred-title">{{ player.dorm }}</div>
                
                <div class="cred-stats-row">
                    <div class="cred-stat">
                        <span class="lbl">RATING</span>
                        <span class="val">{{ player.current_rating }}</span>
                    </div>
                    <div class="cred-stat">
                        <span class="lbl">GLOBAL</span>
                        <span class="val">{% if player.matches_played >= 10 %}#{{ player.rank }}{% else %}PROV{% endif %}</span>
                    </div>
                    <div class="cred-stat">
                        <span class="lbl">NIVEL</span>
                        <span class="val">LVL {{ player.level }}</span>
                    </div>
                </div>
                
                <div class="cred-xp-bar mt-4 w-100">
                    <div class="progress-text" style="font-size:0.7rem; margin-bottom:5px;">XP Progress ({{ player.xp % 100 }} / 100)</div>
                    <div class="progress-bar-bg">
                        <div class="progress-bar-fill" style="width: {{ player.xp % 100 }}%; background: var(--accent);"></div>
                    </div>
                </div>
            </div>
            <div class="cred-footer">
                <div class="qr-placeholder">QR</div>
                <div class="cred-url">duelorapido.cl/torneo/{{ player.slug }}</div>
            </div>
        </div>
        <div style="text-align:center; margin-top:1rem;">
            <button id="btnExport" class="btn btn-primary" style="width:100%; font-size:0.9rem; padding: 0.8rem;">📸 DESCARGAR CREDENCIAL</button>
        </div>
    </aside>
    
    <div class="profile-details">
        <section class="stats-section">
            <h2>ESTADÍSTICAS GLOBALES</h2>
            <div class="stats-grid">
                <div class="stat-box">
                    <span class="label">Matches Jugados</span>
                    <span class="value">{{ player.matches_played }}</span>
                </div>
                <div class="stat-box">
                    <span class="label">Victorias</span>
                    <span class="value">{{ player.wins }}</span>
                </div>
                <div class="stat-box">
                    <span class="label">Win Rate</span>
                    <span class="value">{{ player.win_rate }}%</span>
                </div>
                <div class="stat-box">
                    <span class="label">Peak Rating</span>
                    <span class="value">{{ player.highest_rating }}</span>
                </div>
            </div>
        </section>
        
        <section class="chart-section">
            <h2>EVOLUCIÓN DEL RATING</h2>
            <div class="chart-container" style="position: relative; height:300px; width:100%">
                <canvas id="ratingChart"></canvas>
            </div>
        </section>
        
        <div class="two-columns">
            <section class="history-section">
                <h2>HISTORIAL DE TORNEOS</h2>
                <div class="table-container">
                    <table class="ranking-table" style="font-size:0.9rem;">
                        <thead>
                            <tr>
                                <th>Fecha</th>
                                <th>Formato</th>
                                <th>Pts</th>
                                <th>Pos</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for t in tournaments %}
                            <tr>
                                <td>{{ t.date }}</td>
                                <td>{{ t.format_name }}</td>
                                <td>{{ t.points }}</td>
                                <td>
                                    {% if t.rank == 1 %}🥇 1º{% elif t.rank == 2 %}🥈 2º{% elif t.rank == 3 %}🥉 3º{% else %}-{% endif %}
                                </td>
                            </tr>
                            {% else %}
                            <tr><td colspan="4" style="text-align:center;">Sin participaciones.</td></tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </section>
            
            <section class="formats-section">
                <h2>POR FORMATO</h2>
                <div class="formats-grid">
                    {% for fmt, stats in formats.items() %}
                    <div class="format-card">
                        <h3>{{ fmt }}</h3>
                        <p>Matches: {{ stats.matches_played }}</p>
                        <p>W/L: {{ stats.wins }} - {{ stats.losses }}</p>
                    </div>
                    {% else %}
                    <p class="placeholder-text">Sin datos.</p>
                    {% endfor %}
                </div>
            </section>
        </div>
        
        <section class="achievements-section mt-4">
            <h2>LOGROS OBTENIDOS ({{ achievements|length }})</h2>
            <div class="ach-list">
                {% for a in achievements %}
                <div class="ach-item rarity-{{ a.rarity.lower() }}">
                    <div class="ach-icon">🏆</div>
                    <div class="ach-text">
                        <h4>{{ a.name }}</h4>
                        <p>{{ a.description }}</p>
                        <small>{{ a.date[:10] }}</small>
                    </div>
                </div>
                {% else %}
                <p class="placeholder-text">Aún no ha desbloqueado logros.</p>
                {% endfor %}
            </div>
        </section>
    </div>
</div>

<script>
    document.getElementById('btnExport').addEventListener('click', function() {
        const cred = document.querySelector('.digital-credential');
        html2canvas(cred, { scale: 3, backgroundColor: "#000" }).then(canvas => {
            const link = document.createElement('a');
            link.download = 'Credencial_{{ player.slug }}.png';
            link.href = canvas.toDataURL('image/png');
            link.click();
        });
    });

    const historyData = {{ history|tojson }};
    const ctx = document.getElementById('ratingChart').getContext('2d');
    const labels = historyData.map((d, i) => 'M' + (i+1));
    const dataPts = historyData.map(d => d.new_rating);
    
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'ELO Rating',
                data: dataPts,
                borderColor: '#60a5fa',
                backgroundColor: 'rgba(96, 165, 250, 0.1)',
                fill: true,
                tension: 0.3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: { grid: { color: '#1e293b' } },
                x: { grid: { display: false } }
            }
        }
    });
</script>
{% endblock %}"""
with open(os.path.join(templates_dir, "profile.html"), "w", encoding="utf-8") as f:
    f.write(profile_html)

print("Updated HTML files.")
