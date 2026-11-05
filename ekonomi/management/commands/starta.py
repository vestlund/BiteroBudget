"""Startar Bitero Budget: säkerhetskopia, migrering, inloggning och webbservern (waitress)."""

import datetime as dt
import sqlite3
import threading
import webbrowser

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand

ADRESS = "127.0.0.1"
PORT = "8010"  # annan port än Bitero ERP (8000) så att båda kan köras samtidigt
SPARA_ANTAL = 30


def gor_backup():
    """Kopierar databasen till backupmappen (en per dag) och behåller de senaste 30."""
    db = settings.DATABASES["default"]["NAME"]
    if not db.exists():
        return None
    settings.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    mal = settings.BACKUP_DIR / f"budget-{dt.date.today():%Y-%m-%d}.sqlite3"
    kalla, dest = sqlite3.connect(db), sqlite3.connect(mal)
    try:
        kalla.backup(dest)
    finally:
        dest.close()
        kalla.close()
    for gammal in sorted(settings.BACKUP_DIR.glob("budget-*.sqlite3"))[:-SPARA_ANTAL]:
        gammal.unlink()
    return mal


class Command(BaseCommand):
    help = "Startar Bitero Budget på http://127.0.0.1:8010"

    def add_arguments(self, parser):
        parser.add_argument("--port", default=PORT)
        parser.add_argument("--ingen-webblasare", action="store_true")

    def handle(self, *args, **opts):
        try:
            if b := gor_backup():
                self.stdout.write(f"Säkerhetskopia: {b}")
        except Exception as e:  # noqa: BLE001
            self.stdout.write(self.style.WARNING(f"Kunde inte göra säkerhetskopia: {e}"))
        call_command("migrate", verbosity=0)
        if not get_user_model().objects.filter(is_superuser=True).exists():
            self.stdout.write(self.style.WARNING("\nSkapa din inloggning (används bara lokalt):"))
            call_command("createsuperuser")

        url = f"http://{ADRESS}:{opts['port']}/"
        self.stdout.write(self.style.SUCCESS(f"\nBitero Budget körs på {url}  –  stäng med Ctrl+C"))
        self.stdout.write(f"Data: {settings.DATA_DIR}\n")
        if not opts["ingen_webblasare"]:
            threading.Timer(1.5, lambda: webbrowser.open(url)).start()
        if settings.DEBUG:
            call_command("runserver", f"{ADRESS}:{opts['port']}", use_reloader=False)
            return
        from django.core.wsgi import get_wsgi_application
        from waitress import serve

        try:
            serve(get_wsgi_application(), host=ADRESS, port=int(opts["port"]), threads=8, ident="Bitero Budget")
        except KeyboardInterrupt:
            self.stdout.write("Stoppat.")
