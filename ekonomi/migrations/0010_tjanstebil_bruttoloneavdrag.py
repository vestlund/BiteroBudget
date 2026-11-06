from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("ekonomi", "0009_tjanstebil")]

    operations = [
        migrations.RenameField("tjanstebil", "nettoloneavdrag", "bruttoloneavdrag"),
        migrations.AlterField(
            model_name="tjanstebil",
            name="bruttoloneavdrag",
            field=models.DecimalField(decimal_places=0, default=0, max_digits=9,
                                      help_text="Det du avstår av bruttolönen för bilen (ofta lika med förmånsvärdet)",
                                      verbose_name="bruttolöneavdrag per månad"),
        ),
    ]
