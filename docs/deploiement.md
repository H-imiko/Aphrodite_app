# Mise en ligne d'Aphrodite

Procédure de déploiement en production. Cible : un serveur Windows ou Linux avec
Python 3.12, derrière un reverse proxy qui termine le HTTPS.

L'application se sert elle-même ses fichiers statiques (CSS, images d'interface)
grâce à **WhiteNoise** : le proxy n'a pas besoin de connaître `/static/`.

Les médias sont séparés en deux :

- `/media/` : aperçus d'articles, images d'offrandes, produits non payants.
  C'est le proxy qui les sert, comme avant.
- `private_media/` : originaux payants, avatars et bannières. Jamais exposé par
  le proxy : Django les sert après contrôle d'accès (`/membre/<id>/photo/…`,
  `/article/<id>/lire/`). Les photos marquées mature sont refusées aux
  visiteurs qui n'ont pas accepté ce contenu.

---

## 1. Ce que le serveur exécute

| Élément | Rôle |
|---|---|
| `waitress` | serveur WSGI (remplace `runserver`, qui n'est pas fait pour la production) |
| `whitenoise` | envoie `/static/` depuis le processus Django, avec compression et cache long |
| Django | l'application |
| reverse proxy (IIS, nginx, Caddy…) | HTTPS, nom de domaine, `/media/`, fichiers volumineux |
| SQLite | la base (`db.sqlite3`), un seul écrivain à la fois |

Rien n'est servi par `runserver --insecure` : ce mode n'existe que pour les tests.

---

## 2. Variables d'environnement

À mettre dans `.env` (non versionné) ou dans l'environnement du service.
`DJANGO_DEBUG=0` rend les trois premières obligatoires : sans elles, l'application
refuse de démarrer, volontairement.

| Variable | Exemple | Notes |
|---|---|---|
| `DJANGO_DEBUG` | `0` | **obligatoire en production** |
| `DJANGO_SECRET_KEY` | `python -c "import secrets; print(secrets.token_urlsafe(64))"` | ne jamais réutiliser celle du développement |
| `DJANGO_ALLOWED_HOSTS` | `aphrodite.example.com,www.aphrodite.example.com` | séparés par des virgules |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://aphrodite.example.com,https://www.aphrodite.example.com` | avec le `https://` |
| `DJANGO_SECURE_SSL_REDIRECT` | `1` (défaut) | laisser à `1` derrière le proxy |
| `DJANGO_HSTS_SECONDS` | `3600` | monter progressivement (86400, puis un an) quand tout est stable |
| `DJANGO_USE_X_FORWARDED_FOR` | `0` | laisser à `0` avec `server.py` (waitress fait le travail). Passer à `1` seulement avec un autre serveur qui ne traite pas lui-même l'en-tête |
| `APHRODITE_TRUSTED_PROXY` | `127.0.0.1,::1` | adresses des proxys autorisés à fournir `X-Forwarded-*` |
| `DJANGO_SAUVEGARDES_DIR` | `D:\sauvegardes\aphrodite` | **hors du dossier du projet** |
| `DJANGO_BONUS_PLAFOND_APPAREIL` | `3` | bonus quotidiens par appareil |
| `DJANGO_LIMITE_ENVOI_GARDIENNE` | `5000` | plafond d'un envoi du Trésor (hors Safir) |
| `DJANGO_PLAFOND_JOURNALIER_TRESOR` | `50000` | plafond quotidien du Trésor (hors Safir) |
| `DJANGO_DB_ENGINE` | *(vide = SQLite)* | voir `docs/migration-postgres.md` |

Avec `server.py`, `X-Forwarded-Proto` et `X-Forwarded-For` ne sont lus que
s'ils viennent de `APHRODITE_TRUSTED_PROXY`. La configuration nginx donnée
plus bas utilise `$proxy_add_x_forwarded_for`, qui produit « client, proxy » :
la valeur fournie par l'utilisateur est ignorée. Ne jamais lancer `server.py`
avec un proxy de confiance si le serveur est joignable directement.

Le HTTPS doit être détecté : le proxy envoie `X-Forwarded-Proto: https`, et
Django le lit déjà (`SECURE_PROXY_SSL_HEADER`). Si ce n'est pas fait, les
redirections HTTPS bouclent et les cookies sécurisés ne passent pas.

---

## 3. Installation

```bash
git clone <dépôt> aphrodite
cd aphrodite
python -m venv .venv
.venv/bin/pip install -r requirements.txt      # Windows : .venv\Scripts\pip
cp .env.example .env                            # puis remplir les variables
```

Puis, dans l'ordre :

```bash
.venv/bin/python manage.py migrate
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py installer_catalogue --proprietaire=ton-email
```

- `collectstatic` écrit dans `staticfiles/` (dossier ignoré par git). **À relancer
  après chaque `git pull`** qui touche `static/` : sans ça, l'ancien CSS reste servi.
- `installer_catalogue` a besoin d'un compte Divinité ou superutilisateur pour
  offrir le cadre. Le créer avant.

---

## 4. Lancer le serveur

```bash
.venv/bin/python server.py
```

`server.py` remplace l'appel direct à waitress, pour une raison précise :
**Waitress 3 supprime par défaut les en-têtes `X-Forwarded-*`** (protection
contre l'usurpation). Lancé à la main derrière nginx, Django ne voit jamais
le HTTPS, répond `301` vers lui-même, et la boucle est infinie. Le lanceur
déclare le proxy de confiance (`APHRODITE_TRUSTED_PROXY`, `127.0.0.1,::1` par
défaut), ce qui suffit : `request.is_secure()` devient vrai et `REMOTE_ADDR`
reprend l'adresse réelle du membre, donc la limitation de débit compte juste.

Si le site est exposé **sans** proxy, lancer avec
`APHRODITE_TRUSTED_PROXY= python server.py`.

Pour écouter sur toutes les interfaces (déconseillé derrière un proxy) :
`PORT=8000` ne change que le port ; modifier `server.py` pour l'adresse.

En service permanent :

**Windows** (NSSM, le plus simple) :
```
nssm install Aphrodite "C:\aphrodite\.venv\Scripts\python.exe"
nssm set Aphrodite AppParameters "server.py"
nssm set Aphrodite AppDirectory "C:\aphrodite"
nssm set Aphrodite AppStdout "C:\aphrodite\logs\waitress.log"
nssm set Aphrodite AppStderr "C:\aphrodite\logs\waitress.err.log"
nssm start Aphrodite
```
À écouter sur `127.0.0.1` quand un proxy est devant : le port ne doit pas être
joignable depuis l'extérieur.

**Linux** (`/etc/systemd/system/aphrodite.service`) :
```ini
[Unit]
Description=Aphrodite
After=network.target

[Service]
User=aphrodite
WorkingDirectory=/srv/aphrodite
EnvironmentFile=/srv/aphrodite/.env
Environment=APHRODITE_TRUSTED_PROXY=127.0.0.1,::1
ExecStart=/srv/aphrodite/.venv/bin/python server.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

---

## 5. Reverse proxy

### nginx

```nginx
server {
    listen 443 ssl http2;
    server_name aphrodite.example.com;
    client_max_body_size 8m;          # avatars 3 Mo, bannières 5 Mo

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;   # indispensable
    }

    # Médias publics : aperçus d'articles, offrandes, produits non payants.
    # Les avatars et bannières ne sont PLUS ici : ils passent par Django.
    location /media/ {
        alias /srv/aphrodite/media/;
        expires 7d;
        add_header Cache-Control "public";
    }

    # private_media/ n'apparaît JAMAIS ici : originaux, fichiers payants,
    # avatars et bannières (servis par Django, avec contrôle d'accès).
}
```

### IIS

Installer **URL Rewrite** et **ARR**, puis : règle de reverse proxy vers
`http://127.0.0.1:8000`, en-tête `X-Forwarded-Proto: https` ajouté sur la règle,
et un **virtual directory** `media` pointant sur `C:\aphrodite\media`.
Ne pas créer de répertoire virtuel pour `private_media`.

**À retenir** : `/static/` n'a pas besoin de règle (WhiteNoise s'en charge).
`/media/` doit être servi par le proxy, sinon les avatars et les aperçus
d'articles répondent 404. `/private_media/` ne doit **jamais** être exposé : c'est Django, et lui seul,
qui sert les avatars, les bannières, les originaux et les fichiers payants
après vérification des droits.

---

## 6. Tâches planifiées

Deux commandes doivent tourner sans toi. Sans elles, le monde se dérègle
silencieusement.

| Commande | Fréquence | Sans elle |
|---|---|---|
| `manage.py sauvegarder_base` | 1×/jour (nuit) | aucune copie de la base ; 14 dernières conservées |
| `manage.py traiter_commandes` | toutes les 15–30 min | commandes jamais confirmées ni expirées, Cubis séquestrés pour toujours, suppression de compte bloquée |

**Windows** (Planificateur de tâches → Action « Démarrer un programme ») :
```
Programme : C:\aphrodite\.venv\Scripts\python.exe
Arguments : manage.py sauvegarder_base
Démarrer dans : C:\aphrodite
```

**Linux** (crontab de l'utilisateur `aphrodite`) :
```cron
0 4 * * * cd /srv/aphrodite && .venv/bin/python manage.py sauvegarder_base >> logs/sauvegarde.log 2>&1
*/20 * * * * cd /srv/aphrodite && .venv/bin/python manage.py traiter_commandes >> logs/commandes.log 2>&1
```

Copier ensuite les sauvegardes **hors du serveur** (disque réseau, autre machine) :
une sauvegarde sur le même disque que la base ne protège pas d'une panne disque.

---

## 7. Checklist de mise en ligne

1. `DJANGO_DEBUG=0`, clé secrète neuve, `ALLOWED_HOSTS` et `CSRF_TRUSTED_ORIGINS` du domaine.
2. `manage.py check --deploy` : aucune alerte.
3. `manage.py migrate` : à jour.
4. `manage.py collectstatic --noinput` exécuté **après** le dernier `git pull`.
5. `createsuperuser` fait, compte propriétaire en `is_superuser` (seule à pouvoir réduire des Cubis et retirer un statut Créateur).
6. `installer_catalogue --proprietaire=…` : 10 offrandes + cadre noir.
   Puis `manage.py normaliser_cadres` si des cadres existaient déjà.
7. Vérifier que `private_media/` n'est pas lisible par le serveur web et que
   le compte du service y a accès en lecture.
8. Comptes et articles de test supprimés : `manage.py purger_demonstration`
   (liste d'abord, puis `--supprimer` pour agir). Les articles officiels
   partent avec les comptes de démo : relancer ensuite
   `installer_catalogue --proprietaire=<compte réel>`.
9. `waitress` lancé et supervisé (redémarrage automatique).
10. Proxy en HTTPS, `X-Forwarded-Proto` transmis, `/media/` servi, `/private_media/` absent.
11. Les deux tâches planifiées actives, une sauvegarde déclenchée à la main pour vérifier.
12. HSTS : commencer à `3600`, monter à un an seulement quand tout est stable.

---

## 8. Vérifications après déploiement

```bash
curl -I https://aphrodite.example.com/                       # 200
curl -I https://aphrodite.example.com/static/css/base.css    # 200 (ou nom haché)
curl -I https://aphrodite.example.com/media/                 # 403/404 attendu : il faut une image réelle
```

Puis dans un navigateur, en navigation privée :

- la page d'accueil s'affiche **avec** son style (si le CSS est absent : `collectstatic` oublié) ;
- l'inscription fonctionne (formulaire accepté) ;
- la connexion fonctionne et la session tient après un rechargement ;
- un avatar de profil s'affiche (sinon : règle `/media/` manquante) ;
- une page de commande s'ouvre.

---

## 9. Limites connues avant lancement

- **SQLite** : un seul écrivain. Convient au lancement ; voir `docs/migration-postgres.md` si la fréquentation monte.
- **Mot de passe oublié** : il n'y a pas d'email, donc pas de lien de réinitialisation. La procédure est manuelle et assumée : le membre prévient l'équipe, une Divinité ouvre `/divinites/membres/<id>/` et génère un mot de passe provisoire, qu'elle transmet en privé (WhatsApp). Le membre le remplace ensuite dans Paramètres → Mot de passe. L'action est inscrite au journal des actions.
- **Litiges** : une commande en litige bloque la suppression de compte de ses deux parties jusqu'à décision. Vider les litiges avant d'annoncer la fonction de suppression.
