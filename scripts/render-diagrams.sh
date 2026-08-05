#!/usr/bin/env bash
# Rendert alle D2-Diagramm-Quellen unter specs/diagrams/*.d2 zu SVGs (--sketch-Modus).
# Siehe ADR specs/decisions/0013-diagram-tooling-d2.md und
# Feature-Spec specs/features/0018-diagram-tooling-migration.md.
#
# Eigenständiges Bash-Skript, unabhängig vom Python-Paket unter scripts/
# (reines Binary-Wrapping, keine eigene Testsuite - siehe Teststrategie in der Spec).
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
DIAGRAMS_DIR="$SCRIPT_DIR/../specs/diagrams"

if ! command -v d2 >/dev/null 2>&1; then
  echo "Fehler: 'd2' wurde nicht im PATH gefunden." >&2
  echo "Installationsanleitung: https://d2lang.com/tour/install/" >&2
  exit 1
fi

# nullglob sorgt dafuer, dass die Schleife unten bei keinem Treffer ueber ein
# leeres Array laeuft statt einmal ueber den literalen String "*.d2".
shopt -s nullglob
diagram_files=("$DIAGRAMS_DIR"/*.d2)

if [ "${#diagram_files[@]}" -eq 0 ]; then
  echo "Keine .d2-Dateien in $DIAGRAMS_DIR gefunden, nichts zu rendern."
  exit 0
fi

for f in "${diagram_files[@]}"; do
  svg="${f%.d2}.svg"
  echo "Rendere $f -> $svg"
  d2 --sketch "$f" "$svg"
done

echo "Fertig."
