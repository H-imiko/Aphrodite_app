from io import BytesIO

from django.core.files.base import ContentFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from apps.accounts.models import User
from apps.shop.models import Item
from .models import Equipement, InventoryItem, ObjectTransfer
from .services import accepter, offrir

MDP = "MotDePasse!2026"


def image_png(couleur=(255, 46, 147, 255), taille=(64, 64)):
    tampon = BytesIO()
    Image.new("RGBA", taille, couleur).save(tampon, "PNG")
    return ContentFile(tampon.getvalue())


def creer_item(createur, categorie="cadre", titre="Cadre test"):
    item = Item.objects.create(titre=titre, prix_cubis=50,
                               categorie=categorie, createur=createur)
    item.image.save(f"{titre}.png", image_png(), save=True)
    return item


class EquiperTests(TestCase):
    def setUp(self):
        self.safir = User.objects.create_user(
            email="safir@test.cg", password=MDP, pseudo_whatsapp="Safir",
            est_divinite=True, is_superuser=True)
        self.membre = User.objects.create_user(
            email="membre@test.cg", password=MDP, pseudo_whatsapp="Membre")
        self.cadre = creer_item(self.safir, "cadre", "Cadre lunaire")
        self.client.force_login(self.membre)

    def test_equiper_un_cadre_possede(self):
        InventoryItem.objects.create(proprietaire=self.membre, item=self.cadre)

        reponse = self.client.post(
            reverse("equiper", args=[self.cadre.pk]))

        self.assertRedirects(reponse, reverse("inventaire"))
        self.assertEqual(Equipement.objects.get(user=self.membre).cadre,
                         self.cadre)

    def test_equiper_un_cadre_non_possede_refuse(self):
        reponse = self.client.post(reverse("equiper", args=[self.cadre.pk]))

        self.assertEqual(reponse.status_code, 403)
        self.assertFalse(Equipement.objects.filter(
            user=self.membre, cadre=self.cadre).exists())

    def test_objet_non_equipable_refuse(self):
        sticker = creer_item(self.safir, "stickers", "Pack stickers")
        InventoryItem.objects.create(proprietaire=self.membre, item=sticker)

        reponse = self.client.post(reverse("equiper", args=[sticker.pk]))

        self.assertRedirects(reponse, reverse("inventaire"))
        equip = Equipement.objects.filter(user=self.membre).first()
        self.assertIsNone(equip.cadre if equip else None)

    def test_equiper_exige_un_post(self):
        InventoryItem.objects.create(proprietaire=self.membre, item=self.cadre)

        reponse = self.client.get(reverse("equiper", args=[self.cadre.pk]))

        self.assertEqual(reponse.status_code, 405)

    def test_retirer_le_cadre(self):
        Equipement.objects.create(user=self.membre, cadre=self.cadre)

        reponse = self.client.post(
            reverse("retirer_equipement", args=["cadre"]))

        self.assertRedirects(reponse, reverse("inventaire"))
        self.assertIsNone(Equipement.objects.get(user=self.membre).cadre)

    def test_le_cadre_apparait_sur_le_profil(self):
        InventoryItem.objects.create(proprietaire=self.membre, item=self.cadre)
        Equipement.objects.create(user=self.membre, cadre=self.cadre)

        reponse = self.client.get(reverse("membre", args=[self.membre.pk]))

        self.assertContains(reponse, 'class="avatar-cadre"')
        self.assertContains(reponse,
                            reverse("cosmetique_image", args=[self.cadre.pk]))

    def test_image_du_cadre_servie_meme_non_possedee(self):
        # un autre membre porte le cadre : son image reste publique sur son profil
        autre = User.objects.create_user(
            email="autre@test.cg", password=MDP, pseudo_whatsapp="Autre")
        Equipement.objects.create(user=autre, cadre=self.cadre)

        reponse = self.client.get(
            reverse("cosmetique_image", args=[self.cadre.pk]))

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse["Content-Type"], "image/png")


class CadeauTests(TestCase):
    def setUp(self):
        self.safir = User.objects.create_user(
            email="safir@test.cg", password=MDP, pseudo_whatsapp="Safir",
            est_divinite=True, is_superuser=True)
        self.alice = User.objects.create_user(
            email="alice@test.cg", password=MDP, pseudo_whatsapp="Alice")
        self.bob = User.objects.create_user(
            email="bob@test.cg", password=MDP, pseudo_whatsapp="Bob")
        self.cadre = creer_item(self.safir, "cadre", "Cadre solaire")
        InventoryItem.objects.create(proprietaire=self.alice, item=self.cadre)

    def test_offrir_puis_accepter_transfere_la_possession(self):
        transfert = offrir(self.alice, self.bob.pk, self.cadre.pk)

        accepter(self.bob, transfert.pk)

        self.assertFalse(InventoryItem.objects.filter(
            proprietaire=self.alice, item=self.cadre).exists())
        self.assertTrue(InventoryItem.objects.filter(
            proprietaire=self.bob, item=self.cadre).exists())
        self.assertEqual(ObjectTransfer.objects.get(pk=transfert.pk).statut,
                         ObjectTransfer.Statut.ACCEPTE)

    def test_accepter_retire_le_cadre_equipe_par_l_ancien_proprietaire(self):
        Equipement.objects.create(user=self.alice, cadre=self.cadre)
        transfert = offrir(self.alice, self.bob.pk, self.cadre.pk)

        accepter(self.bob, transfert.pk)

        self.assertIsNone(Equipement.objects.get(user=self.alice).cadre)

    def test_impossible_d_offrir_un_objet_non_possede(self):
        from apps.economy.services import ErreurEconomie
        with self.assertRaises(ErreurEconomie):
            offrir(self.bob, self.alice.pk, self.cadre.pk)

    def test_impossible_de_s_offrir_un_objet(self):
        from apps.economy.services import ErreurEconomie
        with self.assertRaises(ErreurEconomie):
            offrir(self.alice, self.alice.pk, self.cadre.pk)

    def test_seul_le_destinataire_peut_accepter(self):
        from apps.economy.services import ErreurEconomie
        transfert = offrir(self.alice, self.bob.pk, self.cadre.pk)

        with self.assertRaises(ErreurEconomie):
            accepter(self.safir, transfert.pk)
