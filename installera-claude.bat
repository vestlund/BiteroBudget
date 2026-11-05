@echo off
chcp 65001 >nul
REM Kopplar Bitero Budget till Claude-appen (MCP), så att Claude kan läsa och uppdatera budgeten direkt.
cd /d "%~dp0"
uv run python manage.py installera_claude %*
pause
