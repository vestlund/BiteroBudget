from django.contrib import admin
from django.urls import path

from budget import views as b
from ekonomi import views as e
from tillgangar import views as t

urlpatterns = [
    path("", e.oversikt, name="oversikt"),
    # transaktioner och import
    path("transaktioner/", e.transaktioner, name="transaktioner"),
    path("transaktioner/ny/", e.transaktion, name="transaktion_ny"),
    path("transaktioner/<int:pk>/", e.transaktion, name="transaktion"),
    path("transaktioner/<int:pk>/kategori/", e.satt_kategori, name="satt_kategori"),
    path("importera/", e.importsida, name="importera"),
    path("importera/<int:pk>/angra/", e.import_angra, name="import_angra"),
    # konton
    path("konton/", e.konton, name="konton"),
    path("konton/nytt/", e.konto_form, name="konto_nytt"),
    path("konton/<int:pk>/", e.konto, name="konto"),
    path("konton/<int:pk>/andra/", e.konto_form, name="konto_andra"),
    # budget
    path("budget/", b.uppfoljning, name="budget_aktuell"),
    path("budget/budgetar/", b.lista, name="budgetar"),
    path("budget/ny/", b.ny, name="budget_ny"),
    path("budget/<int:pk>/", b.uppfoljning, name="budget_uppfoljning"),
    path("budget/<int:pk>/redigera/", b.redigera, name="budget_redigera"),
    path("budget/<int:pk>/radera/", b.radera, name="budget_radera"),
    # tillgångar, fastigheter och lån
    path("tillgangar/", t.lista, name="tillgangar"),
    path("tillgangar/ny/", t.tillgang_form, name="tillgang_ny"),
    path("tillgangar/<int:pk>/", t.tillgang, name="tillgang"),
    path("tillgangar/<int:pk>/andra/", t.tillgang_form, name="tillgang_andra"),
    path("tillgangar/formogenhet/", t.formogenhet, name="formogenhet"),
    path("lan/nytt/", t.lan_form, name="lan_nytt"),
    path("lan/<int:pk>/", t.lan, name="lan"),
    path("lan/<int:pk>/andra/", t.lan_form, name="lan_andra"),
    # inställningar
    path("installningar/kategorier/", e.kategorier, name="kategorier"),
    path("installningar/kategorier/ny/", e.kategori_form, name="kategori_ny"),
    path("installningar/kategorier/<int:pk>/", e.kategori_form, name="kategori_andra"),
    path("installningar/regler/", e.regler, name="regler"),
    path("installningar/regler/ny/", e.regel_form, name="regel_ny"),
    path("installningar/regler/<int:pk>/", e.regel_form, name="regel_andra"),
    path("installningar/regler/kor/", e.kor_regler, name="kor_regler"),
    path("installningar/regler/importera/", e.regler_importera, name="regler_importera"),
    path("installningar/regler/export.xlsx", e.regler_exportera, name="regler_exportera"),
    path("admin/", admin.site.urls),
]
