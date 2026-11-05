"""Förvalda kategorier och regler som skapas första gången. Ändra fritt under Inställningar."""

INKOMST, UTGIFT, SPARANDE, OVERFORING = "inkomst", "utgift", "sparande", "overforing"

KATEGORIER = [
    # (grupp, namn, typ)
    ("Inkomster", "Lön", INKOMST),
    ("Inkomster", "Ersättningar och bidrag", INKOMST),
    ("Inkomster", "Ränta och utdelning", INKOMST),
    ("Inkomster", "Hyresintäkter", INKOMST),
    ("Inkomster", "Skatteåterbäring", INKOMST),
    ("Inkomster", "Övriga inkomster", INKOMST),
    ("Boende", "Hyra/avgift", UTGIFT),
    ("Boende", "Bolåneränta", UTGIFT),
    ("Boende", "El", UTGIFT),
    ("Boende", "Värme, vatten och sophämtning", UTGIFT),
    ("Boende", "Försäkring boende", UTGIFT),
    ("Boende", "Underhåll och reparationer", UTGIFT),
    ("Boende", "Bredband, TV och telefon", UTGIFT),
    ("Mat", "Livsmedel", UTGIFT),
    ("Mat", "Restaurang och café", UTGIFT),
    ("Transport", "Drivmedel och laddning", UTGIFT),
    ("Transport", "Bil (försäkring, skatt, service)", UTGIFT),
    ("Transport", "Parkering och vägavgifter", UTGIFT),
    ("Transport", "Kollektivtrafik och taxi", UTGIFT),
    ("Hushåll", "Kläder och skor", UTGIFT),
    ("Hushåll", "Hem och inredning", UTGIFT),
    ("Hushåll", "Hälsa och apotek", UTGIFT),
    ("Hushåll", "Personlig vård", UTGIFT),
    ("Hushåll", "Barn", UTGIFT),
    ("Fritid", "Nöje och fritid", UTGIFT),
    ("Fritid", "Resor", UTGIFT),
    ("Fritid", "Prenumerationer och appar", UTGIFT),
    ("Fritid", "Gåvor och välgörenhet", UTGIFT),
    ("Finansiellt", "Bankavgifter och räntor", UTGIFT),
    ("Finansiellt", "Övriga försäkringar", UTGIFT),
    ("Finansiellt", "Skatt", UTGIFT),
    ("Övrigt", "Kontantuttag", UTGIFT),
    ("Övrigt", "Övriga utgifter", UTGIFT),
    ("Sparande", "Sparande och investeringar", SPARANDE),
    ("Sparande", "Amortering", SPARANDE),
    ("Överföringar", "Mellan egna konton", OVERFORING),
    ("Överföringar", "Betalning av kreditkort", OVERFORING),
]

REGLER = [
    # (mönster, grupp, namn, endast_utgifter)
    ("ica ", "Mat", "Livsmedel", True), ("coop", "Mat", "Livsmedel", True), ("willys", "Mat", "Livsmedel", True),
    ("hemköp", "Mat", "Livsmedel", True), ("lidl", "Mat", "Livsmedel", True),
    ("city gross", "Mat", "Livsmedel", True), ("mathem", "Mat", "Livsmedel", True),
    ("circle k", "Transport", "Drivmedel och laddning", True), ("okq8", "Transport", "Drivmedel och laddning", True),
    ("preem", "Transport", "Drivmedel och laddning", True), ("ingo ", "Transport", "Drivmedel och laddning", True),
    ("st1 ", "Transport", "Drivmedel och laddning", True),
    ("easypark", "Transport", "Parkering och vägavgifter", True),
    ("parkster", "Transport", "Parkering och vägavgifter", True),
    ("trängselskatt", "Transport", "Parkering och vägavgifter", True),
    ("sl.se", "Transport", "Kollektivtrafik och taxi", True), ("västtrafik", "Transport", "Kollektivtrafik och taxi", True),
    ("skånetrafiken", "Transport", "Kollektivtrafik och taxi", True), ("uber", "Transport", "Kollektivtrafik och taxi", True),
    ("bolt.eu", "Transport", "Kollektivtrafik och taxi", True),
    ("apotek", "Hushåll", "Hälsa och apotek", True), ("kronans", "Hushåll", "Hälsa och apotek", True),
    ("ikea", "Hushåll", "Hem och inredning", True), ("clas ohlson", "Hushåll", "Hem och inredning", True),
    ("bauhaus", "Boende", "Underhåll och reparationer", True), ("byggmax", "Boende", "Underhåll och reparationer", True),
    ("hornbach", "Boende", "Underhåll och reparationer", True), ("k-rauta", "Boende", "Underhåll och reparationer", True),
    ("spotify", "Fritid", "Prenumerationer och appar", True), ("netflix", "Fritid", "Prenumerationer och appar", True),
    ("hbo", "Fritid", "Prenumerationer och appar", True), ("viaplay", "Fritid", "Prenumerationer och appar", True),
    ("disney plus", "Fritid", "Prenumerationer och appar", True), ("apple.com", "Fritid", "Prenumerationer och appar", True),
    ("google *", "Fritid", "Prenumerationer och appar", True),
    ("sas ", "Fritid", "Resor", True), ("norwegian", "Fritid", "Resor", True), ("booking.com", "Fritid", "Resor", True),
    ("hotel", "Fritid", "Resor", True), ("airbnb", "Fritid", "Resor", True),
    ("max ", "Mat", "Restaurang och café", True), ("espresso house", "Mat", "Restaurang och café", True),
    ("foodora", "Mat", "Restaurang och café", True), ("wolt", "Mat", "Restaurang och café", True),
    ("vattenfall", "Boende", "El", True), ("tibber", "Boende", "El", True), ("ellevio", "Boende", "El", True),
    ("e.on", "Boende", "El", True), ("fortum", "Boende", "El", True),
    ("telia", "Boende", "Bredband, TV och telefon", True), ("tele2", "Boende", "Bredband, TV och telefon", True),
    ("telenor", "Boende", "Bredband, TV och telefon", True), ("comviq", "Boende", "Bredband, TV och telefon", True),
    ("bahnhof", "Boende", "Bredband, TV och telefon", True),
    ("bankomat", "Övrigt", "Kontantuttag", True), ("uttag", "Övrigt", "Kontantuttag", True),
    ("skatteverket", "Finansiellt", "Skatt", True),
    ("american express", "Överföringar", "Betalning av kreditkort", False),
    ("amex", "Överföringar", "Betalning av kreditkort", False),
    ("seb kort", "Överföringar", "Betalning av kreditkort", False),
    ("eurobonus", "Överföringar", "Betalning av kreditkort", False),
    ("betalning mottagen", "Överföringar", "Betalning av kreditkort", False),
    ("ränta", "Finansiellt", "Bankavgifter och räntor", True),
    ("årsavgift", "Finansiellt", "Bankavgifter och räntor", True),
]


def skapa_standard(Kategori, Kategoriregel):
    """Skapar standardkategorier och -regler om det inte finns några kategorier ännu."""
    if Kategori.objects.exists():
        return
    kat = {}
    for i, (grupp, namn, typ) in enumerate(KATEGORIER):
        kat[(grupp, namn)] = Kategori.objects.create(grupp=grupp, namn=namn, typ=typ, ordning=i)
    for monster, grupp, namn, utgift in REGLER:
        Kategoriregel.objects.create(monster=monster, kategori=kat[(grupp, namn)], endast_utgifter=utgift)
