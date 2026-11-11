import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


def _charger_env(chemin=None):
    """Charge un fichier .env (CLE=valeur) sans dependance externe.

    Les variables deja presentes dans l'environnement sont prioritaires :
    le .env sert au confort local, jamais a ecraser une vraie configuration.
    """
    chemin = chemin or BASE_DIR / ".env"
    if not chemin.exists():
        return
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        cle, valeur = ligne.split("=", 1)
        valeur = valeur.strip()
        if len(valeur) >= 2 and valeur[0] == valeur[-1] and valeur[0] in "\"'":
            valeur = valeur[1:-1]
        os.environ.setdefault(cle.strip(), valeur)


_charger_env()


def _drapeau(nom, defaut="0"):
    return os.environ.get(nom, defaut).strip().lower() in {"1", "true", "oui", "yes", "on"}


def _liste(nom):
    return [v.strip() for v in os.environ.get(nom, "").split(",") if v.strip()]


# En local, rien a configurer : DEBUG est actif par defaut.
# En ligne, DJANGO_DEBUG=0 rend les reglages de production obligatoires.
DEBUG = _drapeau("DJANGO_DEBUG", "1")

# SECURITY WARNING: la cle secrete ne doit jamais etre dans le code.
# En developpement, une cle jetable suffit ; en ligne, l'application refuse
# de demarrer sans DJANGO_SECRET_KEY.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "").strip()
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY est obligatoire quand DJANGO_DEBUG=0.\n"
            "Genere-la avec :\n"
            "  python -c \"import secrets; print(secrets.token_urlsafe(64))\"\n"
            "puis place-la dans .env (ou dans les variables d'environnement du serveur)."
        )
    SECRET_KEY = "django-insecure-cle-de-developpement-locale-ne-pas-mettre-en-ligne"

# Hotes acceptes. En local, vides = localhost et 127.0.0.1, comportement Django.
# En ligne, la liste doit etre explicite, sinon on prefere refuser de demarrer
# plutot que de servir n'importe quel domaine.
ALLOWED_HOSTS = _liste("DJANGO_ALLOWED_HOSTS")
if not DEBUG and not ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        "DJANGO_ALLOWED_HOSTS est obligatoire quand DJANGO_DEBUG=0 "
        '(exemple : DJANGO_ALLOWED_HOSTS="aphrodite.example.com,www.aphrodite.example.com").'
    )

# Domaines autorises a envoyer des formulaires (obligatoire hors localhost).
CSRF_TRUSTED_ORIGINS = _liste("DJANGO_CSRF_TRUSTED_ORIGINS")


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'apps.accounts',
    'apps.economy',
    'apps.shop',
    'apps.inventory',
    'apps.creators',
    'apps.moderation',
    'apps.orders',
    'apps.notifications',
    'apps.social',
    'apps.offrandes',
    'apps.maintenance',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'apps.moderation.middleware.ModerationMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.orders.context.commandes_a_traiter',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

# SQLite par defaut : un fichier, zero administration, largement suffisant
# pour une communaute unique. Pour passer a PostgreSQL, voir
# docs/migration-postgres.md (aucune ligne de code a modifier).
MOTEUR_BASE = os.environ.get("DJANGO_DB_ENGINE", "sqlite").strip().lower()

if MOTEUR_BASE in {"postgres", "postgresql", "psql"}:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("POSTGRES_DB", "aphrodite"),
            "USER": os.environ.get("POSTGRES_USER", "aphrodite"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
            "HOST": os.environ.get("POSTGRES_HOST", "127.0.0.1"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": 60,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
            # Evite les "database is locked" quand plusieurs requetes
            # ecrivent en meme temps : on attend au lieu d'echouer.
            "OPTIONS": {"timeout": 20},
        }
    }


# HTTPS et cookies : appliques uniquement hors developpement, pour que
# `manage.py check --deploy` soit propre en production sans gener le local.
if not DEBUG:
    SECURE_SSL_REDIRECT = _drapeau("DJANGO_SECURE_SSL_REDIRECT", "1")
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    X_FRAME_OPTIONS = "DENY"


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'fr'

TIME_ZONE = 'Africa/Brazzaville'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = 'static/'

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'accounts.User'
STATICFILES_DIRS = [BASE_DIR / 'static']
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'
LOGIN_URL = 'connexion'
LOGIN_REDIRECT_URL = 'boutique'
LOGOUT_REDIRECT_URL = 'connexion'
PRIVATE_MEDIA_ROOT = BASE_DIR / 'private_media'
# Dossier des sauvegardes de la base (non versionne).
SAUVEGARDES_DIR = Path(os.environ.get("DJANGO_SAUVEGARDES_DIR", "") or BASE_DIR / "sauvegardes")
LIMITE_ENVOI_GARDIENNE = 999999999999999999
BONUS_CREATEUR = 500
# Nombre de bonus quotidiens servis a un meme appareil (IP + navigateur).
# Empeche de creer des comptes en serie pour ramasser le bonus plusieurs fois.
# 0 desactive le plafond (deconseille).
BONUS_PLAFOND_APPAREIL = int(os.environ.get("DJANGO_BONUS_PLAFOND_APPAREIL", "3"))
PRIX_CONSEILLES = {
    "stickers": (20, 60),
    "fonds": (10, 40),
    "image_rp": (15, 50),
    "autre": (20, 100),

}