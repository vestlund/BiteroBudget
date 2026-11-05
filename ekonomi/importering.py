"""Läser kontoutdrag och kortutdrag (CSV, Excel .xlsx/.xls) och sparar dem som transaktioner.

Filerna ser olika ut hos olika banker, så kolumnerna letas upp på rubrikerna:

* Bank (Handelsbanken, SEB, Swedbank, Nordea, ICA Banken, Länsförsäkringar m.fl.): datum, text, belopp, ev. saldo.
  Uttag är minus och insättningar plus, precis som i filen.
* American Express: export från "Kontoutdrag/Senaste transaktioner" som Excel eller CSV (Datum, Beskrivning,
  Belopp ...). Köp är plus i filen och vänds till minus.
* SAS EuroBonus Mastercard (SEB Kort): export till Excel (Datum, Bokfört, Specifikation, Ort, Valuta,
  Utl. belopp, Belopp). Köp är plus i filen och vänds till minus.

Samma transaktion importeras aldrig två gånger: varje rad får en nyckel av konto, datum, belopp och text
(plus löpnummer för identiska rader i samma fil), så överlappande utdrag kan läsas in utan dubbletter.
"""

import csv
import datetime as dt
import hashlib
import io
import re
from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from django.db import transaction

DATUM = ["transaktionsdatum", "transaktionsdag", "köpdatum", "datum", "bokföringsdag", "bokföringsdatum",
         "bokförd", "bokfört", "reskontradatum", "date", "valutadag", "valutadatum"]
BELOPP = ["belopp", "belopp sek", "belopp (sek)", "belopp i sek", "amount", "summa"]
TEXT = ["specifikation", "beskrivning", "text", "text/mottagare", "rubrik", "transaktion", "meddelande",
        "mottagare", "namn", "description", "referens"]
SALDO = ["bokfört saldo", "saldo", "balance", "saldo sek"]
VALUTA = ["valuta", "currency"]
UTL_BELOPP = ["utl. belopp", "utl.belopp", "utländskt belopp", "belopp i utländsk valuta", "originalbelopp",
              "ursprungligt belopp", "foreign amount"]
ORT = ["ort", "stad", "city"]
STATUS = ["status"]
KORTINNEHAVARE = ["kortmedlem", "kortinnehavare", "card member"]
EXTRA_INFO = ["utökade specifikationer", "utökade detaljer", "extended details"]

# Amex skriver utländska köp som "Foreign Spend Amount: 6.13 UNITED STATES DOLLAR Commission Amount: ..."
VALUTANAMN = {"UNITED STATES DOLLAR": "USD", "EUROPEAN UNION EURO": "EUR", "EURO": "EUR", "NORWEGIAN KRONE": "NOK",
              "DANISH KRONE": "DKK", "POUND STERLING": "GBP", "UK POUND STERLING": "GBP", "SWISS FRANC": "CHF",
              "JAPANESE YEN": "JPY", "CANADIAN DOLLAR": "CAD", "AUSTRALIAN DOLLAR": "AUD", "THAI BAHT": "THB",
              "POLISH ZLOTY": "PLN", "CZECH KORUNA": "CZK", "HUNGARIAN FORINT": "HUF", "ICELANDIC KRONA": "ISK",
              "TURKISH LIRA": "TRY", "MEXICAN PESO": "MXN", "SOUTH AFRICAN RAND": "ZAR"}
_UTLANDSK = re.compile(r"Foreign Spend Amount:\s*([\d.,]+)\s+(.+?)\s+Commission", re.I)

# SEB Kort skriver ibland å, ä, ö med gammal 7-bitars kod: H{GERSTEN = HÄGERSTEN
_SJUBITARS = str.maketrans({"{": "ä", "}": "å", "|": "ö", "[": "Ä", "]": "Å", "\\": "Ö", "¦": "Ö"})
_SJUBITARS_VERSAL = str.maketrans({"{": "Ä", "}": "Å", "|": "Ö", "[": "Ä", "]": "Å", "\\": "Ö", "¦": "Ö"})


def _sjubitars(text):
    """Översätter per ord: H{GERSTEN blir HÄGERSTEN, S{ter blir Säter."""
    def ord_(m):
        w = m.group(0)
        bokstaver = re.sub(r"[{}|\[\]\\¦]", "", w)
        return w.translate(_SJUBITARS_VERSAL if bokstaver.isupper() else _SJUBITARS)
    return re.sub(r"\S+", ord_, text) if re.search(r"[{}|\[\]\\¦]", text) else text
_KORTRAD = re.compile(r"^\d{4,6}\*{4,}\d{4}$")


class ImportFel(Exception):
    pass


@dataclass
class Rad:
    datum: dt.date
    belopp: Decimal
    text: str
    saldo: Decimal | None = None
    valuta: str = ""
    utl_belopp: Decimal | None = None
    kortinnehavare: str = ""


@dataclass
class Utdrag:
    format: str
    rader: list = field(default_factory=list)
    har_saldo: bool = False
    fallande: bool = False  # nyaste först i filen


# ------------------------------------------------------------------ läsa filen till tabellrader

def _avkoda(data: bytes) -> str:
    for kod in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return data.decode(kod)
        except UnicodeDecodeError:
            continue
    raise ImportFel("Kunde inte läsa filens teckenkodning.")


def _csv_tabell(data: bytes):
    text = _avkoda(data)
    rader = text.splitlines()
    prov = "\n".join(rader[:60])
    try:
        dialekt = csv.Sniffer().sniff(prov, delimiters=";,\t")
    except csv.Error:
        avgr = ";" if prov.count(";") >= prov.count(",") else ","

        class dialekt(csv.excel):
            delimiter = avgr
    return [list(r) for r in csv.reader(io.StringIO(text), dialekt)]


def _xlsx_tabeller(data: bytes):
    import openpyxl

    try:
        bok = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as e:  # noqa: BLE001 - visas för användaren
        raise ImportFel(f"Kunde inte läsa Excel-filen: {e}")
    tabeller = []
    for blad in bok.worksheets:
        # Bankernas filer anger ofta fel storlek (t.ex. bara A1) – läs hela bladet i stället
        blad.reset_dimensions()
        tabeller.append([list(r) for r in blad.iter_rows(values_only=True)])
    return tabeller


def _xls_tabeller(data: bytes):
    import xlrd

    try:
        bok = xlrd.open_workbook(file_contents=data)
    except Exception as e:  # noqa: BLE001
        raise ImportFel(f"Kunde inte läsa den gamla Excel-filen (.xls): {e}")
    tabeller = []
    for blad in bok.sheets():
        rader = []
        for i in range(blad.nrows):
            rad = []
            for c in blad.row(i):
                if c.ctype == xlrd.XL_CELL_DATE:
                    rad.append(xlrd.xldate.xldate_as_datetime(c.value, bok.datemode))
                else:
                    rad.append(c.value)
            rader.append(rad)
        tabeller.append(rader)
    return tabeller


def las_tabeller(data: bytes, filnamn: str):
    namn = filnamn.lower()
    if namn.endswith(".xlsx") or namn.endswith(".xlsm") or data[:2] == b"PK":
        return _xlsx_tabeller(data)
    if namn.endswith(".xls") or data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return _xls_tabeller(data)
    if data.lstrip()[:15].lower().startswith((b"<html", b"<!doctype", b"<table")):
        raise ImportFel("Filen är en webbsida (HTML) och inte en CSV/Excel-fil. Spara den som .xlsx i Excel först.")
    return [_csv_tabell(data)]


# ------------------------------------------------------------------ tolka värden

def _str(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip().strip('"').strip()


def tal(v):
    if v is None or v == "":
        return None
    if isinstance(v, (int, float, Decimal)) and not isinstance(v, bool):
        return Decimal(str(v)).quantize(Decimal("0.01"))
    s = str(v).strip().replace("\xa0", "").replace(" ", "").replace("−", "-").replace("–", "-")
    s = re.sub(r"(?i)(sek|kr)\.?$", "", s)
    neg = s.endswith("-") or (s.startswith("(") and s.endswith(")"))
    s = s.strip("()").rstrip("-")
    if not re.fullmatch(r"[+-]?[\d.,']+", s or "x"):
        return None
    s = s.replace("'", "")
    if "," in s and "." in s:
        # den sista avgränsaren är decimaltecknet
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".") if len(s.split(",")[-1]) != 3 or s.count(",") == 1 else s.replace(",", "")
    try:
        d = Decimal(s)
    except InvalidOperation:
        return None
    return (-d if neg else d).quantize(Decimal("0.01"))


_SNEDSTRECK = re.compile(r"^(\d{1,2})[/.](\d{1,2})[/.](\d{2,4})")


def datum(v, dag_forst=True):
    if v is None or v == "":
        return None
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    s = _str(v)
    m = re.match(r"^(\d{4})-?(\d{2})-?(\d{2})", s)
    if m:
        try:
            return dt.date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            return None
    m = re.match(r"^(\d{4})/(\d{1,2})/(\d{1,2})", s)
    if m:
        try:
            return dt.date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            return None
    m = _SNEDSTRECK.match(s)
    if m:
        a, b, ar = int(m[1]), int(m[2]), int(m[3])
        ar += 2000 if ar < 100 else 0
        dag, man = (a, b) if dag_forst else (b, a)
        try:
            return dt.date(ar, man, dag)
        except ValueError:
            return None
    return None


def _dagordning(varden):
    """Avgör om datum som 03/04/2026 är dag/månad eller månad/dag genom att titta på hela kolumnen."""
    forsta = andra = False
    for v in varden:
        m = _SNEDSTRECK.match(_str(v))
        if m:
            forsta |= int(m[1]) > 12
            andra |= int(m[2]) > 12
    if andra and not forsta:
        return False  # månad/dag/år (amerikanskt)
    return True


# ------------------------------------------------------------------ hitta kolumner

def _norm(r):
    return re.sub(r"\s+", " ", _str(r).lower().replace("\n", " ")).strip(" :*")


def _hitta(rubriker, namn, utom=()):
    for n in namn:
        for i, r in enumerate(rubriker):
            if r == n and i not in utom:
                return i
    for n in namn:
        for i, r in enumerate(rubriker):
            if n in r and i not in utom and not any(x in r for x in ("utl", "utländsk", "original", "ursprung")):
                return i
    return None


def _ar_rubrikrad(rad):
    rubriker = [_norm(c) for c in rad]
    har_datum = any(r in DATUM or "datum" in r for r in rubriker)
    har_belopp = any(r in BELOPP or ("belopp" in r and "utl" not in r) or r == "amount" for r in rubriker)
    return har_datum and har_belopp


def kann_igen_format(rader):
    """'amex', 'sas' eller 'bank' utifrån raderna före och med rubrikraden (inte transaktionstexterna)."""
    text = " ".join(_norm(c) for rad in rader for c in rad if c is not None)
    if any(o in text for o in ("american express", "amex", "kortmedlem", "utökade detaljer")):
        return "amex"
    if any(o in text for o in ("eurobonus", "sas mastercard", "seb kort")) or \
            ("specifikation" in text and "utl" in text):
        return "sas"
    return "bank"


def tolka(data: bytes, filnamn: str) -> Utdrag:
    tabeller = las_tabeller(data, filnamn)
    for tabell in tabeller:
        for start, rad in enumerate(tabell[:60]):
            if _ar_rubrikrad(rad):
                utdrag = _tolka_tabell(tabell, start, kann_igen_format(tabell[:start + 1]))
                if utdrag.rader:
                    return utdrag
    raise ImportFel("Hittade ingen rubrikrad med datum och belopp i filen. Kontrollera att det är ett "
                    "kontoutdrag eller en transaktionslista exporterad som CSV eller Excel.")


def _ar_reserverat(c):
    return "reserver" in c or "pending" in c or "ej bokförd" in c or "väntande" in c


def _tolka_tabell(tabell, start, fmt):
    rubriker = [_norm(c) for c in tabell[start]]
    i_datum = _hitta(rubriker, DATUM)
    i_belopp = _hitta(rubriker, BELOPP)
    i_saldo = _hitta(rubriker, SALDO, utom=(i_belopp,))
    i_text = _hitta(rubriker, TEXT, utom=(i_datum, i_belopp))
    i_valuta = _hitta(rubriker, VALUTA)
    i_utl = next((i for i, r in enumerate(rubriker) if r in UTL_BELOPP or any(u in r for u in UTL_BELOPP)), None)
    i_ort = next((i for i, r in enumerate(rubriker) if r in ORT), None)  # exakt: "kortmedlem" innehåller "ort"
    i_status = next((i for i, r in enumerate(rubriker) if r in STATUS), None)
    i_person = next((i for i, r in enumerate(rubriker) if r in KORTINNEHAVARE), None)
    i_extra = next((i for i, r in enumerate(rubriker) if r in EXTRA_INFO), None)
    if i_datum is None or i_belopp is None:
        raise ImportFel(f"Kunde inte hitta datum- och beloppskolumn bland: {', '.join(r for r in rubriker if r)}")

    data_rader = tabell[start + 1:]
    dag_forst = _dagordning(r[i_datum] for r in data_rader if len(r) > i_datum)
    utdrag = Utdrag(format=fmt, har_saldo=i_saldo is not None)
    reserverat_avsnitt = False
    person = ""
    for r in reversed(tabell[:start]):  # står "Reserverade" närmast ovanför rubrikraden?
        celler = [_str(c).lower() for c in r if _str(c)]
        if celler:
            reserverat_avsnitt = len(celler) <= 2 and any(_ar_reserverat(c) for c in celler)
            break
    for r in data_rader:
        if not any(_str(c) for c in r):
            continue
        if _ar_rubrikrad(r):  # ny sektion med samma rubriker (t.ex. per kortinnehavare)
            reserverat_avsnitt = False
            continue
        celler = [_str(c).lower() for c in r if _str(c)]
        if len(celler) == 2 and _KORTRAD.match(celler[0]):  # SEB Kort: ny sektion per kort och innehavare
            person = _str(r[1]).title()
            continue
        if len(celler) <= 2 and any(_ar_reserverat(c) for c in celler):
            reserverat_avsnitt = True
            continue
        if len(celler) <= 2 and any(c.startswith(("bokförda", "posted", "transaktioner")) for c in celler):
            reserverat_avsnitt = False
        if reserverat_avsnitt or len(r) <= max(i_datum, i_belopp):
            continue
        if i_status is not None and i_status < len(r) and re.search(r"reserv|pending|väntande", _str(r[i_status]).lower()):
            continue
        d, b = datum(r[i_datum], dag_forst), tal(r[i_belopp])
        if not d or b is None:
            continue
        txt = _str(r[i_text]) if i_text is not None and i_text < len(r) else ""
        if i_ort is not None and i_ort < len(r) and _str(r[i_ort]) and _str(r[i_ort]).lower() not in txt.lower():
            txt = f"{txt}, {_str(r[i_ort])}" if txt else _str(r[i_ort])
        if fmt == "sas":
            txt = _sjubitars(txt)
        txt = re.sub(r"\s+", " ", txt)[:300] or "(ingen text)"
        valuta = _str(r[i_valuta]).upper()[:3] if i_valuta is not None and i_valuta < len(r) else ""
        utl = tal(r[i_utl]) if i_utl is not None and i_utl < len(r) else None
        if i_extra is not None and i_extra < len(r) and (m := _UTLANDSK.search(_str(r[i_extra]))):
            namn = re.sub(r"\s+", " ", m[2]).upper()
            valuta = VALUTANAMN.get(namn, "")
            utl = tal(m[1]) if valuta else None
        rad_person = _str(r[i_person]).title() if i_person is not None and i_person < len(r) else person
        utdrag.rader.append(Rad(
            datum=d, belopp=b, text=txt, valuta=valuta, utl_belopp=utl or None, kortinnehavare=rad_person[:60],
            saldo=tal(r[i_saldo]) if i_saldo is not None and i_saldo < len(r) else None,
        ))
    if len(utdrag.rader) > 1:
        utdrag.fallande = utdrag.rader[0].datum > utdrag.rader[-1].datum
    return utdrag


# ------------------------------------------------------------------ spara

def ska_vanda_tecken(konto, utdrag):
    from .models import Konto

    if konto.tecken == Konto.TECKEN_VAND:
        return True
    if konto.tecken == Konto.TECKEN_SOM_FIL:
        return False
    if konto.typ == Konto.KREDITKORT or konto.importformat in (Konto.AMEX, Konto.SAS):
        # Kortutgivare visar oftast köp som plus. Är de flesta raderna plus är det så i den här filen.
        positiva = sum(1 for r in utdrag.rader if r.belopp > 0)
        return positiva > len(utdrag.rader) / 2
    return False


def _nyckel(konto_id, r, n):
    text = re.sub(r"\s+", " ", r.text.lower()).strip()
    return hashlib.sha256(f"{konto_id}|{r.datum}|{r.belopp}|{text}|{n}".encode()).hexdigest()


@transaction.atomic
def importera(konto, data: bytes, filnamn: str):
    """Läser filen och sparar nya transaktioner. Returnerar Importfil."""
    from .models import Importfil, Kontosaldo, Transaktion, kategorisera

    utdrag = tolka(data, filnamn)
    vand = ska_vanda_tecken(konto, utdrag)
    if vand:
        for r in utdrag.rader:
            r.belopp = -r.belopp
            if r.saldo is not None:
                r.saldo = -r.saldo
    imp = Importfil.objects.create(
        konto=konto, filnamn=filnamn[:255], format=utdrag.format, tecken_vant=vand,
        forsta_datum=min(r.datum for r in utdrag.rader), sista_datum=max(r.datum for r in utdrag.rader))
    forekomst = Counter()
    nya, finns = [], set()
    nycklar = []
    for r in utdrag.rader:
        bas = (r.datum, r.belopp, r.text.lower())
        forekomst[bas] += 1
        nycklar.append(_nyckel(konto.pk, r, forekomst[bas]))
    finns = set(Transaktion.objects.filter(nyckel__in=nycklar).values_list("nyckel", flat=True))
    for r, n in zip(utdrag.rader, nycklar):
        if n in finns:
            continue
        nya.append(Transaktion(konto=konto, datum=r.datum, belopp=r.belopp, text=r.text, valuta=r.valuta,
                               utlandskt_belopp=r.utl_belopp if r.valuta and r.valuta != "SEK" else None,
                               kortinnehavare=r.kortinnehavare,
                               importfil=imp, nyckel=n))
        finns.add(n)
    Transaktion.objects.bulk_create(nya)
    imp.antal_nya, imp.antal_dubbletter = len(nya), len(utdrag.rader) - len(nya)
    imp.save()

    if utdrag.har_saldo:
        med_saldo = [r for r in utdrag.rader if r.saldo is not None]
        if med_saldo:
            sista_dag = max(r.datum for r in med_saldo)
            samma = [r for r in med_saldo if r.datum == sista_dag]
            sista = samma[0] if utdrag.fallande else samma[-1]
            Kontosaldo.objects.update_or_create(konto=konto, datum=sista.datum,
                                                defaults={"saldo": sista.saldo, "kalla": f"Import {filnamn}"[:100]})
    kategorisera(Transaktion.objects.filter(importfil=imp))
    return imp
