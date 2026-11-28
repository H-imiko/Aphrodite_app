from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render, reverse

from apps.commun.limites import depasse
from apps.economy.services import ErreurEconomie
from . import services
from .models import Partie

TROP_DE_PARTIES = ("Trop de parties en peu de temps. Patiente quelques "
                   "minutes.")


def _mise(request):
    try:
        return int(request.POST.get("mise") or 0)
    except (TypeError, ValueError):
        return 0


def _resultat(request):
    identifiant = request.GET.get("r", "")
    if not identifiant.isdigit():
        return None
    return Partie.objects.filter(pk=int(identifiant),
                                 user=request.user).first()


def _contexte_partie():
    return {
        "mise_min": services.mise_min(),
        "mise_max": services.mise_max(),
    }


@login_required
def hall(request):
    return render(request, "jeux/hall.html", {
        "jeux": services.JEUX,
        "parties_restantes": max(
            0, services.parties_max()
            - services.parties_du_jour(request.user).count()),
        "pertes": services.pertes_du_jour(request.user),
        "perte_max": services.perte_max(),
        "en_cours": services.partie_en_cours(request.user),
        "historique": Partie.objects.filter(
            user=request.user, en_cours=False)[:12],
        **_contexte_partie(),
    })


@login_required
def jeu(request, jeu):
    if jeu == Partie.Jeu.DEMINEUR:
        return redirect("demineur")
    if jeu not in services.JEUX:
        raise Http404("Jeu inconnu")

    if request.method == "POST":
        if depasse("jeu", request):
            messages.error(request, TROP_DE_PARTIES)
            return redirect("jeu", jeu=jeu)
        try:
            partie, consolation = services.jouer(
                request.user, jeu, _mise(request),
                request.POST.get("niveau", ""),
                request.POST.get("choix", ""))
        except ErreurEconomie as erreur:
            messages.error(request, str(erreur))
            return redirect("jeu", jeu=jeu)
        if consolation:
            messages.info(request, f"3 pertes d'affilée : {consolation} "
                                   "Cubis de consolation 💗")
        return redirect(f"{reverse('jeu', args=[jeu])}?r={partie.pk}")

    resultat = _resultat(request)
    return render(request, "jeux/jeu.html", {
        "jeu": jeu,
        "infos": services.JEUX[jeu],
        "niveaux": services.NIVEAUX_BRAQUAGE,
        "roue_parts": services.roue_parts(),
        "resultat": resultat,
        "animation": services.animation(resultat),
        **_contexte_partie(),
    })


@login_required
def demineur(request):
    en_cours = services.partie_en_cours(request.user)

    if request.method == "POST":
        if depasse("jeu", request):
            messages.error(request, TROP_DE_PARTIES)
            return redirect("demineur")
        action = request.POST.get("action")
        try:
            if action == "nouvelle":
                services.demarrer_mines(request.user, _mise(request))
                messages.success(request, "Partie lancée : ouvre une case, "
                                          "puis encaisse avant la mine.")
            elif action == "ouvrir" and en_cours:
                try:
                    case = int(request.POST.get("case", "-1"))
                except (TypeError, ValueError):
                    case = -1
                partie, consolation = services.ouvrir(en_cours, case)
                if not partie.en_cours:
                    messages.error(request, "Mine ! Ta mise est perdue.")
                if consolation:
                    messages.info(request, f"3 pertes d'affilée : "
                                           f"{consolation} Cubis de "
                                           "consolation 💗")
            elif action == "encaisser" and en_cours:
                partie = services.encaisser(en_cours)
                return redirect(f"{reverse('demineur')}?r={partie.pk}")
        except ErreurEconomie as erreur:
            messages.error(request, str(erreur))
        return redirect("demineur")

    en_cours = services.partie_en_cours(request.user)
    return render(request, "jeux/demineur.html", {
        "en_cours": en_cours,
        "grille": services.grille(en_cours),
        "gain_potentiel": services.gain_potentiel(en_cours),
        "resultat": _resultat(request),
        **_contexte_partie(),
    })
