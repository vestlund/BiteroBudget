from django import forms

from .models import Kategori, Kategoriregel, Konto, Kontosaldo, Transaktion


class Datum(forms.DateInput):
    input_type = "date"

    def __init__(self, **kw):
        super().__init__(format="%Y-%m-%d", **kw)


class KategoriVal(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.grupp} – {obj.namn}"


def kategorival(required=False):
    return KategoriVal(Kategori.objects.filter(aktiv=True).order_by("ordning", "grupp", "namn"),
                       required=required, empty_label="(okategoriserad)" if not required else "---------")


class FlerFiler(forms.ClearableFileInput):
    allow_multiple_selected = True


class FlerFilFalt(forms.FileField):
    def __init__(self, *a, **kw):
        kw.setdefault("widget", FlerFiler(attrs={"accept": ".csv,.txt,.xlsx,.xls"}))
        super().__init__(*a, **kw)

    def clean(self, data, initial=None):
        enkel = super().clean
        if isinstance(data, (list, tuple)):
            return [enkel(d, initial) for d in data]
        return [enkel(data, initial)]


class ImportForm(forms.Form):
    konto = forms.ModelChoiceField(Konto.objects.filter(aktiv=True))
    filer = FlerFilFalt(label="Filer (CSV eller Excel)")


class KontoForm(forms.ModelForm):
    class Meta:
        model = Konto
        fields = ["namn", "typ", "institut", "kontonummer", "importformat", "tecken", "ingaende_saldo",
                  "ingaende_datum", "ordning", "aktiv"]
        widgets = {"ingaende_datum": Datum()}


class KontosaldoForm(forms.ModelForm):
    class Meta:
        model = Kontosaldo
        fields = ["datum", "saldo", "kalla"]
        widgets = {"datum": Datum()}


class KategoriForm(forms.ModelForm):
    class Meta:
        model = Kategori
        fields = ["grupp", "namn", "typ", "ordning", "aktiv"]


class RegelForm(forms.ModelForm):
    kategori = kategorival(required=True)

    class Meta:
        model = Kategoriregel
        fields = ["monster", "kategori", "konto", "tillgang", "endast_utgifter", "endast_inkomster", "prioritet"]


class TransaktionForm(forms.ModelForm):
    kategori = kategorival()
    skapa_regel = forms.CharField(
        label="Skapa regel: texten innehåller", required=False,
        help_text="Fyll i t.ex. ett butiksnamn så kategoriseras liknande transaktioner automatiskt framöver")

    class Meta:
        model = Transaktion
        fields = ["konto", "datum", "text", "belopp", "kategori", "tillgang", "anteckning"]
        widgets = {"datum": Datum()}

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        if self.instance.pk and self.instance.importfil_id:
            # importerade transaktioner: datum, belopp och text kommer från banken
            for f in ("konto", "datum", "text", "belopp"):
                self.fields[f].disabled = True
