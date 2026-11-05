from django.db import migrations


def lagg_till(apps, schema_editor):
    from ekonomi.standard import lagg_till_nya_regler

    lagg_till_nya_regler(apps.get_model("ekonomi", "Kategori"), apps.get_model("ekonomi", "Kategoriregel"))


class Migration(migrations.Migration):
    dependencies = [("ekonomi", "0004_kortinnehavare")]

    operations = [migrations.RunPython(lagg_till, migrations.RunPython.noop)]
