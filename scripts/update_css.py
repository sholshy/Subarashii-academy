import os

path = "static/public/css/style.css"
css = open(path, encoding='utf-8').read()

new_css = """
/* Layout utilities */
.two-columns { display: grid; grid-template-columns: 1fr 1fr; gap: 2rem; margin-bottom: 3rem; }
@media (max-width: 768px) { .two-columns { grid-template-columns: 1fr; } }
.mt-4 { margin-top: 1.5rem; }
.w-100 { width: 100%; }

/* Stats & Tournament Cards */
.academy-stats { margin-bottom: 3rem; }
.placeholder-text { color: var(--text-muted); font-style: italic; padding: 1rem; }
.tourney-card { background: var(--bg-card); padding: 1.5rem; border-radius: 8px; border: 1px solid #334155; }
.tourney-card h3 { color: var(--accent); margin-bottom: 1rem; }
.tourney-card p { margin-bottom: 0.5rem; }

/* Tables */
.status-badge { padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.7rem; font-weight: bold; text-transform: uppercase; }
.status-badge.rankeado { background: rgba(59, 130, 246, 0.2); color: #93c5fd; border: 1px solid #3b82f6; }

.provisional-table td.prov { color: var(--text-muted); }
.dorm-row-intercambio td { opacity: 0.8; }

/* Progress Bar */
.progress-container { width: 100%; min-width: 150px; }
.progress-text { font-size: 0.75rem; font-weight: 800; color: var(--text-muted); margin-bottom: 0.2rem; font-family: 'Orbitron'; letter-spacing: 1px; }
.progress-bar-bg { background: #0f172a; border-radius: 10px; height: 8px; width: 100%; overflow: hidden; border: 1px solid #334155; }
.progress-bar-fill { background: var(--text-muted); height: 100%; border-radius: 10px; transition: width 0.3s; }
"""

css += new_css
open(path, 'w', encoding='utf-8').write(css)
print("Updated style.css")
