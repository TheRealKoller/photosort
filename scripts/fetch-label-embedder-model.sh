#!/usr/bin/env bash
# Laedt das gepinnte label_embedder.onnx-Modell-Asset (label_embedding.py, ADR
# specs/decisions/0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md Punkt 4) von
# HuggingFace herunter und verifiziert es gegen den bereits im Code hinterlegten SHA256-Hash -
# siehe specs/decisions/0033-modell-asset-download-statt-commit-label-embedder.md: das Asset
# (118.054.609 Bytes) ueberschreitet GitHubs 100-MiB-Hard-Limit fuer einen regulaeren Push und wird
# deshalb NICHT mehr committet, sondern bei jedem Docker-Image-Build, in CI und einmalig im
# lokalen Bare-Metal-Dev-Setup per verifiziertem Download bezogen (backend/Dockerfile,
# .github/workflows/ci.yml, docs/setup.md).
#
# Eigenstaendiges Bash-Skript, unabhaengig vom Python-Paket unter scripts/ (analog
# render-diagrams.sh - reines Download-/Verifikations-Wrapping, keine eigene Testsuite).
#
# Kein stiller Fallback, kein Weiterlaufen mit einer nicht verifizierten Datei: bricht mit
# Exit-Code != 0 ab, wenn Download oder Hash-Pruefung fehlschlagen (ADR 0033, Umsetzungspunkt 1).
# Idempotent: ueberspringt den Download, wenn die Datei bereits mit passendem Hash vorliegt.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
ASSETS_DIR="$SCRIPT_DIR/../backend/src/photosort/assets"
LABEL_EMBEDDING_MODULE="$SCRIPT_DIR/../backend/src/photosort/label_embedding.py"
TARGET_FILE="$ASSETS_DIR/label_embedder.onnx"
MODEL_URL="https://huggingface.co/Xenova/paraphrase-multilingual-MiniLM-L12-v2/resolve/main/onnx/model_int8.onnx"

# Der SHA256-Hash bleibt die verbindliche Integritaetsquelle in label_embedding.py
# (LABEL_EMBEDDER_ONNX_SHA256, ADR 0033 "Entscheidung") - hier NICHT ein zweites Mal fest verdrahtet,
# um eine kuenftige Modell-Aktualisierung nicht an zwei Stellen synchron halten zu muessen.
# sed statt "grep -P" (PCRE) - portabler, faellt nicht auf BSD-/macOS-grep ohne PCRE-Unterstuetzung
# zurueck (dieselbe Extraktion wird 1:1 im backend/Dockerfile-RUN-Schritt wiederverwendet, dort
# im schlanken Debian-Basisimage, wo dieselbe Portabilitaetsfrage gilt).
EXPECTED_SHA256="$(
  sed -n 's/^LABEL_EMBEDDER_ONNX_SHA256 = "\([0-9a-f]\{64\}\)"$/\1/p' "$LABEL_EMBEDDING_MODULE"
)"

if [ -z "$EXPECTED_SHA256" ]; then
  echo "Fehler: LABEL_EMBEDDER_ONNX_SHA256 konnte nicht aus $LABEL_EMBEDDING_MODULE gelesen werden." >&2
  exit 1
fi

verify_hash() {
  local actual
  actual="$(sha256sum "$TARGET_FILE" | cut -d' ' -f1)"
  [ "$actual" = "$EXPECTED_SHA256" ]
}

if [ -f "$TARGET_FILE" ] && verify_hash; then
  echo "label_embedder.onnx liegt bereits mit passendem SHA256-Hash vor, kein erneuter Download."
  exit 0
fi

mkdir -p "$ASSETS_DIR"
echo "Lade label_embedder.onnx von $MODEL_URL..."
curl -fsSL "$MODEL_URL" -o "$TARGET_FILE"

if ! verify_hash; then
  echo "Fehler: SHA256-Hash von $TARGET_FILE stimmt nicht mit LABEL_EMBEDDER_ONNX_SHA256 ueberein." >&2
  echo "Erwartet: $EXPECTED_SHA256" >&2
  echo "Erhalten: $(sha256sum "$TARGET_FILE" | cut -d' ' -f1)" >&2
  rm -f "$TARGET_FILE"
  exit 1
fi

echo "label_embedder.onnx erfolgreich heruntergeladen und verifiziert."
