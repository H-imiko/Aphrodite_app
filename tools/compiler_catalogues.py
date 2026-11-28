"""Compile les catalogues de traduction et verifie qu'ils sont complets.

Django lit des fichiers .mo compiles, que `compilemessages` fabrique avec
gettext (msgfmt). Sans gettext installe, ce script fait les deux etapes :
il compile chaque locale/<code>/LC_MESSAGES/django.po vers le .mo voisin,
puis signale les textes traduisibles absents du catalogue, les traductions
vides et les entrees devenues inutiles.

Usage :  .venv/bin/python tools/compiler_catalogues.py
         (code de sortie 1 si un catalogue est incomplet)
"""

import sys
from pathlib import Path

import polib

sys.path.insert(0, str(Path(__file__).resolve().parent))
from liste_msgids import BASE, extrait_msgids  # noqa: E402

LANGUES = ("en", "es")


def main():
    singuliers, pluriels = extrait_msgids()
    probleme = False
    for langue in LANGUES:
        chemin_po = BASE / "locale" / langue / "LC_MESSAGES" / "django.po"
        if not chemin_po.exists():
            print("catalogue manquant :", chemin_po)
            probleme = True
            continue
        catalogue = polib.pofile(str(chemin_po))
        traduits = {entree.msgid: entree for entree in catalogue
                    if entree.msgid}
        manquants = sorted(m for m in singuliers if m not in traduits)
        vides = sorted(m for m, e in traduits.items() if not e.msgstr
                       and not e.msgstr_plural)
        vides += sorted(m for m in pluriels
                        if m in traduits and not traduits[m].msgstr_plural)
        inutiles = sorted(m for m in traduits if m not in singuliers)
        catalogue.save_as_mofile(str(chemin_po.with_suffix(".mo")))
        print("%s : %s textes, %s traduits, .mo ecrit"
              % (langue, len(singuliers), len(traduits) - len(vides)))
        for titre, liste in (("SANS TRADUCTION", manquants),
                             ("TRADUCTION VIDE", vides),
                             ("ENTREE INUTILE", inutiles)):
            if liste:
                probleme = True
                print("  %s :" % titre)
                for msgid in liste:
                    print("    %r" % msgid)
    return 1 if probleme else 0


if __name__ == "__main__":
    sys.exit(main())
