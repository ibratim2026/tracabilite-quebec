/* Traçabilité Québec — composants interactifs, sans dépendance externe.
 *
 * Chaque composant se branche sur un élément [data-*] et lit ses données
 * dans un <script type="application/json"> voisin. Fonctionne tel quel dans
 * la version statique (GitHub Pages) : tout se passe dans le navigateur.
 *
 *   data-graph-serie  courbe d'un indicateur dans le temps (survol = valeur)
 *   data-haltere      coût annoncé vs coût actuel des grands projets
 *   data-quiz         « Devinez le chiffre »
 *   data-aveugle      comparateur de promesses à l'aveugle
 *   data-budget       « Jouez au ministre des Finances »
 *   data-parcours     progression « Électeur éclairé »
 */
(function () {
  "use strict";

  var NS = "http://www.w3.org/2000/svg";

  // Les couleurs des graphiques viennent des jetons CSS, comme le reste du site.
  function jeton(nom, secours) {
    var v = getComputedStyle(document.documentElement).getPropertyValue(nom).trim();
    return v || secours;
  }
  var GRIS, GRILLE, BLEU, GRIS_MARQUE, SURFACE;
  function relireCouleurs() {
    GRIS = jeton("--gris", "#4a5a6e");
    GRILLE = jeton("--bordure", "#dfe6ee");
    BLEU = jeton("--bleu", "#2e6be6");
    GRIS_MARQUE = jeton("--gris-badge", "#7b8a9c");
    SURFACE = jeton("--surface", "#ffffff");
  }
  relireCouleurs();

  function donnees(el) {
    var s = el.querySelector('script[type="application/json"]');
    try { return s ? JSON.parse(s.textContent) : null; } catch (e) { return null; }
  }
  function svg(tag, attrs, parent) {
    var n = document.createElementNS(NS, tag);
    for (var k in attrs) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  }
  function h(tag, cls, texte, parent) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (texte != null) n.textContent = texte;
    if (parent) parent.appendChild(n);
    return n;
  }
  function nf(v, dec) {
    return Number(v).toLocaleString("fr-CA", {
      maximumFractionDigits: dec == null ? 1 : dec,
      minimumFractionDigits: 0
    });
  }
  function avecUnite(v, u) {
    if (!u) return nf(v);
    if (u === "%" || u === "$" || u === "G$" || u === "M$") return nf(v) + " " + u;
    return nf(v) + " " + u;
  }
  function melanger(a) {
    for (var i = a.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1)), t = a[i]; a[i] = a[j]; a[j] = t;
    }
    return a;
  }

  /* ---------------------------------------------------------- stockage local */
  // Progression personnelle seulement : si le navigateur la refuse, le site
  // fonctionne quand même, sans mémoire.
  var CLE = "tq-parcours-v1";
  function lireParcours() {
    try { return JSON.parse(localStorage.getItem(CLE)) || {}; } catch (e) { return {}; }
  }
  function ecrireParcours(p) {
    try { localStorage.setItem(CLE, JSON.stringify(p)); } catch (e) { /* ignoré */ }
  }
  function marquer(cle) {
    var p = lireParcours();
    if (!p[cle]) { p[cle] = Date.now(); ecrireParcours(p); }
  }

  /* ---------------------------------------------------------- infobulle */
  var bulle;
  function infobulle(x, y, lignes) {
    if (!bulle) { bulle = h("div", "tq-bulle", null, document.body); }
    bulle.textContent = "";
    lignes.forEach(function (l, i) { h("div", i === 0 ? "tq-bulle-val" : "tq-bulle-lib", l, bulle); });
    bulle.style.display = "block";
    var r = bulle.getBoundingClientRect();
    var gx = Math.min(x + 14, window.innerWidth - r.width - 8);
    bulle.style.left = (gx + window.scrollX) + "px";
    bulle.style.top = (y - r.height - 12 + window.scrollY) + "px";
  }
  function cacherBulle() { if (bulle) bulle.style.display = "none"; }

  /* ---------------------------------------------------------- courbe d'indicateur */
  function grapheSerie(el) {
    var d = donnees(el);
    if (!d || !d.serie || d.serie.length < 2) { el.style.display = "none"; return; }
    var pts = d.serie.slice().sort(function (a, b) { return a.annee - b.annee; });
    var W = 320, H = 150, m = { g: 38, d: 44, h: 14, b: 22 };
    var vals = pts.map(function (p) { return p.valeur; });
    if (d.comparaison_num != null) vals.push(d.comparaison_num);
    var min = Math.min.apply(null, vals), max = Math.max.apply(null, vals);
    var marge = (max - min) * 0.15 || Math.abs(max) * 0.1 || 1;
    min = min - marge; max = max + marge;
    if (min > 0 && min < (max - min) * 0.6) min = 0;
    var x0 = pts[0].annee, x1 = pts[pts.length - 1].annee;
    function X(a) { return m.g + (W - m.g - m.d) * (a - x0) / (x1 - x0); }
    function Y(v) { return m.h + (H - m.h - m.b) * (1 - (v - min) / (max - min)); }

    var s = svg("svg", { viewBox: "0 0 " + W + " " + H, role: "img",
      "aria-label": (d.nom || "Indicateur") + " de " + x0 + " à " + x1 }, null);
    // grille : 3 repères horizontaux
    for (var i = 0; i <= 2; i++) {
      var v = min + (max - min) * i / 2;
      svg("line", { x1: m.g, x2: W - m.d, y1: Y(v), y2: Y(v), stroke: GRILLE, "stroke-width": 1 }, s);
      svg("text", { x: m.g - 6, y: Y(v) + 4, "text-anchor": "end", class: "ig-note" }, s).textContent = nf(v, Math.abs(max - min) < 10 ? 1 : 0);
    }
    svg("text", { x: X(x0), y: H - 4, "text-anchor": "start", class: "ig-note" }, s).textContent = x0;
    svg("text", { x: X(x1), y: H - 4, "text-anchor": "end", class: "ig-note" }, s).textContent = x1;

    if (d.comparaison_num != null) {
      var yc = Y(d.comparaison_num);
      svg("line", { x1: m.g, x2: W - m.d, y1: yc, y2: yc, stroke: GRIS_MARQUE, "stroke-width": 1.5 }, s);
      svg("text", { x: W - m.d + 4, y: yc + 4, class: "ig-note" }, s).textContent = d.comparaison_nom || "Repère";
    }
    var chemin = pts.map(function (p, i) { return (i ? "L" : "M") + X(p.annee) + " " + Y(p.valeur); }).join(" ");
    svg("path", { d: chemin + " L" + X(x1) + " " + (H - m.b) + " L" + X(x0) + " " + (H - m.b) + " Z", fill: BLEU, opacity: 0.08 }, s);
    svg("path", { d: chemin, fill: "none", stroke: BLEU, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }, s);
    var der = pts[pts.length - 1];
    svg("circle", { cx: X(der.annee), cy: Y(der.valeur), r: 4.5, fill: BLEU, stroke: SURFACE, "stroke-width": 2 }, s);
    svg("text", { x: X(der.annee) + 7, y: Y(der.valeur) + 4, class: "ig-val", style: "font-size:12px" }, s).textContent = nf(der.valeur);

    // survol : ligne verticale accrochée à l'année la plus proche
    var ligne = svg("line", { y1: m.h, y2: H - m.b, stroke: GRIS, "stroke-width": 1, visibility: "hidden" }, s);
    var point = svg("circle", { r: 4.5, fill: BLEU, stroke: SURFACE, "stroke-width": 2, visibility: "hidden" }, s);
    var zone = svg("rect", { x: m.g, y: 0, width: W - m.g - m.d, height: H, fill: "transparent" }, s);
    function survol(ev) {
      var r = s.getBoundingClientRect();
      var ax = x0 + (x1 - x0) * ((ev.clientX - r.left) * W / r.width - m.g) / (W - m.g - m.d);
      var p = pts.reduce(function (a, b) { return Math.abs(b.annee - ax) < Math.abs(a.annee - ax) ? b : a; });
      ligne.setAttribute("x1", X(p.annee)); ligne.setAttribute("x2", X(p.annee));
      point.setAttribute("cx", X(p.annee)); point.setAttribute("cy", Y(p.valeur));
      ligne.setAttribute("visibility", "visible"); point.setAttribute("visibility", "visible");
      var l = [avecUnite(p.valeur, d.unite), String(p.annee)];
      if (d.comparaison_num != null) l.push((d.comparaison_nom || "Repère") + " : " + avecUnite(d.comparaison_num, d.unite));
      infobulle(ev.clientX, ev.clientY, l);
    }
    zone.addEventListener("pointermove", survol);
    zone.addEventListener("pointerleave", function () {
      ligne.setAttribute("visibility", "hidden"); point.setAttribute("visibility", "hidden"); cacherBulle();
    });
    el.insertBefore(s, el.firstChild);
    // version texte (accessibilité, lecteurs d'écran, impression)
    var det = h("details", "tq-table", null, el);
    h("summary", null, "Voir les valeurs", det);
    var t = h("table", null, null, det), tb = h("tbody", null, null, t);
    pts.forEach(function (p) {
      var tr = h("tr", null, null, tb);
      h("td", null, String(p.annee), tr); h("td", "num", avecUnite(p.valeur, d.unite), tr);
    });
  }

  /* ---------------------------------------------------------- haltères coûts projets */
  function haltere(el) {
    var d = donnees(el);
    if (!d || !d.length) return;
    var lignes = d.filter(function (p) { return p.initial != null && p.actuel != null; });
    if (!lignes.length) return;
    lignes.sort(function (a, b) { return (b.actuel / b.initial) - (a.actuel / a.initial); });
    var max = Math.max.apply(null, lignes.map(function (p) { return Math.max(p.initial, p.actuel); }));
    // Nom au-dessus de chaque haltère : lisible même sur un téléphone.
    var W = 440, L = 8, D = 64, pas = 50, H = lignes.length * pas + 30;
    var s = svg("svg", { viewBox: "0 0 " + W + " " + H, role: "img",
      "aria-label": "Coût annoncé et coût actuel des grands projets publics" }, null);
    function X(v) { return L + (W - L - D) * v / max; }
    [0, 0.5, 1].forEach(function (f) {
      var v = max * f;
      svg("line", { x1: X(v), x2: X(v), y1: 4, y2: H - 22, stroke: GRILLE, "stroke-width": 1 }, s);
      svg("text", { x: X(v), y: H - 6, "text-anchor": f === 0 ? "start" : "middle", class: "ig-note" }, s).textContent = nf(v, 1) + " G$";
    });
    lignes.forEach(function (p, i) {
      var y = 34 + i * pas;
      var g = svg("g", { tabindex: 0, class: "tq-marque" }, s);
      svg("rect", { x: 0, y: y - 30, width: W, height: pas, fill: "transparent" }, g);
      svg("text", { x: L, y: y - 13, class: "ig-label" }, g).textContent = p.nom;
      svg("line", { x1: X(p.initial), x2: X(p.actuel), y1: y, y2: y, stroke: "#c8d2dc", "stroke-width": 4, "stroke-linecap": "round" }, g);
      svg("circle", { cx: X(p.initial), cy: y, r: 6, fill: GRIS_MARQUE, stroke: SURFACE, "stroke-width": 2 }, g);
      svg("circle", { cx: X(p.actuel), cy: y, r: 6, fill: BLEU, stroke: SURFACE, "stroke-width": 2 }, g);
      var ratio = p.actuel / p.initial;
      svg("text", { x: Math.max(X(p.actuel), X(p.initial)) + 11, y: y + 4, class: "ig-sub" }, g).textContent =
        ratio >= 1.05 ? "×" + nf(ratio, 1) : (ratio <= 0.95 ? "−" + nf((1 - ratio) * 100, 0) + " %" : "stable");
      function montrer(ev) {
        var r = ev.clientX ? ev : g.getBoundingClientRect();
        infobulle(r.clientX || r.left, r.clientY || r.top,
          [nf(p.initial, 2) + " G$ → " + nf(p.actuel, 2) + " G$", p.nom, p.note || ""].filter(Boolean));
      }
      g.addEventListener("pointermove", montrer);
      g.addEventListener("focus", montrer);
      g.addEventListener("pointerleave", cacherBulle);
      g.addEventListener("blur", cacherBulle);
    });
    var fig = h("div", "ig-scroll", null, null);
    fig.appendChild(s);
    el.insertBefore(fig, el.firstChild);
  }

  /* ---------------------------------------------------------- quiz */
  function quiz(el) {
    var qs = donnees(el);
    if (!qs || !qs.length) return;
    var ordre = melanger(qs.slice()).slice(0, el.dataset.nombre ? +el.dataset.nombre : 8);
    var i = 0, points = 0;
    var zone = h("div", "tq-quiz", null, el);

    function ecran() {
      zone.textContent = "";
      if (i >= ordre.length) return fin();
      var q = ordre[i];
      h("div", "tq-progres", "Question " + (i + 1) + " sur " + ordre.length, zone);
      var barre = h("div", "tq-barre-progres", null, zone);
      h("div", null, null, barre).style.width = (100 * i / ordre.length) + "%";
      h("h3", null, q.question, zone);
      if (q.contexte) h("p", "detail", q.contexte, zone);
      var val = h("div", "tq-valeur-choisie", null, zone);
      var r = h("input", null, null, zone);
      r.type = "range"; r.min = q.min; r.max = q.max; r.step = q.pas || 1;
      r.value = (q.min + q.max) / 2;
      r.setAttribute("aria-label", "Votre estimation");
      var bornes = h("div", "tq-bornes", null, zone);
      h("span", null, avecUnite(q.min, q.unite), bornes); h("span", null, avecUnite(q.max, q.unite), bornes);
      function maj() { val.textContent = "Votre estimation : " + avecUnite(+r.value, q.unite); }
      r.addEventListener("input", maj); maj();
      var b = h("button", "tq-bouton", "Valider", zone);
      b.addEventListener("click", function () { reveler(q, +r.value); });
    }

    function reveler(q, choix) {
      var etendue = q.max - q.min;
      var ecart = Math.abs(choix - q.reponse) / etendue;
      var gain = ecart <= 0.05 ? 3 : ecart <= 0.15 ? 2 : ecart <= 0.3 ? 1 : 0;
      points += gain;
      zone.textContent = "";
      h("div", "tq-progres", "Question " + (i + 1) + " sur " + ordre.length, zone);
      h("h3", null, q.question, zone);
      // échelle : votre estimation vs la réalité
      var ech = h("div", "tq-echelle", null, zone);
      var pv = h("div", "tq-repere tq-repere-vous", null, ech);
      pv.style.left = (100 * (choix - q.min) / etendue) + "%";
      h("span", null, "Vous : " + avecUnite(choix, q.unite), pv);
      var pr = h("div", "tq-repere tq-repere-vrai", null, ech);
      pr.style.left = (100 * (q.reponse - q.min) / etendue) + "%";
      h("span", null, "Réalité : " + avecUnite(q.reponse, q.unite), pr);
      var verdict = ["Loin du compte", "Pas mal", "Très proche", "Dans le mille"][gain];
      h("p", "tq-verdict tq-gain-" + gain, verdict + (gain ? " · +" + gain + " point" + (gain > 1 ? "s" : "") : ""), zone);
      h("p", null, q.explication, zone);
      var src = h("p", "source", "Source : ", zone);
      var a = h("a", null, q.source_nom, src); a.href = q.source_url;
      if (q.secteur) {
        var l = h("p", null, null, zone), a2 = h("a", null, "Comprendre ce secteur →", l);
        a2.href = (window.TQ_BASE || "") + "/secteurs/" + q.secteur;
      }
      var b = h("button", "tq-bouton", i + 1 < ordre.length ? "Question suivante" : "Voir mon résultat", zone);
      b.addEventListener("click", function () { i++; ecran(); });
      b.focus();
    }

    function fin() {
      var max = ordre.length * 3, pct = Math.round(100 * points / max);
      marquer("quiz");
      zone.textContent = "";
      h("div", "tq-progres", "Résultat", zone);
      h("div", "tq-score", pct + " %", zone);
      h("p", null, pct >= 70 ? "Vous connaissez très bien le Québec. Rares sont ceux qui font mieux."
        : pct >= 40 ? "Une bonne intuition, avec quelques surprises. C'est le cas de la plupart des gens."
        : "Beaucoup de surprises? Vous n'êtes pas seul : ces chiffres sont rarement expliqués. Les pages Secteurs sont là pour ça.", zone);
      var b = h("button", "tq-bouton", "Rejouer avec d'autres questions", zone);
      b.addEventListener("click", function () { ordre = melanger(qs.slice()).slice(0, ordre.length); i = 0; points = 0; ecran(); });
      majParcours();
    }
    ecran();
  }

  /* ---------------------------------------------------------- comparateur à l'aveugle */
  function aveugle(el) {
    var d = donnees(el);
    if (!d || !d.themes || !d.themes.length) return;
    var themes = d.themes.map(function (t) {
      return { nom: t.nom, question: t.question, options: melanger(t.options.slice()) };
    });
    var i = 0, choix = [];
    var zone = h("div", "tq-quiz", null, el);

    function ecran() {
      zone.textContent = "";
      if (i >= themes.length) return fin();
      var t = themes[i];
      h("div", "tq-progres", "Thème " + (i + 1) + " sur " + themes.length + " · " + t.nom, zone);
      var barre = h("div", "tq-barre-progres", null, zone);
      h("div", null, null, barre).style.width = (100 * i / themes.length) + "%";
      h("h3", null, t.question || "Quelle proposition vous semble la meilleure?", zone);
      h("p", "detail", "Les partis sont masqués et l'ordre est mélangé à chaque partie.", zone);
      var liste = h("div", "tq-options", null, zone);
      t.options.forEach(function (o) {
        var b = h("button", "tq-option", o.texte, liste);
        b.addEventListener("click", function () { choix.push({ theme: t.nom, option: o }); i++; ecran(); });
      });
      var passer = h("button", "tq-lien", "Aucune ne me convient, passer", zone);
      passer.addEventListener("click", function () { choix.push({ theme: t.nom, option: null }); i++; ecran(); });
    }

    function fin() {
      marquer("aveugle");
      zone.textContent = "";
      h("div", "tq-progres", "Révélation", zone);
      var compte = {};
      choix.forEach(function (c) { if (c.option) compte[c.option.parti] = (compte[c.option.parti] || 0) + 1; });
      var total = choix.filter(function (c) { return c.option; }).length || 1;
      h("h3", null, "Les propositions que vous avez choisies venaient de…", zone);
      var g = h("div", "graphique", null, zone);
      Object.keys(d.partis).sort(function (a, b) { return (compte[b] || 0) - (compte[a] || 0); }).forEach(function (p) {
        var n = compte[p] || 0;
        var ln = h("div", "ligne-graphique", null, g);
        h("div", "etiquette-barre", d.partis[p], ln);
        var piste = h("div", "piste", null, ln);
        var bar = h("div", "barre-h", null, piste); bar.style.width = Math.max(0.5, 100 * n / total) + "%";
        h("span", "valeur-barre", n + " choix", piste);
      });
      var det = h("div", "tq-detail-choix", null, zone);
      choix.forEach(function (c) {
        var p = h("p", null, null, det);
        h("strong", null, c.theme + " : ", p);
        p.appendChild(document.createTextNode(c.option ? d.partis[c.option.parti] + ". « " + c.option.texte + " »" : "aucun choix"));
      });
      h("p", "note-verif", "Ceci n'est pas une recommandation de vote. Une proposition par parti et par thème, choisie parmi ses engagements principaux, ne résume pas une plateforme. Consultez le comparateur complet avant de vous faire une idée.", zone);
      var b = h("button", "tq-bouton", "Recommencer", zone);
      b.addEventListener("click", function () { i = 0; choix = []; themes.forEach(function (t) { melanger(t.options); }); ecran(); });
      majParcours();
    }
    ecran();
  }

  /* ---------------------------------------------------------- simulateur budgétaire */
  function budget(el) {
    var d = donnees(el);
    if (!d || !d.missions) return;
    var zone = h("div", "tq-budget", null, el);
    var gauche = h("div", "tq-budget-curseurs", null, zone);
    var droite = h("div", "tq-budget-bilan", null, zone);
    var etat = d.missions.map(function () { return 0; });
    var etatRev = 0;

    d.missions.forEach(function (mi, k) {
      if (mi.fixe) {
        var fixe = h("div", "tq-curseur", null, gauche);
        var t = h("div", "tq-curseur-tete", null, fixe);
        h("strong", null, mi.nom, t);
        h("span", "tq-curseur-val", nf(mi.montant, 1) + " G$", t);
        h("div", "detail", "Non modifiable : ce sont les intérêts sur la dette déjà contractée.", fixe);
        return;
      }
      var bloc = h("div", "tq-curseur", null, gauche);
      var tete = h("div", "tq-curseur-tete", null, bloc);
      h("strong", null, mi.nom, tete);
      var v = h("span", "tq-curseur-val", null, tete);
      var r = h("input", null, null, bloc);
      r.type = "range"; r.min = -10; r.max = 10; r.step = 1; r.value = 0;
      r.setAttribute("aria-label", "Variation du budget : " + mi.nom);
      h("div", "detail", "Budget actuel : " + nf(mi.montant, 1) + " G$" + (mi.exemple ? " · " + mi.exemple : ""), bloc);
      function maj() {
        etat[k] = +r.value;
        var delta = mi.montant * etat[k] / 100;
        v.textContent = (etat[k] > 0 ? "+" : "") + etat[k] + " % (" + (delta >= 0 ? "+" : "") + nf(delta, 2) + " G$)";
        bilan();
      }
      r.addEventListener("input", maj); maj.call();
    });
    if (d.revenus) {
      var bloc = h("div", "tq-curseur tq-curseur-revenus", null, gauche);
      var tete = h("div", "tq-curseur-tete", null, bloc);
      h("strong", null, "Impôts et taxes", tete);
      var v = h("span", "tq-curseur-val", null, tete);
      var r = h("input", null, null, bloc);
      r.type = "range"; r.min = -10; r.max = 10; r.step = 1; r.value = 0;
      r.setAttribute("aria-label", "Variation des impôts et taxes");
      h("div", "detail", "Revenus autonomes actuels : " + nf(d.revenus.montant, 1) + " G$", bloc);
      r.addEventListener("input", function () {
        etatRev = +r.value;
        var delta = d.revenus.montant * etatRev / 100;
        v.textContent = (etatRev > 0 ? "+" : "") + etatRev + " % (" + (delta >= 0 ? "+" : "") + nf(delta, 2) + " G$)";
        bilan();
      });
      v.textContent = "0 %";
    }

    function bilan() {
      droite.textContent = "";
      var depDelta = d.missions.reduce(function (s, mi, k) { return s + mi.montant * etat[k] / 100; }, 0);
      var revDelta = d.revenus ? d.revenus.montant * etatRev / 100 : 0;
      var solde = d.solde + revDelta - depDelta;
      h("div", "surtitre", "Votre budget", droite);
      var c = h("div", "tq-solde " + (solde >= 0 ? "tq-surplus" : "tq-deficit"), null, droite);
      h("div", "tq-solde-chiffre", (solde >= 0 ? "Surplus de " : "Déficit de ") + nf(Math.abs(solde), 1) + " G$", c);
      h("div", "detail", "Point de départ : " + (d.solde >= 0 ? "surplus" : "déficit") + " de " + nf(Math.abs(d.solde), 1) + " G$ (" + d.annee + ")", c);
      var parPers = (depDelta - revDelta) * 1e9 / d.population;
      h("p", null, Math.abs(parPers) < 1 ? "Vos choix ne changent rien au solde pour l'instant."
        : "Vos choix " + (parPers > 0 ? "coûtent" : "économisent") + " environ " + nf(Math.abs(parPers), 0) + " $ par Québécois par année.", droite);
      if (d.equivalences && Math.abs(depDelta) >= 0.05) {
        h("div", "surtitre", Math.abs(depDelta) >= 0.05 ? (depDelta > 0 ? "Ce que représentent vos ajouts" : "Ce que représentent vos coupes") : "", droite);
        var ul = h("ul", "tq-equivalences", null, droite);
        d.equivalences.forEach(function (e) {
          var n = Math.abs(depDelta) * 1e9 / e.cout_unitaire;
          var li = h("li", null, null, ul);
          h("strong", null, nf(n, 0) + " ", li);
          li.appendChild(document.createTextNode(e.libelle + " "));
          var a = h("a", "source", "(source)", li); a.href = e.source_url;
        });
      }
      if (solde < 0 && d.solde < 0 && solde < d.solde) {
        h("p", "piege", "Un déficit plus gros s'ajoute à la dette : il faudra le rembourser plus tard, avec intérêts.", droite);
      }
      marquer("budget");
    }
    bilan();
  }

  /* ---------------------------------------------------------- parcours « Électeur éclairé » */
  var ETAPES = [
    { cle: "page:/election", nom: "Explorer la section Élection" },
    { cle: "page:/election/comparateur", nom: "Consulter le comparateur des partis" },
    { cle: "page:/secteurs/", nom: "Lire la fiche d'un secteur" },
    { cle: "page:/lois-et-projets", nom: "Voir les lois et les grands projets" },
    { cle: "page:/election/decoder", nom: "Décoder la campagne" },
    { cle: "priorites", nom: "Choisir mes priorités" },
    { cle: "indice", nom: "Régler ma note du Québec" },
    { cle: "quiz", nom: "Jouer à « Devinez le chiffre »" },
    { cle: "aveugle", nom: "Faire le comparateur à l'aveugle" },
    { cle: "budget", nom: "Jouer au ministre des Finances" },
    { cle: "page:/quebec-prospere", nom: "Lire la capsule Québec prospère" }
  ];
  function majParcours() {
    // En mode prudent (période électorale), les étapes qui présentent les
    // partis sont retirées du parcours.
    var etapes = window.TQ_PRUDENT ? ETAPES.filter(function (e) {
      return e.cle !== "aveugle" && e.cle !== "page:/election/comparateur";
    }) : ETAPES;
    document.querySelectorAll("[data-parcours]").forEach(function (el) {
      var p = lireParcours();
      var faits = etapes.filter(function (e) {
        return Object.keys(p).some(function (k) { return k === e.cle || (e.cle.indexOf("page:") === 0 && k.indexOf(e.cle) === 0); });
      }).map(function (e) { return e.cle; });
      el.textContent = "";
      var tete = h("div", "tq-parcours-tete", null, el);
      h("strong", null, "Votre parcours d'électeur éclairé", tete);
      h("span", null, faits.length + " / " + etapes.length, tete);
      var barre = h("div", "tq-barre-progres", null, el);
      h("div", null, null, barre).style.width = (100 * faits.length / etapes.length) + "%";
      var ul = h("ul", "tq-etapes", null, el);
      etapes.forEach(function (e) {
        h("li", faits.indexOf(e.cle) >= 0 ? "fait" : "", e.nom, ul);
      });
      if (faits.length === etapes.length) {
        h("p", "tq-badge-final", "Badge obtenu : Électeur éclairé. Il ne reste plus qu'à voter le 5 octobre.", el);
      }
      h("p", "detail", "Votre progression reste dans votre navigateur. Elle n'est jamais envoyée nulle part.", el);
    });
  }

  /* ---------------------------------------------------------- l'état du Québec */
  function indice(el) {
    var d = donnees(el);
    if (!d) return;
    var poids = {};
    d.secteurs.forEach(function (s) { poids[s.slug] = s.poids; });
    try {
      var garde = JSON.parse(localStorage.getItem("tq-poids") || "null");
      if (garde) d.secteurs.forEach(function (s) {
        if (typeof garde[s.slug] === "number") poids[s.slug] = garde[s.slug];
      });
    } catch (e) { /* ignoré */ }

    var zone = h("div", "indice", null, el);
    var tete = h("div", "indice-tete", null, zone);
    var bloc = h("div", "indice-note", null, tete);
    var chiffre = h("div", "indice-chiffre", null, bloc);
    var libelle = h("div", "indice-libelle", null, bloc);
    var jauge = h("div", "indice-anneau", null, tete);
    var resume = h("p", "indice-resume", null, tete);

    var grille = h("div", "indice-secteurs", null, zone);
    var reglages = h("details", "indice-reglages", null, zone);
    h("summary", null, "Régler l'importance de chaque secteur", reglages);
    h("p", "detail", d.reglages.note_poids, reglages);
    var curseurs = h("div", "indice-curseurs", null, reglages);

    function qualite(n) {
      return n >= 75 ? "bon" : n >= 55 ? "moyen" : n >= 40 ? "faible" : "mauvais";
    }

    function calculer() {
      var total = 0, somme = 0;
      d.secteurs.forEach(function (s) { total += poids[s.slug]; somme += s.note * poids[s.slug]; });
      var note = total ? somme / total : 0;
      chiffre.textContent = nf(note, 1);
      libelle.textContent = "sur 100";
      jauge.style.setProperty("--part", note + "%");
      jauge.dataset.qualite = qualite(note);
      resume.textContent = "Moyenne pondérée de " + d.secteurs.length + " secteurs et "
        + d.nb_indicateurs + " indicateurs sourcés. Réglez les pondérations : la note est la vôtre.";

      grille.textContent = "";
      d.secteurs.slice().sort(function (a, b) { return b.note - a.note; }).forEach(function (s) {
        var c = h("a", "indice-secteur", null, grille);
        c.href = (window.TQ_BASE || "") + "/secteurs/" + s.slug;
        c.dataset.qualite = qualite(s.note);
        var t = h("div", "indice-secteur-tete", null, c);
        h("span", null, s.nom, t);
        h("strong", null, nf(s.note, 0), t);
        var rail = h("div", "rail", null, c);
        h("div", "jauge-note", null, rail).style.width = s.note + "%";
        var bas = h("div", "indice-secteur-bas", null, c);
        h("span", null, "poids " + poids[s.slug] + " %", bas);
        if (s.tendance !== null && s.tendance !== undefined) {
          var fleche = s.tendance > 1 ? "▲" : s.tendance < -1 ? "▼" : "→";
          var e = h("span", "tendance tendance-" + (s.tendance > 1 ? "haut" : s.tendance < -1 ? "bas" : "stable"), null, bas);
          e.textContent = fleche + " " + (s.tendance > 0 ? "+" : "") + nf(s.tendance, 1) + " pt"
            + (s.depuis ? " depuis " + s.depuis : "");
          e.title = "Évolution de la note des indicateurs qui ont une série historique";
        }
      });
    }

    d.secteurs.forEach(function (s) {
      var l = h("label", "indice-curseur", null, curseurs);
      var t = h("span", null, s.nom, l);
      var v = h("span", "indice-curseur-val", null, l);
      var r = h("input", null, null, l);
      r.type = "range"; r.min = 0; r.max = 30; r.step = 1; r.value = poids[s.slug];
      r.setAttribute("aria-label", "Importance du secteur " + s.nom);
      function maj() {
        poids[s.slug] = +r.value;
        v.textContent = r.value + " %";
        try { localStorage.setItem("tq-poids", JSON.stringify(poids)); } catch (e) { /* ignoré */ }
        marquer("indice");
        calculer();
      }
      r.addEventListener("input", maj);
      v.textContent = poids[s.slug] + " %";
    });

    var remise = h("button", "tq-lien", "Revenir à la pondération par défaut", reglages);
    remise.addEventListener("click", function () {
      d.secteurs.forEach(function (s) { poids[s.slug] = s.poids; });
      try { localStorage.removeItem("tq-poids"); } catch (e) { /* ignoré */ }
      curseurs.querySelectorAll("input").forEach(function (r, n) { r.value = d.secteurs[n].poids; });
      curseurs.querySelectorAll(".indice-curseur-val").forEach(function (v, n) {
        v.textContent = d.secteurs[n].poids + " %";
      });
      calculer();
    });

    calculer();
  }

  /* ---------------------------------------------------------- vos priorités */
  function priorites(el) {
    var d = donnees(el);
    if (!d || !d.length) return;
    var choisis = [];
    var zone = h("div", null, null, el);
    var choix = h("div", "tq-priorites", null, zone);
    var resultat = h("div", null, null, zone);

    d.forEach(function (s) {
      var b = h("button", "tq-priorite", s.nom, choix);
      b.addEventListener("click", function () {
        var i = choisis.indexOf(s.slug);
        if (i >= 0) { choisis.splice(i, 1); }
        else if (choisis.length < 3) { choisis.push(s.slug); }
        else { return; }
        b.classList.toggle("choisi", i < 0);
        afficher();
      });
    });
    var aide = h("p", "detail", "Jusqu'à trois sujets.", zone);

    function afficher() {
      resultat.textContent = "";
      aide.textContent = choisis.length >= 3
        ? "Trois sujets choisis. Retirez-en un pour en ajouter un autre."
        : "Jusqu'à trois sujets. " + (3 - choisis.length) + " restant(s).";
      if (!choisis.length) return;
      marquer("priorites");
      choisis.forEach(function (slug) {
        var s = d.filter(function (x) { return x.slug === slug; })[0];
        var c = h("div", "carte tq-fiche-priorite", null, resultat);
        var t = h("h3", null, s.nom, c);
        h("p", null, s.accroche, c);
        if (s.budget) h("p", "detail", "Budget : " + s.budget, c);
        if (s.kpis.length) {
          h("div", "surtitre", "L'état des lieux", c);
          var ul = h("ul", "tq-kpis-priorite", null, c);
          s.kpis.forEach(function (k) {
            var li = h("li", null, null, ul);
            h("strong", null, k.valeur + " ", li);
            li.appendChild(document.createTextNode(k.nom + (k.annee ? " (" + k.annee + ")" : "")));
            if (k.comparaison) h("span", "detail", " · " + k.comparaison, li);
          });
        }
        if (s.question) {
          h("div", "surtitre", "La question de fond", c);
          h("p", null, s.question, c);
        }
        if (s.levier) {
          h("div", "surtitre", "Ce que dit la recherche", c);
          var p = h("p", null, null, c);
          h("span", "badge delai-" + s.levier.delai,
            { court: "Effet en moins de 2 ans", moyen: "Effet en 2 à 10 ans", long: "Effet après 10 ans" }[s.levier.delai], p);
          p.appendChild(document.createTextNode(" " + s.levier.effet));
        }
        var liens = h("p", null, null, c);
        var a1 = h("a", null, "Voir la fiche complète du secteur →", liens);
        a1.href = (window.TQ_BASE || "") + "/secteurs/" + s.slug;
      });
      if (!window.TQ_PRUDENT) {
        var note = h("p", "note-verif", "Comparez ensuite ce que proposent les partis sur ces sujets : ", resultat);
        var a = h("a", null, "ouvrir le comparateur", note);
        a.href = (window.TQ_BASE || "") + "/election/comparateur/";
      }
    }
    afficher();
  }

  /* ---------------------------------------------------------- convertisseur d'inflation */
  function inflation(el) {
    var d = donnees(el);
    if (!d || !d.indice) return;
    var annees = Object.keys(d.indice).sort();
    var ref = d.annee_reference;

    var l1 = h("div", "conv-ligne", null, el);
    var champ = h("input", "conv-montant", null, l1);
    champ.type = "number"; champ.value = 100; champ.min = 0; champ.step = 10;
    champ.setAttribute("aria-label", "Montant en dollars");
    h("span", null, "$ en", l1);
    var select = h("select", "conv-annee", null, l1);
    annees.forEach(function (a) {
      var o = h("option", null, a, select);
      o.value = a;
      if (a === "2015") o.selected = true;
    });
    h("span", null, "valent aujourd'hui", l1);

    var res = h("div", "conv-resultat", null, el);
    var note = h("p", "detail", null, el);

    function calculer() {
      var a = select.value, m = parseFloat(champ.value || 0);
      var v = m * d.indice[ref] / d.indice[a];
      res.textContent = nf(v, 2) + " $";
      var hausse = 100 * (d.indice[ref] / d.indice[a] - 1);
      note.textContent = "Les prix ont augmenté de " + nf(hausse, 1) + " % entre "
        + a + " et " + ref + ". Autrement dit, " + nf(m, 0) + " $ de " + ref
        + " valaient " + nf(m * d.indice[a] / d.indice[ref], 2) + " $ en " + a + ".";
    }
    champ.addEventListener("input", calculer);
    select.addEventListener("change", calculer);
    calculer();
  }

  /* ---------------------------------------------------------- FAQ « On clarifie » */
  // Tracker des promesses : filtre par statut. Le compte reste visible pour
  // qu'on voie tout de suite combien de promesses chaque statut couvre.
  function promesses() {
    var lignes = document.querySelectorAll("[data-promesse]");
    var onglets = document.querySelectorAll("[data-promesses-filtres] a");
    onglets.forEach(function (o) {
      o.addEventListener("click", function (e) {
        e.preventDefault();
        var cible = o.dataset.statut;
        onglets.forEach(function (x) { x.classList.toggle("actif", x === o); });
        lignes.forEach(function (l) {
          l.hidden = cible !== "toutes" && l.dataset.promesse !== cible;
        });
      });
    });
  }

  function faq(champ) {
    var questions = document.querySelectorAll("[data-faq]");
    var sections = document.querySelectorAll(".faq-categorie");
    var vide = document.querySelector("[data-faq-vide]");
    var onglets = document.querySelectorAll("[data-faq-categories] a");
    var categorie = "toutes";
    function norm(t) { return t.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase(); }

    function appliquer() {
      var q = norm((champ && champ.value || "").trim()), n = 0;
      questions.forEach(function (el) {
        var sec = el.closest(".faq-categorie");
        var ok = (!q || norm(el.dataset.faq).indexOf(q) >= 0)
              && (categorie === "toutes" || sec.dataset.cat === categorie);
        el.hidden = !ok;
        if (ok) n++;
        if (q && ok) el.open = true;
      });
      sections.forEach(function (sec) {
        sec.hidden = ![].some.call(sec.querySelectorAll("[data-faq]"), function (e) { return !e.hidden; });
      });
      if (vide) vide.hidden = n > 0;
    }
    if (champ) champ.addEventListener("input", appliquer);
    onglets.forEach(function (a) {
      a.addEventListener("click", function (ev) {
        ev.preventDefault();
        categorie = a.dataset.cat;
        onglets.forEach(function (x) { x.classList.toggle("actif", x === a); });
        marquer("faq");
        appliquer();
      });
    });
    appliquer();
  }

  /* ---------------------------------------------------------- filtre du lexique */
  function lexique(champ) {
    var termes = document.querySelectorAll("[data-terme]");
    var vide = document.querySelector("[data-lexique-vide]");
    function norm(t) { return t.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase(); }
    champ.addEventListener("input", function () {
      var q = norm(champ.value.trim()), n = 0;
      termes.forEach(function (t) {
        var ok = !q || norm(t.dataset.terme).indexOf(q) >= 0;
        t.hidden = !ok; if (ok) n++;
      });
      if (vide) vide.hidden = n > 0;
    });
  }

  function init() {
    var chemin = location.pathname.replace(/^\/tracabilite-quebec/, "").replace(/\/$/, "") || "/";
    if (/^\/(election|secteurs|lois-et-projets|quebec-prospere|economie-expliquee|quebec-canada)/.test(chemin)) marquer("page:" + chemin);
    document.querySelectorAll("[data-graph-serie]").forEach(grapheSerie);
    document.querySelectorAll("[data-haltere]").forEach(haltere);
    document.querySelectorAll("[data-quiz]").forEach(quiz);
    document.querySelectorAll("[data-aveugle]").forEach(aveugle);
    document.querySelectorAll("[data-budget]").forEach(budget);
    document.querySelectorAll("[data-filtre-lexique]").forEach(lexique);
    document.querySelectorAll("[data-priorites]").forEach(priorites);
    document.querySelectorAll("[data-indice]").forEach(indice);
    document.querySelectorAll("[data-inflation]").forEach(inflation);
    if (document.querySelector("[data-faq]")) faq(document.querySelector("[data-filtre-faq]"));
    if (document.querySelector("[data-promesses-filtres]")) promesses();
    majParcours();
    // Sous-navigation : amener l'onglet actif dans la zone visible (téléphone).
    var actif = document.querySelector(".sous-nav a.actif");
    if (actif) {
      var zone = actif.parentElement;
      zone.scrollLeft = actif.offsetLeft - (zone.clientWidth - actif.offsetWidth) / 2;
    }
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
