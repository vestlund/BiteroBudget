"""Nettoförmögenhet: konton + tillgångar − lån − kreditkortsskulder, vid ett visst datum."""

import datetime as dt
from decimal import Decimal

from ekonomi.models import Konto

from .models import Lan, Tillgang


def manadsslut(ar, manad):
    nasta = dt.date(ar + (manad == 12), manad % 12 + 1, 1)
    return nasta - dt.timedelta(days=1)


def formogenhet_per(datum=None):
    datum = datum or dt.date.today()
    r = {"likvida": Decimal(0), "investeringskonton": Decimal(0), "kreditkort": Decimal(0),
         "tillgangar": Decimal(0), "fastigheter": Decimal(0), "lan": Decimal(0)}
    for k in Konto.objects.filter(aktiv=True):
        s = k.saldo_per(datum)
        if k.typ == Konto.KREDITKORT and s < 0:
            r["kreditkort"] += s  # skuld till kortutgivaren
        elif k.typ == Konto.KREDITKORT:
            r["likvida"] += s  # tillgodo på kortet
        elif k.typ == Konto.INVESTERING:
            r["investeringskonton"] += s
        else:
            r["likvida"] += s
    for t in Tillgang.objects.all():
        v = t.mitt_varde_per(datum)
        r["tillgangar"] += v
        if t.ar_fastighet:
            r["fastigheter"] += v
    for l in Lan.objects.all():
        r["lan"] += l.mitt_saldo_per(datum)
    r["summa_tillgangar"] = r["likvida"] + r["investeringskonton"] + r["tillgangar"]
    r["summa_skulder"] = r["lan"] - r["kreditkort"]  # kreditkortssaldot är negativt när du är skyldig
    r["netto"] = r["summa_tillgangar"] - r["summa_skulder"]
    return r


def historik(antal_manader=24, idag=None):
    idag = idag or dt.date.today()
    ar, man = idag.year, idag.month
    punkter = []
    for _ in range(antal_manader):
        d = min(manadsslut(ar, man), idag)
        punkter.append((d, formogenhet_per(d)))
        ar, man = (ar - 1, 12) if man == 1 else (ar, man - 1)
    return list(reversed(punkter))
