# Aphrodite

Réseau social 18+ de la communauté WhatsApp RP : profils, Cubis (monnaie de jeu,
sans valeur réelle), boutique, inventaire, offrandes, créations.

## Prérequis

- Python 3.12 (3.11 ou 3.13 devraient passer, 3.12 est la version testée)
- Git
- PyCharm (Community suffit)

## Première installation (une seule fois)

Dans PyCharm : ouvre le projet, puis `Alt+F12` pour le terminal.

```bash
python -m venv .venv            # Windows : py -3.12 -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux
pip install -r requirements.txt
python manage.py migrate
python manage.py charger_offrandes_exemple
```

PyCharm doit utiliser ce même interpréteur : *Settings → Project → Python
Interpreter → Add Interpreter → Existing → `.venv`*.

## Lancer l'application

```bash
python manage.py runserver
```

Puis ouvrir http://127.0.0.1:8000/ dans le navigateur.

Sans rien configurer, l'application n'accepte que `localhost` et `127.0.0.1`.
Pour la tester depuis un téléphone sur le même Wi-Fi, ou depuis un nom de
domaine :

```bash
# Windows (cmd) : set VAR=valeur    |  PowerShell : $env:VAR="valeur"
DJANGO_ALLOWED_HOSTS="192.168.1.20" python manage.py runserver 0.0.0.0:8000
```

Si les formulaires renvoient une erreur 403 « CSRF », ajoute aussi le domaine :

```bash
DJANGO_ALLOWED_HOSTS="aphrodite.exemple.com" \
DJANGO_CSRF_TRUSTED_ORIGINS="https://aphrodite.exemple.com" \
python manage.py runserver 0.0.0.0:8000
```

## Configuration (`.env`)

Rien n'est obligatoire en local : l'application demarre sans configuration.
Pour tout regler, copie le modele fourni :

```bash
cp .env.example .env      # Windows : copy .env.example .env
```

`.env` n'est jamais envoye sur GitHub. Il contient la cle secrete, les domaines
acceptes et, si besoin, la base de donnees. Une variable definie dans
l'environnement du systeme a toujours priorite sur ce fichier.

En ligne, trois reglages sont obligatoires : `DJANGO_DEBUG=0`,
`DJANGO_SECRET_KEY` et `DJANGO_ALLOWED_HOSTS`. Sans eux, l'application refuse
de demarrer avec un message explicite plutot que de tourner en mode insouciant.

Generer une cle secrete :

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

## Catalogue de départ

Sur une installation neuve, la boutique et le catalogue d'offrandes sont vides :
ces objets vivent en base, pas dans git. Une seule commande les installe (10
offrandes, le cadre noir, et le cadre équipé sur ton compte) :

```bash
python manage.py installer_catalogue
```

Elle peut être relancée sans risque : rien n'est dupliqué. Pour choisir un autre
compte propriétaire : `--proprietaire ton@email`.

## Comptes de test

| Email | Mot de passe | Rôle |
|---|---|---|
| `safir@test.cg` | `Test12345!` | superutilisateur |
| `membre@test.cg` | `Test12345!` | membre simple |

Panel d'administration : http://127.0.0.1:8000/admin/

## Tests

```bash
python manage.py test
```

38 tests, doivent être verts avant chaque envoi sur GitHub.

## Sauvegardes

```bash
python manage.py sauvegarder_base
```

Ecrit `sauvegardes/db-AAAAMMJJ-HHMMSS.sqlite3.gz` sans interrompre le site (la
copie passe par l'API de sauvegarde de SQLite, elle est donc coherente même si
quelqu'un écrit au même moment). Les 14 dernières copies sont conservées ;
`--garder 30` change ce nombre, `--dossier /autre/chemin` change la
destination.

Sauvegarder une fois par jour ne sert que si c'est automatique. Sous Linux, une
tache quotidienne à 4 h :

```
0 4 * * * cd /chemin/aphrodite && .venv/bin/python manage.py sauvegarder_base
```

Une sauvegarde non testée n'existe pas. Celle du 11 novembre 2026 a été
restaurée pour vérification : intégrité SQLite `ok`, comptes, articles,
inventaire et offrandes présents. Refais ce contrôle après chaque changement
important : décompresse l'archive, vérifie `PRAGMA integrity_check`, ouvre
l'application dessus.

## Contenu du dépôt

- `apps/` : le code (accounts, economy, shop, inventory, creators, moderation,
  orders, notifications, social, offrandes)
- `templates/`, `static/css/base.css`, `composants.css`, `pages.css` : l'interface
- `static/images/offrandes/` : les 10 offrandes de départ (256×256)
- `static/images/cadres/cadre_noir.png` : cadre livré, 800×800 transparent
- `maquette/` : maquette HTML des écrans + aperçu PNG
- `docs/captures/` : captures des écrans réels de l'application
- `docs/registre-et-plan.md` : liste des défauts à corriger et calendrier
- `docs/migration-postgres.md` : bascule SQLite → PostgreSQL, étape par étape
- `.env.example` : modèle de configuration (à copier en `.env`)
- `LISEZMOI.txt` : historique, obsolète

## Contrat des cadres

Un cadre doit être un **PNG carré**, idéalement 800×800, avec un **vrai canal
alpha** : l'extérieur et le trou central transparents, le trou occupant environ
64 % de la largeur et parfaitement centré. Un damier gris et blanc peint dans
l'image est refusé par le formulaire.

## Git

```bash
git pull                                  # avant de commencer
git add <fichiers>
git commit -m "message court en français"
git push
```

Ne jamais versionner : `.venv/`, `db.sqlite3`, `media/`, `private_media/`,
`.env` (déjà exclus par `.gitignore`). Ne jamais utiliser `git push --force`.
