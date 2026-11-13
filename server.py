"""Lanceur de production d'Aphrodite.

Pourquoi ce fichier existe : Waitress 3 supprime par defaut les en-tetes
`X-Forwarded-*`, par securite (ils sont falsifiables par le client). Derriere
nginx, Django ne voyait donc jamais le HTTPS et repondait 301 en boucle, et
toutes les requetes arrivaient avec l'adresse du proxy — ce qui faussait aussi
la limitation de debit.

Ici, on declare le proxy de confiance : Waitress lit alors X-Forwarded-Proto
et X-Forwarded-For **uniquement** s'ils viennent de cette adresse, pose
`wsgi.url_scheme = https` et remplace REMOTE_ADDR par la vraie adresse du
membre. Django n'a rien d'autre a configurer.

Utilisation :
    python server.py

Reglages (variables d'environnement) :
    PORT                      port d'ecoute, 8000 par defaut
    APHRODITE_TRUSTED_PROXY   adresse du proxy de confiance (defaut
                              127.0.0.1). Waitress n'accepte qu'une adresse :
                              si nginx se connecte en IPv6, mettre ::1.
                              Mettre une valeur vide si le site est expose
                              directement, sans proxy.
"""

import os

from waitress import serve

from config.wsgi import application


def main():
    options = {
        "host": "127.0.0.1",
        "port": int(os.environ.get("PORT", "8000")),
    }
    # Waitress n'accepte qu'une seule adresse de proxy de confiance.
    proxys = os.environ.get("APHRODITE_TRUSTED_PROXY", "127.0.0.1").strip()
    if proxys:
        options["trusted_proxy"] = proxys
        options["trusted_proxy_headers"] = ["x-forwarded-proto",
                                           "x-forwarded-for"]
        options["clear_untrusted_proxy_headers"] = True
    serve(application, **options)


if __name__ == "__main__":
    main()
