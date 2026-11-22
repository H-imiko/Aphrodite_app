/* =========================================================
   Aphrodite — site de présentation
   Deux réglages seulement : les adresses, en haut de ce fichier.
   ========================================================= */

/* Renseigner ces adresses avant la mise en ligne.
   Tant qu'une adresse est vide, le bouton reste sur place
   au lieu de mener à une page inexistante. */
const LIENS = {
    application: "",      // ex. "https://app.aphrodite.cg/"          — bouton « Entrer »
    inscription: "",      // ex. "https://app.aphrodite.cg/inscription/"
    whatsapp: "",         // lien d'invitation du groupe WhatsApp
    createurs: "",        // ex. "https://app.aphrodite.cg/createurs/du-mois/"
    reglement: "",        // ex. "https://app.aphrodite.cg/reglement/"
    confidentialite: ""   // ex. "https://app.aphrodite.cg/confidentialite/"
};

/* --- Adresses ------------------------------------------------- */

document.querySelectorAll("[data-lien]").forEach((lien) => {
    const adresse = LIENS[lien.dataset.lien];
    if (adresse) {
        lien.href = adresse;
        if (lien.dataset.lien === "whatsapp") {
            lien.target = "_blank";
            lien.rel = "noopener";
        }
    } else {
        lien.title = "Adresse à renseigner dans main.js";
    }
});

/* --- En-tête : fond au défilement ----------------------------- */

const entete = document.getElementById("entete");
const progression = document.querySelector(".progression span");

function surDefilement() {
    const y = window.scrollY;
    entete.classList.toggle("entete--solide", y > 80);

    const hauteur = document.documentElement.scrollHeight - window.innerHeight;
    const part = hauteur > 0 ? Math.min(y / hauteur, 1) : 0;
    progression.style.width = (part * 100).toFixed(2) + "%";
}

window.addEventListener("scroll", surDefilement, { passive: true });
surDefilement();

/* --- Apparition des blocs ------------------------------------- */

const blocs = document.querySelectorAll("[data-reveal]");

if ("IntersectionObserver" in window) {
    const observateur = new IntersectionObserver((entrees) => {
        entrees.forEach((entree) => {
            if (entree.isIntersecting) {
                entree.target.classList.add("est-visible");
                observateur.unobserve(entree.target);
            }
        });
    }, { rootMargin: "0px 0px -12% 0px", threshold: 0.08 });

    blocs.forEach((bloc) => observateur.observe(bloc));
} else {
    blocs.forEach((bloc) => bloc.classList.add("est-visible"));
}

/* --- Bouton « couper le mouvement » --------------------------- */

const boutonMouvement = document.querySelector(".bouton-son");

if (boutonMouvement) {
    const actif = window.localStorage.getItem("aphrodite-immobile") === "1";
    document.body.classList.toggle("immobile", actif);
    boutonMouvement.setAttribute("aria-pressed", String(actif));
    boutonMouvement.setAttribute("aria-label", actif ? "Remettre le mouvement" : "Couper le mouvement");

    boutonMouvement.addEventListener("click", () => {
        const maintenant = !document.body.classList.contains("immobile");
        document.body.classList.toggle("immobile", maintenant);
        boutonMouvement.setAttribute("aria-pressed", String(maintenant));
        boutonMouvement.setAttribute("aria-label", maintenant ? "Remettre le mouvement" : "Couper le mouvement");
        window.localStorage.setItem("aphrodite-immobile", maintenant ? "1" : "0");
    });
}
