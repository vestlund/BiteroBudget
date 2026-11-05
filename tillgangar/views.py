import datetime as dt
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render

from budget.models import MANADSNAMN
from ekonomi import diagram
from ekonomi.forms import Datum

from .berakning import formogenhet_per, historik
from .models import Forbattring, Lan, Lanesaldo, Tillgang, Vardering


class TillgangForm(forms.ModelForm):
    class Meta:
        model = Tillgang
        fields = ["namn", "typ", "beskrivning", "adress", "beteckning", "forening", "boarea", "taxeringsvarde",
                  "taxeringsar", "kopdatum", "kopeskilling", "kopkostnader", "agarandel", "salt_datum", "ordning",
                  "aktiv"]
        widgets = {"kopdatum": Datum(), "salt_datum": Datum(), "beskrivning": forms.Textarea(attrs={"rows": 2})}


class VarderingForm(forms.ModelForm):
    class Meta:
        model = Vardering
        fields = ["datum", "varde", "kalla"]
        widgets = {"datum": Datum()}


class ForbattringForm(forms.ModelForm):
    class Meta:
        model = Forbattring
        fields = ["datum", "beskrivning", "belopp"]
        widgets = {"datum": Datum()}


class LanForm(forms.ModelForm):
    startsaldo = forms.DecimalField(label="Nuvarande skuld", required=False, decimal_places=0,
                                    help_text="Sparas som lånets saldo i dag")

    class Meta:
        model = Lan
        fields = ["namn", "typ", "langivare", "lanenummer", "tillgang", "ranta", "bunden_till",
                  "amortering_per_manad", "agarandel", "aktiv"]
        widgets = {"bunden_till": Datum()}

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        if self.instance.pk:
            del self.fields["startsaldo"]


class LanesaldoForm(forms.ModelForm):
    class Meta:
        model = Lanesaldo
        fields = ["datum", "saldo", "ranta"]
        widgets = {"datum": Datum()}


def lista(request):
    idag = dt.date.today()
    tillgangar = []
    for t in Tillgang.objects.prefetch_related("lan", "varderingar"):
        varde, mitt = t.varde_per(idag), t.mitt_varde_per(idag)
        lan = sum((l.mitt_saldo_per(idag) for l in t.lan.all()), Decimal(0))
        tillgangar.append({"t": t, "varde": varde, "mitt": mitt, "lan": lan, "eget": mitt - lan,
                           "belaning": (lan / mitt * 100) if mitt else None, "vardering": t.senaste_vardering()})
    lan = [(l, l.mitt_saldo_per(idag), l.senaste_saldo()) for l in Lan.objects.select_related("tillgang")]
    return render(request, "tillgangar/lista.html", {
        "tillgangar": tillgangar, "lan": lan, "f": formogenhet_per(idag),
        "summa_lan": sum((x[1] for x in lan), Decimal(0))})


def tillgang(request, pk):
    t = get_object_or_404(Tillgang, pk=pk)
    vform = VarderingForm(request.POST if "vardering" in request.POST else None, prefix="v",
                          initial={"datum": dt.date.today()})
    fform = ForbattringForm(request.POST if "forbattring" in request.POST else None, prefix="f",
                            initial={"datum": dt.date.today()})
    if request.method == "POST":
        if "radera_vardering" in request.POST:
            t.varderingar.filter(pk=request.POST["radera_vardering"]).delete()
            return redirect(t)
        if "radera_forbattring" in request.POST:
            t.forbattringar.filter(pk=request.POST["radera_forbattring"]).delete()
            return redirect(t)
        for form in (vform, fform):
            if form.is_bound and form.is_valid():
                o = form.save(commit=False)
                o.tillgang = t
                o.save()
                messages.success(request, "Sparat.")
                return redirect(t)
    idag = dt.date.today()
    # Kostnader och intäkter kopplade till tillgången, per år och kategori
    kostnader = {}
    for r in (t.transaktioner.values("datum__year", "kategori__grupp", "kategori__namn")
              .annotate(s=Sum("belopp")).order_by("-datum__year", "kategori__grupp")):
        kostnader.setdefault(r["datum__year"], []).append(r)
    kostnader = [(ar, rader, sum((r["s"] for r in rader), Decimal(0))) for ar, rader in kostnader.items()]
    varderingar = list(t.varderingar.order_by("datum"))
    graf = None
    if len(varderingar) > 1:
        graf = diagram.linje([str(v.datum)[:7] for v in varderingar],
                             [("Värde", diagram.FARGER["netto"], [v.varde for v in varderingar])])
    mitt, lan = t.mitt_varde_per(idag), sum((l.mitt_saldo_per(idag) for l in t.lan.all()), Decimal(0))
    return render(request, "tillgangar/tillgang.html", {
        "t": t, "vform": vform, "fform": fform, "varde": t.varde_per(idag), "mitt": mitt, "lan_summa": lan,
        "eget": mitt - lan, "belaning": (lan / mitt * 100) if mitt else None, "lan": t.lan.all(),
        "kostnader": kostnader, "graf": graf, "varderingar": reversed(varderingar),
        "kvmpris": (t.varde_per(idag) / t.boarea) if t.boarea and t.varde_per(idag) else None,
        "vinst": (t.varde_per(idag) - t.anskaffningsvarde()) if t.kopeskilling else None})


def tillgang_form(request, pk=None):
    t = get_object_or_404(Tillgang, pk=pk) if pk else None
    form = TillgangForm(request.POST or None, instance=t)
    if request.method == "POST":
        if "radera" in request.POST and t:
            t.delete()
            messages.success(request, "Tillgången raderades.")
            return redirect("tillgangar")
        if form.is_valid():
            t = form.save()
            return redirect(t)
    return render(request, "form.html", {"form": form, "rubrik": "Ändra tillgång" if t else "Ny tillgång",
                                         "kan_radera": bool(t), "tillbaka": "tillgangar"})


def lan(request, pk):
    l = get_object_or_404(Lan, pk=pk)
    form = LanesaldoForm(request.POST or None, initial={"datum": dt.date.today(), "ranta": l.ranta})
    if request.method == "POST":
        if "radera_saldo" in request.POST:
            l.saldon.filter(pk=request.POST["radera_saldo"]).delete()
            return redirect(l)
        if form.is_valid():
            s = form.save(commit=False)
            s.lan = l
            s.save()
            if s.ranta is not None and s.datum >= (l.senaste_saldo().datum if l.senaste_saldo() else s.datum):
                l.ranta = s.ranta
                l.save(update_fields=["ranta"])
            messages.success(request, "Saldot sparades.")
            return redirect(l)
    saldon = list(l.saldon.order_by("datum"))
    graf = diagram.linje([str(s.datum)[:7] for s in saldon], [("Skuld", diagram.FARGER["skuld"],
                                                               [s.saldo for s in saldon])]) if len(saldon) > 1 else None
    return render(request, "tillgangar/lan.html", {"l": l, "form": form, "saldon": reversed(saldon), "graf": graf,
                                                   "saldo": l.saldo_per(), "ranta_manad": l.rantekostnad_per_manad()})


def lan_form(request, pk=None):
    l = get_object_or_404(Lan, pk=pk) if pk else None
    form = LanForm(request.POST or None, instance=l, initial={"tillgang": request.GET.get("tillgang")})
    if request.method == "POST":
        if "radera" in request.POST and l:
            l.delete()
            return redirect("tillgangar")
        if form.is_valid():
            l = form.save()
            if form.cleaned_data.get("startsaldo") is not None:
                Lanesaldo.objects.create(lan=l, datum=dt.date.today(), saldo=form.cleaned_data["startsaldo"],
                                         ranta=l.ranta)
            return redirect(l)
    return render(request, "form.html", {"form": form, "rubrik": "Ändra lån" if l else "Nytt lån",
                                         "kan_radera": bool(l), "tillbaka": "tillgangar"})


def formogenhet(request):
    manader = int(request.GET.get("manader") or 24)
    punkter = historik(manader)
    etiketter = [f"{MANADSNAMN[d.month - 1]} {str(d.year)[2:]}" for d, _ in punkter]
    graf = diagram.linje(etiketter, [
        ("Nettoförmögenhet", diagram.FARGER["netto"], [p["netto"] for _, p in punkter]),
        ("Tillgångar", diagram.FARGER["in"], [p["summa_tillgangar"] for _, p in punkter]),
        ("Skulder", diagram.FARGER["skuld"], [p["summa_skulder"] for _, p in punkter]),
    ], hojd=280)
    return render(request, "tillgangar/formogenhet.html", {"graf": graf, "punkter": list(reversed(punkter)),
                                                           "manader": manader})
