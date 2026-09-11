#!/usr/bin/env bash
#
# Formatiert das ganze Repository in einem Aufruf: `ruff format` in backend/ und scripts/,
# `npm run format` in frontend/ und e2e/.
#
# Begruendung und Geltungsbereich: specs/decisions/0078-maschinelle-formatierung-ruff-format-
# und-prettier.md (Abschnitt 12) und specs/features/0400-einheitliche-code-formatierung.md
# (Abschnitt 9). Dieses Skript enthaelt bewusst KEINE Stiloptionen und KEINE Dateilisten - es
# ruft die beiden Werkzeuge mit ihrer jeweiligen Konfigurationsdatei auf. Alles, was den Stil
# oder den Geltungsbereich bestimmt, steht dort und nur dort: in beiden pyproject.toml
# ([tool.ruff], [tool.ruff.format]) und in /.prettierrc.json plus /.prettierignore. Waere es
# hier ein zweites Mal angegeben, koennte der lokale Lauf von der CI-Pruefung abweichen, ohne
# dass es auffaellt.
#
# Es entsteht ausdruecklich KEIN Automatismus: Dieses Skript wird von Hand aufgerufen. Kein
# Git-Hook, kein Editor-Hook, kein npm-Lebenszyklus-Skript ruft es. Ein Werkzeug, das beim
# Commit still Dateien umschreibt, veraendert einen Stand, den der Aufrufer gerade geprueft hat.
#
# Zwei Vorbedingungen werden je Baum geprueft, und ZWAR ALLE VIER, BEVOR der erste schreibende
# Aufruf faellt - sonst bliebe nach einem Abbruch ein halb formatierter Baum zurueck:
#
#   1. Die aufgerufene `ruff`-Version stimmt mit dem Pin der pyproject.toml des Baums ueberein.
#      Der Pin wird gelesen, nicht hier wiederholt; es gibt keinen zweiten Ort, an dem die Zahl
#      steht. Geprueft wird je Baum getrennt, weil backend/ und scripts/ eigene .venv haben -
#      der Fall lag im Repositorium real vor (0.16.1 bzw. 0.16.2 unter derselben Angabe).
#   2. node_modules liegt in frontend/ und e2e/. Fuer Prettier braucht es keine
#      Versions-Gegenprobe: `npm ci` installiert genau das, was im Lockfile steht - das ist die
#      Fixierung selbst.
#
# Sicherheitskonzept S4: Der aus der pyproject.toml gelesene Wert wird verankert und
# zeichenklassenbegrenzt gelesen (Vorbild: der Schritt "Read pinned label-embedder model hash"
# in .github/workflows/ci.yml), ein leeres oder mehrdeutiges Leseergebnis bricht ab statt
# weiterzulaufen, und der Wert wird AUSSCHLIESSLICH verglichen - nie in eine Kommandozeile, nie
# in einen Installationsaufruf, nie als Glob- oder Regex-Muster.
#
# Verhalten zugesichert durch scripts/tests/test_format_sh.py.
#
# Ausgaenge:
#   0   alle vier Baeume formatiert.
#   1   Vorbedingung verletzt: nichts wurde umgeschrieben, Begruendung auf stderr.

set -euo pipefail

SKRIPT_VERZEICHNIS="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
readonly REPO_WURZEL="${SKRIPT_VERZEICHNIS%/*}"

# Das Ziel haengt am Ablageort dieser Datei, nicht am Arbeitsverzeichnis des Aufrufers - das
# Skript ist aus jedem Verzeichnis heraus aufrufbar und formatiert immer dieselben vier Baeume.
readonly PYTHON_BAEUME=(backend scripts)
readonly TS_BAEUME=(frontend e2e)

abbruch() {
    printf 'format.sh: %s\n' "$1" >&2
    exit 1
}

# Liest den ruff-Pin aus der pyproject.toml eines Baums. Verankert und zeichenklassenbegrenzt:
# Die Zeile muss genau die Form `"ruff==<ziffern und punkte>",` haben. Damit faellt jede
# unscharfe Angabe durch (`"ruff"`, `"ruff>=0.7"`, `"ruff==0.16.*"`), und eine auskommentierte
# Zeile zaehlt nicht mit, weil vor dem Anfuehrungszeichen nur Leerraum stehen darf.
pin_zeilen() {
    sed -n 's/^[[:space:]]*"ruff==\([0-9][0-9.]*\)",\{0,1\}$/\1/p' "$1"
}

# Liest die Versionsnummer aus der Ausgabe von `ruff --version` ("ruff 0.16.4"). Ebenso
# verankert - eine Fremdausgabe oder eine leere Ausgabe liefert nichts und bricht unten ab.
versions_zeilen() {
    sed -n 's/^ruff \([0-9][0-9.]*\)$/\1/p'
}

genau_eine_zeile() {
    [ "$(printf '%s' "$1" | grep -c '' || true)" = "1" ]
}

# --- Phase 1: alle Vorbedingungen, bevor irgendetwas geschrieben wird -------------------------

declare -a RUFF_BINARIES=()

for baum in "${PYTHON_BAEUME[@]}"; do
    pyproject="$REPO_WURZEL/$baum/pyproject.toml"
    [ -f "$pyproject" ] || abbruch "$baum/pyproject.toml fehlt - kein Python-Baum an dieser Stelle."

    pin="$(pin_zeilen "$pyproject")"
    if [ -z "$pin" ]; then
        abbruch "$baum/pyproject.toml nennt keine exakte ruff-Version in der Form \"ruff==X.Y.Z\". Ohne lesbaren Pin ist der Versionsvergleich bedeutungslos, und das Skript formatiert mit irgendeiner Version."
    fi
    if ! genau_eine_zeile "$pin"; then
        abbruch "$baum/pyproject.toml nennt mehrere ruff-Versionen ($(printf '%s' "$pin" | tr '\n' ' ')). Welche gilt, ist nicht entscheidbar."
    fi

    # Der Baum bringt seine eigene .venv mit; die ist massgeblich, nicht das, was zufaellig auf
    # dem PATH liegt. Genau daran haengt der Fall, den diese Pruefung abfangen soll.
    ruff_binary="$REPO_WURZEL/$baum/.venv/bin/ruff"
    if [ ! -x "$ruff_binary" ]; then
        ruff_binary="$(command -v ruff || true)"
    fi
    if [ -z "$ruff_binary" ]; then
        abbruch "Kein ruff fuer $baum gefunden - weder in $baum/.venv/bin/ noch im PATH. Die Entwicklungsabhaengigkeiten dieses Baums installieren, siehe docs/setup.md."
    fi

    if ! rohausgabe="$("$ruff_binary" --version 2>/dev/null)"; then
        abbruch "'$ruff_binary --version' ist fehlgeschlagen. Die Entwicklungsabhaengigkeiten von $baum neu installieren, siehe docs/setup.md."
    fi
    version="$(printf '%s\n' "$rohausgabe" | versions_zeilen)"
    if [ -z "$version" ] || ! genau_eine_zeile "$version"; then
        abbruch "'$ruff_binary --version' liefert keine verwertbare Versionsangabe (Ausgabe: '$rohausgabe'). Ein Vergleich gegen einen Leerstring besteht immer und waere bedeutungslos. Die Entwicklungsabhaengigkeiten von $baum neu installieren, siehe docs/setup.md."
    fi

    if [ "$version" != "$pin" ]; then
        abbruch "$baum: ruff $version ist aufrufbar, $baum/pyproject.toml verlangt $pin. Mit der falschen Version entsteht genau der Diff, den die CI-Pruefung spaeter nicht bestaetigt. Die Entwicklungsabhaengigkeiten dieses Baums neu installieren, siehe docs/setup.md."
    fi

    RUFF_BINARIES+=("$ruff_binary")
done

for baum in "${TS_BAEUME[@]}"; do
    if [ ! -d "$REPO_WURZEL/$baum/node_modules" ]; then
        abbruch "$baum/node_modules fehlt. Erst 'npm ci' in $baum/ ausfuehren (nicht 'npm install' - das Lockfile ist die Fixierung), dann erneut formatieren."
    fi
done

# --- Phase 2: formatieren ----------------------------------------------------------------------

for index in "${!PYTHON_BAEUME[@]}"; do
    baum="${PYTHON_BAEUME[$index]}"
    printf 'Formatiere %s/ ...\n' "$baum"
    (cd "$REPO_WURZEL/$baum" && "${RUFF_BINARIES[$index]}" format .)
done

for baum in "${TS_BAEUME[@]}"; do
    printf 'Formatiere %s/ ...\n' "$baum"
    (cd "$REPO_WURZEL/$baum" && npm run format)
done

echo "Fertig."
