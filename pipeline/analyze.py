"""Calcul des signaux « Ce qui ne fait pas de sens » et de l'index de recherche.

Chaque signal est une règle objective, jamais une accusation :

DEPASSEMENT       Contrat terminé dont la dépense finale excède le montant
                  octroyé (gravité 1 : +10 %, gravité 2 : +25 %, gravité 3 : +50 %).
                  Seulement si le montant octroyé est d'au moins 25 000 $.
ABERRATION        Ratio final/octroyé supérieur à 20 : presque toujours une
                  erreur de saisie à la source. Signalé comme problème de
                  qualité de données, PAS comme dépassement.
GRE_A_GRE         Contrat de gré à gré (sans appel d'offres) de 100 000 $ ou
                  plus — le seuil au-delà duquel un appel d'offres public est
                  normalement attendu. Des exceptions légales existent.
SOUM_UNIQUE       Appel d'offres ouvert où un seul soumissionnaire s'est
                  présenté (contrat de 100 000 $ ou plus).
AVENANTS_SERIE    Trois avenants ou plus sur un même contrat.

Le script est rejouable : il vide et recalcule les tables dérivées.

Usage :
    python3 pipeline/analyze.py
"""
import os
import sqlite3
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
BASE = Path(os.environ.get("SEAO_DB", RACINE / "data" / "seao.db"))


def gravite_depassement(ratio):
    if ratio > 1.50:
        return 3
    if ratio > 1.25:
        return 2
    if ratio > 1.10:
        return 1
    return 0


def main():
    con = sqlite3.connect(BASE)
    cur = con.cursor()

    cur.executescript("""
    DROP TABLE IF EXISTS signal;
    CREATE TABLE signal (
      ocid TEXT,
      type TEXT,
      gravite INTEGER,
      montant_octroye REAL,
      montant_final REAL,
      ratio REAL,
      details TEXT,
      PRIMARY KEY (ocid, type)
    );
    CREATE INDEX idx_signal_type ON signal(type, gravite DESC);
    """)

    # --- DEPASSEMENT et ABERRATION : dépense finale vs montant octroyé ---
    lignes = cur.execute("""
        SELECT c.ocid, o.montant, c.montant
        FROM contrat c
        JOIN octroi o ON o.ocid = c.ocid AND o.octroi_id = c.octroi_id
        WHERE c.statut = 'terminated'
          AND o.montant >= 25000 AND c.montant > 0
    """).fetchall()
    for ocid, octroye, final in lignes:
        ratio = final / octroye
        if ratio > 20:
            cur.execute(
                "INSERT OR REPLACE INTO signal VALUES (?,?,?,?,?,?,?)",
                (ocid, "ABERRATION", 0, octroye, final, ratio,
                 "Ratio invraisemblable : probablement une erreur de saisie "
                 "dans les données sources du SEAO."),
            )
        else:
            g = gravite_depassement(ratio)
            if g:
                cur.execute(
                    "INSERT OR REPLACE INTO signal VALUES (?,?,?,?,?,?,?)",
                    (ocid, "DEPASSEMENT", g, octroye, final, ratio,
                     f"Dépense finale supérieure de {(ratio - 1) * 100:.0f} % "
                     "au montant octroyé."),
                )
    n_dep = cur.execute(
        "SELECT COUNT(*) FROM signal WHERE type='DEPASSEMENT'").fetchone()[0]
    n_aber = cur.execute(
        "SELECT COUNT(*) FROM signal WHERE type='ABERRATION'").fetchone()[0]

    # --- GRE_A_GRE : contrat direct de 100 k$ et plus ---
    cur.execute("""
        INSERT OR REPLACE INTO signal
        SELECT p.ocid, 'GRE_A_GRE',
               CASE WHEN MAX(o.montant) >= 10000000 THEN 3
                    WHEN MAX(o.montant) >= 1000000 THEN 2
                    ELSE 1 END,
               MAX(o.montant), NULL, NULL,
               'Contrat conclu de gré à gré (sans appel d''offres ouvert) '
               || 'au-dessus du seuil de 100 000 $.'
        FROM processus p
        JOIN octroi o ON o.ocid = p.ocid
        WHERE p.methode = 'direct'
        GROUP BY p.ocid
        HAVING MAX(o.montant) >= 100000
    """)
    n_gag = cur.execute(
        "SELECT COUNT(*) FROM signal WHERE type='GRE_A_GRE'").fetchone()[0]

    # --- SOUM_UNIQUE : appel d'offres ouvert, un seul soumissionnaire ---
    cur.execute("""
        INSERT OR REPLACE INTO signal
        SELECT p.ocid, 'SOUM_UNIQUE',
               CASE WHEN MAX(o.montant) >= 1000000 THEN 2 ELSE 1 END,
               MAX(o.montant), NULL, NULL,
               'Appel d''offres ouvert où une seule entreprise a soumissionné.'
        FROM processus p
        JOIN octroi o ON o.ocid = p.ocid
        WHERE p.methode = 'open' AND p.nb_soumissionnaires = 1
        GROUP BY p.ocid
        HAVING MAX(o.montant) >= 100000
    """)
    n_su = cur.execute(
        "SELECT COUNT(*) FROM signal WHERE type='SOUM_UNIQUE'").fetchone()[0]

    # --- AVENANTS_SERIE : 3 avenants ou plus ---
    cur.execute("""
        INSERT OR REPLACE INTO signal
        SELECT a.ocid, 'AVENANTS_SERIE',
               CASE WHEN COUNT(*) >= 6 THEN 3 ELSE 2 END,
               NULL, NULL, NULL,
               COUNT(*) || ' avenants enregistrés sur ce contrat.'
        FROM avenant a
        GROUP BY a.ocid
        HAVING COUNT(*) >= 3
    """)
    n_av = cur.execute(
        "SELECT COUNT(*) FROM signal WHERE type='AVENANTS_SERIE'").fetchone()[0]

    # --- Index de recherche plein texte ---
    cur.executescript("""
    DROP TABLE IF EXISTS recherche;
    CREATE VIRTUAL TABLE recherche USING fts5(ocid UNINDEXED, texte);
    """)
    cur.execute("""
        INSERT INTO recherche (ocid, texte)
        SELECT p.ocid,
               COALESCE(p.titre,'') || ' ' || COALESCE(p.acheteur_nom,'') || ' '
               || COALESCE(p.tender_id,'') || ' '
               || COALESCE((SELECT GROUP_CONCAT(DISTINCT o.fournisseur_nom)
                            FROM octroi o WHERE o.ocid = p.ocid), '')
        FROM processus p
    """)

    con.commit()
    print(f"Signaux : {n_dep} dépassements, {n_aber} aberrations, "
          f"{n_gag} gré à gré ≥100k, {n_su} soumissionnaires uniques, "
          f"{n_av} avenants en série")
    con.close()


if __name__ == "__main__":
    main()
