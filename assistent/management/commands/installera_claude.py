"""Lägger in Bitero Budget som MCP-server i Claude-appen på datorn (claude_desktop_config.json)."""

import json
import os
import shutil
import sys
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

NAMN = "bitero-budget"


def konfigfiler():
    """Alla platser där Claude-appen kan läsa sina inställningar.

    Vanliga Windows-installationen läser %APPDATA%\\Claude. Claude från Microsoft Store (MSIX)
    läser i stället en egen fil, t.ex. %LOCALAPPDATA%\\Claude-Data\\claude_<paket-id>
    eller %LOCALAPPDATA%\\Packages\\Claude_*\\LocalCache\\Roaming\\Claude.
    Kopplingen skrivs alltid till %APPDATA%\\Claude, och dessutom till de andra filerna
    om de redan finns (de skapas aldrig, så att appen inte börjar läsa en halvtom fil).
    """
    if sys.platform == "win32":
        filer = [Path(os.environ["APPDATA"]) / "Claude" / "claude_desktop_config.json"]
        lokal = Path(os.environ.get("LOCALAPPDATA", ""))
        kandidater = []
        for mönster in ("Claude-Data/*/claude_desktop_config.json",
                        "Claude-Data/*/Claude/claude_desktop_config.json",
                        "Packages/Claude_*/LocalCache/Roaming/Claude/claude_desktop_config.json"):
            kandidater += sorted(lokal.glob(mönster))
        filer += [f for f in kandidater if f.is_file() and f not in filer]
        return filer
    if sys.platform == "darwin":
        return [Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"]
    return [Path.home() / ".config" / "Claude" / "claude_desktop_config.json"]


def serverpost():
    return {"command": sys.executable, "args": [str(settings.BASE_DIR / "manage.py"), "mcp"],
            "env": {"PYTHONIOENCODING": "utf-8"}}


class Command(BaseCommand):
    help = "Kopplar Bitero Budget till Claude-appen så att Claude kan läsa och uppdatera budgeten."

    def add_arguments(self, parser):
        parser.add_argument("--fil", help="Sökväg till claude_desktop_config.json (annars standardplatsen)")
        parser.add_argument("--ta-bort", action="store_true", help="Ta bort kopplingen")

    def handle(self, *args, **opts):
        filer = [Path(opts["fil"])] if opts["fil"] else konfigfiler()
        for fil in filer:
            self.uppdatera(fil, opts["ta_bort"])
        if opts["ta_bort"]:
            self.stdout.write("Kopplingen till Bitero Budget är borttagen.")
        else:
            self.stdout.write(self.style.SUCCESS("Bitero Budget är kopplat till Claude-appen."))
            self.stdout.write("Avsluta Claude-appen helt (även i aktivitetsfältet) och starta den igen.")

    def uppdatera(self, fil, ta_bort):
        fil.parent.mkdir(parents=True, exist_ok=True)
        konfig = {}
        if fil.exists():
            try:
                konfig = json.loads(fil.read_text(encoding="utf-8-sig") or "{}")
            except json.JSONDecodeError as e:
                raise CommandError(f"{fil} är inte giltig JSON ({e}). Rätta eller ta bort filen och försök igen.")
            shutil.copy2(fil, fil.with_suffix(".json.bak"))
        servrar = konfig.setdefault("mcpServers", {})
        if ta_bort:
            servrar.pop(NAMN, None)
        else:
            servrar[NAMN] = serverpost()
        fil.write_text(json.dumps(konfig, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self.stdout.write(f"  Inställningar: {fil}")
