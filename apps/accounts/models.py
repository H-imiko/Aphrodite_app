from django.db import models

# Create your models here.
from django.contrib.auth.models import (
    AbstractBaseUser, PermissionsMixin, BaseUserManager
)
from django.db import models
from django.utils import timezone


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
        NEKO = "neko", "Neko"
        SUCCUBE = "succube", "Succube"
        INCUBE = "incube", "Incube"
        DEESSE = "deesse", "Déesse"
        EMPEREUR = "empereur", "Empereur"
        IMPERATRICE = "imperatrice", "Impératrice"
        FANTOME = "fantome", "Fantôme"
        ASSASSIN = "assassin", "Assassin"
        MAGE = "mage", "Mage"
        HUMAIN = "humain", "Humain"
        VAMPIRE = "vampire", "Vampire"
        DEMON = "demon", "Démon"

    class TypeCompte(models.TextChoices):
        PARTICIPANT = "participant", "Participant"
        CREATEUR = "createur", "Créateur"

    email = models.EmailField(unique=True)
    pseudo_whatsapp = models.CharField(max_length=50)
    espece = models.CharField(max_length=20, choices=Espece.choices,
                              default=Espece.HUMAIN)
    type_compte = models.CharField(max_length=20, choices=TypeCompte.choices,
                                   default=TypeCompte.PARTICIPANT)
    bio_rp = models.TextField(blank=True)
    numero_whatsapp = models.CharField(max_length=30, blank=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    banniere = models.ImageField(upload_to="bannieres/", blank=True, null=True)
    titre = models.CharField(max_length=60, blank=True)
    date_naissance = models.DateField(null=True, blank=True)
    solde_cubis = models.PositiveIntegerField(default=0)
    serie_connexion = models.PositiveIntegerField(default=0)
    derniere_connexion_bonus = models.DateField(null=True, blank=True)

    est_divinite = models.BooleanField(default=False)
    est_suspendu = models.BooleanField(default=False)
    createur_valide = models.BooleanField(default=False)
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