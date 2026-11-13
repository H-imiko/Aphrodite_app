from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("creators", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PrimeCreateur",
            fields=[
                ("id", models.BigAutoField(auto_created=True,
                                           primary_key=True, serialize=False,
                                           verbose_name="ID")),
                ("mois", models.CharField(max_length=7)),
                ("rang", models.PositiveSmallIntegerField()),
                ("montant", models.PositiveIntegerField()),
                ("nb_articles", models.PositiveIntegerField(default=0)),
                ("ventes_cubis", models.PositiveIntegerField(default=0)),
                ("nb_likes", models.PositiveIntegerField(default=0)),
                ("date", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="primes_createur",
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Prime createur",
                "verbose_name_plural": "Primes createurs",
                "ordering": ["-mois", "rang"],
            },
        ),
        migrations.AddConstraint(
            model_name="primecreateur",
            constraint=models.UniqueConstraint(
                fields=("mois", "user"),
                name="unique_prime_createur_mois"),
        ),
    ]
