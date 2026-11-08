from django.db import transaction
from django.urls import reverse

from apps.economy.models import Transaction
from apps.economy.services import ErreurEconomie, _verrouiller
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

        verrous = _verrouiller(acheteur, item.createur)
        ach = verrous[acheteur.pk]
        vend = verrous[item.createur_id]

        if InventoryItem.objects.filter(proprietaire=ach, item=item).exists():
            raise ErreurEconomie("Tu possèdes déjà cet article.")

        prix = item.prix_cubis
        if not ach.est_divinite:
            if ach.solde_cubis < prix:
                raise ErreurEconomie("Solde insuffisant.")
            ach.solde_cubis -= prix
            ach.save(update_fields=["solde_cubis"])

        if item.est_officiel:
            # Article officiel : les Cubis sont détruits (anti-inflation)
            if not ach.est_divinite:
                Transaction.objects.create(
                    expediteur=ach, destinataire=None, montant=prix,
                    type=Transaction.Type.DESTRUCTION,
                    description=item.titre)
        else:
            vend.solde_cubis += prix
            vend.save(update_fields=["solde_cubis"])
            Transaction.objects.create(
                expediteur=ach, destinataire=vend, montant=prix,
                type=Transaction.Type.ACHAT, description=item.titre)

        InventoryItem.objects.create(proprietaire=ach, item=item)
        notifier(item.createur, "Nouvel achat",
                 f"{ach.pseudo_whatsapp} a acheté « {item.titre} »"
                 + ("" if item.est_officiel else f" (+{prix} Cubis)"),
                 reverse("article", args=[item.pk]), "vente")
