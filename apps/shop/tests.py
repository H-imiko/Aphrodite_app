from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image, ImageDraw

from apps.accounts.models import User
from apps.economy.services import ErreurEconomie
from apps.inventory.models import InventoryItem
from .forms import ArticleForm
from .models import Item
from .services import acheter

MDP = "MotDePasse!2026"


def png(taille=800, trou=None, couleur=(30, 20, 40, 255)):
    """Image RGBA carree ; avec `trou`, le centre est transparent."""
    image = Image.new("RGBA", (taille, taille), couleur)
    if trou:
        largeur = int(taille * trou)
        marge = (taille - largeur) // 2
        ImageDraw.Draw(image).rectangle(
            [marge, marge, marge + largeur - 1, marge + largeur - 1],
            fill=(0, 0, 0, 0))
    tampon = BytesIO()
    image.save(tampon, "PNG")
    return tampon.getvalue()


def upload(nom, contenu):
    return SimpleUploadedFile(nom, contenu, content_type="image/png")


def compte(email, solde=0, **extra):
    utilisateur = User.objects.create_user(
        email=email, password=MDP, pseudo_whatsapp=email.split("@")[0], **extra)
    if solde:
        User.objects.filter(pk=utilisateur.pk).update(solde_cubis=solde)
        utilisateur.refresh_from_db()
    return utilisateur


class CadreTests(TestCase):
    def setUp(self):
        self.safir = compte("safir@test.cg", est_divinite=True)

    def test_le_trou_est_mesure_a_l_enregistrement(self):
        item = Item(titre="Cadre 60", prix_cubis=0, categorie="cadre",
                    createur=self.safir)
        item.image.save("cadre60.png", upload("cadre60.png", png(trou=0.60)),
                        save=True)
        item.refresh_from_db()

        self.assertAlmostEqual(item.ratio_trou, 0.60, places=2)
        # 100 / 0.60 = 166,67 % : le trou fait la taille de l'avatar.
        self.assertAlmostEqual(item.largeur_cadre_pct, 166.67, places=2)

    def test_sans_trou_aucune_largeur_inventee(self):
        item = Item(titre="Pleine", prix_cubis=0, categorie="cadre",
                    createur=self.safir)
        item.image.save("pleine.png", upload("pleine.png", png()), save=True)
        item.refresh_from_db()

        self.assertIsNone(item.ratio_trou)
        self.assertEqual(item.largeur_cadre_pct, 156.25)

    def test_cadre_valide_accepte(self):
        form = ArticleForm(
            data={"titre": "Cadre lune", "description": "", "prix_cubis": 10,
                  "categorie": "cadre"},
            files={"image": upload("lune.png", png(trou=0.64))},
            user=self.safir)
        self.assertTrue(form.is_valid(), form.errors)

    def test_cadre_non_carre_refuse(self):
        image = Image.new("RGBA", (800, 500), (30, 20, 40, 255))
        ImageDraw.Draw(image).rectangle([280, 190, 519, 309], fill=(0, 0, 0, 0))
        tampon = BytesIO()
        image.save(tampon, "PNG")
        form = ArticleForm(
            data={"titre": "Cadre plat", "prix_cubis": 10,
                  "categorie": "cadre"},
            files={"image": upload("plat.png", tampon.getvalue())},
            user=self.safir)

        self.assertFalse(form.is_valid())
        self.assertIn("image", form.errors)
        self.assertIn("carré", " ".join(form.errors["image"]))

    def test_cadre_sans_trou_central_refuse(self):
        form = ArticleForm(
            data={"titre": "Cadre plein", "prix_cubis": 10,
                  "categorie": "cadre"},
            files={"image": upload("plein.png", png())},
            user=self.safir)

        self.assertFalse(form.is_valid())
        self.assertIn("transparent", " ".join(form.errors["image"]))

    def test_creation_simplifiee_cadre(self):
        # Un membre non Divinité ne peut pas publier un cadre.
        membre = compte("membre@test.cg")
        form = ArticleForm(
            data={"titre": "Cadre", "prix_cubis": 10, "categorie": "cadre"},
            files={"image": upload("c.png", png(trou=0.6))}, user=membre)

        self.assertNotIn("cadre", dict(form.fields["categorie"].choices))


class AchatTests(TestCase):
    def setUp(self):
        self.vendeur = compte("vendeur@test.cg", createur_valide=True)
        self.acheteur = compte("acheteur@test.cg", solde=100)
        self.item = Item.objects.create(titre="Sticker", prix_cubis=40,
                                        categorie="stickers",
                                        createur=self.vendeur)
        self.item.image.save("s.png", upload("s.png", png()), save=True)

    def test_achat_debite_credite_et_livre(self):
        acheter(self.acheteur, self.item.pk, prix_attendu=40)

        self.acheteur.refresh_from_db()
        self.vendeur.refresh_from_db()
        self.assertEqual(self.acheteur.solde_cubis, 60)
        self.assertEqual(self.vendeur.solde_cubis, 40)
        self.assertTrue(InventoryItem.objects.filter(
            proprietaire=self.acheteur, item=self.item).exists())

    def test_second_achat_refuse_sans_deuxieme_debit(self):
        acheter(self.acheteur, self.item.pk, prix_attendu=40)

        with self.assertRaises(ErreurEconomie):
            acheter(self.acheteur, self.item.pk, prix_attendu=40)

        self.acheteur.refresh_from_db()
        self.assertEqual(self.acheteur.solde_cubis, 60)

    def test_prix_change_refuse_sans_debit(self):
        with self.assertRaises(ErreurEconomie):
            acheter(self.acheteur, self.item.pk, prix_attendu=20)

        self.acheteur.refresh_from_db()
        self.assertEqual(self.acheteur.solde_cubis, 100)

    def test_solde_insuffisant(self):
        self.acheteur.solde_cubis = 10
        self.acheteur.save(update_fields=["solde_cubis"])

        with self.assertRaises(ErreurEconomie):
            acheter(self.acheteur, self.item.pk, prix_attendu=40)

        self.assertFalse(InventoryItem.objects.exists())
