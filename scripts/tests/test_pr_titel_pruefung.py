r"""Prueft die PR-Titel-Pruefung aus `.github/workflows/pr-titel.yml` **ausfuehrend**.

Der Anlass (Spec 0343, ADR 0063): Dieses Repository squasht Pull Requests mit
`COMMIT_OR_PR_TITLE` - der PR-Titel wird zum Titel des Merge-Commits auf `main`, und genau
diese Titel wertet `release-please` aus. Ein Titel ohne Conventional-Commit-Praefix wird dabei
**still** uebergangen: kein Changelog-Eintrag, kein Versions-Bump, keine Fehlermeldung. Der
Workflow faengt das vor dem Merge ab.

**Warum dieser Test das Skript ausfuehrt, statt es zu lesen.** Die Fachlichkeit steckt in einem
Shell-Skript in einer YAML-Datei. Eine rein textliche Zusicherung ("der Regex steht da") liesse
genau die Fehler durch, auf die es ankommt: ein Skript, das den Fehler erkennt, ihn aber nur
ausgibt statt mit `exit 1` zu enden, waere gruen und wirkungslos; ein Muster, das im
Runner-Environment anders greift als gedacht, ebenso. Zugesichert wird deshalb je Fall
**Exit-Code und Ausgabe** des real hinterlegten `run:`-Blocks. Der Block wird aus der
Workflow-Datei extrahiert, dedentet und mit gesetztem `PR_TITLE` durch `bash` geschickt - es gibt
**keine zweite Kopie** des Musters oder des Skripts in diesem Test, die driften koennte.

**Was dieser Test ausdruecklich NICHT beweist:**

* Dass ein fehlschlagender PR tatsaechlich nicht mergebar ist. Das haengt allein daran, dass der
  Job-Name `pr-titel` als Kontext in `required_status_checks.contexts` der Branch Protection auf
  `main` steht - eine Repository-Einstellung ausserhalb des Codes.
* Dass GitHub bei `edited` erneut auswertet. Das ist Verhalten des Actions-Dienstes und nur am
  offenen PR beobachtbar.
* Dass die YAML gueltig ist bzw. der Runner den Block genau so ausfuehrt wie das lokale `bash`.
  Die Gegenprobe **im Workflow selbst** (bekannt guter und bekannt schlechter Beispieltitel gegen
  dasselbe Muster, vor der Pruefung des echten Titels) ist die einzige Zusage, die im
  Runner-Environment greift; dieser Test sichert nur, dass es sie gibt und dass sie anschlaegt.

**Selbstschutz.** Der Erfolgsfall mehrerer Zusicherungen hier ist "nichts gefunden" bzw. "Skript
lief durch". Eine kaputte Extraktion waere davon nicht zu unterscheiden, deshalb scheitert jede
Extraktion laut mit `ValueError` statt still mit einem leeren Ergebnis (Muster
`_pruefe_nicht_leer` des Nachbartests `test_release_workflow_ohne_selbstmerge.py`), und der
Ausfuehrungs-Helfer selbst besteht eine Gegenprobe: mit einem bewusst unpassenden Muster darf ein
Positivfall nicht mehr bestehen.

**Zur Injektions-Haerte als Whitelist statt Blacklist.** Der Workflow reicht zum ersten Mal in
diesem Repository von aussen frei waehlbaren Fremdtext in einen `run:`-Step - einen PR-Titel setzt
auf einem public Repository jeder Fork-Autor. Statt gefaehrliche Formen aufzuzaehlen (was ein
Wettlauf waere), zaehlt dieser Test die **erlaubten** auf: Jeder `${{ }}`-Ausdruck der Datei muss
einer von drei benannten sein und auf seiner dafuer vorgesehenen Zeile stehen, im `run:`-Block
steht ueberhaupt keiner, `github.`/`secrets` kommen ausserhalb dieser Ausdruecke nicht vor,
`PR_TITLE` wird nur in Anfuehrungszeichen verwendet, es gibt keine `uses:`-Zeile und
`permissions: {}` steht da.

**Abweichung von der Teststrategie der Spec, bewusst und begruendet:** Dort steht "genau ein
`${{`-Vorkommen in der ganzen Datei". Das ist mit dem ebenfalls dort festgelegten
`concurrency`-Schluessel (`${{ github.workflow }}-${{ github.event.pull_request.number }}`) nicht
gleichzeitig erfuellbar - es sind drei. Die Zusicherung ist deshalb als **ortsgebundene
Allowlist** ueber alle drei Ausdruecke formuliert: Sie ist nicht schwaecher (jeder einzelne
Ausdruck ist namentlich und mit seiner Zeile festgelegt, ein vierter faellt auf), traegt aber
beide Vorgaben.

**Zur Suche im Rohtext, ohne Kommentare zu entfernen** (anders als beim Nachbartest): Innerhalb
eines `run:`-Blockskalars ist ein `#` Skripttext, kein YAML-Kommentar - GitHub ersetzt einen
`${{ }}`-Ausdruck auch dort, bevor `bash` die Zeile ueberhaupt sieht. Ein "auskommentierter"
Ausdruck waere also trotzdem eine Injektion. In einer Datei mit einem einzigen Zweck ist die
Totalsuche zugleich schaerfer und einfacher.

Kein Netzwerk, kein `gh`, keine YAML-Bibliothek (PyYAML ist in scripts/pyproject.toml keine
Abhaengigkeit, die Nachbartests arbeiten genauso textbasiert). Ausgefuehrt wird ausschliesslich
der `run:`-Block dieses Repositories in einem eigenen `bash`-Prozess.
"""

from __future__ import annotations

import os
import re
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_WURZEL = Path(__file__).parents[2]
WORKFLOW_NAME = "pr-titel.yml"
WORKFLOW_PFAD = REPO_WURZEL / ".github" / "workflows" / WORKFLOW_NAME
CLAUDE_MD_PFAD = REPO_WURZEL / "CLAUDE.md"
PR_VORLAGE_PFAD = REPO_WURZEL / ".github" / "pull_request_template.md"

# Spec 0343 / ADR 0063: zehn zulaessige Typen. Die Namen stehen bewusst nirgends in diesem Test -
# sie werden aus dem Muster der Workflow-Datei abgeleitet und gegen CLAUDE.md gehalten. Fest ist
# allein ihre Anzahl, damit ein versehentliches Streichen auffaellt.
ERWARTETE_TYPENZAHL = 10

# Die drei einzigen zulaessigen Ausdruecke, je mit der Zeile, auf der sie stehen duerfen.
ERLAUBTE_AUSDRUECKE = {
    "github.event.pull_request.title": "PR_TITLE: ${{ github.event.pull_request.title }}",
    "github.workflow": "group: ${{ github.workflow }}-${{ github.event.pull_request.number }}",
    "github.event.pull_request.number": (
        "group: ${{ github.workflow }}-${{ github.event.pull_request.number }}"
    ),
}

# AK 1/AK 5: `edited` traegt die erneute Pruefung nach einer Titelkorrektur, `synchronize` ist
# nicht optional (Required Status Checks werden pro Head-SHA ausgewertet).
_TRIGGER = re.compile(
    r"^on:\s*$\n^\s+pull_request:\s*$\n^\s+types:\s*\[\s*opened,\s*edited,\s*reopened,"
    r"\s*synchronize\s*\]\s*$",
    re.MULTILINE,
)

# Beide YAML-Schreibweisen: "run: |" als Folgeschluessel eines Steps und "- run: |" als dessen
# erster. Der Einzug des Blockinhalts bemisst sich in beiden Faellen an der Spalte, in der "run"
# beginnt - sonst gaelte bei der Strich-Form der Inhalt faelschlich als weniger eingerueckt.
_RUN_ZEILE = re.compile(r"^(?P<einzug>\s*)(?P<strich>-\s+)?run: \|\s*$")
_MUSTER_ZEILE = re.compile(r"^MUSTER='(?P<wert>[^']*)'\s*$", re.MULTILINE)
_TYPEN_GRUPPE = re.compile(r"^\^\((?P<typen>[a-z|]+)\)")
_AUSDRUCK = re.compile(r"\$\{\{(?P<inhalt>[^}]*)\}\}")
_USES_ZEILE = re.compile(r"^\s*(?:-\s+)?uses:", re.MULTILINE)
_JOBS_ZEILE = re.compile(r"^jobs:\s*$")
_JOB_SCHLUESSEL = re.compile(r"^  (?P<schluessel>[A-Za-z0-9_-]+):\s*$")
_JOB_NAME_OVERRIDE = re.compile(r"^    name:", re.MULTILINE)
_PR_TITLE_VERWENDUNG = re.compile(r"\$\{?PR_TITLE\}?")
_ENV_ZEILE = re.compile(r"^(?P<einzug>\s*)env:\s*$")
_ENV_ZUWEISUNG = re.compile(r"^\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*):\s+(?P<wert>.+?)\s*$")
_COMMITS_ZEILE = re.compile(r"^- \*\*Commits:\*\*.*$", re.MULTILINE)
_TYP_IM_TEXT = re.compile(r"`([a-z]+):`")

# Bestand am 2026-09-07 (`git log origin/main --first-parent`, letzte 80 Merges): Diese Formen
# kommen dort vor und muessen bestehen, sonst lehnt die Pruefung etablierte, korrekte Praxis ab.
GUELTIGE_TITEL = (
    "feat: neue Funktion",
    "fix(backend): Fehler behoben",
    "feat!: unvereinbare Aenderung",
    "feat(frontend)!: unvereinbare Aenderung",
    "chore(deps-dev): bump vitest from 2.1.1 to 2.1.2",
    "chore(main): release 0.37.0",
    "ci: Release-Workflow ohne Selbst-Merge (Spec 0178) (#345)",
    "docs(specs): Spec 0343 anlegen (Issue #343)",
    'revert: Revert "feat: Projekte loeschen"',
    "fix: a",
    "feat: Groesse der Vorschau (Umlaute, UTF-8)",
)

# Die ersten drei sind der Bestandsdefekt selbst (Titel ohne Praefix, so stehen sie heute auf
# main); der Rest sind die Grenzfaelle, an denen das Muster scharf sein muss.
UNGUELTIGE_TITEL = (
    "Projekte löschen mit Namensbestätigung (Spec 0044) (#351)",
    "Cloud-Modell je Anbieter wählbar, Kostenschätzung ans Modell gebunden (Spec 0304) (#341)",
    "Update README",
    "fix:kein Leerzeichen",
    "fix: ",
    "fix:  zwei Leerzeichen",
    "Feat: Grossschreibung",
    "wip: unbekannter Typ",
    "featuring: kein Typ, nur Praefix eines Typs",
    "feat",
    "feat:",
    " feat: fuehrendes Leerzeichen",
    "",
    "(#351)",
)

# Der nachgemessene Injektionsversuch aus dem Sicherheitsabschnitt der Spec: Er ist ein
# **gueltiger** Titel und muss unveraendert als Text behandelt werden.
INJEKTIONS_TITEL = 'feat: `id` $(id) "x" ; rm -rf /'


# --- Leser und Extraktion ---------------------------------------------------------------------


def workflow_text(pfad: Path = WORKFLOW_PFAD) -> str:
    """Duenner Leser fuer den echten Dateizustand; eine fehlende Datei scheitert laut."""
    return pfad.read_text(encoding="utf-8")


def run_block(text: str, quelle: str = WORKFLOW_NAME) -> str:
    """Der `run: |`-Blockskalar, dedentet und damit direkt ausfuehrbar.

    Genau einer wird erwartet: Der Workflow besteht bewusst aus einem einzigen Step. Zwei
    Bloecke hiessen, dass dieser Test nur noch einen Teil des Verhaltens prueft.
    """
    zeilen = text.splitlines()
    treffer = [(nummer, t) for nummer, z in enumerate(zeilen) if (t := _RUN_ZEILE.match(z))]

    if len(treffer) != 1:
        raise ValueError(
            f"{quelle}: {len(treffer)} 'run: |'-Bloecke gefunden, erwartet genau einer. Der "
            "Workflow besteht aus einem einzigen Step; ohne eindeutigen Block prueft dieser "
            "Test nicht das, was laeuft."
        )

    start, kopf = treffer[0]
    einzug = len(kopf.group("einzug")) + len(kopf.group("strich") or "")
    gesammelt: list[str] = []
    for zeile in zeilen[start + 1 :]:
        if zeile.strip() and len(zeile) - len(zeile.lstrip()) <= einzug:
            break
        gesammelt.append(zeile)

    block = textwrap.dedent("\n".join(gesammelt)).strip("\n")
    if not block.strip():
        raise ValueError(
            f"{quelle}: Der 'run: |'-Block ist leer. Ein leeres Skript besteht jeden Testlauf "
            "und prueft keinen einzigen Titel - ein gruener Test waere hier bedeutungslos."
        )
    return block + "\n"


def muster(block: str) -> str:
    """Der erweiterte regulaere Ausdruck, so wie er im Skript zugewiesen wird."""
    treffer = _MUSTER_ZEILE.findall(block)
    if len(treffer) != 1:
        raise ValueError(
            f"{WORKFLOW_NAME}: {len(treffer)} Zeilen der Form MUSTER='...' im run-Block, "
            "erwartet genau eine. Ohne sie ist nicht feststellbar, gegen welches Muster "
            "geprueft wird, und alle daraus abgeleiteten Zusicherungen waeren bedeutungslos."
        )
    return treffer[0]


def typen(muster_text: str) -> list[str]:
    """Die zulaessigen Commit-Typen, aus dem Muster abgeleitet statt abgeschrieben."""
    treffer = _TYPEN_GRUPPE.match(muster_text)
    if treffer is None:
        raise ValueError(
            f"Aus dem Muster {muster_text!r} laesst sich keine Typenliste ableiten (erwartete "
            "Form: '^(typ|typ|...)...'). Jede Zusicherung ueber die Typen waere ohne sie leer."
        )
    gefunden = [teil for teil in treffer.group("typen").split("|") if teil]
    if not gefunden:
        raise ValueError(f"Aus dem Muster {muster_text!r} ergibt sich eine leere Typenliste.")
    return gefunden


def env_zuweisungen(text: str) -> dict[str, str]:
    """Die `env:`-Zuweisungen des Steps als Name -> Wert."""
    zeilen = text.splitlines()
    treffer = [(nummer, t) for nummer, z in enumerate(zeilen) if (t := _ENV_ZEILE.match(z))]
    if len(treffer) != 1:
        raise ValueError(
            f"{WORKFLOW_NAME}: {len(treffer)} 'env:'-Bloecke gefunden, erwartet genau einer - "
            "der Titel erreicht das Skript ausschliesslich ueber diesen einen Block."
        )

    start, kopf = treffer[0]
    einzug = len(kopf.group("einzug"))
    gefunden: dict[str, str] = {}
    for zeile in zeilen[start + 1 :]:
        if not zeile.strip():
            continue
        if len(zeile) - len(zeile.lstrip()) <= einzug:
            break
        zuweisung = _ENV_ZUWEISUNG.match(zeile)
        if zuweisung is None:
            break
        gefunden[zuweisung.group("name")] = zuweisung.group("wert")

    if not gefunden:
        raise ValueError(f"{WORKFLOW_NAME}: Der 'env:'-Block enthaelt keine Zuweisung.")
    return gefunden


def laufumgebung(text: str) -> dict[str, str]:
    """Die literalen `env:`-Werte des Workflows - alles ausser dem Titel-Ausdruck.

    Damit laeuft der Testlauf unter derselben Umgebung wie der Runner (heute: `LC_ALL`), statt
    unter der zufaelligen Umgebung des Entwicklungsrechners. Verschwindet der literale Wert aus
    dem Workflow, scheitert das hier laut statt still unter anderer Locale weiterzulaufen.
    """
    literale = {name: wert for name, wert in env_zuweisungen(text).items() if "${{" not in wert}
    if not literale:
        raise ValueError(
            f"{WORKFLOW_NAME}: Der 'env:'-Block enthaelt keinen literalen Wert mehr (erwartet "
            "mindestens LC_ALL). Der Testlauf liefe dann unter einer anderen Locale als der "
            "Runner, und das Ergebnis sagte nichts ueber den echten Lauf."
        )
    return literale


def fuehre_aus(block: str, titel: str, umgebung: dict[str, str]) -> tuple[int, str]:
    """Fuehrt den extrahierten Block mit gesetztem `PR_TITLE` aus; liefert (Exit-Code, Ausgabe).

    Ausgabe ist stdout und stderr zusammen: Fuer die Zusicherungen zaehlt, was im Log des Laufs
    steht, nicht auf welchem Deskriptor es dort landet.
    """
    if not block.strip():
        raise ValueError(
            "Leeres Skript uebergeben - ein leeres Skript endet mit Exit-Code 0 und liesse jeden "
            "Positivfall bestehen."
        )

    ergebnis = subprocess.run(
        ["bash", "-c", block],
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), **umgebung, "PR_TITLE": titel},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return ergebnis.returncode, ergebnis.stdout + ergebnis.stderr


def mit_ersetztem_muster(block: str, neues_muster: str) -> str:
    """Tauscht die MUSTER-Zuweisung aus - nur fuer die Gegenproben dieses Tests."""
    ersetzt, anzahl = _MUSTER_ZEILE.subn(f"MUSTER='{neues_muster}'", block)
    if anzahl != 1:
        raise ValueError(f"{anzahl} MUSTER-Zeilen ersetzt, erwartet genau eine.")
    return ersetzt


def claude_md_typen(text: str) -> list[str]:
    """Die Commit-Typen aus der Konventionszeile von CLAUDE.md."""
    zeile = _COMMITS_ZEILE.search(text)
    if zeile is None:
        raise ValueError(
            "CLAUDE.md: Keine Zeile der Form '- **Commits:** ...' gefunden. Die Deckungsgleich"
            "heit mit dem Muster des Workflows ist damit ungeprueft."
        )
    gefunden = _TYP_IM_TEXT.findall(zeile.group(0))
    if not gefunden:
        raise ValueError(
            f"CLAUDE.md: In der Commits-Zeile {zeile.group(0)!r} steht kein Typ der Form "
            "`feat:`. Ein leerer Vergleich waere keine Zusicherung."
        )
    return gefunden


@pytest.fixture(scope="module")
def skript() -> str:
    return run_block(workflow_text())


@pytest.fixture(scope="module")
def umgebung() -> dict[str, str]:
    return laufumgebung(workflow_text())


# --- Verhalten: gueltige Titel -----------------------------------------------------------------


@pytest.mark.parametrize("titel", GUELTIGE_TITEL)
def test_ein_gueltiger_titel_besteht(titel: str, skript: str, umgebung: dict[str, str]) -> None:
    code, ausgabe = fuehre_aus(skript, titel, umgebung)

    assert code == 0, f"Titel {titel!r} wurde abgelehnt (Exit {code}):\n{ausgabe}"
    assert ausgabe == f"OK: {titel}\n", (
        f"Erwartet die unveraenderte Bestaetigungszeile, bekommen: {ausgabe!r}"
    )


def test_jeder_typ_des_musters_besteht(skript: str, umgebung: dict[str, str]) -> None:
    """Abgeleitet statt abgeschrieben: Jeder Typ, den das Muster nennt, muss auch bestehen."""
    abgelehnt = [
        typ
        for typ in typen(muster(skript))
        if fuehre_aus(skript, f"{typ}: Beispielbeschreibung", umgebung)[0] != 0
    ]

    assert not abgelehnt, (
        f"Das Muster nennt {abgelehnt} als zulaessige Typen, lehnt sie in der Ausfuehrung aber "
        "ab. Die Typenliste im Muster und ihr Verhalten sind auseinandergelaufen."
    )


def test_die_zehn_typen_stehen_deckungsgleich_in_claude_md(skript: str) -> None:
    aus_muster = typen(muster(skript))
    aus_claude_md = claude_md_typen(CLAUDE_MD_PFAD.read_text(encoding="utf-8"))

    assert set(aus_muster) == set(aus_claude_md), (
        f"Die Typen des Workflow-Musters {sorted(aus_muster)} und die von CLAUDE.md "
        f"{sorted(aus_claude_md)} sind auseinandergelaufen. Eine Konvention, die in der "
        "Projektverfassung anders steht als die Maschine sie durchsetzt, wird umgangen oder "
        "aufgeweicht - beide Stellen gehoeren im selben Commit angepasst."
    )
    assert len(set(aus_muster)) == ERWARTETE_TYPENZAHL, (
        f"{len(set(aus_muster))} Typen statt {ERWARTETE_TYPENZAHL} (Spec 0343). Eine Erweiterung "
        "oder Kuerzung ist eine bewusste Entscheidung, keine Nebenwirkung."
    )


def test_ein_injektionsversuch_wird_als_text_behandelt(
    skript: str, umgebung: dict[str, str]
) -> None:
    """Die `env:`-Form schliesst die Script-Injection: kein Teilstring wird ausgefuehrt."""
    code, ausgabe = fuehre_aus(skript, INJEKTIONS_TITEL, umgebung)

    assert code == 0
    assert ausgabe == f"OK: {INJEKTIONS_TITEL}\n", (
        f"Der Titel wurde nicht unveraendert als Text behandelt: {ausgabe!r}"
    )
    assert "uid=" not in ausgabe, "Ein Teil des Titels wurde als Kommando ausgefuehrt."


def test_ein_workflow_kommando_im_titel_beginnt_keine_zeile(
    skript: str, umgebung: dict[str, str]
) -> None:
    """Der Runner liest jeden Zeilenanfang der Ausgabe auf Workflow-Kommandos.

    Ein gueltiger Titel wird ausgegeben - aber nur hinter dem Praefix `OK: `, nie als eigene
    Zeile. Zusammen mit der Steuerzeichen-Wache (kein Zeilenumbruch im Titel) kann ein Titel
    damit keine Zeile beginnen.
    """
    code, ausgabe = fuehre_aus(skript, "feat: ::error::etwas ::stop-commands::x", umgebung)

    assert code == 0
    assert [zeile for zeile in ausgabe.splitlines() if zeile.startswith("::")] == []


# --- Verhalten: ungueltige Titel ---------------------------------------------------------------


@pytest.mark.parametrize("titel", UNGUELTIGE_TITEL)
def test_ein_ungueltiger_titel_scheitert(
    titel: str, skript: str, umgebung: dict[str, str]
) -> None:
    code, ausgabe = fuehre_aus(skript, titel, umgebung)

    assert code == 1, (
        f"Titel {titel!r} wurde mit Exit {code} durchgelassen. Ein Skript, das den Fehler nur "
        f"ausgibt statt mit 'exit 1' zu enden, ist gruen und wirkungslos.\nAusgabe:\n{ausgabe}"
    )
    assert ausgabe.strip(), "Ein Fehlschlag ohne jede Meldung sagt niemandem, was zu tun ist."


def test_die_fehlermeldung_nennt_alle_typen_und_die_form(
    skript: str, umgebung: dict[str, str]
) -> None:
    """AK 4: Die Meldung sagt, was fehlt und was zulaessig ist - ohne Nachschlagen anderswo."""
    code, ausgabe = fuehre_aus(skript, "Update README", umgebung)
    erwartete_typen = typen(muster(skript))

    assert code == 1
    fehlend = [typ for typ in erwartete_typen if not re.search(rf"\b{typ}\b", ausgabe)]
    assert not fehlend, (
        f"Die Fehlermeldung nennt {fehlend} nicht, obwohl das Muster diese Typen zulaesst. Wer "
        f"sie liest, muesste nachschlagen.\nAusgabe:\n{ausgabe}"
    )
    assert "typ(scope)!: Beschreibung" in ausgabe, (
        f"Die Meldung nennt die zulaessige Form nicht.\nAusgabe:\n{ausgabe}"
    )


@pytest.mark.parametrize(
    "titel",
    [
        "ohne Praefix\nfeat: zweite Zeile",  # bestuende ohne Wache: grep arbeitet zeilenweise
        "feat: erste Zeile\nzweite Zeile",
        "feat: mit\tTabulator",
        "feat: mit \x1b[31m ANSI",
        "\nfeat: fuehrender Umbruch",
    ],
)
def test_ein_titel_mit_steuerzeichen_wird_abgewiesen(
    titel: str, skript: str, umgebung: dict[str, str]
) -> None:
    """Die Wache steht vor jeder Verarbeitung - und die Meldung gibt den Titel bewusst nicht aus.

    Zwei tragende Gruende: `grep` arbeitet zeilenweise (ein mehrzeiliger Titel gaelte als
    gueltig, sobald irgendeine Zeile passt), und der Runner liest jede Zeile der Step-Ausgabe
    auf Workflow-Kommandos - ein mehrzeiliger Titel koennte damit eine Zeile beginnen.
    """
    code, ausgabe = fuehre_aus(skript, titel, umgebung)

    assert code == 1, f"Titel {titel!r} wurde mit Exit {code} durchgelassen.\n{ausgabe}"
    for teil in titel.splitlines():
        if teil.strip():
            assert teil not in ausgabe, (
                f"Die Meldung der Steuerzeichen-Wache gibt {teil!r} aus. Genau dieser Titel darf "
                f"nicht in die Ausgabe gelangen.\nAusgabe:\n{ausgabe}"
            )
    assert ausgabe.strip(), "Auch die Wache muss sagen, was los ist."


# --- Gegenproben zum Ausfuehrungs-Helfer und zur Gegenprobe im Workflow -------------------------


def test_ein_unpassendes_muster_laesst_einen_positivfall_nicht_bestehen(
    skript: str, umgebung: dict[str, str]
) -> None:
    """Selbstschutz: Ohne diese Probe waere ein gruener Positivlauf oben kein Befund."""
    kaputt = mit_ersetztem_muster(skript, "^ZZZ-gibt-es-nicht")

    code, _ = fuehre_aus(kaputt, "feat: neue Funktion", umgebung)

    assert code != 0, (
        "Mit einem bewusst unpassenden Muster besteht ein Positivfall trotzdem - dann prueft der "
        "Ausfuehrungs-Helfer nicht das, was er zu pruefen vorgibt."
    )


def test_die_gegenprobe_im_workflow_faengt_ein_zu_enges_muster(
    skript: str, umgebung: dict[str, str]
) -> None:
    """Bekannt guter Beispieltitel besteht nicht mehr -> der Job darf nicht gruen werden."""
    kaputt = mit_ersetztem_muster(skript, "^ZZZ-gibt-es-nicht")

    code, ausgabe = fuehre_aus(kaputt, "feat: neue Funktion", umgebung)

    assert code == 1
    assert "Selbstpruefung" in ausgabe, (
        "Der Workflow haelt keinen bekannt guten Beispieltitel gegen sein eigenes Muster. Das "
        f"ist die einzige Zusage, die im Runner-Environment selbst greift.\nAusgabe:\n{ausgabe}"
    )


def test_die_gegenprobe_im_workflow_faengt_ein_zu_weites_muster(
    skript: str, umgebung: dict[str, str]
) -> None:
    """Ein Muster, das alles bestehen laesst, wuerde die Pruefung still wirkungslos machen."""
    kaputt = mit_ersetztem_muster(skript, "")

    code, ausgabe = fuehre_aus(kaputt, "feat: neue Funktion", umgebung)

    assert code == 1
    assert "Selbstpruefung" in ausgabe, (
        "Ein leeres Muster besteht jeden Titel, und der Job waere gruen, ohne irgendetwas zu "
        f"pruefen.\nAusgabe:\n{ausgabe}"
    )


def test_ein_leeres_skript_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"Leeres Skript"):
        fuehre_aus("   \n", "feat: x", {})


def test_ein_leerer_run_block_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"'run: \|'-Block ist leer"):
        run_block("jobs:\n  pr-titel:\n    steps:\n      - run: |\n")


def test_zwei_run_bloecke_scheitern_laut() -> None:
    with pytest.raises(ValueError, match=r"2 'run: \|'-Bloecke"):
        run_block("      - run: |\n          echo a\n      - run: |\n          echo b\n")


def test_beide_schreibweisen_des_run_blocks_liefern_dasselbe_skript() -> None:
    """Ob `run:` erster Schluessel des Steps ist oder nicht, darf das Ergebnis nicht aendern."""
    strichform = run_block("      - run: |\n          echo a\n          echo b\n")
    folgeform = run_block("        run: |\n          echo a\n          echo b\n")

    assert strichform == folgeform == "echo a\necho b\n"


def test_ein_fehlendes_muster_scheitert_laut() -> None:
    with pytest.raises(ValueError, match=r"0 Zeilen der Form MUSTER"):
        muster("set -euo pipefail\ngrep -Eq 'irgendwas'\n")


def test_eine_unableitbare_typenliste_scheitert_laut() -> None:
    with pytest.raises(ValueError, match=r"keine Typenliste"):
        typen("irgendwas ohne Gruppe")


def test_eine_fehlende_workflow_datei_scheitert_laut(tmp_path: Path) -> None:
    """Umbenannt oder geloescht darf nicht heissen: gruen, weil nichts gefunden."""
    with pytest.raises(FileNotFoundError):
        workflow_text(tmp_path / "gibt-es-nicht.yml")


def test_eine_fehlende_commits_zeile_in_claude_md_scheitert_laut() -> None:
    with pytest.raises(ValueError, match=r"Keine Zeile der Form"):
        claude_md_typen("# CLAUDE.md\n\n- **PRs:** klein und fokussiert\n")


def test_eine_commits_zeile_ohne_typ_scheitert_laut() -> None:
    with pytest.raises(ValueError, match=r"kein Typ der Form"):
        claude_md_typen("- **Commits:** Conventional Commits.\n")


def test_ein_env_block_ohne_literalen_wert_scheitert_laut() -> None:
    with pytest.raises(ValueError, match=r"keinen literalen Wert"):
        laufumgebung("        env:\n          PR_TITLE: ${{ github.event.pull_request.title }}\n")


# --- Statische Zusicherungen an der Workflow-Datei ---------------------------------------------


def test_der_trigger_traegt_alle_vier_ereignistypen() -> None:
    assert _TRIGGER.search(workflow_text()), (
        f"{WORKFLOW_NAME} laeuft nicht mehr auf 'pull_request' mit den Typen [opened, edited, "
        "reopened, synchronize]. 'edited' traegt die erneute Pruefung nach einer Titelkorrektur; "
        "ohne 'synchronize' bliebe der Check nach jedem weiteren Push auf 'Expected - waiting "
        "for status to be reported' stehen und blockierte den PR dauerhaft."
    )


def test_der_workflow_fordert_keinerlei_berechtigung() -> None:
    assert re.search(r"^permissions:\s*\{\}\s*$", workflow_text(), re.MULTILINE), (
        f"{WORKFLOW_NAME} traegt kein 'permissions: {{}}'. Der Job liest kein Repository und "
        "ruft keine API - selbst 'contents: read' waere zu viel."
    )


def test_der_workflow_verwendet_keine_einzige_action() -> None:
    fundstellen = _USES_ZEILE.findall(workflow_text())

    assert not fundstellen, (
        f"{WORKFLOW_NAME} enthaelt {len(fundstellen)} 'uses:'-Zeile(n). Der Job verwendet weder "
        "eine externe Action noch 'actions/checkout' - er fuehrt damit keine einzige Zeile aus "
        "dem Pull Request aus. Eine Action hier waere Drittanbieter-Code im PR-Kontext."
    )


def test_der_workflow_nennt_kein_secret() -> None:
    assert "secrets" not in workflow_text(), (
        f"{WORKFLOW_NAME} verweist auf ein Secret. Der Job braucht keines; jedes hier waere in "
        "einem Kontext mit frei waehlbarem Fremdtext exponiert."
    )


def test_die_concurrency_gruppe_haengt_an_der_pr_nummer() -> None:
    text = workflow_text()

    assert ERLAUBTE_AUSDRUECKE["github.workflow"] in [
        zeile.strip() for zeile in text.splitlines()
    ], (
        f"{WORKFLOW_NAME}: Die concurrency-Gruppe lautet nicht "
        f"{ERLAUBTE_AUSDRUECKE['github.workflow']!r}. Der Schluessel muss eine von GitHub "
        "vergebene Zahl sein - nie der Branch-Name und nie der Titel."
    )
    assert re.search(r"^\s*cancel-in-progress: true\s*$", text, re.MULTILINE), (
        f"{WORKFLOW_NAME}: 'cancel-in-progress: true' fehlt. 'edited' laesst sich beliebig oft "
        "ausloesen; ohne Abbruch stapeln sich Laeufe."
    )


def test_jeder_ausdruck_der_datei_steht_auf_der_allowlist() -> None:
    """Whitelist statt Blacklist: drei benannte Ausdruecke, jeder an seinem Ort."""
    befunde: list[str] = []
    for nummer, zeile in enumerate(workflow_text().splitlines(), start=1):
        for treffer in _AUSDRUCK.finditer(zeile):
            inhalt = treffer.group("inhalt").strip()
            if inhalt not in ERLAUBTE_AUSDRUECKE:
                befunde.append(f"Zeile {nummer}: unbekannter Ausdruck {inhalt!r}")
            elif zeile.strip() != ERLAUBTE_AUSDRUECKE[inhalt]:
                befunde.append(
                    f"Zeile {nummer}: {inhalt!r} steht auf {zeile.strip()!r}, erwartet auf "
                    f"{ERLAUBTE_AUSDRUECKE[inhalt]!r}"
                )

    assert not befunde, (
        "; ".join(befunde) + ".\nJeder Ausdruck dieser Datei ist namentlich und mit seiner Zeile "
        "festgelegt. Ein PR-Titel ist auf einem public Repository frei waehlbarer Fremdtext; "
        "GitHub setzt einen Ausdruck woertlich in die Datei ein, bevor irgendetwas laeuft."
    )


def test_alle_drei_erlaubten_ausdruecke_kommen_auch_vor() -> None:
    """Gegenstueck zur Allowlist: Sie darf nicht dadurch gruen sein, dass gar nichts dasteht."""
    gefunden = {treffer.group("inhalt").strip() for treffer in _AUSDRUCK.finditer(workflow_text())}

    assert gefunden == set(ERLAUBTE_AUSDRUECKE), (
        f"Gefundene Ausdruecke {sorted(gefunden)} statt {sorted(ERLAUBTE_AUSDRUECKE)}. Fehlt "
        "der Titel-Ausdruck, prueft der Workflow einen leeren Titel; fehlt die Gruppe, laufen "
        "die Laeufe unkoordiniert."
    )


def test_im_run_block_steht_kein_einziger_ausdruck(skript: str) -> None:
    """Ein `${{ }}` im Skripttext waere die klassische Script-Injection - auch im Kommentar.

    Innerhalb eines Blockskalars ist `#` Skripttext und kein YAML-Kommentar; GitHub ersetzt den
    Ausdruck dort genauso, bevor `bash` die Zeile sieht.
    """
    assert "${{" not in skript, (
        "Im run-Block steht ein Ausdruck. Der Titel erreicht das Skript ausschliesslich ueber "
        'env: und dort ausschliesslich als "$PR_TITLE".'
    )


def test_ausserhalb_der_erlaubten_ausdruecke_steht_kein_kontextverweis() -> None:
    """Restlicher Text ohne `${{ ... }}`: dort darf kein `github.`-Kontext mehr vorkommen."""
    rest = _AUSDRUCK.sub("", workflow_text())

    assert "github." not in rest, (
        f"{WORKFLOW_NAME} verweist ausserhalb der drei erlaubten Ausdruecke auf einen "
        "github.-Kontext."
    )


def test_der_titel_wird_nur_in_anfuehrungszeichen_verwendet(skript: str) -> None:
    befunde: list[str] = []
    for treffer in _PR_TITLE_VERWENDUNG.finditer(skript):
        davor = skript[treffer.start() - 1] if treffer.start() > 0 else ""
        danach = skript[treffer.end() : treffer.end() + 1]
        if davor != '"' or danach != '"':
            zeile = skript[: treffer.start()].count("\n") + 1
            befunde.append(f"Zeile {zeile}: {skript.splitlines()[zeile - 1].strip()!r}")

    assert not befunde, (
        f"$PR_TITLE wird ohne Anfuehrungszeichen verwendet: {befunde}. Ohne sie zerlegt die "
        "Shell den Titel an Leerzeichen und expandiert Platzhalter wie '*'."
    )
    assert len(_PR_TITLE_VERWENDUNG.findall(skript)) >= 2, (
        "Weniger als zwei Verwendungen von $PR_TITLE im Skript - erwartet mindestens die Wache "
        "und die eigentliche Pruefung."
    )


def test_der_workflow_traegt_genau_einen_job_namens_pr_titel() -> None:
    zeilen = workflow_text().splitlines()
    start = next((nummer for nummer, zeile in enumerate(zeilen) if _JOBS_ZEILE.match(zeile)), None)
    assert start is not None, f"{WORKFLOW_NAME}: kein 'jobs:'-Block gefunden."

    schluessel = [
        treffer.group("schluessel")
        for zeile in zeilen[start + 1 :]
        if (treffer := _JOB_SCHLUESSEL.match(zeile))
    ]

    assert schluessel == ["pr-titel"], (
        f"Job-Schluessel {schluessel} statt ['pr-titel']. Der Schluessel *ist* der Kontextname "
        "der Branch Protection: Eine Umbenennung braeche die Zusage nicht sichtbar, sondern "
        "liesse den geforderten Kontext dauerhaft auf 'Expected' stehen und blockierte jeden "
        "Pull Request dieses Repositories."
    )


def test_der_job_traegt_keinen_name_override() -> None:
    assert not _JOB_NAME_OVERRIDE.search(workflow_text()), (
        f"{WORKFLOW_NAME}: Der Job traegt ein 'name:' auf Job-Ebene. Das ueberschreibt den "
        "Kontextnamen der Branch Protection, ohne dass es irgendwo rot wird - der geforderte "
        "Kontext 'pr-titel' bliebe dauerhaft auf 'Expected' stehen."
    )


# --- AK 7 / AK 8: die Regel steht dort, wo PRs entstehen ---------------------------------------


def test_die_pr_vorlage_erwaehnt_die_titelregel(skript: str) -> None:
    """Reine Existenzpruefung, ohne Wortlautbindung - geprueft wird *dass*, nicht *wie*."""
    vorlage = PR_VORLAGE_PFAD.read_text(encoding="utf-8")
    erwartete_typen = typen(muster(skript))

    assert "Titel" in vorlage, (
        f"{PR_VORLAGE_PFAD.name} erwaehnt den Titel nicht. Die Regel muss dort stehen, wo PRs "
        "entstehen."
    )
    beispiele = [typ for typ in erwartete_typen if re.search(rf"`{typ}(\([^()]+\))?!?:", vorlage)]
    assert beispiele, (
        f"{PR_VORLAGE_PFAD.name} nennt kein Praefixbeispiel der Form `feat:`. Wer die Vorlage "
        "ausfuellt, soll die Form sehen, statt sie nachschlagen zu muessen."
    )


def test_der_bezug_block_der_pr_vorlage_bleibt_unangetastet() -> None:
    """AK 8: Die bestehende Closes-Regel wird woertlich uebernommen, nicht umformuliert."""
    vorlage = PR_VORLAGE_PFAD.read_text(encoding="utf-8")

    assert "\nCloses #NNN\n" in vorlage, (
        f"{PR_VORLAGE_PFAD.name}: Die Zeile 'Closes #NNN' fehlt. Nur sie erzeugt die "
        "strukturierte Verknuepfung zwischen PR und Issue."
    )
    assert "nie in eine Commit-Nachricht oder den PR-Titel" in vorlage, (
        f"{PR_VORLAGE_PFAD.name}: Der Hinweis, dass das Keyword ausschliesslich in den Body "
        "gehoert, ist verschwunden oder umformuliert."
    )
