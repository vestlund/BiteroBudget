"""Import av kontoutdrag och kortutdrag. Filerna skapas i testet (riktiga utdrag ska aldrig in i git)."""

import datetime as dt
import io
from decimal import Decimal

import openpyxl
from django.test import TestCase

from ekonomi.importering import ImportFel, datum, importera, tal, tolka
from ekonomi.models import Kategori, Kategoriregel, Konto, Kontosaldo, Transaktion


def xlsx(rader):
    bok = openpyxl.Workbook()
    blad = bok.active
    for r in rader:
        blad.append(r)
    ut = io.BytesIO()
    bok.save(ut)
    return ut.getvalue()


HANDELSBANKEN = [
    ["Kontoutdrag"], ["Konto: Allkonto 123 456 789"], [],
    ["Reskontradatum", "Transaktionsdatum", "Text", "Belopp", "Saldo"],
    ["2026-10-27", "2026-10-26", "ICA NARA SODER", -412.5, 18587.5],
    ["2026-10-25", "2026-10-25", "LÖN", 32000, 19000],
    ["2026-10-24", "2026-10-23", "AMERICAN EXPRESS", -12000, -13000],
]

SWEDBANK = (
    "* Transaktioner Period 2026-10-01 – 2026-10-31 Skapad 2026-11-01 10:00 CET\n"
    "Radnummer,Clearingnummer,Kontonummer,Produkt,Valuta,Bokföringsdag,Transaktionsdag,Valutadag,Referens,Beskrivning,Belopp,Bokfört saldo\n"
    '1,8327,1234567,"Privatkonto",SEK,2026-10-30,2026-10-29,2026-10-30,"COOP","COOP KONSUM",-249.00,5751.00\n'
    '2,8327,1234567,"Privatkonto",SEK,2026-10-29,2026-10-29,2026-10-29,"SPOTIFY","SPOTIFY P1234",-129.00,6000.00\n'
).encode()

AMEX_XLSX = [
    ["Transaktionsdetaljer"], ["American Express® Platinum Card"], ["Kortmedlem", "A VESTLUND"], [],
    ["Datum", "Beskrivning", "Belopp", "Utökade detaljer", "Visas på ditt kontoutdrag som", "Adress", "Ort"],
    ["28/10/2026", "SAS AB STOCKHOLM", "4 520,00", "", "SAS AB", "", "STOCKHOLM"],
    ["15/10/2026", "BETALNING MOTTAGEN, TACK", "-10 000,00", "", "", "", ""],
    ["03/10/2026", "WOLT", "389,00", "", "", "", ""],
    ["03/10/2026", "WOLT", "389,00", "", "", "", ""],
]

AMEX_CSV = (
    "Datum,Beskrivning,Kortmedlem,Konto #,Belopp\n"
    '10/28/2026,"NETFLIX.COM","A VESTLUND",-71004,"139,00"\n'
    '10/13/2026,"HOTEL ARLANDA","A VESTLUND",-71004,"1 890,00"\n'
).encode("cp1252")

SAS_XLSX = [
    ["SAS EuroBonus World Mastercard"], ["Transaktioner 2026-10-01 - 2026-10-31"], [],
    ["Reserverade belopp"],
    ["Datum", "Bokfört", "Specifikation", "Ort", "Valuta", "Utl. belopp", "Belopp"],
    [dt.datetime(2026, 10, 31), None, "CIRCLE K", "UPPSALA", "SEK", None, 650.0],
    ["Bokförda transaktioner"],
    ["Datum", "Bokfört", "Specifikation", "Ort", "Valuta", "Utl. belopp", "Belopp"],
    [dt.datetime(2026, 10, 20), dt.datetime(2026, 10, 21), "HOTEL BRISTOL", "OSLO", "NOK", 1500.0, 1402.35],
    [dt.datetime(2026, 10, 18), dt.datetime(2026, 10, 19), "WILLYS", "UPPSALA", "SEK", None, 1043.9],
    [dt.datetime(2026, 10, 5), dt.datetime(2026, 10, 5), "INBETALNING", "", "SEK", None, -5000.0],
    ["", "", "Totalt", "", "", "", 3446.25],
]


class TolkaVarden(TestCase):
    def test_tal(self):
        self.assertEqual(tal("1 234,50"), Decimal("1234.50"))
        self.assertEqual(tal("-1.234,50"), Decimal("-1234.50"))
        self.assertEqual(tal("1,234.50"), Decimal("1234.50"))
        self.assertEqual(tal("−99,90 kr"), Decimal("-99.90"))
        self.assertEqual(tal(412.5), Decimal("412.50"))
        self.assertEqual(tal("250-"), Decimal("-250.00"))
        self.assertIsNone(tal("Totalt"))

    def test_datum(self):
        self.assertEqual(datum("2026-10-03"), dt.date(2026, 10, 3))
        self.assertEqual(datum("20261003"), dt.date(2026, 10, 3))
        self.assertEqual(datum("03/10/2026"), dt.date(2026, 10, 3))
        self.assertEqual(datum("10/28/2026", dag_forst=False), dt.date(2026, 10, 28))
        self.assertEqual(datum("2026/10/03"), dt.date(2026, 10, 3))


class Import(TestCase):
    def setUp(self):
        self.bank = Konto.objects.create(namn="Lönekonto", typ=Konto.BANK)
        self.amex = Konto.objects.create(namn="Amex", typ=Konto.KREDITKORT)
        self.sas = Konto.objects.create(namn="SAS Mastercard", typ=Konto.KREDITKORT)

    def test_handelsbanken_excel_och_dubbletter(self):
        imp = importera(self.bank, xlsx(HANDELSBANKEN), "kontoutdrag.xlsx")
        self.assertEqual((imp.antal_nya, imp.format, imp.tecken_vant), (3, "bank", False))
        t = Transaktion.objects.get(text="ICA NARA SODER")
        self.assertEqual((t.datum, t.belopp), (dt.date(2026, 10, 26), Decimal("-412.50")))
        self.assertEqual(t.kategori.namn, "Livsmedel")  # standardregeln "ica "
        self.assertEqual(Transaktion.objects.get(text="AMERICAN EXPRESS").kategori.typ, Kategori.OVERFORING)
        # saldot från nyaste raden (filen är sorterad nyast först)
        self.assertEqual(Kontosaldo.objects.get(konto=self.bank).saldo, Decimal("18587.50"))
        self.assertEqual(self.bank.saldo_per(dt.date(2026, 10, 31)), Decimal("18587.50"))
        self.assertEqual(self.bank.saldo_per(dt.date(2026, 10, 25)), Decimal("19000.00"))
        igen = importera(self.bank, xlsx(HANDELSBANKEN), "kontoutdrag.xlsx")
        self.assertEqual((igen.antal_nya, igen.antal_dubbletter), (0, 3))
        self.assertEqual(Transaktion.objects.count(), 3)

    def test_swedbank_csv(self):
        imp = importera(self.bank, SWEDBANK, "Transaktioner.csv")
        self.assertEqual(imp.antal_nya, 2)
        t = Transaktion.objects.get(text="COOP KONSUM")
        self.assertEqual((t.datum, t.belopp, t.valuta), (dt.date(2026, 10, 29), Decimal("-249.00"), "SEK"))
        self.assertIsNone(t.utlandskt_belopp)
        self.assertEqual(Transaktion.objects.get(text="SPOTIFY P1234").kategori.namn, "Prenumerationer och appar")

    def test_amex_excel_vander_tecken_och_behaller_identiska_kop(self):
        imp = importera(self.amex, xlsx(AMEX_XLSX), "activity.xlsx")
        self.assertEqual((imp.format, imp.tecken_vant, imp.antal_nya), ("amex", True, 4))
        self.assertEqual(Transaktion.objects.filter(text="WOLT").count(), 2)  # två likadana köp samma dag
        self.assertEqual(Transaktion.objects.get(text__startswith="SAS AB").belopp, Decimal("-4520.00"))
        bet = Transaktion.objects.get(text__startswith="BETALNING")
        self.assertEqual(bet.belopp, Decimal("10000.00"))
        self.assertEqual(bet.kategori.namn, "Betalning av kreditkort")
        self.assertEqual(importera(self.amex, xlsx(AMEX_XLSX), "activity.xlsx").antal_nya, 0)

    def test_amex_csv_amerikanska_datum(self):
        importera(self.amex, AMEX_CSV, "activity.csv")
        t = Transaktion.objects.get(text="NETFLIX.COM")
        self.assertEqual((t.datum, t.belopp), (dt.date(2026, 10, 28), Decimal("-139.00")))
        self.assertEqual(Transaktion.objects.get(text="HOTEL ARLANDA").belopp, Decimal("-1890.00"))

    def test_sas_mastercard_hoppar_over_reserverade(self):
        imp = importera(self.sas, xlsx(SAS_XLSX), "Transaktioner.xlsx")
        self.assertEqual((imp.format, imp.antal_nya, imp.tecken_vant), ("sas", 3, True))
        self.assertFalse(Transaktion.objects.filter(text__startswith="CIRCLE K").exists())
        h = Transaktion.objects.get(text__startswith="HOTEL BRISTOL")
        self.assertEqual((h.belopp, h.valuta, h.utlandskt_belopp, h.text),
                         (Decimal("-1402.35"), "NOK", Decimal("1500.00"), "HOTEL BRISTOL, OSLO"))
        self.assertEqual(Transaktion.objects.get(text__startswith="INBETALNING").belopp, Decimal("5000.00"))
        self.assertEqual(Transaktion.objects.get(text__startswith="WILLYS").kategori.namn, "Livsmedel")

    def test_overlappande_utdrag(self):
        importera(self.sas, xlsx(SAS_XLSX[:9]), "del1.xlsx")
        imp = importera(self.sas, xlsx(SAS_XLSX), "allt.xlsx")
        self.assertEqual((imp.antal_nya, imp.antal_dubbletter), (2, 1))

    def test_tecken_som_i_filen(self):
        self.amex.tecken = Konto.TECKEN_SOM_FIL
        self.amex.save()
        importera(self.amex, xlsx(AMEX_XLSX), "a.xlsx")
        self.assertEqual(Transaktion.objects.get(text__startswith="SAS AB").belopp,
                         Decimal("4520.00"))

    def test_fel_fil(self):
        with self.assertRaises(ImportFel):
            tolka(b"hej;hopp\n1;2\n", "x.csv")

    def test_regel_med_hogst_prioritet_och_langst_monster(self):
        livs = Kategori.objects.get(namn="Livsmedel")
        rest = Kategori.objects.get(namn="Restaurang och café")
        Kategoriregel.objects.create(monster="ica nara soder", kategori=rest)
        importera(self.bank, xlsx(HANDELSBANKEN), "k.xlsx")
        self.assertEqual(Transaktion.objects.get(text="ICA NARA SODER").kategori, rest)
        Kategoriregel.objects.create(monster="ica", kategori=livs, prioritet=5)
        from ekonomi.models import kategorisera

        self.assertEqual(kategorisera(skriv_over=True), 1)
        self.assertEqual(Transaktion.objects.get(text="ICA NARA SODER").kategori, livs)
