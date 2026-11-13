from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shop", "0003_item_extrait_item_fichier_alter_item_categorie"),
    ]

    operations = [
        migrations.AddField(
            model_name="item",
            name="ratio_trou",
            field=models.FloatField(blank=True, editable=False, null=True),
        ),
    ]
