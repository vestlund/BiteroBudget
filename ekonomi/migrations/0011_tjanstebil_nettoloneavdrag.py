from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("ekonomi", "0010_tjanstebil_bruttoloneavdrag")]

    operations = [
        migrations.AddField(
            model_name="tjanstebil",
            name="nettoloneavdrag",
            field=models.DecimalField(decimal_places=0, default=0, max_digits=9,
                                      help_text="Det du betalar för bilen ur nettolönen – minskar förmånsvärdet",
                                      verbose_name="nettolöneavdrag per månad"),
        ),
        migrations.AlterField(
            model_name="tjanstebil",
            name="bruttoloneavdrag",
            field=models.DecimalField(decimal_places=0, default=0, max_digits=9,
                                      help_text="Det du avstår av bruttolönen för bilen (löneväxling)",
                                      verbose_name="bruttolöneavdrag per månad"),
        ),
    ]
