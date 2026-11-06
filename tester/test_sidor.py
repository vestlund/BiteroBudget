"""Alla sidor ska gå att öppna, och budgetuppföljningen ska räkna rätt."""

import datetime as dt
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from budget.models import Budget, Budgetpost
from ekonomi.models import Kategori, Konto, Kontosaldo, Transaktion
from tillgangar.berakning import formogenhet_per
from tillgangar.models import Lan, Lanesaldo, Tillgang, Vardering


class Sidor(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_superuser("test", "t@example.com", "hemligt-123"))
        self.idag = dt.date.today()
        self.bank = Konto.objects.create(namn="Lönekonto", typ=Konto.BANK)
        self.kort = Konto.objects.create(namn="Amex", typ=Konto.KREDITKORT)
        self.mat = Kategori.objects.get(namn="Livsmedel")
        self.lon = Kategori.objects.get(namn="Lön")
        self.kortbet = Kategori.objects.get(namn="Betalning av kreditkort")
        T = Transaktion.objects.create
        T(konto=self.bank, datum=self.idag, belopp=Decimal("30000"), text="LÖN", kategori=self.lon)
        T(konto=self.kort, datum=self.idag, belopp=Decimal("-2500"), text="ICA", kategori=self.mat)
        T(konto=self.bank, datum=self.idag, belopp=Decimal("-2500"), text="AMEX", kategori=self.kortbet)
        T(konto=self.kort, datum=self.idag, belopp=Decimal("2500"), text="BETALNING", kategori=self.kortbet)
        self.okat = T(konto=self.bank, datum=self.idag, belopp=Decimal("-100"), text="OKÄND")
        self.hus = Tillgang.objects.create(namn="Villan", typ=Tillgang.VILLA, kopeskilling=4000000, agarandel=50,
                                           kopdatum=dt.date(2015, 1, 1), boarea=140)
        Vardering.objects.create(tillgang=self.hus, datum=self.idag - dt.timedelta(days=40), varde=6000000)
        self.lan = Lan.objects.create(namn="Bolån", tillgang=self.hus, ranta=Decimal("3.1"), agarandel=50)
        Lanesaldo.objects.create(lan=self.lan, datum=self.idag - dt.timedelta(days=10), saldo=2000000)
        self.budget = Budget.objects.create(ar=self.idag.year)
        p = Budgetpost(budget=self.budget, kategori=self.mat)
        p.varden = [3000] * 12
        p.save()

    def test_alla_sidor(self):
        for url in ["/", "/transaktioner/", "/transaktioner/?kategori=ingen", "/transaktioner/ny/",
                    f"/transaktioner/{self.okat.pk}/", "/importera/", "/konton/", "/konton/nytt/",
                    f"/konton/{self.bank.pk}/", f"/konton/{self.bank.pk}/andra/", "/budget/", "/budget/?visa=manad",
                    "/budget/budgetar/", "/budget/ny/", f"/budget/{self.budget.pk}/redigera/", "/tillgangar/",
                    "/tillgangar/ny/", f"/tillgangar/{self.hus.pk}/", "/tillgangar/formogenhet/", "/lan/nytt/",
                    f"/lan/{self.lan.pk}/", "/installningar/kategorier/", "/installningar/regler/",
                    "/installningar/regler/ny/", "/installningar/hushall/", "/admin/"]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_budgetuppfoljning_per_manad_ar_standard_och_lankar_till_transaktioner(self):
        Transaktion.objects.create(konto=self.bank, datum=self.idag, belopp=-123, text="ICA", kategori=self.mat)
        sida = self.client.get("/budget/").content.decode()
        lank = f"/transaktioner/?kategori={self.mat.pk}&amp;ar={self.idag.year}&amp;manad={self.idag.month}"
        self.assertIn(lank, sida)
        self.assertIn("Snitt/mån", sida)
        lista = self.client.get(lank.replace("&amp;", "&")).content.decode()
        self.assertIn("ICA", lista)

    def test_budgetuppfoljning_exkludera_kategori(self):
        Transaktion.objects.create(konto=self.bank, datum=self.idag, belopp=-500, text="ICA", kategori=self.mat)

        def utgifter(svar):
            s = next(s for s in svar.context["sektioner"] if s["rubrik"] == "Utgifter")
            return sum(s["summa"]["manader"]), sum(s["summa"]["budget_manader"])

        med = utgifter(self.client.get("/budget/"))
        self.assertGreaterEqual(med[0], 500)
        utan = utgifter(self.client.get(f"/budget/?exkl={self.mat.pk}"))
        mat = -sum(t.belopp for t in Transaktion.objects.filter(kategori=self.mat, datum__year=self.idag.year))
        self.assertEqual(utan, (med[0] - mat, med[1] - 36000))
        sida = self.client.get("/budget/")  # urvalet sparas i sessionen
        self.assertEqual(utgifter(sida), utan)
        self.assertContains(sida, "Räkna med alla")
        self.assertEqual(utgifter(self.client.get("/budget/?exkl=")), med)

    def test_budgetuppfoljning_budget_per_ar_eller_manad(self):
        def mat_budget(svar):
            s = next(s for s in svar.context["sektioner"] if s["rubrik"] == "Utgifter")
            return s["summa"]["b_visa"]
        self.assertEqual(mat_budget(self.client.get("/budget/?exkl=")), 36000)
        svar = self.client.get("/budget/?budget=manad")
        self.assertEqual(mat_budget(svar), 3000)
        self.assertContains(svar, "Budget/mån")
        self.assertEqual(mat_budget(self.client.get("/budget/")), 3000)  # valet sparas i sessionen
        self.assertEqual(mat_budget(self.client.get("/budget/?budget=ar")), 36000)

    def test_oversikt_jamfor_mot_konsumentverket(self):
        from ekonomi import referenser
        from ekonomi.models import Hushallsmedlem

        ref = referenser.konsumentverket([45, 43, 14, 12, 7])
        self.assertEqual((ref["livsmedel"], ref["klader"], ref["hygien"], ref["el"]), (12890, 4770, 2060, 1010))
        self.assertEqual(ref["medier"], 420 + 1920 - 229 + 720)  # mobil från 8 år
        sida = self.client.get("/").content.decode()
        self.assertIn("Inställningar → Hushåll", sida)
        self.client.post("/installningar/hushall/", {"namn": "Vuxen", "fodelsear": self.idag.year - 40})
        self.client.post("/installningar/hushall/", {"namn": "Barn", "fodelsear": self.idag.year - 10})
        self.assertEqual(Hushallsmedlem.objects.count(), 2)
        self.assertContains(self.client.post("/installningar/hushall/", {"namn": "Fel", "fodelsear": "1800"}),
                            "giltigt födelseår")
        svar = self.client.get("/")
        j = svar.context["j"]
        self.assertEqual(len(j["kv_rader"]), 9)
        self.assertEqual(j["kv_rader"][0]["referens"], 2730 + 2130)
        self.assertContains(svar, "Andel av utgifterna mot SCB")
        self.client.post("/installningar/hushall/", {"radera": Hushallsmedlem.objects.first().pk})
        self.assertEqual(Hushallsmedlem.objects.count(), 1)

    def test_tjanstebil_raknas_med_i_jamforelsen(self):
        from ekonomi.models import Tjanstebil

        fore = next(r for r in self.client.get("/").context["j"]["ovriga"] if r["rubrik"] == "Bil och drivmedel")
        self.client.post("/installningar/hushall/", {"tjanstebil": "1", "namn": "Elbil", "formansvarde": "5400",
                                                     "nettoloneavdrag": "5400", "bruttoloneavdrag": "",
                                                     "marginalskatt": "52"})
        bil = Tjanstebil.objects.get()
        self.assertEqual((bil.beskattat_formansvarde, bil.skatt, bil.kostnad), (0, 0, 5400))
        delvis = Tjanstebil(formansvarde=6000, nettoloneavdrag=2000, marginalskatt=52)
        self.assertEqual(delvis.kostnad, 2000 + 2080)  # 2 000 netto + 52 % på 4 000
        brutto = Tjanstebil(formansvarde=5000, bruttoloneavdrag=5000, marginalskatt=52)
        self.assertEqual(brutto.kostnad, 2400 + 2600)
        j = self.client.get("/").context["j"]
        efter = next(r for r in j["ovriga"] if r["rubrik"] == "Bil och drivmedel")
        self.assertEqual(efter["faktiskt"] - fore["faktiskt"], 5400)
        self.assertEqual(j["tjanstebil"], 5400)
        self.client.post("/installningar/hushall/", {"tjanstebil": "1", "vaxla": bil.pk})
        self.assertEqual(self.client.get("/").context["j"]["tjanstebil"], 0)

    def test_kraver_inloggning(self):
        self.client.logout()
        self.assertEqual(self.client.get("/").status_code, 302)

    def test_formogenhet(self):
        f = formogenhet_per(self.idag)
        self.assertEqual(f["tillgangar"], Decimal(3000000))  # 50 % av 6 Mkr
        self.assertEqual(f["lan"], Decimal(1000000))
        self.assertEqual(f["likvida"], Decimal("27400"))
        self.assertEqual(f["kreditkort"], Decimal("0"))
        self.assertEqual(f["netto"], Decimal("2027400"))

    def test_budgetuppfoljning_raknar_inte_overforingar(self):
        r = self.client.get("/budget/")
        utg = next(s for s in r.context["sektioner"] if s["rubrik"] == "Utgifter")
        self.assertEqual(utg["summa"]["u_man"], Decimal("2500"))
        self.assertEqual(utg["summa"]["b_man"], Decimal("3000"))
        self.assertEqual(utg["summa"]["d_man"], Decimal("500"))  # 500 kr under budget = bra
        self.assertEqual(r.context["over"]["u_man"], Decimal("27500"))

    def test_satt_kategori_och_regel(self):
        self.client.post(f"/transaktioner/{self.okat.pk}/kategori/", {"kategori": self.mat.pk})
        self.okat.refresh_from_db()
        self.assertTrue(self.okat.manuellt_kategoriserad)
        ny = Transaktion.objects.create(konto=self.bank, datum=self.idag, belopp=-5, text="OKÄND BUTIK 2")
        self.client.post(f"/transaktioner/{self.okat.pk}/", {"kategori": self.mat.pk, "skapa_regel": "okänd",
                                                              "konto": self.bank.pk, "datum": self.idag,
                                                              "text": "OKÄND", "belopp": "-100"})
        ny.refresh_from_db()
        self.assertEqual(ny.kategori, self.mat)

    def test_ny_budget_fran_utfall_och_redigera(self):
        Transaktion.objects.create(konto=self.bank, datum=dt.date(self.idag.year - 1, 3, 5), belopp=-1200,
                                   text="ICA", kategori=self.mat)
        r = self.client.post("/budget/ny/", {"ar": self.idag.year + 1, "namn": "Nästa", "huvudbudget": "on",
                                             "utga_fran": "utfall", "okning": "0"})
        self.assertEqual(r.status_code, 302)
        b = Budget.objects.get(ar=self.idag.year + 1)
        # förra året för den nya budgeten är i år: livsmedel och lön, men inte överföringar eller okategoriserat
        self.assertEqual(b.poster.get(kategori=self.mat).varden[self.idag.month - 1], Decimal(2500))
        self.assertEqual(set(b.poster.values_list("kategori__namn", flat=True)), {"Livsmedel", "Lön"})
        data = {f"k{self.mat.pk}_m{m}": "2 000" for m in range(1, 13)}
        self.client.post(f"/budget/{b.pk}/redigera/", data | {"namn": "Nästa"})
        self.assertEqual(b.poster.get().summa, Decimal(24000))

    def test_kontosaldo_manuellt(self):
        Kontosaldo.objects.create(konto=self.bank, datum=self.idag - dt.timedelta(days=1), saldo=1000)
        self.assertEqual(self.bank.saldo_per(self.idag), Decimal("28400"))
