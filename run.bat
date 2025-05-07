@echo off
echo === STARTING KATILO-ERP (Production Mode via WSGI) ===
call venv\Scripts\activate.bat
python wsgi.py
pause
