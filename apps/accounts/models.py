from django.conf import settings
from django.contrib.auth.models import (
    AbstractBaseUser, PermissionsMixin, BaseUserManager
)
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

# Codes de langue acceptes, dans l'ordre d'affichage des parametres.
LANGUES = (("fr", "Français"), ("en", "English"), ("es", "Español"))
LANGUE_PAR_DEFAUT = "fr"


def stockage_prive():
    """Photos de profil hors de /media/ : elles ne sont plus publiques.

    Une photo de profil ne doit pas etre accessible par sa seule URL : le
    fichier est servi par une vue qui verifie qui regarde et pose noindex.
    """
    return FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT)


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError("L'email est obligatoire")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("est_divinite", True)
        return self.create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    class Espece(models.TextChoices):
        NEKO = "neko", _("Neko")
        SUCCUBE = "succube", _("Succube")
        INCUBE = "incube", _("Incube")
        DEESSE = "deesse", _("Déesse")
        EMPEREUR = "empereur", _("Empereur")
        IMPERATRICE = "imperatrice", _("Impératrice")
        FANTOME = "fantome", _("Fantôme")
        ASSASSIN = "assassin", _("Assassin")
        MAGE = "mage", _("Mage")
        HUMAIN = "humain", _("Humain")
        VAMPIRE = "vampire", _("Vampire")
        DEMON = "demon", _("Démon")

    class TypeCompte(models.TextChoices):
        PARTICIPANT = "participant", _("Participant")
        CREATEUR = "createur", _("Créateur")

    email = models.EmailField(unique=True)
    pseudo_whatsapp = models.CharField(max_length=50)
    espece = models.CharField(max_length=20, choices=Espece.choices,
                              default=Espece.HUMAIN)
    type_compte = models.CharField(max_length=20, choices=TypeCompte.choices,
                                   default=TypeCompte.PARTICIPANT)
    bio_rp = models.TextField(blank=True)
    numero_whatsapp = models.CharField(max_length=30, blank=True)
    avatar = models.ImageField(upload_to="avatars/", storage=stockage_prive,
                               blank=True, null=True)
    banniere = models.ImageField(upload_to="bannieres/", storage=stockage_prive,
                                 blank=True, null=True)
    titre = models.CharField(max_length=60, blank=True)
    date_naissance = models.DateField(null=True, blank=True)

    # Langue de l'interface choisie dans les parametres. Vide : celle du
    # navigateur (LocaleMiddleware s'en charge).
    langue = models.CharField(max_length=5, blank=True, default="")

    solde_cubis = models.PositiveIntegerField(default=0)
    serie_connexion = models.PositiveIntegerField(default=0)
    derniere_connexion_bonus = models.DateField(null=True, blank=True)

    # Passe a True quand une Divinite genere un mot de passe provisoire :
    # le membre doit en choisir un autre avant de pouvoir utiliser le site.
    doit_changer_mot_de_passe = models.BooleanField(default=False)

    est_divinite = models.BooleanField(default=False)
    createur_valide = models.BooleanField(default=False)
    est_suspendu = models.BooleanField(default=False)
    date_fin_suspension = models.DateTimeField(null=True, blank=True)

    date_inscription = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["pseudo_whatsapp"]

    def __str__(self):
        return self.pseudo_whatsapp

    @property
    def peut_publier(self):
        return self.est_divinite or self.createur_valide


class DemandeAcces(models.Model):
    """Une demande de mot de passe oublie, sans email.

    Le membre laisse son adresse ; l'equipe la voit dans le panel, verifie
    l'identite sur WhatsApp, puis genere un mot de passe provisoire que le
    membre devra changer des sa premiere connexion.
    """

    email = models.EmailField()
    traite = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)
    date_traitement = models.DateTimeField(null=True, blank=True)
    traite_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True,
                                   blank=True, on_delete=models.SET_NULL,
                                   related_name="demandes_traitees")

    class Meta:
        ordering = ["-date"]
        verbose_name = "Demande d'acces"
        verbose_name_plural = "Demandes d'acces"

    def __str__(self):
        return f"Demande de {self.email} ({self.date:%d/%m/%Y})"
