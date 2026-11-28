from io import BytesIO

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image, ImageDraw

from apps.accounts.models import User
from apps.economy.models import Transaction
from apps.economy.services import ErreurEconomie
from .models import Blocage, Offrande, OffrandeEnvoyee
from .services import bloquer, envoyer

MDP = "MotDePasse!2026"


def compte(email, solde=0, **extra):
    u = User.objects.create_user(email=email, password=MDP,
                                 pseudo_whatsapp=email.split("@")[0], **extra)
    if solde:
        User.objects.filter(pk=u.pk).update(solde_cubis=solde)
        u.refresh_from_db()
    return u


def offrande(nom="Rose", prix=20):
    tampon = BytesIO()
    Image.new("RGBA", (256, 256), (255, 46, 147, 255)).save(tampon, "PNG")
    o = Offrande(nom=nom, prix_cubis=prix)
    o.image.save(f"{nom}.png", ContentFile(tampon.getvalue()), save=True)
    return o


class OffrandeTests(TestCase):
    def setUp(self):
        self.alice = compte("alice@test.cg", solde=100)
        self.bob = compte("bob@test.cg")
        self.rose = offrande()

    def test_envoi_debite_et_notifie(self):
        envoyer(self.alice, self.bob.pk, self.rose.pk, "pour toi")

        self.alice.refresh_from_db()
        self.assertEqual(self.alice.solde_cubis, 80)
        self.assertEqual(self.bob.notifications.count(), 1)
        self.assertEqual(Transaction.objects.filter(
            type=Transaction.Type.OFFRANDE).count(), 1)

    def test_solde_insuffisant_refuse(self):
        self.alice.solde_cubis = 5
        self.alice.save(update_fields=["solde_cubis"])

        with self.assertRaises(ErreurEconomie):
            envoyer(self.alice, self.bob.pk, self.rose.pk)

        self.assertFalse(OffrandeEnvoyee.objects.exists())

    def test_offrande_a_soi_meme_refusee(self):
        with self.assertRaises(ErreurEconomie):
            envoyer(self.alice, self.alice.pk, self.rose.pk)

    def test_anonyme_cache_le_pseudo(self):
        envoyer(self.alice, self.bob.pk, self.rose.pk, anonyme=True)

        notification = self.bob.notifications.first()
        self.assertIn("Quelqu'un", notification.message)
        self.assertNotIn("alice", notification.message.lower())

    def test_plafond_par_destinataire(self):
        for _ in range(5):
            envoyer(self.alice, self.bob.pk, self.rose.pk)

        with self.assertRaises(ErreurEconomie):
            envoyer(self.alice, self.bob.pk, self.rose.pk)

        self.assertEqual(OffrandeEnvoyee.objects.count(), 5)

    def test_membre_bloque_ne_peut_plus_envoyer(self):
        Blocage.objects.create(bloqueur=self.bob, bloque=self.alice)

        with self.assertRaises(ErreurEconomie):
            envoyer(self.alice, self.bob.pk, self.rose.pk)

    def test_bloquer_masque_les_dons_precedents(self):
        don = envoyer(self.alice, self.bob.pk, self.rose.pk)

        bloquer(self.bob, don.pk)

        don.refresh_from_db()
        self.assertTrue(don.masque)
        self.assertTrue(Blocage.objects.filter(
            bloqueur=self.bob, bloque=self.alice).exists())

    def test_divinite_envoie_sans_payer(self):
        gardienne = compte("gardienne@test.cg", est_divinite=True)
        envoyer(gardienne, self.bob.pk, self.rose.pk)

        don = OffrandeEnvoyee.objects.get()
        self.assertEqual(don.prix_paye, 0)
        self.assertFalse(Transaction.objects.exists())


def image_transparente(nom="fleur.png"):
    """Un PNG avec de vrais pixels transparents, comme en attend le formulaire."""
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse((64, 64, 192, 192), fill=(255, 46, 147, 255))
    tampon = BytesIO()
    img.save(tampon, "PNG")
    return SimpleUploadedFile(nom, tampon.getvalue(), content_type="image/png")


class CatalogueDivinitesTests(TestCase):
    """Les Divinités gèrent seules le catalogue : ajouter, retirer, supprimer."""

    def setUp(self):
        self.divinite = compte("divinite@test.cg", est_divinite=True)
        self.membre = compte("simple@test.cg", solde=500)
        self.client.force_login(self.divinite)

    def test_catalogue_reserve_aux_divinites(self):
        self.client.force_login(self.membre)

        reponse = self.client.get("/divinites/offrandes/")

        self.assertEqual(reponse.status_code, 403)

    def test_la_page_liste_les_offrandes_du_catalogue(self):
        offrande("Rose", 20)

        reponse = self.client.get("/divinites/offrandes/")

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Rose")
        self.assertContains(reponse, "Ajouter une offrande")

    def test_divinite_ajoute_une_offrande(self):
        reponse = self.client.post("/divinites/offrandes/", {
            "nom": "Fleur de lune",
            "prix_cubis": 90,
            "image": image_transparente(),
            "ordre": 11,
            "est_actif": "on",
        })

        self.assertEqual(reponse.status_code, 302)
        fleur = Offrande.objects.get(nom="Fleur de lune")
        self.assertEqual(fleur.prix_cubis, 90)
        self.assertTrue(fleur.est_actif)
        self.assertTrue(fleur.image.name.endswith(".png"))

    def test_image_sans_transparence_refusee(self):
        opaque = Image.new("RGB", (256, 256), (255, 46, 147))
        tampon = BytesIO()
        opaque.save(tampon, "PNG")

        reponse = self.client.post("/divinites/offrandes/", {
            "nom": "Faux PNG",
            "prix_cubis": 10,
            "image": SimpleUploadedFile("faux.png", tampon.getvalue(),
                                        content_type="image/png"),
            "ordre": 1,
        })

        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(Offrande.objects.filter(nom="Faux PNG").exists())

    def test_divinite_retire_puis_remet_une_offrande(self):
        rose = offrande("Rose", 20)

        self.client.post(f"/divinites/offrandes/{rose.pk}/basculer/")
        rose.refresh_from_db()
        self.assertFalse(rose.est_actif)

        self.client.post(f"/divinites/offrandes/{rose.pk}/basculer/")
        rose.refresh_from_db()
        self.assertTrue(rose.est_actif)

    def test_offrande_retiree_disparait_du_catalogue_des_membres(self):
        rose = offrande("Rose", 20)
        self.client.post(f"/divinites/offrandes/{rose.pk}/basculer/")

        reponse = self.client.get(f"/offrandes/envoyer/{self.membre.pk}/")

        self.assertNotContains(reponse, "Rose")

    def test_divinite_supprime_une_offrande_jamais_envoyee(self):
        rose = offrande("Rose", 20)
        nom_fichier = rose.image.name

        reponse = self.client.post(
            f"/divinites/offrandes/{rose.pk}/supprimer/")

        self.assertRedirects(reponse, "/divinites/offrandes/")
        self.assertFalse(Offrande.objects.filter(pk=rose.pk).exists())
        self.assertFalse(rose.image.storage.exists(nom_fichier))

    def test_suppression_refusee_si_offrande_deja_envoyee(self):
        rose = offrande("Rose", 20)
        envoyer(self.membre, self.divinite.pk, rose.pk)

        reponse = self.client.get(f"/divinites/offrandes/{rose.pk}/supprimer/",
                                  follow=True)
        self.assertContains(reponse, "déjà été envoyée")

        self.client.post(f"/divinites/offrandes/{rose.pk}/supprimer/")
        self.assertTrue(Offrande.objects.filter(pk=rose.pk).exists())

    def test_membre_simple_ne_peut_pas_supprimer(self):
        rose = offrande("Rose", 20)
        self.client.force_login(self.membre)

        reponse = self.client.post(
            f"/divinites/offrandes/{rose.pk}/supprimer/")

        self.assertEqual(reponse.status_code, 403)
        self.assertTrue(Offrande.objects.filter(pk=rose.pk).exists())
