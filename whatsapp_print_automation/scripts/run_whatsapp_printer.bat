@echo off
set PROJECT_DIR=%~dp0..
cd /d "%PROJECT_DIR%"
call .venv\Scripts\activate.bat
python main.py
