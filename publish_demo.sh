#!/bin/zsh
# Publication hebdomadaire de la démo statique sur GitHub Pages.
#
# 1. Régénère l'instantané statique du site (data/site_statique/) à partir
#    de la base de données courante — donc avec les données fraîches de la
#    mise à jour quotidienne.
# 2. Le pousse sur la branche gh-pages du dépôt GitHub, qui alimente
#    https://ibratim2026.github.io/tracabilite-quebec/
#
# Le dépôt git temporaire est créé hors du dossier (GIT_DIR), pour ne jamais
# laisser de .git dans l'export.
#
# Journal : data/demo.log

set -e
cd "$(dirname "$0")"
exec >> data/demo.log 2>&1

echo ""
echo "=== Publication de la démo, $(date '+%Y-%m-%d %H:%M') ==="

.venv/bin/python pipeline/export_static.py

TMPGIT=$(mktemp -d)/git
export GIT_DIR="$TMPGIT" GIT_WORK_TREE="$PWD/data/site_statique"
git init -q -b gh-pages
git add -A
git -c user.name="William Carrier" -c user.email="williamcarrierlive@gmail.com" \
    commit -qm "Démo statique — $(date '+%Y-%m-%d')"
git push -f https://github.com/ibratim2026/tracabilite-quebec.git gh-pages
unset GIT_DIR GIT_WORK_TREE
rm -rf "$(dirname "$TMPGIT")"

echo "=== Démo publiée : $(date '+%Y-%m-%d %H:%M') ==="
