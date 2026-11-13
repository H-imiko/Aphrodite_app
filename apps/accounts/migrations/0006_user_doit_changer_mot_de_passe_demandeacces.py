import shutil
from pathlib import Path

import apps.accounts.models
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def deplacer_photos(apps, schema_editor):
    """Deplace les photos de media/ (public) vers private_media/."""
    User = apps.get_model("accounts", "User")
    source = Path(settings.MEDIA_ROOT)
    cible = Path(settings.PRIVATE_MEDIA_ROOT)
    for utilisateur in User.objects.all().iterator():
        for champ in ("avatar", "banniere"):
            nom = getattr(utilisateur, champ).name if getattr(
                utilisateur, champ) else ""
            if not nom:
                continue
            ancien = source / nom
            nouveau = cible / nom
            if nouveau.exists() or not ancien.exists():
                continue
            nouveau.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(ancien), str(nouveau))


def remettre_photos(apps, schema_editor):
    """Retour arriere : remet les photos dans media/."""
    User = apps.get_model("accounts", "User")
    source = Path(settings.PRIVATE_MEDIA_ROOT)
    cible = Path(settings.MEDIA_ROOT)
    for utilisateur in User.objects.all().iterator():
        for champ in ("avatar", "banniere"):
            nom = getattr(utilisateur, champ).name if getattr(
                utilisateur, champ) else ""
            if not nom:
                continue
            ancien = source / nom
            nouveau = cible / nom
            if nouveau.exists() or not ancien.exists():
                continue
            nouveau.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(ancien), str(nouveau))


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_user_afficher_mature_user_profil_mature"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="doit_changer_mot_de_passe",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="user",
            name="avatar",
            field=models.ImageField(blank=True, null=True,
                                    storage=apps.accounts.models.stockage_prive,
                                    upload_to="avatars/"),
        ),
        migrations.AlterField(
            model_name="user",
            name="banniere",
            field=models.ImageField(blank=True, null=True,
                                    storage=apps.accounts.models.stockage_prive,
                                    upload_to="bannieres/"),
        ),
        migrations.CreateModel(
            name="DemandeAcces",
            fields=[
                ("id", models.BigAutoField(auto_created=True,
                                           primary_key=True, serialize=False,
                                           verbose_name="ID")),
                ("email", models.EmailField(max_length=254)),
                ("traite", models.BooleanField(default=False)),
                ("date", models.DateTimeField(auto_now_add=True)),
                ("date_traitement", models.DateTimeField(blank=True,
                                                         null=True)),
                ("traite_par", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="demandes_traitees",
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Demande d'acces",
                "verbose_name_plural": "Demandes d'acces",
                "ordering": ["-date"],
            },
        ),
        migrations.RunPython(deplacer_photos, remettre_photos),
    ]
