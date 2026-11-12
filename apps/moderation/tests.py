from django.test import TestCase
from django.urls import reverse

from .models import AuditLog, Sanction

from django.contrib.auth import get_user_model

User = get_user_model()
MDP = "MotDePasse!2026"


def compte(email, **extra):
    return User.objects.create_user(email=email, password=MDP,
                                    pseudo_whatsapp=email.split("@")[0], **extra)


class EquipeTests(TestCase):
    """Nomination des Divinités et des modérateurs."""

    def setUp(self):
        self.safir = User.objects.create_superuser(
            email="safir@test.cg", password=MDP, pseudo_whatsapp="Safir")
        self.divinite = compte("divinite@test.cg", est_divinite=True)
        self.staff = compte("staff@test.cg", is_staff=True)
        self.membre = compte("membre@test.cg")

    def nommer(self, cible, action):
        return self.client.post(reverse("equipe_action", args=[cible.pk]),
                                {"action": action})

    def test_page_reservee_aux_divinites(self):
        for utilisateur in (self.membre, self.staff):
            self.client.force_login(utilisateur)
            with self.subTest(utilisateur=utilisateur.email):
                self.assertEqual(
                    self.client.get(reverse("equipe")).status_code, 403)

    def test_nommer_puis_retirer_un_moderateur(self):
        self.client.force_login(self.divinite)

        self.nommer(self.membre, "staff")
        self.membre.refresh_from_db()
        self.assertTrue(self.membre.is_staff)
        self.assertFalse(self.membre.est_divinite)

        self.nommer(self.membre, "retirer_staff")
        self.membre.refresh_from_db()
        self.assertFalse(self.membre.is_staff)

    def test_nommer_une_divinite(self):
        self.client.force_login(self.divinite)

        self.nommer(self.membre, "divinite")

        self.membre.refresh_from_db()
        self.assertTrue(self.membre.est_divinite)

    def test_nomination_inscrite_au_journal(self):
        self.client.force_login(self.divinite)

        self.nommer(self.membre, "staff")

        entree = AuditLog.objects.filter(cible=self.membre).first()
        self.assertIsNotNone(entree)
        self.assertEqual(entree.action, AuditLog.Action.ROLE_ATTRIBUE)
        self.assertEqual(entree.auteur, self.divinite)

    def test_pas_de_modification_de_ses_propres_roles(self):
        self.client.force_login(self.divinite)

        self.nommer(self.divinite, "retirer_divinite")

        self.divinite.refresh_from_db()
        self.assertTrue(self.divinite.est_divinite)

    def test_proprietaire_protege(self):
        self.client.force_login(self.divinite)

        self.nommer(self.safir, "retirer_divinite")

        self.safir.refresh_from_db()
        self.assertTrue(self.safir.is_superuser)

    def test_retirer_une_divinite_quand_il_en_reste_une(self):
        self.client.force_login(self.safir)

        self.nommer(self.divinite, "retirer_divinite")

        self.divinite.refresh_from_db()
        self.assertFalse(self.divinite.est_divinite)

    def test_action_inconnue_ignoree(self):
        self.client.force_login(self.divinite)

        self.nommer(self.membre, "empereur")

        self.membre.refresh_from_db()
        self.assertFalse(self.membre.is_staff)
        self.assertFalse(self.membre.est_divinite)


class ModerateurTests(TestCase):
    """Le staff modère, mais ne touche ni aux Cubis ni à l'économie."""

    def setUp(self):
        self.divinite = compte("divinite@test.cg", est_divinite=True)
        self.staff = compte("staff@test.cg", is_staff=True)
        self.membre = compte("membre@test.cg", solde_cubis=200)

    def test_acces_du_moderateur(self):
        self.client.force_login(self.staff)

        self.assertEqual(self.client.get(reverse("panel")).status_code, 200)
        self.assertEqual(
            self.client.get(reverse("signalements")).status_code, 200)
        for nom in ("economie", "tresor", "journal", "candidatures", "litiges"):
            with self.subTest(page=nom):
                self.assertEqual(
                    self.client.get(reverse(nom)).status_code, 403)

    def test_divinite_garde_tous_les_acces(self):
        self.client.force_login(self.divinite)

        for nom in ("panel", "signalements", "economie", "tresor", "journal"):
            with self.subTest(page=nom):
                self.assertEqual(
                    self.client.get(reverse(nom)).status_code, 200)

    def test_moderateur_peut_avertir(self):
        self.client.force_login(self.staff)

        reponse = self.client.post(
            reverse("sanction_action", args=[self.membre.pk]),
            {"action": "avertir", "raison": "Propos hors charte"})

        self.assertEqual(reponse.status_code, 302)
        self.assertTrue(Sanction.objects.filter(
            user=self.membre, type=Sanction.Type.AVERTISSEMENT).exists())

    def test_moderateur_ne_peut_pas_reduire_les_cubis(self):
        self.client.force_login(self.staff)

        self.client.post(
            reverse("sanction_action", args=[self.membre.pk]),
            {"action": "reduire", "montant": "50", "raison": "Test cubis"})

        self.membre.refresh_from_db()
        self.assertEqual(self.membre.solde_cubis, 200)
        self.assertFalse(Sanction.objects.filter(
            type=Sanction.Type.REDUCTION_CUBIS).exists())

    def test_moderateur_ne_peut_pas_sanctionner_une_divinite(self):
        self.client.force_login(self.staff)

        self.client.post(
            reverse("sanction_action", args=[self.divinite.pk]),
            {"action": "avertir", "raison": "Tentative"})

        self.assertFalse(Sanction.objects.filter(
            user=self.divinite).exists())
