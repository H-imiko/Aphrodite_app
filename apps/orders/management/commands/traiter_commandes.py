from django.core.management.base import BaseCommand

from apps.orders.services import traiter_echeances


class Command(BaseCommand):
    help = "Confirme automatiquement les commandes livrées et expire les demandes sans réponse."

    def handle(self, *args, **options):
        n_auto, n_exp = traiter_echeances()
        self.stdout.write(
            f"{n_auto} commande(s) confirmée(s) automatiquement, "
            f"{n_exp} demande(s) expirée(s).")
