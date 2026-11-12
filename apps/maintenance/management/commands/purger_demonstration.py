"""Retire les comptes et articles de demonstration avant l'ouverture.

Par defaut la commande ne fait que lister : rien n'est supprime sans
--supprimer. Les comptes sont reconnus a leur domaine email (test.cg par
defaut), les articles a leur createur. Un compte qui a des commandes est
conserve : l'historique est partage avec l'autre partie et les modeles
interdisent la suppression (PROTECT).
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import ProtectedError, Q

from apps.inventory.models import InventoryItem
from apps.orders.models import Order
from apps.shop.models import Item

User = get_user_model()
MOT_CONFIRMATION = "SUPPRIMER"


class Command(BaseCommand):
    help = ("Liste les comptes et articles de demonstration, et les supprime "
            "uniquement avec --supprimer (confirmation demandee).")

    def add_arguments(self, parser):
        parser.add_argument(
            "--domaine", default="test.cg",
            help="Domaine email des comptes de demo (defaut : test.cg).")
        parser.add_argument(
            "--email", action="append", default=[],
            help="Email supplementaire a purger (option repetable).")
        parser.add_argument(
            "--article", action="append", type=int, default=[],
            help="Identifiant d'article supplementaire a supprimer (repetable).")
        parser.add_argument(
            "--avec-proprietaire", action="store_true",
            help="Inclut les superutilisateurs dans la purge (deconseille).")
        parser.add_argument(
            "--supprimer", action="store_true",
            help="Supprime reellement, apres confirmation.")
        parser.add_argument(
            "--oui", action="store_true",
            help="Supprime sans demander confirmation (scripts).")

    # ----- selection -----

    def _comptes(self, options):
        domaine = (options["domaine"] or "").strip().lstrip("@")
        emails = [e.strip() for e in options["email"] if e.strip()]
        if not domaine and not emails:
            raise CommandError("Indique --domaine ou --email.")
        condition = Q(pk__in=[])
        if domaine:
            condition |= Q(email__iendswith="@" + domaine)
        if emails:
            condition |= Q(email__in=emails)
        comptes = User.objects.filter(condition)
        if not options["avec_proprietaire"]:
            comptes = comptes.exclude(is_superuser=True)
        return comptes.order_by("date_inscription")

    def _articles(self, comptes, identifiants):
        condition = Q(createur__in=comptes)
        if identifiants:
            condition |= Q(pk__in=identifiants)
        return (Item.objects.filter(condition)
                .select_related("createur")
                .order_by("pk"))

    # ----- affichage -----

    def _lister(self, comptes, articles):
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"Comptes de demonstration ({comptes.count()}) :"))
        for compte in comptes:
            roles = [r for r, vrai in (("Divinité", compte.est_divinite),
                                       ("Modérateur", compte.is_staff),
                                       ("Créateur", compte.createur_valide))
                     if vrai]
            commandes = Order.objects.filter(
                Q(acheteur=compte) | Q(vendeur=compte)).count()
            self.stdout.write(
                f"  - {compte.email} · {compte.pseudo_whatsapp}"
                f" · {', '.join(roles) if roles else 'membre'}"
                f" · {compte.articles.count()} article(s)"
                f" · {commandes} commande(s)"
                f" · {compte.solde_cubis} Cubis")
        if not comptes:
            self.stdout.write("  (aucun)")

        achetes = InventoryItem.objects.filter(item__in=articles).count()
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"Articles a supprimer ({articles.count()}) :"))
        for article in articles:
            self.stdout.write(
                f"  - #{article.pk} {article.titre}"
                f" · {article.createur.pseudo_whatsapp}"
                f" · {article.prix_cubis} Cubis"
                f" · {article.get_categorie_display()}"
                f"{' · officiel' if article.est_officiel else ''}")
        if not articles:
            self.stdout.write("  (aucun)")
        if achetes:
            self.stdout.write(self.style.WARNING(
                f"  Attention : {achetes} exemplaire(s) de ces articles sont "
                "dans des inventaires et disparaitront avec eux."))
        officiels = articles.filter(est_officiel=True).count()
        if officiels:
            self.stdout.write(self.style.WARNING(
                f"  Attention : {officiels} article(s) officiels (catalogue) "
                "vont disparaitre. Relance installer_catalogue "
                "--proprietaire=<compte reel> apres la purge."))

    def _confirmer(self):
        reponse = input(
            f"\nTape {MOT_CONFIRMATION} pour confirmer la suppression "
            "definitive : ").strip()
        return reponse == MOT_CONFIRMATION

    # ----- suppression -----

    def _supprimer(self, comptes, articles):
        nb_articles = 0
        for article in articles:
            try:
                with transaction.atomic():
                    article.delete()
                nb_articles += 1
            except ProtectedError:
                self.stdout.write(self.style.WARNING(
                    f"Article #{article.pk} conservé : il est encore utilisé "
                    "(cadre, décor ou commande)."))

        nb_comptes = 0
        for compte in comptes:
            if Order.objects.filter(Q(acheteur=compte) | Q(vendeur=compte)).exists():
                self.stdout.write(self.style.WARNING(
                    f"{compte.email} conservé : ce compte a des commandes, "
                    "l'historique est partagé avec l'autre partie. Supprime ou "
                    "clos d'abord ces commandes."))
                continue
            try:
                with transaction.atomic():
                    compte.delete()
                nb_comptes += 1
            except ProtectedError:
                self.stdout.write(self.style.WARNING(
                    f"{compte.email} conservé : une donnée liée empêche la "
                    "suppression."))

        self.stdout.write(self.style.SUCCESS(
            f"{nb_comptes} compte(s) et {nb_articles} article(s) supprimés."))

    # ----- commande -----

    def handle(self, *args, **options):
        comptes = self._comptes(options)
        articles = self._articles(comptes, options["article"])
        self._lister(comptes, articles)

        if not comptes.exists() and not articles.exists():
            self.stdout.write("Rien à supprimer.")
            return
        if not options["supprimer"]:
            self.stdout.write(self.style.WARNING(
                "Mode liste : rien n'a été supprimé. "
                "Ajoute --supprimer pour agir."))
            return
        if not options["oui"] and not self._confirmer():
            self.stdout.write("Abandon : rien n'a été supprimé.")
            return
        self._supprimer(comptes, articles)
