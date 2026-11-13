from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.shop.models import Item

MDP = "MotDePasse!2026"


def compte(email, **extra):
    return User.objects.create_user(email=email, password=MDP,
                                    pseudo_whatsapp=email.split("@")[0], **extra)


class SignalementArticleTests(TestCase):
    def setUp(self):
        # Chaque test repart d'un compteur de debit vierge (le cache survit
        # d'un test a l'autre dans le meme processus).
        cache.clear()
        self.createur = compte("createur@test.cg", createur_valide=True)
        self.item = Item.objects.create(titre="Aura suspecte", prix_cubis=20,
                                        categorie="image_rp",
                                        createur=self.createur)
        self.signaleurs = [compte(f"temoin{rang}@test.cg") for rang in range(3)]

    def signaler(self, signaleur, motif="harcelement"):
        client = Client()
        client.force_login(signaleur)
        return client.post(
            reverse("signaler", args=["article", self.item.pk]),
            {"motif": motif, "details": "Signalement de test"})

    def test_un_seul_signalement_ne_masque_pas(self):
        self.signaler(self.signaleurs[0])

        self.item.refresh_from_db()
        self.assertTrue(self.item.est_actif)

    def test_trois_signalements_distincts_masquent(self):
        for signaleur in self.signaleurs:
            self.signaler(signaleur)

        self.item.refresh_from_db()
        self.assertFalse(self.item.est_actif)
        self.assertTrue(self.item.masque_moderation)

    def test_motif_grave_masque_des_deux_signalements(self):
        for signaleur in self.signaleurs[:2]:
            self.signaler(signaleur, motif="mineur")

        self.item.refresh_from_db()
        self.assertFalse(self.item.est_actif)

    @override_settings(LIMITES={"signalement": (2, 600)})
    def test_limite_de_debit_bloque_les_signalements(self):
        articles = [Item.objects.create(
            titre=f"Article {rang}", prix_cubis=10, categorie="image_rp",
            createur=self.createur) for rang in range(3)]
        client = Client()
        client.force_login(self.signaleurs[0])
        for article in articles:
            client.post(reverse("signaler", args=["article", article.pk]),
                        {"motif": "harcelement", "details": "Test"})

        from .models import Report
        self.assertEqual(Report.objects.count(), 2)

    def test_meme_membre_ne_compte_qu_une_fois(self):
        for _ in range(3):
            self.signaler(self.signaleurs[0])

        self.item.refresh_from_db()
        self.assertTrue(self.item.est_actif)
