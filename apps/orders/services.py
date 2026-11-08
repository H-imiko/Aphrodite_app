from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.economy.models import Transaction
from apps.economy.services import ErreurEconomie, _verrouiller
from apps.moderation.models import AuditLog
from apps.moderation.services import journaliser
from apps.notifications.services import notifier, notifier_divinites
from .models import Order, OrderMessage

S = Order.Statut
PRIX_MAX = 1_000_000
MAX_ACTIVES = 10
ACTIVES = (S.DEMANDE, S.EN_COURS, S.LIVREE, S.LITIGE)


def _delai_confirmation():
    return getattr(settings, "DELAI_CONFIRMATION_JOURS", 5)


def _delai_demande():
    return getattr(settings, "DELAI_DEMANDE_JOURS", 7)


def _lien(c):
    return reverse("commande", args=[c.pk])


def _systeme(commande, texte):
    OrderMessage.objects.create(
        commande=commande, auteur=None, texte=texte[:1000], systeme=True)


def _charger(order_id):
    try:
        return Order.objects.select_for_update().get(pk=order_id)
    except Order.DoesNotExist:
        raise ErreurEconomie("Commande introuvable.")


def _liberer(c, texte):
    """Verse les Cubis bloqués au Créateur et termine la commande."""
    vend = _verrouiller(c.vendeur)[c.vendeur_id]
    vend.solde_cubis += c.prix_cubis
    vend.save(update_fields=["solde_cubis"])
    Transaction.objects.create(
        expediteur=None, destinataire=vend, montant=c.prix_cubis,
        type=Transaction.Type.LIBERATION, description=c.titre[:150])
    c.statut = S.TERMINEE
    c.date_fin = timezone.now()
    c.save()
    _systeme(c, texte)
    notifier(vend, "Paiement reçu",
             f"+{c.prix_cubis} Cubis pour la commande « {c.titre} »",
             _lien(c), "commande")


def _rembourser(c, statut, texte):
    """Rend les Cubis bloqués à l'acheteur."""
    ach = _verrouiller(c.acheteur)[c.acheteur_id]
    ach.solde_cubis += c.prix_cubis
    ach.save(update_fields=["solde_cubis"])
    Transaction.objects.create(
        expediteur=None, destinataire=ach, montant=c.prix_cubis,
        type=Transaction.Type.REMBOURSEMENT, description=c.titre[:150])
    c.statut = statut
    c.date_fin = timezone.now()
    c.save()
    _systeme(c, texte)
    notifier(ach, "Commande remboursée",
             f"+{c.prix_cubis} Cubis rendus pour « {c.titre} »",
             _lien(c), "commande")


def creer_demande(acheteur, vendeur, titre, description, prix):
    titre = (titre or "").strip()
    description = (description or "").strip()
    if acheteur.est_divinite:
        raise ErreurEconomie(
            "Les Divinités récompensent via le Trésor et ne passent pas "
            "de commande.")
    if acheteur.est_suspendu:
        raise ErreurEconomie("Ton compte est suspendu.")
    if vendeur.pk == acheteur.pk:
        raise ErreurEconomie("Tu ne peux pas te commander à toi-même.")
    if not (vendeur.peut_publier and vendeur.is_active
            and not vendeur.est_suspendu):
        raise ErreurEconomie("Ce membre n'accepte pas de commandes.")
    if not 3 <= len(titre) <= 100:
        raise ErreurEconomie("Le titre doit faire entre 3 et 100 caractères.")
    if not 10 <= len(description) <= 2000:
        raise ErreurEconomie(
            "Décris ta demande (10 à 2000 caractères) pour que le Créateur "
            "puisse t'aider.")
    if not 1 <= prix <= PRIX_MAX:
        raise ErreurEconomie(f"Le prix doit être entre 1 et {PRIX_MAX} Cubis.")
    if acheteur.solde_cubis < prix:
        raise ErreurEconomie(
            "Solde insuffisant : il te faut ce montant disponible, il sera "
            "bloqué quand le Créateur accepte.")
    with transaction.atomic():
        if Order.objects.filter(
                acheteur=acheteur, statut__in=ACTIVES).count() >= MAX_ACTIVES:
            raise ErreurEconomie(
                f"Tu as déjà {MAX_ACTIVES} commandes en cours. Termine-en "
                "avant d'en passer une autre.")
        if Order.objects.filter(acheteur=acheteur, vendeur=vendeur,
                                titre=titre, statut=S.DEMANDE).exists():
            raise ErreurEconomie("Tu as déjà envoyé cette demande.")
        c = Order.objects.create(
            acheteur=acheteur, vendeur=vendeur, titre=titre,
            description=description, prix_cubis=prix)
        _systeme(c, f"Demande envoyée à {vendeur.pseudo_whatsapp} "
                    f"pour {prix} Cubis.")
        notifier(vendeur, "Nouvelle demande de commande",
                 f"{acheteur.pseudo_whatsapp} te demande « {titre} » "
                 f"pour {prix} Cubis", _lien(c), "commande")
    return c


def accepter(user, order_id):
    with transaction.atomic():
        c = _charger(order_id)
        if c.vendeur_id != user.pk:
            raise ErreurEconomie("Cette commande n'est pas la tienne.")
        if c.statut != S.DEMANDE:
            raise ErreurEconomie("Cette demande n'est plus en attente.")
        if user.est_suspendu:
            raise ErreurEconomie("Ton compte est suspendu.")
        ach = _verrouiller(c.acheteur)[c.acheteur_id]
        if ach.est_suspendu:
            raise ErreurEconomie("Le compte de l'acheteur est suspendu.")
        if ach.solde_cubis < c.prix_cubis:
            raise ErreurEconomie(
                "L'acheteur n'a plus assez de Cubis. Tu peux refuser la "
                "demande.")
        ach.solde_cubis -= c.prix_cubis
        ach.save(update_fields=["solde_cubis"])
        Transaction.objects.create(
            expediteur=ach, destinataire=None, montant=c.prix_cubis,
            type=Transaction.Type.SEQUESTRE, description=c.titre[:150])
        c.statut = S.EN_COURS
        c.date_acceptation = timezone.now()
        c.save()
        _systeme(c, f"Commande acceptée. {c.prix_cubis} Cubis sont bloqués "
                    "jusqu'à la livraison.")
        notifier(c.acheteur, "Commande acceptée",
                 f"« {c.titre} » est acceptée : {c.prix_cubis} Cubis "
                 "sont bloqués jusqu'à la livraison.", _lien(c), "commande")


def refuser(user, order_id):
    with transaction.atomic():
        c = _charger(order_id)
        if c.vendeur_id != user.pk:
            raise ErreurEconomie("Cette commande n'est pas la tienne.")
        if c.statut != S.DEMANDE:
            raise ErreurEconomie("Cette demande n'est plus en attente.")
        c.statut = S.REFUSEE
        c.date_fin = timezone.now()
        c.save()
        _systeme(c, "Demande refusée par le Créateur.")
        notifier(c.acheteur, "Demande refusée",
                 f"Le Créateur a refusé « {c.titre} ».", _lien(c), "commande")


def annuler_demande(user, order_id):
    with transaction.atomic():
        c = _charger(order_id)
        if c.acheteur_id != user.pk:
            raise ErreurEconomie("Cette commande n'est pas la tienne.")
        if c.statut != S.DEMANDE:
            raise ErreurEconomie(
                "Tu ne peux plus annuler : si besoin, ouvre un litige.")
        c.statut = S.ANNULEE
        c.date_fin = timezone.now()
        c.save()
        _systeme(c, "Demande annulée par l'acheteur.")
        notifier(c.vendeur, "Demande annulée",
                 f"{c.acheteur.pseudo_whatsapp} a annulé « {c.titre} ».",
                 _lien(c), "commande")


def livrer(user, order_id, message=""):
    message = (message or "").strip()[:1000]
    with transaction.atomic():
        c = _charger(order_id)
        if c.vendeur_id != user.pk:
            raise ErreurEconomie("Cette commande n'est pas la tienne.")
        if c.statut != S.EN_COURS:
            raise ErreurEconomie("Cette commande n'est pas en cours.")
        maintenant = timezone.now()
        c.statut = S.LIVREE
        c.date_livraison = maintenant
        c.date_auto_confirmation = maintenant + timedelta(
            days=_delai_confirmation())
        c.save()
        _systeme(c, f"Le Créateur indique avoir livré la commande. Sans "
                    f"réponse de l'acheteur, elle sera confirmée "
                    f"automatiquement dans {_delai_confirmation()} jours.")
        if message:
            OrderMessage.objects.create(
                commande=c, auteur=user, texte=message)
        notifier(c.acheteur, "Commande livrée",
                 f"« {c.titre} » est livrée : confirme la réception.",
                 _lien(c), "commande")


def confirmer(user, order_id):
    with transaction.atomic():
        c = _charger(order_id)
        if c.acheteur_id != user.pk:
            raise ErreurEconomie("Cette commande n'est pas la tienne.")
        if c.statut not in (S.EN_COURS, S.LIVREE):
            raise ErreurEconomie("Cette commande ne peut pas être confirmée.")
        _liberer(c, "Réception confirmée par l'acheteur. Le Créateur a été "
                    "payé.")


def annuler_par_vendeur(user, order_id):
    with transaction.atomic():
        c = _charger(order_id)
        if c.vendeur_id != user.pk:
            raise ErreurEconomie("Cette commande n'est pas la tienne.")
        if c.statut != S.EN_COURS:
            raise ErreurEconomie("Tu ne peux annuler qu'une commande en cours.")
        _rembourser(c, S.ANNULEE,
                    "Commande annulée par le Créateur. L'acheteur est "
                    "remboursé.")


def ouvrir_litige(user, order_id, raison):
    raison = (raison or "").strip()
    if not 10 <= len(raison) <= 500:
        raise ErreurEconomie(
            "Explique le problème en 10 à 500 caractères.")
    with transaction.atomic():
        c = _charger(order_id)
        if user.pk not in (c.acheteur_id, c.vendeur_id):
            raise ErreurEconomie("Cette commande n'est pas la tienne.")
        if c.statut not in (S.EN_COURS, S.LIVREE):
            raise ErreurEconomie("Un litige ne peut pas être ouvert ici.")
        c.statut = S.LITIGE
        c.raison_litige = raison
        c.litige_par = user
        c.save()
        _systeme(c, f"Litige ouvert par {user.pseudo_whatsapp} : {raison} "
                    "Une Divinité va examiner la commande.")
        autre = c.vendeur if user.pk == c.acheteur_id else c.acheteur
        notifier(autre, "Litige ouvert",
                 f"Un litige a été ouvert sur « {c.titre} ».",
                 _lien(c), "commande")
        notifier_divinites("Litige à trancher", f"Commande « {c.titre} »",
                           _lien(c), "commande",
                           exclure=[c.acheteur_id, c.vendeur_id])


def trancher(divinite, order_id, decision, note):
    note = (note or "").strip()
    if not divinite.est_divinite:
        raise ErreurEconomie("Réservé aux Divinités.")
    if decision not in ("rembourser", "payer"):
        raise ErreurEconomie("Décision invalide.")
    if len(note) < 3:
        raise ErreurEconomie("Explique ta décision (3 caractères minimum).")
    with transaction.atomic():
        c = _charger(order_id)
        if divinite.pk in (c.acheteur_id, c.vendeur_id):
            raise ErreurEconomie(
                "Tu ne peux pas trancher une commande où tu es concernée.")
        if c.statut != S.LITIGE:
            raise ErreurEconomie("Cette commande n'est pas en litige.")
        c.tranche_par = divinite
        c.decision = decision
        if decision == "rembourser":
            _rembourser(c, S.REMBOURSEE,
                        f"Décision de la Divinité : l'acheteur est "
                        f"remboursé. {note}")
            gagnant = c.acheteur
        else:
            _liberer(c, f"Décision de la Divinité : le Créateur est payé. "
                        f"{note}")
            gagnant = c.vendeur
        autre_partie = c.vendeur if decision == "rembourser" else c.acheteur
        notifier(autre_partie, "Litige tranché",
                 f"Décision sur « {c.titre} » : "
                 + ("l'acheteur est remboursé." if decision == "rembourser"
                    else "le Créateur est payé."), _lien(c), "commande")
        journaliser(divinite, AuditLog.Action.LITIGE_RESOLU, gagnant,
                    f"Commande #{c.pk} : {decision} · {note}")


def poster_message(user, order_id, texte):
    texte = (texte or "").strip()
    if not 1 <= len(texte) <= 1000:
        raise ErreurEconomie("Écris un message de 1 à 1000 caractères.")
    with transaction.atomic():
        c = _charger(order_id)
        partie = user.pk in (c.acheteur_id, c.vendeur_id)
        arbitre = (user.est_divinite and c.statut == S.LITIGE and not partie)
        if not (partie or arbitre):
            raise ErreurEconomie("Accès refusé.")
        if c.statut not in ACTIVES:
            raise ErreurEconomie("Cette commande est terminée : la messagerie "
                                 "est fermée.")
        OrderMessage.objects.create(commande=c, auteur=user, texte=texte)
        if user.pk == c.acheteur_id:
            destinataires = [c.vendeur]
        elif user.pk == c.vendeur_id:
            destinataires = [c.acheteur]
        else:
            destinataires = [c.acheteur, c.vendeur]
        for d in destinataires:
            notifier(d, "Nouveau message",
                     f"{user.pseudo_whatsapp} : {texte[:80]}",
                     _lien(c), "message", regrouper=True)


def traiter_echeances():
    """Confirmations automatiques et demandes expirées (sans tâche planifiée)."""
    maintenant = timezone.now()
    n_auto = n_exp = 0
    ids = list(Order.objects.filter(
        statut=S.LIVREE, date_auto_confirmation__lte=maintenant
    ).values_list("pk", flat=True))
    for pk in ids:
        with transaction.atomic():
            c = _charger(pk)
            if c.statut == S.LIVREE:
                _liberer(c, "Confirmation automatique : l'acheteur n'a pas "
                            "répondu. Le Créateur a été payé.")
                notifier(c.acheteur, "Commande confirmée automatiquement",
                         f"« {c.titre} » a été confirmée sans réponse de ta part.",
                         _lien(c), "commande")
                n_auto += 1
    limite = maintenant - timedelta(days=_delai_demande())
    ids = list(Order.objects.filter(
        statut=S.DEMANDE, date_creation__lte=limite
    ).values_list("pk", flat=True))
    for pk in ids:
        with transaction.atomic():
            c = _charger(pk)
            if c.statut == S.DEMANDE:
                c.statut = S.EXPIREE
                c.date_fin = timezone.now()
                c.save()
                _systeme(c, "Demande expirée : le Créateur n'a pas répondu.")
                notifier(c.acheteur, "Demande expirée",
                         f"« {c.titre} » n'a pas reçu de réponse.", _lien(c), "commande")
                n_exp += 1
    return n_auto, n_exp
