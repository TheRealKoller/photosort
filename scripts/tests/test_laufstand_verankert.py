r"""Haelt die Verankerung des Laufstands fest - Ausgabepflicht im Lauf, Lesepflicht in der Auskunft.

Gegenstand ist Markdown, das ein Modell zur Laufzeit interpretiert: `.claude/agents/developer.md`
gibt einen Block `## Laufstand` in seine eigene Ausgabe, `.claude/skills/laufstand/SKILL.md` liest
ihn von aussen. Kein Mechanismus dieses Repositoriums konsumiert diesen Block - er entsteht und
vergeht in einem Ausgabefenster. Zugesichert wird hier deshalb ausschliesslich **Nachweisbares**:
dass die Anweisung dasteht, an welcher Stelle sie dasteht, und dass sie nur an einer Stelle steht.

Kein Netzwerk, kein GitHub, kein echtes git ausser `git ls-files`: gelesen werden ausschliesslich
die von Git verwalteten Dateien dieses Repositoriums.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Mapping
from pathlib import Path

import pytest

REPO_WURZEL = Path(__file__).parents[2]

DEVELOPER_PFAD = ".claude/agents/developer.md"
SKILL_PFAD = ".claude/skills/laufstand/SKILL.md"

# --- Der Block selbst ----------------------------------------------------------------------

# Die Ueberschrift des Blocks. Ausschliesslich in `developer.md` als eingezaeunter Codeblock
# definiert - wie die uebrigen Anker dieses Laufs. Eine zweite Definitionsstelle waere ein
# zweites Abbild desselben Formats, und zwei Abbilder driften.
ANKER = "## Laufstand"

# Die drei Zustaende als **geschlossene** Menge. Verglichen wird auf Gleichheit, nicht auf
# Teilmenge: Ein vierter Zustand ("blockiert", "uebersprungen") macht die Auskunft unentscheidbar,
# und ein fehlender dritter laesst "offen" und "erledigt" ununterscheidbar werden.
ZUSTANDSMARKER = frozenset({"erledigt", "in Arbeit", "offen"})

# Der Satz, der die Kardinalitaet innerhalb des Blocks traegt. Ohne ihn ist der Block eine Liste
# von Zeilen, aus der niemand ablesen kann, welcher Schritt gerade laeuft.
EINER_IN_ARBEIT = "genau einer in Arbeit"

# Jede Listenzeile des Blocks fuehrt ihren Zustand in eckigen Klammern. Gelesen werden nur die
# Listenzeilen - eine Klammer im Fliesstext des Blocks ist kein Zustandsmarker.
_ZUSTANDSZEILE = re.compile(r"^\s*-\s*\[([^\]\n]+)\]", re.MULTILINE)

# --- Selbstschutz --------------------------------------------------------------------------

# Untergrenzen weit unter dem Ist-Stand (2026-09-13: 251 Markdown-Dateien im Suchraum, 7
# Agenten-Dateien, 21.000 bzw. 8.000 Zeichen in den beiden gelesenen Dateien). Sie fangen den
# Totalausfall der Aufzaehlung, nicht jede geloeschte Datei: Ein leer oder halb gelesener
# Suchraum darf nie als "genau einmal gefunden" oder "nirgends gefunden" durchgehen.
MINDESTZAHL_DATEIEN_IM_SUCHRAUM = 150
MINDESTZAHL_AGENTEN_DATEIEN = 7
MINDESTGROESSE = {DEVELOPER_PFAD: 10_000, SKILL_PFAD: 3_000}

SUCHRAUM_ORTE = (".claude", "docs", "specs")

_ABSCHNITT = re.compile(r"^## ", re.MULTILINE)
_FENCE = ("```", "~~~")


# --- Reine Funktionen ----------------------------------------------------------------------


def ohne_codebloecke(text: str) -> str:
    """Reine Funktion: leert jede Zeile innerhalb eines Codefence-Blocks.

    Geleert statt entfernt, damit gemeldete Zeilennummern weiterhin auf die echte Datei zeigen.
    Zwingend vor jeder Prosa- und jeder Abwesenheitspruefung: Die **Definition** des Blocks steht
    selbst in einem Codefence und traegt den Anker; ohne diese Behandlung zaehlte sie als
    Anweisung mit und jede Fundstellenzahl waere um eins daneben.
    """
    ergebnis: list[str] = []
    offen = False
    for zeile in text.split("\n"):
        if zeile.lstrip().startswith(_FENCE):
            offen = not offen
            ergebnis.append("")
            continue
        ergebnis.append("" if offen else zeile)
    return "\n".join(ergebnis)


def codebloecke(text: str) -> list[str]:
    """Reine Funktion: alle mit ``` eingezaeunten Bloecke - dort steht eine Definition."""
    return re.findall(r"^```[^\n]*\n(.*?)^```", text, re.MULTILINE | re.DOTALL)


def abschnitt(text: str, ueberschrift: str) -> str:
    """Reine Funktion: der Abschnitt ab `ueberschrift` bis zur naechsten `## `-Zeile.

    Die Abschnittsgrenze ist bei einem Formtest ueber Markdown der wahrscheinlichste stille
    Defekt: Greift sie nicht, zieht der Abschnitt den Rest der Datei in sich und besteht jede
    Zusicherung zufaellig. Sie bekommt deshalb eine eigene Assertion, keinen Kommentar.
    """
    kopf = re.search(rf"^{re.escape(ueberschrift)}", text, re.MULTILINE)
    if kopf is None:
        raise ValueError(
            f"Ueberschrift {ueberschrift!r} nicht gefunden. Ohne sie hat dieser Test keinen "
            "Anker - ein Nullbefund darf dann nicht als 'nichts zu beanstanden' durchgehen."
        )
    naechster = _ABSCHNITT.search(text, kopf.end())
    return text[kopf.start() : naechster.start() if naechster else len(text)]


def blockdefinitionen(abbild: Mapping[str, str]) -> list[str]:
    """Reine Funktion: jede Datei, die den Anker **in einem Codeblock** fuehrt.

    Ein Codeblock mit dem Anker ist eine Definition des Formats; eine Erwaehnung im Fliesstext
    (in Backticks, als Verweis) ist keine und bleibt ausdruecklich frei.
    """
    if not abbild:
        raise ValueError(
            "0 Dateien im Suchraum: Ein leerer Suchraum darf nie als 'genau eine "
            "Definitionsstelle' durchgehen."
        )
    return sorted(
        datei
        for datei, inhalt in abbild.items()
        if any(ANKER in block for block in codebloecke(inhalt))
    )


def formatblock(text: str) -> str:
    """Reine Funktion: der eine Codeblock, der den Anker traegt.

    Wirft, wenn es keinen oder mehr als einen gibt - beides macht jede Aussage ueber "den" Block
    bedeutungslos, und ein stiller Nullbefund waere hier die schlechteste Antwort.
    """
    kandidaten = [block for block in codebloecke(text) if ANKER in block]
    if len(kandidaten) != 1:
        raise ValueError(
            f"{len(kandidaten)} Codebloecke mit {ANKER!r} in der Datei, erwartet genau einer. "
            "Ohne genau einen Block ist nicht entscheidbar, welche Form gilt."
        )
    return kandidaten[0]


def zustaende(block: str) -> list[str]:
    """Reine Funktion: die Zustandsmarker der Listenzeilen, in Fundreihenfolge."""
    return [treffer.strip() for treffer in _ZUSTANDSZEILE.findall(block)]


def formatverstoesse(block: str) -> list[str]:
    """Reine Funktion: die vollstaendige Formpruefung des Blocks."""
    befunde: list[str] = []

    gefunden = set(zustaende(block))
    if gefunden != set(ZUSTANDSMARKER):
        befunde.append(
            f"Der Block fuehrt die Zustaende {sorted(gefunden)}, erwartet genau "
            f"{sorted(ZUSTANDSMARKER)}. Geprueft wird Gleichheit, nicht Teilmenge: Ein vierter "
            "Zustand macht die Auskunft unentscheidbar, ein fehlender dritter laesst zwei "
            "Zustaende ununterscheidbar werden."
        )
    if EINER_IN_ARBEIT not in block:
        befunde.append(
            f"Der Block traegt {EINER_IN_ARBEIT!r} nicht. Ohne diese Kardinalitaet ist er eine "
            "Liste von Zeilen, aus der niemand ablesen kann, welcher Schritt gerade laeuft."
        )
    return befunde


def ausgabepflicht_ausserhalb(abbild: Mapping[str, str]) -> list[str]:
    """Reine Funktion: jede Agenten-Datei ausser `developer.md`, die den Anker nennt.

    Der Geltungsbereich der Pflicht ist ausschliesslich der Umsetzungslauf. Die kurzen
    Konsultationslaeufe bleiben unberuehrt - eine dort eingesickerte Ausgabepflicht waere eine
    zweite, nie gelesene Fortschrittsquelle.
    """
    if len(abbild) < MINDESTZAHL_AGENTEN_DATEIEN:
        raise ValueError(
            f"Nur {len(abbild)} Agenten-Dateien gefunden (erwartet mindestens "
            f"{MINDESTZAHL_AGENTEN_DATEIEN}). Die Aufzaehlung ist kaputt; eine Nullmeldung waere "
            "dann bedeutungslos."
        )
    befunde: list[str] = []
    for datei in sorted(abbild):
        if datei == DEVELOPER_PFAD:
            continue
        sichtbar = ohne_codebloecke(abbild[datei])
        for nummer, zeile in enumerate(sichtbar.split("\n"), start=1):
            if ANKER in zeile:
                befunde.append(f"{datei}:{nummer}")
    return befunde


# --- Duenne Leser --------------------------------------------------------------------------


def suchraum(wurzel: Path = REPO_WURZEL) -> dict[str, str]:
    """Duenner Leser: alle von Git verwalteten `.md` unter `.claude/`, `docs/` und `specs/`.

    Ueber `git ls-files` statt `rglob`: Unterhalb von `.claude/worktrees/` liegen ausgecheckte
    Arbeitsbaeume dieses Repositoriums. Ein Verzeichnislauf faende die Definition dort noch
    einmal je Arbeitsbaum und machte die Einmaligkeitspruefung aus einem Grund rot, der mit
    ihrem Gegenstand nichts zu tun hat - und in CI (frischer Klon) faellt das nie auf.
    """
    ergebnis = subprocess.run(
        ["git", "ls-files", "-z", "--", *SUCHRAUM_ORTE],
        cwd=wurzel,
        capture_output=True,
        check=True,
    )
    pfade = [roh.decode("utf-8") for roh in ergebnis.stdout.split(b"\0") if roh]
    return {
        pfad: (wurzel / pfad).read_text(encoding="utf-8")
        for pfad in pfade
        if pfad.endswith(".md") and (wurzel / pfad).is_file()
    }


def agenten_dateien(wurzel: Path = REPO_WURZEL) -> dict[str, str]:
    """Duenner Leser: die Agenten-Dateien - der Geltungsbereich der Ausgabepflicht."""
    return {
        pfad: inhalt
        for pfad, inhalt in suchraum(wurzel).items()
        if pfad.startswith(".claude/agents/")
    }


def dateitext(pfad: str, wurzel: Path = REPO_WURZEL) -> str:
    return (wurzel / pfad).read_text(encoding="utf-8")


# --- Selbstschutz ----------------------------------------------------------------------------


def test_der_suchraum_hat_eine_plausible_groesse() -> None:
    dateien = suchraum()

    assert len(dateien) >= MINDESTZAHL_DATEIEN_IM_SUCHRAUM, (
        f"Nur {len(dateien)} Markdown-Dateien im Suchraum (erwartet mindestens "
        f"{MINDESTZAHL_DATEIEN_IM_SUCHRAUM}). Die Aufzaehlung ist kaputt; eine Aussage ueber "
        "Einmaligkeit waere dann bedeutungslos."
    )
    assert DEVELOPER_PFAD in dateien, f"{DEVELOPER_PFAD} liegt nicht im Suchraum."


def test_ein_leerer_suchraum_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"0 Dateien im Suchraum"):
        blockdefinitionen({})


def test_eine_leere_agentenliste_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"Agenten-Dateien"):
        ausgabepflicht_ausserhalb({DEVELOPER_PFAD: "Text"})


# --- AK 1/AK 3: der Block ist definiert, und zwar in genau einer Form -------------------------


def test_der_block_ist_in_developer_md_als_codeblock_definiert() -> None:
    """AK 1: eingezaeunt, genau einmal in dieser Datei."""
    block = formatblock(dateitext(DEVELOPER_PFAD))

    assert block.lstrip().startswith(ANKER), (
        f"Der Codeblock beginnt nicht mit {ANKER!r}, sondern mit {block.lstrip()[:40]!r}. Der "
        "Anker ist die erste Zeile der Ausgabe; steht er weiter unten, findet ihn niemand."
    )


def test_der_block_kennt_genau_die_drei_zustaende() -> None:
    """AK 3: geschlossene Menge, plus die Kardinalitaetszusage im Block selbst."""
    befunde = formatverstoesse(formatblock(dateitext(DEVELOPER_PFAD)))

    assert not befunde, "; ".join(befunde)


def test_die_blockdefinition_steht_ausschliesslich_in_developer_md() -> None:
    """AK 7: keine zweite Datei fuehrt eine Kopie - zwei Abbilder desselben Formats driften."""
    stellen = blockdefinitionen(suchraum())

    assert stellen == [DEVELOPER_PFAD], (
        f"Der Block {ANKER!r} wird in {stellen} als Codeblock gefuehrt, erwartet ausschliesslich "
        f"in {DEVELOPER_PFAD}. Eine Erwaehnung im Fliesstext ist davon unberuehrt und bleibt "
        "ausdruecklich frei; eine zweite eingezaeunte Fassung ist eine zweite Quelle."
    )


# --- AK 8: der Geltungsbereich ist der Umsetzungslauf, sonst niemand --------------------------


def test_keine_andere_agenten_datei_traegt_die_ausgabepflicht() -> None:
    befunde = ausgabepflicht_ausserhalb(agenten_dateien())

    assert not befunde, (
        f"{ANKER!r} steht in {befunde}. Die Pflicht gilt ausschliesslich fuer den "
        "Umsetzungslauf; die kurzen Konsultationslaeufe bleiben unberuehrt. Eine zweite Quelle "
        "des Fortschritts hat bei der ersten Abweichung keine."
    )


# --- Gegenproben an synthetischem Text --------------------------------------------------------

_ECHTER_BLOCK = (
    "## Laufstand\n\n"
    "**Spec:** <NNNN> — <Kurztitel>\n\n"
    "- [erledigt] <Teilschritt 1>\n"
    "- [in Arbeit] <Teilschritt 2>\n"
    "- [offen] <Teilschritt 3>\n\n"
    "Jeder Teilschritt eine Zeile, genau einer in Arbeit, der Plan jedes Mal vollständig.\n"
)


def test_die_erwartete_blockform_gilt_nicht_als_verstoss() -> None:
    assert formatverstoesse(_ECHTER_BLOCK) == []


def test_ein_vierter_zustand_wird_gemeldet() -> None:
    """Gegenprobe zur Gleichheit: Eine Teilmengenpruefung liesse genau das durch."""
    befunde = formatverstoesse(_ECHTER_BLOCK + "- [blockiert] <Teilschritt 4>\n")

    assert len(befunde) == 1
    assert "blockiert" in befunde[0]


def test_ein_fehlender_zustand_wird_gemeldet() -> None:
    ohne = _ECHTER_BLOCK.replace("- [erledigt] <Teilschritt 1>\n", "")

    befunde = formatverstoesse(ohne)

    assert len(befunde) == 1
    assert "erledigt" in befunde[0]


def test_ein_block_ohne_die_kardinalitaet_wird_gemeldet() -> None:
    ohne = _ECHTER_BLOCK.replace(EINER_IN_ARBEIT, "die Reihenfolge steht fest")

    befunde = formatverstoesse(ohne)

    assert len(befunde) == 1
    assert EINER_IN_ARBEIT in befunde[0]


def test_eine_klammer_im_fliesstext_ist_kein_zustandsmarker() -> None:
    """Sonst zoege jede eckige Klammer des Blocks in die Zustandsmenge."""
    mit_fliesstext = _ECHTER_BLOCK + "\nEine Anmerkung [in Klammern] zaehlt hier nicht mit.\n"

    assert formatverstoesse(mit_fliesstext) == []


def test_eine_erwaehnung_im_fliesstext_ist_keine_definition() -> None:
    """Gegenprobe zur Methodik: Nur ein eingezaeunter Block definiert."""
    abbild = {
        "a.md": f"Der Lauf gibt den Block `{ANKER}` aus.",
        "b.md": f"Text\n\n```\n{ANKER}\n\n- [offen] Schritt\n```\n",
    }

    assert blockdefinitionen(abbild) == ["b.md"]


def test_zwei_definitionsstellen_werden_beide_gemeldet() -> None:
    block = f"```\n{ANKER}\n```\n"

    assert blockdefinitionen({"a.md": block, "b.md": block}) == ["a.md", "b.md"]


def test_mehrere_bloecke_in_einer_datei_scheitern_laut_statt_still() -> None:
    text = f"```\n{ANKER}\n```\n\n```\n{ANKER}\n```\n"

    with pytest.raises(ValueError, match=r"2 Codebloecke"):
        formatblock(text)


def test_ein_anker_in_einer_anderen_agenten_datei_wird_gemeldet() -> None:
    abbild = {
        DEVELOPER_PFAD: f"```\n{ANKER}\n```\n",
        ".claude/agents/architect.md": f"Zeile\nGib den Block {ANKER} aus.\n",
        ".claude/agents/requirements-engineer.md": "Text\n",
        ".claude/agents/research-engineer.md": "Text\n",
        ".claude/agents/security-engineer.md": "Text\n",
        ".claude/agents/test-engineer.md": "Text\n",
        ".claude/agents/ux-ui-designer.md": "Text\n",
    }

    assert ausgabepflicht_ausserhalb(abbild) == [".claude/agents/architect.md:2"]


def test_ein_anker_im_codeblock_einer_anderen_agenten_datei_zaehlt_nicht() -> None:
    """Die Gegenrichtung: Ein Formatzitat in einem Codefence ist keine Anweisung.

    Ohne diese Behandlung waere die Abwesenheitspruefung an der eigenen Dokumentation rot - und
    der naheliegende Reparaturgriff waere eine Ausnahmeliste je Datei gewesen, die spaeter jeden
    echten Verstoss in derselben Datei mitgedeckt haette.
    """
    abbild = {
        DEVELOPER_PFAD: f"```\n{ANKER}\n```\n",
        ".claude/agents/architect.md": f"Text\n\n```\n{ANKER}\n```\n",
        ".claude/agents/requirements-engineer.md": "Text\n",
        ".claude/agents/research-engineer.md": "Text\n",
        ".claude/agents/security-engineer.md": "Text\n",
        ".claude/agents/test-engineer.md": "Text\n",
        ".claude/agents/ux-ui-designer.md": "Text\n",
    }

    assert ausgabepflicht_ausserhalb(abbild) == []


def test_der_abschnittsleser_schneidet_an_der_naechsten_ueberschrift() -> None:
    text = "## Schritt 2\nA\n\n## Schritt 3\nB\n"

    assert abschnitt(text, "## Schritt 2").strip() == "## Schritt 2\nA"
    assert "B" not in abschnitt(text, "## Schritt 2")


def test_eine_fehlende_ueberschrift_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"nicht gefunden"):
        abschnitt("# Titel\n\nNur Prosa.\n", "## Schritt 2")
