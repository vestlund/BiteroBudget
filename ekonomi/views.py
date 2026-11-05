import datetime as dt
from decimal import Decimal

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from budget.models import MANADSNAMN, Budget
from tillgangar.berakning import formogenhet_per

from . import diagram
from .forms import ImportForm, KategoriForm, KontoForm, KontosaldoForm, RegelForm, TransaktionForm
from .importering import ImportFel, importera
from .models import (
    Importfil,
    Kategori,
    Kategoriregel,
    Konto,
    Kontosaldo,
    Transaktion,
    kategorisera,
    utfall_per_kategori_och_manad,
)


def _manader_bakat(idag, n):
    ar, m, res = idag.year, idag.month, []
    for _ in range(n):
        res.append((ar, m))
        ar, m = (ar - 1, 12) if m == 1 else (ar, m - 1)
    return list(reversed(res))


# ------------------------------------------------------------------ översikt

def oversikt(request):
    idag = dt.date.today()
    ar, man = idag.year, idag.month
    form = formogenhet_per(idag)

    # In och ut per månad senaste 12 månaderna (överföringar räknas inte)
    perioder = _manader_bakat(idag, 12)
    fran = dt.date(*perioder[0], 1)
    rader = (Transaktion.objects.raknas().filter(datum__gte=fran)
             .values("datum__year", "datum__month")
             .annotate(inn=Sum("belopp", filter=Q(belopp__gt=0)), ut=Sum("belopp", filter=Q(belopp__lt=0))))
    per = {(r["datum__year"], r["datum__month"]): r for r in rader}
    inn = [per.get(p, {}).get("inn") or 0 for p in perioder]
    ut = [-(per.get(p, {}).get("ut") or 0) for p in perioder]
    etiketter = [MANADSNAMN[m - 1] for _, m in perioder]

    # Månaden mot budget per kategorigrupp
    budget = Budget.for_ar(ar)
    bud = budget.per_kategori() if budget else {}
    utfall = utfall_per_kategori_och_manad(ar)
    grupper = {}
    for k in Kategori.objects.filter(typ=Kategori.UTGIFT):
        g = grupper.setdefault(k.grupp, {"grupp": k.grupp, "utfall": Decimal(0), "budget": Decimal(0)})
        g["utfall"] += utfall.get(k.pk, [0] * 12)[man - 1]
        g["budget"] += bud.get(k.pk, [0] * 12)[man - 1]
    grupplista = sorted((g for g in grupper.values() if g["utfall"] or g["budget"]), key=lambda g: -g["utfall"])
    for g in grupplista:
        g["procent"] = min(100, int(g["utfall"] / g["budget"] * 100)) if g["budget"] else 100
        g["over"] = g["utfall"] > g["budget"]

    inkomst_id = set(Kategori.objects.filter(typ=Kategori.INKOMST).values_list("pk", flat=True))
    manad_inn = sum((v[man - 1] for k, v in utfall.items() if k in inkomst_id), Decimal(0))
    manad_ut = sum(g["utfall"] for g in grupper.values())
    return render(request, "ekonomi/oversikt.html", {
        "form": form, "idag": idag, "manadsnamn": MANADSNAMN[man - 1], "budget": budget,
        "diagram": diagram.stapel(etiketter, [("Inkomster", diagram.FARGER["in"], inn),
                                              ("Utgifter", diagram.FARGER["ut"], ut)]),
        "grupper": grupplista, "manad_inn": manad_inn, "manad_ut": manad_ut,
        "manad_budget_ut": sum(g["budget"] for g in grupper.values()),
        "konton": [(k, k.saldo_per(idag)) for k in Konto.objects.filter(aktiv=True)],
        "senaste_import": Importfil.objects.select_related("konto").first(),
        "okategoriserade": Transaktion.objects.okategoriserade().count(),
    })


# ------------------------------------------------------------------ transaktioner

def transaktioner(request):
    qs = Transaktion.objects.select_related("konto", "kategori", "tillgang")
    g = request.GET
    if g.get("konto"):
        qs = qs.filter(konto_id=g["konto"])
    if g.get("kategori") == "ingen":
        qs = qs.filter(kategori__isnull=True)
    elif g.get("kategori"):
        qs = qs.filter(kategori_id=g["kategori"])
    if g.get("grupp"):
        qs = qs.filter(kategori__grupp=g["grupp"])
    if g.get("ar"):
        qs = qs.filter(datum__year=g["ar"])
    if g.get("manad"):
        qs = qs.filter(datum__month=g["manad"])
    if g.get("import"):
        qs = qs.filter(importfil_id=g["import"])
    if g.get("tillgang"):
        qs = qs.filter(tillgang_id=g["tillgang"])
    if g.get("person"):
        qs = qs.filter(kortinnehavare=g["person"])
    if q := g.get("q", "").strip():
        qs = qs.sok(q)
    summa = qs.aggregate(s=Sum("belopp"), n=Count("id"))
    sida = Paginator(qs, 200).get_page(g.get("sida"))
    ar_lista = sorted({d.year for d in Transaktion.objects.dates("datum", "year")}, reverse=True)
    return render(request, "ekonomi/transaktioner.html", {
        "sida": sida, "summa": summa, "konton": Konto.objects.all(), "kategorier": Kategori.objects.all(),
        "ar_lista": ar_lista, "personer": Transaktion.objects.exclude(kortinnehavare="").order_by("kortinnehavare")
        .values_list("kortinnehavare", flat=True).distinct(), "manader": list(enumerate(MANADSNAMN, 1)), "f": g,
        "parametrar": g.urlencode().replace("sida=", "x="),
    })


@require_POST
def satt_kategori(request, pk):
    """Anropas från listan (htmx) när kategorin väljs i rullgardinen."""
    t = get_object_or_404(Transaktion, pk=pk)
    t.kategori_id = request.POST.get("kategori") or None
    t.manuellt_kategoriserad = bool(t.kategori_id)
    t.save(update_fields=["kategori", "manuellt_kategoriserad"])
    return HttpResponse('<span class="sparat">✓</span>')


def transaktion(request, pk=None):
    t = get_object_or_404(Transaktion, pk=pk) if pk else Transaktion(datum=dt.date.today())
    if pk is None and request.GET.get("konto"):
        t.konto_id = request.GET["konto"]
    form = TransaktionForm(request.POST or None, instance=t)
    if request.method == "POST":
        if "radera" in request.POST and t.pk:
            t.delete()
            messages.success(request, "Transaktionen raderades.")
            return redirect("transaktioner")
        if form.is_valid():
            gammal_kategori = Transaktion.objects.filter(pk=t.pk).values_list("kategori_id", flat=True).first()
            t = form.save(commit=False)
            if t.kategori_id != gammal_kategori or not pk:
                t.manuellt_kategoriserad = bool(t.kategori_id)
            t.save()
            if (monster := form.cleaned_data.get("skapa_regel", "").strip()) and t.kategori_id:
                Kategoriregel.objects.create(monster=monster, kategori=t.kategori, tillgang=t.tillgang)
                n = kategorisera()
                messages.success(request, f"Regeln '{monster}' skapades och kategoriserade {n} transaktioner till.")
            else:
                messages.success(request, "Sparat.")
            return redirect(request.GET.get("tillbaka") or "transaktioner")
    return render(request, "ekonomi/transaktion.html", {"form": form, "t": t})


# ------------------------------------------------------------------ import

_FORMATNAMN = {"bank": "en bank", "amex": "American Express", "sas": "SEB Kort (SAS EuroBonus Mastercard)"}

def importsida(request):
    form = ImportForm(request.POST or None, request.FILES or None, initial={"konto": request.GET.get("konto")})
    if request.method == "POST" and form.is_valid():
        konto = form.cleaned_data["konto"]
        for f in form.cleaned_data["filer"]:
            try:
                imp = importera(konto, f.read(), f.name)
            except ImportFel as e:
                messages.error(request, f"{f.name}: {e}")
                continue
            if konto.importformat != Konto.AUTO and imp.format != konto.importformat:
                messages.warning(request, f"{f.name} ser ut att vara en fil från {_FORMATNAMN.get(imp.format, imp.format)}, "
                                          f"men kontot {konto} är inställt på {konto.get_importformat_display()}. "
                                          "Kontrollera att du valde rätt konto – annars ångra importen nedan.")
            messages.success(request, f"{f.name}: {imp.antal_nya} nya transaktioner ({imp.forsta_datum} – "
                                      f"{imp.sista_datum}), {imp.antal_dubbletter} fanns redan"
                                      f"{', tecknet vändes (köp = minus)' if imp.tecken_vant else ''}.")
        return redirect("importera")
    return render(request, "ekonomi/importera.html", {
        "form": form, "importer": Importfil.objects.select_related("konto")[:50],
        "har_konton": Konto.objects.exists()})


@require_POST
def import_angra(request, pk):
    imp = get_object_or_404(Importfil, pk=pk)
    n = imp.transaktioner.count()
    Kontosaldo.objects.filter(konto=imp.konto, kalla=f"Import {imp.filnamn}"[:100]).delete()
    imp.delete()
    messages.success(request, f"Importen av {imp.filnamn} ångrades ({n} transaktioner togs bort).")
    return redirect("importera")


# ------------------------------------------------------------------ konton

def konton(request):
    idag = dt.date.today()
    lista = [(k, k.saldo_per(idag), k.transaktioner.count(), k.transaktioner.order_by("-datum").first())
             for k in Konto.objects.all()]
    return render(request, "ekonomi/konton.html", {"lista": lista})


def konto(request, pk):
    k = get_object_or_404(Konto, pk=pk)
    form = KontosaldoForm(request.POST or None, initial={"datum": dt.date.today()})
    if request.method == "POST":
        if "radera_saldo" in request.POST:
            k.saldon.filter(pk=request.POST["radera_saldo"]).delete()
            return redirect(k)
        if form.is_valid():
            s = form.save(commit=False)
            s.konto = k
            s.save()
            messages.success(request, "Saldot sparades.")
            return redirect(k)
    idag = dt.date.today()
    perioder = _manader_bakat(idag, 12)
    from tillgangar.berakning import manadsslut

    saldon = [k.saldo_per(min(manadsslut(a, m), idag)) for a, m in perioder]
    return render(request, "ekonomi/konto.html", {
        "k": k, "form": form, "saldo": k.saldo_per(idag), "saldon": k.saldon.all()[:20],
        "importer": k.importer.all()[:10],
        "diagram": diagram.linje([f"{MANADSNAMN[m - 1]} {str(a)[2:]}" for a, m in perioder],
                                 [("Saldo", diagram.FARGER["netto"], saldon)]),
        "senaste": k.transaktioner.select_related("kategori")[:15]})


def konto_form(request, pk=None):
    k = get_object_or_404(Konto, pk=pk) if pk else None
    form = KontoForm(request.POST or None, instance=k)
    if request.method == "POST":
        if "radera" in request.POST and k:
            if k.transaktioner.exists():
                messages.error(request, "Kontot har transaktioner. Ångra importerna först eller gör kontot inaktivt.")
                return redirect("konto_andra", pk=k.pk)
            k.delete()
            return redirect("konton")
        if form.is_valid():
            k = form.save()
            messages.success(request, "Kontot sparades.")
            return redirect(k)
    return render(request, "form.html", {"form": form, "rubrik": "Ändra konto" if k else "Nytt konto",
                                         "kan_radera": bool(k), "tillbaka": "konton"})


# ------------------------------------------------------------------ kategorier och regler

def kategorier(request):
    ar = dt.date.today().year
    antal = dict(Transaktion.objects.filter(datum__year=ar).values_list("kategori").annotate(n=Count("id")))
    lista = [(k, antal.get(k.pk, 0)) for k in Kategori.objects.annotate(antal_regler=Count("regler"))]
    return render(request, "ekonomi/kategorier.html", {"lista": lista, "ar": ar})


def kategori_form(request, pk=None):
    k = get_object_or_404(Kategori, pk=pk) if pk else None
    form = KategoriForm(request.POST or None, instance=k, initial={"grupp": request.GET.get("grupp", "")})
    if request.method == "POST":
        if "radera" in request.POST and k:
            k.delete()
            messages.success(request, "Kategorin raderades. Transaktionerna blev okategoriserade.")
            return redirect("kategorier")
        if form.is_valid():
            form.save()
            return redirect("kategorier")
    return render(request, "form.html", {"form": form, "rubrik": "Ändra kategori" if k else "Ny kategori",
                                         "kan_radera": bool(k), "tillbaka": "kategorier"})


def regler(request):
    return render(request, "ekonomi/regler.html", {
        "regler": Kategoriregel.objects.select_related("kategori", "konto", "tillgang")})


def regel_form(request, pk=None):
    r = get_object_or_404(Kategoriregel, pk=pk) if pk else None
    form = RegelForm(request.POST or None, instance=r, initial={"monster": request.GET.get("monster", "")})
    if request.method == "POST":
        if "radera" in request.POST and r:
            r.delete()
            return redirect("regler")
        if form.is_valid():
            form.save()
            n = kategorisera()
            messages.success(request, f"Regeln sparades. {n} okategoriserade transaktioner fick kategori.")
            return redirect("regler")
    return render(request, "form.html", {"form": form, "rubrik": "Ändra regel" if r else "Ny regel",
                                         "kan_radera": bool(r), "tillbaka": "regler"})


@require_POST
def regler_importera(request):
    from .regelfil import importera_regler

    f = request.FILES.get("fil")
    if not f:
        messages.error(request, "Välj en fil.")
        return redirect("regler")
    try:
        nya, uppd, nya_kat = importera_regler(f.read(), f.name)
    except ImportFel as e:
        messages.error(request, f"{f.name}: {e}")
        return redirect("regler")
    n = kategorisera(skriv_over=request.POST.get("skriv_over") == "1")
    messages.success(request, f"{nya} nya och {uppd} uppdaterade regler, {nya_kat} nya kategorier. "
                              f"{n} transaktioner fick kategori.")
    return redirect("regler")


def regler_exportera(request):
    from .regelfil import exportera_regler

    svar = HttpResponse(exportera_regler(),
                        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    svar["Content-Disposition"] = f'attachment; filename="kategoriregler-{dt.date.today()}.xlsx"'
    return svar


@require_POST
def kor_regler(request):
    skriv_over = request.POST.get("skriv_over") == "1"
    n = kategorisera(skriv_over=skriv_over)
    messages.success(request, f"Reglerna kördes: {n} transaktioner fick ny kategori"
                              f"{' (manuellt kategoriserade rördes inte)' if skriv_over else ''}.")
    return redirect(request.POST.get("tillbaka") or "regler")
