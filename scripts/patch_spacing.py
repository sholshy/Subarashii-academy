import sys

with open('tournament_graphics.py', 'r', encoding='utf-8') as f:
    content = f.read()

target_header = '    draw.text((140, 166), "JUGADOR", fill="#94a3b8", font=header_font)'
replacement_header = '    draw.text((170, 166), "JUGADOR", fill="#94a3b8", font=header_font)'
content = content.replace(target_header, replacement_header)

target_name1 = '        name_font = fit_text(draw, name, name_font_size, 430, min_size=16)'
replacement_name1 = '        name_font = fit_text(draw, name, name_font_size, 420, min_size=16)'
content = content.replace(target_name1, replacement_name1)

target_name2 = '        draw_text_shadow(draw, 140, y + max(10, (row_h - 34) // 2), name, name_font, fill="#f8fafc")'
replacement_name2 = '        draw_text_shadow(draw, 170, y + max(10, (row_h - 34) // 2), name, name_font, fill="#f8fafc")'
content = content.replace(target_name2, replacement_name2)

with open('tournament_graphics.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patch applied")
