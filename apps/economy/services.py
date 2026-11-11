import hashlib
import logging
import random
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import F, Q
from django.urls import reverse
from django.utils import timezone

from apps.moderation.models import AuditLog
from apps.moderation.services import journaliser
from apps.notifications.services import notifier
from .models import BonusAppareil, Transaction

# Nombre de bonus quotidiens servis a un meme appareil dans la journee.
PLAFOND_BONUS_PAR_APPAREIL = 3

logger = logging.getLogger(__name__)


class ErreurEconomie(Exception):
    pass


def crediter(user_id, montant):
    """Ajoute des Cubis sans ecraser une ecriture concurrente."""
    if montant <= 0:
        raise ErreurEconomie("Le montant doit être positif.")
    get_user_model().objects.filter(pk=user_id).update(
        solde_cubis=F("solde_cubis") + montant)


def debiter(user_id, montant):
    """Retire des Cubis si et seulement si le solde suffit.

    Renvoie True si le debit a eu lieu, False si le solde etait insuffisant.
    La condition est dans le UPDATE lui-meme : deux achats simultanes ne
    peuvent pas passer tous les deux avec le meme solde, meme sans verrou.
    """
    if montant <= 0:
        raise ErreurEconomie("Le montant doit être positif.")
    return get_user_model().objects.filter(
        pk=user_id, solde_cubis__gte=montant
    ).update(solde_cubis=F("solde_cubis") - montant) == 1


def empreinte_appareil(request):
    """Empreinte technique d'un appareil (adresse + navigateur), jamais affichee.

    Sert uniquement a compter les bonus quotidiens servis a un meme appareil.
    """
    if request is None:
        return "inconnu"
    adresse = (request.META.get("REMOTE_ADDR") or "").strip()
    if not adresse:
        return "inconnu"
    agent = request.META.get("HTTP_USER_AGENT", "")
    return hashlib.sha256(f"{adresse}|{agent}".encode("utf-8")).hexdigest()


def _reserver_creneau(appareil, jour):
    """Autorise un nombre limite de bonus par appareil et par jour."""
    plafond = getattr(settings, "BONUS_PLAFOND_APPAREIL",
                      PLAFOND_BONUS_PAR_APPAREIL)
    if plafond <= 0:
        return True
    try:
        # Savepoint : si le compteur est indisponible (table absente parce que
        # `migrate` n'a pas ete lance, base verrouillee), on peut continuer
        # sans casser la transaction en cours.
        with transaction.atomic():
            try:
                BonusAppareil.objects.get_or_create(empreinte=appareil,
                                                    jour=jour)
            except IntegrityError:
                pass  # deux creations simultanees : la ligne existe deja
            return BonusAppareil.objects.filter(
                empreinte=appareil, jour=jour, nombre__lt=plafond
            ).update(nombre=F("nombre") + 1) == 1
    except DatabaseError:
        # Un compteur anti-farm ne doit jamais empecher un membre de se
        # connecter : on sert le bonus et on previent l'administrateur.
        logger.warning(
            "Compteur de bonus indisponible : plafond par appareil ignore "
            "(migration manquante ?).", exc_info=True)
        return True


def bonus_quotidien(user, appareil="inconnu"):
    """Donne le bonus du jour. Renvoie le montant, ou None si deja recu.

    Le droit au bonus est revendique par une ecriture conditionnelle : sur
    deux connexions simultanees, une seule obtient la journee.
    """
    aujourdhui = timezone.localdate()
    hier = aujourdhui - timedelta(days=1)
    User = get_user_model()
    u = User.objects.filter(pk=user.pk).first()
    if u is None:
        return None

    with transaction.atomic():
        revendique = User.objects.filter(pk=u.pk).filter(
            Q(derniere_connexion_bonus__isnull=True)
            | ~Q(derniere_connexion_bonus=aujourdhui)
        ).update(derniere_connexion_bonus=aujourdhui)
        if revendique != 1:
            return None

        if not _reserver_creneau(appareil, aujourdhui):
            # Compteur d'appareil atteint : on annule la revendication pour
            # que le membre puisse recevoir son bonus le lendemain.
            transaction.set_rollback(True)
            return None

        serie = (u.serie_connexion + 1
                 if u.derniere_connexion_bonus == hier else 1)
        montant = random.randint(15, 25) + min(serie - 1, 7) * 2
        User.objects.filter(pk=u.pk).update(
            solde_cubis=F("solde_cubis") + montant, serie_connexion=serie)
        Transaction.objects.create(
            destinataire=u, montant=montant,
            type=Transaction.Type.CONNEXION,
            description=f"Série de {serie} jour(s)")

    user.refresh_from_db()
    return montant


def envoyer_par_divinite(divinite, destinataire, montant, description=""):
    """Envoi depuis le Trésor : illimité pour Safir, plafonné pour les Gardiennes."""
    if not divinite.est_divinite:
        raise ErreurEconomie("Seules les Divinités peuvent utiliser le Trésor.")
    if montant <= 0:
        raise ErreurEconomie("Le montant doit être positif.")
    if not divinite.is_superuser and montant > settings.LIMITE_ENVOI_GARDIENNE:
        raise ErreurEconomie(
            f"Limite par envoi : {settings.LIMITE_ENVOI_GARDIENNE} Cubis.")
    with transaction.atomic():
        crediter(destinataire.pk, montant)
        Transaction.objects.create(
            expediteur=None, auteur=divinite, destinataire=destinataire,
            montant=montant, type=Transaction.Type.ENVOI_DIVINITE,
            description=description)
        details = f"{montant} Cubis"
        if description:
            details += f" · {description}"
        journaliser(divinite, AuditLog.Action.ENVOI_CUBIS, destinataire,
                    details)
        message = f"{montant} Cubis offerts par les Divinités"
        if description:
            message += f" : {description}"
        notifier(destinataire, "Tu as reçu des Cubis", message,
                 reverse("transactions"), "cubis")


def transferer(expediteur, destinataire, montant, description=""):
    """Transfert entre membres."""
    if montant <= 0:
        raise ErreurEconomie("Le montant doit être positif.")
    if expediteur.pk == destinataire.pk:
        raise ErreurEconomie("Tu ne peux pas t'envoyer des Cubis à toi-même.")
    if expediteur.est_suspendu:
        raise ErreurEconomie("Ton compte est suspendu.")
    with transaction.atomic():
        # Le debit conditionnel est la seule barriere : si deux transferts
        # partent en meme temps avec le meme solde, un seul passe.
        if not debiter(expediteur.pk, montant):
            raise ErreurEconomie("Solde insuffisant.")
        crediter(destinataire.pk, montant)
        Transaction.objects.create(
            expediteur=expediteur, destinataire=destinataire, montant=montant,
            type=Transaction.Type.TRANSFERT, description=description)
        notifier(destinataire, "Cubis reçus",
                 f"{expediteur.pseudo_whatsapp} t'a envoyé {montant} Cubis",
                 reverse("transactions"), "cubis")
