from datetime import date

from django.test import TestCase
from django.urls import reverse

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
