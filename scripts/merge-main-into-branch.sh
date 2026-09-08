#!/usr/bin/env bash
#
# Uebernimmt den aktuellen Stand von main in den gerade ausgecheckten Feature-Branch.
#
# Aufgerufen von .claude/skills/ship-feature/SKILL.md an zwei Zeitpunkten (Schritt 6 vor dem
# Push, Schritt 8 als erste Handlung vor der Finalisierung). Hintergrund und Begruendung:
# specs/decisions/0063-abgleich-mit-main-als-getestetes-lokales-skript-merge-statt-rebase.md
# und specs/features/0338-abgleich-mit-main-vor-der-freigabe.md.
#
# Keine Argumente: "origin" und "main" stehen als Literale hier, gearbeitet wird im Repositorium
# des aktuellen Arbeitsverzeichnisses auf dem aktuell ausgecheckten Branch. Das Ziel wird nie aus
# dem Ablageort dieser Datei abgeleitet - kein "cd $(dirname "$0")".
#
# Ausgaenge:
#   0   main ist bereits enthalten. Kein Merge abgesetzt, keine Ausgabe auf stdout und stderr.
#   10  main sauber uebernommen: genau ein neuer Merge-Commit, Arbeitsverzeichnis sauber.
#   20  Konflikt, mindestens ein Pfad unmerged: Merge steht offen (MERGE_HEAD), Konfliktpfade
#       auf stdout, eine Zeile je Pfad.
#   30  Vorbedingung verletzt oder Umgebung nicht in Ordnung: Zustand unveraendert, Begruendung
#       auf stderr.
#
# Was dieses Skript nie tut (zugesichert durch scripts/tests/test_main_abgleich_verdrahtung.py):
# es schreibt nichts zum Remote zurueck, es schreibt keine bestehenden Commits um, und es checkt
# main nie aus. Es enthaelt deshalb weder einen Push noch ein Rebase, weder ein Nachbessern des
# letzten Commits noch ein hartes Zuruecksetzen.
#
# Alle Entscheidungen fallen an Exit-Codes und Dateizustaenden, nie an Ausgabetexten von git -
# die sind uebersetzbar und formulierungsabhaengig.

set -euo pipefail

# Sicherheitskonzept, Bedrohung 1: "keine Argumente" bindet das Ziel nicht. Mit gesetztem
# GIT_DIR/GIT_WORK_TREE meldet git den Branch eines *anderen* Repositoriums, und ueber
# GIT_CONFIG_COUNT laesst sich core.hooksPath unterschieben. GIT_AUTHOR_*/GIT_COMMITTER_* und
# GIT_CONFIG_GLOBAL bleiben ausdruecklich stehen (Identitaet bzw. Test-Isolation).
unset GIT_DIR GIT_WORK_TREE GIT_COMMON_DIR GIT_INDEX_FILE GIT_OBJECT_DIRECTORY \
    GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_CONFIG_COUNT

readonly REMOTE="origin"
readonly HAUPTZWEIG="main"
readonly MERGE_NACHRICHT="chore: Stand von main in den Feature-Branch übernehmen"

readonly EXIT_ENTHALTEN=0
readonly EXIT_UEBERNOMMEN=10
readonly EXIT_KONFLIKT=20
readonly EXIT_VORBEDINGUNG=30

# Selbst erzeugter Text, nie rohe git-Ausgabe: Die Meldung landet im Chat-Bericht und in einer
# SendMessage; ein credential-behafteter Remote waere darin ein Secret-Leck (Bedrohung 5).
abbruch() {
    printf 'merge-main-into-branch: %s\n' "$1" >&2
    exit "$EXIT_VORBEDINGUNG"
}

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    abbruch "das aktuelle Arbeitsverzeichnis liegt in keinem Git-Arbeitsbaum."
fi

zweig="$(git symbolic-ref --quiet --short HEAD 2>/dev/null || true)"
if [[ -z "$zweig" ]]; then
    abbruch "losgeloester HEAD. Ein Merge hier hinterliesse einen Commit, den kein Ref haelt."
fi

if [[ "$zweig" == "$HAUPTZWEIG" ]]; then
    abbruch "'$HAUPTZWEIG' ist ausgecheckt. Der Abgleich laeuft ausschliesslich auf einem Feature-Branch."
fi

# Unversionierte Dateien blockieren bewusst nicht (AK 10): Ein Entwicklungslauf hat fast immer
# Streudateien. Kollidiert eine davon tatsaechlich, verweigert git den Merge von sich aus.
if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
    abbruch "Arbeitsverzeichnis nicht sauber (gestagte oder ungestagte Aenderung an einer verfolgten Datei). Erst committen, dann abgleichen."
fi

if ! git remote get-url "$REMOTE" >/dev/null 2>&1; then
    abbruch "kein Remote '$REMOTE' konfiguriert."
fi

# Die Refspec zieht den *lokalen* main-Ref mit. Ohne sie bliebe die Merge-Basis auf dem alten
# Stand stehen, und "git diff main...HEAD" zeigte ab hier den Feature-Diff plus alles
# zwischenzeitlich auf main Passierte - an allen sechs Stellen der Review-Phase.
# Ein Fehlschlag hat drei moegliche Ursachen (Remote nicht erreichbar, dort kein main, main
# lokal nicht vorspulbar). Unterschieden werden sie hier bewusst nicht: Das ginge nur ueber den
# Meldungstext von git, und der ist uebersetzbar.
if ! git fetch --quiet "$REMOTE" "$HAUPTZWEIG:$HAUPTZWEIG" >/dev/null 2>&1; then
    abbruch "'$HAUPTZWEIG' konnte nicht von '$REMOTE' geholt werden: Remote nicht erreichbar, '$HAUPTZWEIG' dort nicht vorhanden, oder '$HAUPTZWEIG' lokal nicht vorspulbar (umgeschrieben). Ein Fall fuer Daniel, nicht fuer eine Korrektur nebenbei."
fi

# Der No-Op wird gerechnet, nicht gelesen - und ausschliesslich Rueckgabe 0 heisst "enthalten".
# Rueckgabe 1 heisst "nicht enthalten", 128 heisst "unbekanntes Objekt/kaputtes Repositorium"
# (Bedrohung 2: still falsch sein kann allein dieser Ausgang).
vorfahre_rueckgabe=0
git merge-base --is-ancestor "$HAUPTZWEIG" HEAD || vorfahre_rueckgabe=$?

if [[ "$vorfahre_rueckgabe" -eq 0 ]]; then
    exit "$EXIT_ENTHALTEN"
fi

if [[ "$vorfahre_rueckgabe" -ne 1 ]]; then
    abbruch "'git merge-base --is-ancestor' meldete Rueckgabe $vorfahre_rueckgabe. Weder 'enthalten' noch 'nicht enthalten' - hier wurde nichts gemessen."
fi

# --no-ff sichert zu, dass der bisherige Kopf immer erster Elternteil des neuen bleibt (AK 4).
# Ohne es schoebe ein Vorspulen den Feature-Branch stillschweigend auf main und leerte den
# Pull Request.
merge_rueckgabe=0
git merge --no-ff --no-edit -m "$MERGE_NACHRICHT" "$HAUPTZWEIG" >/dev/null 2>&1 ||
    merge_rueckgabe=$?

if [[ "$merge_rueckgabe" -eq 0 ]]; then
    exit "$EXIT_UEBERNOMMEN"
fi

# AK 11: "Merge-Rueckgabe ungleich 0" ist nicht gleich "Konflikt". Ein pre-merge-commit-Hook
# (oder commit.gpgsign ohne Schluessel) laesst git merge scheitern, MERGE_HEAD existieren - und
# hinterlaesst null Pfade im Konfliktzustand.
konfliktpfade="$(git -c core.quotePath=false -c diff.relative=false diff --name-only --diff-filter=U)"

if [[ -n "$konfliktpfade" ]]; then
    printf '%s\n' "$konfliktpfade"
    exit "$EXIT_KONFLIKT"
fi

git merge --abort >/dev/null 2>&1 || true
abbruch "'git merge' scheiterte mit Rueckgabe $merge_rueckgabe, ohne einen Pfad im Konfliktzustand zu hinterlassen (Hook, Signatur oder Arbeitsbaum-Kollision). Der Merge wurde zurueckgenommen."
