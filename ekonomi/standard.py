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
    # (mönster, grupp, namn, endast_utgifter). Returer (plusbelopp) får samma kategori som köpet. Mönstret matchar i början av ett ord; 1–2 tecken = helt ord.
    # Handelsbanken kortar texten till 14 tecken ("American Expre"), så håll mönstren korta.
    # Mat
    ("ica", "Mat", "Livsmedel", False), ("coop", "Mat", "Livsmedel", False), ("willys", "Mat", "Livsmedel", False),
    ("hemköp", "Mat", "Livsmedel", False), ("lidl", "Mat", "Livsmedel", False), ("city gross", "Mat", "Livsmedel", False),
    ("mathem", "Mat", "Livsmedel", False), ("systembolaget", "Mat", "Livsmedel", False),
    ("max burgers", "Mat", "Restaurang och café", False), ("mcd", "Mat", "Restaurang och café", False),
    ("mcdonald", "Mat", "Restaurang och café", False), ("espresso house", "Mat", "Restaurang och café", False),
    ("foodora", "Mat", "Restaurang och café", False), ("wolt", "Mat", "Restaurang och café", False),
    ("pressbyr", "Mat", "Restaurang och café", False), ("7-eleven", "Mat", "Restaurang och café", False),
    ("restaurang", "Mat", "Restaurang och café", False), ("sushi", "Mat", "Restaurang och café", False),
    ("bageri", "Mat", "Restaurang och café", False), ("burger", "Mat", "Restaurang och café", False),
    # Transport
    ("circle k", "Transport", "Drivmedel och laddning", False), ("okq8", "Transport", "Drivmedel och laddning", False),
    ("preem", "Transport", "Drivmedel och laddning", False), ("ingo", "Transport", "Drivmedel och laddning", False),
    ("st1", "Transport", "Drivmedel och laddning", False),
    ("easypark", "Transport", "Parkering och vägavgifter", False), ("parkster", "Transport", "Parkering och vägavgifter", False),
    ("parkman", "Transport", "Parkering och vägavgifter", False), ("aimo", "Transport", "Parkering och vägavgifter", False),
    ("trängselskatt", "Transport", "Parkering och vägavgifter", False),
    ("transportstyre", "Transport", "Parkering och vägavgifter", False),
    ("infrastruktura", "Transport", "Parkering och vägavgifter", False),
    ("fordonsskatt", "Transport", "Bil (försäkring, skatt, service)", False),
    ("biltema", "Transport", "Bil (försäkring, skatt, service)", False),
    ("sl", "Transport", "Kollektivtrafik och taxi", False), ("sl.se", "Transport", "Kollektivtrafik och taxi", False),
    ("västtrafik", "Transport", "Kollektivtrafik och taxi", False), ("skånetrafiken", "Transport", "Kollektivtrafik och taxi", False),
    ("uber", "Transport", "Kollektivtrafik och taxi", False), ("bolt.eu", "Transport", "Kollektivtrafik och taxi", False),
    ("taxi", "Transport", "Kollektivtrafik och taxi", False),
    # Hushåll
    ("apotek", "Hushåll", "Hälsa och apotek", False), ("apotea", "Hushåll", "Hälsa och apotek", False),
    ("kronans", "Hushåll", "Hälsa och apotek", False), ("vårdcentral", "Hushåll", "Hälsa och apotek", False),
    ("folktandvård", "Hushåll", "Hälsa och apotek", False),
    ("kicks", "Hushåll", "Personlig vård", False), ("bokadirekt", "Hushåll", "Personlig vård", False),
    ("hm", "Hushåll", "Kläder och skor", False), ("h&m", "Hushåll", "Kläder och skor", False),
    ("hm.com", "Hushåll", "Kläder och skor", False), ("lindex", "Hushåll", "Kläder och skor", False),
    ("kappahl", "Hushåll", "Kläder och skor", False), ("gina tricot", "Hushåll", "Kläder och skor", False),
    ("ginatricot", "Hushåll", "Kläder och skor", False), ("zalando", "Hushåll", "Kläder och skor", False),
    ("arket", "Hushåll", "Kläder och skor", False), ("eurosko", "Hushåll", "Kläder och skor", False), ("stadium", "Hushåll", "Kläder och skor", False),
    ("ikea", "Hushåll", "Hem och inredning", False), ("clas ohlson", "Hushåll", "Hem och inredning", False),
    ("jula", "Hushåll", "Hem och inredning", False), ("åhléns", "Hushåll", "Hem och inredning", False),
    ("ahlens", "Hushåll", "Hem och inredning", False), ("rusta", "Hushåll", "Hem och inredning", False),
    ("barnbidrag", "Inkomster", "Ersättningar och bidrag", False), ("barnbdr", "Inkomster", "Ersättningar och bidrag", False),
    ("försäkringskassan", "Inkomster", "Ersättningar och bidrag", False),
    # Boende
    ("bauhaus", "Boende", "Underhåll och reparationer", False), ("byggmax", "Boende", "Underhåll och reparationer", False),
    ("hornbach", "Boende", "Underhåll och reparationer", False), ("k-rauta", "Boende", "Underhåll och reparationer", False),
    ("vattenfall", "Boende", "El", False), ("tibber", "Boende", "El", False), ("ellevio", "Boende", "El", False),
    ("e.on", "Boende", "El", False), ("fortum", "Boende", "El", False),
    ("stockholm vatt", "Boende", "Värme, vatten och sophämtning", False),
    ("stadshypotek", "Boende", "Bolåneränta", False), ("sbab", "Boende", "Bolåneränta", False),
    ("telia", "Boende", "Bredband, TV och telefon", False), ("tele2", "Boende", "Bredband, TV och telefon", False),
    ("telenor", "Boende", "Bredband, TV och telefon", False), ("comviq", "Boende", "Bredband, TV och telefon", False),
    ("hallon", "Boende", "Bredband, TV och telefon", False), ("bahnhof", "Boende", "Bredband, TV och telefon", False),
    # Fritid
    ("spotify", "Fritid", "Prenumerationer och appar", False), ("netflix", "Fritid", "Prenumerationer och appar", False),
    ("hbo", "Fritid", "Prenumerationer och appar", False), ("hbomax", "Fritid", "Prenumerationer och appar", False),
    ("viaplay", "Fritid", "Prenumerationer och appar", False), ("disney", "Fritid", "Prenumerationer och appar", False),
    ("apple.com", "Fritid", "Prenumerationer och appar", False), ("google", "Fritid", "Prenumerationer och appar", False),
    ("amazon prime", "Fritid", "Prenumerationer och appar", False), ("kindle", "Fritid", "Prenumerationer och appar", False),
    ("storytel", "Fritid", "Prenumerationer och appar", False), ("youtube", "Fritid", "Prenumerationer och appar", False),
    ("sas", "Fritid", "Resor", False), ("flysas", "Fritid", "Resor", False), ("norwegian", "Fritid", "Resor", False),
    ("booking.com", "Fritid", "Resor", False), ("hotel", "Fritid", "Resor", False), ("airbnb", "Fritid", "Resor", False),
    ("scandic", "Fritid", "Resor", False), ("sj", "Fritid", "Resor", False),
    ("akademibokhande", "Fritid", "Nöje och fritid", False), ("adlibris", "Fritid", "Nöje och fritid", False),
    ("filmstaden", "Fritid", "Nöje och fritid", False),
    ("ticketmaster", "Fritid", "Nöje och fritid", False), ("gröna lund", "Fritid", "Nöje och fritid", False),
    # Finansiellt och övrigt
    ("trygg-hansa", "Finansiellt", "Övriga försäkringar", False), ("folksam", "Finansiellt", "Övriga försäkringar", False),
    ("länsförsäkr", "Finansiellt", "Övriga försäkringar", False), ("if skade", "Finansiellt", "Övriga försäkringar", False),
    ("skatteverket", "Finansiellt", "Skatt", False),
    ("baserbjudande", "Finansiellt", "Bankavgifter och räntor", False),
    ("ränta", "Finansiellt", "Bankavgifter och räntor", True),
    ("dröjsmålsränta", "Finansiellt", "Bankavgifter och räntor", True),
    ("årsavgift", "Finansiellt", "Bankavgifter och räntor", False),
    ("år-/mån avg", "Finansiellt", "Bankavgifter och räntor", False),
    ("kontantuttagsavgift", "Finansiellt", "Bankavgifter och räntor", False),
    ("bankomat", "Övrigt", "Kontantuttag", True), ("uttag", "Övrigt", "Kontantuttag", True),
    ("lön", "Inkomster", "Lön", False),
    ("avanza", "Sparande", "Sparande och investeringar", False),
    ("nordnet", "Sparande", "Sparande och investeringar", False),
    # Kreditkort: betalning från banken och inbetalning på kortet räknas inte (annars dubbelräknas köpen)
    ("american exp", "Överföringar", "Betalning av kreditkort", False),
    ("amex", "Överföringar", "Betalning av kreditkort", False),
    ("seb kort", "Överföringar", "Betalning av kreditkort", False),
    ("eurobonus", "Överföringar", "Betalning av kreditkort", False),
    ("bank norwegian", "Överföringar", "Betalning av kreditkort", False),
    ("sas eurobonus", "Överföringar", "Betalning av kreditkort", False),
    ("betalning mottagen", "Överföringar", "Betalning av kreditkort", False),
    ("^inbetalning", "Överföringar", "Betalning av kreditkort", False),
]


def skapa_standard(Kategori, Kategoriregel):
    """Skapar standardkategorier och -regler om det inte finns några kategorier ännu."""
    if Kategori.objects.exists():
        return
    kat = {}
    for i, (grupp, namn, typ) in enumerate(KATEGORIER):
        kat[(grupp, namn)] = Kategori.objects.create(grupp=grupp, namn=namn, typ=typ, ordning=i)
    for monster, grupp, namn, utgift in REGLER:
        k = kat[(grupp, namn)]
        Kategoriregel.objects.create(monster=monster, kategori=k, endast_utgifter=utgift,
                                     endast_inkomster=k.typ == INKOMST)


def lagg_till_nya_regler(Kategori, Kategoriregel):
    """Lägger till standardregler som saknas (för befintliga databaser). Rör inte dina egna regler."""
    if not Kategori.objects.exists():
        return
    for gammalt, nytt in (("american express", "american exp"), ("ica ", "ica"), ("max ", "max"), ("sas ", "sas"),
                          ("ingo ", "ingo"), ("st1 ", "st1"), ("google *", "google"), ("disney plus", "disney")):
        Kategoriregel.objects.filter(monster=gammalt).update(monster=nytt)
    # Returer ska få samma kategori som köpet: släpp "bara utgifter" där standardlistan inte kräver det
    for monster, grupp, namn, utgift in REGLER:
        if not utgift:
            Kategoriregel.objects.filter(monster=monster, kategori__grupp=grupp, kategori__namn=namn,
                                         endast_utgifter=True).update(endast_utgifter=False)
    finns = set(Kategoriregel.objects.values_list("monster", flat=True))
    for monster, grupp, namn, utgift in REGLER:
        kat = Kategori.objects.filter(grupp=grupp, namn=namn).first()
        if kat and monster not in finns:
            Kategoriregel.objects.create(monster=monster, kategori=kat, endast_utgifter=utgift,
                                         endast_inkomster=kat.typ == INKOMST)
            finns.add(monster)
