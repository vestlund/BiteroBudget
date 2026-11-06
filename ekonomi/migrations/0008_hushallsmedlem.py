from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("ekonomi", "0007_returer_i_standardregler")]

    operations = [
        migrations.CreateModel(
            name="Hushallsmedlem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("namn", models.CharField(max_length=60)),
                ("fodelsear", models.PositiveSmallIntegerField(verbose_name="födelseår")),
            ],
            options={"verbose_name": "hushållsmedlem", "verbose_name_plural": "hushållsmedlemmar",
                     "ordering": ["fodelsear", "namn"]},
        ),
    ]
