#!/usr/bin/env bash
#
# Prueft das ganze Repository in einem Aufruf: Formatierung, Lint und Typen in backend/,
# scripts/, frontend/ und e2e/ - zehn Befehle, dieselben wie in .github/workflows/ci.yml.
#
# Siehe specs/decisions/0081-frueheres-qualitaets-feedback-ein-pruefbefehl-und-ein-pruefpunkt-je-
# tdd-einheit.md. Verhalten zugesichert durch scripts/tests/test_check_sh.py.

set -euo pipefail

SKRIPT_VERZEICHNIS="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
readonly REPO_WURZEL="${SKRIPT_VERZEICHNIS%/*}"

readonly FRONTEND_SKRIPTE=(format:check lint typecheck)
readonly E2E_SKRIPTE=(format:check typecheck)
readonly PRUEFUNGEN_GESAMT=10

GEPRUEFT=0
declare -a BEFUNDE=()
declare -a UNGEPRUEFT=()

# Der Baum bringt seine eigene .venv mit; die ist massgeblich, nicht das, was zufaellig auf dem
# PATH liegt. Der PATH-Rueckfall ist derselbe wie in format.sh und in der Spec als bewusst
# getragenes Restrisiko benannt.
werkzeug_binary() {
    local kandidat="$REPO_WURZEL/$1/.venv/bin/$2"
    if [ -x "$kandidat" ]; then
        printf '%s' "$kandidat"
        return
    fi
    command -v "$2" || true
}

# Liest den ruff-Pin aus der pyproject.toml eines Baums. Verankert und zeichenklassenbegrenzt:
# Die Zeile muss genau die Form `"ruff==<ziffern und punkte>",` haben. Damit faellt jede
# unscharfe Angabe durch (`"ruff"`, `"ruff>=0.7"`, `"ruff==0.16.*"`), und eine auskommentierte
# Zeile zaehlt nicht mit, weil vor dem Anfuehrungszeichen nur Leerraum stehen darf.
pin_zeilen() {
    sed -n 's/^[[:space:]]*"ruff==\([0-9][0-9.]*\)",\{0,1\}$/\1/p' "$1"
}

# Liest die Versionsnummer aus der Ausgabe von `ruff --version` ("ruff 0.16.4"). Ebenso
# verankert - eine Fremdausgabe oder eine leere Ausgabe liefert nichts und nimmt den Baum unten
# aus dem Lauf.
versions_zeilen() {
    sed -n 's/^ruff \([0-9][0-9.]*\)$/\1/p'
}

genau_eine_zeile() {
    [ "$(printf '%s' "$1" | grep -c '' || true)" = "1" ]
}

# Liest die Schluessel des scripts-Blocks einer package.json - verankert,
# zeichenklassenbegrenzt und auf den Block begrenzt. Ausgewertet wird ausschliesslich die
# ANWESENHEIT eines Namens; der gelesene Wert wird nie benutzt. Die Begrenzung auf den Block ist
# nicht Kosmetik: Ein gleichnamiger Schluessel unter "devDependencies" liesse ein entferntes
# Skript sonst als vorhanden durchgehen.
npm_skript_namen() {
    sed -n '/^[[:space:]]*"scripts"[[:space:]]*:[[:space:]]*{[[:space:]]*$/,/^[[:space:]]*}/ {
        s/^[[:space:]]*"\([a-zA-Z][a-zA-Z0-9:._-]*\)"[[:space:]]*:.*$/\1/p
    }' "$1"
}

melde_ungeprueft() {
    UNGEPRUEFT+=("$1: $2")
}

# Stellt die ruff-Vorbedingung eines Python-Baums fest. Setzt PRUEF_BINARY und PRUEF_GRUND; ein
# nicht-leerer Grund nimmt den Baum aus dem Lauf.
ruff_vorbedingung() {
    local baum="$1"
    PRUEF_BINARY=""
    PRUEF_GRUND=""

    local pyproject="$REPO_WURZEL/$baum/pyproject.toml"
    if [ ! -f "$pyproject" ]; then
        PRUEF_GRUND="$baum/pyproject.toml fehlt - kein Python-Baum an dieser Stelle."
        return
    fi

    local pin
    pin="$(pin_zeilen "$pyproject")"
    if [ -z "$pin" ]; then
        PRUEF_GRUND="$baum/pyproject.toml nennt keine exakte ruff-Version in der Form \"ruff==X.Y.Z\". Ohne lesbaren Pin ist der Versionsvergleich bedeutungslos, und ein gruenes Ergebnis sagt nichts ueber die CI. Die Entwicklungsabhaengigkeiten dieses Baums installieren, siehe docs/setup.md."
        return
    fi
    if ! genau_eine_zeile "$pin"; then
        PRUEF_GRUND="$baum/pyproject.toml nennt mehrere ruff-Versionen ($(printf '%s' "$pin" | tr '\n' ' ')). Welche gilt, ist nicht entscheidbar."
        return
    fi

    local ruff_binary
    ruff_binary="$(werkzeug_binary "$baum" ruff)"
    if [ -z "$ruff_binary" ]; then
        PRUEF_GRUND="Kein ruff fuer $baum gefunden - weder in $baum/.venv/bin/ noch im PATH. Die Entwicklungsabhaengigkeiten dieses Baums installieren, siehe docs/setup.md."
        return
    fi

    local rohausgabe
    if ! rohausgabe="$("$ruff_binary" --version 2>/dev/null)"; then
        PRUEF_GRUND="'$ruff_binary --version' ist fehlgeschlagen. Die Entwicklungsabhaengigkeiten von $baum neu installieren, siehe docs/setup.md."
        return
    fi
    local version
    version="$(printf '%s\n' "$rohausgabe" | versions_zeilen)"
    if [ -z "$version" ] || ! genau_eine_zeile "$version"; then
        PRUEF_GRUND="'$ruff_binary --version' liefert keine verwertbare Versionsangabe (Ausgabe: '$rohausgabe'). Ein Vergleich gegen einen Leerstring besteht immer und waere bedeutungslos. Die Entwicklungsabhaengigkeiten von $baum neu installieren, siehe docs/setup.md."
        return
    fi

    if [ "$version" != "$pin" ]; then
        PRUEF_GRUND="$baum: ruff $version ist aufrufbar, $baum/pyproject.toml verlangt $pin. Eine andere Version faellt anders aus als die CI-Pruefung; ein gruenes Ergebnis von hier sagt dann nichts. Die Entwicklungsabhaengigkeiten dieses Baums neu installieren, siehe docs/setup.md."
        return
    fi

    PRUEF_BINARY="$ruff_binary"
}

# Stellt die npm-Vorbedingungen eines TypeScript-Baums fest: node_modules, die aufgerufenen
# Skriptnamen. Setzt PRUEF_GRUND.
npm_vorbedingung() {
    local baum="$1"
    shift
    PRUEF_GRUND=""

    if [ ! -d "$REPO_WURZEL/$baum/node_modules" ]; then
        PRUEF_GRUND="$baum/node_modules fehlt. Erst 'npm ci' in $baum/ ausfuehren (nicht 'npm install' - das Lockfile ist die Fixierung), dann erneut pruefen."
        return
    fi

    local paket="$REPO_WURZEL/$baum/package.json"
    if [ ! -f "$paket" ]; then
        PRUEF_GRUND="$baum/package.json fehlt - kein TypeScript-Baum an dieser Stelle."
        return
    fi

    local namen
    namen="$(npm_skript_namen "$paket")"
    local skript
    for skript in "$@"; do
        if ! printf '%s\n' "$namen" | grep -Fxq -- "$skript"; then
            PRUEF_GRUND="$baum/package.json kennt im scripts-Block kein '$skript'. Ein fehlgeschlagener Aufruf waere hier von einem echten Befund nicht zu unterscheiden."
            return
        fi
    done
}

# Ein Prueflauf. Der Zaehler steht hier und nur hier: Ausgang 0 verlangt, dass alle zehn
# tatsaechlich gelaufen sind - nicht, dass nichts gemeldet wurde.
pruefe() {
    local baum="$1"
    shift
    local bezeichnung
    bezeichnung="$(basename -- "$1") ${*:2}"
    if ! (cd "$REPO_WURZEL/$baum" && "$@"); then
        BEFUNDE+=("$baum: $bezeichnung")
    fi
    GEPRUEFT=$((GEPRUEFT + 1))
}

# --- Phase 1: Vorbedingungen, alle vier Baeume, bevor der erste Pruefbefehl laeuft -------------
#
# Strenger als noetig waere (je Baum vor dessen erstem Aufruf) und bewusst so: Wer erst am Ende
# erfaehrt, dass zwei Baeume fehlten, hat die Ausgabe dazwischen unter falscher Annahme gelesen.
# Ein Baum mit verletzter Vorbedingung wird uebersprungen und ausdruecklich als "nicht geprueft"
# gemeldet - er erhoeht den Zaehler nicht und kann deshalb nicht als Ausgang 0 durchgehen.

PRUEF_BINARY=""
PRUEF_GRUND=""

BACKEND_RUFF=""
BACKEND_MYPY=""
SCRIPTS_RUFF=""
NPM=""
FRONTEND_PRUEFBAR="nein"
E2E_PRUEFBAR="nein"

ruff_vorbedingung backend
BACKEND_RUFF="$PRUEF_BINARY"
if [ -n "$PRUEF_GRUND" ]; then
    melde_ungeprueft backend "$PRUEF_GRUND"
else
    BACKEND_MYPY="$(werkzeug_binary backend mypy)"
    if [ -z "$BACKEND_MYPY" ]; then
        BACKEND_RUFF=""
        melde_ungeprueft backend "Kein mypy fuer backend gefunden - weder in backend/.venv/bin/ noch im PATH. Ein fehlgeschlagener Aufruf waere hier von echten Typfehlern nicht zu unterscheiden. Die Entwicklungsabhaengigkeiten dieses Baums installieren, siehe docs/setup.md."
    fi
fi

ruff_vorbedingung scripts
SCRIPTS_RUFF="$PRUEF_BINARY"
if [ -n "$PRUEF_GRUND" ]; then
    melde_ungeprueft scripts "$PRUEF_GRUND"
fi

NPM="$(command -v npm || true)"
if [ -z "$NPM" ]; then
    melde_ungeprueft frontend "Kein npm im PATH. Node installieren, siehe docs/setup.md."
    melde_ungeprueft e2e "Kein npm im PATH. Node installieren, siehe docs/setup.md."
else
    npm_vorbedingung frontend "${FRONTEND_SKRIPTE[@]}"
    if [ -n "$PRUEF_GRUND" ]; then
        melde_ungeprueft frontend "$PRUEF_GRUND"
    else
        FRONTEND_PRUEFBAR="ja"
    fi

    npm_vorbedingung e2e "${E2E_SKRIPTE[@]}"
    if [ -n "$PRUEF_GRUND" ]; then
        melde_ungeprueft e2e "$PRUEF_GRUND"
    else
        E2E_PRUEFBAR="ja"
    fi
fi

if [ "${#UNGEPRUEFT[@]}" -gt 0 ]; then
    for eintrag in "${UNGEPRUEFT[@]}"; do
        printf 'Nicht geprueft - %s\n' "$eintrag" >&2
    done
fi

# --- Phase 2: pruefen --------------------------------------------------------------------------
#
# Aufgerufen wird dasselbe Binary, dessen Version Phase 1 gelesen hat - geprueft und aufgerufen
# duerfen nicht auseinanderfallen. Ein roter Baum bricht nichts ab: Jeder Aufruf steht als
# `if ! ...` in pruefe(), nie als Rueckgabewert hinter einem Befehl.

if [ -n "$BACKEND_RUFF" ]; then
    pruefe backend "$BACKEND_RUFF" format --check .
    pruefe backend "$BACKEND_RUFF" check .
    pruefe backend "$BACKEND_MYPY" src
fi

if [ -n "$SCRIPTS_RUFF" ]; then
    pruefe scripts "$SCRIPTS_RUFF" format --check .
    pruefe scripts "$SCRIPTS_RUFF" check .
fi

if [ "$FRONTEND_PRUEFBAR" = "ja" ]; then
    for skript in "${FRONTEND_SKRIPTE[@]}"; do
        pruefe frontend "$NPM" run "$skript"
    done
fi

if [ "$E2E_PRUEFBAR" = "ja" ]; then
    for skript in "${E2E_SKRIPTE[@]}"; do
        pruefe e2e "$NPM" run "$skript"
    done
fi

# --- Bilanz ------------------------------------------------------------------------------------

if [ "${#UNGEPRUEFT[@]}" -gt 0 ]; then
    printf '\nNicht geprueft:\n'
    for eintrag in "${UNGEPRUEFT[@]}"; do
        printf '  - %s\n' "$eintrag"
    done
fi

if [ "${#BEFUNDE[@]}" -gt 0 ]; then
    printf '\nBefunde:\n'
    for eintrag in "${BEFUNDE[@]}"; do
        printf '  - %s\n' "$eintrag"
    done
fi

printf '\n%d von %d Pruefungen gelaufen.\n' "$GEPRUEFT" "$PRUEFUNGEN_GESAMT"

if [ "${#BEFUNDE[@]}" -gt 0 ]; then
    exit 2
fi
if [ "$GEPRUEFT" -ne "$PRUEFUNGEN_GESAMT" ]; then
    exit 1
fi

printf 'Format, Lint und Typen sauber. Tests, Coverage-Gate, Build und die uebrigen\n'
printf 'CI-Pruefungen sind hier nicht enthalten - das ist keine Zusage ueber die CI.\n'
