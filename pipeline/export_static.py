"""Export d'une version statique du site pour GitHub Pages.

GitHub Pages ne sert que des fichiers HTML : impossible d'y faire tourner la
recherche en direct ni les 215 000 fiches. Ce script génère donc un
« instantané navigable » : les pages principales, les fiches de contrats
qui y sont liées, puis les pages d'organismes et de fournisseurs liées à ces
fiches. Tout lien vers une page non incluse est redirigé vers une page
d'explication.

Résultat : data/site_statique/ (à publier sur la branche gh-pages).

Usage :
    .venv/bin/python pipeline/export_static.py
"""
import hashlib
import html
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

RACINE = Path(__file__).resolve().parent.parent
SORTIE = RACINE / "data" / "site_statique"
BASE = "/tracabilite-quebec"  # préfixe des pages de projet GitHub

sys.path.insert(0, str(RACINE / "app"))
from app import app  # noqa: E402

TYPES = ["DEPASSEMENT", "GRE_A_GRE", "SOUM_UNIQUE", "AVENANTS_SERIE", "ABERRATION"]
PAGES_PAR_TYPE = 3
MAX_PAGES = 4000


def chemin_de(url):
    """Traduit une URL du site en chemin de fichier statique."""
    p = urlsplit(url)
    q = parse_qs(p.query)
    if p.path == "/":
        return "index.html"
    if p.path == "/ce-qui-ne-fait-pas-de-sens":
        t = q.get("type", ["DEPASSEMENT"])[0]
        pg = q.get("page", ["1"])[0]
        return f"ce-qui-ne-fait-pas-de-sens/{t}/{pg}/index.html"
    if p.path in ("/organisme", "/fournisseur"):
        nom = q.get("nom", [""])[0]
        h = hashlib.md5(nom.encode()).hexdigest()[:12]
        return f"{p.path.strip('/')}/{h}/index.html"
    if p.path == "/recherche":
        return None  # pas de recherche en statique
    return p.path.strip("/") + "/index.html"


def liens_internes(page_html, url_courante):
    """Extrait les liens internes (absolus ou requêtes relatives) d'une page."""
    for brut in re.findall(r'href="([^"]+)"', page_html):
        lien = html.unescape(brut)
        if lien.startswith("?"):
            yield urlsplit(url_courante).path + lien
        elif lien.startswith("/") and not lien.startswith("//"):
            yield lien


def page_hors_demo():
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Page non incluse — Traçabilité Québec (démo)</title>
<link rel="stylesheet" href="{BASE}/static/style.css"></head>
<body><main class="contenant" style="padding:3rem 1.2rem">
<h1>Cette page n'est pas dans la démo</h1>
<p class="explication">Vous consultez la <strong>version démo statique</strong>
de Traçabilité Québec : elle contient les pages principales et quelques
centaines de fiches, mais pas les 215 000 contrats ni la recherche en direct.
La version complète tourne pour l'instant en local — un site public complet
est prévu.</p>
<p><a href="{BASE}/">← Retour à l'accueil de la démo</a> ·
<a href="https://github.com/ibratim2026/tracabilite-quebec">Code source sur GitHub</a></p>
</main></body></html>"""


def main():
    app.config["STATIQUE"] = True
    client = app.test_client()

    graines = ["/", "/meilleur-des-mondes", "/meilleur-des-mondes/saaqclic",
               "/methodologie"]
    for t in TYPES:
        for pg in range(1, PAGES_PAR_TYPE + 1):
            graines.append(f"/ce-qui-ne-fait-pas-de-sens?type={t}&page={pg}")

    rendus = {}  # url -> html

    def rendre(url):
        if url in rendus or len(rendus) >= MAX_PAGES:
            return
        rep = client.get(url)
        if rep.status_code == 200:
            rendus[url] = rep.get_data(as_text=True)

    # Vague 0 : pages principales
    for u in graines:
        rendre(u)
    # Vague 1 : fiches de contrats liées aux pages principales
    for u, contenu in list(rendus.items()):
        for lien in liens_internes(contenu, u):
            if lien.startswith("/contrat/"):
                rendre(lien)
    # Vague 2 : organismes et fournisseurs liés aux pages déjà rendues
    for u, contenu in list(rendus.items()):
        for lien in liens_internes(contenu, u):
            if lien.startswith(("/organisme?", "/fournisseur?")):
                rendre(lien)

    # Ensemble final : réécriture des liens et écriture des fichiers
    exportes = {}
    for u in rendus:
        c = chemin_de(u)
        if c:
            exportes[u] = c
    chemins_connus = {}
    for u, c in exportes.items():
        chemins_connus[c] = BASE + "/" + c.removesuffix("index.html").rstrip("/")
        if not chemins_connus[c].removeprefix(BASE):
            chemins_connus[c] = BASE + "/"

    if SORTIE.exists():
        shutil.rmtree(SORTIE)
    SORTIE.mkdir(parents=True)

    def reecrire(m):
        lien = html.unescape(m.group(1))
        if lien.startswith("/static/"):
            return f'href="{BASE}{lien}"'
        if lien.startswith("?") or (lien.startswith("/") and not lien.startswith("//")):
            absolu = (urlsplit(url_courante).path + lien) if lien.startswith("?") else lien
            c = chemin_de(absolu)
            if c and c in chemins_connus:
                return f'href="{chemins_connus[c]}/"'.replace(BASE + "//", BASE + "/")
            return f'href="{BASE}/non-inclus/"'
        return m.group(0)

    for url_courante, contenu in rendus.items():
        c = exportes.get(url_courante)
        if not c:
            continue
        contenu = re.sub(r'href="([^"]+)"', reecrire, contenu)
        dest = SORTIE / c
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(contenu)

    # Pages annexes et actifs
    (SORTIE / "non-inclus").mkdir(exist_ok=True)
    (SORTIE / "non-inclus" / "index.html").write_text(page_hors_demo())
    (SORTIE / "404.html").write_text(page_hors_demo())
    (SORTIE / ".nojekyll").write_text("")
    dossier_static = SORTIE / "static"
    dossier_static.mkdir(exist_ok=True)
    shutil.copy(RACINE / "app" / "static" / "style.css", dossier_static / "style.css")

    print(f"{len(exportes)} pages exportées vers {SORTIE}")


if __name__ == "__main__":
    main()
