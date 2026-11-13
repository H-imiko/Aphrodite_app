# Aphrodite — consignes de travail

Application Django de communauté WhatsApp RP (18+) avec une monnaie virtuelle,
les Cubis. Interface et messages en français. Base SQLite.

## Commandes

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt   # installation
.venv/bin/python manage.py runserver                                # développement
.venv/bin/python manage.py test                                     # TOUS les tests
.venv/bin/python manage.py check --deploy                           # avec DJANGO_DEBUG=0
.venv/bin/python manage.py makemigrations --check --dry-run         # modèles non migrés
```

Le projet n'a **pas** de `package.json` : `npm test` n'existe pas et échouera.
La commande de test est `python manage.py test`, c'est aussi celle de la CI
(`.github/workflows/tests.yml`). La suite prend environ 2 min 20.

En production, lancer `python server.py` (jamais `waitress` directement : il
supprime `X-Forwarded-*` et casse la redirection HTTPS derrière nginx).

## Règles non négociables

- **`generator/` : ne jamais y toucher.** Les packs `.wastickers` sont confiés à
  un autre développeur. On ne modifie pas, ne déplace pas et ne reformate pas
  ce dossier, même si son code semble faux : on relève le problème et on le
  signale. (Le dossier n'existe pas encore dans le dépôt.)
- **Indentation :** Python en 4 espaces (PEP 8, tout le dépôt est ainsi ;
  des tabulations dans un `.py` provoquent des `TabError` et cassent la
  relecture). Tabulations uniquement dans le code JS/TS, le jour où il arrive.
- **Aucun secret dans le dépôt** : ni mot de passe, ni clé, ni identifiant de
  démonstration. Le dépôt est public. Tout passe par l'environnement
  (`.env` local, non suivi) ; voir `.env.example` et `docs/deploiement.md`.
- **Toute modification de modèle exige une migration** livrée avec le code.
- **Tout comportement nouveau ou corrigé exige un test.** Une régression
  signalée se corrige par un test qui échoue avant et passe après.
- Avant de considérer un travail fini : suite complète verte, `check --deploy`
  propre, aucune migration manquante.
- Le compte principal en production est **Safir** (superutilisateur). Un
  superutilisateur n'est jamais soumis aux plafonds du Trésor.

## Relecture en cinq angles

Chaque changement est relu sous ces cinq angles, avant d'être annoncé comme fini :

1. **Créateur** — l'écran est-il utilisable depuis un téléphone, sans notice ?
2. **Nouvel arrivant** — inscription, première visite, un inconnu comprend-il ?
3. **Manager / Safir** — l'administrateur peut-il modérer et réparer seul ?
4. **Attaquant** — que peut-on falsifier (prix, statut, identité, en-têtes) ?
5. **Designer** — cohérence visuelle, contraste, texte, accessibilité de base.

## Documentation

- `README.md` — présentation, installation, commandes.
- `docs/deploiement.md` — procédure de mise en ligne (nginx, systemd, variables).
- `docs/registre-et-plan.md` — journal des décisions et des corrections.
