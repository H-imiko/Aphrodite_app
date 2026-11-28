/* Mini-jeux : déclenche les animations d'après le résultat décidé par le
   serveur. Aucun tirage ici : l'angle de la roue, la face de la pièce et les
   cartes viennent des attributs data-* rendus par le serveur. */
(function () {
  "use strict";

  var reduit = window.matchMedia
    && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function apres(callback) {
    requestAnimationFrame(function () {
      requestAnimationFrame(callback);
    });
  }

  var roue = document.querySelector(".roue-zone[data-angle]");
  if (roue) {
    var disque = roue.querySelector(".roue-disque");
    var angle = roue.dataset.angle;
    if (reduit) {
      disque.style.transition = "none";
      disque.style.transform = "rotate(" + angle + "deg)";
    } else {
      apres(function () {
        disque.style.transform = "rotate(" + angle + "deg)";
      });
    }
  }

  var piece = document.querySelector(".piece-zone[data-cote]");
  if (piece) {
    var moitie = piece.dataset.cote === "face" ? 180 : 0;
    var tours = reduit ? 0 : 1800;
    apres(function () {
      var pieceInterieure = piece.querySelector(".piece");
      pieceInterieure.style.transition = reduit ? "none" : "";
      pieceInterieure.style.transform = "rotateY(" + (tours + moitie) + "deg)";
    });
  }

  var cartes = document.querySelectorAll(".poker-zone[data-tire] .carte");
  for (var index = 0; index < cartes.length; index += 1) {
    (function (carte, rang) {
      if (reduit) {
        carte.classList.add("retournee");
        return;
      }
      window.setTimeout(function () {
        carte.classList.add("retournee");
      }, 250 + rang * 650);
    })(cartes[index], index);
  }
})();
