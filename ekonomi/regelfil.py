"""Import och export av kategoriseringsregler som Excel/CSV.

Kolumner (rubrikraden avgör ordningen): Mönster, Grupp, Kategori, Typ, Gäller, Prioritet, Kommentar.
- Typ: Inkomst, Utgift, Sparande eller Överföring – används bara när kategorin inte finns och skapas.
- Gäller: alla, utgifter (minusbelopp) eller inkomster (plusbelopp).
Finns redan en regel med samma mönster och villkor uppdateras den, annars skapas en ny.
"""

import io

from django.db import transaction

from .importering import ImportFel, _norm, _str, las_tabeller
from .models import Kategori, Kategoriregel

TYPER = {"inkomst": Kategori.INKOMST, "utgift": Kategori.UTGIFT, "sparande": Kategori.SPARANDE,
         "sparande/amortering": Kategori.SPARANDE, "överföring": Kategori.OVERFORING, "overforing": Kategori.OVERFORING}
KOLUMNER = ["Mönster", "Grupp", "Kategori", "Typ", "Gäller", "Prioritet", "Kommentar"]


def _galler(v):
    v = _str(v).lower()
    if v.startswith("utg") or v.startswith("minus"):
        return True, False
    if v.startswith("ink") or v.startswith("plus") or v.startswith("inb"):
        return False, True
    return False, False


@transaction.atomic
def importera_regler(data: bytes, filnamn: str):
    """Returnerar (nya regler, uppdaterade regler, nya kategorier)."""
    for tabell in las_tabeller(data, filnamn):
        for start, rad in enumerate(tabell[:20]):
            rubriker = [_norm(c) for c in rad]
            if "mönster" in rubriker and "kategori" in rubriker:
                return _importera(tabell[start + 1:], rubriker)
    raise ImportFel("Hittade ingen rubrikrad med Mönster och Kategori.")


def _importera(rader, rubriker):
    def kol(namn):
        return rubriker.index(namn) if namn in rubriker else None

    i = {k: kol(k) for k in ("mönster", "grupp", "kategori", "typ", "gäller", "prioritet")}
    nya = uppdaterade = nya_kat = 0
    for r in rader:
        def v(k, r=r):
            return _str(r[i[k]]) if i[k] is not None and i[k] < len(r) else ""

        # mönstret läses rått: citattecken betyder exakt text och får inte tas bort
        ra = r[i["mönster"]] if i["mönster"] is not None and i["mönster"] < len(r) else None
        monster, namn = ("" if ra is None else str(ra).strip()), v("kategori")
        if not monster or not namn:
            continue
        grupp = v("grupp")
        kat = Kategori.objects.filter(namn__iexact=namn, **({"grupp__iexact": grupp} if grupp else {})).first()
        if not kat:
            typ = TYPER.get(v("typ").lower(), Kategori.UTGIFT)
            kat = Kategori.objects.create(namn=namn, grupp=grupp or "Övrigt", typ=typ, ordning=900)
            nya_kat += 1
        utg, ink = _galler(v("gäller"))
        try:
            prio = int(float(v("prioritet") or 10))
        except ValueError:
            prio = 10
        regel, skapad = Kategoriregel.objects.update_or_create(
            monster=monster, endast_utgifter=utg, endast_inkomster=ink, konto=None,
            defaults={"kategori": kat, "prioritet": prio})
        nya += skapad
        uppdaterade += not skapad
    return nya, uppdaterade, nya_kat


def exportera_regler() -> bytes:
    import openpyxl

    bok = openpyxl.Workbook()
    blad = bok.active
    blad.title = "Regler"
    blad.append(KOLUMNER)
    for r in Kategoriregel.objects.select_related("kategori").order_by("kategori__grupp", "kategori__namn", "monster"):
        galler = "utgifter" if r.endast_utgifter else "inkomster" if r.endast_inkomster else "alla"
        monster = f'"{r.monster[1:]}"' if r.monster.startswith("=") else r.monster  # = blir formel i Excel
        blad.append([monster, r.kategori.grupp, r.kategori.namn, r.kategori.get_typ_display(), galler, r.prioritet, ""])
    for kolumn, bredd in zip("ABCDEFG", (28, 16, 30, 14, 10, 9, 40)):
        blad.column_dimensions[kolumn].width = bredd
    ut = io.BytesIO()
    bok.save(ut)
    return ut.getvalue()
