@echo off
echo Iniciando Servidor Web de Subarashii Duel Academy...
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" public_web.py
) else (
    python public_web.py
)
pause
