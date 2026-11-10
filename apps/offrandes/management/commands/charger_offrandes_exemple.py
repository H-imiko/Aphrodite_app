from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from apps.offrandes.models import Offrande

# nom du fichier -> (nom affiché, prix, ordre)
# Images carrées 256x256, PNG transparent, dans static/images/offrandes/.
EXEMPLES = {
    "rose.png": ("Rose", 20, 1),
    "bougie.png": ("Bougie parfumée", 30, 2),
    "coeur.png": ("Cœur de cristal", 45, 3),
    "papillon.png": ("Papillon de nuit", 60, 4),
    "bouquet.png": ("Bouquet de fleurs", 80, 5),
    "bouquet_rose.png": ("Bouquet de roses", 100, 6),
    "ourse.png": ("Ourse en peluche", 130, 7),
    "peluche.png": ("Peluche câline", 160, 8),
    "pendentif.png": ("Pendentif", 200, 9),
    "rose_cristal.png": ("Rose de cristal", 350, 10),
}


class Command(BaseCommand):
    help = "Crée un petit catalogue d'offrandes de départ (sans doublon)."

    def handle(self, *args, **options):
        dossier = Path(settings.BASE_DIR) / "static" / "images" / "offrandes"
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
