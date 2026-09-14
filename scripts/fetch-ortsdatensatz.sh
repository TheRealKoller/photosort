#!/usr/bin/env bash
# Bezieht den lokalen Ortsdatensatz (GeoNames allCountries) fuer das Messkommando
# `python -m photosort.place_probe` (specs/features/0434-ortsnamen-fuer-events.md).
#
# EINMALIGER BEZUG, nicht je Lauf: Die Datei ist rund 400 MB gepackt und rund 1,5 GB entpackt.
# Sie liegt danach lokal, gehoert NICHT ins Repository und NICHT ins Docker-Image.
#
# KEIN FESTER, VORAB EINGETRAGENER HASH - und das ist eine Eigenschaft der Quelle, kein
# Versaeumnis: GeoNames erzeugt allCountries.zip naechtlich neu und veroeffentlicht ueberhaupt
# keine Pruefsummen (keine .md5/.sha256, keine Signatur). Es gibt damit weder einen stabilen
# Sollwert noch eine vertrauenswuerdige Quelle fuer einen; das Muster aus
# fetch-label-embedder-model.sh traegt dort nur, weil jene Modelldatei unveraenderlich und
# versioniert ist.
#
# STATTDESSEN: Der Hash entsteht BEIM ERSTBEZUG selbst und wird daneben abgelegt. Jeder spaetere
# Lauf prueft dagegen und bricht bei Abweichung LAUT ab - kein stiller Rueckfall auf den externen
# Weg. Das erkennt jede Veraenderung des ARCHIVS nach dem Erstbezug.
#
# WORAUF SICH DIE PRUEFUNG GENAU BEZIEHT - und worauf NICHT: Geprueft wird allCountries.zip, das
# BEZOGENE Archiv. Die entpackte allCountries.txt, die das Messkommando tatsaechlich liest, wird
# NICHT bei jedem Lauf erneut geprueft: sie misst rund 1,5 GB, und sie bei jedem Aufruf zu hashen
# oder neu zu entpacken kostete jedes Mal Minuten fuer einen Fall, der ohne Zutun nicht eintritt.
# Die Folge ist ausgeschrieben, damit sich niemand auf eine Zusage verlaesst, die hier nicht
# gegeben wird: Wird die .txt veraendert oder beschaedigt, waehrend das Archiv daneben intakt
# bleibt, faellt das hier NICHT auf.
#
# ABHILFE, falls daran je ein Zweifel besteht: die .txt loeschen und dieses Skript erneut laufen
# lassen. Es entpackt sie dann aus dem zuvor gegen den Hash geprueften Archiv neu.
#
# UNGESCHUETZT BLEIBT AUSDRUECKLICH DER ERSTBEZUG: Dort tragen allein HTTPS und das Vertrauen in
# GeoNames. Eine an der Quelle oder auf dem Weg veraenderte Datei wuerde als Sollwert uebernommen
# und von jeder Folgepruefung bestaetigt. Das ist ein bewusst akzeptiertes Restrisiko (Daniel,
# 2026-09-14) und getragen davon, dass der Schaden auf falsche Ortsnamen begrenzt ist: die Werte
# laufen durch dieselbe Sanitisierung und Laengengrenze wie jeder andere Fremdtext, steuern keinen
# Kontrollfluss ausserhalb der Event-Ueberschrift und erreichen keinen Secrets-, Auth- oder
# Bilddatenpfad.
#
# Lizenz: GeoNames steht unter CC BY 4.0. Die Namensnennung erfuellt die Anwendung sichtbar,
# sobald die Wegwahl auf diesen Datensatz faellt.
#
# Eigenstaendiges Bash-Skript, unabhaengig vom Python-Paket unter scripts/ (analog
# fetch-label-embedder-model.sh und render-diagrams.sh - reines Download-/Verifikations-Wrapping,
# keine eigene Testsuite).
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
ZIEL_VERZEICHNIS="${ORTSDATENSATZ_DIR:-$SCRIPT_DIR/../.ortsdatensatz}"
ARCHIV="$ZIEL_VERZEICHNIS/allCountries.zip"
DATENSATZ="$ZIEL_VERZEICHNIS/allCountries.txt"
HASH_DATEI="$ZIEL_VERZEICHNIS/allCountries.zip.sha256"
QUELLE="https://download.geonames.org/export/dump/allCountries.zip"

hash_der_datei() {
  sha256sum "$1" | cut -d' ' -f1
}

if [ -f "$ARCHIV" ] && [ -f "$HASH_DATEI" ]; then
  ERWARTET="$(cut -d' ' -f1 <"$HASH_DATEI")"
  TATSAECHLICH="$(hash_der_datei "$ARCHIV")"
  if [ "$ERWARTET" != "$TATSAECHLICH" ]; then
    echo "Fehler: $ARCHIV weicht vom beim Erstbezug gebildeten SHA256-Hash ab." >&2
    echo "Erwartet: $ERWARTET" >&2
    echo "Erhalten: $TATSAECHLICH" >&2
    echo "Die lokale Datei hat sich seit dem Erstbezug veraendert. Kein stiller Rueckfall:" >&2
    echo "Archiv und Hash-Datei von Hand loeschen und bewusst neu beziehen." >&2
    exit 1
  fi
  echo "allCountries.zip liegt vor und stimmt mit dem abgelegten Hash ueberein."
  echo "(Geprueft ist damit das ARCHIV. Die daneben liegende, entpackte allCountries.txt wird"
  echo " nicht erneut geprueft - bei Zweifeln loeschen und dieses Skript erneut aufrufen.)"
else
  if [ -f "$ARCHIV" ] || [ -f "$HASH_DATEI" ]; then
    echo "Fehler: Es liegt nur eines von beiden vor (Archiv bzw. Hash-Datei)." >&2
    echo "Ein Archiv ohne seinen Hash ist nicht pruefbar, ein Hash ohne Archiv sagt nichts." >&2
    echo "Beide Reste unter $ZIEL_VERZEICHNIS loeschen und neu beziehen." >&2
    exit 1
  fi
  mkdir -p "$ZIEL_VERZEICHNIS"
  echo "Erstbezug von $QUELLE (rund 400 MB)..."
  echo "HINWEIS: Der Erstbezug ist ungeschuetzt - es gibt bei GeoNames keinen Sollwert, gegen"
  echo "den er sich pruefen liesse. Ab hier traegt der selbst gebildete Hash jede Folgepruefung."
  curl -fsSL "$QUELLE" -o "$ARCHIV"
  hash_der_datei "$ARCHIV" >"$HASH_DATEI"
  echo "SHA256 gebildet und abgelegt: $(cut -d' ' -f1 <"$HASH_DATEI")"
fi

if [ ! -f "$DATENSATZ" ]; then
  echo "Entpacke allCountries.txt (rund 1,5 GB)..."
  unzip -o -q "$ARCHIV" allCountries.txt -d "$ZIEL_VERZEICHNIS"
fi

echo
echo "Fertig. Das Messkommando liest den Datensatz ueber:"
echo "  python -m photosort.place_probe --project-id <N> --ortsdatensatz $DATENSATZ"
