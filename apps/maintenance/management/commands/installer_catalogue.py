"""Installe le catalogue de depart en une seule commande.

Rien de tout cela n'est versionne (images en base, objets de jeu) : sur une
installation neuve, les offrandes et le cadre sont absents tant que cette
commande n'a pas tourne. C'est la cause des « catalogues vides ».
"""

from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from apps.inventory.models import Equipement, InventoryItem
from apps.shop.models import Item

CADRE = Path("static") / "images" / "cadres" / "cadre_noir.png"
TITRE_CADRE = "Cadre noir"


class Command(BaseCommand):
    help = ("Installe les 10 offrandes de depart et le cadre noir, puis "
            "equipe le cadre sur le profil de la proprietaire.")

    def add_arguments(self, parser):
        parser.add_argument(
            "--proprietaire", default=None, help=
            "Email du compte qui recoit le cadre (par defaut : la premiere "
            "Divinite, sinon le premier superutilisateur).")

    def _proprietaire(self, email):
        """Compte a qui le cadre est offert : Divinite, sinon superutilisateur."""
        User = get_user_model()
        if email:
            compte = User.objects.filter(email__iexact=email.strip()).first()
            if compte is None:
                raise CommandError(f"Aucun compte pour l'email {email}.")
            return compte
        return (User.objects.filter(est_divinite=True).order_by("pk").first()
                or User.objects.filter(is_superuser=True)
                .order_by("pk").first())

    def handle(self, *args, **options):
        call_command("charger_offrandes_exemple")

        proprietaire = self._proprietaire(options["proprietaire"])
        if proprietaire is None:
            raise CommandError(
                "Aucun compte proprietaire : cree la tienne avec "
                "'python manage.py createsuperuser', ou precise "
                "--proprietaire ton@email.")

        item = Item.objects.filter(titre=TITRE_CADRE).first()
        if item is None:
            chemin = Path(settings.BASE_DIR) / CADRE
            if not chemin.exists():
                raise CommandError(f"Fichier introuvable : {chemin}")
            item = Item(titre=TITRE_CADRE, categorie="cadre",
                        description="Cadre offert par le créateur.",
                        prix_cubis=0, est_actif=True,
                        createur=proprietaire)
            with chemin.open("rb") as fichier:
                item.image.save("cadre_noir.png", File(fichier), save=False)
            item.save()
            self.stdout.write(self.style.SUCCESS(
                "Cadre noir ajoute a la boutique."))
        else:
            self.stdout.write("Cadre noir deja present.")

        # Mesure le trou du cadre pour que l'affichage soit aligne sur la
        # photo de profil (utile aussi si le cadre existait deja).
        call_command("normaliser_cadres", verbosity=0)

        InventoryItem.objects.get_or_create(proprietaire=proprietaire,
                                            item=item)
        equipement, _ = Equipement.objects.get_or_create(user=proprietaire)
        if equipement.cadre_id != item.pk:
            equipement.cadre = item
            equipement.save(update_fields=["cadre"])
        self.stdout.write(self.style.SUCCESS(
            f"Cadre equipe sur le profil de {proprietaire.pseudo_whatsapp}."))
