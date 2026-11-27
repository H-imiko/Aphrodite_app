"""Mini-jeux : le hasard et l'argent, côté serveur uniquement.

Le navigateur envoie une mise ; il ne décide jamais du résultat. Chaque
tirage est calculé ici, la mise est débitée dans la même transaction que le
gain, et chaque partie laisse une ligne dans l'historique des Cubis.
"""

import random
from decimal import ROUND_DOWN, Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.economy.models import Transaction
from apps.economy.services import ErreurEconomie, crediter, debiter
from .models import Partie

# Valeurs par défaut, surchargeables dans config/settings.py.
MISE_MIN_DEFAUT = 5
MISE_MAX_DEFAUT = 30
PARTIES_JOUR_DEFAUT = 8
PERTE_JOUR_DEFAUT = 100
CONSOLATION_MIN = 5
CONSOLATION_MAX = 10

# Déminer : 9 cases, 2 mines, gain plafonné à x2.
CASES = 9
MINES = 2
PALIERS_MINES = {1: Decimal("1.3"), 2: Decimal("1.6"), 3: Decimal("2.0")}

# Chance de gagner et multiplicateur, réglés pour que l'espérance reste sous
# 1 : le Trésor ne se vide pas, les Cubis perdus sont détruits.
PILE_OU_FACE_CHANCE = 0.47
PILE_OU_FACE_GAIN = Decimal("1.8")

ROUE = (
    (Decimal("0"), 55, "Perdu"),
    (Decimal("1.5"), 25, "x1.5"),
    (Decimal("2.0"), 12, "x2"),
    (Decimal("3.0"), 6, "x3"),
    (Decimal("5.0"), 2, "x5"),
)

POKER = (
    (Decimal("0"), 60, "Le bot te bat"),
    (Decimal("2.0"), 28, "x2"),
    (Decimal("2.5"), 9, "x2.5"),
    (Decimal("3.0"), 3, "x3"),
)

NIVEAUX_BRAQUAGE = {
    "facile": {"nom": "Facile", "multiplicateur": Decimal("2.0"),
               "chance": 0.46},
    "moyen": {"nom": "Moyen", "multiplicateur": Decimal("2.8"),
              "chance": 0.33},
    "difficile": {"nom": "Difficile", "multiplicateur": Decimal("4.0"),
                  "chance": 0.22},
}

JEUX = {
    "pile_ou_face": {
        "nom": "Pile ou Face", "risque": "Faible", "gain_max": "x1.8",
        "resume": "Un lancer, une pièce, et c'est réglé.",
    },
    "roue": {
        "nom": "Roue de la Fortune", "risque": "Faible à moyen",
        "gain_max": "x5",
        "resume": "Une roue, plusieurs crans : x1.5 à x5.",
    },
    "poker": {
        "nom": "Poker Bot", "risque": "Moyen", "gain_max": "x3",
        "resume": "Le bot abat ses cartes. Tu tiens ou tu tombes.",
    },
    "braquage": {
        "nom": "Braquage", "risque": "Élevé", "gain_max": "x4",
        "resume": "Choisis ton risque : plus gros gain, plus grosse chute.",
    },
    "demineur": {
        "nom": "Déminer", "risque": "Moyen", "gain_max": "x2",
        "resume": "Neuf cases, deux mines. Encaisse avant d'exploser.",
    },
}


def _reglage(nom, defaut):
    return getattr(settings, nom, defaut)


def mise_min():
    return _reglage("JEU_MISE_MIN", MISE_MIN_DEFAUT)


def mise_max():
    return _reglage("JEU_MISE_MAX", MISE_MAX_DEFAUT)


def parties_max():
    return _reglage("JEU_PARTIES_PAR_JOUR", PARTIES_JOUR_DEFAUT)


def perte_max():
    return _reglage("JEU_PERTE_JOUR_MAX", PERTE_JOUR_DEFAUT)


def montant_gain(mise, multiplicateur):
    return int((Decimal(mise) * Decimal(multiplicateur))
               .to_integral_value(rounding=ROUND_DOWN))


def parties_du_jour(user):
    return Partie.objects.filter(user=user, date__date=timezone.localdate())


def pertes_du_jour(user):
    total = (parties_du_jour(user)
             .filter(en_cours=False, gagne=False)
             .aggregate(t=Sum("mise"))["t"])
    return total or 0


def verifier(user, mise):
    """Refuse une mise qui sort des règles. Rien n'est débité ici."""
    if user.est_suspendu:
        raise ErreurEconomie("Ton compte est suspendu.")
    if mise < mise_min() or mise > mise_max():
        raise ErreurEconomie(
            f"La mise doit être entre {mise_min()} et {mise_max()} Cubis.")
    if parties_du_jour(user).count() >= parties_max():
        raise ErreurEconomie(
            f"Tu as joué tes {parties_max()} parties du jour. "
            "Reviens demain.")
    if pertes_du_jour(user) >= perte_max():
        raise ErreurEconomie(
            f"Tu as perdu {perte_max()} Cubis aujourd'hui : plus de jeu "
            "jusqu'à demain. C'est une protection, pas une punition.")
    if user.solde_cubis < mise:
        raise ErreurEconomie("Solde insuffisant pour cette mise.")


# ---------- Tirages ----------

def pile_ou_face(_niveau=""):
    face = random.random() < PILE_OU_FACE_CHANCE
    return face, (PILE_OU_FACE_GAIN if face else Decimal("0")), (
        "Face" if face else "Pile")


def roue(_niveau=""):
    multiplicateur, _, libelle = random.choices(
        ROUE, weights=[ligne[1] for ligne in ROUE])[0]
    return multiplicateur > 0, multiplicateur, libelle


def poker(_niveau=""):
    multiplicateur, _, libelle = random.choices(
        POKER, weights=[ligne[1] for ligne in POKER])[0]
    return multiplicateur > 0, multiplicateur, libelle


def braquage(niveau):
    reglage = NIVEAUX_BRAQUAGE.get(niveau)
    if reglage is None:
        raise ErreurEconomie("Choisis un niveau de risque.")
    reussi = random.random() < reglage["chance"]
    multiplicateur = reglage["multiplicateur"] if reussi else Decimal("0")
    libelle = f"{reglage['nom']} · réussi" if reussi else \
        f"{reglage['nom']} · raté"
    return reussi, multiplicateur, libelle


def tirages():
    """Table des tirages, relue à chaque partie.

    Une fonction et non un dictionnaire constant : les tests remplacent un
    tirage par un résultat connu, et la partie doit utiliser le remplacement.
    """
    return {
        "pile_ou_face": pile_ou_face,
        "roue": roue,
        "poker": poker,
        "braquage": braquage,
    }


# ---------- Règlement ----------

def _consolation(user):
    """Petit bonus après 3 pertes d'affilée (5 à 10 Cubis).

    Versé à la 3e, 6e, 9e perte consécutive, jamais après une victoire.
    """
    suite = 0
    for partie in (Partie.objects.filter(user=user, en_cours=False)
                   .order_by("-date", "-id")[:30]):
        if partie.gagne:
            break
        suite += 1
    if suite == 0 or suite % 3:
        return 0
    montant = random.randint(CONSOLATION_MIN, CONSOLATION_MAX)
    crediter(user.pk, montant)
    Transaction.objects.create(
        destinataire=user, montant=montant, type=Transaction.Type.JEU,
        description=f"Consolation ({suite} pertes d'affilée)")
    return montant


def jouer(user, jeu, mise, niveau=""):
    """Joue une partie instantanée. Renvoie (partie, consolation)."""
    tirage = tirages().get(jeu)
    if tirage is None:
        raise ErreurEconomie("Jeu inconnu.")
    verifier(user, mise)
    gagne, multiplicateur, detail = tirage(niveau)

    with transaction.atomic():
        if not debiter(user.pk, mise):
            raise ErreurEconomie("Solde insuffisant pour cette mise.")
        gain = 0
        if gagne:
            gain = montant_gain(mise, multiplicateur)
            crediter(user.pk, gain)
        partie = Partie.objects.create(
            user=user, jeu=jeu, mise=mise, gagne=gagne, gain=gain,
            multiplicateur=str(multiplicateur) if gagne else "",
            niveau=niveau if jeu == "braquage" else "", detail=detail)
        if gagne:
            Transaction.objects.create(
                destinataire=user, montant=gain, type=Transaction.Type.JEU,
                description=f"{partie.get_jeu_display()} x{multiplicateur}"
                            f" (mise {mise})")
        else:
            Transaction.objects.create(
                expediteur=user, montant=mise, type=Transaction.Type.JEU,
                description=f"{partie.get_jeu_display()} perdu "
                            f"(mise {mise})")
        consolation = 0 if gagne else _consolation(user)

    user.refresh_from_db()
    return partie, consolation


# ---------- Déminer ----------

def partie_en_cours(user):
    return Partie.objects.filter(
        user=user, jeu=Partie.Jeu.DEMINEUR, en_cours=True).first()


def demarrer_mines(user, mise):
    verifier(user, mise)
    if partie_en_cours(user):
        raise ErreurEconomie(
            "Une partie de Déminer est déjà en cours : termine-la d'abord.")
    mines = sorted(random.sample(range(CASES), MINES))
    with transaction.atomic():
        if not debiter(user.pk, mise):
            raise ErreurEconomie("Solde insuffisant pour cette mise.")
        partie = Partie.objects.create(
            user=user, jeu=Partie.Jeu.DEMINEUR, mise=mise, en_cours=True,
            mines=",".join(str(m) for m in mines),
            detail="Partie en cours")
        Transaction.objects.create(
            expediteur=user, montant=mise, type=Transaction.Type.JEU,
            description=f"Déminer · mise de {mise}")
    return partie


def _encaisser(partie):
    if not partie.cases_liste:
        raise ErreurEconomie("Ouvre au moins une case avant d'encaisser.")
    multiplicateur = PALIERS_MINES[min(len(partie.cases_liste), 3)]
    gain = montant_gain(partie.mise, multiplicateur)
    crediter(partie.user_id, gain)
    Transaction.objects.create(
        destinataire=partie.user, montant=gain, type=Transaction.Type.JEU,
        description=f"Déminer x{multiplicateur} · encaissé")
    partie.gagne = True
    partie.gain = gain
    partie.en_cours = False
    partie.multiplicateur = str(multiplicateur)
    partie.detail = f"Encaissé x{multiplicateur}"
    partie.save(update_fields=["gagne", "gain", "en_cours",
                               "multiplicateur", "detail"])
    return partie


def encaisser(partie):
    with transaction.atomic():
        partie = Partie.objects.select_for_update().get(pk=partie.pk)
        if not partie.en_cours:
            raise ErreurEconomie("Cette partie est terminée.")
        return _encaisser(partie)


def ouvrir(partie, case):
    """Ouvre une case. Renvoie (partie, consolation)."""
    if case not in range(CASES):
        raise ErreurEconomie("Case inconnue.")
    with transaction.atomic():
        partie = Partie.objects.select_for_update().get(pk=partie.pk)
        if not partie.en_cours:
            raise ErreurEconomie("Cette partie est terminée.")
        if case in partie.cases_liste:
            raise ErreurEconomie("Case déjà ouverte.")
        if case in partie.mines_liste:
            partie.en_cours = False
            partie.gagne = False
            partie.detail = "Mine"
            partie.save(update_fields=["en_cours", "gagne", "detail"])
            return partie, _consolation(partie.user)

        ouvertes = partie.cases_liste + [case]
        partie.cases_ouvertes = ",".join(str(c) for c in ouvertes)
        partie.multiplicateur = str(PALIERS_MINES[min(len(ouvertes), 3)])
        partie.detail = f"{len(ouvertes)} case(s) ouverte(s)"
        partie.save(update_fields=["cases_ouvertes", "multiplicateur",
                                   "detail"])
        if len(ouvertes) >= CASES - MINES:
            _encaisser(partie)
    return partie, 0


def gain_potentiel(partie):
    """Ce que rapporterait un encaissement maintenant (0 sans case ouverte)."""
    if partie is None or not partie.cases_liste:
        return 0
    multiplicateur = PALIERS_MINES[min(len(partie.cases_liste), 3)]
    return montant_gain(partie.mise, multiplicateur)


def grille(partie):
    """État des neuf cases pour l'affichage."""
    if partie is None:
        return []
    mines = set(partie.mines_liste)
    ouvertes = set(partie.cases_liste)
    finie = not partie.en_cours
    return [
        {
            "index": index,
            "ouverte": index in ouvertes,
            "mine": finie and not partie.gagne and index in mines,
            "cliquable": partie.en_cours and index not in ouvertes,
        }
        for index in range(CASES)
    ]
