import sys

with open('deck_editor_ui.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix preview box newline literals
content = content.replace('text = f"{name}\\\\n{type_}"', 'text = f"{name}\\n{type_}"')
content = content.replace('text += f"\\\\nNivel: {lvl} | ATK: {atk} | DEF: {def_}"', 'text += f"\\nNivel: {lvl} | ATK: {atk} | DEF: {def_}"')
content = content.replace('text += f"\\\\n\\\\n{desc}"', 'text += f"\\n\\n{desc}"')

# Also fix the loaded messages
content = content.replace('f"Base de datos {fmt} cargada ({len(data)} cartas).\\n¡Busca cartas a la derecha!"', 'f"Base de datos {fmt} cargada ({len(data)} cartas).\\n¡Busca cartas a la derecha!"')

with open('deck_editor_ui.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed newlines")
