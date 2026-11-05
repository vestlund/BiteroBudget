"""Det Claude kan göra i Bitero Budget via MCP. Rena funktioner som anropas av assistent/server.py.

Samma logik som webbsidorna använder (import, regler, budget, saldon). Skrivande anrop godkänns av
användaren i Claude-appen. Transaktionsrader från banken (datum, belopp, text) ändras aldrig, bara
kategori, koppling till tillgång och anteckning.
"""

import datetime as dt
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.db import transaction
from django.db.models import Count, Q, Sum

from budget.models import MANADSNAMN, Budget, Budgetpost
from ekonomi.importering import ImportFel, importera
from ekonomi.models import (
    Importfil,
    Kategori,
    Kategoriregel,
    Konto,
    Kontosaldo,
    Transaktion,
    kategorisera,
    okategoriserat_per_manad,
    utfall_per_kategori_och_manad,
)
from tillgangar.berakning import formogenhet_per
from tillgangar.models import Lan, Lanesaldo, Tillgang, Vardering

WEBB = "http://127.0.0.1:8010"
MAX_RADER = 500


class VerktygsFel(Exception):
    """Fel som visas för Claude/användaren som ett vanligt meddelande."""


# ------------------------------------------------------------------ hjälp

def _s(v):
    """Till text. Belopp avrundas till ören (summor från SQLite kan få många decimaler)."""
    if v is None:
        return None
    if isinstance(v, (Decimal, float)):
        return str(Decimal(str(v)).quantize(Decimal("0.01")))
    return str(v)


def _belopp(v, falt="belopp"):
    try:
        return Decimal(str(v).replace(" ", "").replace("\xa0", "").replace(",", ".")).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        raise VerktygsFel(f"Ogiltigt belopp för {falt}: {v}")


def _datum(v, falt="datum"):
    if isinstance(v, dt.date):
        return v
    try:
        return dt.date.fromisoformat(str(v)[:10])
    except ValueError:
        raise VerktygsFel(f"Ogiltigt datum för {falt}: {v} (använd ÅÅÅÅ-MM-DD)")


def _konto(v):
    """Konto på id eller namn (skiftlägesokänsligt, del av namnet räcker om det är entydigt)."""
    if v in (None, ""):
        raise VerktygsFel("Ange konto (id eller namn). Använd verktyget konton.")
    if str(v).isdigit():
        k = Konto.objects.filter(pk=int(v)).first()
        if k:
            return k
    traff = list(Konto.objects.filter(namn__iexact=str(v))) or list(Konto.objects.filter(namn__icontains=str(v)))
    if len(traff) == 1:
        return traff[0]
    namn = ", ".join(f"{k.pk}: {k.namn}" for k in Konto.objects.all())
    raise VerktygsFel(f"Hittade {'flera' if traff else 'inget'} konto som matchar '{v}'. Konton: {namn}")


def _kategori(v):
    """Kategori på id, 'Grupp – Namn' eller namn."""
    if v in (None, ""):
        raise VerktygsFel("Ange kategori. Använd verktyget kategorier.")
    s = str(v).strip()
    if s.isdigit():
        k = Kategori.objects.filter(pk=int(s)).first()
        if k:
            return k
    for sep in (" – ", " - ", "/", ":"):
        if sep in s:
            grupp, namn = (x.strip() for x in s.split(sep, 1))
            k = Kategori.objects.filter(grupp__iexact=grupp, namn__iexact=namn).first()
            if k:
                return k
    traff = list(Kategori.objects.filter(namn__iexact=s))
    if len(traff) == 1:
        return traff[0]
    raise VerktygsFel(f"Hittade {'flera' if traff else 'ingen'} kategori som heter '{v}'. "
                      "Använd id eller 'Grupp – Namn' från verktyget kategorier, eller skapa den med ny_kategori.")


def _tillgang(v):
    if v in (None, ""):
        return None
    if str(v).isdigit() and (t := Tillgang.objects.filter(pk=int(v)).first()):
        return t
    traff = list(Tillgang.objects.filter(namn__icontains=str(v)))
    if len(traff) == 1:
        return traff[0]
    raise VerktygsFel(f"Hittade {'flera' if traff else 'ingen'} tillgång som matchar '{v}'. Använd verktyget tillgangar.")


def _lan(v):
    if str(v).isdigit() and (l := Lan.objects.filter(pk=int(v)).first()):
        return l
    traff = list(Lan.objects.filter(namn__icontains=str(v)))
    if len(traff) == 1:
        return traff[0]
    raise VerktygsFel(f"Hittade {'flera' if traff else 'inget'} lån som matchar '{v}'. Använd verktyget tillgangar.")


def _kat_text(k):
    return f"{k.grupp} – {k.namn}" if k else None


def _transaktion(t):
    return {"id": t.pk, "datum": str(t.datum), "konto": t.konto.namn, "text": t.text, "belopp": str(t.belopp),
            "kategori": _kat_text(t.kategori), "tillgang": t.tillgang.namn if t.tillgang else None,
            "kortinnehavare": t.kortinnehavare or None, "anteckning": t.anteckning or None,
            "valuta": f"{t.utlandskt_belopp} {t.valuta}" if t.utlandskt_belopp else None,
            "manuellt_kategoriserad": t.manuellt_kategoriserad}


# ------------------------------------------------------------------ läsa

def oversikt():
    idag = dt.date.today()
    f = formogenhet_per(idag)
    utfall = utfall_per_kategori_och_manad(idag.year)
    budget = Budget.for_ar(idag.year)
    bud = budget.per_kategori() if budget else {}
    typer = dict(Kategori.objects.values_list("pk", "typ"))

    def summa(typ, manad=None):
        u = sum((v[manad - 1] if manad else sum(v)) for k, v in utfall.items() if typer.get(k) == typ)
        b = sum((v[manad - 1] if manad else sum(v[:idag.month])) for k, v in bud.items() if typer.get(k) == typ)
        return {"utfall": _s(u), "budget": _s(b) if budget else None}

    return {
        "datum": str(idag), "webb": WEBB,
        "formogenhet": {k: _s(v) for k, v in f.items()},
        "konton": [{"id": k.pk, "namn": k.namn, "typ": k.get_typ_display(), "saldo": _s(k.saldo_per(idag))}
                   for k in Konto.objects.filter(aktiv=True)],
        "manaden": {"inkomster": summa(Kategori.INKOMST, idag.month), "utgifter": summa(Kategori.UTGIFT, idag.month),
                    "sparande": summa(Kategori.SPARANDE, idag.month)},
        "hittills_i_ar": {"inkomster": summa(Kategori.INKOMST), "utgifter": summa(Kategori.UTGIFT),
                          "sparande": summa(Kategori.SPARANDE)},
        "budget": str(budget) if budget else None,
        "okategoriserade": Transaktion.objects.okategoriserade().count(),
        "senaste_import": (lambda i: {"fil": i.filnamn, "konto": i.konto.namn, "tid": str(i.importerad)[:16],
                                      "sista_datum": str(i.sista_datum)} if i else None)(
            Importfil.objects.select_related("konto").first()),
    }


def konton():
    idag = dt.date.today()
    return [{"id": k.pk, "namn": k.namn, "typ": k.get_typ_display(), "institut": k.institut,
             "importformat": k.get_importformat_display(), "saldo": _s(k.saldo_per(idag)),
             "senaste_avstamda_saldo": (lambda s: {"datum": str(s.datum), "saldo": str(s.saldo)} if s else None)(
                 k.saldon.first()),
             "transaktioner": k.transaktioner.count(),
             "senaste_transaktion": _s(k.transaktioner.order_by("-datum").values_list("datum", flat=True).first()),
             "aktiv": k.aktiv} for k in Konto.objects.all()]


def kategorier():
    ar = dt.date.today().year
    antal = dict(Transaktion.objects.filter(datum__year=ar).values_list("kategori").annotate(n=Count("id")))
    return [{"id": k.pk, "kategori": _kat_text(k), "typ": k.typ, "aktiv": k.aktiv,
             f"transaktioner_{ar}": antal.get(k.pk, 0)} for k in Kategori.objects.all()]


def transaktioner(sok="", konto=None, kategori=None, grupp="", fran="", till="", okategoriserade=False,
                  kortinnehavare="", tillgang=None, min_belopp=None, max_belopp=None, max_antal=100):
    qs = Transaktion.objects.select_related("konto", "kategori", "tillgang")
    if sok:
        qs = qs.sok(sok)
    if konto not in (None, ""):
        qs = qs.filter(konto=_konto(konto))
    if okategoriserade:
        qs = qs.filter(kategori__isnull=True)
    elif kategori not in (None, ""):
        qs = qs.filter(kategori=_kategori(kategori))
    if grupp:
        qs = qs.filter(kategori__grupp__iexact=grupp)
    if fran:
        qs = qs.filter(datum__gte=_datum(fran, "fran"))
    if till:
        qs = qs.filter(datum__lte=_datum(till, "till"))
    if kortinnehavare:
        qs = qs.filter(kortinnehavare__icontains=kortinnehavare)
    if tillgang not in (None, ""):
        qs = qs.filter(tillgang=_tillgang(tillgang))
    if min_belopp not in (None, ""):
        qs = qs.filter(belopp__gte=_belopp(min_belopp))
    if max_belopp not in (None, ""):
        qs = qs.filter(belopp__lte=_belopp(max_belopp))
    summa = qs.aggregate(s=Sum("belopp"), n=Count("id"))
    n = max(1, min(int(max_antal or 100), MAX_RADER))
    return {"antal": summa["n"], "summa": _s(Decimal(summa["s"] or 0)), "visas": min(n, summa["n"]),
            "transaktioner": [_transaktion(t) for t in qs[:n]]}


def okategoriserade_grupperade(max_antal=100):
    """Okategoriserade transaktioner grupperade på text – snabbaste sättet att gå igenom dem."""
    rader = (Transaktion.objects.okategoriserade().values("text").annotate(n=Count("id"), summa=Sum("belopp"))
             .order_by("-n", "text"))
    return {"antal_transaktioner": Transaktion.objects.okategoriserade().count(),
            "texter": [{"text": r["text"], "antal": r["n"], "summa": _s(r["summa"])} for r in rader[:max_antal]]}


def utfall(ar=None, manad=None):
    """Budget och utfall per kategori för ett år (och en månad)."""
    ar = int(ar or dt.date.today().year)
    u = utfall_per_kategori_och_manad(ar)
    b = Budget.for_ar(ar)
    bud = b.per_kategori() if b else {}
    noll = [Decimal(0)] * 12
    rader = []
    for k in Kategori.objects.exclude(typ=Kategori.OVERFORING):
        uv, bv = u.get(k.pk, noll), bud.get(k.pk, noll)
        if not any(uv) and not any(bv):
            continue
        rad = {"kategori": _kat_text(k), "typ": k.typ, "utfall_ar": _s(sum(uv)), "budget_ar": _s(sum(bv))}
        if manad:
            rad |= {"utfall_manad": _s(uv[int(manad) - 1]), "budget_manad": _s(bv[int(manad) - 1])}
        else:
            rad["utfall_per_manad"] = [_s(x) for x in uv]
        rader.append(rad)
    ok_in, ok_ut = okategoriserat_per_manad(ar)
    return {"ar": ar, "manad": MANADSNAMN[int(manad) - 1] if manad else None, "budget": str(b) if b else None,
            "belopp": "Inkomster som plus, utgifter och sparande som plus när pengar går ut. Överföringar ingår inte.",
            "kategorier": rader, "okategoriserat_in": _s(sum(ok_in)), "okategoriserat_ut": _s(sum(ok_ut))}


def regler(sok=""):
    qs = Kategoriregel.objects.select_related("kategori", "konto", "tillgang")
    if sok:
        qs = qs.filter(Q(monster__icontains=sok) | Q(kategori__namn__icontains=sok) | Q(kategori__grupp__icontains=sok))
    return [{"id": r.pk, "monster": r.monster, "kategori": _kat_text(r.kategori),
             "galler": "utgifter" if r.endast_utgifter else "inkomster" if r.endast_inkomster else "alla",
             "konto": r.konto.namn if r.konto else None, "tillgang": r.tillgang.namn if r.tillgang else None,
             "prioritet": r.prioritet} for r in qs[:MAX_RADER]]


def budget(ar=None):
    ar = int(ar or dt.date.today().year)
    b = Budget.for_ar(ar)
    if not b:
        return {"ar": ar, "budget": None, "info": "Ingen budget för året. Skapa med spara_budget."}
    return {"ar": ar, "budget": str(b), "id": b.pk,
            "poster": [{"kategori": _kat_text(p.kategori), "per_manad": [str(v) for v in p.varden], "summa": str(p.summa)}
                       for p in b.poster.select_related("kategori").order_by("kategori__ordning", "kategori__grupp")]}


def tillgangar():
    idag = dt.date.today()
    return {
        "tillgangar": [{"id": t.pk, "namn": t.namn, "typ": t.get_typ_display(), "adress": t.adress or None,
                        "marknadsvarde": _s(t.varde_per(idag)), "agarandel": _s(t.agarandel),
                        "mitt_varde": _s(t.mitt_varde_per(idag)),
                        "senaste_vardering": (lambda v: {"datum": str(v.datum), "varde": str(v.varde), "kalla": v.kalla}
                                              if v else None)(t.senaste_vardering()),
                        "kopeskilling": _s(t.kopeskilling), "kopdatum": _s(t.kopdatum)}
                       for t in Tillgang.objects.all()],
        "lan": [{"id": l.pk, "namn": l.namn, "typ": l.get_typ_display(), "langivare": l.langivare,
                 "sakerhet": l.tillgang.namn if l.tillgang else None, "ranta": _s(l.ranta),
                 "bunden_till": _s(l.bunden_till), "skuld": _s(l.saldo_per(idag)),
                 "saldo_per": _s(l.senaste_saldo().datum if l.senaste_saldo() else None),
                 "amortering_per_manad": _s(l.amortering_per_manad)} for l in Lan.objects.select_related("tillgang")],
    }


# ------------------------------------------------------------------ skriva

@transaction.atomic
def satt_kategori(transaktion_ids, kategori, tillgang=None, anteckning=None):
    """Sätter kategori (och ev. tillgång/anteckning) på transaktioner. Markeras som manuellt kategoriserade."""
    ids = [int(i) for i in (transaktion_ids if isinstance(transaktion_ids, (list, tuple)) else [transaktion_ids])]
    if not ids:
        raise VerktygsFel("Ange minst ett transaktions-id.")
    if len(ids) > MAX_RADER:
        raise VerktygsFel(f"Högst {MAX_RADER} transaktioner per anrop.")
    k = None if str(kategori).lower() in ("", "ingen", "none") else _kategori(kategori)
    t_obj = _tillgang(tillgang)
    qs = Transaktion.objects.filter(pk__in=ids)
    saknas = set(ids) - set(qs.values_list("pk", flat=True))
    if saknas:
        raise VerktygsFel(f"Transaktionerna {sorted(saknas)} finns inte.")
    andra = {"kategori": k, "manuellt_kategoriserad": bool(k)}
    if t_obj:
        andra["tillgang"] = t_obj
    if anteckning is not None:
        andra["anteckning"] = str(anteckning)[:300]
    n = qs.update(**andra)
    return {"uppdaterade": n, "kategori": _kat_text(k), "tillgang": t_obj.namn if t_obj else None}


@transaction.atomic
def kategorisera_text(text, kategori, exakt=True, galler="alla", skapa_regel=True, tillgang=None):
    """Kategoriserar alla transaktioner med en viss text och skapar (valfritt) en regel för framtida importer."""
    k = _kategori(kategori)
    t_obj = _tillgang(tillgang)
    text = str(text).strip()
    if not text:
        raise VerktygsFel("Ange text.")
    monster = f'"{text.lower()}"' if exakt else text.lower()
    regel = Kategoriregel(monster=monster, kategori=k, tillgang=t_obj, endast_utgifter=galler == "utgifter",
                          endast_inkomster=galler == "inkomster")
    traff = [t for t in Transaktion.objects.sok(text.split()[0]) if regel.traffar(t.text, t.belopp, t.konto_id)]
    for t in traff:
        t.kategori, t.manuellt_kategoriserad = k, True
        if t_obj:
            t.tillgang = t_obj
        t.save(update_fields=["kategori", "manuellt_kategoriserad", "tillgang"])
    if skapa_regel:
        regel, _ = Kategoriregel.objects.update_or_create(
            monster=monster, endast_utgifter=regel.endast_utgifter, endast_inkomster=regel.endast_inkomster,
            konto=None, defaults={"kategori": k, "tillgang": t_obj})
    return {"kategoriserade": len(traff), "kategori": _kat_text(k),
            "regel": {"id": regel.pk, "monster": regel.monster} if skapa_regel else None}


def ny_kategori(grupp, namn, typ="utgift"):
    typer = {"inkomst": Kategori.INKOMST, "utgift": Kategori.UTGIFT, "sparande": Kategori.SPARANDE,
             "overforing": Kategori.OVERFORING, "överföring": Kategori.OVERFORING}
    if str(typ).lower() not in typer:
        raise VerktygsFel("typ ska vara inkomst, utgift, sparande eller overforing.")
    k, skapad = Kategori.objects.get_or_create(grupp=str(grupp).strip(), namn=str(namn).strip(),
                                               defaults={"typ": typer[str(typ).lower()], "ordning": 900})
    return {"id": k.pk, "kategori": _kat_text(k), "typ": k.typ, "skapad": skapad}


def ny_regel(monster, kategori, galler="alla", konto=None, tillgang=None, prioritet=0, kor_nu=True):
    k = _kategori(kategori)
    if galler not in ("alla", "utgifter", "inkomster"):
        raise VerktygsFel("galler ska vara alla, utgifter eller inkomster.")
    monster = str(monster).strip()
    if not monster:
        raise VerktygsFel("Ange mönster.")
    r, skapad = Kategoriregel.objects.update_or_create(
        monster=monster, endast_utgifter=galler == "utgifter", endast_inkomster=galler == "inkomster",
        konto=_konto(konto) if konto else None,
        defaults={"kategori": k, "tillgang": _tillgang(tillgang), "prioritet": int(prioritet or 0)})
    n = kategorisera() if kor_nu else 0
    return {"id": r.pk, "monster": r.monster, "kategori": _kat_text(k), "skapad": skapad,
            "okategoriserade_som_fick_kategori": n}


def ta_bort_regel(regel_id):
    r = Kategoriregel.objects.filter(pk=int(regel_id)).first()
    if not r:
        raise VerktygsFel(f"Regel {regel_id} finns inte.")
    text = str(r)
    r.delete()
    return {"borttagen": text, "info": "Transaktioner som redan fått kategori påverkas inte."}


def kor_regler(skriv_over=False):
    n = kategorisera(skriv_over=bool(skriv_over))
    return {"andrade": n, "okategoriserade_kvar": Transaktion.objects.okategoriserade().count(),
            "info": "Manuellt kategoriserade transaktioner rörs aldrig."}


def importera_fil(sokvag, konto):
    """Importerar ett kontoutdrag (CSV/Excel) från en fil på datorn till ett konto."""
    p = Path(str(sokvag)).expanduser()
    if not p.is_file():
        raise VerktygsFel(f"Filen {p} finns inte.")
    if p.suffix.lower() not in (".csv", ".txt", ".xlsx", ".xls", ".xlsm"):
        raise VerktygsFel("Bara CSV- och Excel-filer kan importeras.")
    k = _konto(konto)
    try:
        imp = importera(k, p.read_bytes(), p.name)
    except ImportFel as e:
        raise VerktygsFel(str(e))
    varning = None
    if k.importformat != Konto.AUTO and imp.format != k.importformat:
        varning = f"Filen ser ut att vara formatet '{imp.format}' men kontot är inställt på '{k.importformat}'."
    return {"konto": k.namn, "format": imp.format, "nya": imp.antal_nya, "fanns_redan": imp.antal_dubbletter,
            "period": f"{imp.forsta_datum} – {imp.sista_datum}", "tecken_vant": imp.tecken_vant,
            "okategoriserade_fran_filen": imp.transaktioner.filter(kategori__isnull=True).count(),
            "import_id": imp.pk, "varning": varning}


def satt_kontosaldo(konto, datum, saldo):
    """Avstämt saldo för ett konto (kreditkortsskuld som minus)."""
    k = _konto(konto)
    s, _ = Kontosaldo.objects.update_or_create(konto=k, datum=_datum(datum),
                                               defaults={"saldo": _belopp(saldo, "saldo"), "kalla": "Claude"})
    return {"konto": k.namn, "datum": str(s.datum), "saldo": str(s.saldo), "saldo_i_dag": str(k.saldo_per())}


@transaction.atomic
def spara_budget(ar, poster, namn="Budget", ersatt=False):
    """poster: [{"kategori": ..., "per_manad": [12 belopp]} eller {"kategori": ..., "ar": belopp}]."""
    ar = int(ar)
    b = Budget.for_ar(ar) or Budget.objects.create(ar=ar, namn=namn)
    if ersatt:
        b.poster.all().delete()
    sparade = []
    for p in poster or []:
        k = _kategori(p.get("kategori"))
        if k.typ == Kategori.OVERFORING:
            raise VerktygsFel(f"{_kat_text(k)} är en överföring och budgeteras inte.")
        if p.get("per_manad") is not None:
            varden = [_belopp(v, "per_manad") for v in p["per_manad"]]
            if len(varden) != 12:
                raise VerktygsFel("per_manad ska ha 12 belopp (jan–dec).")
        elif p.get("ar") is not None:
            tot = _belopp(p["ar"], "ar").quantize(Decimal(1))
            per = (tot / 12).quantize(Decimal(1), rounding="ROUND_FLOOR")
            varden = [per] * 12
            varden[11] += tot - per * 12
        else:
            raise VerktygsFel("Ange per_manad eller ar för varje post.")
        post, _ = Budgetpost.objects.get_or_create(budget=b, kategori=k)
        post.varden = [abs(v) for v in varden]
        post.save()
        sparade.append({"kategori": _kat_text(k), "summa": str(post.summa)})
    return {"budget": str(b), "id": b.pk, "sparade": sparade, "webb": f"{WEBB}/budget/{b.pk}/"}


def ny_tillgang(namn, typ, kopdatum="", kopeskilling=None, adress="", agarandel=100, beskrivning=""):
    typer = dict((k, k) for k, _ in Tillgang.TYPER) | {v.lower(): k for k, v in Tillgang.TYPER}
    if str(typ).lower() not in typer:
        raise VerktygsFel(f"typ ska vara en av: {', '.join(k for k, _ in Tillgang.TYPER)}")
    t = Tillgang.objects.create(namn=namn, typ=typer[str(typ).lower()], adress=adress, beskrivning=beskrivning,
                                kopdatum=_datum(kopdatum) if kopdatum else None,
                                kopeskilling=_belopp(kopeskilling).quantize(Decimal(1)) if kopeskilling else None,
                                agarandel=_belopp(agarandel))
    return {"id": t.pk, "namn": t.namn, "typ": t.get_typ_display()}


def ny_vardering(tillgang, datum, varde, kalla=""):
    t = _tillgang(tillgang)
    if not t:
        raise VerktygsFel("Ange tillgång.")
    v = Vardering.objects.create(tillgang=t, datum=_datum(datum), varde=_belopp(varde).quantize(Decimal(1)),
                                 kalla=kalla or "Claude")
    return {"tillgang": t.namn, "datum": str(v.datum), "varde": str(v.varde), "mitt_varde": str(t.mitt_varde_per())}


def nytt_lan(namn, skuld, typ="bolan", langivare="", tillgang=None, ranta=None, bunden_till="",
             amortering_per_manad=None, datum=""):
    if typ not in dict(Lan.TYPER):
        raise VerktygsFel(f"typ ska vara en av: {', '.join(dict(Lan.TYPER))}")
    l = Lan.objects.create(namn=namn, typ=typ, langivare=langivare, tillgang=_tillgang(tillgang),
                           ranta=_belopp(ranta) if ranta not in (None, "") else None,
                           bunden_till=_datum(bunden_till) if bunden_till else None,
                           amortering_per_manad=_belopp(amortering_per_manad).quantize(Decimal(1))
                           if amortering_per_manad not in (None, "") else None)
    Lanesaldo.objects.create(lan=l, datum=_datum(datum) if datum else dt.date.today(),
                             saldo=_belopp(skuld).quantize(Decimal(1)), ranta=l.ranta)
    return {"id": l.pk, "namn": l.namn, "skuld": str(l.saldo_per())}


def nytt_lanesaldo(lan, datum, skuld, ranta=None):
    l = _lan(lan)
    r = _belopp(ranta) if ranta not in (None, "") else None
    s = Lanesaldo.objects.create(lan=l, datum=_datum(datum), saldo=_belopp(skuld).quantize(Decimal(1)), ranta=r)
    if r is not None and s == l.senaste_saldo():
        l.ranta = r
        l.save(update_fields=["ranta"])
    return {"lan": l.namn, "datum": str(s.datum), "skuld": str(s.saldo), "ranta": _s(l.ranta)}
