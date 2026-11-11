# Passer de SQLite à PostgreSQL

Décision actuelle : **rester sur SQLite pour le lancement de décembre**, et
exécuter cette bascule en S2, en même temps que le P0 n°4 (double-dépense).
Ce document existe pour que la bascule reste une opération de dix minutes et
non un chantier.

## Pourquoi ne pas basculer tout de suite

À ton échelle (une communauté WhatsApp, quelques centaines de comptes, un
serveur unique), SQLite suffit : c'est un fichier, il n'y a aucun service à
administrer, aucune sauvegarde serveur à surveiller, et il est plus rapide que
PostgreSQL sur des lectures simples.

Ce que SQLite ne sait pas faire, et qui compte pour toi :

1. **`SELECT ... FOR UPDATE`** n'existe pas. Le verrou de la file de Cubis ne
   protège donc rien → double-dépense possible (P0 4).
2. **Un seul écrivain à la fois.** Sous forte charge, les écritures font la
   queue. Ce n'est pas un problème à 50 membres connectés, ça en devient un audelà.
3. **Une seule machine.** Impossible de répartir la charge sur deux serveurs.

Point important : le double-dépense **n'exige pas PostgreSQL**. Il se corrige
aussi en SQLite, avec des écritures conditionnelles du type
`UPDATE ... SET solde = solde - X WHERE solde >= X` et un contrôle du nombre de
lignes modifiées, dans une transaction. PostgreSQL rend simplement la chose plus
simple et plus sûre à mesure que le trafic monte.

Tu peux donc lancer en décembre sur SQLite **à condition** que le P0 4 soit
corrigé par écriture conditionnelle, et que la sauvegarde quotidienne tourne.

## Ce qui est déjà prêt

`config/settings.py` lit la base dans l'environnement : **aucune ligne de code
à modifier** pour changer de moteur, seulement des variables.

## Bascule (à faire en S2)

### 1. Installer le pilote

```bash
pip install "psycopg[binary]"
pip freeze > requirements.txt      # ou ajoute la ligne psycopg à la main
```

### 2. Créer la base (sur le serveur)

```bash
sudo -u postgres psql <<'SQL'
CREATE USER aphrodite WITH PASSWORD 'un-mot-de-passe-long';
CREATE DATABASE aphrodite OWNER aphrodite;
SQL
```

### 3. Renseigner `.env`

```
DJANGO_DB_ENGINE=postgres
POSTGRES_DB=aphrodite
POSTGRES_USER=aphrodite
POSTGRES_PASSWORD=le-mot-de-passe
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
```

### 4. Créer le schéma et transférer les données

```bash
python manage.py migrate

# Si tu as des données à conserver (utilisateurs, articles, Cubis) :
# 1) avec SQLite encore actif
python manage.py dumpdata --natural-foreign --natural-primary \
    -e contenttypes -e auth.permission -e sessions \
    -o sauvegardes/donnees.json
# 2) après avoir basculé sur PostgreSQL
python manage.py loaddata sauvegardes/donnees.json
```

Les fichiers (`media/`, `private_media/`) ne sont pas dans la base : copie les
dossiers tels quels, les chemins enregistrés ne changent pas.

### 5. Vérifier

```bash
python manage.py check --deploy
python manage.py test
python manage.py shell -c "from django.db import connection; print(connection.vendor)"
```

Attendu : `postgresql`, 38 tests verts, `check --deploy` sans avertissement
critique.

### 6. Sauvegardes

`manage.py sauvegarder_base` ne gère que SQLite et refuse de tourner sur
PostgreSQL. Une fois basculé, la sauvegarde devient :

```bash
pg_dump -Fc aphrodite > /var/sauvegardes/aphrodite-$(date +%Y%m%d).dump
```

Restauration : `pg_restore -d aphrodite --clean /chemin/aphrodite-20261201.dump`

## Retour arrière

Tant que SQLite n'est pas supprimé, revenir en arrière = retirer
`DJANGO_DB_ENGINE=postgres` du `.env` et redémarrer. Garde une copie du fichier
`db.sqlite3` avant la bascule, elle reste valable.
