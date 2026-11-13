"""Mesure le trou transparent des cadres et decors deja en base.

A executer une fois apres la mise a jour, puis apres chaque ajout de cadre
fait hors de l'application. La commande ne modifie aucune image : elle
enregistre la geometrie du trou, utilisee pour afficher le cadre a la taille
de la photo de profil.
"""

from django.core.management.base import BaseCommand
from PIL import Image

from apps.shop.cadres import mesurer_trou
from apps.shop.models import COSMETIQUES, Item


class Command(BaseCommand):
    help = ("Mesure le trou des cadres et decors deja en base, pour un "
            "affichage aligne sur la photo de profil.")

    def add_arguments(self, parser):
        parser.add_argument("--simuler", action="store_true",
                            help="Affiche les changements sans les enregistrer.")

    def handle(self, *args, **options):
        simuler = options["simuler"]
        corriges = 0
        for item in Item.objects.filter(categorie__in=COSMETIQUES):
            if not item.image:
                continue
            mesure = None
            try:
                item.image.open("rb")
                with Image.open(item.image) as img:
                    img.load()
                    mesure = mesurer_trou(img)
            except Exception as erreur:
                self.stderr.write(
                    f"#{item.pk} {item.titre} : image illisible ({erreur})")
                continue
            finally:
                item.image.close()
            ratio = round(mesure["ratio"], 4) if mesure else None
            if item.ratio_trou == ratio:
                continue
            if simuler:
                self.stdout.write(
                    f"#{item.pk} {item.titre} : ratio {ratio}")
            else:
                Item.objects.filter(pk=item.pk).update(ratio_trou=ratio)
            corriges += 1
        verbe = "a corriger" if simuler else "corrige(s)"
        self.stdout.write(self.style.SUCCESS(f"{corriges} element(s) {verbe}."))
