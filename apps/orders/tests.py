from unittest import mock

from django.test import TestCase

from apps.accounts.models import User
from apps.economy.models import Transaction
from apps.economy.services import ErreurEconomie
from . import services
from .models import Order

MDP = "MotDePasse!2026"
S = Order.Statut


def compte(email, solde=0, **extra):
    u = User.objects.create_user(email=email, password=MDP,
                                 pseudo_whatsapp=email.split("@")[0], **extra)
    if solde:
        User.objects.filter(pk=u.pk).update(solde_cubis=solde)
        u.refresh_from_db()
    return u


class CommandeTests(TestCase):
    def setUp(self):
        self.acheteur = compte("acheteur@test.cg", solde=200)
        self.vendeur = compte("vendeur@test.cg", createur_valide=True)
        self.safir = compte("safir@test.cg", est_divinite=True,
                            is_superuser=True)

    def demande(self, prix=50):
        return services.creer_demande(
            self.acheteur, self.vendeur, "Scenario prive",
            "Une scene longue et detaillee", prix)

    def test_parcours_complet_livre_et_paie(self):
        c = self.demande(50)
        services.accepter(self.vendeur, c.pk)
        self.acheteur.refresh_from_db()
        self.assertEqual(self.acheteur.solde_cubis, 150)

        services.livrer(self.vendeur, c.pk)
        services.confirmer(self.acheteur, c.pk)

        self.acheteur.refresh_from_db()
        self.vendeur.refresh_from_db()
        c.refresh_from_db()
        self.assertEqual(self.acheteur.solde_cubis, 150)
        self.assertEqual(self.vendeur.solde_cubis, 50)
        self.assertEqual(c.statut, S.TERMINEE)

    def test_double_acceptation_ne_debite_qu_une_fois(self):
        c = self.demande(50)
        perimee = Order.objects.get(pk=c.pk)  # vue avant toute validation
        services.accepter(self.vendeur, c.pk)

        with mock.patch("apps.orders.services._charger", return_value=perimee):
            with self.assertRaises(ErreurEconomie):
                services.accepter(self.vendeur, c.pk)

        self.acheteur.refresh_from_db()
        self.assertEqual(self.acheteur.solde_cubis, 150)
        self.assertEqual(Transaction.objects.filter(
            type=Transaction.Type.SEQUESTRE).count(), 1)

    def test_double_confirmation_ne_paie_qu_une_fois(self):
        c = self.demande(50)
        services.accepter(self.vendeur, c.pk)
        services.livrer(self.vendeur, c.pk)
        perimee = Order.objects.get(pk=c.pk)
        services.confirmer(self.acheteur, c.pk)

        with mock.patch("apps.orders.services._charger", return_value=perimee):
            with self.assertRaises(ErreurEconomie):
                services.confirmer(self.acheteur, c.pk)

        self.vendeur.refresh_from_db()
        self.assertEqual(self.vendeur.solde_cubis, 50)
        self.assertEqual(Transaction.objects.filter(
            type=Transaction.Type.LIBERATION).count(), 1)

    def test_double_livraison_refusee(self):
        c = self.demande()
        services.accepter(self.vendeur, c.pk)
        services.livrer(self.vendeur, c.pk)

        with self.assertRaises(ErreurEconomie):
            services.livrer(self.vendeur, c.pk)

    def test_refus_et_annulation_ne_touchent_pas_aux_cubis(self):
        c = self.demande()
        services.refuser(self.vendeur, c.pk)

        self.acheteur.refresh_from_db()
        self.assertEqual(self.acheteur.solde_cubis, 200)
        self.assertEqual(Order.objects.get(pk=c.pk).statut, S.REFUSEE)

    def test_annulation_par_vendeur_rembourse(self):
        c = self.demande(50)
        services.accepter(self.vendeur, c.pk)
        services.annuler_par_vendeur(self.vendeur, c.pk)

        self.acheteur.refresh_from_db()
        c.refresh_from_db()
        self.assertEqual(self.acheteur.solde_cubis, 200)
        self.assertEqual(c.statut, S.ANNULEE)

    def test_litige_tranche_une_seule_fois(self):
        c = self.demande(50)
        services.accepter(self.vendeur, c.pk)
        services.ouvrir_litige(self.acheteur, c.pk, "Rien recu apres 3 jours")
        services.trancher(self.safir, c.pk, "rembourser", "Aucune preuve")

        with self.assertRaises(ErreurEconomie):
            services.trancher(self.safir, c.pk, "rembourser", "Encore")

        self.acheteur.refresh_from_db()
        self.vendeur.refresh_from_db()
        self.assertEqual(self.acheteur.solde_cubis, 200)
        self.assertEqual(self.vendeur.solde_cubis, 0)
        self.assertEqual(Transaction.objects.filter(
            type=Transaction.Type.REMBOURSEMENT).count(), 1)

    def test_decision_de_litige_enregistree(self):
        c = self.demande(50)
        services.accepter(self.vendeur, c.pk)
        services.ouvrir_litige(self.acheteur, c.pk, "Rien recu apres 3 jours")

        services.trancher(self.safir, c.pk, "rembourser", "Aucune preuve")

        c.refresh_from_db()
        self.assertEqual(c.statut, S.REMBOURSEE)
        self.assertEqual(c.decision, "rembourser")
        self.assertEqual(c.tranche_par, self.safir)

    def test_decision_de_litige_en_faveur_du_createur_enregistree(self):
        c = self.demande(50)
        services.accepter(self.vendeur, c.pk)
        services.ouvrir_litige(self.acheteur, c.pk, "Pas conforme a la demande")

        services.trancher(self.safir, c.pk, "payer", "Livraison prouvee")

        c.refresh_from_db()
        self.assertEqual(c.statut, S.TERMINEE)
        self.assertEqual(c.decision, "payer")
        self.assertEqual(c.tranche_par, self.safir)

    def test_litige_tranche_en_faveur_du_createur_une_seule_fois(self):
        c = self.demande(50)
        services.accepter(self.vendeur, c.pk)
        services.ouvrir_litige(self.acheteur, c.pk, "Pas conforme a la demande")
        services.trancher(self.safir, c.pk, "payer", "Livraison prouvee")

        with self.assertRaises(ErreurEconomie):
            services.trancher(self.safir, c.pk, "payer", "Encore")

        self.vendeur.refresh_from_db()
        self.assertEqual(self.vendeur.solde_cubis, 50)

    def test_confirmation_automatique_apres_delai(self):
        c = self.demande(50)
        services.accepter(self.vendeur, c.pk)
        services.livrer(self.vendeur, c.pk)
        Order.objects.filter(pk=c.pk).update(
            date_auto_confirmation=Order.objects.get(pk=c.pk).date_livraison)

        services.traiter_echeances()

        self.vendeur.refresh_from_db()
        self.assertEqual(self.vendeur.solde_cubis, 50)

    def test_divinite_ne_peut_pas_trancher_sa_propre_commande(self):
        c = self.demande(50)
        services.accepter(self.vendeur, c.pk)
        services.ouvrir_litige(self.acheteur, c.pk, "Probleme de livraison")
        Order.objects.filter(pk=c.pk).update(acheteur=self.safir)

        with self.assertRaises(ErreurEconomie):
            services.trancher(self.safir, c.pk, "rembourser", "Moi")

    def test_solde_insuffisant_a_l_acceptation(self):
        c = self.demande(50)
        # L'acheteur depense ailleurs entre la demande et l'acceptation.
        User.objects.filter(pk=self.acheteur.pk).update(solde_cubis=10)

        with self.assertRaises(ErreurEconomie):
            services.accepter(self.vendeur, c.pk)

        c.refresh_from_db()
        self.assertEqual(c.statut, S.DEMANDE)
