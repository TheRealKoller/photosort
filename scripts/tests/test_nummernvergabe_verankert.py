"""Haelt fest, dass die Nummernvergabe an genau einem Ort verankert und ueberall verdrahtet ist.

Die Konvention selbst steht als **ein** Punkt im Abschnitt `## Konventionen` von `CLAUDE.md`;
keine Agenten- oder Skill-Datei formuliert sie ein zweites Mal, dort steht ausschliesslich der
jeweilige **Ablaufschritt**. Zwei Abbilder derselben Regel driften.

Zugesichert ist die **Verankerung**, ausdruecklich nicht die **Befolgung**: Ob ein Lauf den
Zuteiler zur Laufzeit wirklich aufruft, zeichnet kein Artefakt dieses Repositoriums auf, und
jede Heuristik darueber waere gruen, ohne etwas zu wissen. Derselbe Vorbehalt wie in
`test_werkzeugwahl_verankert.py`.

**Die Reihenfolge wird ueber Zeichenoffsets gemessen, nicht aus Prosa gelesen** - ein Pruefer,
der aus einem Satz herausliest, dass nach Exit 10 etwas passiert, waere gruen, weil ein Satz
dasteht, und froere nebenbei dessen Formulierung ein. Die Gegenprobe zur Offset-Methodik selbst
steht am Ende dieser Datei.

**Die abgeloeste Regel wird an zwei Stellen gemessen, und die zweite ist die tragende.** Der
Meldungstext des Waechters wird nicht im Dateitext gesucht, sondern **erzeugt**: Ein Test ueber
dem Quelltext bliebe gruen, wenn die Regelnennung in einen anderen Zweig derselben Datei
wanderte. Die Pruefungen der beiden Sicherheitsnetze bleiben dabei unveraendert; gemessen wird,
dass beide ihre tragenden Testfunktionen weiterhin namentlich fuehren.
"""

from __future__ import annotations

import os
import re
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

REPO_WURZEL = Path(__file__).parents[2]

SKRIPT = "scripts/nummern.py"
CLAUDE_MD = "CLAUDE.md"
ARCHITECT = ".claude/agents/architect.md"
DEVELOPER = ".claude/agents/developer.md"
SHIP_FEATURE = ".claude/skills/ship-feature/SKILL.md"
SPEC_WRITER = ".claude/skills/spec-writer/SKILL.md"
ADR_0081 = "specs/decisions/0081-dokumentnummer-ist-identitaet-die-juengere-dublette-zieht-um.md"
NETZ_DOKUMENTNUMMERN = "scripts/tests/test_dokumentnummern_eindeutig.py"
NETZ_MIGRATIONSKETTE = "backend/tests/test_migration_chain.py"

MARKE_KONVENTION = "- **Nummernvergabe:**"
AUFRUF_VORSCHLAG = "scripts/nummern.py vorschlag decisions"
AUFRUF_MIGRATION = "scripts/nummern.py migration"
AUFRUF_PRUEFEN = "scripts/nummern.py pruefen"
AUFRUF_UMHAENGEN = "scripts/nummern.py umhaengen"
MARKE_MERGE_SKRIPT = "scripts/merge-main-into-branch.sh"
MARKE_PUSH = "git push -u origin"
MARKE_BERICHTSZEILE = "hinter <neuer Head> gehängt"

# Die abgeloeste Regel in der Form, in der sie eine Handlungsanweisung waere.
ABGELOESTE_REGEL = re.compile(r"(zieht|umziehen|Umzug).{0,60}n(ae|ä)chste[nr]? freie", re.DOTALL)


def dateitext(relativ: str) -> str:
    return (REPO_WURZEL / relativ).read_text(encoding="utf-8")


def ohne_codebloecke(text: str) -> str:
    """Leert eingezaeunte Bloecke zeichengenau - die Offsets des Originals bleiben erhalten.

    `developer.md` fuehrt seine Abschluss-Anker als Codebloecke, und die beginnen mit `## `.
    Ohne diese Maskierung endete ein Abschnitt an einer Formatvorlage statt an der naechsten
    echten Ueberschrift, und die Verdrahtung dahinter waere unsichtbar.
    """
    zeilen = []
    drin = False
    for zeile in text.splitlines(keepends=True):
        zaun = zeile.lstrip().startswith("```")
        if zaun or drin:
            zeilen.append("".join(" " if zeichen != "\n" else "\n" for zeichen in zeile))
        else:
            zeilen.append(zeile)
        if zaun:
            drin = not drin
    return "".join(zeilen)


def abschnitt(text: str, ueberschrift: str) -> str:
    """Von einer Ueberschrift bis zur naechsten gleichrangigen - oder bis zum Dateiende."""
    beginn = text.index(ueberschrift)
    ebene = ueberschrift.split(" ", 1)[0]
    maskiert = ohne_codebloecke(text)[beginn + len(ueberschrift) :]
    naechste = re.search(rf"^{re.escape(ebene)} ", maskiert, re.MULTILINE)
    rest = text[beginn + len(ueberschrift) :]
    return ueberschrift + (rest[: naechste.start()] if naechste else rest)


def anweisungsdateien() -> Iterator[tuple[str, str]]:
    """`CLAUDE.md` und alles unter `.claude/` - die Orte, an denen eine Regel angewiesen wird."""
    yield CLAUDE_MD, dateitext(CLAUDE_MD)
    for pfad in sorted((REPO_WURZEL / ".claude").rglob("*.md")):
        yield str(pfad.relative_to(REPO_WURZEL)), pfad.read_text(encoding="utf-8")


# --- 1. Das Skript ------------------------------------------------------------------------------


def test_der_zuteiler_liegt_und_ist_ausfuehrbar() -> None:
    pfad = REPO_WURZEL / SKRIPT

    assert pfad.is_file() and os.access(pfad, os.X_OK), (
        f"{SKRIPT} fehlt oder ist nicht ausfuehrbar - jede Aufrufstelle unten liefe ins Leere."
    )


# --- 2. Die Konvention steht genau einmal --------------------------------------------------------


def test_die_konvention_steht_genau_einmal_in_claude_md() -> None:
    text = dateitext(CLAUDE_MD)

    assert text.count(MARKE_KONVENTION) == 1
    assert MARKE_KONVENTION in abschnitt(text, "## Konventionen")


def test_keine_andere_datei_wiederholt_die_konvention() -> None:
    """Anti-Erosion: null Vorkommen sind hier der Sollzustand, nicht eine Luecke."""
    fundstellen = [
        pfad for pfad, text in anweisungsdateien() if pfad != CLAUDE_MD and MARKE_KONVENTION in text
    ]

    assert fundstellen == [], (
        f"Die Konvention steht zusaetzlich in {fundstellen}. Zwei Abbilder derselben Regel "
        "driften; Agenten- und Skill-Dateien tragen ausschliesslich den Ablaufschritt."
    )


def test_die_konvention_nennt_skript_entscheidung_und_die_ausnahme() -> None:
    punkt = abschnitt(dateitext(CLAUDE_MD), "## Konventionen")
    zeile = next(z for z in punkt.splitlines() if z.startswith(MARKE_KONVENTION))

    assert SKRIPT in zeile
    assert "0108" in zeile
    assert "Issue" in zeile, "ohne die Ausnahme fuer `specs/features/` gilt die Regel zu weit"


# --- 3. Die Verdrahtung an den Aufrufstellen -----------------------------------------------------


def test_architect_holt_die_nummer_vor_dem_anlegen_der_adr() -> None:
    aufgabe = abschnitt(dateitext(ARCHITECT), "## Aufgabe 1")

    assert AUFRUF_VORSCHLAG in aufgabe
    assert aufgabe.index(AUFRUF_VORSCHLAG) < aufgabe.index("specs/decisions/NNNN"), (
        "Der Zuteiler steht hinter dem Anlegen der Datei - dann ist die Nummer bereits gewaehlt "
        "und die Frueherkennung kommt zu spaet."
    )


def test_developer_holt_die_kennung_vor_dem_anlegen_der_migration() -> None:
    schritt = abschnitt(dateitext(DEVELOPER), "## Schritt 2")

    assert AUFRUF_MIGRATION in schritt


def test_developer_prueft_im_abschliessenden_qualitaetscheck() -> None:
    schritt = abschnitt(dateitext(DEVELOPER), "## Schritt 4")

    assert AUFRUF_PRUEFEN in schritt


def test_developer_haengt_beim_main_abgleich_selbsttaetig_um() -> None:
    folgeauftrag = abschnitt(dateitext(DEVELOPER), "## Folgeauftrag: Abgleich mit `main`")

    assert AUFRUF_UMHAENGEN in folgeauftrag
    assert MARKE_BERICHTSZEILE in folgeauftrag, (
        "Ohne die Berichtszeile ist ein Umhaengen der einzige Eingriff des Laufs, den weder eine "
        "Review-Runde noch der Bericht zeigt."
    )


def test_ship_feature_prueft_direkt_nach_dem_main_abgleich() -> None:
    schritt = abschnitt(dateitext(SHIP_FEATURE), "## Schritt 6")

    assert schritt.index(MARKE_MERGE_SKRIPT) < schritt.index(AUFRUF_PRUEFEN)
    assert schritt.index(AUFRUF_PRUEFEN) < schritt.index(MARKE_PUSH), (
        "Die Pruefung steht hinter dem Push - eine dort gefundene Dublette waere bereits "
        "veroeffentlicht."
    )


@pytest.mark.parametrize(
    ("relativ", "ueberschrift", "aufruf", "codes"),
    [
        (ARCHITECT, "## Aufgabe 1", AUFRUF_VORSCHLAG, ("`0`", "`10`", "`30`")),
        (DEVELOPER, "## Schritt 4", AUFRUF_PRUEFEN, ("`0`", "`10`", "`20`", "`30`")),
        (SHIP_FEATURE, "## Schritt 6", AUFRUF_PRUEFEN, ("`0`", "`10`", "`20`", "`30`")),
    ],
)
def test_jede_aufrufstelle_unterscheidet_die_exit_codes_einzeln(
    relativ: str, ueberschrift: str, aufruf: str, codes: tuple[str, ...]
) -> None:
    """Ein Sammelzweig ("alles ausser 0") verbuchte einen unbekannten Code wie einen bekannten."""
    schritt = abschnitt(dateitext(relativ), ueberschrift)
    hinter_dem_aufruf = schritt[schritt.index(aufruf) :]

    fehlend = [code for code in codes if code not in hinter_dem_aufruf]

    assert fehlend == [], f"{relativ} unterscheidet die Codes {fehlend} nicht einzeln."


def test_ship_feature_prueft_die_nachaenderung_aus_ak_7_nach() -> None:
    """Der `main`-Abgleich liegt hinter der Review-Phase - die einzige inhaltliche Aenderung,
    die sonst keine Review mehr sieht."""
    schritt = abschnitt(dateitext(SHIP_FEATURE), "## Schritt 6")
    hinter_dem_abgleich = schritt[schritt.index(MARKE_MERGE_SKRIPT) :]

    assert "review-architecture" in hinter_dem_abgleich
    for gegenstand in ("Nummern-Token", "Dateiname", "down_revision"):
        assert gegenstand in hinter_dem_abgleich


def test_spec_writer_nimmt_die_spec_nummer_von_der_rangregel_aus() -> None:
    text = dateitext(SPEC_WRITER)

    assert SKRIPT in text or "nummern.py" in text
    assert "Rangregel" in text


# --- 4. Die abgeloeste Regel gilt an keiner Stelle mehr -----------------------------------------


def test_adr_0081_traegt_den_teil_vermerk() -> None:
    kopf = dateitext(ADR_0081).split("## Kontext", 1)[0]

    assert "**Teilweise abgelöst:**" in kopf
    assert "0108" in kopf


def test_keine_anweisung_nennt_die_abgeloeste_regel() -> None:
    """Anti-Erosion: null Vorkommen sind der Sollzustand."""
    fundstellen = [pfad for pfad, text in anweisungsdateien() if ABGELOESTE_REGEL.search(text)]

    assert fundstellen == [], (
        f"{fundstellen} weist die abgeloeste Vergabe als Handlungsanweisung aus. Welches "
        "Dokument umzieht und auf welche Nummer, entscheidet seit ADR 0108 der Rang des "
        "Arbeitsstands."
    )


def test_der_waechter_meldet_die_geltende_regel() -> None:
    """Gemessen am **erzeugten** Befund, nicht am Dateitext: Eine Suche ueber dem Quelltext
    bliebe gruen, wenn die Regelnennung in einen anderen Zweig derselben Datei wanderte."""
    sys.path.insert(0, str(Path(__file__).parent))
    import test_dokumentnummern_eindeutig as netz

    (befund,) = netz.dubletten_befunde(
        {"specs/decisions": ["specs/decisions/0069-a.md", "specs/decisions/0069-b.md"]}
    )

    assert "0108" in befund
    assert not ABGELOESTE_REGEL.search(befund), (
        "Der Waechter gibt die abgeloeste Regel als Handlungsanweisung aus - zwei Seiten, die "
        "ihr folgen, landen auf derselben Ersatznummer."
    )


# --- 5. Beide Sicherheitsnetze bleiben unberuehrt ------------------------------------------------


@pytest.mark.parametrize(
    ("relativ", "funktion"),
    [
        (NETZ_DOKUMENTNUMMERN, "def test_keine_nummer_ist_in_einem_verzeichnis_zweimal_vergeben("),
        (NETZ_DOKUMENTNUMMERN, "def test_jedes_dokument_traegt_ein_vierstelliges_nummernpraefix("),
        (NETZ_MIGRATIONSKETTE, "def test_the_migration_chain_resolves_at_all("),
        (NETZ_MIGRATIONSKETTE, "def test_every_revision_id_is_unique("),
        (NETZ_MIGRATIONSKETTE, "def test_there_is_exactly_one_head("),
        (NETZ_MIGRATIONSKETTE, "def test_every_revision_is_reachable_from_the_head("),
    ],
)
def test_beide_netze_fuehren_ihre_tragenden_funktionen_weiterhin(
    relativ: str, funktion: str
) -> None:
    """Die Fruehwarnung tritt neben die beiden Netze, nie an ihre Stelle."""
    assert funktion in dateitext(relativ), (
        f"{funktion!r} fehlt in {relativ}. Was bislang spaetestens beim Zusammenfuehren laut "
        "wird, muss weiterhin laut werden."
    )


def test_die_pruefung_der_migrationskette_bleibt_wortgleich() -> None:
    """`backend/tests/test_migration_chain.py` wird von dieser Story gar nicht angefasst."""
    text = dateitext(NETZ_MIGRATIONSKETTE)

    assert "from alembic.script import ScriptDirectory" in text
    assert "nummern" not in text


# --- 6. Gegenprobe zur Offset-Methodik selbst ----------------------------------------------------


@pytest.mark.parametrize(
    ("text", "erwartet_vertauscht"),
    [
        ("## Schritt 6\n1. a.sh\n2. nummern.py pruefen\n3. git push -u origin\n", False),
        ("## Schritt 6\n1. a.sh\n2. git push -u origin\n3. nummern.py pruefen\n", True),
    ],
)
def test_die_reihenfolgepruefung_unterscheidet_die_beiden_faelle(
    text: str, erwartet_vertauscht: bool
) -> None:
    schritt = abschnitt(text, "## Schritt 6")

    vertauscht = schritt.index("nummern.py pruefen") > schritt.index(MARKE_PUSH)

    assert vertauscht is erwartet_vertauscht


def test_eine_ueberschrift_im_codeblock_beendet_keinen_abschnitt() -> None:
    """Gegenprobe zur Maskierung: ohne sie endete der Abschnitt an der Formatvorlage."""
    text = "## Schritt 6\nvorher\n\n```\n## Abschlussbericht\n**Feld:** wert\n```\n\nnachher\n"

    schritt = abschnitt(text, "## Schritt 6")

    assert "nachher" in schritt
    assert "**Feld:** wert" in schritt
