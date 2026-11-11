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
