@echo off
title Subarashii Smart Showcase
cd /d "%~dp0"
if exist "..\.venv\Scripts\python.exe" (
    "..\.venv\Scripts\python.exe" manage.py runserver 0.0.0.0:8000
) else if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" manage.py runserver 0.0.0.0:8000
) else (
    python manage.py runserver 0.0.0.0:8000
)
pause
