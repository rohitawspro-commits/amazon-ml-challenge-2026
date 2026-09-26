#!/usr/bin/env bash
# Build <team_name>_submission.zip in the structure required by the challenge.
# Usage: ./package.sh <team_name>
set -euo pipefail
TEAM="${1:?usage: ./package.sh <team_name>}"
ROOT="$(cd "$(dirname "$0")" && pwd)"
STAGE="$(mktemp -d)/${TEAM}_submission"
mkdir -p "$STAGE/output" "$STAGE/code/business_entity_resolution"

cp "$ROOT/output/matching_results.tsv" "$ROOT/output/candidate_pairs.tsv" "$STAGE/output/"
cp -r "$ROOT/code/business_entity_resolution/src" "$STAGE/code/business_entity_resolution/"
cp "$ROOT/code/business_entity_resolution/README.md" "$ROOT/code/business_entity_resolution/requirements.txt" \
   "$STAGE/code/business_entity_resolution/"
cp "$ROOT/Documentation_template.md" "$STAGE/"
find "$STAGE" -name "__pycache__" -type d -prune -exec rm -rf {} +

( cd "$(dirname "$STAGE")" && zip -q -r "$ROOT/${TEAM}_submission.zip" "${TEAM}_submission" )
rm -rf "$(dirname "$STAGE")"
echo "wrote $ROOT/${TEAM}_submission.zip"
unzip -l "$ROOT/${TEAM}_submission.zip" | tail -n +1
