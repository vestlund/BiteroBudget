@echo off
REM Kör de automatiska testerna. Din riktiga databas rörs inte.
cd /d "%~dp0"
uv run python manage.py test tester %*
pause
