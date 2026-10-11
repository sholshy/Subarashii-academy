import os

templates_dir = "templates/public"

seasons = """{% extends "base.html" %}
{% block title %}Temporadas - Duelorapido.cl{% endblock %}
{% block content %}
<div class="page-header">
    <h1>TEMPORADAS DE LA ACADEMIA</h1>
    <p class="subtitle">Historial de las etapas competitivas de Subarashii Duel Academy</p>
</div>

<div class="two-columns">
    <div class="tourney-card" style="border-color: var(--accent);">
        <h3 style="color: var(--accent);">Temporada 1 - El Despertar</h3>
        <p><strong>Estado:</strong> EN CURSO</p>
        <p><strong>Descripción:</strong> La primera temporada oficial de la academia. Los duelistas compiten por ascender a los dormitorios de élite y asegurar su lugar en el Torneo Final.</p>
        <p class="mt-4"><a href="/ranking" class="btn btn-primary" style="padding: 0.5rem 1rem; font-size: 0.8rem;">Ver Ranking Actual</a></p>
    </div>
    
    <div class="tourney-card" style="opacity: 0.7;">
        <h3>Pretemporada</h3>
        <p><strong>Estado:</strong> FINALIZADA</p>
        <p><strong>Descripción:</strong> Etapa de calibración y pruebas. Los resultados sirvieron para iniciar a los duelistas pioneros pero no otorgan clasificación oficial en la Temporada 1.</p>
    </div>
</div>
{% endblock %}"""
with open(os.path.join(templates_dir, "seasons.html"), "w", encoding="utf-8") as f:
    f.write(seasons)


hof = """{% extends "base.html" %}
{% block title %}Hall of Fame - Duelorapido.cl{% endblock %}
{% block content %}
<div class="page-header">
    <h1>HALL OF FAME</h1>
    <p class="subtitle">El muro de las leyendas de Subarashii Duel Academy</p>
</div>

<div style="text-align: center; padding: 4rem; background: var(--bg-card); border-radius: 12px; margin-top: 2rem;">
    <div style="font-size: 5rem; margin-bottom: 1rem;">👑</div>
    <h3>EL SALÓN ESTÁ ESPERANDO</h3>
    <p style="color: var(--text-muted); max-width: 500px; margin: 1rem auto;">Al finalizar la <strong>Temporada 1 - El Despertar</strong>, los campeones y jugadores más destacados serán inmortalizados en esta sección.</p>
</div>
{% endblock %}"""
with open(os.path.join(templates_dir, "hall_of_fame.html"), "w", encoding="utf-8") as f:
    f.write(hof)

print("Updated seasons.html and hall_of_fame.html")
