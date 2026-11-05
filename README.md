# Bitero Budget

Personlig budget och ekonomiuppföljning: konton och kort, importerade transaktioner, budget per kategori och månad,
tillgångar (fastigheter, bostadsrätter, värdepapper, pension, fordon), lån och nettoförmögenhet över tid.

Samma upplägg som Bitero ERP: Django + SQLite, körs lokalt på din dator och används i webbläsaren.

## Starta

**Windows:** dubbelklicka på `start.bat` · **Mac/Linux:** `./start.sh`

Första gången installeras `uv` (om det saknas) samt Python och Django, databasen skapas med standardkategorier
och du väljer användarnamn och lösenord. Webbläsaren öppnas på http://127.0.0.1:8010 (port 8010 så att Bitero ERP
kan köras samtidigt på 8000). Stoppa med Ctrl+C.

- Databasen ligger i `%USERPROFILE%\bitero-budget-data` (Windows) eller `~/bitero-budget-data`, inte i OneDrive.
  Annan plats: miljövariabeln `BUDGET_DATA_DIR`.
- Vid varje start görs en säkerhetskopia (en per dag, de 30 senaste sparas) i `bitero-budget-data/backups`
  eller i `BUDGET_BACKUP_DIR`. Kopiorna är inte krypterade – lägg dem bara på en plats du litar på.
- Utvecklingsläge med Djangos felsidor: `set BUDGET_DEBUG=1` innan `start.bat`.
- Systemet lyssnar bara på 127.0.0.1 och kräver inloggning på alla sidor.

## Kom igång

1. **Konton och kort → Nytt konto**: lägg upp t.ex. lönekontot (Bankkonto), sparkonton,
   American Express och SAS EuroBonus Mastercard (typ Kreditkort). Ange gärna ingående saldo.
2. **Importera filer**: välj konto och ladda upp en eller flera filer (CSV, .xlsx eller .xls).
3. **Att kategorisera**: välj kategori i listan (sparas direkt) eller klicka ✎ för att skapa en regel,
   så kategoriseras liknande köp automatiskt framöver.
4. **Budget → Ny budget**: utgå från förra årets utfall (med uppräkning i %), en annan budget eller en tom.
5. **Tillgångar och lån**: lägg upp bostad, fritidshus, depå, pension och lån. Uppdatera värderingar och
   lånesaldon då och då så blir förmögenhetskurvan rättvisande.

## Import

Kolumnerna letas upp på rubrikerna, så filer från de flesta svenska banker fungerar:

| Källa | Exportera | Tecken |
|---|---|---|
| Bank (Handelsbanken, SEB, Swedbank, Nordea …) | Kontoutdrag/transaktioner → Excel eller CSV | som i filen |
| American Express | amex.se → Kontoutdrag → Ladda ner → Excel/CSV | köp vänds till minus |
| SAS EuroBonus Mastercard | Mina sidor → transaktioner → Excel | köp vänds till minus, reserverade hoppas över |

- Datum, text, belopp, saldo, valuta och utländskt belopp känns igen. Datum som `03/10/2026` tolkas som dag/månad
  om inte kolumnen visar att det är amerikanskt format (månad/dag).
- Dubbletter: samma transaktion importeras aldrig två gånger, så överlappande perioder går bra.
- Saldo: har filen en saldokolumn sparas det senaste saldot som avstämt saldo för kontot.
- Fel fil? Under **Importera filer → Tidigare importer** kan en import ångras.
- För kreditkort vänds tecknet automatiskt om de flesta raderna i filen är plus. Det går att styra per konto
  (Som i filen / Vänd alltid).

## Kategorier och regler

- Kategorityp: **Inkomst**, **Utgift**, **Sparande/amortering** och **Överföring** (räknas inte).
  Betalningen av kreditkortsfakturan från lönekontot och inbetalningen på kortet ska vara Överföring –
  annars räknas köpen två gånger. Standardregler finns för Amex, SEB Kort och SAS EuroBonus.
- Regler matchar i början av ett ord, oavsett skiftläge (`ica` träffar "ICA NARA" men inte "AMERICAN").
  Börja med `^` om texten ska börja så. Högst prioritet vinner, sedan längst mönster.
- En regel kan även koppla transaktionen till en fastighet, så syns driftkostnaderna per år på fastighetens sida.

## Tester

`test.bat` / `./test.sh` kör testerna (egen testdatabas i minnet; din riktiga databas rörs inte).

Riktiga kontoutdrag ska aldrig checkas in: `.gitignore` utesluter databaser, CSV-, Excel- och PDF-filer.
