#!/usr/bin/env bash
# Kopplar Bitero Budget till Claude-appen (MCP), så att Claude kan läsa och uppdatera budgeten direkt.
cd "$(dirname "$0")"
uv run python manage.py installera_claude "$@"
