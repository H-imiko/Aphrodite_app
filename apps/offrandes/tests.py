from io import BytesIO

from django.core.files.base import ContentFile
from django.test import TestCase
from PIL import Image

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
