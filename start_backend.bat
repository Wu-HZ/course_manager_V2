@echo off
echo Starting Course Manager Backend...
cd /d "%~dp0backend"
call venv\Scripts\activate
python manage.py runserver 8001
pause
