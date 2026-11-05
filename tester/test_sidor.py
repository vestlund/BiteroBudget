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
                    f"/konton/{self.bank.pk}/", f"/konton/{self.bank.pk}/andra/", "/budget/", "/budget/?visa=manader",
                    "/budget/budgetar/", "/budget/ny/", f"/budget/{self.budget.pk}/redigera/", "/tillgangar/",
                    "/tillgangar/ny/", f"/tillgangar/{self.hus.pk}/", "/tillgangar/formogenhet/", "/lan/nytt/",
                    f"/lan/{self.lan.pk}/", "/installningar/kategorier/", "/installningar/regler/",
                    "/installningar/regler/ny/", "/admin/"]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

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
