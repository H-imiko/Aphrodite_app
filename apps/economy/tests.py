from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import User
from .models import Transaction
from .services import (ErreurEconomie, bonus_quotidien, envoyer_par_divinite,
                       transferer)

MDP = "MotDePasse!2026"


def creer_user(email, solde=0, **extra):
    user = User.objects.create_user(email=email, password=MDP,
                                    pseudo_whatsapp=email.split("@")[0],
                                    **extra)
    if solde:
        User.objects.filter(pk=user.pk).update(solde_cubis=solde)
        user.refresh_from_db()
    return user


class TransfertTests(TestCase):
    def setUp(self):
        self.alice = creer_user("alice@test.cg", solde=100)
        self.bob = creer_user("bob@test.cg", solde=20)

    def test_transfert_debite_credite_et_trace(self):
        transferer(self.alice, self.bob, 30, "merci")

        self.alice.refresh_from_db()
        self.bob.refresh_from_db()
        self.assertEqual(self.alice.solde_cubis, 70)
        self.assertEqual(self.bob.solde_cubis, 50)
        t = Transaction.objects.get(type=Transaction.Type.TRANSFERT)
        self.assertEqual((t.expediteur, t.destinataire, t.montant),
                         (self.alice, self.bob, 30))

    def test_solde_insuffisant_ne_touche_a_rien(self):
        with self.assertRaises(ErreurEconomie):
            transferer(self.alice, self.bob, 101)

        self.alice.refresh_from_db()
        self.bob.refresh_from_db()
        self.assertEqual(self.alice.solde_cubis, 100)
        self.assertEqual(self.bob.solde_cubis, 20)
        self.assertFalse(Transaction.objects.exists())

    def test_montant_non_positif_refuse(self):
        for montant in (0, -5):
            with self.assertRaises(ErreurEconomie):
                transferer(self.alice, self.bob, montant)

    def test_transfert_a_soi_meme_refuse(self):
        with self.assertRaises(ErreurEconomie):
            transferer(self.alice, self.alice, 10)

    def test_expediteur_suspendu_refuse(self):
        User.objects.filter(pk=self.alice.pk).update(est_suspendu=True)
        self.alice.refresh_from_db()

        with self.assertRaises(ErreurEconomie):
            transferer(self.alice, self.bob, 10)

        self.bob.refresh_from_db()
        self.assertEqual(self.bob.solde_cubis, 20)


class BonusQuotidienTests(TestCase):
    def setUp(self):
        self.user = creer_user("quotidien@test.cg")

    def test_bonus_une_seule_fois_par_jour(self):
        premier = bonus_quotidien(self.user)
        self.assertIsNotNone(premier)
        self.assertGreaterEqual(premier, 15)
        self.assertLessEqual(premier, 25)

        self.user.refresh_from_db()
        solde = self.user.solde_cubis
        self.assertIsNone(bonus_quotidien(self.user))

        self.user.refresh_from_db()
        self.assertEqual(self.user.solde_cubis, solde)
        self.assertEqual(
            Transaction.objects.filter(
                type=Transaction.Type.CONNEXION).count(), 1)

    def test_serie_incrementee_si_connexion_la_veille(self):
        User.objects.filter(pk=self.user.pk).update(
            serie_connexion=3,
            derniere_connexion_bonus=timezone.localdate() - timedelta(days=1))
        self.user.refresh_from_db()

        montant = bonus_quotidien(self.user)

        self.user.refresh_from_db()
        self.assertEqual(self.user.serie_connexion, 4)
        # bonus de série = (4 - 1) * 2 = 6 Cubis
        self.assertGreaterEqual(montant, 15 + 6)
        self.assertLessEqual(montant, 25 + 6)

    def test_serie_reinitialisee_apres_un_trou(self):
        User.objects.filter(pk=self.user.pk).update(
            serie_connexion=9,
            derniere_connexion_bonus=timezone.localdate() - timedelta(days=3))
        self.user.refresh_from_db()

        bonus_quotidien(self.user)

        self.user.refresh_from_db()
        self.assertEqual(self.user.serie_connexion, 1)


class TresorTests(TestCase):
    def setUp(self):
        self.membre = creer_user("membre@test.cg")
        self.gardienne = creer_user("gardienne@test.cg", est_divinite=True)
        self.safir = creer_user("safir@test.cg", est_divinite=True,
                                is_superuser=True)

    def test_reserve_aux_divinites(self):
        with self.assertRaises(ErreurEconomie):
            envoyer_par_divinite(self.membre, self.membre, 10)

    def test_gardienne_plafonnee(self):
        with override_settings(LIMITE_ENVOI_GARDIENNE=100):
            with self.assertRaises(ErreurEconomie):
                envoyer_par_divinite(self.gardienne, self.membre, 101)

    def test_safir_sans_plafond(self):
        with override_settings(LIMITE_ENVOI_GARDIENNE=100):
            envoyer_par_divinite(self.safir, self.membre, 10_000)

        self.membre.refresh_from_db()
        self.assertEqual(self.membre.solde_cubis, 10_000)

    def test_envoi_trace_et_notifie(self):
        envoyer_par_divinite(self.gardienne, self.membre, 50, "bienvenue")

        self.membre.refresh_from_db()
        self.assertEqual(self.membre.solde_cubis, 50)
        t = Transaction.objects.get(type=Transaction.Type.ENVOI_DIVINITE)
        self.assertEqual((t.auteur, t.destinataire, t.montant),
                         (self.gardienne, self.membre, 50))
        self.assertEqual(self.membre.notifications.count(), 1)
