#!/bin/zsh
# Mise à jour quotidienne de Traçabilité Québec.
#
# 1. Télécharge les nouveaux fichiers de données ouvertes du SEAO (les fichiers
#    déjà présents sont sautés — seul le nouveau est transféré).
# 2. Reconstruit la base au complet dans un fichier temporaire, en ordre
#    chronologique strict (garantit que l'état le plus récent de chaque
#    contrat a toujours le dernier mot, même quand un fichier mensuel vient
#    remplacer des fichiers hebdomadaires).
# 3. Remplace la base d'un seul coup : le site n'est jamais cassé pendant la
#    mise à jour, et son cache se rafraîchit automatiquement.
#
# Journal : data/maj.log

set -e
cd "$(dirname "$0")"

PYTHON=".venv/bin/python"
mkdir -p data
exec >> data/maj.log 2>&1

echo ""
echo "=== Mise à jour du $(date '+%Y-%m-%d %H:%M') ==="

"$PYTHON" pipeline/download.py --depuis 2025-01

rm -f data/seao_build.db
SEAO_DB="$PWD/data/seao_build.db" "$PYTHON" pipeline/ingest.py
SEAO_DB="$PWD/data/seao_build.db" "$PYTHON" pipeline/analyze.py
mv -f data/seao_build.db data/seao.db

echo "=== Terminé : $(date '+%Y-%m-%d %H:%M') ==="
