import os
import re

from django.http import HttpResponse, StreamingHttpResponse

RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")
TYPES = {
    ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".ogg": "audio/ogg",
    ".wav": "audio/wav", ".mp4": "video/mp4", ".webm": "video/webm",
}


def _lire(fichier, debut, longueur, bloc=256 * 1024):
    try:
        fichier.seek(debut)
        restant = longueur
        while restant > 0:
            donnees = fichier.read(min(bloc, restant))
            if not donnees:
                break
            restant -= len(donnees)
            yield donnees
    finally:
        fichier.close()


def servir_media(request, champ, telecharger=False):
    """Envoie un fichier audio/vidéo avec prise en charge des lectures
    partielles (Range), indispensable pour iPhone et pour avancer dans la
    lecture."""
    nom = champ.name
    ext = os.path.splitext(nom)[1].lower()
    type_mime = TYPES.get(ext, "application/octet-stream")
    taille = champ.storage.size(nom)
    debut, fin, statut = 0, max(taille - 1, 0), 200

    m = RANGE_RE.match(request.headers.get("Range", ""))
    if m and taille:
        g1, g2 = m.groups()
        if g1 == "" and g2 != "":
            debut = max(taille - int(g2), 0)
        else:
            debut = int(g1) if g1 else 0
            fin = min(int(g2), taille - 1) if g2 else taille - 1
        if debut > fin or debut >= taille:
            rep = HttpResponse(status=416)
            rep["Content-Range"] = f"bytes */{taille}"
            return rep
        statut = 206

    longueur = (fin - debut + 1) if taille else 0
    fichier = champ.storage.open(nom, "rb")
    rep = StreamingHttpResponse(_lire(fichier, debut, longueur),
                                status=statut, content_type=type_mime)
    rep["Content-Length"] = str(longueur)
    rep["Accept-Ranges"] = "bytes"
    if statut == 206:
        rep["Content-Range"] = f"bytes {debut}-{fin}/{taille}"
    rep["X-Content-Type-Options"] = "nosniff"
    rep["Cache-Control"] = "private, max-age=3600"
    disposition = "attachment" if telecharger else "inline"
    nom_propre = os.path.basename(nom).replace('"', "")
    rep["Content-Disposition"] = f'{disposition}; filename="{nom_propre}"'
    return rep
