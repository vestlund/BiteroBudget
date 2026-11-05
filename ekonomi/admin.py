from django.contrib import admin

from .models import Importfil, Kategori, Kategoriregel, Konto, Kontosaldo, Transaktion

admin.site.site_header = "Bitero Budget"
admin.site.site_title = "Bitero Budget"


@admin.register(Konto)
class KontoAdmin(admin.ModelAdmin):
    list_display = ["namn", "typ", "institut", "aktiv"]


@admin.register(Kategori)
class KategoriAdmin(admin.ModelAdmin):
    list_display = ["grupp", "namn", "typ", "aktiv"]
    list_filter = ["typ", "grupp"]


@admin.register(Kategoriregel)
class KategoriregelAdmin(admin.ModelAdmin):
    list_display = ["monster", "kategori", "konto", "prioritet"]


@admin.register(Transaktion)
class TransaktionAdmin(admin.ModelAdmin):
    list_display = ["datum", "konto", "text", "belopp", "kategori"]
    list_filter = ["konto", "kategori"]
    search_fields = ["text"]


admin.site.register(Kontosaldo)
admin.site.register(Importfil)
