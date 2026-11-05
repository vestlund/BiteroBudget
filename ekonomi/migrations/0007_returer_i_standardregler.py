from django.db import migrations


def uppdatera(apps, schema_editor):
    from ekonomi.standard import lagg_till_nya_regler

    lagg_till_nya_regler(apps.get_model("ekonomi", "Kategori"), apps.get_model("ekonomi", "Kategoriregel"))


class Migration(migrations.Migration):
    dependencies = [("ekonomi", "0006_regeltext2")]

    operations = [migrations.RunPython(uppdatera, migrations.RunPython.noop)]
