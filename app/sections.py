"""Sections éditoriales : Élection 2026, secteurs de l'État, lois et projets,
capsule « Québec prospère », à propos.

Le contenu vit dans app/contenu/*.json, rédigé et vérifié à la main à partir
des recherches du dossier recherche/. Chaque affirmation chiffrée y porte sa
source. Le code ne fait que mettre en page — et, pour chaque secteur, croiser
avec les contrats publics du SEAO.
"""
import json
from pathlib import Path

from flask import Blueprint, abort, current_app, render_template

CONTENU = Path(__file__).resolve().parent / "contenu"

bp = Blueprint("sections", __name__)

_cache = {}


def charger(nom):
    """Lit app/contenu/<nom>.json (relu automatiquement s'il a changé)."""
    f = CONTENU / f"{nom}.json"
    if not f.exists():
        return None
    mtime = f.stat().st_mtime
    entree = _cache.get(nom)
    if entree is None or entree[0] != mtime:
        _cache[nom] = (mtime, json.loads(f.read_text()))
    return _cache[nom][1]


# Navigation : 4 grandes entrées, chacune avec ses sous-onglets. Une page
# appartient à la rubrique dont un préfixe correspond à son chemin.
NAVIGATION = [
    {"cle": "election", "nom": "Élection 2026", "url": "/election", "prefixes": ["/election"],
     "sous": [("/election", "Vue d'ensemble"), ("/election/mieux-voter", "Mieux voter"),
              ("/election/comparateur/", "Comparateur"),
              ("/election/decoder", "Décoder la campagne"), ("/election/jouer", "Testez-vous")]},
    {"cle": "comprendre", "nom": "Comprendre", "url": "/secteurs",
     "prefixes": ["/secteurs", "/economie-expliquee", "/quebec-canada", "/lois-et-projets", "/quebec-prospere"],
     "sous": [("/secteurs", "Secteurs et indicateurs"), ("/economie-expliquee", "L'économie expliquée"),
              ("/quebec-canada", "Le Québec dans le Canada"),
              ("/lois-et-projets", "Lois et projets"), ("/quebec-prospere", "Québec prospère")]},
    {"cle": "argent", "nom": "Suivre l'argent", "url": "/",
     "prefixes": ["/ce-qui-ne-fait-pas-de-sens", "/aux-nouvelles", "/meilleur-des-mondes",
                  "/recherche", "/contrat", "/organisme", "/fournisseur"],
     "sous": [("/", "Où va l'argent"), ("/ce-qui-ne-fait-pas-de-sens", "Ce qui ne fait pas de sens"),
              ("/aux-nouvelles", "Aux nouvelles"), ("/meilleur-des-mondes", "Meilleur des mondes")]},
    {"cle": "apropos", "nom": "À propos", "url": "/a-propos", "prefixes": ["/a-propos", "/methodologie"],
     "sous": [("/a-propos", "Qui fait ce site"), ("/methodologie", "Méthodologie")]},
]


def rubrique_de(chemin):
    if chemin == "/":
        return NAVIGATION[2]
    return next((r for r in NAVIGATION if any(chemin.startswith(p) for p in r["prefixes"])), None)


def sous_onglet_actif(chemin, url):
    if url == "/":
        return chemin == "/"
    if url == "/election":
        return chemin.rstrip("/") == "/election"
    return chemin.startswith(url.rstrip("/"))


@bp.app_context_processor
def injecter_navigation():
    from flask import request
    return {"navigation": NAVIGATION, "rubrique": rubrique_de(request.path),
            "sous_onglet_actif": sous_onglet_actif}


@bp.app_context_processor
def injecter_reglages():
    """mode_prudent : masque tout contenu qui nomme ou présente les partis
    (Loi électorale, visibilité donnée par un tiers en période électorale)."""
    r = charger("reglages") or {}
    return {"prudent": r.get("mode_prudent", False),
            "note_prudent": r.get("note_prudent", "")}


# ---------------------------------------------------------------- Élection

@bp.route("/election")
def election():
    from datetime import date
    e = dict(charger("election") or {})
    if e.get("date_scrutin"):
        e["jours_restants"] = max(0, (date.fromisoformat(e["date_scrutin"])
                                      - date.today()).days)
    return render_template("election.html", e=e,
                           p=charger("plateformes"), secteurs=charger("secteurs"))


@bp.route("/election/comparateur/")
@bp.route("/election/comparateur/<theme>")
def comparateur(theme=None):
    p = charger("plateformes")
    if not p:
        abort(404)
    themes = {t["slug"]: t for t in p["themes"]}
    if theme is None:
        theme = p["themes"][0]["slug"]
    if theme not in themes:
        abort(404)
    par_parti = {pa["slug"]: [] for pa in p["partis"]}
    for eng in p["engagements"]:
        if eng["theme"] == theme and eng["parti"] in par_parti:
            par_parti[eng["parti"]].append(eng)
    secteur = next((s for s in (charger("secteurs") or [])
                    if theme in s.get("themes_plateformes", [])), None)
    return render_template("comparateur.html", p=p, theme=themes[theme],
                           par_parti=par_parti, secteur=secteur)


@bp.route("/election/jouer")
def jouer():
    p = charger("plateformes")
    aveugle = None
    if p:
        # Une proposition par parti et par thème : celle marquée « phare »,
        # sinon la première. Un thème n'entre dans le jeu que si tous les
        # partis y ont une proposition (sinon le jeu serait déséquilibré).
        themes = []
        for t in p["themes"]:
            options = []
            for pa in p["partis"]:
                engs = [e for e in p["engagements"]
                        if e["theme"] == t["slug"] and e["parti"] == pa["slug"]]
                phare = next((e for e in engs if e.get("phare")), engs[0] if engs else None)
                if phare:
                    options.append({"parti": pa["slug"], "texte": phare["texte"]})
            if len(options) == len(p["partis"]):
                themes.append({"nom": t["nom"], "question": t.get("question"),
                               "options": options})
        aveugle = {"themes": themes,
                   "partis": {pa["slug"]: pa["nom"] for pa in p["partis"]}}
    return render_template("jouer.html", quiz=charger("quiz"), aveugle=aveugle,
                           budget=charger("budget"))


@bp.route("/election/mieux-voter")
def decider():
    """Aide à la décision, centrée sur l'électeur : ses priorités, l'état du
    secteur, les questions à poser et le délai d'effet des leviers. Aucun
    jugement sur les partis (charte + Loi électorale en période électorale)."""
    e = charger("election") or {}
    secteurs = charger("secteurs") or []
    capsule = charger("capsule") or {}
    plateformes = charger("plateformes") or {}
    themes = {t["slug"]: t for t in plateformes.get("themes", [])}
    leviers_par_secteur = {lv["secteur"]: lv for lv in capsule.get("leviers", []) if lv.get("secteur")}

    priorites = []
    for s in secteurs:
        kpis = [k for k in s["kpis"] if k.get("valeur")][:3]
        theme = next((themes[t] for t in s.get("themes_plateformes", []) if t in themes), None)
        lv = leviers_par_secteur.get(s["slug"])
        priorites.append({
            "slug": s["slug"], "nom": s["nom"], "accroche": s["accroche"],
            "budget": (s.get("budget") or {}).get("montant"),
            "kpis": [{"nom": k["nom"], "valeur": k["valeur"], "annee": k["annee"],
                      "comparaison": k.get("comparaison")} for k in kpis],
            "question": theme["question"] if theme else None,
            "levier": {"titre": lv["titre_court"], "delai": lv["delai"], "preuve": lv["preuve"],
                       "effet": lv["effet"], "slug": lv["slug"]} if lv else None,
        })
    return render_template("decider.html", e=e, priorites=priorites,
                           leviers=capsule.get("leviers", []))


@bp.route("/election/decoder")
def decoder():
    return render_template("decoder.html", e=charger("election"))


# ---------------------------------------------------------------- Secteurs

def depenses_seao(db, motifs):
    """Contrats publics des organismes associés à un secteur, repérés par le
    nom de l'acheteur. Approximation assumée et expliquée sur la page."""
    if not motifs:
        return None
    # Un motif qui commence par « - » exclut (ex. « -CHU » pour ne pas compter
    # les hôpitaux universitaires dans l'éducation).
    inclus = [m for m in motifs if not m.startswith("-")]
    exclus = [m[1:] for m in motifs if m.startswith("-")]
    clause = "(" + " OR ".join("p.acheteur_nom LIKE ?" for _ in inclus) + ")"
    clause += "".join(" AND p.acheteur_nom NOT LIKE ?" for _ in exclus)
    args = [f"%{m}%" for m in inclus + exclus]
    total, nb = db.execute(f"""
        SELECT COALESCE(SUM(o.montant),0), COUNT(*)
        FROM octroi o JOIN processus p ON p.ocid = o.ocid
        WHERE o.montant > 0 AND o.date >= '2025-01-01' AND ({clause})
    """, args).fetchone()
    gag = db.execute(f"""
        SELECT COALESCE(SUM(o.montant),0)
        FROM octroi o JOIN processus p ON p.ocid = o.ocid
        WHERE o.montant > 0 AND o.date >= '2025-01-01' AND p.methode = 'direct'
          AND ({clause})
    """, args).fetchone()[0]
    acheteurs = db.execute(f"""
        SELECT p.acheteur_nom AS nom, SUM(o.montant) AS valeur, COUNT(*) AS nb
        FROM octroi o JOIN processus p ON p.ocid = o.ocid
        WHERE o.montant > 0 AND o.date >= '2025-01-01' AND ({clause})
        GROUP BY p.acheteur_nom ORDER BY valeur DESC LIMIT 6
    """, args).fetchall()
    signaux = dict(db.execute(f"""
        SELECT s.type, COUNT(*) FROM signal s JOIN processus p ON p.ocid = s.ocid
        WHERE ({clause}) GROUP BY s.type
    """, args).fetchall())
    return {"total": total, "nb": nb, "gre_a_gre": gag,
            "pct_gag": 100 * gag / total if total else 0,
            "acheteurs": acheteurs, "signaux": signaux}


@bp.route("/secteurs")
def secteurs():
    return render_template("secteurs.html", secteurs=charger("secteurs") or [],
                           budget=charger("budget"))


@bp.route("/secteurs/<slug>")
def secteur(slug):
    tous = charger("secteurs") or []
    s = next((x for x in tous if x["slug"] == slug), None)
    if not s:
        abort(404)
    p = charger("plateformes")
    engagements = []
    if p:
        noms = {pa["slug"]: pa for pa in p["partis"]}
        for eng in p["engagements"]:
            if eng["theme"] in s.get("themes_plateformes", []):
                engagements.append({**eng, "parti_nom": noms[eng["parti"]]["nom"]})
    projets = [pr for pr in (charger("lois") or {}).get("projets", [])
               if pr.get("secteur") == slug]
    lois = [l for l in (charger("lois") or {}).get("adoptees", [])
            if l.get("secteur") == slug]
    return render_template("secteur.html", s=s, tous=tous,
                           seao=depenses_seao(current_app.extensions["tq_db"](), s.get("motifs_seao")),
                           engagements=engagements, projets=projets, lois=lois,
                           p=p)


# ---------------------------------------------------------------- Lois et projets

@bp.route("/economie-expliquee")
def economie():
    import unicodedata
    e = dict(charger("economie") or {})

    def cle(t):
        return unicodedata.normalize("NFD", t["terme"]).encode("ascii", "ignore").decode().lower()
    e["lexique"] = sorted(e.get("lexique", []), key=cle)
    return render_template("economie.html", e=e)


@bp.route("/quebec-canada")
def quebec_canada():
    q = charger("quebec_canada")
    if not q:
        abort(404)
    return render_template("quebec_canada.html", q=q)


@bp.route("/lois-et-projets")
def lois_et_projets():
    l = charger("lois") or {}
    haltere = [{"nom": pr.get("nom_court", pr["nom"]), "initial": pr["cout_initial_num"],
                "actuel": pr["cout_actuel_num"], "note": pr.get("statut")}
               for pr in l.get("projets", [])
               if pr.get("cout_initial_num") and pr.get("cout_actuel_num")]
    return render_template("lois.html", l=l, haltere=haltere,
                           secteurs={s["slug"]: s for s in charger("secteurs") or []})


# ---------------------------------------------------------------- Capsule

@bp.route("/quebec-prospere")
def capsule():
    return render_template("capsule.html", c=charger("capsule"))


@bp.route("/a-propos")
def a_propos():
    db = current_app.extensions["tq_db"]()
    secteurs = charger("secteurs") or []
    chiffres = {
        "contrats": db.execute("SELECT COUNT(*) FROM processus").fetchone()[0],
        "fichiers": db.execute("SELECT COUNT(*) FROM fichier_ingere").fetchone()[0],
        "secteurs": len(secteurs),
        "indicateurs": sum(len(s["kpis"]) for s in secteurs),
        "lois": len((charger("lois") or {}).get("adoptees", [])),
    }
    return render_template("a_propos.html", chiffres=chiffres,
                           corrections=charger("corrections") or [])
