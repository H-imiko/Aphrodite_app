from io import BytesIO

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
        reponse = self.other.post(reverse("mot_de_passe_oublie"),
                                  {"email": "oubli@test.cg"})

        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(DemandeAcces.objects.filter(
            email="oubli@test.cg").exists())

    def test_adresse_inconnue_meme_reponse(self):
        reponse = self.other.post(reverse("mot_de_passe_oublie"),
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


class PhotoProfilTests(TestCase):
    def setUp(self):
        self.proprietaire = compte("mature@test.cg")
        self.proprietaire.avatar.save("avatar.jpg", photo(), save=True)
        self.proprietaire.profil_mature = True
        self.proprietaire.save(update_fields=["profil_mature"])
        self.visiteur = compte("visiteur@test.cg")
        self.client.force_login(self.visiteur)

    def test_photo_mature_refusee_par_defaut(self):
        reponse = self.client.get(
            reverse("photo_membre", args=[self.proprietaire.pk, "avatar"]))

        self.assertEqual(reponse.status_code, 403)

    def test_photo_mature_visible_apres_acceptation(self):
        self.visiteur.afficher_mature = True
        self.visiteur.save(update_fields=["afficher_mature"])

        reponse = self.client.get(
            reverse("photo_membre", args=[self.proprietaire.pk, "avatar"]))

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse["X-Robots-Tag"], "noindex")

    def test_proprietaire_voit_toujours_sa_photo(self):
        self.client.force_login(self.proprietaire)

        reponse = self.client.get(
            reverse("photo_membre", args=[self.proprietaire.pk, "avatar"]))

        self.assertEqual(reponse.status_code, 200)

    def test_photo_non_mature_lisible_par_tous(self):
        self.proprietaire.profil_mature = False
        self.proprietaire.save(update_fields=["profil_mature"])
        anonyme = Client()

        reponse = anonyme.get(
            reverse("photo_membre", args=[self.proprietaire.pk, "avatar"]))

        self.assertEqual(reponse.status_code, 200)
