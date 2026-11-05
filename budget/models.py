"""Budget per år och kategori, med ett belopp per månad.

Beloppen anges som positiva tal: inkomster som det du får in, utgifter och sparande som det som går ut.
"""

from decimal import Decimal

from django.db import models
from django.urls import reverse

from ekonomi.models import Kategori

MANADER = range(1, 13)
MANADSNAMN = ["jan", "feb", "mar", "apr", "maj", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]


class Budget(models.Model):
    ar = models.PositiveSmallIntegerField("år")
    namn = models.CharField(max_length=100, default="Budget")
    huvudbudget = models.BooleanField(default=True, help_text="Används på översikten och i uppföljningen")
    anteckning = models.TextField(blank=True)
    skapad = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "budget"
        verbose_name_plural = "budgetar"
        ordering = ["-ar", "-huvudbudget", "namn"]

    def __str__(self):
        return f"{self.namn} {self.ar}"

    def get_absolute_url(self):
        return reverse("budget_uppfoljning", args=[self.pk])

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.huvudbudget:
            Budget.objects.filter(ar=self.ar).exclude(pk=self.pk).update(huvudbudget=False)

    @classmethod
    def for_ar(cls, ar):
        return cls.objects.filter(ar=ar).order_by("-huvudbudget", "-id").first()

    def per_kategori(self):
        """{kategori_id: [12 belopp]}"""
        return {p.kategori_id: p.varden for p in self.poster.all()}


class Budgetpost(models.Model):
    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name="poster")
    kategori = models.ForeignKey(Kategori, on_delete=models.CASCADE, related_name="budgetposter")
    m1 = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    m2 = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    m3 = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    m4 = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    m5 = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    m6 = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    m7 = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    m8 = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    m9 = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    m10 = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    m11 = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    m12 = models.DecimalField(max_digits=12, decimal_places=0, default=0)

    class Meta:
        verbose_name = "budgetpost"
        verbose_name_plural = "budgetposter"
        constraints = [models.UniqueConstraint(fields=["budget", "kategori"], name="en_post_per_kategori")]

    def __str__(self):
        return f"{self.budget}: {self.kategori}"

    @property
    def varden(self):
        return [getattr(self, f"m{m}") for m in MANADER]

    @varden.setter
    def varden(self, lista):
        for m, v in zip(MANADER, lista):
            setattr(self, f"m{m}", Decimal(v or 0))

    @property
    def summa(self):
        return sum(self.varden, Decimal(0))
