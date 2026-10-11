import os

templates_dir = "templates/public"

html = """{% extends "base.html" %}
{% block title %}Catálogo de Logros - Duelorapido.cl{% endblock %}
{% block content %}
<div class="page-header">
    <h1>CATÁLOGO DE LOGROS</h1>
    <p class="subtitle">Todos los trofeos disponibles en Subarashii Duel Academy</p>
</div>

<div class="ach-list" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 1.5rem;">
    {% for a in catalog %}
    <div class="ach-item rarity-{{ a.rarity.lower() }}" style="flex-direction: column; text-align: center; padding: 2rem;">
        <div class="ach-icon" style="font-size: 3rem; margin-bottom: 1rem;">{{ a.icon }}</div>
        <div class="ach-text">
            <h4 style="font-size: 1.2rem; margin-bottom: 0.5rem; color: #fff;">{{ a.name }}</h4>
            <p style="font-size: 0.9rem;">{{ a.description }}</p>
            <span class="status-badge" style="margin-top: 1rem; display: inline-block;">{{ a.rarity }}</span>
        </div>
    </div>
    {% else %}
    <p class="placeholder-text">El catálogo de logros no está disponible en este momento.</p>
    {% endfor %}
</div>
{% endblock %}"""
with open(os.path.join(templates_dir, "achievements.html"), "w", encoding="utf-8") as f:
    f.write(html)

print("Updated achievements.html")
