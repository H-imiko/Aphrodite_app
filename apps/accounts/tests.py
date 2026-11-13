from datetime import date

from django.test import Client, TestCase
from django.urls import reverse

from apps.orders.models import Order

from .models import User

MDP = "MotDePasse!2026"


def annee_ecartee(nb_annees):
    auj = date.today()
    return auj.replace(year=auj.year - nb_annees)


def donnees_inscription(**extra):
    data = {
        "email": "nouveau@test.cg",
        "pseudo_whatsapp": "Nouvelle",
        "espece": "neko",
        "type_compte": "participant",
        "date_naissance": annee_ecartee(20).isoformat(),
        "password1": MDP,
        "password2": MDP,
        "accepte_cgu": "on",
    }
    data.update(extra)
    return data


class InscriptionTests(TestCase):
    def test_case_reglement_contient_un_lien(self):
        reponse = self.client.get(reverse("inscription"))

        self.assertContains(reponse, '<a href="/reglement/">le règlement</a>')

    def test_mineur_refuse(self):
        data = donnees_inscription(date_naissance=annee_ecartee(17).isoformat())
        reponse = self.client.post(reverse("inscription"), data)

        self.assertEqual(reponse.status_code, 200)
        self.assertIn("date_naissance", reponse.context["form"].errors)
        self.assertFalse(User.objects.filter(email=data["email"]).exists())

    def test_adulte_inscrit_et_connecte(self):
        data = donnees_inscription()
        reponse = self.client.post(reverse("inscription"), data)

        self.assertRedirects(reponse, reverse("modifier_profil"))
        user = User.objects.get(email=data["email"])
        self.assertEqual(user.pseudo_whatsapp, "Nouvelle")
        self.assertIn("_auth_user_id", self.client.session)

    def test_email_deja_utilise_refuse(self):
        User.objects.create_user(email="pris@test.cg", password=MDP,
                                 pseudo_whatsapp="Pris")
        reponse = self.client.post(
            reverse("inscription"), donnees_inscription(email="pris@test.cg"))

        self.assertEqual(reponse.status_code, 200)
        self.assertIn("email", reponse.context["form"].errors)
        self.assertEqual(User.objects.filter(email="pris@test.cg").count(), 1)

    def test_mot_de_passe_non_confirme_refuse(self):
        data = donnees_inscription(password2="AutreMotDePasse!2026")
        reponse = self.client.post(reverse("inscription"), data)

        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(User.objects.filter(email=data["email"]).exists())

    def test_case_18_ans_obligatoire(self):
        data = donnees_inscription()
        data.pop("accepte_cgu")
        reponse = self.client.post(reverse("inscription"), data)

        self.assertEqual(reponse.status_code, 200)
        self.assertIn("accepte_cgu", reponse.context["form"].errors)


class ConnexionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="membre@test.cg", password=MDP, pseudo_whatsapp="Membre")

    def test_connexion_ok_et_bonus_quotidien(self):
        reponse = self.client.post(
            reverse("connexion"),
            {"username": "membre@test.cg", "password": MDP}, follow=True)

        self.assertEqual(reponse.status_code, 200)
        self.user.refresh_from_db()
        self.assertGreater(self.user.solde_cubis, 0)
        self.assertContains(reponse, "Bonus quotidien")

    def test_mauvais_mot_de_passe_refuse(self):
        reponse = self.client.post(
            reverse("connexion"),
            {"username": "membre@test.cg", "password": "faux"})

        self.assertEqual(reponse.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_deconnexion_en_post(self):
        self.client.force_login(self.user)
        reponse = self.client.post(reverse("deconnexion"))

        self.assertEqual(reponse.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)


class ProfilTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="profil@test.cg", password=MDP, pseudo_whatsapp="Profil")
        self.client.force_login(self.user)

    def test_page_modification_accessible(self):
        reponse = self.client.get(reverse("modifier_profil"))

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Modifier mon profil")

    def test_modification_du_profil(self):
        reponse = self.client.post(reverse("modifier_profil"), {
            "pseudo_whatsapp": "NouveauPseudo",
            "titre": "Reine des ombres",
            "bio_rp": "Une bio",
            "numero_whatsapp": "+242000000000",
            "afficher_mature": "on",
        })

        self.assertRedirects(reponse, reverse("membre", args=[self.user.pk]))
        self.user.refresh_from_db()
        self.assertEqual(self.user.pseudo_whatsapp, "NouveauPseudo")
        self.assertTrue(self.user.afficher_mature)

    def test_profil_public_accessible_aux_membres(self):
        autre = User.objects.create_user(
            email="autre@test.cg", password=MDP, pseudo_whatsapp="Autre")
        reponse = self.client.get(reverse("membre", args=[autre.pk]))

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Autre")

    def test_profil_inaccessible_sans_connexion(self):
        self.client.logout()
        reponse = self.client.get(reverse("membre", args=[self.user.pk]))

        self.assertEqual(reponse.status_code, 302)
        self.assertIn(reverse("connexion"), reponse["Location"])


class CompteTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="partant@test.cg", password=MDP, pseudo_whatsapp="Partante")
        self.client.force_login(self.user)

    def test_parametres_et_suppression_reserves_aux_connectes(self):
        anonyme = Client()
        for nom in ("parametres", "supprimer_compte"):
            self.assertEqual(anonyme.get(reverse(nom)).status_code, 302)

    def test_reglement_public(self):
        reponse = Client().get(reverse("reglement"))

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "18 ans")

    def test_mauvais_mot_de_passe_ne_supprime_rien(self):
        reponse = self.client.post(
            reverse("supprimer_compte"),
            {"mot_de_passe": "FauxMotDePasse!", "confirmer": "on"})

        self.assertEqual(reponse.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertEqual(self.user.email, "partant@test.cg")

    def test_suppression_efface_les_donnees_personnelles(self):
        self.user.solde_cubis = 120
        self.user.save()

        reponse = self.client.post(
            reverse("supprimer_compte"),
            {"mot_de_passe": MDP, "confirmer": "on"})

        self.assertRedirects(reponse, reverse("accueil"))
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertFalse(self.user.check_password(MDP))
        self.assertNotEqual(self.user.email, "partant@test.cg")
        self.assertEqual(self.user.pseudo_whatsapp, "Compte supprimé")
        self.assertEqual(self.user.solde_cubis, 0)
        self.assertFalse(self.user.avatar)


class SuppressionAvecCommandeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="acheteur@test.cg", password=MDP, pseudo_whatsapp="Acheteur")
        self.vendeur = User.objects.create_user(
            email="vendeur@test.cg", password=MDP, pseudo_whatsapp="Vendeur")
        self.client.force_login(self.user)

    def commande(self, statut):
        return Order.objects.create(
            acheteur=self.user, vendeur=self.vendeur, titre="Scenario prive",
            description="Une scene sur mesure", prix_cubis=40, statut=statut)

    def supprimer(self):
        return self.client.post(
            reverse("supprimer_compte"),
            {"mot_de_passe": MDP, "confirmer": "on"})

    def test_chaque_statut_en_cours_bloque_la_suppression(self):
        for statut in (Order.Statut.DEMANDE, Order.Statut.EN_COURS,
                       Order.Statut.LITIGE):
            with self.subTest(statut=statut):
                commande = self.commande(statut)
                reponse = self.supprimer()

                self.assertEqual(reponse.status_code, 200)
                self.user.refresh_from_db()
                self.assertTrue(self.user.is_active)
                self.assertEqual(self.user.email, "acheteur@test.cg")
                self.assertContains(reponse, "Suppression impossible")
                self.assertContains(
                    reponse, reverse("commande", args=[commande.pk]))
                commande.delete()

    def test_commande_en_cours_du_vendeur_bloque_aussi(self):
        Order.objects.create(
            acheteur=self.vendeur, vendeur=self.user, titre="Ma creation",
            description="Livraison attendue", prix_cubis=25,
            statut=Order.Statut.EN_COURS)

        reponse = self.supprimer()

        self.assertEqual(reponse.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_suppression_possible_apres_commande_terminee(self):
        commande = self.commande(Order.Statut.DEMANDE)
        commande.statut = Order.Statut.TERMINEE
        commande.save()

        reponse = self.supprimer()

        self.assertRedirects(reponse, reverse("accueil"))
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)


class MotDePasseTests(TestCase):
    def setUp(self):
        self.membre = User.objects.create_user(
            email="oubli@test.cg", password=MDP, pseudo_whatsapp="Oublieuse")
        self.divinite = User.objects.create_user(
            email="divinite@test.cg", password=MDP, pseudo_whatsapp="Divinite",
            est_divinite=True)
        self.staff = User.objects.create_user(
            email="staff@test.cg", password=MDP, pseudo_whatsapp="Staff",
            is_staff=True)
        self.proprietaire = User.objects.create_superuser(
            email="safir@test.cg", password=MDP, pseudo_whatsapp="Safir")

    def test_changement_refuse_avec_mauvais_ancien_mot_de_passe(self):
        self.client.force_login(self.membre)

        reponse = self.client.post(reverse("changer_mot_de_passe"), {
            "old_password": "FauxMotDePasse!1",
            "new_password1": "NouveauMotDePasse!2026",
            "new_password2": "NouveauMotDePasse!2026"})

        self.assertEqual(reponse.status_code, 200)
        self.membre.refresh_from_db()
        self.assertTrue(self.membre.check_password(MDP))

    def test_changement_garde_la_session_ouverte(self):
        self.client.force_login(self.membre)

        reponse = self.client.post(reverse("changer_mot_de_passe"), {
            "old_password": MDP,
            "new_password1": "NouveauMotDePasse!2026",
            "new_password2": "NouveauMotDePasse!2026"})

        self.assertRedirects(reponse, reverse("parametres"))
        self.assertEqual(self.client.get(reverse("parametres")).status_code, 200)
        self.membre.refresh_from_db()
        self.assertTrue(self.membre.check_password("NouveauMotDePasse!2026"))

    def test_divinite_reinitialise_et_le_membre_se_connecte(self):
        self.client.force_login(self.divinite)

        reponse = self.client.post(
            reverse("reinitialiser_mot_de_passe", args=[self.membre.pk]))

        self.assertEqual(reponse.status_code, 200)
        temporaire = reponse.context["temporaire"]
        self.assertGreaterEqual(len(temporaire), 10)
        self.membre.refresh_from_db()
        self.assertTrue(self.membre.check_password(temporaire))
        self.assertFalse(self.membre.check_password(MDP))

        autre_client = Client()
        self.assertTrue(autre_client.login(username="oubli@test.cg",
                                           password=temporaire))
        # Le mot de passe provisoire ne donne pas le compte : le membre doit
        # en choisir un autre avant de pouvoir faire quoi que ce soit.
        self.assertRedirects(autre_client.get(reverse("parametres")),
                             reverse("changer_mot_de_passe"))

        autre_client.post(reverse("changer_mot_de_passe"), {
            "old_password": temporaire,
            "new_password1": "MonVraiMotDePasse!2026",
            "new_password2": "MonVraiMotDePasse!2026"})
        self.membre.refresh_from_db()
        self.assertFalse(self.membre.doit_changer_mot_de_passe)
        self.assertEqual(
            autre_client.get(reverse("parametres")).status_code, 200)

    def test_moderateur_ne_peut_pas_reinitialiser(self):
        self.client.force_login(self.staff)

        reponse = self.client.post(
            reverse("reinitialiser_mot_de_passe", args=[self.membre.pk]))

        self.assertEqual(reponse.status_code, 403)
        self.membre.refresh_from_db()
        self.assertTrue(self.membre.check_password(MDP))

    def test_proprietaire_intouchable(self):
        self.client.force_login(self.divinite)

        self.client.post(
            reverse("reinitialiser_mot_de_passe", args=[self.proprietaire.pk]))

        self.proprietaire.refresh_from_db()
        self.assertTrue(self.proprietaire.check_password(MDP))

    def test_reinitialisation_inscrite_au_journal(self):
        from apps.moderation.models import AuditLog
        self.client.force_login(self.divinite)

        self.client.post(
            reverse("reinitialiser_mot_de_passe", args=[self.membre.pk]))

        self.assertTrue(AuditLog.objects.filter(
            action=AuditLog.Action.MOT_DE_PASSE_REINITIALISE,
            cible=self.membre, auteur=self.divinite).exists())
