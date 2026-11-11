"""Sauvegarde de la base sans interrompre le site.

Sous SQLite, copier le fichier a la main peut donner une base corrompue si une
ecriture est en cours : cette commande passe par l'API de sauvegarde de SQLite,
qui produit un instantane coherent, puis compresse le resultat.
"""

import gzip
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connections


class Command(BaseCommand):
    help = "Enregistre une copie compressee de la base dans sauvegardes/."

    def add_arguments(self, parser):
        parser.add_argument(
            "--garder",
            type=int,
            default=14,
            help="Nombre de sauvegardes a conserver (defaut : 14).",
        )
        parser.add_argument(
            "--dossier",
            default=None,
            help="Dossier de destination (defaut : SAUVEGARDES_DIR).",
        )

    def handle(self, *args, **options):
        connexion = connections["default"]
        if connexion.vendor != "sqlite":
            raise CommandError(
                "Cette commande ne gere que SQLite. "
                "Pour PostgreSQL, utilisez pg_dump (voir docs/migration-postgres.md)."
            )

        dossier = Path(options["dossier"] or settings.SAUVEGARDES_DIR)
        dossier.mkdir(parents=True, exist_ok=True)

        connexion.ensure_connection()
        horodatage = datetime.now().strftime("%Y%m%d-%H%M%S")
        temporaire = dossier / f"db-{horodatage}.sqlite3"
        if temporaire.exists():
            temporaire.unlink()

        copie = sqlite3.connect(temporaire)
        try:
            connexion.connection.backup(copie)
        finally:
            copie.close()

        archive = dossier / f"db-{horodatage}.sqlite3.gz"
        with temporaire.open("rb") as source, gzip.open(archive, "wb") as cible:
            shutil.copyfileobj(source, cible)
        temporaire.unlink()

        conservees = self._purger(dossier, max(1, options["garder"]))
        taille = archive.stat().st_size / 1024
        self.stdout.write(
            self.style.SUCCESS(f"Sauvegarde ecrite : {archive} ({taille:.0f} Ko)")
        )
        self.stdout.write(f"{conservees} sauvegarde(s) conservee(s) dans {dossier}")

    def _purger(self, dossier, a_garder):
        fichiers = sorted(
            dossier.glob("db-*.sqlite3.gz"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        for ancienne in fichiers[a_garder:]:
            ancienne.unlink()
        return min(len(fichiers), a_garder)
