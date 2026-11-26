import re
from io import BytesIO

from django.core import mail
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import DemandeAcces, User

MDP = "MotDePasse!2026"


def compte(email, **extra):
    return User.objects.create_user(email=email, password=MDP,
                                    pseudo_whatsapp=email.split("@")[0], **extra)


def photo():
    tampon = BytesIO()
    Image.new("RGB", (80, 80), (40, 20, 60)).save(tampon, "JPEG")
    return ContentFile(tampon.getvalue(), name="photo.jpg")


class LimiteTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_connexion_bloquee_apres_trop_d_essais(self):
        compte("membre@test.cg")
        for _ in range(8):
            self.client.post(reverse("connexion"), {
                "username": "membre@test.cg", "password": "faux"})

        reponse = self.client.post(reverse("connexion"), {
            "username": "membre@test.cg", "password": "faux"})

        self.assertEqual(reponse.status_code, 429)

    def test_connexion_normale_non_bloquee(self):
        compte("membre@test.cg")

        reponse = self.client.post(reverse("connexion"), {
            "username": "membre@test.cg", "password": MDP})

        self.assertEqual(reponse.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)

    def test_entete_forwarded_for_ne_contourne_pas_la_limite(self):
        compte("membre@test.cg")
        for rang in range(8):
            self.client.post(
                reverse("connexion"),
                {"username": "membre@test.cg", "password": "faux"},
                HTTP_X_FORWARDED_FOR=f"10.0.0.{rang}")

        reponse = self.client.post(
            reverse("connexion"),
            {"username": "membre@test.cg", "password": "faux"},
            HTTP_X_FORWARDED_FOR="10.0.0.99")

        self.assertEqual(reponse.status_code, 429)

    @override_settings(USE_X_FORWARDED_FOR=True)
    def test_adresse_du_proxy_utilisee_quand_elle_est_de_confiance(self):
        compte("membre@test.cg")
        for rang in range(8):
            self.client.post(
                reverse("connexion"),
                {"username": "membre@test.cg", "password": "faux"},
                HTTP_X_FORWARDED_FOR=f"faux{ rang }, 203.0.113.7")

        reponse = self.client.post(
            reverse("connexion"),
            {"username": "membre@test.cg", "password": "faux"},
            HTTP_X_FORWARDED_FOR="autre, 203.0.113.7")

        self.assertEqual(reponse.status_code, 429)

    @override_settings(LIMITES={"connexion": (100, 300),
                                "connexion_ip": (3, 300)})
    def test_balayage_sur_plusieurs_comptes_bloque_par_adresse(self):
        for rang in range(3):
            compte(f"compte{rang}@test.cg")
        for rang in range(3):
            self.client.post(reverse("connexion"), {
                "username": f"compte{rang}@test.cg", "password": "faux"})

        reponse = self.client.post(reverse("connexion"), {
            "username": "compte0@test.cg", "password": "faux"})

        self.assertEqual(reponse.status_code, 429)

    def test_inscription_bloquee_apres_trop_d_essais(self):
        for _ in range(10):
            self.client.post(reverse("inscription"), {})
        reponse = self.client.post(reverse("inscription"), {})

        self.assertEqual(reponse.status_code, 429)


class MotDePasseProvisoireTests(TestCase):
    def setUp(self):
        self.membre = compte("provisoire@test.cg")
        self.client.force_login(self.membre)

    def test_acces_bloque_tant_que_le_mot_de_passe_n_est_pas_change(self):
        User.objects.filter(pk=self.membre.pk).update(
            doit_changer_mot_de_passe=True)
        self.membre.refresh_from_db()

        self.assertRedirects(self.client.get(reverse("boutique")),
                             reverse("changer_mot_de_passe"))
        self.assertEqual(
            self.client.get(reverse("changer_mot_de_passe")).status_code, 200)

    def test_changement_du_mot_de_passe_libere_le_compte(self):
        User.objects.filter(pk=self.membre.pk).update(
            doit_changer_mot_de_passe=True)
        self.membre.refresh_from_db()

        self.client.post(reverse("changer_mot_de_passe"), {
            "old_password": MDP,
            "new_password1": "NouveauMotDePasse!2026",
            "new_password2": "NouveauMotDePasse!2026"})

        self.membre.refresh_from_db()
        self.assertFalse(self.membre.doit_changer_mot_de_passe)
        self.assertEqual(self.client.get(reverse("boutique")).status_code, 200)


class DemandeAccesTests(TestCase):
    def setUp(self):
        cache.clear()
        self.membre = compte("oubli@test.cg")
        self.divinite = compte("divinite@test.cg", est_divinite=True)
        self.other = Client()

    def tearDown(self):
        cache.clear()

    def test_demande_publique_enregistree(self):
        reponse = self.other.post(reverse("mot_de_passe_sans_email"),
                                  {"email": "oubli@test.cg"})

        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(DemandeAcces.objects.filter(
            email="oubli@test.cg").exists())

    def test_adresse_inconnue_meme_reponse(self):
        reponse = self.other.post(reverse("mot_de_passe_sans_email"),
                                  {"email": "inconnu@nulle.part"})

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Demande enregistrée")

    def test_reservee_aux_divinites(self):
        self.other.force_login(self.membre)

        self.assertEqual(self.other.get(reverse("demandes")).status_code, 403)

    def test_suppression_du_compte_efface_la_demande(self):
        DemandeAcces.objects.create(email="oubli@test.cg")

        from apps.accounts.services import fermer_compte
        fermer_compte(self.membre)

        self.assertFalse(DemandeAcces.objects.exists())

    def test_traitement_ouvre_la_fiche_du_compte(self):
        demande = DemandeAcces.objects.create(email="oubli@test.cg")
        self.other.force_login(self.divinite)

        reponse = self.other.post(
            reverse("traiter_demande", args=[demande.pk]))

        self.assertRedirects(reponse, reverse("membre_moderation",
                                             args=[self.membre.pk]))
        demande.refresh_from_db()
        self.assertTrue(demande.traite)


class ReinitialisationParEmailTests(TestCase):
    """Le mot de passe se récupère seul, par email, sans passer par l'équipe."""

    def setUp(self):
        cache.clear()
        self.membre = compte("reset@test.cg")
        self.anonyme = Client()

    def tearDown(self):
        cache.clear()

    def _lien_recu(self):
        self.anonyme.post(reverse("mot_de_passe_oublie"),
                          {"email": "reset@test.cg"})
        self.assertEqual(len(mail.outbox), 1)
        trouve = re.search(r"http://testserver(\S+)", mail.outbox[0].body)
        self.assertIsNotNone(trouve)
        return trouve.group(1)

    def test_email_avec_lien_envoye(self):
        reponse = self.anonyme.post(reverse("mot_de_passe_oublie"),
                                    {"email": "reset@test.cg"})

        self.assertRedirects(reponse, reverse("mot_de_passe_envoye"))
        self.assertEqual(mail.outbox[0].to, ["reset@test.cg"])
        self.assertIn("/reinitialiser/", mail.outbox[0].body)

    def test_adresse_inconnue_meme_reponse_sans_email(self):
        reponse = self.anonyme.post(reverse("mot_de_passe_oublie"),
                                    {"email": "inconnu@nulle.part"})

        self.assertRedirects(reponse, reverse("mot_de_passe_envoye"))
        self.assertEqual(len(mail.outbox), 0)

    def test_lien_permet_de_choisir_un_mot_de_passe(self):
        User.objects.filter(pk=self.membre.pk).update(
            doit_changer_mot_de_passe=True)
        lien = self._lien_recu()

        # Django remplace le jeton du lien par « set-password » dans l'URL
        # avant d'afficher le formulaire : le jeton ne reste pas a l'ecran.
        redirection = self.anonyme.get(lien)
        self.assertEqual(redirection.status_code, 302)
        cible = redirection["Location"]
        self.assertEqual(self.anonyme.get(cible).status_code, 200)

        reponse = self.anonyme.post(cible, {
            "new_password1": "NouveauMotDePasse!2026",
            "new_password2": "NouveauMotDePasse!2026"})

        self.assertRedirects(reponse, reverse("connexion"))
        self.membre.refresh_from_db()
        self.assertTrue(self.membre.check_password("NouveauMotDePasse!2026"))
        self.assertFalse(self.membre.doit_changer_mot_de_passe)

    def test_lien_invalide_refuse(self):
        page = self.anonyme.get(reverse("reinitialiser_mot_de_passe",
                                        kwargs={"uidb64": "bad",
                                                "token": "bad-token"}))

        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "plus valide")


class PhotoProfilTests(TestCase):
    def setUp(self):
        self.proprietaire = compte("proprio@test.cg")
        self.proprietaire.avatar.save("avatar.jpg", photo(), save=True)
        self.visiteur = compte("visiteur@test.cg")
        self.client.force_login(self.visiteur)

    def test_photo_lisible_par_un_membre_connecte(self):
        reponse = self.client.get(
            reverse("photo_membre", args=[self.proprietaire.pk, "avatar"]))

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse["X-Robots-Tag"], "noindex")
        self.assertEqual(reponse["X-Content-Type-Options"], "nosniff")

    def test_photo_lisible_sans_connexion(self):
        reponse = Client().get(
            reverse("photo_membre", args=[self.proprietaire.pk, "avatar"]))

        self.assertEqual(reponse.status_code, 200)

    def test_membre_sans_photo_renvoie_404(self):
        sans_photo = compte("sansphoto@test.cg")

        reponse = self.client.get(
            reverse("photo_membre", args=[sans_photo.pk, "avatar"]))

        self.assertEqual(reponse.status_code, 404)

    def test_champ_inconnu_renvoie_404(self):
        reponse = self.client.get(
            reverse("photo_membre", args=[self.proprietaire.pk, "secret"]))

        self.assertEqual(reponse.status_code, 404)


class PagesPubliquesTests(TestCase):
    def test_confidentialite_publique(self):
        reponse = Client().get(reverse("confidentialite"))

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Ce que nous enregistrons")
        self.assertContains(reponse, "Numéro WhatsApp")

    def test_lien_confidentialite_dans_le_reglement(self):
        reponse = Client().get(reverse("reglement"))

        self.assertContains(reponse, reverse("confidentialite"))

    def test_lien_confidentialite_dans_l_inscription(self):
        reponse = Client().get(reverse("inscription"))

        self.assertContains(reponse, reverse("confidentialite"))
