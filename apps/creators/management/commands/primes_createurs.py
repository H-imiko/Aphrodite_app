"""Podium mensuel des createurs.

Pourquoi un podium et pas 10 000 Cubis a tous ceux qui publient 5 articles :
dans cette economie, 10 000 Cubis valent environ 25 ventes de stickers. Payer
le volume rendrait la vente inutile et pousserait a publier six images vides.
Ici, la prime recompense ce que la communaute a reellement achete et aime,
avec un budget plafonne par le nombre de places.

Eligibilite (reglages PRIME_MIN_ARTICLES, PRIME_MIN_LIKES) :
  - createur valide, non Divinite, compte actif ;
  - au moins 5 articles actifs publies dans le mois ;
  - et une preuve d'utilite : au moins une vente, ou 5 likes recus.

Classement : Cubis encaisses dans le mois, puis likes, puis nombre d'articles.
Montants : reglage PRIMES_CREATEURS (1er, 2e, 3e).

Par defaut la commande n'ecrit rien. Pour payer :
    python manage.py primes_createurs --mois 2026-11 --appliquer
"""

from datetime import datetime, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.creators.models import PrimeCreateur
from apps.economy.models import Transaction
from apps.economy.services import crediter
from apps.moderation.models import AuditLog
from apps.notifications.services import notifier
from apps.shop.models import Item
from apps.social.models import Like


def _bornes(mois):
    try:
        annee, numero = (int(partie) for partie in mois.split("-"))
        debut = timezone.make_aware(datetime(annee, numero, 1))
    except (ValueError, TypeError):
        raise CommandError("Mois invalide. Format attendu : AAAA-MM.")
    if not 1 <= numero <= 12:
        raise CommandError("Mois invalide. Format attendu : AAAA-MM.")
    if numero == 12:
        fin = timezone.make_aware(datetime(annee + 1, 1, 1))
    else:
        fin = timezone.make_aware(datetime(annee, numero + 1, 1))
    return debut, fin


def _mois_precedent():
    aujourd_hui = timezone.localdate()
    premier = aujourd_hui.replace(day=1)
    precedent = premier - timedelta(days=1)
    return f"{precedent.year:04d}-{precedent.month:02d}"


def _verser(createur, montant, mois, rang):
    """Credite la prime et laisse une trace complete."""
    crediter(createur.pk, montant)
    Transaction.objects.create(
        expediteur=None, destinataire=createur, montant=montant,
        type=Transaction.Type.BONUS_CREATEUR,
        description=f"Prime createur {mois} · {rang}e place"[:200])
    notifier(
        createur, "Prime du mois",
        f"Tu termines {rang}e du mois de {mois} : {montant} Cubis "
        "viennent d'arriver sur ton solde.",
        reverse("transactions"), "prime")
    AuditLog.objects.create(
        action=AuditLog.Action.ENVOI_CUBIS, cible=createur,
        details=f"Prime createur {mois} · {rang}e : {montant}")


class Command(BaseCommand):
    help = ("Classe les createurs du mois et verse le podium. Sans "
            "--appliquer, affiche seulement le resultat.")

    def add_arguments(self, parser):
        parser.add_argument("--mois", default=None,
                            help="Mois a traiter (AAAA-MM). Defaut : le mois "
                                 "precedent.")
        parser.add_argument("--appliquer", action="store_true",
                            help="Verse reellement les primes.")

    def handle(self, *args, **options):
        mois = options["mois"] or _mois_precedent()
        debut, fin = _bornes(mois)
        appliquer = options["appliquer"]
        montants = list(getattr(settings, "PRIMES_CREATEURS",
                                (5000, 2000, 1000)))
        min_articles = getattr(settings, "PRIME_MIN_ARTICLES", 5)
        min_likes = getattr(settings, "PRIME_MIN_LIKES", 5)

        candidats = []
        createurs = (User.objects.filter(createur_valide=True, is_active=True,
                                         est_divinite=False, est_suspendu=False)
                     .order_by("pk"))
        for createur in createurs:
            nb_articles = Item.objects.filter(
                createur=createur, est_actif=True,
                date_creation__gte=debut, date_creation__lt=fin).count()
            if nb_articles < min_articles:
                continue
            ventes = Transaction.objects.filter(
                destinataire=createur, type=Transaction.Type.ACHAT,
                date__gte=debut, date__lt=fin)
            nb_ventes = ventes.count()
            cubis = ventes.aggregate(t=Sum("montant"))["t"] or 0
            nb_likes = Like.objects.filter(
                item__createur=createur,
                date__gte=debut, date__lt=fin).count()
            if nb_ventes < 1 and nb_likes < min_likes:
                continue
            candidats.append({
                "user": createur, "articles": nb_articles,
                "ventes": nb_ventes, "cubis": cubis, "likes": nb_likes})

        if not candidats:
            self.stdout.write(self.style.WARNING(
                f"Aucun createur eligible pour {mois}. Rien a verser."))
            return

        candidats.sort(key=lambda c: (c["cubis"], c["likes"],
                                      c["articles"]), reverse=True)

        versees = 0
        for rang, candidat in enumerate(candidats[:len(montants)], start=1):
            montant = montants[rang - 1]
            createur = candidat["user"]
            self.stdout.write(
                f"{rang}. {createur.pseudo_whatsapp} : {montant} Cubis "
                f"({candidat['articles']} articles, {candidat['cubis']} Cubis "
                f"de ventes, {candidat['likes']} likes)")
            if PrimeCreateur.objects.filter(mois=mois, user=createur).exists():
                continue
            if not appliquer:
                continue
            try:
                with transaction.atomic():
                    PrimeCreateur.objects.get_or_create(
                        mois=mois, user=createur,
                        defaults={"rang": rang, "montant": montant,
                                  "nb_articles": candidat["articles"],
                                  "ventes_cubis": candidat["cubis"],
                                  "nb_likes": candidat["likes"]})
                    _verser(createur, montant, mois, rang)
            except IntegrityError:
                # Deux commandes lancees en meme temps : la contrainte a fait
                # son travail, une seule a paye.
                continue
            versees += 1

        if not appliquer:
            self.stdout.write(self.style.WARNING(
                "Simulation : rien n'a ete verse. Relance avec --appliquer."))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"{versees} prime(s) versee(s) pour {mois}."))
