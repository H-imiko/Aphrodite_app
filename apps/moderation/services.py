from .models import AuditLog


def journaliser(auteur, action, cible=None, details=""):
    AuditLog.objects.create(
        auteur=auteur, action=action, cible=cible, details=details[:300])
