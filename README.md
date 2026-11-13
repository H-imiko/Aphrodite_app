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

Après l'ajout de cadres en dehors de l'application (par un créateur, ou par
import), mesure leurs trous une fois pour aligner l'affichage :

```bash
python manage.py normaliser_cadres --simuler   # montre, n'écrit rien
python manage.py normaliser_cadres             # enregistre
```

## Comptes

Aucun compte n'est livré avec le dépôt : les mots de passe ne sont jamais
écrits dans un fichier suivi par Git. Pour le premier compte (Safir, le compte
principal), en local :

```bash
python manage.py createsuperuser
```

Ou sans saisie interactive, avec le mot de passe fourni par l'environnement :

```bash
DJANGO_SUPERUSER_PASSWORD='...' python manage.py createsuperuser \
  --noinput --username safir --email safir@exemple.cg
```

Panel d'administration : http://127.0.0.1:8000/admin/

> Les identifiants de démonstration qui figuraient ici ont été retirés : ce
> dépôt est public, et un mot de passe publié reste lisible dans l'historique
> Git même après suppression. Si un compte a déjà utilisé un mot de passe
> présent dans l'historique, change-le :
> `python manage.py changepassword <identifiant>`.

## Tests

```bash
python manage.py test
```

157 tests, doivent être verts avant chaque envoi sur GitHub. Une CI les
rejoue à chaque push (`.github/workflows/tests.yml`), avec
`check --deploy`.

Les tests couvrent ce qui peut coûter cher : séquestre et paiement des
commandes (dont les doubles validations simultanées), achats, offrandes
(plafonds et blocages), likes et abonnements, cadres, limitation de débit,
mots de passe provisoires et photos matures.

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
- `docs/deploiement.md` : mise en ligne (waitress, WhiteNoise, proxy, tâches planifiées)
- `.env.example` : modèle de configuration (à copier en `.env`)
- `LISEZMOI.txt` : historique, obsolète

## Contrat des cadres

Un cadre doit être un **PNG ou WebP carré**, 800×800 conseillé, avec un **vrai
canal alpha** : l'extérieur et le trou central transparents, trou centré
entre 40 % et 85 % de la largeur. Un damier gris et blanc peint dans l'image
est refusé.

La taille du trou n'est pas imposée : elle est **mesurée à l'envoi** et
stockée sur l'article. Le profil affiche le cadre à la largeur qui fait
correspondre le trou à la photo de profil (`100 / ratio`), donc un cadre de
60 % et un cadre de 64 % s'affichent tous les deux correctement. Le cadre
noir livré a un trou de 60 %, d'où son affichage à 166,67 %.

## Photos de profil protégées

Les avatars et bannières ne sont plus dans `media/` : ils sont stockés dans
`private_media/` et servis par `/membre/<id>/photo/<avatar|banniere>/`. Une
photo marquée « mature » n'est visible que par son propriétaire et par les
membres qui ont coché « Afficher le contenu mature ». Le flou du navigateur
n'est plus la seule barrière : le fichier n'est pas accessible par sa seule
URL. Cela vaut aussi pour les photos anciennes, déplacées automatiquement par
la migration.

## Mot de passe oublié et comptes

Il n'y a pas d'email sortant. Le membre dépose une demande sur
`/mot-de-passe-oublie/` ; elle apparaît dans **Panel → Demandes d'accès**. Une
Divinité vérifie l'identité sur WhatsApp, puis génère un mot de passe
provisoire depuis la fiche du membre. Ce mot de passe **ne donne pas le
compte** : la personne doit en choisir un autre dès sa connexion (elle est
redirigée vers l'écran de changement).

Une Divinité ne peut pas réinitialiser le mot de passe d'une autre Divinité :
seule Safir le peut, et jamais le sien par ce chemin.

## Prime mensuelle des créateurs

Un créateur qui publie beaucoup ne gagne presque rien : 10 000 Cubis par
mois seraient l'équivalent de 25 ventes de stickers, et paieraient le volume
plutôt que le travail. D'où un **podium mensuel** fondé sur ce que la
communauté a réellement acheté et aimé :

- éligible : créateur validé, non Divinité, **5 articles actifs publiés dans
  le mois**, et une preuve d'utilité (au moins une vente, ou 5 likes reçus) ;
- classement : Cubis encaissés dans le mois, puis likes, puis articles ;
- montants : 5 000 / 2 000 / 1 000 (réglage `PRIMES_CREATEURS`).

La commande ne verse rien par défaut :

```bash
python manage.py primes_createurs --mois 2026-11            # simulation
python manage.py primes_createurs --mois 2026-11 --appliquer # paie
```

Sans `--mois`, elle traite le mois précédent. Relancer la commande ne paie
jamais deux fois le même créateur pour le même mois (`PrimeCreateur` sert de
verrou), et chaque prime est une transaction `BONUS_CREATEUR` notifiée et
journalisée.

La page publique `/createurs/du-mois/` affiche le podium en direct (Cubis
encaissés, likes, articles) et le palmarès des primes déjà versées. Elle est
accessible sans compte, depuis la page d'accueil.

## Mise en ligne

Le lanceur de production est `server.py`, pas `waitress` directement :
Waitress 3 supprime par défaut les en-têtes `X-Forwarded-*`, ce qui fait
boucler la redirection HTTPS derrière nginx. `server.py` déclare le proxy de
confiance (`APHRODITE_TRUSTED_PROXY`, `127.0.0.1` par défaut). Voir
`docs/deploiement.md`.

## Limites anti-abus

| Action | Limite par défaut |
|---|---|
| Connexion | 8 tentatives / 5 min (par IP + adresse) et 30 / 5 min par IP tous comptes confondus |
| Inscription | 10 / 15 min |
| Offrande | 20 / 10 min |
| Signalement | 10 / 10 min |
| Transfert de Cubis | 20 / 10 min |
| Trésor | 30 / 10 min |

Le compteur vit dans le cache Django. Avec plusieurs processus, brancher un
cache partagé (Redis) sinon chaque processus compte séparément.

Le Trésor est plafonné pour une Gardienne : 5 000 Cubis par envoi et
50 000 Cubis par jour. Safir (superutilisatrice) distribue sans limite. Deux
réglages : `DJANGO_LIMITE_ENVOI_GARDIENNE`, `DJANGO_PLAFOND_JOURNALIER_TRESOR`.

Un signalement isolé ne masque plus un article : il faut 3 membres distincts
(2 pour un motif grave : mineur, contenu illégal).

## Git

```bash
git pull                                  # avant de commencer
git add <fichiers>
git commit -m "message court en français"
git push
```

Ne jamais versionner : `.venv/`, `db.sqlite3`, `media/`, `private_media/`,
`.env` (déjà exclus par `.gitignore`). Ne jamais utiliser `git push --force`.
