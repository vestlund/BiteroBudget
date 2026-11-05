"""MCP-server som låter Claude läsa och uppdatera Bitero Budget. Startas av Claude-appen med `manage.py mcp`."""

import functools

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations

from . import verktyg as v

INSTRUKTIONER = """Bitero Budget är användarens privatekonomi: konton och kort (Handelsbanken, SAS Amex Premium,
SAS EuroBonus Mastercard från SEB Kort), importerade transaktioner, kategorier, budget, tillgångar och lån.

Belopp: minus = pengar ut, plus = pengar in (även på kreditkort, där köp är minus). Kategorityper:
inkomst, utgift, sparande (sparande och amortering) och overforing (mellan egna konton och betalning av
kreditkortsfakturan – räknas inte i budgeten, annars dubbelräknas köpen).

Kategorisera:
- Börja med `okategoriserade_grupperade` (en rad per text) eller `transaktioner` med okategoriserade=true.
- Återkommande text (butik, Swish-mottagare): `kategorisera_text` – sätter kategori på alla med texten och
  sparar en regel så att framtida importer får samma kategori. exakt=true för Swish-namn och egna meddelanden,
  exakt=false för butiker vars text varierar ("ICA NARA ALVSJO 957..." → text "ica").
- Enstaka transaktioner: `satt_kategori` med id:n.
- Regler matchar i början av ett ord (1–2 tecken = helt ord), "^" = texten börjar med, "citattecken" = exakt.
  Längst mönster vinner, sedan högst prioritet. Handelsbanken kortar texter till 14 tecken.
- Saknas en kategori: `ny_kategori`. Fråga användaren innan du lägger till många nya kategorier.
- Kategorin "Övrigt – Att utreda" innehåller poster användaren behöver förklara. Fråga om dem.

Övrigt:
- `oversikt`, `konton`, `utfall` (budget mot utfall), `budget`, `tillgangar` för att läsa.
- `importera_fil` läser ett kontoutdrag från en sökväg på datorn (CSV/Excel) till ett konto.
- `satt_kontosaldo` för avstämt saldo (kreditkortsskuld som minus).
- `spara_budget` för budgetbelopp per kategori (positiva tal; per månad eller årsbelopp).
- `ny_vardering`, `nytt_lanesaldo`, `ny_tillgang`, `nytt_lan` för tillgångar och lån.

Transaktionernas datum, text och belopp kommer från banken och ändras aldrig. Sammanfatta vad du tänker ändra
innan större ändringar (många transaktioner eller regler). Användaren ser allt på http://127.0.0.1:8010."""

server = MCPServer("Bitero Budget", instructions=INSTRUKTIONER)

LAS = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)
SKRIV = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False)
TA_BORT = ToolAnnotations(read_only_hint=False, destructive_hint=True, idempotent_hint=True, open_world_hint=False)


def _verktyg(fn):
    """Gör fel till läsbara meddelanden och stänger gamla databasanslutningar (servern körs länge)."""
    @functools.wraps(fn)
    def inre(*args, **kwargs):
        from django.core.exceptions import ValidationError
        from django.db import close_old_connections

        close_old_connections()
        try:
            return fn(*args, **kwargs)
        except v.VerktygsFel as e:
            raise ToolError(str(e)) from e
        except ValidationError as e:
            raise ToolError("; ".join(e.messages)) from e
    return inre


# ------------------------------------------------------------------ läsa

@server.tool(annotations=LAS, structured_output=False)
@_verktyg
def oversikt() -> dict:
    """Nettoförmögenhet, kontosaldon, månadens och årets inkomster/utgifter mot budget och antal okategoriserade."""
    return v.oversikt()


@server.tool(annotations=LAS, structured_output=False)
@_verktyg
def konton() -> list:
    """Konton och kort med id, typ, saldo i dag, senaste avstämda saldo och senaste transaktion."""
    return v.konton()


@server.tool(annotations=LAS, structured_output=False)
@_verktyg
def kategorier() -> list:
    """Alla kategorier (id, 'Grupp – Namn', typ) och antal transaktioner i år."""
    return v.kategorier()


@server.tool(annotations=LAS, structured_output=False)
@_verktyg
def transaktioner(sok: str = "", konto: str = "", kategori: str = "", grupp: str = "", fran: str = "",
                  till: str = "", okategoriserade: bool = False, kortinnehavare: str = "", tillgang: str = "",
                  min_belopp: str = "", max_belopp: str = "", max_antal: int = 100) -> dict:
    """Sök transaktioner (nyast först). Datum ÅÅÅÅ-MM-DD. konto/kategori/tillgang som id eller namn.

    Belopp: minus = utgift. max_belopp="-1000" ger utgifter större än 1 000 kr. Högst 500 rader.
    """
    return v.transaktioner(sok, konto, kategori, grupp, fran, till, okategoriserade, kortinnehavare, tillgang,
                           min_belopp, max_belopp, max_antal)


@server.tool(annotations=LAS, structured_output=False)
@_verktyg
def okategoriserade_grupperade(max_antal: int = 100) -> dict:
    """Okategoriserade transaktioner grupperade på text, med antal och summa. Börja här vid kategorisering."""
    return v.okategoriserade_grupperade(max_antal)


@server.tool(annotations=LAS, structured_output=False)
@_verktyg
def utfall(ar: int | None = None, manad: int | None = None) -> dict:
    """Utfall och budget per kategori för ett år, valfritt för en månad (1–12). Utan månad: utfall per månad."""
    return v.utfall(ar, manad)


@server.tool(annotations=LAS, structured_output=False)
@_verktyg
def regler(sok: str = "") -> list:
    """Kategoriseringsregler, valfritt filtrerade på mönster eller kategori."""
    return v.regler(sok)


@server.tool(annotations=LAS, structured_output=False)
@_verktyg
def budget(ar: int | None = None) -> dict:
    """Årets budget (eller angivet år) med belopp per kategori och månad."""
    return v.budget(ar)


@server.tool(annotations=LAS, structured_output=False)
@_verktyg
def tillgangar() -> dict:
    """Tillgångar (fastigheter, värdepapper m.m.) med senaste värdering, och lån med skuld och ränta."""
    return v.tillgangar()


# ------------------------------------------------------------------ kategorisera

@server.tool(annotations=SKRIV, structured_output=False)
@_verktyg
def kategorisera_text(text: str, kategori: str, exakt: bool = True, galler: str = "alla",
                      skapa_regel: bool = True, tillgang: str = "") -> dict:
    """Sätt kategori på alla transaktioner med en text och spara en regel för framtida importer.

    exakt=true: hela texten måste stämma (Swish-namn, egna meddelanden). exakt=false: texten matchar i början av
    ett ord (butiker). galler: alla / utgifter / inkomster. tillgang: koppla också till en tillgång (t.ex. huset).
    """
    return v.kategorisera_text(text, kategori, exakt, galler, skapa_regel, tillgang or None)


@server.tool(annotations=SKRIV, structured_output=False)
@_verktyg
def satt_kategori(transaktion_ids: list[int], kategori: str, tillgang: str = "", anteckning: str | None = None) -> dict:
    """Sätt kategori på enskilda transaktioner (id från transaktioner). kategori="ingen" tar bort kategorin."""
    return v.satt_kategori(transaktion_ids, kategori, tillgang or None, anteckning)


@server.tool(annotations=SKRIV, structured_output=False)
@_verktyg
def dela_transaktion(transaktion_id: int, belopp: str, kategori: str, anteckning: str | None = None) -> dict:
    """Dela en transaktion i två: `belopp` (positivt) flyttas till en ny rad med `kategori`, resten blir kvar.

    T.ex. en bolånebetalning som är både ränta och amortering. Saldot påverkas inte.
    """
    return v.dela_transaktion(transaktion_id, belopp, kategori, anteckning)


@server.tool(annotations=SKRIV, structured_output=False)
@_verktyg
def ny_kategori(grupp: str, namn: str, typ: str = "utgift") -> dict:
    """Skapa en kategori. typ: inkomst, utgift, sparande eller overforing."""
    return v.ny_kategori(grupp, namn, typ)


@server.tool(annotations=SKRIV, structured_output=False)
@_verktyg
def ny_regel(monster: str, kategori: str, galler: str = "alla", konto: str = "", tillgang: str = "",
             prioritet: int = 0, kor_nu: bool = True) -> dict:
    """Skapa eller uppdatera en kategoriseringsregel. kor_nu kategoriserar okategoriserade transaktioner direkt."""
    return v.ny_regel(monster, kategori, galler, konto or None, tillgang or None, prioritet, kor_nu)


@server.tool(annotations=TA_BORT, structured_output=False)
@_verktyg
def ta_bort_regel(regel_id: int) -> dict:
    """Ta bort en kategoriseringsregel (id från regler)."""
    return v.ta_bort_regel(regel_id)


@server.tool(annotations=SKRIV, structured_output=False)
@_verktyg
def kor_regler(skriv_over: bool = False) -> dict:
    """Kör reglerna på okategoriserade transaktioner, eller på alla (skriv_over) utom manuellt kategoriserade."""
    return v.kor_regler(skriv_over)


# ------------------------------------------------------------------ import, saldon, budget, tillgångar

@server.tool(annotations=SKRIV, structured_output=False)
@_verktyg
def importera_fil(sokvag: str, konto: str) -> dict:
    """Importera ett kontoutdrag (CSV/Excel) från en sökväg på datorn. Dubbletter hoppas över automatiskt."""
    return v.importera_fil(sokvag, konto)


@server.tool(annotations=SKRIV, structured_output=False)
@_verktyg
def satt_kontosaldo(konto: str, datum: str, saldo: str) -> dict:
    """Spara ett avstämt saldo för ett konto ett visst datum. Kreditkortsskuld anges som minus."""
    return v.satt_kontosaldo(konto, datum, saldo)


@server.tool(annotations=SKRIV, structured_output=False)
@_verktyg
def spara_budget(ar: int, poster: list[dict], namn: str = "Budget", ersatt: bool = False) -> dict:
    """Spara budgetbelopp (positiva tal) för ett år.

    poster: [{"kategori": "Mat – Livsmedel", "per_manad": [12 belopp]}] eller [{"kategori": "El", "ar": 18000}].
    Övriga kategorier i budgeten behålls, om inte ersatt=true.
    """
    return v.spara_budget(ar, poster, namn, ersatt)


@server.tool(annotations=SKRIV, structured_output=False)
@_verktyg
def ny_tillgang(namn: str, typ: str, kopdatum: str = "", kopeskilling: str = "", adress: str = "",
                agarandel: str = "100", beskrivning: str = "") -> dict:
    """Lägg upp en tillgång. typ: villa, bostadsratt, fritidshus, tomt, hyresfastighet, vardepapper, pension,
    fordon eller ovrigt."""
    return v.ny_tillgang(namn, typ, kopdatum, kopeskilling or None, adress, agarandel, beskrivning)


@server.tool(annotations=SKRIV, structured_output=False)
@_verktyg
def ny_vardering(tillgang: str, datum: str, varde: str, kalla: str = "") -> dict:
    """Spara en värdering av en tillgång (hela värdet; ägarandelen räknas fram automatiskt)."""
    return v.ny_vardering(tillgang, datum, varde, kalla)


@server.tool(annotations=SKRIV, structured_output=False)
@_verktyg
def nytt_lan(namn: str, skuld: str, typ: str = "bolan", langivare: str = "", tillgang: str = "",
             ranta: str = "", bunden_till: str = "", amortering_per_manad: str = "", datum: str = "") -> dict:
    """Lägg upp ett lån med nuvarande skuld. typ: bolan, billan, blanco, csn eller ovrigt."""
    return v.nytt_lan(namn, skuld, typ, langivare, tillgang or None, ranta, bunden_till, amortering_per_manad, datum)


@server.tool(annotations=SKRIV, structured_output=False)
@_verktyg
def nytt_lanesaldo(lan: str, datum: str, skuld: str, ranta: str = "") -> dict:
    """Spara lånets skuld (och ev. ny ränta) ett visst datum."""
    return v.nytt_lanesaldo(lan, datum, skuld, ranta)
