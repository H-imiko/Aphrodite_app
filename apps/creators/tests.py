from datetime import datetime
from io import StringIO

from django.core.management import call_command
from django.test import Client, TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.economy.models import Transaction
from apps.shop.models import Item
from apps.social.models import Like
from .models import PrimeCreateur

MDP = "MotDePasse!2026"
JOUR = timezone.make_aware(datetime(2026, 11, 10, 12, 0))


def compte(email, **extra):
    return User.objects.create_user(email=email, password=MDP,
                                    pseudo_whatsapp=email.split("@")[0], **extra)


def article(createur, jour=JOUR, titre="Creation"):
    item = Item.objects.create(titre=titre, prix_cubis=40, categorie="stickers",
                               createur=createur)
    Item.objects.filter(pk=item.pk).update(date_creation=jour)
    return item


def vente(createur, montant, jour=JOUR):
    t = Transaction.objects.create(destinataire=createur, montant=montant,
                                   type=Transaction.Type.ACHAT)
    Transaction.objects.filter(pk=t.pk).update(date=jour)
    return t


def like(item, membre, jour=JOUR):
    like_obj = Like.objects.create(user=membre, item=item)
    Like.objects.filter(pk=like_obj.pk).update(date=jour)


class PrimeCreateurTests(TestCase):
    def setUp(self):
        self.createur = compte("createur@test.cg", createur_valide=True)
        self.autre = compte("autre@test.cg", createur_valide=True)
        self.membre = compte("membre@test.cg")

    def lancer(self, *options):
        sortie = StringIO()
        call_command("primes_createurs", "--mois", "2026-11",
                     *options, stdout=sortie)
        return sortie.getvalue()

    def cinq_articles(self, createur=None):
        createur = createur or self.createur
        for rang in range(5):
            article(createur, titre=f"Creation {rang}")

    def test_simulation_ne_verse_rien(self):
        self.cinq_articles()
        vente(self.createur, 100)

        sortie = self.lancer()

        self.assertIn("Simulation", sortie)
        self.assertFalse(PrimeCreateur.objects.exists())
        self.createur.refresh_from_db()
        self.assertEqual(self.createur.solde_cubis, 0)

    def test_podium_verse_et_trace(self):
        self.cinq_articles()
        vente(self.createur, 200)

        sortie = self.lancer("--appliquer")

        self.assertIn("1. createur", sortie)
        self.createur.refresh_from_db()
        self.assertEqual(self.createur.solde_cubis, 5000)
        prime = PrimeCreateur.objects.get(mois="2026-11", user=self.createur)
        self.assertEqual((prime.rang, prime.montant), (1, 5000))
        self.assertTrue(Transaction.objects.filter(
            destinataire=self.createur,
            type=Transaction.Type.BONUS_CREATEUR, montant=5000).exists())
        self.assertEqual(self.createur.notifications.count(), 1)

    def test_deux_lancements_ne_paient_qu_une_fois(self):
        self.cinq_articles()
        vente(self.createur, 200)

        self.lancer("--appliquer")
        sortie = self.lancer("--appliquer")

        self.createur.refresh_from_db()
        self.assertEqual(self.createur.solde_cubis, 5000)
        self.assertEqual(PrimeCreateur.objects.count(), 1)
        self.assertIn("0 prime(s) versee(s)", sortie)

    def test_moins_de_cinq_articles_pas_de_prime(self):
        for rang in range(4):
            article(self.createur, titre=f"Creation {rang}")
        vente(self.createur, 500)

        sortie = self.lancer("--appliquer")

        self.assertIn("Aucun createur eligible", sortie)
        self.assertFalse(PrimeCreateur.objects.exists())

    def test_likes_suffisent_comme_preuve_d_utilite(self):
        self.cinq_articles()
        for rang in range(5):
            like(article(self.createur, titre=f"Aime {rang}"), self.membre)

        self.lancer("--appliquer")

        self.createur.refresh_from_db()
        self.assertEqual(self.createur.solde_cubis, 5000)

    def test_vente_sans_like_suffit(self):
        self.cinq_articles()
        vente(self.createur, 40)

        self.lancer("--appliquer")

        self.assertTrue(PrimeCreateur.objects.filter(user=self.createur,
                                                     rang=1).exists())

    def test_classement_par_cubis_encaisses(self):
        self.cinq_articles(self.createur)
        self.cinq_articles(self.autre)
        vente(self.createur, 100)
        vente(self.autre, 300)

        self.lancer("--appliquer")

        self.assertEqual(PrimeCreateur.objects.get(
            user=self.createur).montant, 2000)
        self.assertEqual(PrimeCreateur.objects.get(
            user=self.autre).montant, 5000)
        self.assertEqual(PrimeCreateur.objects.get(user=self.autre).rang, 1)

    def test_divinite_exclue_du_podium(self):
        divinite = compte("divinite@test.cg", createur_valide=True,
                          est_divinite=True)
        self.cinq_articles(divinite)
        vente(divinite, 500)

        sortie = self.lancer("--appliquer")

        self.assertIn("Aucun createur eligible", sortie)
        self.assertFalse(PrimeCreateur.objects.exists())

    def test_mois_sans_activite_pas_de_prime(self):
        self.cinq_articles()
        vente(self.createur, 500, jour=timezone.make_aware(
            datetime(2026, 10, 10, 12, 0)))

        sortie = self.lancer("--appliquer")

        self.assertIn("Aucun createur eligible", sortie)


class PageCreateursDuMoisTests(TestCase):
    """Podium public : reconnaissance, pas classement au volume."""

    def setUp(self):
        from datetime import timedelta
        from django.urls import reverse
        self.reverse = reverse
        self.createur = compte("createur@test.cg", createur_valide=True)
        self.autre = compte("autre@test.cg", createur_valide=True)
        self.divinite = compte("divinite@test.cg", createur_valide=True,
                               est_divinite=True)
        self.membre = compte("membre@test.cg")
        self.mois_precedent = (
            timezone.localdate().replace(day=1) - timedelta(days=1)
        ).strftime("%Y-%m")

    def page(self):
        return Client().get(self.reverse("createurs_du_mois"))

    def test_page_publique_accessible(self):
        reponse = self.page()

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Créateurs du mois")

    def test_classement_par_cubis_encaisse(self):
        for rang in range(5):
            article(self.createur, titre=f"Vente {rang}")
            article(self.autre, titre=f"Autre {rang}")
        vente(self.createur, 100)
        vente(self.autre, 300)

        reponse = self.page()

        self.assertEqual(reponse.context["podium"][0]["user"], self.autre)
        self.assertEqual(reponse.context["podium"][1]["user"], self.createur)

    def test_divinite_absente_du_podium(self):
        for rang in range(5):
            article(self.divinite, titre=f"Officiel {rang}")
        vente(self.divinite, 900)

        reponse = self.page()

        self.assertEqual(reponse.context["podium"], [])
        self.assertNotContains(reponse, "divinite")

    def test_mois_vide_affiche_un_message(self):
        reponse = self.page()

        self.assertContains(reponse, "Le mois commence")

    def test_palmares_du_mois_precedent_affiche(self):
        PrimeCreateur.objects.create(
            mois=self.mois_precedent, user=self.createur, rang=1,
            montant=5000, nb_articles=6, ventes_cubis=400, nb_likes=12)

        reponse = self.page()

        self.assertContains(reponse, "Palmarès")
        self.assertContains(reponse, "5000")
