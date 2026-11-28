from django.conf import settings
from django.db import models


class Partie(models.Model):
    """Une partie de mini-jeu, tirée et réglée par le serveur.

    Le résultat n'est jamais envoyé par le navigateur : cette ligne est la
    trace de ce que le serveur a tiré, débité et éventuellement rendu.
    """

    class Jeu(models.TextChoices):
        PILE_OU_FACE = "pile_ou_face", "Pile ou Face"
        ROUE = "roue", "Roue de la Fortune"
        POKER = "poker", "Poker Bot"
        BRAQUAGE = "braquage", "Braquage"
        DEMINEUR = "demineur", "Déminer"

    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE, related_name="parties")
    jeu = models.CharField(max_length=20, choices=Jeu.choices)
    mise = models.PositiveIntegerField()
    gagne = models.BooleanField(default=False)
    # Somme rendue au joueur, mise comprise. 0 quand la mise est perdue.
    gain = models.PositiveIntegerField(default=0)
    multiplicateur = models.CharField(max_length=10, blank=True)
    # Niveau de risque du Braquage (facile, moyen, difficile).
    niveau = models.CharField(max_length=10, blank=True)
    detail = models.CharField(max_length=120, blank=True)
    # Déminer uniquement : mines tirées et cases déjà ouvertes, "0,4,7".
    mines = models.CharField(max_length=40, blank=True)
    cases_ouvertes = models.CharField(max_length=40, blank=True)
    en_cours = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]
        verbose_name = "Partie"
        verbose_name_plural = "Parties"
        indexes = [models.Index(fields=["user", "date"])]

    def __str__(self):
        return f"{self.get_jeu_display()} · {self.mise} Cubis"

    @staticmethod
    def _lire(valeur):
        return [int(v) for v in valeur.split(",") if v.strip()]

    @property
    def benefice(self):
        """Bénéfice net : le gain rendu, mise récupérée déduite."""
        return max(0, self.gain - self.mise)

    @property
    def cases_liste(self):
        return self._lire(self.cases_ouvertes)

    @property
    def mines_liste(self):
        return self._lire(self.mines)
