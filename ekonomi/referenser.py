"""Jämförelse av hushållets utgifter mot referenser: Konsumentverket, SCB och några andra.

Referensvärdena är inskrivna här och behöver uppdateras när nya siffror publiceras (Konsumentverket i
mitten av november varje år). Faktiska utgifter räknas som snitt per månad för de senaste tolv hela
månaderna; budgeten är årets budget delad med tolv.
"""

import datetime as dt
from decimal import Decimal

from budget.models import Budget

from .models import Hushallsmedlem, Kategori, Tjanstebil, utfall_per_kategori_och_manad

KV_AR = 2026
# Konsumentverkets åldersgrupper 2026: (från, till) år
KV_ALDRAR = [(0, 0), (1, 3), (4, 6), (7, 10), (11, 14), (15, 17), (18, 24), (25, 50), (51, 70), (71, 200)]
KV_MAT = [1030, 1100, 1710, 2130, 2650, 3050, 2840, 2730, 2490, 2450]          # all mat lagas hemma
KV_KLADER = [1070, 1050, 1160, 1130, 1000, 950, 870, 820, 790, 720]
KV_FRITID = [120, 240, 420, 450, 410, 520, 630, 600, 590, 560]
KV_MOBIL = [0, 0, 0, 80, 80, 130, 130, 130, 110, 110]                        # mobiltelefon från 8 år
KV_HYGIEN = [510, 660, 170, 180, 350, 560, 570, 590, 580, 550]
KV_BARNFORSAKRING = [230, 230, 230, 230, 230, 230, 0, 0, 0, 0]
KV_BARNUTRUSTNING = [990, 550, 20, 20, 0, 0, 0, 0, 0, 0]
# Hushållsgemensamma kostnader för 1–7 personer
KV_GEMENSAMT = {
    "forbrukning": [200, 300, 460, 560, 690, 790, 890],
    "hemutrustning": [920, 1030, 1310, 1560, 1790, 1950, 2060],
    "internet_mobil": [1000, 1230, 1460, 1690, 1920, 2150, 2380],   # minskas med 229 kr om barn under 8 år
    "medier": [640, 690, 720, 720, 720, 720, 840],
    "el": [400, 530, 700, 870, 1010, 1150, 1280],
    "vatten": [220, 440, 650, 880, 1080, 1310, 1530],
    "hemforsakring": [150, 170, 200, 250, 300, 340, 350],
}

# SCB, Hushållens utgifter 2021: andel av hushållens totala utgifter (procent)
SCB_AR = 2021
SCB_ANDELAR = [
    ("Livsmedel", Decimal("13.6"), ["Mat – Livsmedel"]),
    ("Restaurang och hotell", Decimal("5.2"), ["Mat – Restaurang och café"]),
    ("Kläder och skor", Decimal("4.0"), ["Hushåll – Kläder och skor"]),
    ("Boende", Decimal("21.9"), ["grupp:Boende", "-Boende – Bredband, TV och telefon"]),
    ("Transport", Decimal("14.9"), ["grupp:Transport"]),
    ("Hälsovård", Decimal("4.2"), ["Hushåll – Hälsa och apotek"]),
    ("Datorer, telefoner, internet", Decimal("3.9"), ["Boende – Bredband, TV och telefon"]),
    ("Fritid, sport, kultur (inkl. resor)", Decimal("8.4"), ["grupp:Fritid", "-Fritid – Gåvor och välgörenhet"]),
]
# Räknas inte med i hushållets totala konsumtion vid jämförelse av andelar
EJ_KONSUMTION = {"Finansiellt – Skatt", "Övrigt – Utlägg för företaget", "Övrigt – Swish privatpersoner",
                 "Övrigt – Att utreda"}

KALLOR = [
    ("Konsumentverket – Hushållskostnader 2026",
     "https://stpubshop.blob.core.windows.net/publikationer/kostnadsberakningar-hushallskostnader-2026-sv-kov_tga_32d.pdf"),
    ("SCB – Hushållens utgifter 2021",
     "https://www.scb.se/hitta-statistik/statistik-efter-amne/hushallens-ekonomi/hushallens-utgifter/"
     "hushallens-utgifter-hut/pong/statistiknyhet/hushallens-utgifter-2021/"),
    ("Swedbank/Sparbankerna – bilkostnader och boendeparkering", "https://mb.cision.com/Public/67/3592813/ad12fc36e8f5dda2.pdf"),
    ("minbilkoll.se – ägarkostnader bil", "https://minbilkoll.se/guide/agarkostnader"),
    ("SL-priser 2026 (hurbra.se)", "https://hurbra.se/halva-priset-manadskort-2026/"),
]
TRANSPORT_SCB = "Transport"


def _grupp(alder):
    for i, (fran, till) in enumerate(KV_ALDRAR):
        if fran <= alder <= till:
            return i
    return len(KV_ALDRAR) - 1


def _gemensamt(post, antal):
    rad = KV_GEMENSAMT[post]
    return rad[min(max(antal, 1), len(rad)) - 1] + max(0, antal - len(rad)) * (rad[-1] - rad[-2])


def konsumentverket(aldrar):
    """Referensvärden per månad för ett hushåll med personer i de givna åldrarna."""
    g = [_grupp(a) for a in aldrar]
    n = len(aldrar)

    def summa(tabell, villkor=lambda a: True):
        return sum(tabell[i] for i, a in zip(g, aldrar) if villkor(a))

    internet = _gemensamt("internet_mobil", n) - (229 if any(a < 8 for a in aldrar) else 0)
    return {
        "livsmedel": summa(KV_MAT),
        "klader": summa(KV_KLADER),
        "fritid": summa(KV_FRITID) + summa(KV_BARNUTRUSTNING),
        "hygien": summa(KV_HYGIEN),
        "medier": summa(KV_MOBIL, lambda a: a >= 8) + internet + _gemensamt("medier", n),
        "hem": _gemensamt("forbrukning", n) + _gemensamt("hemutrustning", n),
        "forsakring": _gemensamt("hemforsakring", n) + summa(KV_BARNFORSAKRING),
        "el": _gemensamt("el", n),
        "vatten": _gemensamt("vatten", n),
    }


KV_RADER = [
    ("livsmedel", "Livsmedel (all mat lagas hemma)", ["Mat – Livsmedel"], ""),
    ("klader", "Kläder och skor", ["Hushåll – Kläder och skor"], ""),
    ("fritid", "Fritid och lek", ["Fritid – Nöje och fritid", "Fritid – Träning och sport", "Hushåll – Barn"],
     "Nöje, träning och barn. Resor och båt ingår inte."),
    ("hygien", "Personlig hygien", ["Hushåll – Personlig vård", "Hushåll – Hälsa och apotek"], ""),
    ("medier", "Mobil, internet och medier", ["Boende – Bredband, TV och telefon", "Fritid – Prenumerationer och appar"], ""),
    ("hem", "Förbrukningsvaror och hemutrustning", ["Hushåll – Hem och inredning"], ""),
    ("forsakring", "Hem- och barnförsäkring", ["Finansiellt – Övriga försäkringar", "Boende – Försäkring boende"], ""),
    ("el", "Hushållsel", ["Boende – El"], "Konsumentverket räknar på lägenhet – uppvärmning ingår inte."),
    ("vatten", "Vatten och avlopp", ["Boende – Värme, vatten och sophämtning"], "Hos dig ingår även värme och sophämtning."),
]


def bedomning(varde, referens):
    """(text, css-klass, kvot) för hur ett belopp förhåller sig till referensen."""
    if not referens:
        return "", "", None
    kvot = Decimal(varde) / Decimal(referens)
    if kvot < Decimal("0.9"):
        return "Under", "under", kvot
    if kvot <= Decimal("1.2"):
        return "I nivå", "niva", kvot
    if kvot <= Decimal("1.6"):
        return "Något högt", "nagot", kvot
    return "Högt", "hogt", kvot


def _manader(idag, n=12):
    """De n senaste hela månaderna som (år, månad), äldst först."""
    ar, m, res = idag.year, idag.month, []
    for _ in range(n):
        ar, m = (ar - 1, 12) if m == 1 else (ar, m - 1)
        res.append((ar, m))
    return list(reversed(res))


def jamforelse(idag=None):
    idag = idag or dt.date.today()
    manader = _manader(idag)
    utfall = {ar: utfall_per_kategori_och_manad(ar) for ar in {a for a, _ in manader}}
    budget = Budget.for_ar(idag.year)
    bud = budget.per_kategori() if budget else {}
    kategorier = list(Kategori.objects.all())
    namn = {f"{k.grupp} – {k.namn}": k for k in kategorier}

    def faktiskt(k):
        return sum((utfall[a].get(k.pk, [0] * 12)[m - 1] for a, m in manader), Decimal(0)) / 12

    def budget_man(k):
        return sum(bud.get(k.pk, [0] * 12), Decimal(0)) / 12

    def valda(urval):
        res = set()
        for u in urval:
            if u.startswith("grupp:"):
                res |= {k for k in kategorier if k.grupp == u[6:]}
            elif u.startswith("-"):
                res.discard(namn.get(u[1:]))
            elif u in namn:
                res.add(namn[u])
        res.discard(None)
        return res

    def summor(urval):
        ks = valda(urval)
        return sum((faktiskt(k) for k in ks), Decimal(0)), sum((budget_man(k) for k in ks), Decimal(0))

    bilar = list(Tjanstebil.objects.filter(aktiv=True))
    tjanstebil = sum((b.kostnad for b in bilar), Decimal(0))

    medlemmar = list(Hushallsmedlem.objects.all())
    aldrar = [m.alder(idag.year) for m in medlemmar]

    kv_rader = []
    if medlemmar:
        ref = konsumentverket(aldrar)
        for nyckel, rubrik, urval, kommentar in KV_RADER:
            f, b = summor(urval)
            text, klass, kvot = bedomning(f, ref[nyckel])
            kv_rader.append({"rubrik": rubrik, "referens": ref[nyckel], "budget": b, "faktiskt": f,
                             "kvot": kvot, "bedomning": text, "klass": klass, "kommentar": kommentar,
                             "kategorier": ", ".join(u.split(" – ")[-1] for u in urval)})
        tot_ref = sum(r["referens"] for r in kv_rader)
        tot_f = sum((r["faktiskt"] for r in kv_rader), Decimal(0))
        text, klass, kvot = bedomning(tot_f, tot_ref)
        kv_summa = {"referens": tot_ref, "budget": sum((r["budget"] for r in kv_rader), Decimal(0)),
                    "faktiskt": tot_f, "kvot": kvot, "bedomning": text, "klass": klass}
    else:
        kv_summa = None

    konsumtion = [k for k in kategorier if k.typ == Kategori.UTGIFT and f"{k.grupp} – {k.namn}" not in EJ_KONSUMTION]
    tot_f = sum((faktiskt(k) for k in konsumtion), Decimal(0)) + tjanstebil
    tot_b = sum((budget_man(k) for k in konsumtion), Decimal(0)) + tjanstebil
    scb_rader = []
    for rubrik, andel, urval in SCB_ANDELAR:
        f, b = summor(urval)
        if rubrik == TRANSPORT_SCB:
            f, b = f + tjanstebil, b + tjanstebil
        af = f / tot_f * 100 if tot_f else Decimal(0)
        ab = b / tot_b * 100 if tot_b else Decimal(0)
        text, klass, kvot = bedomning(af, andel)
        scb_rader.append({"rubrik": rubrik, "referens": andel, "faktiskt": f, "budget": b, "andel": af,
                          "andel_budget": ab, "kvot": kvot, "bedomning": text, "klass": klass})

    vuxna = sum(1 for a in aldrar if a >= 20)
    ungdomar = sum(1 for a in aldrar if 7 <= a < 20)
    ovriga = []

    def ovrig(rubrik, urval, referens, reftext, tillagg=Decimal(0)):
        f, b = summor(urval)
        f, b = f + tillagg, b + tillagg
        text, klass, kvot = bedomning(f, referens)
        ovriga.append({"rubrik": rubrik, "faktiskt": f, "budget": b, "referens": referens, "reftext": reftext,
                       "kvot": kvot, "bedomning": text, "klass": klass})

    ovrig("Parkering och vägavgifter", ["Transport – Parkering och vägavgifter"], 750,
          "Boendeparkering i Stockholms stad, snitt (Swedbank 2022)")
    if medlemmar:
        ovrig("Kollektivtrafik och taxi", ["Transport – Kollektivtrafik och taxi"], vuxna * 1060 + ungdomar * 650,
              f"SL 30 dagar för alla i hushållet: {vuxna} × 1 060 + {ungdomar} × 650 kr")
    ovrig("Bil och drivmedel", ["Transport – Bil (försäkring, skatt, service)", "Transport – Drivmedel och laddning"],
          5000, "Genomsnittlig bil inkl. värdeminskning – värdeminskningen syns inte bland dina utgifter"
          + (f". Inkl. tjänstebil {tjanstebil:,.0f} kr/mån (löneavdrag och skatt på förmånsvärdet)".replace(",", " ") if bilar else ""),
          tjanstebil)

    lon_f, lon_b = summor(["Inkomster – Lön"])
    spar = [k for k in kategorier if k.typ == Kategori.SPARANDE]
    spar_f = sum((faktiskt(k) for k in spar), Decimal(0))
    spar_b = sum((budget_man(k) for k in spar), Decimal(0))
    sparande = {"faktiskt": spar_f, "budget": spar_b, "lon": lon_f,
                "andel": spar_f / lon_f * 100 if lon_f else None,
                "andel_budget": spar_b / lon_b * 100 if lon_b else None}
    sparande["ok"] = sparande["andel"] is not None and sparande["andel"] >= 10

    return {
        "period": f"{manader[0][1]:02d}/{manader[0][0]} – {manader[-1][1]:02d}/{manader[-1][0]}",
        "budget": budget, "medlemmar": medlemmar, "aldrar": aldrar, "kv_ar": KV_AR, "scb_ar": SCB_AR,
        "kv_rader": kv_rader, "kv_summa": kv_summa, "scb_rader": scb_rader,
        "konsumtion_faktiskt": tot_f, "konsumtion_budget": tot_b, "ovriga": ovriga, "sparande": sparande,
        "kallor": KALLOR, "tjanstebilar": bilar, "tjanstebil": tjanstebil,
    }
