from django.db import IntegrityError, transaction
from django.urls import reverse

from apps.economy.models import Transaction
from apps.economy.services import ErreurEconomie, crediter, debiter
from apps.inventory.models import InventoryItem
from apps.notifications.services import notifier
from .models import Item


def acheter(acheteur, item_id, prix_attendu=None):
    with transaction.atomic():
        try:
            item = Item.objects.select_related("createur").get(
                pk=item_id, est_actif=True)
        except Item.DoesNotExist:
            raise ErreurEconomie("Cet article n'est plus disponible.")
        if prix_attendu is not None and prix_attendu != item.prix_cubis:
            raise ErreurEconomie(
                "Le prix de cet article a changé. Vérifie le nouveau prix.")
        if item.createur_id == acheteur.pk:
            raise ErreurEconomie("C'est ton propre article.")
        if acheteur.est_suspendu:
            raise ErreurEconomie("Ton compte est suspendu.")

        ach = acheteur
        vend = item.createur

        if InventoryItem.objects.filter(proprietaire=ach, item=item).exists():
            raise ErreurEconomie("Tu possèdes déjà cet article.")

        prix = item.prix_cubis
        if not ach.est_divinite and not debiter(ach.pk, prix):
            raise ErreurEconomie("Solde insuffisant.")

        if item.est_officiel:
            # Article officiel : les Cubis sont détruits (anti-inflation)
            if not ach.est_divinite:
                Transaction.objects.create(
                    expediteur=ach, destinataire=None, montant=prix,
                    type=Transaction.Type.DESTRUCTION,
                    description=item.titre)
        else:
            crediter(vend.pk, prix)
            Transaction.objects.create(
                expediteur=ach, destinataire=vend, montant=prix,
                type=Transaction.Type.ACHAT, description=item.titre)

        try:
            with transaction.atomic():
                InventoryItem.objects.create(proprietaire=ach, item=item)
        except IntegrityError:
            # Deux achats simultanes du meme article : le second est annule
            # (et son debit avec lui), il ne paie pas deux fois.
            raise ErreurEconomie("Tu possèdes déjà cet article.")
        notifier(item.createur, "Nouvel achat",
                 f"{ach.pseudo_whatsapp} a acheté « {item.titre} »"
                 + ("" if item.est_officiel else f" (+{prix} Cubis)"),
                 reverse("article", args=[item.pk]), "vente")
