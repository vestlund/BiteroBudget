from django.db import migrations


def skapa(apps, schema_editor):
    from ekonomi.standard import skapa_standard

    skapa_standard(apps.get_model("ekonomi", "Kategori"), apps.get_model("ekonomi", "Kategoriregel"))


class Migration(migrations.Migration):
    dependencies = [("ekonomi", "0001_initial")]

    operations = [migrations.RunPython(skapa, migrations.RunPython.noop)]
