# Traçabilité Québec

**Démo en ligne : https://ibratim2026.github.io/tracabilite-quebec/**
(version statique — pages principales et ~500 fiches; la version complète avec
recherche et 215 000 fiches tourne en local, régénérable avec `export_static.py`)

Outil d'intelligence citoyenne pour suivre où va l'argent public au Québec.
Posture éditoriale : **pro-transparence, anti-complot**. Un signal n'est pas une
accusation; chaque écart mérite une explication avant une interprétation.

## Ce que fait l'outil (version actuelle)

- Agrège les **données ouvertes du SEAO** (contrats publics du Québec :
  ministères, organismes, santé, éducation, municipalités).
- Offre une **recherche** par fournisseur, organisme ou mot-clé, avec des fiches
  de contrat entièrement sourcées (lien vers l'avis officiel, fichier de données
  d'origine, NEQ du fournisseur).
- Détecte les signaux **« Ce qui ne fait pas de sens »** par règles objectives :
  - **Dépassement de coût** : dépense finale > montant octroyé (+10/25/50 %);
  - **Gré à gré 100 k$ et plus** : contrat sans appel d'offres au-dessus du seuil;
  - **Soumissionnaire unique** : appel d'offres ouvert avec un seul répondant;
  - **Avenants en série** : 3 modifications ou plus au contrat;
  - **Donnée aberrante** : ratio invraisemblable, classé comme erreur de saisie
    probable plutôt que présenté comme un scandale.

## Sections du site

- **Élection 2026** (`/election`) : dates de vote, enjeux mesurés, comparateur des
  plateformes (masqué tant que le mode prudent est actif), « Décoder la campagne »
  et trois jeux (« Devinez le chiffre », promesses à l'aveugle, simulateur de budget).
- **Comprendre** : 13 secteurs de l'État avec 90 indicateurs sourcés et leurs
  courbes (`/secteurs`), « L'économie expliquée » (budget, déficit, dette, lexique),
  « Le Québec dans le Canada », « Lois et projets », capsule « Québec prospère ».
- **Suivre l'argent** : les contrats du SEAO, les signaux, les dossiers.
- **À propos** : charte éditoriale, méthode, journal des corrections.

Le contenu éditorial vit dans `app/contenu/*.json`; `app/sections.py` ne fait que
le mettre en page et le croiser avec les contrats du SEAO.

### Mode prudent (Loi électorale)

`app/contenu/reglages.json` → `mode_prudent: true` masque tout ce qui présente les
partis. Motif : pendant la période électorale, toute visibilité donnée à un parti
par un tiers — même neutre — est une dépense électorale, sauf exception
(directive D-31 : tous les partis autorisés, aucun commentaire, méthode publiée).
À valider auprès d'Élections Québec avant de désactiver. `publish_demo.sh` refuse
aussi de publier le jour du scrutin (art. 429.1).

## Architecture

```
pipeline/download.py   Télécharge les fichiers officiels depuis Données Québec
                       (mensuels; les mois absents du catalogue sont comblés
                       par les fichiers hebdomadaires).
pipeline/ingest.py     Consolide le journal d'événements Open Contracting en
                       une base SQLite (un enregistrement par processus d'achat,
                       ordre chronologique strict : le plus récent gagne).
pipeline/analyze.py    Calcule les signaux et l'index de recherche plein texte.
data/brut/             Fichiers sources bruts, conservés tels quels (provenance).
data/seao.db           Base SQLite consolidée.
app/                   Site web Flask (lecture seule sur la base).
```

## Mise à jour des données

```bash
./update.sh        # télécharge le nouveau, reconstruit la base, journal dans data/maj.log
```

Le script reconstruit la base au complet dans un fichier temporaire puis la
remplace d'un coup : l'ordre chronologique est toujours garanti et le site
n'est jamais interrompu. Une routine `launchd`
(`~/Library/LaunchAgents/com.tracabilite-quebec.maj.plist`) l'exécute chaque
jour à 6 h 30 (ou au réveil de la machine).

## Publication de la démo (GitHub Pages)

```bash
./publish_demo.sh   # régénère l'export statique et le pousse sur gh-pages
```

Une seconde routine `launchd` (`com.tracabilite-quebec.demo.plist`) publie la
démo chaque lundi à 7 h 30, une heure après la mise à jour des données —
la démo en ligne reflète donc toujours les données de la semaine.

## Installation (nouvelle machine)

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
./update.sh        # premier téléchargement : ~5 Go, puis incrémental
```

## Lancement du site

```bash
.venv/bin/python app/app.py     # http://localhost:5071
```

## Source des données

[Système électronique d'appel d'offres (SEAO) — Données Québec](https://www.donneesquebec.ca/recherche/dataset/systeme-electronique-dappel-doffres-seao),
diffusé par le Secrétariat du Conseil du trésor, format JSON inspiré du standard
[Open Contracting](https://standard.open-contracting.org/). Les données sont
déclaratives (saisies par les organismes publics) et peuvent contenir des
erreurs; voir la page Méthodologie du site.

## Prochaines étapes envisagées

1. Historique complet 2009–2024 (fichiers XML, à convertir).
2. Regroupement des fournisseurs par NEQ (une entreprise = une fiche, malgré
   les variations de graphie).
3. Croisement avec les comptes publics du Québec → KPI « taux de traçabilité ».
4. Brief hebdomadaire automatisé (nouveaux gros contrats, avenants notables).
5. Volet fédéral (divulgation proactive, open.canada.ca).
6. Fiches éditoriales « meilleur des mondes » sur les grands projets.
