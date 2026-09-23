"""Exporte en CSV les données que le site calcule, pour que n'importe qui puisse
refaire nos chiffres sans nous croire sur parole.

Les fichiers atterrissent dans data/site_statique/donnees/ et sont publiés avec
le site. Les données d'origine restent celles du SEAO (Données Québec) : ce que
nous publions ici, ce sont nos consolidations et nos calculs.

Usage : .venv/bin/python pipeline/export_donnees.py
"""
import csv
import json
import sqlite3
import zipfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
BASE = RACINE / "data" / "seao.db"
CONTENU = RACINE / "app" / "contenu"
SORTIE = RACINE / "data" / "site_statique" / "donnees"


def ecrire(nom, entetes, lignes):
    """Écrit le CSV. Au-delà de 2 Mo, on le livre compressé : le site est
    republié chaque semaine et on ne veut pas y pousser 30 Mo à chaque fois."""
    fichier = SORTIE / nom
    with fichier.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(entetes)
        w.writerows(lignes)
    taille = fichier.stat().st_size
    if taille > 2_000_000:
        archive = fichier.with_suffix(".csv.zip")
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            z.write(fichier, nom)
        fichier.unlink()
        return archive.name, archive.stat().st_size
    return fichier.name, taille


def main():
    SORTIE.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(BASE)
    db.row_factory = sqlite3.Row
    fichiers = []

    # 1. Tous les signaux détectés, avec le contrat concerné.
    lignes = db.execute("""
        SELECT s.type, s.ocid, p.titre, p.acheteur_nom, p.methode, p.nb_soumissionnaires,
               s.montant_octroye, s.montant_final, s.ratio, s.details, p.url_seao,
               (SELECT fournisseur_nom FROM octroi o WHERE o.ocid = s.ocid
                ORDER BY montant DESC LIMIT 1) AS fournisseur
        FROM signal s JOIN processus p ON p.ocid = s.ocid
        ORDER BY s.type, s.montant_octroye DESC
    """).fetchall()
    fichiers.append(("Tous les signaux détectés dans les contrats publics", len(lignes),
                     ecrire("signaux.csv",
                            ["type_signal", "ocid", "titre", "organisme", "mode_attribution",
                             "nb_soumissionnaires", "montant_octroye", "montant_final", "ratio",
                             "details", "url_seao", "fournisseur"],
                            [tuple(l) for l in lignes])))

    # 2. Les contrats qui cumulent trois signaux ou plus (« à examiner en priorité »).
    lignes = db.execute("""
        SELECT p.ocid, p.titre, p.acheteur_nom,
               (SELECT COUNT(DISTINCT type) FROM signal x WHERE x.ocid = p.ocid) AS nb_signaux,
               (SELECT GROUP_CONCAT(DISTINCT type) FROM signal x WHERE x.ocid = p.ocid) AS signaux,
               (SELECT MAX(montant) FROM octroi o WHERE o.ocid = p.ocid) AS montant,
               p.url_seao
        FROM processus p
        WHERE (SELECT COUNT(DISTINCT type) FROM signal x WHERE x.ocid = p.ocid) >= 3
        ORDER BY nb_signaux DESC, montant DESC
    """).fetchall()
    fichiers.append(("Contrats cumulant au moins trois signaux", len(lignes),
                     ecrire("a-examiner-en-priorite.csv",
                            ["ocid", "titre", "organisme", "nb_signaux", "signaux",
                             "montant", "url_seao"], [tuple(l) for l in lignes])))

    # 3. Les contrats terminés sous le montant octroyé.
    lignes = db.execute("""
        SELECT p.ocid, p.titre, p.acheteur_nom, o.fournisseur_nom, o.montant, c.montant,
               (o.montant - c.montant) AS economie, c.date_fin, p.url_seao
        FROM contrat c
        JOIN octroi o ON o.ocid = c.ocid AND o.octroi_id = c.octroi_id
        JOIN processus p ON p.ocid = c.ocid
        WHERE c.statut = 'terminated' AND c.montant > 0 AND o.montant > c.montant * 1.02
        ORDER BY economie DESC
    """).fetchall()
    fichiers.append(("Contrats terminés sous le montant octroyé", len(lignes),
                     ecrire("economies-realisees.csv",
                            ["ocid", "titre", "organisme", "fournisseur", "montant_octroye",
                             "depense_finale", "economie", "date_fin", "url_seao"],
                            [tuple(l) for l in lignes])))

    # 4. Les indicateurs des secteurs, avec leur source.
    secteurs = json.loads((CONTENU / "secteurs.json").read_text())
    lignes = [(s["slug"], s["nom"], k["nom"], k.get("valeur"), k.get("annee"),
               k.get("unite"), k.get("sens"), k.get("tendance"), k.get("comparaison"),
               k.get("cible"), k.get("source_nom"), k.get("source_url"))
              for s in secteurs for k in s["kpis"]]
    fichiers.append(("Les indicateurs de chaque secteur", len(lignes),
                     ecrire("indicateurs.csv",
                            ["secteur", "secteur_nom", "indicateur", "valeur", "annee", "unite",
                             "sens", "tendance", "comparaison", "cible", "source", "url_source"],
                            lignes)))

    # 5. Les grands projets et leurs coûts.
    projets = json.loads((CONTENU / "lois.json").read_text()).get("projets", [])
    lignes = [(p["nom"], p.get("secteur"), p.get("cout_initial"), p.get("cout_actuel"),
               p.get("cout_initial_num"), p.get("cout_actuel_num"), p.get("annee_initiale"),
               p.get("echeance_initiale"), p.get("echeance_actuelle"), p.get("statut"),
               " · ".join(s["url"] for s in p.get("sources", [])))
              for p in projets]
    fichiers.append(("Grands projets publics : coût annoncé et coût actuel", len(lignes),
                     ecrire("grands-projets.csv",
                            ["projet", "secteur", "cout_initial", "cout_actuel",
                             "cout_initial_g", "cout_actuel_g", "annee_annonce",
                             "echeance_initiale", "echeance_actuelle", "statut", "sources"],
                            lignes)))

    # 6. La série d'inflation utilisée pour les conversions.
    infl = json.loads((CONTENU / "inflation.json").read_text())
    fichiers.append(("Indice des prix à la consommation du Québec", len(infl["indice"]),
                     ecrire("indice-prix-quebec.csv", ["annee", "indice_2002_100"],
                            sorted(infl["indice"].items()))))

    # 7. Les dépenses déjà engagées pour les prochaines années.
    aven = json.loads((CONTENU / "a_venir.json").read_text())
    lignes = [(p["slug"], p["titre"], p["montant"], p.get("montant_g"), p.get("nature"),
               p.get("horizon"), p.get("statut"), p.get("secteur"),
               " · ".join(s["url"] for s in p.get("sources", [])))
              for p in aven["postes"]]
    fichiers.append(("Dépenses publiques déjà engagées pour les prochaines années", len(lignes),
                     ecrire("depenses-a-venir.csv",
                            ["poste", "titre", "montant", "montant_g", "nature", "horizon",
                             "statut", "secteur", "sources"], lignes)))

    catalogue = [{"fichier": nom, "description": d, "lignes": lg, "octets": o}
                 for d, lg, (nom, o) in fichiers]
    (SORTIE / "catalogue.json").write_text(json.dumps(catalogue, ensure_ascii=False, indent=1))
    (CONTENU / "donnees.json").write_text(json.dumps(catalogue, ensure_ascii=False, indent=1))
    for c in catalogue:
        print(f"{c['fichier']:32} {c['lignes']:>7} lignes  {c['octets'] / 1e6:>6.1f} Mo")


if __name__ == "__main__":
    main()
