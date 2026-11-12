import gzip
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase


class SauvegardeBaseTests(TestCase):
    def test_cree_une_archive_lisible(self):
        with tempfile.TemporaryDirectory() as dossier:
            call_command("sauvegarder_base", dossier=dossier, stdout=StringIO())

            archives = list(Path(dossier).glob("db-*.sqlite3.gz"))
            self.assertEqual(len(archives), 1)
            with gzip.open(archives[0], "rb") as archive:
                self.assertEqual(archive.read(16), b"SQLite format 3\x00")
            self.assertEqual(list(Path(dossier).glob("*.sqlite3")), [])

    def test_ne_conserve_que_les_dernieres(self):
        with tempfile.TemporaryDirectory() as dossier:
            for rang in range(3):
                ancienne = Path(dossier) / f"db-20260101-00000{rang}.sqlite3.gz"
                ancienne.write_bytes(b"ancienne")

            call_command(
                "sauvegarder_base", dossier=dossier, garder=2, stdout=StringIO()
            )

            self.assertEqual(len(list(Path(dossier).glob("db-*.sqlite3.gz"))), 2)


from unittest import mock

from django.contrib.auth import get_user_model

from apps.orders.models import Order
from apps.shop.models import Item

User = get_user_model()


def compte(email, **extra):
    return User.objects.create_user(email=email, password="MotDePasse!2026",
                                    pseudo_whatsapp=email.split("@")[0], **extra)


def article(createur, titre="Article de test"):
    return Item.objects.create(titre=titre, prix_cubis=25, createur=createur)


class PurgeDemonstrationTests(TestCase):
    def setUp(self):
        self.demo = compte("demo@test.cg")
        self.reel = compte("vrai@exemple.fr")

    def lancer(self, **options):
        sortie = StringIO()
        call_command("purger_demonstration", stdout=sortie, **options)
        return sortie.getvalue()

    def test_liste_seulement_par_defaut(self):
        sortie = self.lancer()

        self.assertTrue(User.objects.filter(pk=self.demo.pk).exists())
        self.assertIn("demo@test.cg", sortie)
        self.assertIn("Mode liste", sortie)

    def test_supprime_comptes_et_articles_de_demo(self):
        item = article(self.demo)
        garde = article(self.reel, "Article reel")

        sortie = self.lancer(supprimer=True, oui=True)

        self.assertFalse(User.objects.filter(pk=self.demo.pk).exists())
        self.assertFalse(Item.objects.filter(pk=item.pk).exists())
        self.assertTrue(User.objects.filter(pk=self.reel.pk).exists())
        self.assertTrue(Item.objects.filter(pk=garde.pk).exists())
        self.assertIn("1 compte(s)", sortie)

    def test_article_demande_explicitement(self):
        item = article(self.reel, "Brouillon")

        self.lancer(supprimer=True, oui=True, article=[item.pk])

        self.assertFalse(Item.objects.filter(pk=item.pk).exists())
        self.assertTrue(User.objects.filter(pk=self.reel.pk).exists())

    def test_proprietaire_conserve_par_defaut(self):
        patron = User.objects.create_superuser(
            email="patron@test.cg", password="MotDePasse!2026",
            pseudo_whatsapp="Patron")

        self.lancer(supprimer=True, oui=True)
        self.assertTrue(User.objects.filter(pk=patron.pk).exists())

        self.lancer(supprimer=True, oui=True, avec_proprietaire=True)
        self.assertFalse(User.objects.filter(pk=patron.pk).exists())

    def test_compte_avec_commande_conserve(self):
        Order.objects.create(acheteur=self.demo, vendeur=self.reel,
                             titre="Scenario", description="Scene",
                             prix_cubis=10)

        sortie = self.lancer(supprimer=True, oui=True)

        self.assertTrue(User.objects.filter(pk=self.demo.pk).exists())
        self.assertIn("commandes", sortie)

    def test_confirmation_refusee_ne_supprime_rien(self):
        with mock.patch("builtins.input", return_value="non"):
            sortie = self.lancer(supprimer=True)

        self.assertTrue(User.objects.filter(pk=self.demo.pk).exists())
        self.assertIn("Abandon", sortie)

    def test_confirmation_acceptee_supprime(self):
        with mock.patch("builtins.input", return_value="SUPPRIMER"):
            self.lancer(supprimer=True)

        self.assertFalse(User.objects.filter(pk=self.demo.pk).exists())
