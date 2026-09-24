# Passation — Traçabilité Québec

État au 24 septembre 2026. À lire en entier avant de toucher au code : ce projet
a des contraintes légales, et certaines erreurs ne sont pas rattrapables.

---

## 1. Ce que c'est

Site d'intelligence citoyenne qui suit l'argent public québécois. Deux moitiés :

- **Un explorateur de contrats** bâti sur les données ouvertes du SEAO
  (229 167 processus, 257 300 octrois, 52 721 signaux détectés).
- **Une section éditoriale** qui explique le Québec en chiffres sourcés :
  secteurs et indicateurs, lois et grands projets, élection, FAQ, capsules.

Posture éditoriale, écrite dans le README et tenue partout : **pro-transparence,
anti-complot**. Un signal n'est pas une accusation. Chaque écart mérite une
explication avant une interprétation.

**Propriétaire : William Carrier.** Non technique, francophone québécois.
Il décide du fond ; il ne lit pas le code. Lui écrire en français, en expliquant
les arbitrages plutôt que la mécanique.

---

## 2. Où ça vit

| Quoi | Où |
|---|---|
| Dépôt local | `~/Projets/tracabilite-quebec` (symlink depuis `~/Desktop/Travail`) |
| GitHub | `https://github.com/ibratim2026/tracabilite-quebec` — branche `main` |
| Site public | `https://ibratim2026.github.io/tracabilite-quebec/` — branche `gh-pages` |
| Base de données | `data/seao.db` — 305 Mo, **jamais commitée** |
| Serveur local | `.claude/launch.json` → nom `tracabilite-quebec`, port 5071 |

⚠️ **Le projet a été déplacé du Bureau vers `~/Projets` pour une raison.** macOS
(TCC) empêche les tâches planifiées de lire `~/Desktop`, ce qui avait gelé les
données pendant deux mois sans aucune erreur visible. Ne jamais le remettre là.

---

## 3. Comment ça tourne

```bash
cd ~/Projets/tracabilite-quebec
.venv/bin/python app/app.py          # serveur local, port 5071
./update.sh                          # télécharge le SEAO, reconstruit la base
./publish_demo.sh                    # exporte le statique et pousse sur gh-pages
.venv/bin/python pipeline/export_donnees.py   # régénère les CSV téléchargeables
```

**Deux tâches launchd tournent tous les jours :**

| Tâche | Heure | Ce qu'elle fait |
|---|---|---|
| `com.tracabilite-quebec.maj` | 6 h 30 | `update.sh` — rafraîchit les données |
| `com.tracabilite-quebec.demo` | 7 h 30 | `publish_demo.sh` — **republie le site public** |

Les runners sont dans `~/Library/Application Support/tracabilite-quebec/`.
Journaux : `data/maj.log`, `data/demo.log`, `data/launchd*.log`.

Données fraîches au moment d'écrire : dernier contrat SEAO du 18 septembre 2026.

---

## 4. Architecture

**Pipeline** (`pipeline/`) : `download.py` → `ingest.py` → `analyze.py`.
`update.sh` reconstruit la base dans un fichier temporaire puis la remplace d'un
coup, pour que le site ne casse jamais pendant la mise à jour.

**Application** : Flask.
- `app/app.py` (733 l.) — l'explorateur : recherche, fiches, signaux, vues CUMUL
  et ECONOMIE.
- `app/sections.py` (496 l.) — toutes les pages éditoriales, la `NAVIGATION`
  (4 rubriques et leurs sous-onglets) et les processeurs de contexte.

**Contenu en JSON** : `app/contenu/*.json`, chargé par `charger(nom)` avec cache
sur mtime. **Le contenu ne vit jamais dans les gabarits.** Pour modifier un
texte, on modifie le JSON.

| Fichier | Contenu |
|---|---|
| `election.json` | dates, enjeux, notions, vérificateurs |
| `mandat.json` | mandat en cours + tracker de 11 promesses + constats des chiens de garde |
| `plateformes.json` | 183 engagements, liste officielle des 20 partis autorisés |
| `lois.json` | 40 lois adoptées, 12 mortes au feuilleton, 23 grands projets, 14 mesures |
| `secteurs.json` | 13 secteurs, 90 indicateurs |
| `faq.json` | 35 questions, 10 catégories |
| `relever.json` | 8 révélations sur les richesses du Québec |
| `a_venir.json` | 11 postes de dépenses futures |
| `corrections.json` | **9 corrections publiques, datées** |
| `reglages.json` | **le mode prudent — voir §5** |
| `inflation.json` | IPC Québec, pour les conversions en dollars constants |

**JS** : `app/static/interactif.js` (767 l.), vanilla, zéro dépendance. Les
données passent par `<script type="application/json">`.

**CSS** : `app/static/style.css` (973 l.). Jetons de design, bandes pleine
largeur (`.bande-bleue` avec inversion automatique des enfants), curseurs
fleur de lys, `.table-cartes` pour le mobile.

**Export statique** : `pipeline/export_static.py`. La liste des chemins à
exporter est en dur, **ligne 89** — toute nouvelle page doit y être ajoutée,
sinon elle n'existe pas en ligne.

---

## 5. ⚠️ Les règles non négociables

### 5.1 La Loi électorale du Québec

**Élection générale le lundi 5 octobre 2026.** Jusque-là, ce site est un *tiers
non autorisé*. Conséquences, vérifiées auprès du guide DGE-259 :

- **Toute visibilité donnée à un parti ou à un candidat par un tiers — même
  parfaitement neutre — constitue une dépense électorale.** Pas seulement les
  éloges ou les attaques : la simple présentation.
- L'exception du « comparatif de programmes » (D-31) exige **les 20 partis
  autorisés ayant au moins 2 candidats**, zéro commentaire, méthodologie
  publiée. Nous n'avons que 5 plateformes → l'exception ne s'applique pas.
- L'art. 429.1 interdit la publicité électorale **le jour du scrutin**.
  `publish_demo.sh` refuse de publier le 2026-10-05 (variable
  `JOURS_SANS_PUBLICATION`). **Ne pas retirer ce garde-fou.**

**Le mode prudent** (`app/contenu/reglages.json`) masque tout contenu qui nomme
ou présente les partis. Le processeur de contexte `injecter_reglages()` dans
`sections.py` expose `prudent` à tous les gabarits.

```json
{ "mode_prudent": true, "prudent_jusqu_au": "2026-10-05" }
```

Le verrou **tombe tout seul le 6 octobre** : le code compare la date du jour à
l'échéance. Les gabarits font `{% if prudent %}…{% else %}…{% endif %}`.

### 5.2 🔴 Ce qui va se passer le 6 octobre sans que personne ne fasse rien

**La tâche launchd de 7 h 30 republie le site tous les jours.** Donc le
6 octobre vers 7 h 30, le verrou sera tombé et **le contenu masqué partira en
ligne automatiquement**, sans relecture.

Ce qui sortira ce matin-là :

- `/election/mandat-en-cours` — le tracker des 11 promesses, les statuts, et la
  section sur les constats de la vérificatrice générale et de la commission
  Gallant.
- Les pourcentages du Polimètre (48 / 25 / 8 / 17 / 2 %) — **ces chiffres n'ont
  pas pu être confirmés à la source.** Le Polimètre québécois n'est plus en
  ligne (polimeter.org ne porte plus que le tracker fédéral). Ils viennent d'un
  extrait de recherche web, et `mandat.json` porte `"a_rafraichir": true` qui
  affiche un encadré d'avertissement.
- `/election/comparateur/` et les blocs partisans de `/election`.

**Action requise avant le 5 octobre au soir** : soit rafraîchir et valider ces
contenus, soit désarmer temporairement la tâche launchd de publication. Ne pas
laisser des chiffres non confirmés sortir tout seuls.

### 5.3 Ce qu'on ne fait pas

- **Aucun verdict sur un parti, un chef ou un programme.** Jamais, même après
  l'élection. On cite des institutions (Vérificateur général, Protecteur du
  citoyen, Commissaire à l'éthique, Commissaire à la santé), on ne juge pas.
- **Aucun label accusatoire.** L'utilisateur avait demandé une étoile pour « ce
  qui ressemble à de la fraude » ; c'est devenu **« ★ À examiner en priorité »**
  (contrats cumulant 3 signaux ou plus). Garder cette formulation.
- **Aucune recommandation de politique publique.** Dans « Relever le Québec »,
  on décrit des leviers documentés ; on ne dit pas d'en tirer quoi que ce soit.
- **On ne publie pas un chiffre qu'on n'a pas retrouvé.** On écrit qu'on ne l'a
  pas trouvé. Voir les blocs « à vérifier » de `a_venir.json` et `lois.json`.
- **On corrige en public.** `corrections.json` → page `/a-propos`. Neuf entrées,
  dont plusieurs corrigent mes propres erreurs publiées. C'est la colonne
  vertébrale de la crédibilité du site : ne jamais corriger en silence.

---

## 6. État actuel

Tout est commité et publié. Dernier commit : `3a7f378`.

**Rubriques du site**

- **Élection 2026** — Vue d'ensemble · **Mandat en cours** · Mieux voter ·
  Comparateur · Décoder la campagne · Testez-vous
- **Comprendre** — L'état du Québec · Secteurs · L'économie expliquée ·
  Le Québec dans le Canada · Lois et projets · Ce qui s'en vient · On clarifie ·
  **Relever le Québec** · Québec prospère
- **Suivre l'argent** — Où va l'argent · Ce qui ne fait pas de sens ·
  Aux nouvelles · Meilleur des mondes
- **À propos** — Qui fait ce site · Méthodologie · Données brutes

**Construit dans les dernières sessions**

- `/on-clarifie` : 35 questions reformulées à la première personne, dans la
  langue des gens, avec 9 blocs « d'où vient l'impression ».
- `/ce-qui-s-en-vient` : 11 postes de dépenses engagées (49,7 G$ pour les
  réseaux d'eau municipaux, 167 G$ de PQI, 155-185 G$ pour Hydro-Québec…),
  séparés en sommes uniques et dépenses annuelles récurrentes.
- `/relever-le-quebec` : 8 révélations sur les richesses québécoises, chacune
  avec « où va l'argent » et « ce qui le ramènerait ici ». Contient la citation
  clé du ministère : la plus-value du traitement « n'appartient pas aux
  Québécois et Québécoises ».
- `/election/mandat-en-cours` : cadre institutionnel visible, tracker verrouillé.

---

## 7. Décisions en suspens (William n'a pas tranché)

1. **Appeler Élections Québec** pour faire valider le comparateur, ou compléter
   les 15 plateformes manquantes sur 20. Sans l'un des deux, le comparateur
   reste masqué.
2. **Nom et mention d'IA sur la page À propos.** La page existe mais
   n'identifie personne.
3. **La veille quotidienne** : locale ou infonuagique, et à quelle heure. Un
   projet discuté, jamais mis en place.
4. **Les dons** : pages et mécanisme à décider.
5. **Le nom de domaine** — le site est encore sur une URL GitHub.
6. **L'édition canadienne** : discutée, non commencée. La logique de « Relever
   le Québec » s'y transpose (sables bitumineux, potasse, bois).

---

## 8. Pièges connus

- **Les caches CSS mentent.** Plusieurs vérifications ont été faussées par du
  CSS périmé. Le cache-busting `?v={{ v_statique }}` est en place, mais faire
  un rechargement dur avant de conclure qu'un style ne marche pas.
- **Les captures d'écran du navigateur intégré peuvent être périmées** après un
  `scrollTo`. Vérifier `scrollY` en JS avant de croire une image.
- **Les polices en export statique** : chemins relatifs obligatoires
  (`url(fonts/…)`), jamais `/static/…` — sinon tout casse sous le préfixe
  `/tracabilite-quebec/`.
- **`.bande-bleue` inverse ses enfants** via une longue liste de sélecteurs.
  Tout nouveau composant placé dans une bande bleue doit y être ajouté.
- **Sites qui bloquent les robots** (403) : Radio-Canada parfois, Le Devoir,
  RAMQ, Revenu Québec, LégisQuébec. Les liens marchent pour un humain. Préférer
  une source équivalente sur `quebec.ca` quand elle existe.
- **Vérifier tous les liens de sources avant de publier.** Plusieurs liens
  étaient morts à la première rédaction. Boucle utile :
  ```bash
  curl -sL -o /dev/null -w '%{http_code}' --max-time 25 -A 'Mozilla/5.0' "$url"
  ```

---

## 9. Conventions

- **Tout en français**, y compris les noms de variables, de fonctions et de
  fichiers. Le code se lit comme le site.
- **Messages de commit en français**, en prose, expliquant le *pourquoi* et pas
  seulement le quoi. Se terminer par
  `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.
- **Design** : jamais un titre gras terminé par de l'italique sérif — William
  trouve ça « trop Claude ». L'accent se fait par la couleur, même police.
- **Pas de mode sombre.** Retiré à sa demande ; le contraste passe par les
  bandes bleues pleine largeur.
- **Vérifier avant d'affirmer.** Lancer le serveur, regarder la page, compter
  les éléments en JS, tester les deux états du mode prudent. Ne jamais dire
  « c'est fait » sans l'avoir vu.

---

## 10. Si tu ne fais qu'une chose

Va lire `app/contenu/reglages.json` et décide, avec William, ce qui doit
arriver le 6 octobre au matin. C'est la seule échéance de ce projet qui ne
pardonne pas.
