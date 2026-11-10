import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-_bw6$apk2^tpm*gg#$%@^e-s8gnync2#a0ogr6f7g8k$qi@vv+'

# SECURITY WARNING: don't run with debug turned on in production!
# En local, rien a configurer : DEBUG=True autorise deja localhost.
# Pour tester depuis un autre appareil ou un nom de domaine :
#   DJANGO_ALLOWED_HOSTS=".style.dev,192.168.1.20" python manage.py runserver 0.0.0.0:3000
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"

ALLOWED_HOSTS = [h.strip() for h in
                 os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")
                 if h.strip()]

# Domaines autorises a envoyer des formulaires (obligatoire hors localhost).
CSRF_TRUSTED_ORIGINS = [o.strip() for o in
                        os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
                        if o.strip()]


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

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


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
LIMITE_ENVOI_GARDIENNE = 999999999999999999
BONUS_CREATEUR = 500
PRIX_CONSEILLES = {
    "stickers": (20, 60),
    "fonds": (10, 40),
    "image_rp": (15, 50),
    "autre": (20, 100),

}