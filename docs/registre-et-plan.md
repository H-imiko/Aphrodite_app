# Aphrodite — registre des défaillances et plan jusqu'au lancement

Dernière mise à jour : 9 novembre 2026

Ce document est la liste de travail unique. Chaque ligne se coche quand elle est
corrigée **et** vérifiée. Ordre = ordre d'exécution : on ne passe jamais au
niveau suivant en laissant un P0 ouvert.

---

## Définition du « gel des fonctionnalités »

Geler ≠ arrêter de coder. Geler veut dire :

- **Ce qui est déjà codé reste** et reçoit des tests. Rien n'est supprimé.
- **Aucune nouvelle fonctionnalité** n'entre dans le périmètre avant le
  lancement (pas de nouveau jeu, pas de nouvelle monnaie, pas d'arène, pas de
  refonte du modèle économique).
- **On ne code que trois choses** : corriger, sécuriser, rendre utilisable.
- Tout ce qui est « une bonne idée » va dans la section *Après le lancement*.
  Il n'est pas perdu, il est reporté.

Exemple concret : les offrandes sont déjà codées → elles ne sont pas une
nouveauté, elles entrent dans le sprint 4 (mise en catalogue + recette).
Les packs de stickers, eux, sont une nouveauté → version 1 = ZIP + tutoriel.

---

## P0 — bloquant pour une mise en ligne (à faire avant tout)

| # | Défaillance | Preuve / fichier | Correctif | Vérification |
|---|---|---|---|---|
| 1 ✅ | Secrets et réglages de prod en dur | `config/settings.py` L11-16 (`SECRET_KEY`, `DEBUG=True`, `ALLOWED_HOSTS=[]`) | variables d'environnement, `SECRET_KEY` générée, `DEBUG=False`, hôtes explicites | `check --deploy` sans avertissement critique |
| 2 ✅ | Aucune sauvegarde | — | dump quotidien de la base + médias, test de restauration | restaurer une base dans un environnement vide |
| 3 ✅ | HTTPS et cookies non sécurisés | `check --deploy` (7 avertissements) | redirection SSL, HSTS, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` | `check --deploy` propre |
| 4 | Double-dépense possible | `economy/services.py:_verrouiller` — `select_for_update` ignoré sur SQLite | PostgreSQL + transaction réelle | test de concurrence (2 threads, 1 solde) |
| 5 | Farm de Cubis multi-comptes | bonus quotidien + email non vérifié | email vérifié avant bonus, plafond par appareil/IP | test : 3 comptes neufs ne génèrent plus de Cubis |
| 6 | Aucune page de règlement alors que la case 18+ est obligatoire | `accounts/forms.py:InscriptionForm.accepte_cgu` | CGU + confidentialité rédigées et liées | la case pointe vers une page réelle |
| 7 | Signalement = masquage automatique (griefing) | `views_public.py:58` | masquage seulement après N signalements distincts ou décision d'une Gardienne | test : 1 signalement ne masque plus rien |

## P1 — indispensable pour que le site tienne debout

| # | Défaillance | Correctif | Vérification |
|---|---|---|---|
| 8 | Médiathèque payante : tout est public | URL signées ou contrôle d'accès par achat | un non-acheteur reçoit 403 |
| 9 | Pas de limitation de débit | throttling sur connexion, inscription, envoi d'offrande, signalement | test : 20 requêtes/min bloquées |
| 10 | Trésor quasi illimité | plafond quotidien + journal des envois | test : plafond respecté |
| 11 | Mot de passe oublié absent | parcours par email | parcours complet testé |
| 12 | Pas de suppression de compte | page + anonymisation | test : le compte disparaît, les contenus restent attribués à « Anonyme » |
| 13 | Aucun `README`, aucune CI | `README.md` (installation, tests, déploiement) + tests lancés à chaque push | un inconnu installe le projet en 10 min |
| 14 | Cadres non normalisés | canevas carré, trou à 64 %, contrôle à l'upload | upload d'un cadre hors spec refusé avec un message clair |

## P2 — qualité et image

| # | Défaillance | Correctif |
|---|---|---|
| 15 | Landing absente pour un visiteur non connecté | page publique : promesse, aperçu, inscription |
| 16 | Écran « modifier mon profil » à plat (`form.as_p`) | maquette `maquette/design.html` : blocs, vignettes de cadres, barre d'enregistrement |
| 17 | Écran de publication sans garde-fou visuel | dépôt de fichier + contrôle transparence/carré/trou avant envoi |
| 18 | 27 `alt=""`, 0 `aria`, 36 styles inline | alternatives textuelles, labels liés, contrastes |
| 19 | Offrandes 1 à 2 Mo pour une icône de 52 px | fait : 10 PNG 256×256 carrés, 954 Ko au total |
| 20 | Poids des pages sur mobile | vignettes servies à la taille d'affichage |

---

## Calendrier

| Sprint | Dates | Objectif | Sortie |
|---|---|---|---|
| S0 | 9–10 nov | filet de tests, gel, migrations propres | 36 tests verts ✅ |
| S1 | 11–17 nov | P0 1, 2, 3 + hébergement | app en ligne, HTTPS, sauvegardes |
| S2 | 18–24 nov | P0 4, 5, 7 + P1 9, 10 | économie non manipulable |
| S3 | 25 nov–1 déc | P0 6 + P1 11, 12 + P2 15, 16, 17 | parcours membre complet |
| S4 | 2–8 déc | P2 14, 18, 19, 20 + recette sur téléphone | catalogue prêt, bugs visuels corrigés |
| Buffer | 9–15 déc | corrections, répétition générale | lancement |

## Règles de travail

1. Un sprint = un objectif. On ne mélange pas sécurité et nouveauté.
2. Rien ne part en production sans `python manage.py test` vert **et**
   `python manage.py check --deploy` propre.
3. Un bug se signale par son symptôme (« le cadre est décalé à gauche sur mon
   téléphone »), pas par un diagnostic.
4. Toute correction de faille arrive avec le test qui la reproduit.

## Après le lancement

- packs de stickers au format `.wastickers` ;
- saisons et reliques ;
- commande personnalisée avec suivi de livraison WhatsApp ;
- statistiques créateur ;
- application mobile.
