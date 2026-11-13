"""Limitation de debit des actions sensibles.

Le compteur vit dans le cache Django (LocMemCache en local, un seul
processus). En production multi-processus, brancher un cache partage
(Redis, Memcached) dans config/settings.py : sinon chaque processus compte
separement, ce qui reste utile mais moins strict.

Regle : on ne bloque jamais un membre sur une action anodine. On compte par
adresse IP, et par email tente pour la connexion, afin qu'un voisin de
reseau ne puisse pas bloquer tout le monde.
"""

from django.conf import settings
from django.core.cache import cache

# Valeurs par defaut, surchargeables par le reglage LIMITES.
LIMITES = {
    "connexion": (8, 300),      # 8 tentatives / 5 minutes par adresse + email
    "connexion_ip": (30, 300),  # 30 tentatives / 5 minutes par adresse
    "inscription": (10, 900),   # 10 inscriptions / 15 minutes
    "offrande": (20, 600),
    "signalement": (10, 600),
    "transfert": (20, 600),
    "tresor": (30, 600),
    "mot_de_passe_oublie": (5, 900),
}


def _ip(request):
    """Adresse de comptage.

    X-Forwarded-For est ecrite par le client : la lire sans precaution permet
    de reinitialiser son compteur a chaque requete (contournement total).
    Elle n'est donc utilisee que si DJANGO_USE_X_FORWARDED_FOR=1, c'est-a-dire
    quand un proxy de confiance la pose. On prend la derniere valeur, celle
    ajoutee par le proxy le plus proche, pas celle fournie par le client.
    """
    if request is None:
        return "inconnu"
    if getattr(settings, "USE_X_FORWARDED_FOR", False):
        valeurs = [v.strip() for v in
                   (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")
                   if v.strip()]
        if valeurs:
            return valeurs[-1]
    return (request.META.get("REMOTE_ADDR") or "inconnu").strip()


def _regle(nom):
    return getattr(settings, "LIMITES", LIMITES).get(nom, LIMITES.get(nom, (20, 600)))


def compter(nom, request, discriminant=""):
    """Incremente le compteur et renvoie le nombre de tentatives vues."""
    maxi, periode = _regle(nom)
    cle = f"limite:{nom}:{_ip(request)}:{discriminant}".lower()[:200]
    if cache.add(cle, 1, periode):
        return 1
    try:
        return cache.incr(cle)
    except ValueError:
        # Cle expiree entre-temps (ou backend qui ne sait pas incrementer).
        cache.set(cle, 1, periode)
        return 1


def depasse(nom, request, discriminant=""):
    """True si la limite est depassee pour cette action."""
    maxi, _ = _regle(nom)
    return compter(nom, request, discriminant) > maxi
