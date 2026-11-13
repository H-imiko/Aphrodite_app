from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.commun.limites import depasse
from apps.shop.models import Item
from .forms import SignalementForm
from .models import AuditLog, Report, Sanction
from .services import journaliser

User = get_user_model()
MOTIFS_URGENTS = (Report.Motif.MINEUR, Report.Motif.ILLEGAL)


@login_required
def signaler(request, type_cible, pk):
    article = membre = None
    if type_cible == "article":
        article = get_object_or_404(Item, pk=pk)
        if article.createur_id == request.user.pk:
            messages.error(request, "C'est ton propre article.")
            return redirect("article", pk=pk)
    elif type_cible == "membre":
        membre = get_object_or_404(User, pk=pk, is_active=True)
        if membre.pk == request.user.pk:
            messages.error(request, "Tu ne peux pas te signaler toi-même.")
            return redirect("membre", pk=pk)
    else:
        raise Http404

    def retour():
        return redirect("boutique") if article else redirect(
            "membre", pk=membre.pk)

    form = SignalementForm(request.POST or None)
    if request.method == "POST" and depasse("signalement", request):
        form.add_error(
            None, "Trop de signalements en peu de temps. Réessaie dans "
                  "quelques minutes.")
    elif request.method == "POST" and form.is_valid():
        recents = Report.objects.filter(
            auteur=request.user,
            date__gte=timezone.now() - timedelta(hours=1)).count()
        if recents >= 5:
            form.add_error(
                None, "Trop de signalements en peu de temps. Réessaie plus tard.")
        elif Report.objects.filter(
                auteur=request.user, statut=Report.Statut.OUVERT,
                article=article, membre=membre).exists():
            messages.info(
                request, "Tu as déjà signalé ça : une Divinité va l'examiner.")
            return retour()
        else:
            r = Report.objects.create(
                auteur=request.user, article=article, membre=membre,
                motif=form.cleaned_data["motif"],
                details=form.cleaned_data["details"])
            # Un seul membre ne peut plus faire disparaitre un article :
            # il faut plusieurs signalements distincts. Les motifs graves
            # (mineur, illegal) baissent le seuil, ils ne le suppriment pas.
            seuil = 2 if r.motif in MOTIFS_URGENTS else 3
            signaleurs = (Report.objects.filter(article=article)
                          .values("auteur_id").distinct().count())
            if (article and article.est_actif and not article.masque_moderation
                    and signaleurs >= seuil):
                article.est_actif = False
                article.masque_moderation = True
                article.save(update_fields=["est_actif", "masque_moderation"])
                journaliser(None, AuditLog.Action.ARTICLE_MASQUE,
                            article.createur,
                            f"Masqué après {signaleurs} signalements distincts")
            messages.success(request, "Signalement envoyé, merci 🙏")
            return retour()
    return render(request, "moderation/signaler.html", {
        "form": form, "article": article, "membre": membre})


@login_required
def suspendu(request):
    if not request.user.est_suspendu:
        return redirect("boutique")
    derniere = request.user.sanctions.filter(
        type=Sanction.Type.SUSPENSION).first()
    return render(request, "moderation/suspendu.html", {"derniere": derniere})
