import datetime as dt
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

from django import forms
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from ekonomi import diagram
from ekonomi.models import Kategori, okategoriserat_per_manad, utfall_per_kategori_och_manad

from .models import MANADER, MANADSNAMN, Budget, Budgetpost

NOLL = [Decimal(0)] * 12
SEKTIONER = [(Kategori.INKOMST, "Inkomster"), (Kategori.UTGIFT, "Utgifter"), (Kategori.SPARANDE, "Sparande och amortering")]


class NyBudgetForm(forms.ModelForm):
    UTGA = [("tom", "Tom budget"), ("utfall", "Förra årets utfall"), ("budget", "Kopiera en befintlig budget")]
    utga_fran = forms.ChoiceField(label="Utgå från", choices=UTGA, initial="utfall")
    kopiera = forms.ModelChoiceField(Budget.objects.all(), required=False, label="Budget att kopiera")
    okning = forms.DecimalField(label="Justera alla belopp med (%)", initial=0, required=False,
                                help_text="T.ex. 3 för att räkna upp med inflationen")

    class Meta:
        model = Budget
        fields = ["ar", "namn", "huvudbudget", "anteckning"]
        widgets = {"anteckning": forms.Textarea(attrs={"rows": 2})}


def lista(request):
    return render(request, "budget/lista.html", {"budgetar": Budget.objects.all()})


def ny(request):
    idag = dt.date.today()
    form = NyBudgetForm(request.POST or None, initial={"ar": idag.year + (idag.month >= 10), "namn": "Budget"})
    if request.method == "POST" and form.is_valid():
        b = form.save()
        faktor = 1 + Decimal(form.cleaned_data.get("okning") or 0) / 100
        kalla = {}
        if form.cleaned_data["utga_fran"] == "utfall":
            kalla = utfall_per_kategori_och_manad(b.ar - 1)
        elif form.cleaned_data["utga_fran"] == "budget" and form.cleaned_data["kopiera"]:
            kalla = form.cleaned_data["kopiera"].per_kategori()
        for kat_id, varden in kalla.items():
            if Kategori.objects.filter(pk=kat_id).exclude(typ=Kategori.OVERFORING).exists():
                p = Budgetpost(budget=b, kategori_id=kat_id)
                p.varden = [max(Decimal(0), (Decimal(v) * faktor).quantize(Decimal(1))) for v in varden]
                p.save()
        messages.success(request, "Budgeten skapades. Justera beloppen och spara.")
        return redirect("budget_redigera", pk=b.pk)
    return render(request, "form.html", {"form": form, "rubrik": "Ny budget", "tillbaka": "budgetar"})


def _belopp(v):
    try:
        return Decimal((v or "0").replace(" ", "").replace("\xa0", "").replace(",", ".") or 0).quantize(Decimal(1))
    except InvalidOperation:
        return Decimal(0)


def redigera(request, pk):
    b = get_object_or_404(Budget, pk=pk)
    kategorier = list(Kategori.objects.filter(aktiv=True).exclude(typ=Kategori.OVERFORING))
    poster = {p.kategori_id: p for p in b.poster.all()}
    if request.method == "POST":
        b.namn = request.POST.get("namn") or b.namn
        b.save()
        for k in kategorier:
            varden = [_belopp(request.POST.get(f"k{k.pk}_m{m}")) for m in MANADER]
            p = poster.get(k.pk)
            if not any(varden):
                if p:
                    p.delete()
                continue
            p = p or Budgetpost(budget=b, kategori=k)
            p.varden = varden
            p.save()
        messages.success(request, "Budgeten sparades.")
        return redirect("budget_uppfoljning", pk=b.pk)
    sektioner = []
    for typ, rubrik in SEKTIONER:
        rader = [(k, poster[k.pk].varden if k.pk in poster else NOLL) for k in kategorier if k.typ == typ]
        sektioner.append((rubrik, rader))
    return render(request, "budget/redigera.html", {"b": b, "sektioner": sektioner, "manader": MANADSNAMN})


def radera(request, pk):
    b = get_object_or_404(Budget, pk=pk)
    if request.method == "POST":
        b.delete()
        messages.success(request, "Budgeten raderades.")
        return redirect("budgetar")
    return render(request, "bekrafta.html", {"text": f"Radera {b}?", "tillbaka": b.get_absolute_url()})


def uppfoljning(request, pk=None):
    idag = dt.date.today()
    if pk:
        b = get_object_or_404(Budget, pk=pk)
        ar = b.ar
    else:
        ar = int(request.GET.get("ar") or idag.year)
        b = Budget.for_ar(ar)
    manad = int(request.GET.get("manad") or (idag.month if ar == idag.year else 12))
    bud = b.per_kategori() if b else {}
    utfall = utfall_per_kategori_och_manad(ar)
    # Snitt per månad räknas på hela månader: innevarande år t.o.m. förra månaden, tidigare år alla tolv
    snitt_n = 12 if ar < idag.year else (idag.month - 1 if ar == idag.year else 0)
    # Kategorier som användaren klickat ur: visas men räknas inte i summorna. Sparas i sessionen.
    if "exkl" in request.GET:
        exkl = sorted({int(x) for x in request.GET["exkl"].split(",") if x.strip().isdigit()})
        request.session["budget_exkl"] = exkl
    else:
        exkl = request.session.get("budget_exkl", [])
    exkl = set(exkl)
    # Budgetkolumnen i månadsvyn: hela året eller per månad (årsbudget / 12). Sparas i sessionen.
    if request.GET.get("budget") in ("ar", "manad"):
        request.session["budget_per"] = request.GET["budget"]
    budget_per = request.session.get("budget_per", "ar")

    def rad(namn, bv, uv, typ, url=""):
        bm, um = bv[manad - 1], uv[manad - 1]
        bh, uh = sum(bv[:manad], Decimal(0)), sum(uv[:manad], Decimal(0))
        # positiv avvikelse = bättre än budget (mer inkomst, mindre utgift)
        tecken = 1 if typ == Kategori.INKOMST else -1
        return {"namn": namn, "url": url, "b_man": bm, "u_man": um, "d_man": (um - bm) * tecken + 0,
                "b_hit": bh, "u_hit": uh, "d_hit": (uh - bh) * tecken + 0, "b_ar": sum(bv, Decimal(0)),
                "b_visa": (sum(bv, Decimal(0)) / 12).quantize(Decimal(1)) if budget_per == "manad" else sum(bv, Decimal(0)),
                "manader": uv, "budget_manader": bv,
                "snitt": (sum(uv[:snitt_n], Decimal(0)) / snitt_n).quantize(Decimal(1)) if snitt_n else None}

    sektioner, summor = [], {}
    for typ, rubrik in SEKTIONER:
        grupper = {}
        for k in Kategori.objects.filter(typ=typ):
            bv, uv = bud.get(k.pk, NOLL), utfall.get(k.pk, NOLL)
            if not any(bv) and not any(uv):
                continue
            r = rad(k.namn, bv, uv, typ, f"/transaktioner/?kategori={k.pk}&ar={ar}")
            r["id"], r["exkluderad"] = k.pk, k.pk in exkl
            grupper.setdefault(k.grupp, []).append(r)
        gruppsummor = []
        for g, rader in grupper.items():
            med = [r for r in rader if not r["exkluderad"]]
            bv = [sum((r["budget_manader"][i] for r in med), Decimal(0)) for i in range(12)]
            uv = [sum((r["manader"][i] for r in med), Decimal(0)) for i in range(12)]
            gruppsummor.append((rad(g, bv, uv, typ, f"/transaktioner/?grupp={quote(g)}&ar={ar}"), rader))
        bv = [sum(gs[0]["budget_manader"][i] for gs in gruppsummor) for i in range(12)] if gruppsummor else NOLL
        uv = [sum(gs[0]["manader"][i] for gs in gruppsummor) for i in range(12)] if gruppsummor else NOLL
        summor[typ] = (bv, uv)
        sektioner.append({"rubrik": rubrik, "grupper": gruppsummor, "summa": rad(f"Summa {rubrik.lower()}", bv, uv, typ)})

    bi, ui = summor[Kategori.INKOMST]
    bu, uu = summor[Kategori.UTGIFT]
    bs, us = summor[Kategori.SPARANDE]
    over = rad("Kvar efter utgifter och sparande", [bi[i] - bu[i] - bs[i] for i in range(12)],
               [ui[i] - uu[i] - us[i] for i in range(12)], Kategori.INKOMST)
    ok_in, ok_ut = okategoriserat_per_manad(ar)
    return render(request, "budget/uppfoljning.html", {
        "b": b, "ar": ar, "manad": manad, "manadsnamn": MANADSNAMN[manad - 1], "manader": list(enumerate(MANADSNAMN, 1)),
        "sektioner": sektioner, "over": over, "ok_in": ok_in, "ok_ut": ok_ut,
        "okategoriserat": sum(ok_in, Decimal(0)) + sum(ok_ut, Decimal(0)),
        "visa_alla": request.GET.get("visa") != "manad", "budgetar": Budget.objects.filter(ar=ar),
        "snitt_n": snitt_n, "exkl": exkl, "budget_per": budget_per, "snitt_till": MANADSNAMN[snitt_n - 1] if snitt_n else "",
        "ar_lista": range(idag.year + 1, idag.year - 6, -1),
        "diagram": diagram.budgetstapel(MANADSNAMN, uu, bu),
    })
