import threading
from datetime import timedelta

from django.db import DatabaseError, connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from apps.accounts.models import User
from .models import Transaction
from .services import (ErreurEconomie, bonus_quotidien, debiter,
                       envoyer_par_divinite, transferer)

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

    def test_gardienne_plafonnee_par_jour(self):
        with override_settings(LIMITE_ENVOI_GARDIENNE=100,
                               PLAFOND_JOURNALIER_TRESOR=120):
            envoyer_par_divinite(self.gardienne, self.membre, 100)

            with self.assertRaises(ErreurEconomie):
                envoyer_par_divinite(self.gardienne, self.membre, 30)

        self.membre.refresh_from_db()
        self.assertEqual(self.membre.solde_cubis, 100)

    def test_safir_depasse_le_plafond_journalier(self):
        with override_settings(PLAFOND_JOURNALIER_TRESOR=100):
            envoyer_par_divinite(self.safir, self.membre, 5_000)

        self.membre.refresh_from_db()
        self.assertEqual(self.membre.solde_cubis, 5_000)

    def test_envoi_trace_et_notifie(self):
        envoyer_par_divinite(self.gardienne, self.membre, 50, "bienvenue")

        self.membre.refresh_from_db()
        self.assertEqual(self.membre.solde_cubis, 50)
        t = Transaction.objects.get(type=Transaction.Type.ENVOI_DIVINITE)
        self.assertEqual((t.auteur, t.destinataire, t.montant),
                         (self.gardienne, self.membre, 50))
        self.assertEqual(self.membre.notifications.count(), 1)


class FarmBonusTests(TestCase):
    """Un appareil ne peut pas ramasser le bonus avec des comptes en serie."""

    def test_bonus_plafonne_par_appareil(self):
        empreinte = "a" * 64
        montants = [
            bonus_quotidien(creer_user(f"farm{rang}@test.cg"),
                            appareil=empreinte)
            for rang in range(4)
        ]

        self.assertEqual(len([m for m in montants if m]), 3)
        self.assertIsNone(montants[3])

    def test_appareils_differents_servis_normalement(self):
        for rang in range(3):
            self.assertIsNotNone(
                bonus_quotidien(creer_user(f"appareil{rang}@test.cg"),
                                appareil=f"{rang}" * 64))

    def test_quota_atteint_ne_bloque_pas_le_lendemain(self):
        empreinte = "b" * 64
        for rang in range(3):
            bonus_quotidien(creer_user(f"serie{rang}@test.cg"),
                            appareil=empreinte)
        dernier = creer_user("serie-refus@test.cg")

        self.assertIsNone(bonus_quotidien(dernier, appareil=empreinte))
        dernier.refresh_from_db()
        # La journee refusee n'a pas ete consommee.
        self.assertIsNone(dernier.derniere_connexion_bonus)


class ConcurrenceTests(TransactionTestCase):
    """Deux depenses simultanees ne peuvent pas vider deux fois le solde."""

    def test_debit_conditionnel_ne_passe_qu_une_fois(self):
        # Le coeur du correctif, sans threads : le deuxieme debit ne trouve
        # plus de solde suffisant, meme si la valeur a ete lue avant.
        alice = creer_user("alice-debit@test.cg", solde=100)

        self.assertTrue(debiter(alice.pk, 100))
        self.assertFalse(debiter(alice.pk, 100))

        alice.refresh_from_db()
        self.assertEqual(alice.solde_cubis, 0)

    def test_double_depense_simultanee(self):
        alice = creer_user("alice-concurrente@test.cg", solde=100)
        bob = creer_user("bob-concurrent@test.cg")
        resultats = []

        def depenser():
            try:
                transferer(alice, bob, 100)
                resultats.append("accepte")
            except ErreurEconomie:
                resultats.append("refuse")
            except DatabaseError:
                # SQLite peut refuser la seconde ecriture simultanee :
                # dans tous les cas, aucun Cubis n'est cree.
                resultats.append("bloque")
            finally:
                connections.close_all()

        fils = [threading.Thread(target=depenser) for _ in range(2)]
        for fil in fils:
            fil.start()
        for fil in fils:
            fil.join()

        alice.refresh_from_db()
        bob.refresh_from_db()
        self.assertEqual(len(resultats), 2)
        self.assertLessEqual(resultats.count("accepte"), 1)
        # L'invariant qui compte : rien n'est cree ni perdu.
        self.assertEqual(alice.solde_cubis + bob.solde_cubis, 100)
        self.assertEqual(bob.solde_cubis, 100 * resultats.count("accepte"))
        self.assertEqual(
            Transaction.objects.filter(
                type=Transaction.Type.TRANSFERT).count(),
            resultats.count("accepte"))


class CompteurIndisponibleTests(TestCase):
    """Un compteur absent ne doit jamais bloquer la connexion d'un membre."""

    def test_bonus_verse_si_la_table_du_compteur_manque(self):
        user = creer_user("sans-compteur@test.cg")
        with connections["default"].cursor() as curseur:
            curseur.execute("DROP TABLE economy_bonusappareil")

        montant = bonus_quotidien(user, appareil="c" * 64)

        self.assertIsNotNone(montant)
        user.refresh_from_db()
        self.assertIsNotNone(user.derniere_connexion_bonus)
