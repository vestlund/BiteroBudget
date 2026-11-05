"""Konton, kategorier, regler och transaktioner.

Belopp lagras med tecken ur kontots perspektiv: inbetalning/kredit = positivt, utgift/köp = negativt.
För kreditkort vänds tecknet vid import om kortutgivaren visar köp som positiva belopp (Amex, SAS Mastercard).
"""

import datetime as dt
import re
from decimal import Decimal

from django.db import models
from django.db.models import Q, Sum
from django.urls import reverse


class Konto(models.Model):
    BANK, SPAR, KREDITKORT, INVESTERING, KONTANT = "bank", "spar", "kreditkort", "investering", "kontant"
    TYPER = [(BANK, "Bankkonto (lönekonto/hushåll)"), (SPAR, "Sparkonto"), (KREDITKORT, "Kreditkort"),
             (INVESTERING, "Investeringssparkonto/depå"), (KONTANT, "Kontanter")]
    AUTO, BANKFIL, AMEX, SAS = "auto", "bank", "amex", "sas"
    FORMAT = [(AUTO, "Känn igen automatiskt"), (BANKFIL, "Bank (CSV/Excel med datum, text, belopp)"),
              (AMEX, "American Express (även SAS Amex)"), (SAS, "SEB Kort (SAS EuroBonus Mastercard m.fl.)")]
    TECKEN_AUTO, TECKEN_SOM_FIL, TECKEN_VAND = "auto", "fil", "vand"
    TECKEN = [(TECKEN_AUTO, "Automatiskt (kreditkort: köp blir minus)"), (TECKEN_SOM_FIL, "Som i filen"),
              (TECKEN_VAND, "Vänd alltid tecknet")]

    namn = models.CharField(max_length=100)
    typ = models.CharField(max_length=12, choices=TYPER, default=BANK)
    institut = models.CharField("bank/kortutgivare", max_length=100, blank=True)
    kontonummer = models.CharField("kontonummer (eller sista siffrorna)", max_length=40, blank=True)
    importformat = models.CharField(max_length=10, choices=FORMAT, default=AUTO)
    tecken = models.CharField("tecken vid import", max_length=6, choices=TECKEN, default=TECKEN_AUTO)
    ingaende_saldo = models.DecimalField("ingående saldo", max_digits=14, decimal_places=2, default=0,
                                         help_text="Saldo före första transaktionen. Kreditkortsskuld anges som minus.")
    ingaende_datum = models.DateField("ingående saldo per", null=True, blank=True)
    ordning = models.PositiveSmallIntegerField(default=0)
    aktiv = models.BooleanField(default=True)

    class Meta:
        verbose_name = "konto"
        verbose_name_plural = "konton"
        ordering = ["ordning", "namn"]

    def __str__(self):
        return self.namn

    def get_absolute_url(self):
        return reverse("konto", args=[self.pk])

    @property
    def ar_kreditkort(self):
        return self.typ == self.KREDITKORT

    def saldo_per(self, datum=None):
        """Saldo vid dagens slut. Utgår från närmaste avstämda saldo (Kontosaldo) och räknar med transaktionerna."""
        datum = datum or dt.date.today()
        tr = self.transaktioner.all()
        fore = self.saldon.filter(datum__lte=datum).order_by("-datum", "-id").first()
        if fore:
            return fore.saldo + (tr.filter(datum__gt=fore.datum, datum__lte=datum).aggregate(s=Sum("belopp"))["s"] or 0)
        efter = self.saldon.filter(datum__gt=datum).order_by("datum", "id").first()
        if efter:
            return efter.saldo - (tr.filter(datum__gt=datum, datum__lte=efter.datum).aggregate(s=Sum("belopp"))["s"] or 0)
        if self.ingaende_datum and datum < self.ingaende_datum:
            return Decimal(0)
        if self.ingaende_datum:
            tr = tr.filter(datum__gte=self.ingaende_datum)
        return self.ingaende_saldo + (tr.filter(datum__lte=datum).aggregate(s=Sum("belopp"))["s"] or 0)


class Kontosaldo(models.Model):
    """Avstämt saldo ett visst datum, från kontoutdraget (saldokolumnen) eller inmatat för hand."""

    konto = models.ForeignKey(Konto, on_delete=models.CASCADE, related_name="saldon")
    datum = models.DateField()
    saldo = models.DecimalField(max_digits=14, decimal_places=2)
    kalla = models.CharField("källa", max_length=100, blank=True)

    class Meta:
        verbose_name = "kontosaldo"
        verbose_name_plural = "kontosaldon"
        ordering = ["-datum", "-id"]

    def __str__(self):
        return f"{self.konto} {self.datum}: {self.saldo}"


class Kategori(models.Model):
    INKOMST, UTGIFT, SPARANDE, OVERFORING = "inkomst", "utgift", "sparande", "overforing"
    TYPER = [(INKOMST, "Inkomst"), (UTGIFT, "Utgift"), (SPARANDE, "Sparande/amortering"),
             (OVERFORING, "Överföring mellan egna konton (räknas inte)")]

    namn = models.CharField(max_length=100)
    grupp = models.CharField(max_length=60, help_text="T.ex. Boende, Mat, Transport")
    typ = models.CharField(max_length=10, choices=TYPER, default=UTGIFT)
    ordning = models.PositiveSmallIntegerField(default=0)
    aktiv = models.BooleanField(default=True)

    class Meta:
        verbose_name = "kategori"
        verbose_name_plural = "kategorier"
        ordering = ["ordning", "grupp", "namn"]
        constraints = [models.UniqueConstraint(fields=["grupp", "namn"], name="unik_kategori")]

    def __str__(self):
        return f"{self.grupp} – {self.namn}"

    @property
    def budgeteras(self):
        return self.typ != self.OVERFORING

    def utfall(self, belopp):
        """Belopp i budgetens riktning: inkomster positiva, utgifter och sparande positiva när pengar går ut."""
        return belopp if self.typ == self.INKOMST else -belopp


class Kategoriregel(models.Model):
    """Om transaktionstexten innehåller mönstret sätts kategorin (och ev. tillgång) automatiskt."""

    monster = models.CharField("texten innehåller", max_length=100,
                               help_text="Matchar i början av ett ord (mönster på 1–2 tecken: hela ordet), skiftläge spelar ingen roll. "
                                         "Börja med ^ för att texten ska börja så.")
    kategori = models.ForeignKey(Kategori, on_delete=models.CASCADE, related_name="regler")
    konto = models.ForeignKey(Konto, on_delete=models.CASCADE, null=True, blank=True,
                              help_text="Lämna tomt för att gälla alla konton")
    tillgang = models.ForeignKey("tillgangar.Tillgang", on_delete=models.SET_NULL, null=True, blank=True,
                                 verbose_name="koppla till tillgång/fastighet")
    endast_utgifter = models.BooleanField("bara utgifter (minusbelopp)", default=False)
    endast_inkomster = models.BooleanField("bara inbetalningar (plusbelopp)", default=False)
    prioritet = models.SmallIntegerField(default=0, help_text="Högre vinner när flera regler träffar")

    class Meta:
        verbose_name = "kategoriregel"
        verbose_name_plural = "kategoriregler"
        ordering = ["-prioritet", "monster"]

    def __str__(self):
        return f"'{self.monster}' → {self.kategori}"

    def traffar(self, text, belopp, konto_id):
        if self.konto_id and self.konto_id != konto_id:
            return False
        if self.endast_utgifter and belopp >= 0 or self.endast_inkomster and belopp <= 0:
            return False
        t, m = (text or "").casefold(), self.monster.casefold().strip()
        if not m or m == "^":
            return False
        if m.startswith("^"):
            return t.startswith(m[1:])
        # mönstret ska börja ett ord: "ica" träffar "ICA NARA" och "MAXI ICA" men inte "AMERICAN EXPRESS".
        # Korta mönster (1–2 tecken) måste vara ett helt ord: "sl" träffar "SL, STOCKHOLM" men inte "SLITS".
        bokstav = "0-9a-zåäöæøéüß"
        slut = f"(?![{bokstav}])" if len(m) <= 2 else ""
        return re.search(f"(?<![{bokstav}])" + re.escape(m) + slut, t) is not None


class Importfil(models.Model):
    konto = models.ForeignKey(Konto, on_delete=models.CASCADE, related_name="importer")
    filnamn = models.CharField(max_length=255)
    format = models.CharField(max_length=40)
    importerad = models.DateTimeField(auto_now_add=True)
    antal_nya = models.PositiveIntegerField(default=0)
    antal_dubbletter = models.PositiveIntegerField(default=0)
    forsta_datum = models.DateField(null=True, blank=True)
    sista_datum = models.DateField(null=True, blank=True)
    tecken_vant = models.BooleanField(default=False)

    class Meta:
        verbose_name = "import"
        verbose_name_plural = "importer"
        ordering = ["-importerad"]

    def __str__(self):
        return f"{self.filnamn} ({self.konto})"


class TransaktionQuerySet(models.QuerySet):
    def raknas(self):
        """Transaktioner som påverkar budgeten: inte överföringar mellan egna konton."""
        return self.exclude(kategori__typ=Kategori.OVERFORING)

    def okategoriserade(self):
        return self.filter(kategori__isnull=True)

    def period(self, ar, manad=None):
        q = self.filter(datum__year=ar)
        return q.filter(datum__month=manad) if manad else q


class Transaktion(models.Model):
    objects = TransaktionQuerySet.as_manager()

    konto = models.ForeignKey(Konto, on_delete=models.CASCADE, related_name="transaktioner")
    datum = models.DateField(db_index=True)
    belopp = models.DecimalField(max_digits=14, decimal_places=2)
    text = models.CharField(max_length=300)
    valuta = models.CharField(max_length=3, blank=True)
    utlandskt_belopp = models.DecimalField("belopp i utländsk valuta", max_digits=14, decimal_places=2,
                                           null=True, blank=True)
    kategori = models.ForeignKey(Kategori, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="transaktioner")
    tillgang = models.ForeignKey("tillgangar.Tillgang", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="transaktioner", verbose_name="tillgång/fastighet")
    anteckning = models.CharField(max_length=300, blank=True)
    kortinnehavare = models.CharField(max_length=60, blank=True, help_text="Från kortutdraget (Amex, SEB Kort)")
    importfil = models.ForeignKey(Importfil, on_delete=models.CASCADE, null=True, blank=True,
                                  related_name="transaktioner")
    nyckel = models.CharField(max_length=64, unique=True, null=True, blank=True,
                              help_text="Används för att känna igen dubbletter vid import")
    manuellt_kategoriserad = models.BooleanField(default=False)
    skapad = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "transaktion"
        verbose_name_plural = "transaktioner"
        ordering = ["-datum", "-id"]
        indexes = [models.Index(fields=["konto", "datum"])]

    def __str__(self):
        return f"{self.datum} {self.text} {self.belopp}"

    def get_absolute_url(self):
        return reverse("transaktion", args=[self.pk])


def basta_regel(regler, text, belopp, konto_id):
    """Den regel som ska gälla: högst prioritet, sedan längst mönster (mest specifik)."""
    traff = [r for r in regler if r.traffar(text, belopp, konto_id)]
    if not traff:
        return None
    return max(traff, key=lambda r: (r.prioritet, len(r.monster), bool(r.konto_id)))


def kategorisera(qs=None, skriv_over=False):
    """Kör reglerna på transaktioner. Rör inte manuellt kategoriserade. Returnerar antal ändrade."""
    regler = list(Kategoriregel.objects.select_related("kategori"))
    qs = Transaktion.objects.all() if qs is None else qs
    qs = qs.filter(manuellt_kategoriserad=False)
    if not skriv_over:
        qs = qs.filter(kategori__isnull=True)
    andrade = 0
    for t in qs:
        r = basta_regel(regler, t.text, t.belopp, t.konto_id)
        if r and (t.kategori_id != r.kategori_id or (r.tillgang_id and t.tillgang_id != r.tillgang_id)):
            t.kategori_id = r.kategori_id
            if r.tillgang_id:
                t.tillgang_id = r.tillgang_id
            t.save(update_fields=["kategori", "tillgang"])
            andrade += 1
    return andrade


def utfall_per_kategori_och_manad(ar):
    """{kategori_id: [12 belopp i budgetens riktning]} för året. Överföringar och okategoriserat ingår inte."""
    res = {}
    rader = (Transaktion.objects.filter(datum__year=ar).exclude(kategori__isnull=True)
             .values("kategori_id", "kategori__typ", "datum__month").annotate(s=Sum("belopp")))
    for r in rader:
        v = r["s"] if r["kategori__typ"] == Kategori.INKOMST else -r["s"]
        res.setdefault(r["kategori_id"], [Decimal(0)] * 12)[r["datum__month"] - 1] += v
    return res


def okategoriserat_per_manad(ar):
    """(inbetalningar, utbetalningar) per månad för okategoriserade transaktioner."""
    inn, ut = [Decimal(0)] * 12, [Decimal(0)] * 12
    for r in (Transaktion.objects.filter(datum__year=ar, kategori__isnull=True)
              .values("datum__month").annotate(i=Sum("belopp", filter=Q(belopp__gt=0)),
                                               u=Sum("belopp", filter=Q(belopp__lt=0)))):
        inn[r["datum__month"] - 1] += r["i"] or 0
        ut[r["datum__month"] - 1] -= r["u"] or 0
    return inn, ut
