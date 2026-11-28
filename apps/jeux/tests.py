from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.economy.models import Transaction
from apps.economy.services import ErreurEconomie
from . import services
from .models import Partie

MDP = "MotDePasse!2026"
GAGNE = (True, Decimal("1.8"), "Face")
PERDU = (False, Decimal("0"), "Pile")


def compte(email="joueur@test.cg", solde=100, **extra):
    user = User.objects.create_user(
        email=email, password=MDP,
        pseudo_whatsapp=email.split("@")[0], **extra)
    if solde:
        User.objects.filter(pk=user.pk).update(solde_cubis=solde)
        user.refresh_from_db()
    return user


class MiseTests(TestCase):
    def setUp(self):
        cache.clear()
        self.joueur = compte()

    def test_mise_sous_le_minimum_refusee(self):
        with self.assertRaises(ErreurEconomie):
            services.jouer(self.joueur, "pile_ou_face", services.mise_min() - 1)

        self.assertFalse(Partie.objects.exists())
        self.assertEqual(self.joueur.solde_cubis, 100)

    def test_mise_au_dessus_du_maximum_refusee(self):
        with self.assertRaises(ErreurEconomie):
            services.jouer(self.joueur, "roue", services.mise_max() + 1)

        self.assertFalse(Partie.objects.exists())

    def test_solde_insuffisant_refuse(self):
        pauvre = compte("pauvre@test.cg", solde=5)
        with self.assertRaises(ErreurEconomie):
            services.jouer(pauvre, "roue", 10)

        self.assertFalse(Partie.objects.exists())

    def test_compte_suspendu_refuse(self):
        self.joueur.est_suspendu = True
        self.joueur.save(update_fields=["est_suspendu"])

        with self.assertRaises(ErreurEconomie):
            services.jouer(self.joueur, "roue", 10)

    def test_niveau_de_braquage_inconnu_refuse(self):
        with self.assertRaises(ErreurEconomie):
            services.jouer(self.joueur, "braquage", 10, "triche")

        self.assertFalse(Partie.objects.exists())

    def test_jeu_inconnu_refuse(self):
        with self.assertRaises(ErreurEconomie):
            services.jouer(self.joueur, "machine_a_sous", 10)

    def test_pile_ou_face_sans_choix_refuse(self):
        with self.assertRaises(ErreurEconomie):
            services.jouer(self.joueur, "pile_ou_face", 10)

        self.joueur.refresh_from_db()
        self.assertFalse(Partie.objects.exists())
        self.assertEqual(self.joueur.solde_cubis, 100)

    def test_pile_ou_face_gagne_avec_la_bonne_face(self):
        with patch("apps.jeux.services.random.random", return_value=0.2):
            partie, _ = services.jouer(self.joueur, "pile_ou_face", 10,
                                       choix="face")

        self.joueur.refresh_from_db()
        self.assertTrue(partie.gagne)
        self.assertEqual(partie.detail, "Face")
        self.assertEqual(partie.gain, 19)
        self.assertEqual(self.joueur.solde_cubis, 109)

    def test_pile_ou_face_perd_avec_l_autre_face(self):
        with patch("apps.jeux.services.random.random", return_value=0.2):
            partie, _ = services.jouer(self.joueur, "pile_ou_face", 10,
                                       choix="pile")

        self.joueur.refresh_from_db()
        self.assertFalse(partie.gagne)
        self.assertEqual(partie.detail, "Face")
        self.assertEqual(self.joueur.solde_cubis, 90)

    def test_poker_garde_l_egalite_pour_le_bot(self):
        # Deux As de couleurs différentes : le bot garde la mise.
        with patch("apps.jeux.services.random.sample", return_value=[12, 25]):
            partie, _ = services.jouer(self.joueur, "poker", 10)

        self.assertFalse(partie.gagne)
        self.assertEqual(partie.detail, "Toi A♠ · bot A♥")

    def test_poker_la_plus_haute_carte_gagne(self):
        with patch("apps.jeux.services.random.sample", return_value=[12, 0]):
            partie, _ = services.jouer(self.joueur, "poker", 10)

        self.joueur.refresh_from_db()
        self.assertTrue(partie.gagne)
        self.assertEqual(partie.detail, "Toi A♠ · bot 2♠")
        self.assertEqual(partie.gain, 19)


class ReglementTests(TestCase):
    def setUp(self):
        cache.clear()
        self.joueur = compte()

    def test_gain_credite_et_trace(self):
        with patch("apps.jeux.services.pile_ou_face", return_value=GAGNE):
            partie, consolation = services.jouer(self.joueur, "pile_ou_face",
                                                 10)

        self.joueur.refresh_from_db()
        self.assertTrue(partie.gagne)
        self.assertEqual(partie.gain, 18)
        self.assertEqual(self.joueur.solde_cubis, 108)
        self.assertEqual(consolation, 0)
        self.assertTrue(Transaction.objects.filter(
            type=Transaction.Type.JEU, destinataire=self.joueur,
            montant=18).exists())

    def test_perte_debite_la_mise(self):
        with patch("apps.jeux.services.pile_ou_face", return_value=PERDU):
            partie, _ = services.jouer(self.joueur, "pile_ou_face", 10)

        self.joueur.refresh_from_db()
        self.assertFalse(partie.gagne)
        self.assertEqual(partie.gain, 0)
        self.assertEqual(self.joueur.solde_cubis, 90)
        self.assertTrue(Transaction.objects.filter(
            type=Transaction.Type.JEU, expediteur=self.joueur,
            montant=10).exists())

    def test_huit_parties_par_jour_maximum(self):
        with patch("apps.jeux.services.roue", return_value=GAGNE):
            for _ in range(services.parties_max()):
                services.jouer(self.joueur, "roue", services.mise_min())

            with self.assertRaises(ErreurEconomie):
                services.jouer(self.joueur, "roue", services.mise_min())

        self.assertEqual(Partie.objects.count(), services.parties_max())

    def test_plafond_de_perte_journalier(self):
        riche = compte("riche@test.cg", solde=1000)
        mise = 100
        nombre = services.perte_max() // mise
        with patch("apps.jeux.services.braquage", return_value=PERDU):
            for _ in range(nombre):
                services.jouer(riche, "braquage", mise, "difficile")

            self.assertEqual(services.pertes_du_jour(riche),
                             services.perte_max())
            with self.assertRaises(ErreurEconomie) as capture:
                services.jouer(riche, "braquage", mise, "difficile")

        self.assertIn("perdu", str(capture.exception))
        self.assertEqual(Partie.objects.count(), nombre)

    def test_consolation_apres_trois_pertes(self):
        with patch("apps.jeux.services.roue", return_value=PERDU):
            services.jouer(self.joueur, "roue", 10)
            services.jouer(self.joueur, "roue", 10)
            _, consolation = services.jouer(self.joueur, "roue", 10)

        self.assertGreaterEqual(consolation, services.CONSOLATION_MIN)
        self.assertLessEqual(consolation, services.CONSOLATION_MAX)
        self.joueur.refresh_from_db()
        self.assertEqual(self.joueur.solde_cubis, 70 + consolation)
        self.assertTrue(Transaction.objects.filter(
            type=Transaction.Type.JEU,
            description__startswith="Consolation").exists())

    def test_pas_de_consolation_hors_troisieme_perte(self):
        with patch("apps.jeux.services.roue", return_value=PERDU):
            services.jouer(self.joueur, "roue", 10)
            _, consolation = services.jouer(self.joueur, "roue", 10)

        self.assertEqual(consolation, 0)

    def test_consolation_remise_a_zero_par_une_victoire(self):
        with patch("apps.jeux.services.roue", return_value=PERDU):
            services.jouer(self.joueur, "roue", 10)
            services.jouer(self.joueur, "roue", 10)
        with patch("apps.jeux.services.roue", return_value=GAGNE):
            services.jouer(self.joueur, "roue", 10)

        self.assertEqual(services.pertes_du_jour(self.joueur), 20)
        with patch("apps.jeux.services.roue", return_value=PERDU):
            _, consolation = services.jouer(self.joueur, "roue", 10)

        self.assertEqual(consolation, 0)


class HabillageTests(TestCase):
    """Données d'affichage envoyées au navigateur pour les animations."""

    def setUp(self):
        cache.clear()
        self.joueur = compte()

    def test_chaque_segment_de_roue_a_son_angle(self):
        for index, (_multiplicateur, _poids, libelle) in enumerate(
                services.ROUE):
            angle = services.angle_roue(libelle)
            self.assertEqual(angle % 360, (360 - (index * 60 + 30)) % 360)

    def test_angle_de_roue_inconnu_sans_animation(self):
        self.assertIsNone(services.angle_roue("x42"))

    def test_animation_de_la_roue_suit_le_segment_tire(self):
        partie = Partie.objects.create(
            user=self.joueur, jeu=Partie.Jeu.ROUE, mise=10, gagne=True,
            gain=30, detail="x3")

        self.assertEqual(services.animation(partie),
                         {"angle": services.angle_roue("x3")})

    def test_animation_de_la_piece_donne_le_cote_tombe(self):
        partie = Partie.objects.create(
            user=self.joueur, jeu=Partie.Jeu.PILE_OU_FACE, mise=10,
            detail="Pile")

        self.assertEqual(services.animation(partie), {"cote": "pile"})

    def test_animation_du_poker_relit_les_deux_cartes(self):
        partie = Partie.objects.create(
            user=self.joueur, jeu=Partie.Jeu.POKER, mise=10,
            detail="Toi A♠ · bot 7♦")

        self.assertEqual(services.animation(partie),
                         {"joueur": "A♠", "bot": "7♦"})

    def test_benefice_net_deduit_la_mise(self):
        partie = Partie.objects.create(
            user=self.joueur, jeu=Partie.Jeu.ROUE, mise=10, gagne=True,
            gain=19)

        self.assertEqual(partie.benefice, 9)


class DemineurTests(TestCase):
    def setUp(self):
        cache.clear()
        self.joueur = compte()

    def test_mine_perd_la_mise(self):
        with patch("apps.jeux.services.random.sample", return_value=[0, 4]):
            partie = services.demarrer_mines(self.joueur, 10)
            partie, consolation = services.ouvrir(partie, 4)

        self.joueur.refresh_from_db()
        self.assertFalse(partie.en_cours)
        self.assertFalse(partie.gagne)
        self.assertEqual(partie.detail, "Mine")
        self.assertEqual(self.joueur.solde_cubis, 90)
        self.assertGreaterEqual(consolation, 0)

    def test_case_sure_puis_encaissement(self):
        with patch("apps.jeux.services.random.sample", return_value=[0, 1]):
            partie = services.demarrer_mines(self.joueur, 10)
            partie, _ = services.ouvrir(partie, 2)

            self.assertTrue(partie.en_cours)
            self.assertEqual(partie.multiplicateur, "1.3")
            self.assertEqual(services.gain_potentiel(partie), 13)

            partie = services.encaisser(partie)

        self.joueur.refresh_from_db()
        self.assertFalse(partie.en_cours)
        self.assertTrue(partie.gagne)
        self.assertEqual(partie.gain, 13)
        self.assertEqual(self.joueur.solde_cubis, 103)

    def test_toutes_les_cases_sures_encaissent_seules(self):
        with patch("apps.jeux.services.random.sample", return_value=[0, 1]):
            partie = services.demarrer_mines(self.joueur, 10)
            for case in (2, 3, 4, 5, 6, 7, 8):
                partie, _ = services.ouvrir(partie, case)

        self.joueur.refresh_from_db()
        self.assertFalse(partie.en_cours)
        self.assertTrue(partie.gagne)
        self.assertEqual(partie.gain, 20)
        self.assertEqual(self.joueur.solde_cubis, 110)

    def test_case_deja_ouverte_refusee(self):
        with patch("apps.jeux.services.random.sample", return_value=[0, 1]):
            partie = services.demarrer_mines(self.joueur, 10)
            services.ouvrir(partie, 2)

            with self.assertRaises(ErreurEconomie):
                services.ouvrir(partie, 2)

    def test_encaisser_sans_case_refuse(self):
        with patch("apps.jeux.services.random.sample", return_value=[0, 1]):
            partie = services.demarrer_mines(self.joueur, 10)

        with self.assertRaises(ErreurEconomie):
            services.encaisser(partie)

        self.joueur.refresh_from_db()
        self.assertEqual(self.joueur.solde_cubis, 90)

    def test_une_seule_partie_en_cours(self):
        with patch("apps.jeux.services.random.sample", return_value=[0, 1]):
            services.demarrer_mines(self.joueur, 10)

            with self.assertRaises(ErreurEconomie):
                services.demarrer_mines(self.joueur, 10)


class VuesTests(TestCase):
    def setUp(self):
        cache.clear()
        self.joueur = compte()

    def test_hall_reserve_aux_membres(self):
        reponse = self.client.get(reverse("jeux"))
        self.assertEqual(reponse.status_code, 302)

        self.client.force_login(self.joueur)
        reponse = self.client.get(reverse("jeux"))
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Jeu de hasard")

    def test_icone_manette_dans_la_navigation(self):
        self.client.force_login(self.joueur)

        reponse = self.client.get(reverse("boutique"))

        self.assertContains(reponse, 'href="{}"'.format(reverse("jeux")))
        self.assertContains(reponse, "manette.svg")

    def test_jouer_par_post(self):
        self.client.force_login(self.joueur)
        # La connexion sert le bonus du jour : on part du solde réel d'après
        # connexion, pas du solde posé avant.
        self.joueur.refresh_from_db()
        avant = self.joueur.solde_cubis
        with patch("apps.jeux.services.pile_ou_face", return_value=GAGNE):
            reponse = self.client.post(reverse("jeu", args=["pile_ou_face"]),
                                       {"mise": "10"})

        self.assertEqual(reponse.status_code, 302)
        self.assertEqual(Partie.objects.count(), 1)
        self.joueur.refresh_from_db()
        self.assertEqual(self.joueur.solde_cubis, avant - 10 + 18)

    def test_page_roue_affiche_la_roue_et_l_angle_du_tirage(self):
        self.client.force_login(self.joueur)
        with patch("apps.jeux.services.roue", return_value=(
                True, Decimal("3.0"), "x3")):
            self.client.post(reverse("jeu", args=["roue"]), {"mise": "10"})
        partie = Partie.objects.get()

        reponse = self.client.get(reverse("jeu", args=["roue"]),
                                  {"r": partie.pk})

        self.assertContains(reponse, "roue-disque")
        self.assertEqual(reponse.context["animation"],
                         {"angle": services.angle_roue("x3")})

    def test_page_pile_ou_face_propose_les_deux_faces(self):
        self.client.force_login(self.joueur)

        reponse = self.client.get(reverse("jeu", args=["pile_ou_face"]))

        self.assertContains(reponse, 'name="choix" value="pile"')
        self.assertContains(reponse, 'name="choix" value="face"')
        self.assertContains(reponse, "piece-zone")

    def test_page_braquage_affiche_le_coffre(self):
        self.client.force_login(self.joueur)

        reponse = self.client.get(reverse("jeu", args=["braquage"]))

        self.assertContains(reponse, "coffre-zone")

    def test_resultat_d_un_autre_membre_invisible(self):
        autre = compte("autre@test.cg")
        partie = Partie.objects.create(user=autre, jeu="roue", mise=10)
        self.client.force_login(self.joueur)

        reponse = self.client.get(reverse("jeu", args=["roue"]),
                                  {"r": partie.pk})

        self.assertIsNone(reponse.context["resultat"])

    def test_jeu_inconnu_renvoie_404(self):
        self.client.force_login(self.joueur)
        self.assertEqual(
            self.client.get(reverse("jeu", args=["inconnu"])).status_code, 404)

    def test_demineur_lance_et_ouvre_une_case(self):
        self.client.force_login(self.joueur)
        with patch("apps.jeux.services.random.sample", return_value=[0, 1]):
            self.client.post(reverse("demineur"),
                             {"action": "nouvelle", "mise": "10"})
            partie = services.partie_en_cours(self.joueur)
            self.assertIsNotNone(partie)
            self.client.post(reverse("demineur"),
                             {"action": "ouvrir", "case": "2"})

        partie.refresh_from_db()
        self.assertTrue(partie.en_cours)
        self.assertEqual(partie.cases_liste, [2])
