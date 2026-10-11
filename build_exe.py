import PyInstaller.__main__
import os

# Define added files
added_files = [
    ('yugi_dance.gif', '.'),
    ('keygen.wav', '.'),
    ('background.png', '.'),
    ('Orbitron-Black.ttf', '.'),
    ('*_banlist.json', '.'),
    ('templates', 'templates'),
    ('static', 'static'),
    ('mock_server', 'mock_server'),
    ('data/achievements/catalog.json', 'data/achievements'),
    ('data/missions/catalog.json', 'data/missions')
]

# Convert added_files into --add-data arguments
add_data_args = []
for src, dst in added_files:
    if os.path.exists(src) or '*' in src:
        add_data_args.append(f'--add-data={src};{dst}')

# Define PyInstaller arguments
args = [
    'main.py',
    '--name=YGO_Tools',
    '--windowed',  # No console window
    '--icon=NONE', # Replace with an .ico path if you have one
    '--clean',
    '--noconfirm',
] + add_data_args

print("Iniciando empaquetado con PyInstaller...")
PyInstaller.__main__.run(args)
print("Empaquetado completado. Revisa la carpeta 'dist/YGO_Tools'")
