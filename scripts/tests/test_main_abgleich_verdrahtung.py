r"""Haelt die Verdrahtung des `main`-Abgleichs fest - das, was ein Verhaltenstest nicht kann.

Der Abgleich mit `main` (Spec 0338, ADR 0063) besteht aus zwei Haelften. Die eine ist
`scripts/merge-main-into-branch.sh` und wird in `test_merge_main_into_branch.py` **ausgefuehrt**
geprueft. Die andere ist Ablauftext in `.claude/skills/ship-feature/SKILL.md` und
`.claude/agents/developer.md`, den zur Laufzeit ein LLM interpretiert. Zugesichert wird hier
deshalb ausschliesslich **Nachweisbares**:

1. Das Skript existiert, ist ausfuehrbar und traegt die Eigenschaften, die AK 4 und AK 7 zu
   Texteigenschaften machen: kein `push`, kein `rebase`, kein `commit --amend`, kein
   `reset --hard`, kein `--force`. Damit liegt AK 7 im Required Check `demo-scripts`.
2. Der `fetch` traegt die Refspec **und** das `--quiet`. Das ist die eine Zeile, deren
   Vereinfachung zu `git fetch origin` die Review-Runde **still** braeche: `git diff main...HEAD`
   bildet die Merge-Basis aus dem lokalen `main`-Ref, und die sechs Fundstellen der Review-Phase
   bekaemen ab da fremde Dateien vorgelegt, ohne dass irgendetwas rot wuerde.
3. Das Skript entscheidet nirgends an einem Ausgabetext von git (`Already up to date`,
   `CONFLICT`, `Automatic merge failed`) - der ehrliche Pruefer fuer die Locale-Unabhaengigkeit,
   die `test_merge_main_into_branch.py` bewusst nicht ueber `LC_ALL=C` erzwingt.
4. `ship-feature` ruft das Skript an **genau zwei** Stellen auf, in Schritt 6 **nach** dem
   Commit-Teilschritt und **vor** `git push`, in Schritt 8 **vor** der Verknuepfungspruefung und
   **vor** dem Setzen der `**Status:**`-Zeile (Reihenfolge ueber Zeichenoffsets).
5. Beide neuen Anker stehen wortgleich in `developer.md` und werden **nur** dort definiert;
   `ship-feature` nennt sie in seiner Trigger-Liste, ohne das Format zu wiederholen.
6. Die feste Merge-Nachricht kommt im Suchraum `scripts/` + `.claude/` **genau einmal** vor,
   naemlich im Skript - und `release-please-config.json` schaltet `chore` nicht sichtbar (AK 8
   haengt an dieser Vorgabe, ein `changelog-sections`-Eintrag kippte sie still).
7. Der dokumentierte Abschlussbefehl traegt `--cleanup=strip` und schliesst pfadgenau ab; ein
   `git add -A`/`git commit -a` steht nirgends in `developer.md` (Sicherheitskonzept,
   Bedrohung 4 - der Branch geht unmittelbar danach in ein oeffentliches Repositorium).

**Was hier bewusst NICHT gebaut wird:** ein Pruefer, der aus dem Prosatext herausliest, dass nach
Exit 10 der Qualitaetscheck laeuft oder dass bei Rot abgebrochen wird. Er waere gruen, weil ein
Satz dasteht, und froere nebenbei die Formulierung ein. AK 2, 5, 6 und 9 sind damit je zur
Haelfte zugesichert: Skript ausfuehrbar bewiesen, Ablauf nur verankert.

**Selbstschutz** wie bei den uebrigen Repo-Konsistenztests, weil die Haelfte der Zusagen hier
Abwesenheiten sind: Untergrenze fuer den Suchraum, Nachweis, dass die tragenden Dateien **im**
Suchraum liegen, eine Gegenprobe **je Musterfamilie**, und der Mutationsnachweis **nach** Gruen.

**Mutationsnachweis (2026-09-08, nach Gruen gefuehrt, danach zurueckgenommen).** Je Familie
probeweise eingesetzt und jeweils genau die erwartete Zusicherung rot bekommen: `git push origin
HEAD` ins Skript (Abwesenheitsverbot); `--quiet` aus der fetch-Zeile entfernt und die Refspec
durch `"$REMOTE"` ersetzt (fetch-Form); die zweite Aufrufstelle in Schritt 8 hinter die
Verknuepfungspruefung geschoben (Reihenfolge ueber Offsets) und danach ganz geloescht (Anzahl);
die Merge-Nachricht zusaetzlich in `developer.md` gesetzt (Einmaligkeit); `## Blockiert:
main-Abgleich fehlgeschlagen` in einen Codeblock in `ship-feature` gesetzt (einzige
Definitionsstelle); `"changelog-sections": [{"type": "chore", "section": "Sonstiges", "hidden":
false}]` in `release-please-config.json` (AK 8). Wer ein Muster aendert, wiederholt diese Probe,
statt sie zu glauben.

Kein Netzwerk, kein `gh`, kein echtes git: gelesen werden ausschliesslich Dateien dieses
Repositories.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterable
from pathlib import Path

import pytest

REPO_WURZEL = Path(__file__).parents[2]

SKRIPT_PFAD = REPO_WURZEL / "scripts" / "merge-main-into-branch.sh"
SKRIPT_REPO_RELATIV = "scripts/merge-main-into-branch.sh"
SHIP_FEATURE_PFAD = REPO_WURZEL / ".claude" / "skills" / "ship-feature" / "SKILL.md"
DEVELOPER_PFAD = REPO_WURZEL / ".claude" / "agents" / "developer.md"
RELEASE_PLEASE_PFAD = REPO_WURZEL / "release-please-config.json"

# Wortgleich mit der Zeile im Skript (ADR 0063, Abschnitt 2).
MERGE_NACHRICHT = "chore: Stand von main in den Feature-Branch übernehmen"

# Ausschliesslich in .claude/agents/developer.md definiert; ship-feature verweist funktional.
ANKER_ABSCHLUSS = "## Abschlussbericht (Folgeauftrag: main-Abgleich)"
ANKER_BLOCKIERT = "## Blockiert: main-Abgleich fehlgeschlagen"
NEUE_ANKER = (ANKER_ABSCHLUSS, ANKER_BLOCKIERT)

# AK 4 und AK 7 als Texteigenschaft. Der Suchraum ist der kommentarfreie Skripttext - der
# Kopfkommentar benennt notwendigerweise, was er verbietet.
VERBOTENE_BEFEHLE = {
    "push": re.compile(r"\bpush\b", re.IGNORECASE),
    "rebase": re.compile(r"\brebase\b", re.IGNORECASE),
    "commit --amend": re.compile(r"commit\s+--amend"),
    "reset --hard": re.compile(r"reset\s+--hard"),
    "--force": re.compile(r"--force\b"),
}

# Locale-Unabhaengigkeit: Entschieden wird an Exit-Codes und Dateizustaenden, nie an Text.
VERBOTENE_AUSGABETEXTE = ("Already up to date", "CONFLICT", "Automatic merge failed")

# Sicherheitskonzept, Bedrohung 1: Muss-Liste, direkt nach `set -euo pipefail`.
ZU_BEREINIGENDE_VARIABLEN = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_COMMON_DIR",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_CONFIG_COUNT",
)

# Ordnungsmarken fuer die Reihenfolge-Zusicherung (Zeichenoffsets innerhalb des Abschnitts).
MARKE_COMMIT = "committen"
MARKE_PUSH = "git push -u origin"
MARKE_VERKNUEPFUNG = "pr-verknuepfung-lesen"
MARKE_STATUSZEILE = "**Status:**"

# Sicherheitskonzept, Bedrohung 4: pfadgenau schliessen, nie pauschal. Zugesichert wird die
# **Anwesenheit** beider Befehle, nicht die Abwesenheit ihrer pauschalen Gegenstuecke - siehe die
# Begruendung an den Tests unten.
ABSCHLUSSBEFEHL = "git commit --no-edit --cleanup=strip"
PFADGENAUES_HINZUFUEGEN = "git add <genau die Konfliktpfade>"

# Selbstschutz: eine kaputte Dateiaufzaehlung liesse die Einmaligkeitspruefung still gruen werden.
MINDESTZAHL_DATEIEN_IM_SUCHRAUM = 20
TEXT_ENDUNGEN = frozenset({".sh", ".py", ".md", ".json", ".toml", ".txt", ".yml", ".yaml"})

# Die Pruefer selbst muessen den Wortlaut fuehren, um ihn pruefen zu koennen - sie sind nicht der
# Ablauf und deshalb aus dem Suchraum der Einmaligkeitspruefung ausgenommen. Die Ausnahme ist so
# eng wie moeglich: genau dieses Verzeichnis, und die Tests unten weisen nach, dass Skript und
# Skill-Dateien weiterhin darin liegen.
AUSGENOMMEN_VOM_SUCHRAUM = ("scripts/tests",)


def wirksame_zeilen(text: str, kommentarzeichen: str) -> list[str]:
    """Ersetzt ganzzeilige Kommentare durch Leerzeilen, laesst alles andere unberuehrt.

    Zwingend fuer den Skripttext: Sein Kopfkommentar benennt die verbotenen Befehle
    (`push`, `rebase`, ...) und wuerde die Abwesenheitspruefung sonst mit genau der
    Dokumentation rot machen, die sie erzwingen soll. Kommentarzeilen werden zu Leerzeilen statt
    entfernt, damit gemeldete Zeilennummern denen der echten Datei entsprechen.

    Inline-Kommentare werden ausdruecklich nicht abgeschnitten - ein naives Abschneiden an jedem
    `#` blendete Inhalt hinter einem `#` in einer Zeichenkette aus.
    """
    return [
        "" if zeile.lstrip().startswith(kommentarzeichen) else zeile
        for zeile in text.splitlines()
    ]


def wirksamer_skripttext(text: str) -> str:
    return "\n".join(wirksame_zeilen(text, "#"))


def _pruefe_nicht_leer(text: str, quelle: str) -> None:
    if not text.strip():
        raise ValueError(
            f"{quelle}: 0 wirksame Zeilen. Datei leer, nur Kommentare oder umbenannt - in jedem "
            "Fall ist die Zusicherung ungeprueft, und ein gruener Test waere bedeutungslos."
        )


def fundstellen(text: str, muster: re.Pattern[str]) -> list[str]:
    return [
        f"Zeile {text[: treffer.start()].count(chr(10)) + 1}: {treffer.group(0)!r}"
        for treffer in muster.finditer(text)
    ]


def verbotene_befehle(text: str) -> list[str]:
    """AK 4/AK 7 als Texteigenschaft: meldet jeden schreibenden oder umschreibenden Befehl."""
    wirksam = wirksamer_skripttext(text)
    _pruefe_nicht_leer(wirksam, SKRIPT_REPO_RELATIV)
    return [
        f"{name} - {fund}"
        for name, muster in VERBOTENE_BEFEHLE.items()
        for fund in fundstellen(wirksam, muster)
    ]


def fetch_zeilen(text: str) -> list[str]:
    wirksam = wirksamer_skripttext(text)
    _pruefe_nicht_leer(wirksam, SKRIPT_REPO_RELATIV)
    return [zeile.strip() for zeile in wirksam.splitlines() if "git fetch" in zeile]


def fetch_befunde(text: str) -> list[str]:
    """Der `fetch` traegt genau eine Zeile, und die traegt Refspec und `--quiet`."""
    zeilen = fetch_zeilen(text)
    if len(zeilen) != 1:
        return [f"{len(zeilen)} 'git fetch'-Zeilen gefunden ({zeilen}), erwartet genau eine."]

    zeile = zeilen[0]
    befunde: list[str] = []
    if "--quiet" not in zeile:
        befunde.append(f"'--quiet' fehlt in {zeile!r} (AK 3: keine Ausgabe bei Exit 0).")
    if not re.search(r'\bfetch\b[^|;]*\S+:\S+', zeile):
        befunde.append(
            f"keine Refspec der Form '<ref>:<ref>' in {zeile!r}. Ohne sie bleibt der lokale "
            "main-Ref stehen, und 'git diff main...HEAD' zeigt an sechs Stellen der "
            "Review-Phase fremde Dateien - ohne dass irgendetwas rot wird (ADR 0063, Abs. 3)."
        )
    return befunde


def abschnitt(text: str, ueberschrift: str) -> str:
    """Der Text eines `##`-Abschnitts bis zur naechsten `##`-Ueberschrift."""
    beginn = text.index(ueberschrift)
    rest = text[beginn + len(ueberschrift) :]
    treffer = re.search(r"^## ", rest, re.MULTILINE)
    return ueberschrift + (rest[: treffer.start()] if treffer else rest)


def codeblock_texte(text: str) -> list[str]:
    """Alle mit ``` eingezaeunten Bloecke - dort steht die Definition eines Ankers."""
    return re.findall(r"^```[^\n]*\n(.*?)^```", text, re.MULTILINE | re.DOTALL)


def suchraum(wurzel: Path = REPO_WURZEL) -> dict[str, str]:
    """Repo-relativer Pfad -> Inhalt fuer `scripts/` und `.claude/`, ohne die Pruefer selbst."""
    abbild: dict[str, str] = {}
    for verzeichnis in ("scripts", ".claude"):
        for pfad in sorted((wurzel / verzeichnis).rglob("*")):
            if not pfad.is_file() or pfad.suffix not in TEXT_ENDUNGEN:
                continue
            relativ = pfad.relative_to(wurzel).as_posix()
            if "__pycache__" in relativ:
                continue
            if any(relativ.startswith(f"{ort}/") for ort in AUSGENOMMEN_VOM_SUCHRAUM):
                continue
            abbild[relativ] = pfad.read_text(encoding="utf-8", errors="replace")
    return abbild


def vorkommen(abbild: dict[str, str], zeichenkette: str) -> list[str]:
    if not abbild:
        raise ValueError(
            "0 Dateien im Suchraum: Ein leerer Suchraum darf nie als 'genau einmal gefunden' "
            "oder 'nicht gefunden' durchgehen."
        )
    return [
        f"{name} ({inhalt.count(zeichenkette)}x)"
        for name, inhalt in sorted(abbild.items())
        if zeichenkette in inhalt
    ]


def anker_definitionsstellen(abbild: dict[str, str], anker: str) -> list[str]:
    """Dateien, die den Anker **in einem Codeblock** fuehren - das ist eine Definition."""
    return [
        name
        for name, inhalt in sorted(abbild.items())
        if any(anker in block for block in codeblock_texte(inhalt))
    ]


def skripttext() -> str:
    return SKRIPT_PFAD.read_text(encoding="utf-8")


def dateitext(pfad: Path) -> str:
    return pfad.read_text(encoding="utf-8")


# --- 1. Das Skript selbst ---------------------------------------------------------------------


def test_das_skript_existiert_und_ist_ausfuehrbar() -> None:
    assert SKRIPT_PFAD.is_file(), (
        f"{SKRIPT_REPO_RELATIV} fehlt. 'ship-feature' ruft es an zwei Stellen auf und scheitert "
        "sonst mit 'Kommando nicht gefunden'."
    )
    assert os.access(SKRIPT_PFAD, os.X_OK), (
        f"{SKRIPT_REPO_RELATIV} ist nicht ausfuehrbar (Modus "
        f"{SKRIPT_PFAD.stat().st_mode & 0o777:o}). Das Ausfuehrungsbit ist Teil des Commits."
    )


def test_das_skript_beginnt_mit_shebang_und_strengem_modus() -> None:
    text = skripttext()

    assert text.startswith("#!/usr/bin/env bash\n")
    assert "set -euo pipefail" in text


def test_das_skript_bereinigt_die_umgebung() -> None:
    """Bedrohung 1: 'keine Argumente' bindet das Ziel nicht - `GIT_DIR` richtet es woandershin."""
    wirksam = wirksamer_skripttext(skripttext())
    unset_text = "\n".join(zeile for zeile in wirksam.splitlines() if "unset" in zeile or True)

    fehlend = [name for name in ZU_BEREINIGENDE_VARIABLEN if f" {name}" not in unset_text]
    assert not fehlend, (
        f"Im `unset` fehlen: {fehlend}. Mit gesetztem GIT_DIR/GIT_WORK_TREE meldet git den "
        "Branch eines anderen Repositoriums, ueber GIT_CONFIG_COUNT laesst sich core.hooksPath "
        "unterschieben."
    )
    assert "GIT_AUTHOR" not in wirksam and "GIT_CONFIG_GLOBAL" not in wirksam, (
        "GIT_AUTHOR_*/GIT_COMMITTER_* und GIT_CONFIG_GLOBAL bleiben ausdruecklich stehen - ohne "
        "sie hat der Merge-Commit im Unterprozess keine Identitaet und die Tests keine Isolation."
    )


def test_das_skript_enthaelt_keinen_schreibenden_oder_umschreibenden_befehl() -> None:
    befunde = verbotene_befehle(skripttext())

    assert not befunde, (
        f"{SKRIPT_REPO_RELATIV} enthaelt wieder einen verbotenen Befehl: {'; '.join(befunde)}.\n"
        "Der Abgleich ist eine Einbahnstrasse (AK 7) und schreibt keine veroeffentlichten "
        "Commits um (AK 4). Die Freigabe nach main bleibt vollstaendig Daniels Entscheidung."
    )


@pytest.mark.parametrize(
    "zeile",
    [
        'git push --quiet "$REMOTE" HEAD',
        'git push --force-with-lease "$REMOTE" HEAD',
        'git rebase "$HAUPTZWEIG"',
        'git commit --amend --no-edit',
        'git reset --hard "$HAUPTZWEIG"',
        'git merge --no-ff --force "$HAUPTZWEIG"',
    ],
)
def test_jede_verbotene_musterfamilie_wuerde_erkannt(zeile: str) -> None:
    """Gegenprobe je Familie: Eine Nullmeldung oben ist sonst kein Befund, sondern ein Defekt."""
    assert verbotene_befehle(f"#!/usr/bin/env bash\nset -e\n{zeile}\n")


def test_der_kopfkommentar_darf_die_verbotenen_befehle_benennen() -> None:
    """Der wahrscheinlichste Selbst-Rotfall: Die Doku benennt notwendig, was sie verbietet."""
    text = "#!/usr/bin/env bash\n# kein push, kein rebase, kein reset --hard\nset -e\ngit fetch\n"

    assert verbotene_befehle(text) == []


def test_ein_leerer_skripttext_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"0 wirksame Zeilen"):
        verbotene_befehle("# nur ein Kommentar\n\n   \n")


# --- 2. Die eine Zeile, deren Vereinfachung still braeche -------------------------------------


def test_der_fetch_traegt_refspec_und_quiet() -> None:
    befunde = fetch_befunde(skripttext())

    assert not befunde, "; ".join(befunde)


@pytest.mark.parametrize(
    "zeile",
    [
        'git fetch --quiet "$REMOTE"',
        'git fetch "$REMOTE" "$HAUPTZWEIG:$HAUPTZWEIG"',
        'git fetch "$REMOTE"',
    ],
)
def test_eine_vereinfachte_fetch_zeile_wird_gemeldet(zeile: str) -> None:
    assert fetch_befunde(f"#!/usr/bin/env bash\nset -e\n{zeile}\n")


@pytest.mark.parametrize(
    "zeile",
    [
        'git fetch --quiet "$REMOTE" "$HAUPTZWEIG:$HAUPTZWEIG"',
        'git fetch --quiet origin main:main >/dev/null 2>&1',
    ],
)
def test_die_zugesicherte_fetch_form_bleibt_gruen(zeile: str) -> None:
    assert fetch_befunde(f"#!/usr/bin/env bash\nset -e\n{zeile}\n") == []


@pytest.mark.parametrize("ausgabetext", VERBOTENE_AUSGABETEXTE)
def test_das_skript_entscheidet_an_keinem_ausgabetext_von_git(ausgabetext: str) -> None:
    """Ausgabetexte sind uebersetzbar; alle drei Entscheidungen fallen an Exit-Codes."""
    assert ausgabetext not in wirksamer_skripttext(skripttext()), (
        f"{SKRIPT_REPO_RELATIV} sucht nach {ausgabetext!r}. Unter einem deutschen Katalog steht "
        "dort etwas anderes, und die Verzweigung faellt still falsch aus."
    )


def test_der_no_op_ausgang_entsteht_an_genau_einer_stelle() -> None:
    """Bedrohung 2: Still falsch sein kann allein der Ausgang 0."""
    wirksam = wirksamer_skripttext(skripttext())

    assert wirksam.count('exit "$EXIT_ENTHALTEN"') == 1
    assert not re.search(r"^\s*exit\s+0\s*$", wirksam, re.MULTILINE), (
        "Ein zweiter, literaler 'exit 0' im Skript: Exit 0 bedeutet 'main ist bereits "
        "enthalten' und darf ausschliesslich aus der Rueckgabe 0 von 'merge-base "
        "--is-ancestor' entstehen."
    )


# --- 4. Die zwei Aufrufstellen in `ship-feature` ----------------------------------------------


def test_ship_feature_ruft_das_skript_an_genau_zwei_stellen_auf() -> None:
    text = dateitext(SHIP_FEATURE_PFAD)

    assert text.count(SKRIPT_REPO_RELATIV) == 2, (
        f"{text.count(SKRIPT_REPO_RELATIV)} Aufrufstellen in ship-feature, erwartet genau zwei "
        "(Schritt 6 vor dem Push, Schritt 8 als erste Handlung). Der zweite Zeitpunkt ist der "
        "tragende: Zwischen PR-Eroeffnung und Freigabe vergeht die meiste Zeit (AK 2)."
    )


def test_der_erste_aufruf_steht_nach_dem_commit_und_vor_dem_push() -> None:
    """AK 1, Reihenfolge ueber Zeichenoffsets statt ueber eine Formulierung."""
    schritt = abschnitt(dateitext(SHIP_FEATURE_PFAD), "## Schritt 6")

    assert schritt.count(SKRIPT_REPO_RELATIV) == 1
    assert schritt.index(MARKE_COMMIT) < schritt.index(SKRIPT_REPO_RELATIV), (
        "Der Abgleich steht vor dem Committen der Reste - das Skript verlangt aber ein sauberes "
        "Arbeitsverzeichnis und braeche dort mit einer Vorbedingung ab."
    )
    assert schritt.index(SKRIPT_REPO_RELATIV) < schritt.index(MARKE_PUSH), (
        "Der Abgleich steht nach dem Push. Dann geht ein Branch hinaus, der den aktuellen Stand "
        "von main nicht enthaelt, und der Merge-Commit erzwingt einen zweiten CI-Lauf."
    )


def test_der_zweite_aufruf_ist_die_erste_handlung_in_schritt_acht() -> None:
    """AK 2: vor der Verknuepfungspruefung und vor dem Setzen der Statuszeile."""
    schritt = abschnitt(dateitext(SHIP_FEATURE_PFAD), "## Schritt 8")

    assert schritt.count(SKRIPT_REPO_RELATIV) == 1
    assert schritt.index(SKRIPT_REPO_RELATIV) < schritt.index(MARKE_VERKNUEPFUNG)
    assert schritt.index(SKRIPT_REPO_RELATIV) < schritt.index(MARKE_STATUSZEILE), (
        "Der Abgleich steht nach dem Setzen der Statuszeile. Der Finalisierungs-Commit soll aber "
        "gebuendelt mit dem Merge-Commit in *einem* Push hinausgehen (ADR 0042/0063)."
    )


def test_ship_feature_nimmt_den_offenen_merge_in_den_recovery_pfad_auf() -> None:
    """Sonst wird nach einem SendMessage-Fehlschlag ein Repositorium mit offenem Merge
    uebergeben."""
    recovery = abschnitt(dateitext(SHIP_FEATURE_PFAD), "## Recovery")

    assert "git merge --abort" in recovery


@pytest.mark.parametrize(
    ("text", "erwartet_rot"),
    [
        ("## Schritt 6\n1. committen\n2. scripts/x.sh\n3. git push -u origin\n", False),
        ("## Schritt 6\n1. committen\n2. git push -u origin\n3. scripts/x.sh\n", True),
    ],
)
def test_die_reihenfolgepruefung_unterscheidet_die_beiden_faelle(
    text: str, erwartet_rot: bool
) -> None:
    """Gegenprobe zur Offset-Methodik selbst - sie ist die Zusicherung, nicht der Wortlaut."""
    schritt = abschnitt(text, "## Schritt 6")
    vertauscht = schritt.index("scripts/x.sh") > schritt.index(MARKE_PUSH)

    assert vertauscht is erwartet_rot


def test_der_abschnittsleser_schneidet_an_der_naechsten_ueberschrift() -> None:
    text = "## Schritt 6\nA\n\n## Schritt 7\nB\n\n## Schritt 8\nC\n"

    assert abschnitt(text, "## Schritt 6").strip() == "## Schritt 6\nA"
    assert "B" not in abschnitt(text, "## Schritt 6")
    assert abschnitt(text, "## Schritt 8").strip() == "## Schritt 8\nC"


# --- 5. Die beiden Anker ----------------------------------------------------------------------


@pytest.mark.parametrize("anker", NEUE_ANKER)
def test_beide_anker_stehen_wortgleich_in_developer_md(anker: str) -> None:
    assert anker in dateitext(DEVELOPER_PFAD), (
        f"Der Anker {anker!r} fehlt in .claude/agents/developer.md. Er ist der verbindliche "
        "Uebergabepunkt an den Orchestrator; ohne ihn bleibt der Abgleich unbemerkt."
    )


@pytest.mark.parametrize("anker", NEUE_ANKER)
def test_die_ankerdefinition_steht_ausschliesslich_in_developer_md(anker: str) -> None:
    """Einzige Definitionsstelle im Repo - `ship-feature` verweist funktional, kopiert nicht."""
    stellen = anker_definitionsstellen(suchraum(), anker)

    assert stellen == [".claude/agents/developer.md"], (
        f"Der Anker {anker!r} wird in {stellen} als Format-Block gefuehrt. Zwei Abbilder "
        "desselben Formats driften; die Feldnamen stehen ausschliesslich in developer.md."
    )


@pytest.mark.parametrize("anker", NEUE_ANKER)
def test_ship_feature_nennt_beide_anker_in_seiner_trigger_liste(anker: str) -> None:
    schritt = abschnitt(dateitext(SHIP_FEATURE_PFAD), "## Schritt 0")

    assert anker in schritt, (
        f"Schritt 0 von ship-feature kennt den Anker {anker!r} nicht - eine developer-Antwort "
        "mit diesem Anker loeste den Skill dann nicht aus."
    )


def test_der_codeblock_leser_findet_nur_eingezaeunte_bloecke() -> None:
    """Gegenprobe zur Methodik: Eine blosse Erwaehnung ist keine Definition."""
    text = "Erwaehnung von `## Blockiert: X`.\n\n```\n## Blockiert: Y\n**Feld:** wert\n```\n"
    bloecke = codeblock_texte(text)

    assert len(bloecke) == 1
    assert "## Blockiert: Y" in bloecke[0]
    assert "## Blockiert: X" not in bloecke[0]


# --- 6. Die feste Merge-Nachricht und `chore` -------------------------------------------------


def test_die_merge_nachricht_kommt_im_suchraum_genau_einmal_vor() -> None:
    abbild = suchraum()

    assert len(abbild) >= MINDESTZAHL_DATEIEN_IM_SUCHRAUM, (
        f"Nur {len(abbild)} Dateien im Suchraum (erwartet mindestens "
        f"{MINDESTZAHL_DATEIEN_IM_SUCHRAUM}). Die Aufzaehlung ist kaputt; ein Befund von genau "
        "einem Vorkommen waere dann bedeutungslos."
    )
    for pflicht in (SKRIPT_REPO_RELATIV, ".claude/skills/ship-feature/SKILL.md"):
        assert pflicht in abbild, (
            f"{pflicht} liegt nicht im Suchraum - er sieht nicht, was er sehen soll."
        )

    stellen = vorkommen(abbild, MERGE_NACHRICHT)

    assert stellen == [f"{SKRIPT_REPO_RELATIV} (1x)"], (
        f"Die feste Merge-Nachricht steht an {stellen} statt ausschliesslich im Skript. Eine "
        "zweite Fassung driftet; die Nachricht liegt fuer den Konfliktfall in MERGE_MSG bereit "
        "und wird an keiner Stelle wiederholt (ADR 0063, Abschnitt 2)."
    )


def test_die_merge_nachricht_ist_einzeilig_und_konventionell() -> None:
    assert "\n" not in MERGE_NACHRICHT
    assert MERGE_NACHRICHT.startswith("chore: ")
    assert "#" not in MERGE_NACHRICHT, "AK 8: kein '#' - es wuerde im Squash-Body ausgewertet."
    assert not re.search(r"\b[0-9a-f]{7,40}\b", MERGE_NACHRICHT), "AK 8: kein Commit-Hash."


def test_eine_zweite_fundstelle_der_nachricht_wuerde_gemeldet() -> None:
    """Gegenprobe zur Einmaligkeitspruefung."""
    abbild = {"a.sh": MERGE_NACHRICHT, "b.md": MERGE_NACHRICHT}

    assert vorkommen(abbild, MERGE_NACHRICHT) == ["a.sh (1x)", "b.md (1x)"]


def test_ein_leerer_suchraum_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"0 Dateien im Suchraum"):
        vorkommen({}, MERGE_NACHRICHT)


def test_release_please_schaltet_chore_nicht_sichtbar() -> None:
    """AK 8 haengt an dieser Vorgabe: `chore` ist in den Vorgabe-Sektionen ausgeblendet."""
    konfiguration = json.loads(RELEASE_PLEASE_PFAD.read_text(encoding="utf-8"))
    sektionen: Iterable[dict[str, object]] = konfiguration.get("changelog-sections", [])

    sichtbare_chore = [
        eintrag
        for eintrag in sektionen
        if eintrag.get("type") == "chore" and eintrag.get("hidden") is not True
    ]

    assert not sichtbare_chore, (
        f"release-please-config.json schaltet 'chore' sichtbar: {sichtbare_chore}. Damit "
        "erschiene der Merge-Commit des Abgleichs im Changelog und AK 8 ('kein Rauschen') "
        "faellt - nachzuziehen ist dann ADR 0063, nicht dieser Test."
    )


# --- 7. Der dokumentierte Abschlussbefehl -----------------------------------------------------


def test_developer_dokumentiert_den_abschlussbefehl_mit_cleanup_strip() -> None:
    """Ohne `--cleanup=strip` bliebe die `# Conflicts:`-Liste im Commit-Body (AK 8)."""
    assert ABSCHLUSSBEFEHL in dateitext(DEVELOPER_PFAD), (
        f"{ABSCHLUSSBEFEHL!r} steht nicht in developer.md. 'git commit --no-edit' allein laesst "
        "die von git angehaengte Konfliktliste im Body stehen; sie wandert in den Squash-Body."
    )


def test_developer_dokumentiert_das_pfadgenaue_hinzufuegen() -> None:
    """Bedrohung 4: `git add -A` naehme eine danebenliegende untracked `.env` mit.

    **Bewusst nicht gebaut** ist das naheliegende Gegenstueck - ein Verbot der pauschalen
    Befehle im Text von `developer.md`. Ein Verbot muss benennen, was es verbietet; ein
    Textprueferkann eine Warnung ("nie `git add -A`") nicht von einer Anweisung unterscheiden
    und faerbte die Datei mit genau der Doku rot, die er erzwingen soll. Zugesichert ist
    deshalb die Anwesenheit des richtigen Wegs, nicht die Abwesenheit des falschen.
    """
    assert PFADGENAUES_HINZUFUEGEN in dateitext(DEVELOPER_PFAD), (
        f"{PFADGENAUES_HINZUFUEGEN!r} steht nicht in developer.md. Der Branch geht unmittelbar "
        "nach der Konfliktaufloesung in ein oeffentliches Repositorium; gemessen committet "
        "'git commit --no-edit' nur den Index, waehrend 'git add -A' eine danebenliegende "
        "untracked .env mitnaehme."
    )
