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
MISE_MAX_DEFAUT = 100
PARTIES_JOUR_DEFAUT = 10
PERTE_JOUR_DEFAUT = 300
CONSOLATION_MIN = 10
CONSOLATION_MAX = 25

# Déminer : 9 cases, 2 mines, gain plafonné à x2.
CASES = 9
MINES = 2
PALIERS_MINES = {1: Decimal("1.3"), 2: Decimal("1.6"), 3: Decimal("2.0")}

# Gains réglés pour que l'espérance reste sous 1 (le Trésor ne se vide pas,
# les Cubis perdus sont détruits) tout en restant lisibles face aux prix de la
# boutique : une mise de 100 peut rapporter jusqu'à 1000 sur la roue.
PILE_OU_FACE_GAIN = Decimal("1.9")
POKER_GAIN = Decimal("1.9")

# Segments de la roue, dans l'ordre d'affichage : (multiplicateur, poids, nom).
# Six segments de 60°, le pointeur en haut.
ROUE = (
    (Decimal("0"), 60, "Perdu"),
    (Decimal("1.5"), 20, "x1.5"),
    (Decimal("2.0"), 10, "x2"),
    (Decimal("3.0"), 6, "x3"),
    (Decimal("5.0"), 3, "x5"),
    (Decimal("10.0"), 1, "x10"),
)
ROUE_TOURS = 6

RANGS = ("2", "3", "4", "5", "6", "7", "8", "9", "10", "V", "D", "R", "A")
COULEURS = ("♠", "♥", "♦", "♣")

NIVEAUX_BRAQUAGE = {
    "facile": {"nom": "Facile", "multiplicateur": Decimal("2.2"),
               "chance": 0.44},
    "moyen": {"nom": "Moyen", "multiplicateur": Decimal("3.0"),
              "chance": 0.32},
    "difficile": {"nom": "Difficile", "multiplicateur": Decimal("5.0"),
                  "chance": 0.19},
}

JEUX = {
    "pile_ou_face": {
        "nom": "Pile ou Face", "risque": "Faible", "gain_max": "x1.9",
        "resume": "Tu choisis ta face, la pièce tourne, elle tombe.",
    },
    "roue": {
        "nom": "Roue de la Fortune", "risque": "Faible à moyen",
        "gain_max": "x10",
        "resume": "Une vraie roue qui tourne : x1.5 à x10.",
    },
    "poker": {
        "nom": "Poker Bot", "risque": "Moyen", "gain_max": "x1.9",
        "resume": "Une carte chacun. La plus haute gagne.",
    },
    "braquage": {
        "nom": "Braquage", "risque": "Élevé", "gain_max": "x5",
        "resume": "Trois risques, un coffre : x2.2 à x5.",
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

def pile_ou_face(_niveau="", choix=""):
    """La pièce tombe sur Pile ou Face ; le membre doit l'avoir annoncé."""
    choix = (choix or "").strip().lower()
    if choix not in ("pile", "face"):
        raise ErreurEconomie("Choisis Pile ou Face avant de lancer la pièce.")
    cote = "Face" if random.random() < 0.5 else "Pile"
    gagne = cote.lower() == choix
    return gagne, (PILE_OU_FACE_GAIN if gagne else Decimal("0")), cote


def roue(_niveau="", _choix=""):
    multiplicateur, _, libelle = random.choices(
        ROUE, weights=[ligne[1] for ligne in ROUE])[0]
    return multiplicateur > 0, multiplicateur, libelle


def _nom_carte(index):
    return f"{RANGS[index % 13]}{COULEURS[index // 13]}"


def poker(_niveau="", _choix=""):
    """Duel de cartes honnête : la carte la plus haute gagne.

    Deux cartes distinctes du même jeu de 52. Une égalité (même rang, autre
    couleur) tourne à l'avantage du bot, ce qui garde l'espérance sous 1.
    """
    joueur, bot = random.sample(range(52), 2)
    gagne = joueur % 13 > bot % 13
    multiplicateur = POKER_GAIN if gagne else Decimal("0")
    detail = f"Toi {_nom_carte(joueur)} · bot {_nom_carte(bot)}"
    return gagne, multiplicateur, detail


def braquage(niveau, _choix=""):
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


# ---------- Habillage des animations ----------
# Le navigateur ne décide jamais du résultat ; il reçoit seulement l'angle ou
# la carte à afficher, calculés à partir de la partie enregistrée.

def roue_parts():
    """Les six segments de la roue, positionnés pour l'affichage."""
    return [
        {"index": index, "libelle": libelle,
         "angle": index * 60 + 30}
        for index, (_multiplicateur, _poids, libelle) in enumerate(ROUE)
    ]


def angle_roue(libelle):
    """Angle final qui amène le segment tiré sous le pointeur du haut."""
    for index, (_multiplicateur, _poids, nom) in enumerate(ROUE):
        if nom == libelle:
            return 360 * ROUE_TOURS - (index * 60 + 30)
    return None


def cartes_du_detail(detail):
    """Relit « Toi A♠ · bot 7♦ » en (carte du joueur, carte du bot)."""
    morceaux = (detail or "").split(" · ")
    if len(morceaux) != 2:
        return None
    cartes = [morceau.split(" ")[-1] for morceau in morceaux]
    if any(len(carte) < 2 for carte in cartes):
        return None
    return cartes[0], cartes[1]


def animation(partie):
    """Données d'affichage de la dernière partie, pour les animations."""
    if partie is None:
        return {}
    if partie.jeu == Partie.Jeu.ROUE:
        angle = angle_roue(partie.detail)
        return {"angle": angle} if angle is not None else {}
    if partie.jeu == Partie.Jeu.PILE_OU_FACE:
        return {"cote": (partie.detail or "").lower()}
    if partie.jeu == Partie.Jeu.POKER:
        cartes = cartes_du_detail(partie.detail)
        if cartes:
            return {"joueur": cartes[0], "bot": cartes[1]}
        return {}
    if partie.jeu == Partie.Jeu.BRAQUAGE:
        return {"reussi": partie.gagne}
    return {}


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


def jouer(user, jeu, mise, niveau="", choix=""):
    """Joue une partie instantanée. Renvoie (partie, consolation)."""
    tirage = tirages().get(jeu)
    if tirage is None:
        raise ErreurEconomie("Jeu inconnu.")
    verifier(user, mise)
    gagne, multiplicateur, detail = tirage(niveau, choix)

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
