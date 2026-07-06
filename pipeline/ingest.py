"""Ingestion des fichiers SEAO (JSON Open Contracting) vers SQLite.

Le format source est un journal d'événements : chaque « release » décrit un
moment de la vie d'un processus d'achat (publication d'un avis, octroi,
modification, dépense finale). Plusieurs releases parlent du même processus,
identifié par son `ocid`. Ce script les consolide : pour chaque ocid on garde
l'état le plus récent de chaque champ, et on accumule octrois, contrats et
avenants.

Usage :
    python3 pipeline/ingest.py            # ingère tout data/brut/
"""
import json
import os
import re
import sqlite3
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_BRUT = RACINE / "data" / "brut"
# SEAO_DB permet de construire dans un fichier temporaire (mise à jour sans
# interruption : on reconstruit à côté, puis on remplace d'un coup).
BASE = Path(os.environ.get("SEAO_DB", RACINE / "data" / "seao.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS processus (
  ocid TEXT PRIMARY KEY,
  tender_id TEXT,
  titre TEXT,
  acheteur_nom TEXT,
  acheteur_id TEXT,
  municipal INTEGER DEFAULT 0,
  methode TEXT,
  methode_details TEXT,
  categorie TEXT,
  unspsc_id TEXT,
  unspsc_desc TEXT,
  nb_soumissionnaires INTEGER,
  url_seao TEXT,
  premiere_date TEXT,
  derniere_date TEXT,
  dernier_fichier TEXT,
  nb_releases INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS octroi (
  ocid TEXT,
  octroi_id TEXT,
  date TEXT,
  montant REAL,
  fournisseur_nom TEXT,
  fournisseur_neq TEXT,
  PRIMARY KEY (ocid, octroi_id)
);
CREATE TABLE IF NOT EXISTS contrat (
  ocid TEXT,
  contrat_id TEXT,
  octroi_id TEXT,
  statut TEXT,
  montant REAL,
  date_signature TEXT,
  date_fin TEXT,
  PRIMARY KEY (ocid, contrat_id)
);
CREATE TABLE IF NOT EXISTS avenant (
  ocid TEXT,
  contrat_id TEXT,
  avenant_id TEXT,
  date TEXT,
  justification TEXT,
  PRIMARY KEY (ocid, contrat_id, avenant_id)
);
CREATE TABLE IF NOT EXISTS fichier_ingere (
  nom TEXT PRIMARY KEY,
  date_publication TEXT,
  nb_releases INTEGER
);
CREATE INDEX IF NOT EXISTS idx_octroi_fournisseur ON octroi(fournisseur_nom);
CREATE INDEX IF NOT EXISTS idx_octroi_neq ON octroi(fournisseur_neq);
CREATE INDEX IF NOT EXISTS idx_processus_acheteur ON processus(acheteur_nom);
"""


def extraire_neq(parties):
    """Associe l'identifiant de chaque partie à son NEQ quand disponible."""
    neq = {}
    for p in parties or []:
        n = (p.get("details") or {}).get("neq")
        if n:
            neq[p.get("id")] = n
    return neq


def ingerer_release(cur, r, nom_fichier):
    ocid = r.get("ocid")
    if not ocid:
        return
    date = r.get("date", "")
    tender = r.get("tender") or {}
    buyer = r.get("buyer") or {}
    parties = r.get("parties") or []
    neq_par_id = extraire_neq(parties)
    municipal = any(
        (p.get("details") or {}).get("municipal") == "1"
        for p in parties
        if "buyer" in (p.get("roles") or [])
    )
    items = tender.get("items") or []
    classif = (items[0].get("classification") or {}) if items else {}
    docs = tender.get("documents") or []
    url = docs[0].get("url") if docs else None

    cur.execute(
        """
        INSERT INTO processus (ocid, tender_id, titre, acheteur_nom, acheteur_id,
                               municipal, methode, methode_details, categorie,
                               unspsc_id, unspsc_desc, nb_soumissionnaires,
                               url_seao, premiere_date, derniere_date,
                               dernier_fichier, nb_releases)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)
        ON CONFLICT(ocid) DO UPDATE SET
          tender_id = COALESCE(excluded.tender_id, tender_id),
          titre = COALESCE(excluded.titre, titre),
          acheteur_nom = COALESCE(excluded.acheteur_nom, acheteur_nom),
          acheteur_id = COALESCE(excluded.acheteur_id, acheteur_id),
          municipal = MAX(municipal, excluded.municipal),
          methode = COALESCE(excluded.methode, methode),
          methode_details = COALESCE(excluded.methode_details, methode_details),
          categorie = COALESCE(excluded.categorie, categorie),
          unspsc_id = COALESCE(excluded.unspsc_id, unspsc_id),
          unspsc_desc = COALESCE(excluded.unspsc_desc, unspsc_desc),
          nb_soumissionnaires = COALESCE(excluded.nb_soumissionnaires, nb_soumissionnaires),
          url_seao = COALESCE(excluded.url_seao, url_seao),
          premiere_date = MIN(premiere_date, excluded.premiere_date),
          derniere_date = MAX(derniere_date, excluded.derniere_date),
          dernier_fichier = excluded.dernier_fichier,
          nb_releases = nb_releases + 1
        """,
        (
            ocid, tender.get("id"), tender.get("title"),
            buyer.get("name"), buyer.get("id"), int(municipal),
            tender.get("procurementMethod"), tender.get("procurementMethodDetails"),
            tender.get("mainProcurementCategory"),
            classif.get("id"), classif.get("description"),
            tender.get("numberOfTenderers"), url, date, date, nom_fichier,
        ),
    )

    for a in r.get("awards") or []:
        fournisseurs = a.get("suppliers") or [{}]
        f = fournisseurs[0]
        montant = (a.get("value") or {}).get("amount")
        cur.execute(
            """
            INSERT INTO octroi (ocid, octroi_id, date, montant,
                                fournisseur_nom, fournisseur_neq)
            VALUES (?,?,?,?,?,?)
            ON CONFLICT(ocid, octroi_id) DO UPDATE SET
              date = COALESCE(excluded.date, date),
              montant = COALESCE(excluded.montant, montant),
              fournisseur_nom = COALESCE(excluded.fournisseur_nom, fournisseur_nom),
              fournisseur_neq = COALESCE(excluded.fournisseur_neq, fournisseur_neq)
            """,
            (
                ocid, a.get("id"), a.get("date"), montant,
                f.get("name"), neq_par_id.get(f.get("id")),
            ),
        )

    for c in r.get("contracts") or []:
        montant = (c.get("value") or {}).get("amount")
        periode = c.get("period") or {}
        cur.execute(
            """
            INSERT INTO contrat (ocid, contrat_id, octroi_id, statut, montant,
                                 date_signature, date_fin)
            VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(ocid, contrat_id) DO UPDATE SET
              octroi_id = COALESCE(excluded.octroi_id, octroi_id),
              statut = COALESCE(excluded.statut, statut),
              montant = COALESCE(excluded.montant, montant),
              date_signature = COALESCE(excluded.date_signature, date_signature),
              date_fin = COALESCE(excluded.date_fin, date_fin)
            """,
            (
                ocid, c.get("id"), c.get("awardID"), c.get("status"),
                montant, c.get("dateSigned"), periode.get("endDate"),
            ),
        )
        for am in c.get("amendments") or []:
            cur.execute(
                """
                INSERT OR IGNORE INTO avenant (ocid, contrat_id, avenant_id,
                                               date, justification)
                VALUES (?,?,?,?,?)
                """,
                (ocid, c.get("id"), am.get("id"), am.get("date"),
                 am.get("rationale")),
            )


def main():
    con = sqlite3.connect(BASE)
    con.executescript(SCHEMA)
    cur = con.cursor()

    def date_debut(f):
        """Clé de tri chronologique : mensuel_2025-01.json → 2025-01-01,
        hebdo_20251103.json → 2025-11-03. L'ordre importe : pour un même
        processus, l'état le plus récent doit être traité en dernier."""
        m = re.search(r"mensuel_(\d{4})-(\d{2})", f.name)
        if m:
            return f"{m.group(1)}-{m.group(2)}-01"
        h = re.search(r"hebdo_(\d{4})(\d{2})(\d{2})", f.name)
        if h:
            return f"{h.group(1)}-{h.group(2)}-{h.group(3)}"
        return f.name

    fichiers = sorted(DOSSIER_BRUT.glob("*.json"), key=date_debut)
    deja = {row[0] for row in cur.execute("SELECT nom FROM fichier_ingere")}

    for f in fichiers:
        if f.name in deja:
            print(f"[déjà ingéré] {f.name}")
            continue
        print(f"[ingestion] {f.name} ...", flush=True)
        doc = json.loads(f.read_text())
        releases = doc.get("releases", [])
        # Ordre chronologique : le plus récent écrase le plus ancien.
        releases.sort(key=lambda r: r.get("date", ""))
        for r in releases:
            ingerer_release(cur, r, f.name)
        cur.execute(
            "INSERT INTO fichier_ingere (nom, date_publication, nb_releases) VALUES (?,?,?)",
            (f.name, doc.get("publishedDate"), len(releases)),
        )
        con.commit()
        print(f"    {len(releases)} événements consolidés")

    n = cur.execute("SELECT COUNT(*) FROM processus").fetchone()[0]
    print(f"Base : {n} processus d'achat consolidés → {BASE}")
    con.close()


if __name__ == "__main__":
    main()
