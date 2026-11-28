"""Liste les textes a traduire (templates + Python).

`makemessages` de Django a besoin de gettext (xgettext), qui n'est pas
toujours installe. Ce script fait le meme travail de recensement en lisant
les balises {% translate %} / {% blocktranslate %} du moteur de templates et
les appels _() du code Python.

Usage :  .venv/bin/python tools/liste_msgids.py
"""

import ast
import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent


def _preparer_django():
    if str(BASE) not in sys.path:
        sys.path.insert(0, str(BASE))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()


def extrait_msgids():
    """Renvoie (singuliers, pluriels) : les textes a traduire du projet."""
    _preparer_django()

    from django.template.base import NodeList
    from django.template.loader import get_template
    from django.templatetags.i18n import (
        BlockTranslateNode, TranslateNode)

    singuliers = set()
    pluriels = set()

    def parcourir(noeuds):
        for noeud in noeuds:
            if isinstance(noeud, BlockTranslateNode):
                # render_token_list reproduit exactement le msgid cherche par
                # Django (variables -> %(nom)s, blancs reduits si trimmed).
                msgid = noeud.render_token_list(noeud.singular)[0]
                singuliers.add(msgid)
                if noeud.plural:
                    pluriels.add(msgid)
            elif isinstance(noeud, TranslateNode):
                litteral = getattr(noeud.filter_expression.var, "literal", None)
                if litteral is not None:
                    singuliers.add(str(litteral))
            for nom in getattr(noeud, "child_nodelists", ()):
                valeur = getattr(noeud, nom, None)
                if isinstance(valeur, NodeList):
                    parcourir(valeur)
                elif isinstance(valeur, (list, tuple)):
                    for element in valeur:
                        if isinstance(element, NodeList):
                            parcourir(element)
                        elif hasattr(element, "child_nodelists"):
                            parcourir([element])

    for chemin in sorted((BASE / "templates").rglob("*.html")):
        nom = str(chemin.relative_to(BASE / "templates"))
        parcourir(get_template(nom).template.nodelist)

    for chemin in sorted((BASE / "apps").rglob("*.py")):
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.Call):
                continue
            fonction = noeud.func
            nom = getattr(fonction, "id", getattr(fonction, "attr", ""))
            if nom not in {"_", "gettext", "gettext_lazy"}:
                continue
            if noeud.args and isinstance(noeud.args[0], ast.Constant):
                singuliers.add(noeud.args[0].value)

    return singuliers, pluriels


def main():
    singuliers, pluriels = extrait_msgids()
    print("=== SINGULIERS", len(singuliers))
    for msgid in sorted(singuliers):
        print(repr(msgid))
    print("=== PLURIELS", len(pluriels))
    for msgid in sorted(pluriels):
        print(repr(msgid))


if __name__ == "__main__":
    main()
