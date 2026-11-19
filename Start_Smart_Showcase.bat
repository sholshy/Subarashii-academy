@echo off
title Subarashii Smart Showcase
echo ============================================================
echo   Iniciando Servidor Web Subarashii Smart Showcase (Django)
echo ============================================================
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    echo Usando entorno virtual: .venv\Scripts\python.exe
    ".venv\Scripts\python.exe" smart_showcase\manage.py runserver 0.0.0.0:8000
) else (
    echo No se encontro .venv local, intentando python global...
    python smart_showcase\manage.py runserver 0.0.0.0:8000
)
pause
