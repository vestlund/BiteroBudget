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


# ------------------------------------------------------------------ format som i verkliga exporter (påhittade data)

def xlsx_med_fel_storlek(rader):
    """Som bankernas filer: arket påstår att det bara är cell A1 stort."""
    import re
    import zipfile

    kalla = zipfile.ZipFile(io.BytesIO(xlsx(rader)))
    ut = io.BytesIO()
    with zipfile.ZipFile(ut, "w") as z:
        for namn in kalla.namelist():
            data = kalla.read(namn)
            if namn.startswith("xl/worksheets/"):
                data = re.sub(rb'<dimension ref="[^"]*"/>', b'<dimension ref="A1"/>', data)
            z.writestr(namn, data)
    return ut.getvalue()


HANDELSBANKEN_EXPORT = [
    ["Handelsbanken"], ["2026-11-05, 18:15"], [""], ["Lönekonto 123 456 789"], [""],
    ["Kontoform: Allkonto", "Clearingnummer: 6000", "Saldo: 1500.50"],
    ["Period: 2026-01-01 - 2026-11-05", "Transaktionstyp: Alla"], [""],
    ["Reskontradatum", "Transaktionsdatum", "Text", "Belopp", "Saldo"],
    ["2026-11-02", "2026-11-02", "TRÄNGSELSKATT", -45, 1500.5],
    ["2026-10-30", "2026-10-30", "SAS EUROBONUS", -9000, 1545.5],
    ["2026-10-30", "2026-10-30", "American Expre", -4000, 10545.5],
    ["2026-10-25", "2026-10-25", "Lön", 30000, 14545.5],
]

SEBKORT_EXPORT = [
    ["Transaktionsexport", "", "", "", "", "", "2026-11-03 16:53:24", ""], ["", "", "", "", "", "", "", ""],
    ["Totalt övriga händelser", "", "", "", "", "", "", ""],
    ["Datum", "Bokfört", "Specifikation", "Ort", "Valuta", "Utl. belopp", "Belopp", None],
    [dt.datetime(2026, 10, 30), dt.datetime(2026, 10, 30), "Inbetalning", "", "SEK", 0, -9000, None],
    [dt.datetime(2026, 10, 17), dt.datetime(2026, 10, 19), "Ränta på utnyttjad kredit 17,98% 261030", "", "SEK", 0, 58.14, None],
    ["", "", "Summa köp/uttag", "", "", "", 9058.14, ""], ["Totalt belopp", "", "", "", "", "", 1200.0, ""],
    ["", "", "", "", "", "", "", ""],
    ["525412******1111", "Testsson Anna", None, None, None, None, None, None], ["Köp/uttag", None, None, None, None, None, None, None],
    ["Datum", "Bokfört", "Specifikation", "Ort", "Valuta", "Utl. belopp", "Belopp", None],
    [dt.datetime(2026, 10, 20), dt.datetime(2026, 10, 21), "CAFE SOLEIL", "NICE", "EUR", 10, 115.5, None],
    ["Valutakurs: 11.55 Valutapåslag ingår med 2,00\xa0%", "", "", "", "", "", "", ""],
    [dt.datetime(2026, 10, 18), dt.datetime(2026, 10, 19), "S¦DERBERGS BAGERI", "H{GERSTEN", "SEK", 0, 89, None],
    ["Totalt belopp", "", "", "", "", "", 204.5, ""], ["", "", "", "", "", "", "", ""],
    ["525412******2222", "Testsson Bo", None, None, None, None, None, None], ["Köp/uttag", None, None, None, None, None, None, None],
    ["Datum", "Bokfört", "Specifikation", "Ort", "Valuta", "Utl. belopp", "Belopp", None],
    [dt.datetime(2026, 10, 12), dt.datetime(2026, 10, 13), "SL", "STOCKHOLM", "SEK", 0, 1060, None],
    [dt.datetime(2026, 10, 11), dt.datetime(2026, 10, 13), "HM SE0152", "KUNGENS KURVA", "SEK", 0, -299, None],
    ["Totalt belopp", "", "", "", "", "", 761, ""],
]

AMEX_EXPORT = [
    ["Transaktionsspecifikationer", "SAS Amex Premium / 01 Jan, 2026 till 03 Nov, 2026"], ["Förberedd för", ""],
    ["ANNA TESTSSON", ""], ["Kontonummer", ""], ["XXXX-XXXXXX-11111", ""], ["", ""],
    ["Datum", "Beskrivning", "Kortmedlem", "Konto #", "Belopp", "Utökade specifikationer",
     "Visas på ditt kontoutdrag som", "Adress", "Ort", "Postnummer", "Land", "Referens", "Kategori"],
    ["11/02/2026", "PERIODENS DEL AV ÅRSAVGIFT FÖR KONTOT", "ANNA TESTSSON", "-11111", 150.0, "", "", "", "", "", "", "R1", ""],
    ["11/01/2026", "KINDLE SVCS*ABC123   888-802-3080", "ANNA TESTSSON", "-11111", 61.68,
     "Foreign Spend Amount: 6.13 UNITED STATES DOLLAR Commission Amount: 1.21 Currency Exchange Rate: 0.1013",
     "", "", "", "", "", "R2", "Miscellaneous-Other"],
    ["10/31/2026", "ICA KVANTUM LILJEHOLMEN STOCKHOLM", "BO TESTSSON", "-11129", 1879.6, "", "", "LILJEHOLMSTORGET 3\nSTOCKHOLM",
     "", "S-117 63", "SWEDEN", "R3", "Miscellaneous-Other"],
    ["10/27/2026", "BETALNING MOTTAGEN, TACK", "ANNA TESTSSON", "-11111", -4000.0, "", "", "", "", "", "", "R4", ""],
    ["10/16/2026", "ICA NARA ALVSJO 9570240 ALVSJO", "BO TESTSSON", "-11129", -105.7, "", "", "", "", "", "", "R5", ""],
]


class VerkligaFormat(TestCase):
    def setUp(self):
        self.bank = Konto.objects.create(namn="Lönekonto", typ=Konto.BANK)
        self.seb = Konto.objects.create(namn="SAS EuroBonus Mastercard", typ=Konto.KREDITKORT, importformat=Konto.SAS)
        self.amex = Konto.objects.create(namn="SAS Amex Premium", typ=Konto.KREDITKORT, importformat=Konto.AMEX)

    def test_handelsbanken_med_fel_arkstorlek_och_kortade_texter(self):
        imp = importera(self.bank, xlsx_med_fel_storlek(HANDELSBANKEN_EXPORT), "Handelsbanken_Account_Transactions.xlsx")
        self.assertEqual((imp.antal_nya, imp.format), (4, "bank"))
        self.assertEqual(self.bank.saldo_per(dt.date(2026, 11, 5)), Decimal("1500.50"))
        kat = dict(Transaktion.objects.values_list("text", "kategori__namn"))
        self.assertEqual(kat["American Expre"], "Betalning av kreditkort")
        self.assertEqual(kat["SAS EUROBONUS"], "Betalning av kreditkort")
        self.assertEqual(kat["Lön"], "Lön")
        self.assertEqual(kat["TRÄNGSELSKATT"], "Parkering och vägavgifter")

    def test_sebkort_sektioner_per_kort(self):
        imp = importera(self.seb, xlsx(SEBKORT_EXPORT), "transaktioner.xlsx")
        self.assertEqual((imp.format, imp.antal_nya, imp.tecken_vant), ("sas", 6, True))
        self.assertEqual(sum(Transaktion.objects.values_list("belopp", flat=True)), Decimal("7976.36"))  # filens summa, omvänd
        cafe = Transaktion.objects.get(text__startswith="CAFE SOLEIL")
        self.assertEqual((cafe.valuta, cafe.utlandskt_belopp, cafe.kortinnehavare), ("EUR", Decimal("10.00"), "Testsson Anna"))
        self.assertTrue(Transaktion.objects.filter(text="SÖDERBERGS BAGERI, HÄGERSTEN").exists())
        sl = Transaktion.objects.get(text="SL, STOCKHOLM")
        self.assertEqual((sl.kortinnehavare, sl.kategori.namn), ("Testsson Bo", "Kollektivtrafik och taxi"))
        retur = Transaktion.objects.get(text__startswith="HM SE0152")
        self.assertEqual((retur.belopp, retur.kategori.namn), (Decimal("299.00"), "Kläder och skor"))
        self.assertEqual(Transaktion.objects.get(text="Inbetalning").kategori.namn, "Betalning av kreditkort")
        self.assertEqual(Transaktion.objects.get(text__startswith="Ränta på").kategori.namn, "Bankavgifter och räntor")

    def test_amex_transaktionsspecifikationer(self):
        imp = importera(self.amex, xlsx(AMEX_EXPORT), "activity.xlsx")
        self.assertEqual((imp.format, imp.antal_nya, imp.tecken_vant), ("amex", 5, True))
        kindle = Transaktion.objects.get(text__startswith="KINDLE")
        self.assertEqual((kindle.datum, kindle.belopp, kindle.valuta, kindle.utlandskt_belopp),
                         (dt.date(2026, 11, 1), Decimal("-61.68"), "USD", Decimal("6.13")))
        self.assertEqual(kindle.kategori.namn, "Prenumerationer och appar")
        ica = Transaktion.objects.get(text="ICA KVANTUM LILJEHOLMEN STOCKHOLM")
        self.assertEqual((ica.kortinnehavare, ica.kategori.namn), ("Bo Testsson", "Livsmedel"))
        self.assertEqual(Transaktion.objects.get(text__startswith="BETALNING").belopp, Decimal("4000.00"))
        self.assertEqual(Transaktion.objects.get(text__startswith="PERIODENS").kategori.namn, "Bankavgifter och räntor")
        self.assertEqual(Transaktion.objects.get(text__startswith="ICA NARA").belopp, Decimal("105.70"))  # retur
