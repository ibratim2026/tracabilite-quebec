"""Téléchargement des données ouvertes du SEAO depuis Données Québec.

Interroge l'API CKAN de Données Québec pour obtenir la liste officielle des
fichiers mensuels (format JSON / Open Contracting), puis télécharge ceux de
la période demandée dans data/brut/. Les fichiers déjà présents sont sautés,
donc le script peut être relancé sans danger.

Usage :
    python3 pipeline/download.py --depuis 2025-01 --jusqua 2026-06
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

CKAN_API = (
    "https://www.donneesquebec.ca/recherche/api/3/action/package_show"
    "?id=systeme-electronique-dappel-doffres-seao"
)
RACINE = Path(__file__).resolve().parent.parent
DOSSIER_BRUT = RACINE / "data" / "brut"


def curl(url, *args):
    """Télécharge via curl (les certificats SSL du Python local sont absents)."""
    return subprocess.run(
        ["curl", "-sSL", "--fail", *args, url],
        check=True, capture_output=True,
    )


def lister_ressources():
    """Retourne ({AAAA-MM: url} mensuels, {AAAAMMJJ: url} hebdomadaires).

    Le catalogue comporte des trous : certains mois n'ont pas de fichier
    mensuel (ex. : novembre 2025 à mars 2026). Les fichiers hebdomadaires
    servent alors de solution de rechange.
    """
    paquet = json.loads(curl(CKAN_API).stdout)
    mensuels, hebdos = {}, {}
    for r in paquet["result"]["resources"]:
        nom = r.get("name", "")
        m = re.match(r"mensuel_(\d{4})(\d{2})01_\d{8}\.json", nom)
        if m:
            cle = f"{m.group(1)}-{m.group(2)}"
            # En cas de doublon dans le catalogue, on garde la première entrée
            # (la plus récente, le catalogue étant trié du plus neuf au plus vieux).
            mensuels.setdefault(cle, r["url"])
            continue
        h = re.match(r"hebdo_(\d{8})_\d{8}\.json", nom)
        if h:
            hebdos.setdefault(h.group(1), r["url"])
    return mensuels, hebdos


def telecharger(url, destination):
    tmp = destination.with_suffix(".part")
    curl(url, "-o", str(tmp))
    tmp.rename(destination)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--depuis", default="2025-01", help="Premier mois (AAAA-MM)")
    p.add_argument("--jusqua", default="2099-12", help="Dernier mois (AAAA-MM)")
    args = p.parse_args()

    DOSSIER_BRUT.mkdir(parents=True, exist_ok=True)
    mensuels, hebdos = lister_ressources()
    cibles = sorted(k for k in mensuels if args.depuis <= k <= args.jusqua)
    print(f"{len(cibles)} fichiers mensuels dans la période {args.depuis} → {args.jusqua}")

    a_telecharger = [(f"mensuel_{cle}.json", mensuels[cle]) for cle in cibles]

    # Mois de la période sans fichier mensuel : on les comble avec les hebdos.
    tous_les_mois = set()
    annee, mois = map(int, args.depuis.split("-"))
    while f"{annee:04d}-{mois:02d}" <= args.jusqua and annee < 2100:
        tous_les_mois.add(f"{annee:04d}-{mois:02d}")
        mois += 1
        if mois > 12:
            mois, annee = 1, annee + 1
    manquants = tous_les_mois - set(cibles)
    if manquants:
        print(f"Mois sans fichier mensuel au catalogue : {sorted(manquants)}")
        for debut, url in sorted(hebdos.items()):
            if f"{debut[:4]}-{debut[4:6]}" in manquants:
                a_telecharger.append((f"hebdo_{debut}.json", url))
        print("  → comblés par les fichiers hebdomadaires disponibles")

    for nom, url in a_telecharger:
        dest = DOSSIER_BRUT / nom
        if dest.exists():
            print(f"  [déjà là] {dest.name}")
            continue
        print(f"  [téléchargement] {dest.name} ...")
        try:
            telecharger(url, dest)
            print(f"      ok ({dest.stat().st_size / 1e6:.0f} Mo)")
        except Exception as e:
            print(f"      ÉCHEC : {e}", file=sys.stderr)

    print("Terminé.")


if __name__ == "__main__":
    main()
