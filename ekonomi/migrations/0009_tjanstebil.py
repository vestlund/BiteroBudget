from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("ekonomi", "0008_hushallsmedlem")]

    operations = [
        migrations.CreateModel(
            name="Tjanstebil",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("namn", models.CharField(max_length=80)),
                ("formansvarde", models.DecimalField(decimal_places=0, max_digits=9, verbose_name="förmånsvärde per månad")),
                ("marginalskatt", models.DecimalField(decimal_places=1, default=Decimal("52"), max_digits=4,
                                                      help_text="Skatten på förmånsvärdet. Cirka 32 % under brytpunkten, 52 % över.",
                                                      verbose_name="marginalskatt (%)")),
                ("nettoloneavdrag", models.DecimalField(decimal_places=0, default=0, max_digits=9,
                                                        help_text="Om du betalar något för bilen ur nettolönen",
                                                        verbose_name="nettolöneavdrag per månad")),
                ("aktiv", models.BooleanField(default=True)),
            ],
            options={"verbose_name": "tjänstebil", "verbose_name_plural": "tjänstebilar", "ordering": ["-aktiv", "namn"]},
        ),
    ]
