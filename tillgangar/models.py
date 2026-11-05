"""Tillgångar (fastigheter, bostadsrätter, värdepapper, pension, fordon m.m.), värderingar och lån."""

import datetime as dt
from decimal import Decimal

from django.db import models
from django.db.models import Sum
from django.urls import reverse


class Tillgang(models.Model):
    VILLA, BOSTADSRATT, FRITIDSHUS, TOMT, HYRESFASTIGHET = "villa", "bostadsratt", "fritidshus", "tomt", "hyresfastighet"
    VARDEPAPPER, PENSION, FORDON, OVRIGT = "vardepapper", "pension", "fordon", "ovrigt"
    TYPER = [(VILLA, "Villa/radhus (fastighet)"), (BOSTADSRATT, "Bostadsrätt"), (FRITIDSHUS, "Fritidshus"),
             (TOMT, "Tomt/mark/skog"), (HYRESFASTIGHET, "Uthyrd fastighet/lägenhet"),
             (VARDEPAPPER, "Aktier och fonder"), (PENSION, "Pension"), (FORDON, "Bil/båt/fordon"),
             (OVRIGT, "Övrig tillgång")]
    FASTIGHETSTYPER = (VILLA, BOSTADSRATT, FRITIDSHUS, TOMT, HYRESFASTIGHET)

    namn = models.CharField(max_length=120)
    typ = models.CharField(max_length=16, choices=TYPER)
    beskrivning = models.TextField(blank=True)
    # Fastighet/bostad
    adress = models.CharField(max_length=200, blank=True)
    beteckning = models.CharField("fastighetsbeteckning / lägenhetsnr", max_length=100, blank=True)
    forening = models.CharField("bostadsrättsförening", max_length=120, blank=True)
    boarea = models.DecimalField("boarea (m²)", max_digits=7, decimal_places=1, null=True, blank=True)
    taxeringsvarde = models.DecimalField("taxeringsvärde", max_digits=14, decimal_places=0, null=True, blank=True)
    taxeringsar = models.PositiveSmallIntegerField("taxeringsår", null=True, blank=True)
    # Anskaffning
    kopdatum = models.DateField("köpdatum", null=True, blank=True)
    kopeskilling = models.DecimalField("köpeskilling", max_digits=14, decimal_places=0, null=True, blank=True)
    kopkostnader = models.DecimalField("köpkostnader (lagfart, pantbrev, mäklare)", max_digits=14,
                                       decimal_places=0, null=True, blank=True)
    agarandel = models.DecimalField("din ägarandel (%)", max_digits=5, decimal_places=2, default=100)
    salt_datum = models.DateField("såld", null=True, blank=True)
    aktiv = models.BooleanField(default=True)
    ordning = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "tillgång"
        verbose_name_plural = "tillgångar"
        ordering = ["ordning", "namn"]

    def __str__(self):
        return self.namn

    def get_absolute_url(self):
        return reverse("tillgang", args=[self.pk])

    @property
    def ar_fastighet(self):
        return self.typ in self.FASTIGHETSTYPER

    def varde_per(self, datum=None):
        """Hela tillgångens marknadsvärde enligt senaste värdering till och med datum (eller None)."""
        datum = datum or dt.date.today()
        if self.salt_datum and datum >= self.salt_datum:
            return Decimal(0)
        if self.kopdatum and datum < self.kopdatum:
            return Decimal(0)
        v = self.varderingar.filter(datum__lte=datum).order_by("-datum", "-id").first()
        if v:
            return v.varde
        return self.kopeskilling or Decimal(0)

    def mitt_varde_per(self, datum=None):
        return (self.varde_per(datum) * self.agarandel / 100).quantize(Decimal(1))

    def senaste_vardering(self):
        return self.varderingar.order_by("-datum", "-id").first()

    def lan_per(self, datum=None):
        return sum((l.saldo_per(datum) for l in self.lan.filter(aktiv=True)), Decimal(0))

    def summa_forbattringar(self):
        return self.forbattringar.aggregate(s=Sum("belopp"))["s"] or Decimal(0)

    def anskaffningsvarde(self):
        return (self.kopeskilling or 0) + (self.kopkostnader or 0) + self.summa_forbattringar()


class Vardering(models.Model):
    tillgang = models.ForeignKey(Tillgang, on_delete=models.CASCADE, related_name="varderingar")
    datum = models.DateField()
    varde = models.DecimalField("värde", max_digits=14, decimal_places=0,
                                help_text="Hela tillgångens värde (din andel räknas fram med ägarandelen)")
    kalla = models.CharField("källa", max_length=120, blank=True, help_text="T.ex. Booli, mäklare, depåutdrag")

    class Meta:
        verbose_name = "värdering"
        verbose_name_plural = "värderingar"
        ordering = ["-datum", "-id"]

    def __str__(self):
        return f"{self.tillgang} {self.datum}: {self.varde}"


class Forbattring(models.Model):
    """Förbättringsutgifter (ny- till- och ombyggnad, förbättrande reparationer) – höjer anskaffningsvärdet."""

    tillgang = models.ForeignKey(Tillgang, on_delete=models.CASCADE, related_name="forbattringar")
    datum = models.DateField()
    beskrivning = models.CharField(max_length=200)
    belopp = models.DecimalField(max_digits=14, decimal_places=0)

    class Meta:
        verbose_name = "förbättringsutgift"
        verbose_name_plural = "förbättringsutgifter"
        ordering = ["-datum"]

    def __str__(self):
        return f"{self.beskrivning} ({self.datum})"


class Lan(models.Model):
    BOLAN, BILLAN, BLANCO, CSN, OVRIGT = "bolan", "billan", "blanco", "csn", "ovrigt"
    TYPER = [(BOLAN, "Bolån"), (BILLAN, "Billån"), (BLANCO, "Privatlån/blanco"), (CSN, "Studielån (CSN)"),
             (OVRIGT, "Övrigt lån")]

    namn = models.CharField(max_length=120)
    typ = models.CharField(max_length=8, choices=TYPER, default=BOLAN)
    langivare = models.CharField("långivare", max_length=100, blank=True)
    lanenummer = models.CharField("lånenummer", max_length=60, blank=True)
    tillgang = models.ForeignKey(Tillgang, on_delete=models.SET_NULL, null=True, blank=True, related_name="lan",
                                 verbose_name="säkerhet (tillgång)")
    ranta = models.DecimalField("ränta (%)", max_digits=5, decimal_places=3, null=True, blank=True)
    bunden_till = models.DateField("räntan bunden till", null=True, blank=True)
    amortering_per_manad = models.DecimalField("amortering per månad", max_digits=12, decimal_places=0,
                                               null=True, blank=True)
    agarandel = models.DecimalField("din andel av lånet (%)", max_digits=5, decimal_places=2, default=100)
    aktiv = models.BooleanField(default=True)

    class Meta:
        verbose_name = "lån"
        verbose_name_plural = "lån"
        ordering = ["namn"]

    def __str__(self):
        return self.namn

    def get_absolute_url(self):
        return reverse("lan", args=[self.pk])

    def saldo_per(self, datum=None):
        """Hela lånets skuld (positivt belopp) enligt senaste saldo till och med datum."""
        datum = datum or dt.date.today()
        s = self.saldon.filter(datum__lte=datum).order_by("-datum", "-id").first()
        return s.saldo if s else Decimal(0)

    def mitt_saldo_per(self, datum=None):
        return (self.saldo_per(datum) * self.agarandel / 100).quantize(Decimal(1))

    def senaste_saldo(self):
        return self.saldon.order_by("-datum", "-id").first()

    def rantekostnad_per_manad(self):
        if not self.ranta:
            return None
        return (self.saldo_per() * self.ranta / 100 / 12).quantize(Decimal(1))


class Lanesaldo(models.Model):
    lan = models.ForeignKey(Lan, on_delete=models.CASCADE, related_name="saldon")
    datum = models.DateField()
    saldo = models.DecimalField("skuld", max_digits=14, decimal_places=0)
    ranta = models.DecimalField("ränta (%) vid tillfället", max_digits=5, decimal_places=3, null=True, blank=True)

    class Meta:
        verbose_name = "lånesaldo"
        verbose_name_plural = "lånesaldon"
        ordering = ["-datum", "-id"]

    def __str__(self):
        return f"{self.lan} {self.datum}: {self.saldo}"
