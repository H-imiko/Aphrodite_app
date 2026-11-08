from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from apps.offrandes.models import Offrande

# nom du fichier -> (nom affiché, prix, ordre)
EXEMPLES = {
    "rose.png": ("Rose", 20, 1),
    "coeur.png": ("Cœur de cristal", 35, 2),
    "ourson.png": ("Ourson", 50, 3),
    "etoile.png": ("Étoile dorée", 60, 4),
    "couronne.png": ("Couronne", 120, 5),
    "cube.png": ("Cube d'émeraude", 250, 6),
}


class Command(BaseCommand):
    help = "Crée un petit catalogue d'offrandes de départ (sans doublon)."

    def handle(self, *args, **options):
        dossier = Path(settings.BASE_DIR) / "static" / "offrandes_exemple"
        crees = 0
        for fichier, (nom, prix, ordre) in EXEMPLES.items():
            chemin = dossier / fichier
            if not chemin.exists():
                self.stdout.write(f"Fichier manquant : {chemin}")
                continue
            if Offrande.objects.filter(nom=nom).exists():
                continue
            offrande = Offrande(nom=nom, prix_cubis=prix, ordre=ordre)
            offrande.image.save(fichier, ContentFile(chemin.read_bytes()),
                                save=True)
            crees += 1
        self.stdout.write(f"{crees} offrande(s) créée(s).")
