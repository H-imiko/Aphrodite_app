"""Contrat geometrique des cadres de profil.

Un cadre est un PNG carre dont le centre est un trou transparent. Le trou
n'occupe pas toujours la meme part de l'image (60 % pour le cadre livre,
64 % pour la consigne du README). Plutot que d'imposer un chiffre unique et
de laisser les anciens cadres decales, on mesure le trou a l'envoi et on le
stocke sur l'article : le profil affiche alors chaque cadre a la taille qui
aligne son trou sur l'avatar.

Mesure volontairement simple (balayage depuis le centre) : elle ne lit que
quelques milliers de pixels et ne peut pas faire expirer un envoi.
"""

TROU_MIN = 0.40
TROU_MAX = 0.85
ECART_CENTRE_MAX = 0.04
SEUIL_ALPHA = 16


def mesurer_trou(img):
    """Renvoie la geometrie du trou central, ou None s'il n'y en a pas.

    Clefs : ratio (part de la largeur), ecart_x / ecart_y (0 = centre),
    largeur et hauteur du trou en pixels.
    """
    rgba = img.convert("RGBA")
    alpha = rgba.getchannel("A")
    largeur_image, hauteur_image = rgba.size
    if largeur_image != hauteur_image:
        return None
    cx = cy = largeur_image // 2

    def vide(x, y):
        return alpha.getpixel((x, y)) <= SEUIL_ALPHA

    if not vide(cx, cy):
        return None

    gauche = cx
    while gauche > 0 and vide(gauche - 1, cy):
        gauche -= 1
    droite = cx
    while droite < largeur_image - 1 and vide(droite + 1, cy):
        droite += 1
    haut = cy
    while haut > 0 and vide(cx, haut - 1):
        haut -= 1
    bas = cy
    while bas < hauteur_image - 1 and vide(cx, bas + 1):
        bas += 1

    largeur_trou = droite - gauche + 1
    hauteur_trou = bas - haut + 1
    return {
        "ratio": max(largeur_trou, hauteur_trou) / largeur_image,
        "ecart_x": abs((gauche + droite) / 2 / largeur_image - 0.5),
        "ecart_y": abs((haut + bas) / 2 / hauteur_image - 0.5),
        "largeur": largeur_trou,
        "hauteur": hauteur_trou,
    }


def problemes_cadre(img):
    """Liste des raisons de refuser un cadre (vide si le cadre est valable)."""
    problemes = []
    largeur, hauteur = img.size
    if min(largeur, hauteur) < 300:
        problemes.append(
            "Le cadre est trop petit : 800 x 800 est la taille conseillée.")
    if not 0.97 <= largeur / hauteur <= 1.03:
        problemes.append(
            "Le cadre doit être carré (largeur = hauteur).")
        # Sans carré, la mesure du trou n'a pas de sens.
        return problemes
    mesure = mesurer_trou(img)
    if mesure is None:
        problemes.append(
            "Le centre du cadre doit être transparent : c'est le trou où "
            "apparaît la photo de profil.")
        return problemes
    if not TROU_MIN <= mesure["ratio"] <= TROU_MAX:
        problemes.append(
            "Le trou central doit occuper entre 40 % et 85 % de la largeur "
            f"(mesure : {mesure['ratio'] * 100:.0f} %).")
    if (mesure["ecart_x"] > ECART_CENTRE_MAX
            or mesure["ecart_y"] > ECART_CENTRE_MAX):
        problemes.append(
            "Le trou central n'est pas centré : laisse une marge égale "
            "autour de la photo.")
    return problemes


def largeur_affichage(ratio):
    """Largeur du cadre en % de l'avatar, pour que le trou fasse 100 %."""
    if not ratio:
        return None
    return round(100 / ratio, 2)
