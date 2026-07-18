"""Traçabilité Québec — explorateur des contrats publics du SEAO.

Application web en lecture seule sur la base data/seao.db produite par le
pipeline. Chaque page cite ses sources : lien vers l'avis officiel sur
seao.gouv.qc.ca et fichier de données ouvertes d'origine.
"""
import sqlite3
from pathlib import Path

from flask import Flask, abort, g, render_template, request

RACINE = Path(__file__).resolve().parent.parent
BASE = RACINE / "data" / "seao.db"

app = Flask(__name__)

TYPES_SIGNAUX = {
    "DEPASSEMENT": {
        "nom": "Dépassement de coût",
        "couleur": "rouge",
        "explication": (
            "La dépense finale déclarée au SEAO excède le montant octroyé. "
            "Explications possibles et fréquentes : élargissement de la portée "
            "des travaux, imprévus de chantier, prolongation, options exercées, "
            "indexation prévue au contrat — ou erreur de saisie. Un dépassement "
            "n'est pas une faute en soi : il mérite une explication."
        ),
    },
    "GRE_A_GRE": {
        "nom": "Gré à gré 100 k$ et plus",
        "couleur": "bleu",
        "explication": (
            "Contrat conclu sans appel d'offres ouvert au-dessus du seuil où un "
            "appel d'offres public est normalement attendu. La loi prévoit des "
            "exceptions légitimes : fournisseur unique, urgence, sécurité, "
            "services professionnels particuliers. Le signal indique seulement "
            "que le mécanisme concurrentiel habituel n'a pas été utilisé."
        ),
    },
    "SOUM_UNIQUE": {
        "nom": "Soumissionnaire unique",
        "couleur": "violet",
        "explication": (
            "Un appel d'offres ouvert a été publié, mais une seule entreprise a "
            "soumissionné. Explications possibles : marché très spécialisé, "
            "région éloignée, exigences restrictives, délais courts. Un taux "
            "élevé de soumissionnaires uniques chez un organisme peut indiquer "
            "des devis mal calibrés — ou un marché peu concurrentiel."
        ),
    },
    "AVENANTS_SERIE": {
        "nom": "Avenants en série",
        "couleur": "jaune",
        "explication": (
            "Trois modifications ou plus au contrat initial. Les avenants sont "
            "un mécanisme normal et légal; leur multiplication peut toutefois "
            "signaler une planification initiale déficiente ou un contrat dont "
            "la portée réelle diffère de ce qui a été mis en concurrence."
        ),
    },
    "ABERRATION": {
        "nom": "Donnée aberrante",
        "couleur": "gris",
        "explication": (
            "Le ratio entre la dépense finale et le montant octroyé est "
            "invraisemblable (plus de 20×). Dans la quasi-totalité des cas, il "
            "s'agit d'une erreur de saisie dans les données sources du SEAO. "
            "Nous le signalons comme un problème de qualité de données, pas "
            "comme un dépassement réel."
        ),
    },
}


# Segments UNSPSC (2 premiers chiffres du code) — libellés français abrégés.
SEGMENTS_UNSPSC = {
    "22": "Équipement de construction",
    "23": "Équipement industriel",
    "24": "Manutention et entreposage",
    "25": "Véhicules et transport",
    "26": "Machines de production d'énergie",
    "27": "Outils et machinerie",
    "30": "Matériaux de construction",
    "31": "Pièces et composants",
    "32": "Composants électroniques",
    "39": "Électricité et éclairage",
    "40": "Chauffage, ventilation, plomberie",
    "41": "Équipement de laboratoire et mesure",
    "42": "Équipement et fournitures médicales",
    "43": "Technologies de l'information",
    "44": "Équipement de bureau",
    "45": "Imprimerie, photo, audiovisuel",
    "46": "Sécurité et défense",
    "47": "Nettoyage et entretien",
    "48": "Équipement de restauration et service",
    "49": "Sports et loisirs",
    "50": "Alimentation",
    "51": "Médicaments et produits pharmaceutiques",
    "52": "Ameublement et articles domestiques",
    "53": "Vêtements et articles personnels",
    "55": "Publications et médias imprimés",
    "56": "Mobilier",
    "60": "Musique, arts, éducation (matériel)",
    "70": "Agriculture, pêche, foresterie",
    "71": "Forage et exploitation minière",
    "72": "Construction et entretien de bâtiments",
    "73": "Production industrielle (services)",
    "76": "Nettoyage industriel (services)",
    "77": "Services environnementaux",
    "78": "Transport, entreposage, courrier",
    "80": "Services professionnels et de gestion",
    "81": "Ingénierie, recherche, technologie",
    "82": "Éditique, design, arts (services)",
    "83": "Services publics et télécommunications",
    "84": "Services financiers et assurances",
    "85": "Services de santé",
    "86": "Éducation et formation",
    "90": "Restauration, hébergement, tourisme",
    "91": "Services personnels et domestiques",
    "92": "Sécurité publique",
    "93": "Services politiques et civils",
    "94": "Organisations et associations",
    "95": "Terrains, bâtiments (location/achat)",
}


def db():
    if "db" not in g:
        g.db = sqlite3.connect(BASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def fermer_db(exc):
    d = g.pop("db", None)
    if d is not None:
        d.close()


MOIS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
           "août", "septembre", "octobre", "novembre", "décembre"]


@app.context_processor
def injecter_derniere_maj():
    """Date et heure de la dernière mise à jour des données (horodatage de la
    base), affichées dans l'en-tête de la version démo."""
    from datetime import datetime
    t = datetime.fromtimestamp(BASE.stat().st_mtime)
    return {"derniere_maj":
            f"{t.day} {MOIS_FR[t.month - 1]} {t.year}, {t.hour} h {t.minute:02d}"}


_cache_stats = {}


def cache_selon_base(fn):
    """Met en cache le résultat tant que data/seao.db n'a pas changé.
    Après une mise à jour nocturne des données, le cache se rafraîchit seul."""
    def enveloppe():
        mtime = BASE.stat().st_mtime
        entree = _cache_stats.get(fn.__name__)
        if entree is None or entree[0] != mtime:
            _cache_stats[fn.__name__] = (mtime, fn())
        return _cache_stats[fn.__name__][1]
    enveloppe.__name__ = fn.__name__
    return enveloppe


@app.template_filter("montant")
def f_montant(v):
    if v is None:
        return "—"
    if v >= 1e9:
        return f"{v / 1e9:,.2f} G$".replace(",", " ").replace(".", ",")
    if v >= 1e6:
        return f"{v / 1e6:,.2f} M$".replace(",", " ").replace(".", ",")
    return f"{v:,.0f} $".replace(",", " ")


@app.template_filter("nombre")
def f_nombre(v):
    return f"{v:,.0f}".replace(",", " ") if v is not None else "—"


@app.template_filter("datefr")
def f_datefr(v):
    return v[:10] if v else "—"


@cache_selon_base
def stats_globales():
    cur = db()
    s = {}
    s["nb_processus"] = cur.execute("SELECT COUNT(*) FROM processus").fetchone()[0]
    s["nb_octrois"], s["valeur_octrois"] = cur.execute(
        "SELECT COUNT(*), COALESCE(SUM(montant),0) FROM octroi WHERE montant > 0"
    ).fetchone()
    s["nb_gre_a_gre"], s["valeur_gre_a_gre"] = cur.execute(
        """SELECT COUNT(*), COALESCE(SUM(o.montant),0)
           FROM octroi o JOIN processus p ON p.ocid = o.ocid
           WHERE p.methode = 'direct' AND o.montant > 0"""
    ).fetchone()
    s["signaux"] = dict(cur.execute(
        "SELECT type, COUNT(*) FROM signal GROUP BY type").fetchall())
    s["periode"] = cur.execute(
        "SELECT MIN(nom), MAX(nom) FROM fichier_ingere").fetchone()
    s["nb_fichiers"] = cur.execute(
        "SELECT COUNT(*) FROM fichier_ingere").fetchone()[0]
    return s


@cache_selon_base
def stats_2026():
    """Portrait de l'année 2026 (octrois datés du 1er janvier 2026 ou après)."""
    cur = db()
    s = {}
    s["total"], s["nb"] = cur.execute("""
        SELECT COALESCE(SUM(montant),0), COUNT(*)
        FROM octroi WHERE date >= '2026-01-01' AND montant > 0
    """).fetchone()

    # Où va l'argent : par segment UNSPSC (catégorie d'achat)
    lignes = cur.execute("""
        SELECT substr(p.unspsc_id, 1, 2) AS seg, SUM(o.montant) AS v
        FROM octroi o JOIN processus p ON p.ocid = o.ocid
        WHERE o.date >= '2026-01-01' AND o.montant > 0
        GROUP BY seg ORDER BY v DESC
    """).fetchall()
    categories, autres = [], 0.0
    for seg, v in lignes:
        nom = SEGMENTS_UNSPSC.get(seg)
        if nom and len(categories) < 10:
            categories.append({"nom": nom, "valeur": v,
                               "pct": 100 * v / s["total"] if s["total"] else 0})
        else:
            autres += v
    if autres:
        categories.append({"nom": "Autres et non catégorisé", "valeur": autres,
                           "pct": 100 * autres / s["total"] if s["total"] else 0})
    s["categories"] = categories
    s["max_categorie"] = max((c["valeur"] for c in categories), default=1)

    # Par mode d'attribution (part de la valeur)
    modes = dict(cur.execute("""
        SELECT p.methode, SUM(o.montant)
        FROM octroi o JOIN processus p ON p.ocid = o.ocid
        WHERE o.date >= '2026-01-01' AND o.montant > 0
        GROUP BY p.methode
    """).fetchall())
    total_modes = sum(v for v in modes.values() if v) or 1
    s["modes"] = [
        {"nom": "Appel d'offres ouvert", "valeur": modes.get("open", 0) or 0,
         "classe": "mode-ouvert"},
        {"nom": "Sur invitation / sélectif",
         "valeur": (modes.get("limited", 0) or 0) + (modes.get("selective", 0) or 0),
         "classe": "mode-invitation"},
        {"nom": "Gré à gré", "valeur": modes.get("direct", 0) or 0,
         "classe": "mode-gre"},
    ]
    for m in s["modes"]:
        m["pct"] = 100 * m["valeur"] / total_modes

    # Les plus grands acheteurs de 2026
    s["organismes"] = cur.execute("""
        SELECT p.acheteur_nom AS nom, SUM(o.montant) AS valeur, COUNT(*) AS nb
        FROM octroi o JOIN processus p ON p.ocid = o.ocid
        WHERE o.date >= '2026-01-01' AND o.montant > 0
        GROUP BY p.acheteur_nom ORDER BY valeur DESC LIMIT 8
    """).fetchall()

    # Ce qui va bien
    s["fournisseurs_distincts"] = cur.execute("""
        SELECT COUNT(DISTINCT COALESCE(fournisseur_neq, fournisseur_nom))
        FROM octroi WHERE date >= '2026-01-01' AND montant > 0
    """).fetchone()[0]
    s["soumissions_moyennes"] = cur.execute("""
        SELECT AVG(nb_soumissionnaires) FROM processus
        WHERE methode = 'open' AND nb_soumissionnaires > 0
          AND ocid IN (SELECT DISTINCT ocid FROM octroi
                       WHERE date >= '2026-01-01' AND montant > 0)
    """).fetchone()[0] or 0
    s["respect_budget"], s["termines_comparables"] = cur.execute("""
        SELECT SUM(CASE WHEN c.montant <= o.montant * 1.005 THEN 1 ELSE 0 END),
               COUNT(*)
        FROM contrat c
        JOIN octroi o ON o.ocid = c.ocid AND o.octroi_id = c.octroi_id
        WHERE c.statut = 'terminated' AND o.montant >= 25000 AND c.montant > 0
    """).fetchone()
    return s


@cache_selon_base
def stats_reperes():
    """Indicateurs observés vs repères de saine gouvernance contractuelle.

    Les repères proviennent de références publiques (tableau de bord du marché
    unique de la Commission européenne, recommandations OCDE). Quand aucun
    repère officiel n'existe, on le dit — on n'invente pas de norme.
    """
    cur = db()
    a = stats_2026()

    seul, ao_connus = cur.execute("""
        SELECT SUM(CASE WHEN nb_soumissionnaires = 1 THEN 1 ELSE 0 END), COUNT(*)
        FROM processus WHERE methode = 'open' AND nb_soumissionnaires > 0
    """).fetchone()
    pct_soum_unique = 100 * seul / ao_connus if ao_connus else 0

    dep25, comparables = cur.execute("""
        SELECT SUM(CASE WHEN c.montant > o.montant * 1.25
                         AND c.montant <= o.montant * 20 THEN 1 ELSE 0 END),
               COUNT(*)
        FROM contrat c
        JOIN octroi o ON o.ocid = c.ocid AND o.octroi_id = c.octroi_id
        WHERE c.statut = 'terminated' AND o.montant >= 25000 AND c.montant > 0
    """).fetchone()
    pct_dep25 = 100 * dep25 / comparables if comparables else 0
    pct_budget = (100 * a["respect_budget"] / a["termines_comparables"]
                  if a["termines_comparables"] else 0)

    def statut(valeur, vert, jaune, inverse=False):
        """vert/jaune sont des seuils; inverse=True quand plus petit = mieux."""
        if inverse:
            return "vert" if valeur < vert else ("jaune" if valeur < jaune else "rouge")
        return "vert" if valeur >= vert else ("jaune" if valeur >= jaune else "rouge")

    pct_gag = a["modes"][2]["pct"]
    pct_ouvert = a["modes"][0]["pct"]
    return [
        {
            "nom": "Part de la valeur attribuée par appel d'offres ouvert",
            "valeur": f"{pct_ouvert:.0f} %",
            "repere": "Le plus élevé possible — la concurrence devrait être la "
                      "règle, et le gré à gré l'exception justifiée.",
            "source": "Recommandation de l'OCDE sur les marchés publics (2015)",
            "statut": statut(pct_ouvert, 75, 50),
            "note": "Mesuré sur la valeur des octrois 2026.",
        },
        {
            "nom": "Part de la valeur attribuée de gré à gré",
            "valeur": f"{pct_gag:.0f} %",
            "repere": "Moins de 10 % : satisfaisant. Plus de 20 % : préoccupant.",
            "source": "Seuils du tableau de bord du marché unique, Commission "
                      "européenne (indicateur « procédures sans appel à la "
                      "concurrence »)",
            "statut": statut(pct_gag, 10, 20, inverse=True),
            "note": "Mesuré sur la valeur des octrois 2026. Des exceptions "
                    "légales existent (fournisseur unique, urgence).",
        },
        {
            "nom": "Appels d'offres ouverts n'attirant qu'un seul soumissionnaire",
            "valeur": f"{pct_soum_unique:.0f} %",
            "repere": "Moins de 10 % : satisfaisant. Plus de 20 % : préoccupant "
                      "— un appel d'offres sans concurrence n'en est pas "
                      "vraiment un.",
            "source": "Seuils du tableau de bord du marché unique, Commission "
                      "européenne (indicateur « soumissionnaire unique »)",
            "statut": statut(pct_soum_unique, 10, 20, inverse=True),
            "note": "Mesuré sur tous les appels d'offres ouverts de la période "
                    "où le nombre de soumissionnaires est publié.",
        },
        {
            "nom": "Nombre moyen de soumissionnaires par appel d'offres ouvert",
            "valeur": f"{a['soumissions_moyennes']:.1f}".replace(".", ","),
            "repere": "Au moins 3 : signe d'un marché réellement concurrentiel.",
            "source": "Indicateur de concurrence utilisé par la Commission "
                      "européenne et l'OCDE",
            "statut": statut(a["soumissions_moyennes"], 3, 2),
            "note": "",
        },
        {
            "nom": "Contrats terminés au montant prévu — ou moins",
            "valeur": f"{pct_budget:.0f} %",
            "repere": "Pas de norme officielle. Plus c'est élevé, mieux la "
                      "planification initiale reflétait le besoin réel.",
            "source": "Aucun repère officiel établi — nous le disons plutôt "
                      "que d'en inventer un",
            "statut": "gris",
            "note": "Les dépassements légitimes existent (imprévus, portée "
                    "élargie); l'enjeu est leur fréquence et leur ampleur.",
        },
        {
            "nom": "Contrats terminés avec dépassement de plus de 25 %",
            "valeur": f"{pct_dep25:.0f} %",
            "repere": "Pas de norme officielle. La recherche sur les grands "
                      "projets (Flyvbjerg) montre que les dépassements sont "
                      "fréquents partout — la question est de savoir s'ils "
                      "sont expliqués publiquement.",
            "source": "Aucun repère officiel établi",
            "statut": "gris",
            "note": "Erreurs de saisie évidentes exclues (ratio > 20).",
        },
    ]


def signaux_de(ocid):
    return db().execute(
        "SELECT * FROM signal WHERE ocid = ? ORDER BY gravite DESC", (ocid,)
    ).fetchall()


@app.route("/")
def accueil():
    cur = db()
    gros_depassements = cur.execute("""
        SELECT s.*, p.titre, p.acheteur_nom,
               (SELECT fournisseur_nom FROM octroi o WHERE o.ocid = s.ocid LIMIT 1)
               AS fournisseur
        FROM signal s JOIN processus p ON p.ocid = s.ocid
        WHERE s.type = 'DEPASSEMENT' AND s.montant_final >= 1000000
        ORDER BY (s.montant_final - s.montant_octroye) DESC LIMIT 5
    """).fetchall()
    return render_template("index.html", s=stats_globales(), a=stats_2026(),
                           depassements=gros_depassements,
                           types=TYPES_SIGNAUX)


@app.route("/recherche")
def recherche():
    q = request.args.get("q", "").strip()
    resultats = []
    if q:
        fts = " ".join(f'"{mot}"' for mot in q.split())
        resultats = db().execute("""
            SELECT p.*, (SELECT MAX(montant) FROM octroi o WHERE o.ocid = p.ocid)
                   AS montant,
                   (SELECT fournisseur_nom FROM octroi o WHERE o.ocid = p.ocid
                    ORDER BY montant DESC LIMIT 1) AS fournisseur
            FROM recherche r JOIN processus p ON p.ocid = r.ocid
            WHERE recherche MATCH ? ORDER BY rank LIMIT 100
        """, (fts,)).fetchall()
    return render_template("recherche.html", q=q, resultats=resultats)


@app.route("/contrat/<path:ocid>")
def fiche(ocid):
    cur = db()
    p = cur.execute("SELECT * FROM processus WHERE ocid = ?", (ocid,)).fetchone()
    if not p:
        abort(404)
    octrois = cur.execute(
        "SELECT * FROM octroi WHERE ocid = ? ORDER BY montant DESC", (ocid,)
    ).fetchall()
    contrats = cur.execute(
        "SELECT * FROM contrat WHERE ocid = ?", (ocid,)).fetchall()
    avenants = cur.execute(
        "SELECT * FROM avenant WHERE ocid = ? ORDER BY date", (ocid,)).fetchall()
    fichier = cur.execute(
        "SELECT * FROM fichier_ingere WHERE nom = ?", (p["dernier_fichier"],)
    ).fetchone()
    # Comparaison octroyé vs final par contrat terminé
    comparaisons = []
    for c in contrats:
        if c["statut"] == "terminated" and c["montant"]:
            oc = next((o for o in octrois if o["octroi_id"] == c["octroi_id"]), None)
            if oc and oc["montant"]:
                comparaisons.append({
                    "octroye": oc["montant"], "final": c["montant"],
                    "ratio": c["montant"] / oc["montant"],
                })
    return render_template("fiche.html", p=p, octrois=octrois, contrats=contrats,
                           avenants=avenants, signaux=signaux_de(ocid),
                           comparaisons=comparaisons, fichier=fichier,
                           types=TYPES_SIGNAUX)


@app.route("/ce-qui-ne-fait-pas-de-sens")
def anomalies():
    type_filtre = request.args.get("type", "DEPASSEMENT")
    if type_filtre not in TYPES_SIGNAUX:
        type_filtre = "DEPASSEMENT"
    page = max(1, request.args.get("page", 1, type=int))
    ordre = {
        "DEPASSEMENT": "(s.montant_final - s.montant_octroye) DESC",
        "GRE_A_GRE": "s.montant_octroye DESC",
        "SOUM_UNIQUE": "s.montant_octroye DESC",
        "AVENANTS_SERIE": "s.gravite DESC, p.derniere_date DESC",
        "ABERRATION": "s.ratio DESC",
    }[type_filtre]
    lignes = db().execute(f"""
        SELECT s.*, p.titre, p.acheteur_nom, p.derniere_date,
               (SELECT fournisseur_nom FROM octroi o WHERE o.ocid = s.ocid
                ORDER BY montant DESC LIMIT 1) AS fournisseur
        FROM signal s JOIN processus p ON p.ocid = s.ocid
        WHERE s.type = ?
        ORDER BY {ordre} LIMIT 50 OFFSET ?
    """, (type_filtre, (page - 1) * 50)).fetchall()
    compte = dict(db().execute(
        "SELECT type, COUNT(*) FROM signal GROUP BY type").fetchall())
    return render_template("anomalies.html", lignes=lignes, types=TYPES_SIGNAUX,
                           type_filtre=type_filtre, compte=compte, page=page)


@app.route("/organisme")
def organisme():
    nom = request.args.get("nom", "")
    cur = db()
    total, valeur = cur.execute("""
        SELECT COUNT(DISTINCT p.ocid), COALESCE(SUM(o.montant),0)
        FROM processus p LEFT JOIN octroi o ON o.ocid = p.ocid
        WHERE p.acheteur_nom = ?""", (nom,)).fetchone()
    gag = cur.execute("""
        SELECT COALESCE(SUM(o.montant),0)
        FROM processus p JOIN octroi o ON o.ocid = p.ocid
        WHERE p.acheteur_nom = ? AND p.methode = 'direct'""", (nom,)).fetchone()[0]
    lignes = cur.execute("""
        SELECT p.*, (SELECT MAX(montant) FROM octroi o WHERE o.ocid = p.ocid)
               AS montant,
               (SELECT fournisseur_nom FROM octroi o WHERE o.ocid = p.ocid
                ORDER BY montant DESC LIMIT 1) AS fournisseur
        FROM processus p WHERE p.acheteur_nom = ?
        ORDER BY montant DESC LIMIT 100""", (nom,)).fetchall()
    return render_template("organisme.html", nom=nom, total=total,
                           valeur=valeur, gre_a_gre=gag, lignes=lignes)


@app.route("/fournisseur")
def fournisseur():
    nom = request.args.get("nom", "")
    cur = db()
    lignes = cur.execute("""
        SELECT o.*, p.titre, p.acheteur_nom, p.methode
        FROM octroi o JOIN processus p ON p.ocid = o.ocid
        WHERE o.fournisseur_nom = ?
        ORDER BY o.montant DESC LIMIT 200""", (nom,)).fetchall()
    total = sum(l["montant"] or 0 for l in lignes)
    neq = next((l["fournisseur_neq"] for l in lignes if l["fournisseur_neq"]), None)
    acheteurs = len({l["acheteur_nom"] for l in lignes})
    return render_template("fournisseur.html", nom=nom, lignes=lignes,
                           total=total, neq=neq, acheteurs=acheteurs)


@app.route("/meilleur-des-mondes")
def meilleur_des_mondes():
    return render_template("meilleur.html", indicateurs=stats_reperes(),
                           a=stats_2026())


ACTUALITES = [
    {
        "slug": "saaqclic",
        "titre": "SAAQclic : « ça ne vaut pas 1 milliard »… vraiment?",
        "date": "2026-02-16",
        "etiquette": "Deux enquêtes publiques",
        "resume": "Le public voit un site web bogué et conclut au gaspillage. "
                  "La réalité est double : le projet lui-même se défend — mais son "
                  "dérapage de coût, lui, est bien réel et documenté. Démêlons.",
    },
]


@app.route("/aux-nouvelles")
def actualites():
    return render_template("actualites.html", articles=ACTUALITES)


@app.route("/aux-nouvelles/saaqclic")
def actualite_saaqclic():
    art = next(a for a in ACTUALITES if a["slug"] == "saaqclic")
    return render_template("actu_saaqclic.html", art=art)


@app.route("/meilleur-des-mondes/saaqclic")
def fiche_saaqclic():
    cur = db()
    nb_saaq, total_saaq = cur.execute("""
        SELECT COUNT(DISTINCT p.ocid), COALESCE(SUM(o.montant),0)
        FROM processus p JOIN octroi o ON o.ocid = p.ocid
        WHERE p.acheteur_nom LIKE '%assurance automobile%' AND o.montant > 0
    """).fetchone()
    lgs = cur.execute("""
        SELECT p.ocid, p.titre, p.methode, o.montant, o.date
        FROM octroi o JOIN processus p ON p.ocid = o.ocid
        WHERE p.acheteur_nom LIKE '%assurance automobile%'
          AND o.fournisseur_nom LIKE '%LGS%' AND o.montant > 0
        ORDER BY o.montant DESC LIMIT 5
    """).fetchall()
    nom_saaq = cur.execute("""
        SELECT acheteur_nom FROM processus
        WHERE acheteur_nom LIKE '%assurance automobile%' LIMIT 1
    """).fetchone()
    return render_template("saaqclic.html", nb_saaq=nb_saaq,
                           total_saaq=total_saaq, lgs=lgs,
                           nom_saaq=nom_saaq[0] if nom_saaq else "")


@app.route("/methodologie")
def methodologie():
    return render_template("methodologie.html", s=stats_globales(),
                           types=TYPES_SIGNAUX)


if __name__ == "__main__":
    app.run(port=5071, debug=True)
