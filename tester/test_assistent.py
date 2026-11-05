"""MCP-verktygen för Claude (assistent/verktyg.py) och att servern registrerar dem."""

import asyncio
import datetime as dt
import json
import tempfile
from decimal import Decimal
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from assistent import verktyg as v
from budget.models import Budget
from ekonomi.models import Kategori, Kategoriregel, Konto, Transaktion
from tillgangar.models import Lan, Tillgang

from .test_import import HANDELSBANKEN_EXPORT, xlsx


class Verktyg(TestCase):
    def setUp(self):
        self.bank = Konto.objects.create(namn="Lönekonto", typ=Konto.BANK)
        T = Transaktion.objects.create
        self.swish = [T(konto=self.bank, datum=dt.date(2026, 10, d), belopp=-200, text="Ebba Kristina") for d in (1, 8)]
        self.butik = T(konto=self.bank, datum=dt.date(2026, 10, 3), belopp=-150, text="KLÄTTERCENTRET, SOLNA")
        self.annan = T(konto=self.bank, datum=dt.date(2026, 10, 4), belopp=-99, text="Ebba Kristina Andersson")

    def test_kategorisera_text_exakt_skapar_regel(self):
        r = v.kategorisera_text("Ebba Kristina", "Hushåll – Barn")
        self.assertEqual(r["kategoriserade"], 2)
        self.assertIsNone(Transaktion.objects.get(pk=self.annan.pk).kategori)
        regel = Kategoriregel.objects.get(pk=r["regel"]["id"])
        self.assertEqual(regel.monster, '"ebba kristina"')
        ny = Transaktion.objects.create(konto=self.bank, datum=dt.date(2026, 11, 1), belopp=-50, text="Ebba Kristina")
        v.kor_regler()
        self.assertEqual(Transaktion.objects.get(pk=ny.pk).kategori.namn, "Barn")

    def test_ny_kategori_och_kategorisera_butik(self):
        v.ny_kategori("Fritid", "Träning och sport")
        r = v.kategorisera_text("klättercentret", "Träning och sport", exakt=False)
        self.assertEqual(r["kategoriserade"], 1)
        self.assertTrue(Transaktion.objects.get(pk=self.butik.pk).manuellt_kategoriserad)

    def test_satt_kategori_och_fel(self):
        v.satt_kategori([self.annan.pk], "Övrigt – Övriga utgifter", anteckning="Okänt")
        t = Transaktion.objects.get(pk=self.annan.pk)
        self.assertEqual((t.kategori.namn, t.anteckning), ("Övriga utgifter", "Okänt"))
        with self.assertRaises(v.VerktygsFel):
            v.satt_kategori([999999], "Barn")
        with self.assertRaises(v.VerktygsFel):
            v.satt_kategori([self.annan.pk], "Finns inte")

    def test_lasverktyg(self):
        forsta = v.okategoriserade_grupperade()["texter"][0]
        self.assertEqual((forsta["text"], forsta["antal"], Decimal(forsta["summa"])), ("Ebba Kristina", 2, -400))
        self.assertEqual(v.transaktioner(sok="klättercentret")["antal"], 1)  # å/ä/ö oavsett skiftläge
        self.assertEqual(v.transaktioner(sok="ebba")["antal"], 3)
        self.assertEqual(v.transaktioner(max_belopp="-150")["antal"], 3)
        json.dumps([v.oversikt(), v.konton(), v.kategorier(), v.utfall(2026), v.utfall(2026, 10), v.regler("ica"),
                    v.budget(2026), v.tillgangar()])  # allt ska gå att skicka som JSON

    def test_importera_fil_budget_saldo_och_tillgangar(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "hb.xlsx"
            p.write_bytes(xlsx(HANDELSBANKEN_EXPORT))
            r = v.importera_fil(str(p), "lönekonto")
            self.assertEqual((r["nya"], r["fanns_redan"]), (4, 0))
            self.assertEqual(v.importera_fil(str(p), self.bank.pk)["nya"], 0)
        b = v.spara_budget(2026, [{"kategori": "Livsmedel", "ar": 70000}, {"kategori": "Mat – Restaurang och café",
                                                                           "per_manad": [1000] * 12}])
        post = Budget.objects.get(pk=b["id"]).poster.get(kategori__namn="Livsmedel")
        self.assertEqual((post.summa, post.m1, post.m12), (Decimal(70000), Decimal(5833), Decimal(5837)))
        kort = Konto.objects.create(namn="SAS Amex Premium", typ=Konto.KREDITKORT)
        self.assertEqual(v.satt_kontosaldo("amex", "2026-11-05", "-12 345,50")["saldo"], "-12345.50")
        self.assertEqual(kort.saldo_per(dt.date(2026, 11, 5)), Decimal("-12345.50"))
        t = v.ny_tillgang("Bostadsrätt", "bostadsratt", "2018-05-01", "4200000", agarandel="50")
        v.ny_vardering(t["id"], "2026-10-01", "5400000", "Booli")
        self.assertEqual(Tillgang.objects.get(pk=t["id"]).mitt_varde_per(), Decimal(2700000))
        v.nytt_lan("Bolån", "2600000", tillgang="bostadsr", ranta="3.15", datum="2026-09-01")
        v.nytt_lanesaldo("bolån", "2026-11-01", "2596000", ranta="2.95")
        l = Lan.objects.get()
        self.assertEqual((l.saldo_per(), l.ranta), (Decimal(2596000), Decimal("2.950")))

    def test_overforing_budgeteras_inte(self):
        with self.assertRaises(v.VerktygsFel):
            v.spara_budget(2026, [{"kategori": "Mellan egna konton", "ar": 1000}])
        self.assertIsNotNone(Kategori.objects.get(namn="Mellan egna konton"))


class Server(TestCase):
    def test_verktygen_ar_registrerade(self):
        from assistent.server import server

        namn = {t.name for t in asyncio.run(server.list_tools())}
        self.assertTrue({"oversikt", "transaktioner", "kategorisera_text", "satt_kategori", "importera_fil",
                         "spara_budget", "nytt_lanesaldo"} <= namn)

    def test_installera_claude(self):
        with tempfile.TemporaryDirectory() as d:
            fil = Path(d) / "claude_desktop_config.json"
            fil.write_text('{"mcpServers": {"bitero-erp": {"command": "x"}}}', encoding="utf-8")
            call_command("installera_claude", fil=str(fil), stdout=open("/dev/null", "w"))
            konfig = json.loads(fil.read_text(encoding="utf-8"))
            self.assertEqual(set(konfig["mcpServers"]), {"bitero-erp", "bitero-budget"})
            self.assertEqual(konfig["mcpServers"]["bitero-budget"]["args"][-1], "mcp")
