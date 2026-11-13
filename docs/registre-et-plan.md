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
| 4 ✅ | Double-dépense possible | `economy/services.py:_verrouiller` — `select_for_update` ignoré sur SQLite | PostgreSQL + transaction réelle | test de concurrence (2 threads, 1 solde) |
| 5 🟡 | Farm de Cubis multi-comptes | bonus quotidien + email non vérifié | email vérifié avant bonus, plafond par appareil/IP | test : 3 comptes neufs ne génèrent plus de Cubis |
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

---

## État d'avancement — 11 novembre 2026

| Sprint | Objectif | État |
|---|---|---|
| S0 | filet de tests, gel, migrations propres | ✅ 44 tests verts |
| S1 | P0 1-3 : clé secrète, configuration, sauvegardes, HTTPS | ✅ fait et vérifié |
| S2 | P0 4-5 : économie non manipulable | 🟡 P0 4 fait ; P0 5 partiel (plafond par appareil, pas d'email vérifié) |
| S3 | P0 6 + P1 11-12 : CGU, mot de passe oublié, suppression de compte | ⬜ à faire |
| S4 | P2 14, 18-20 : cadres normalisés, accessibilité, poids des pages | ⬜ à faire |
| Buffer | corrections, répétition générale | ⬜ |

### Ce qui manque encore pour lancer

1. **P0 6 — pages de règlement** : la case 18+ obligatoire ne renvoie vers
   aucun texte. C'est le seul P0 encore ouvert ; sans lui, l'inscription
   recueille un consentement qui n'existe pas.
2. **P1 11 — mot de passe oublié** : un membre qui perd son mot de passe est
   perdu, définitivement.
3. **P1 12 — suppression de compte** : obligatoire pour une app 18+.
4. **P0 5 — email vérifié avant bonus** : demande un service d'envoi d'emails
   et des enregistrements DNS, donc une inscription chez un prestataire.
5. **P1 9 — limitation de débit** sur connexion, inscription, offrandes et
   signalements.
6. **Hébergement** : nom de domaine, HTTPS, tâche de sauvegarde quotidienne.
7. **P2 18 — accessibilité** : partiel (icônes de l'en-tête en SVG avec
   `aria-label`, formulaires liés à leurs libellés).

### Fait le 11 novembre

- Rendu commun des formulaires (`partials/champs.html`) : libellés, champs,
  textes d'aide et erreurs alignés ; appliqué aux 12 écrans de formulaire.
- `modifier_profil.html` ne commence plus par un document HTML parasite, qui
  cassait l'affichage de la page.
- Icônes de l'en-tête en SVG (engrenage, colis, cloche) au lieu d'emojis.
- `python manage.py installer_catalogue` : 10 offrandes + cadre noir + cadre
  équipé, en une commande idempotente. C'était la cause des « catalogues vides ».

---

## État au 12 novembre 2026 — corrections avant lancement

Les points ci-dessous ont été corrigés et vérifiés par des tests
(`python manage.py test` : 157 tests verts, `check --deploy` propre).

| Point | Correctif | Preuve |
|---|---|---|
| P0 5 farm de bonus | plafond par appareil conservé, limitation de débit sur inscription et connexion | `test_connexion_bloquee_apres_trop_d_essais`, `test_inscription_bloquee...`, `FarmBonusTests` |
| P0 7 griefing | un article n'est masqué qu'après 3 signaleurs distincts (2 pour mineur/illégal) | `apps/moderation/test_signalements.py` |
| P1 9 limitation de débit | connexion, inscription, offrande, signalement, transfert, trésor | `apps/commun/limites.py` + tests |
| P1 10 trésor illimité | 5 000 par envoi et 50 000 par jour pour une Gardienne ; Safir sans plafond | `test_gardienne_plafonnee_par_jour` |
| P1 11 mot de passe oublié | demande publique sans email, traitée dans le panel ; mot de passe provisoire à changer d'office | `DemandeAccesTests`, `MotDePasseProvisoireTests` |
| P1 12 suppression de compte | déjà en place, conservée | `CompteTests` |
| P1 13 CI | `.github/workflows/tests.yml` (tests + check --deploy) | workflow |
| P1 14 cadres | trou mesuré et stocké, largeur calculée (`100 / ratio`), validation carré / centrage / 40–85 % | `apps/shop/tests.py` |
| P2 16 profil | écran recomposé en blocs (photos, identité, contenu mature) avec aperçu en direct | `/profil/modifier/` |
| P2 17 publication | écran recomposé en deux colonnes + aperçu de l'image + bloc audio/vidéo contextuel | `/mes-articles/nouveau/` |
| Photos matures | stockage privé, servies par une vue qui vérifie l'accord du visiteur | `PhotoProfilTests` |
| Double paiement des commandes | statut revendiqué par écriture conditionnelle (select_for_update est inopérant sur SQLite) | `apps/orders/tests.py` |
| Achat simultané | contrainte d'inventaire interceptée, pas de double débit | `test_second_achat_refuse_sans_deuxieme_debit` |

### Ce qui reste ouvert, assumé

- **Email vérifié** : impossible sans service d'envoi ; remplacé par le plafond
  par appareil et la limitation de débit. À faire quand un prestataire email
  sera choisi.
- **Cache partagé** : la limitation de débit compte par processus. Passer à
  Redis si le site tourne sur plusieurs processus.
- **Packs de stickers `.wastickers`** : confiés à un autre développeur.
- **Accessibilité** : partielle (libellés, icônes nommées) ; les emojis
  décoratifs restent à nettoyer écran par écran.

### Prime mensuelle des créateurs — 12 novembre 2026

Une prime fixe de 10 000 Cubis par créateur publiant 5 articles a été
écartée : dans l'économie actuelle (bonus quotidien ~20, prix 10–100), elle
vaudrait 25 ventes de stickers et récompenserait le volume plutôt que le
travail. Remplacée par un podium mensuel (5 000 / 2 000 / 1 000) fondé sur
les Cubis encaissés puis les likes, avec un seuil de 5 articles actifs et une
preuve d'utilité. Commande idempotente `primes_createurs`, simulation par
défaut. Tests : `apps/creators/tests.py` (9 tests).

### Audit du 12 novembre 2026 — régressions corrigées

Deux régressions introduites par les correctifs de la veille, trouvées par
relecture et couvertes par des tests :

1. **Décision de litige perdue.** `trancher()` posait `tranche_par` et
   `decision` sur l'objet en mémoire, en comptant sur le `save()` global de
   `_rembourser()`/`_liberer()`. Ces fonctions revendiquent désormais le statut
   par écriture conditionnelle et ne sauvent plus l'objet entier : la décision
   n'était plus écrite. Corrigé par un `update()` explicite, qui sert aussi de
   revendication (deux décisions simultanées : une seule passe).
   Tests : `test_decision_de_litige_enregistree`,
   `test_decision_de_litige_en_faveur_du_createur_enregistree`.
2. **Limitation de débit contournable.** Le compteur lisait la **première**
   valeur de `X-Forwarded-For`, en-tête entièrement contrôlé par le client :
   il suffisait de la changer à chaque requête pour repartir de zéro.
   Corrigé : `REMOTE_ADDR` par défaut, `X-Forwarded-For` uniquement si
   `DJANGO_USE_X_FORWARDED_FOR=1`, et alors la **dernière** valeur (celle du
   proxy). Ajout d'un compteur global par IP sur la connexion, qui bloque le
   balayage de mots de passe sur des comptes différents.
   Tests : `test_entete_forwarded_for_ne_contourne_pas_la_limite`,
   `test_balayage_sur_plusieurs_comptes_bloque_par_adresse`.

Autres points trouvés pendant le même audit :

- la limitation de débit des signalements était annoncée dans le README mais
  **pas branchée** : elle l'est maintenant, avec un test ;
- la suppression de compte laissait les demandes d'accès (adresse email) en
  base : elles sont désormais effacées ;
- la commande des primes pouvait planter sur deux lancements simultanés
  (`IntegrityError`) : l'erreur est absorbée, une seule prime est versée.

### Avant mise en ligne — 13 novembre 2026

- **Page publique « Créateurs du mois »** (`/createurs/du-mois/`) : podium
  calculé sur les Cubis encaissés puis les likes, vitrine du 1er, palmarès des
  primes versées, accessible sans compte. 5 tests.
- **Page Confidentialité** (`/confidentialite/`) : décrit les données réellement
  stockées, qui les voit, la durée de conservation et les droits. Liée depuis le
  règlement et la case d'inscription. 3 tests.
- **Pages 404 et 500** lisibles en production (le mode debug ne les sert plus).
- **Bloqueur de déploiement trouvé par un test réel** : Waitress 3 supprime par
  défaut `X-Forwarded-*`. Lancé comme le documentait `docs/deploiement.md`,
  Django ne voyait jamais le HTTPS et redirigeait en boucle, et toutes les
  requêtes portaient l'adresse du proxy — donc limitation de débit faussée.
  Corrigé par `server.py`, qui déclare le proxy de confiance à Waitress.
  Vérifié de bout en bout : collectstatic, waitress, 200 sur les pages, CSS
  avec empreinte servi, 404 personnalisée, `X-Forwarded-For` pris en compte
  uniquement depuis le proxy.
