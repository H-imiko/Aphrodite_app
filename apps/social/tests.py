from django.test import TestCase

from apps.accounts.models import User
from apps.economy.services import ErreurEconomie
from apps.shop.models import Item
from .models import Abonnement, Like
from .services import basculer_abonnement, basculer_like

MDP = "MotDePasse!2026"


def compte(email, **extra):
    return User.objects.create_user(email=email, password=MDP,
                                    pseudo_whatsapp=email.split("@")[0], **extra)


class LikeTests(TestCase):
    def setUp(self):
        self.createur = compte("createur@test.cg", createur_valide=True)
        self.membre = compte("membre@test.cg")
        self.item = Item.objects.create(titre="Aura", prix_cubis=10,
                                        createur=self.createur)

    def test_aimer_puis_retirer(self):
        self.assertTrue(basculer_like(self.membre, self.item.pk))
        self.assertEqual(Like.objects.count(), 1)

        self.assertFalse(basculer_like(self.membre, self.item.pk))
        self.assertEqual(Like.objects.count(), 0)

    def test_impossible_d_aimer_son_propre_article(self):
        with self.assertRaises(ErreurEconomie):
            basculer_like(self.createur, self.item.pk)

    def test_article_inactif_refuse(self):
        Item.objects.filter(pk=self.item.pk).update(est_actif=False)

        with self.assertRaises(ErreurEconomie):
            basculer_like(self.membre, self.item.pk)


class AbonnementTests(TestCase):
    def setUp(self):
        self.createur = compte("createur@test.cg", createur_valide=True)
        self.membre = compte("membre@test.cg")
        self.simple = compte("simple@test.cg")

    def test_s_abonner_puis_se_desabonner(self):
        self.assertTrue(basculer_abonnement(self.membre, self.createur.pk))
        self.assertTrue(Abonnement.objects.exists())

        self.assertFalse(basculer_abonnement(self.membre, self.createur.pk))
        self.assertFalse(Abonnement.objects.exists())

    def test_notification_une_seule_fois_par_semaine(self):
        basculer_abonnement(self.membre, self.createur.pk)
        self.assertEqual(self.createur.notifications.count(), 1)

        basculer_abonnement(self.membre, self.createur.pk)
        basculer_abonnement(self.membre, self.createur.pk)

        self.assertEqual(self.createur.notifications.count(), 1)

    def test_impossible_de_s_abonner_a_un_membre_simple(self):
        with self.assertRaises(ErreurEconomie):
            basculer_abonnement(self.membre, self.simple.pk)

    def test_impossible_de_s_abonner_a_soi_meme(self):
        with self.assertRaises(ErreurEconomie):
            basculer_abonnement(self.createur, self.createur.pk)
