#!/usr/bin/env bash
#
# Uebernimmt den aktuellen Stand von main in den gerade ausgecheckten Feature-Branch.
#
# Aufgerufen von .claude/skills/ship-feature/SKILL.md an zwei Zeitpunkten (Schritt 6 vor dem
# Push, Schritt 8 als erste Handlung vor der Finalisierung).
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
# Dieses Skript fasst refs/heads/main NIE an - es liest ihn nicht und schreibt ihn erst recht
# nicht. Geholt wird ausschliesslich in den Remote-Tracking-Namensraum, gemerged wird der
# Tracking-Ref, und die Vergleichsbasis der Review-Phase ist entsprechend "origin/main...HEAD".
# Grund: Hintergrund-Laeufe arbeiten in einem eigenen Arbeitsbaum unter .claude/worktrees/,
# waehrend der Haupt-Checkout meist main ausgecheckt hat. "git fetch origin main:main"
# verweigert in dieser Lage gemessen den Dienst (Exit 128) - die Verweigerung gilt dem Ref, nicht
# dem Verzeichnis, und sie tritt auf, sobald main in irgendeinem Arbeitsbaum desselben
# Repositoriums ausgecheckt ist. Das Ausweichen ueber "git update-ref refs/heads/main" scheidet
# aus: Der Ref wanderte, waehrend Index und Arbeitsbaum des Haupt-Checkouts stehen blieben.
#
# Die Refspec steht ausgeschrieben und voll qualifiziert da, nicht als "git fetch origin main":
# Ein lokaler Branch namens "origin/main" wuerde einen unqualifizierten Namen sonst auf sich
# ziehen (gemessen: git loest dann auf refs/heads/origin/main auf und warnt nur), und die
# No-Op-Rechnung meldete "bereits enthalten" fuer einen Stand, den dieses Skript nie geholt hat.
# Das fuehrende "+" der Refspec ist kein "--force" auf einen Branch: Es betrifft ausschliesslich
# einen Ref unterhalb von refs/remotes/ und ist gegenueber dem Remote rein lesend. Weil es die
# von git sonst durchgesetzte Vorspul-Pruefung aufhebt, wird das Umschreiben von main auf origin
# stattdessen ausdruecklich gemessen (siehe Umschreib-Pruefung unten).
#
# Was dieses Skript nie tut (zugesichert durch scripts/tests/test_main_abgleich_verdrahtung.py):
# es schreibt nichts zum Remote zurueck, es schreibt keine bestehenden Commits um, es schreibt
# keinen Ref unterhalb von refs/heads/, und es checkt main nie aus. Es enthaelt deshalb weder
# einen Push noch ein Rebase, weder ein Nachbessern des letzten Commits noch ein hartes
# Zuruecksetzen.
#
# Alle Entscheidungen fallen an Exit-Codes und Dateizustaenden, nie an Ausgabetexten von git -
# die sind uebersetzbar und formulierungsabhaengig. Jedes Kommando, dessen Rueckgabe ausgewertet
# wird, verschluckt dabei seine eigene Ausgabe: Der Meldungskanal traegt ausschliesslich selbst
# erzeugten Text, nie eine rohe git-Zeile.

set -euo pipefail

# Sicherheitskonzept, Bedrohung 1: "keine Argumente" bindet das Ziel nicht. Mit gesetztem
# GIT_DIR/GIT_WORK_TREE meldet git den Branch eines *anderen* Repositoriums, und ueber
# GIT_CONFIG_COUNT laesst sich core.hooksPath unterschieben. GIT_AUTHOR_*/GIT_COMMITTER_* und
# GIT_CONFIG_GLOBAL bleiben ausdruecklich stehen (Identitaet bzw. Test-Isolation).
unset GIT_DIR GIT_WORK_TREE GIT_COMMON_DIR GIT_INDEX_FILE GIT_OBJECT_DIRECTORY \
    GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_CONFIG_COUNT

readonly REMOTE="origin"
readonly HAUPTZWEIG="main"
# Voll qualifiziert, damit ein gleichnamiger lokaler Branch die Aufloesung nicht an sich ziehen
# kann. Das ist keine Kosmetik, sondern die Zusicherung selbst: Exit 0 ist der einzige Ausgang,
# der still falsch sein kann.
readonly TRACKING_REF="refs/remotes/origin/main"
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

# Gebraucht wird es erst ganz am Ende, fuer die Frage "wurde ueberhaupt ein Merge begonnen?".
# Hier bestimmt, weil dort jeder Pfad in einer eigenen Meldung enden soll und ein spaeter
# scheiterndes Kommando unter `set -e` das Skript ohne Begruendung beendete.
git_verzeichnis="$(git rev-parse --git-dir 2>/dev/null || true)"
if [[ -z "$git_verzeichnis" ]]; then
    abbruch "das Git-Verzeichnis dieses Arbeitsbaums liess sich nicht bestimmen."
fi

zweig="$(git symbolic-ref --quiet --short HEAD 2>/dev/null || true)"
if [[ -z "$zweig" ]]; then
    abbruch "losgeloester HEAD. Ein Merge hier hinterliesse einen Commit, den kein Ref haelt."
fi

if [[ "$zweig" == "$HAUPTZWEIG" ]]; then
    abbruch "'$HAUPTZWEIG' ist ausgecheckt. Der Abgleich laeuft ausschliesslich auf einem Feature-Branch."
fi

# Unversionierte Dateien blockieren bewusst nicht: Ein Entwicklungslauf hat fast immer
# Streudateien. Kollidiert eine davon tatsaechlich, verweigert git den Merge von sich aus.
if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
    abbruch "Arbeitsverzeichnis nicht sauber (gestagte oder ungestagte Aenderung an einer verfolgten Datei). Erst committen, dann abgleichen."
fi

if ! git remote get-url "$REMOTE" >/dev/null 2>&1; then
    abbruch "kein Remote '$REMOTE' konfiguriert."
fi

# Der Stand des Tracking-Refs *vor* dem Fetch. Er ist die einzige Grundlage, auf der sich ein
# umgeschriebenes main hinterher noch messen laesst - das "+" der Refspec nimmt git die
# Vorspul-Pruefung ab, die diese Messung sonst uebernommen haette.
# Fehlt der Ref (frischer Klon, frischer Arbeitsbaum), bleibt die Variable leer. Das heisst
# "keine Messung", nicht "geprueft", und wird unten als eigener Zweig behandelt.
tracking_vorher="$(git rev-parse --verify --quiet "$TRACKING_REF" || true)"

# Ein Fehlschlag hat hier noch zwei moegliche Ursachen (Remote nicht erreichbar, dort kein main).
# Unterschieden werden sie bewusst nicht: Das ginge nur ueber den Meldungstext von git, und der
# ist uebersetzbar. Die dritte frueher genannte Ursache ("lokal nicht vorspulbar") kann diese
# Zeile wegen des "+" nicht mehr ausloesen; sie wird stattdessen gemessen.
if ! git fetch --quiet "$REMOTE" "+refs/heads/$HAUPTZWEIG:$TRACKING_REF" >/dev/null 2>&1; then
    abbruch "'$HAUPTZWEIG' konnte nicht von '$REMOTE' geholt werden: Remote nicht erreichbar oder '$HAUPTZWEIG' dort nicht vorhanden. Ein Fall fuer Daniel, nicht fuer eine Korrektur nebenbei."
fi

# Guertel und Hosentraeger: Ein durchgelaufener Fetch, nach dem das benannte Ziel trotzdem fehlt,
# ist keine Lage, in der weitergerechnet werden darf - jede Folgemessung liefe auf einen Ref, den
# es nicht gibt, und endete in einer Fehlermeldung ueber das falsche Thema.
if ! git rev-parse --verify --quiet "$TRACKING_REF" >/dev/null 2>&1; then
    abbruch "'$TRACKING_REF' existiert auch nach dem Holen nicht. Hier wurde nichts uebernommen, und es gibt nichts zu messen - bitte von Hand ansehen."
fi

# Umschreib-Pruefung: gemessen statt geraten. Nur mit einem gemerkten Vorher-Stand gibt es
# ueberhaupt etwas zu vergleichen - "" ist kein Ref, und `merge-base --is-ancestor "" <ref>`
# liefert gemessen 128. Ein ungeprueft eingesetzter leerer Wert machte jeden frischen Klon zu
# einem falschen Exit 30, also genau zu der Fehlmeldung, gegen die dieses Skript umgebaut wurde.
if [[ -n "$tracking_vorher" ]]; then
    umschreib_rueckgabe=0
    git merge-base --is-ancestor "$tracking_vorher" "$TRACKING_REF" >/dev/null 2>&1 ||
        umschreib_rueckgabe=$?

    if [[ "$umschreib_rueckgabe" -eq 1 ]]; then
        abbruch "'$HAUPTZWEIG' auf '$REMOTE' wurde umgeschrieben: der zuvor geholte Stand ist im neuen kein Vorfahre mehr. Ein Fall fuer Daniel, nicht fuer eine Korrektur nebenbei."
    fi

    if [[ "$umschreib_rueckgabe" -ne 0 ]]; then
        abbruch "'git merge-base --is-ancestor' meldete beim Vergleich der beiden Tracking-Staende Rueckgabe $umschreib_rueckgabe. Weder 'fortgeschrieben' noch 'umgeschrieben' - hier wurde nichts gemessen."
    fi
fi

# Der No-Op wird gerechnet, nicht gelesen - und ausschliesslich Rueckgabe 0 heisst "enthalten".
# Rueckgabe 1 heisst "nicht enthalten", 128 heisst "unbekanntes Objekt/kaputtes Repositorium"
# (Bedrohung 2: still falsch sein kann allein dieser Ausgang).
vorfahre_rueckgabe=0
git merge-base --is-ancestor "$TRACKING_REF" HEAD >/dev/null 2>&1 || vorfahre_rueckgabe=$?

if [[ "$vorfahre_rueckgabe" -eq 0 ]]; then
    exit "$EXIT_ENTHALTEN"
fi

if [[ "$vorfahre_rueckgabe" -ne 1 ]]; then
    abbruch "'git merge-base --is-ancestor' meldete Rueckgabe $vorfahre_rueckgabe. Weder 'enthalten' noch 'nicht enthalten' - hier wurde nichts gemessen."
fi

# --no-ff sichert zu, dass der bisherige Kopf immer erster Elternteil des neuen bleibt. Ohne es
# schoebe ein Vorspulen den Feature-Branch stillschweigend auf main und leerte den Pull Request.
merge_rueckgabe=0
git merge --no-ff --no-edit -m "$MERGE_NACHRICHT" "$TRACKING_REF" >/dev/null 2>&1 ||
    merge_rueckgabe=$?

if [[ "$merge_rueckgabe" -eq 0 ]]; then
    exit "$EXIT_UEBERNOMMEN"
fi

# "Merge-Rueckgabe ungleich 0" ist nicht gleich "Konflikt". Ein pre-merge-commit-Hook
# (oder commit.gpgsign ohne Schluessel) laesst git merge scheitern, MERGE_HEAD existieren - und
# hinterlaesst null Pfade im Konfliktzustand.
konflikt_rueckgabe=0
konfliktpfade="$(git -c core.quotePath=false -c diff.relative=false diff --name-only --diff-filter=U)" ||
    konflikt_rueckgabe=$?

if [[ "$konflikt_rueckgabe" -ne 0 ]]; then
    abbruch "die Konfliktpfade liessen sich nicht ermitteln ('git diff --diff-filter=U' meldete Rueckgabe $konflikt_rueckgabe), nachdem 'git merge' mit Rueckgabe $merge_rueckgabe geendet hat. Der Zustand des Repositoriums ist offen - bitte von Hand ansehen."
fi

if [[ -n "$konfliktpfade" ]]; then
    printf '%s\n' "$konfliktpfade"
    exit "$EXIT_KONFLIKT"
fi

# Kein Pfad im Konfliktzustand - zwei verschiedene Lagen, und die Meldung darf sie nicht
# verwechseln (sie ist der Text, den der Ablauf unveraendert an Daniel weitergibt):
#   (a) Der Merge hat begonnen und wurde abgelehnt (pre-merge-commit-Hook, commit.gpgsign ohne
#       Schluessel). MERGE_HEAD existiert, `git merge --abort` nimmt ihn zurueck.
#   (b) Der Merge hat gar nicht erst begonnen - gemessen etwa, wenn eine unversionierte Datei mit
#       einer neu auf `main` entstandenen kollidiert (Rueckgabe 2). MERGE_HEAD existiert nie, und
#       `git merge --abort` scheiterte hier mit "There is no merge to abort". Es gibt nichts
#       zurueckzunehmen; genau das ist die Zusage, dass git selbst verweigert.
# Unterschieden wird an der Existenz von MERGE_HEAD, nicht an einem Ausgabetext.
if [[ -e "$git_verzeichnis/MERGE_HEAD" ]]; then
    if ! git merge --abort >/dev/null 2>&1; then
        abbruch "'git merge' scheiterte mit Rueckgabe $merge_rueckgabe und der begonnene Merge liess sich nicht zuruecknehmen. Das Repositorium steht mit einem offenen Merge da - bitte von Hand ansehen."
    fi
    abbruch "'git merge' scheiterte mit Rueckgabe $merge_rueckgabe, ohne einen Pfad im Konfliktzustand zu hinterlassen (Hook oder Signatur hat den begonnenen Merge abgelehnt). Der begonnene Merge wurde zurueckgenommen, der Zustand ist unveraendert."
fi

abbruch "'git merge' scheiterte mit Rueckgabe $merge_rueckgabe, ohne einen Merge zu beginnen (in aller Regel kollidiert eine nicht versionierte Datei im Arbeitsverzeichnis mit einer Datei aus '$HAUPTZWEIG'). Es gab nichts zurueckzunehmen, der Zustand ist unveraendert."
