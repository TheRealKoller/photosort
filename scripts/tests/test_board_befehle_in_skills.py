"""Prueft die Board-Befehlszeilen in den Skill-/Agent-Dateien statisch.

Seit ADR 0057 gibt es kein Board-Werkzeug mehr, das einen Statuswert vor dem Schreiben gegen
eine mitgefuehrte Konstantenliste pruefen koennte. Ein Tippfehler in `--value "In progress"`
oder ein zurueckgebliebenes `--value Todo` fiele sonst erst zur Laufzeit auf - mitten in einer
Session, nachdem der Ablauf bereits laeuft. Dieser Test nimmt genau diese Pruefung wieder auf,
eine Ebene hoeher: Er parst die `gh project item-edit`-Aufrufe unter `.claude/**` und haelt die
geschriebenen `--field`/`--value`-Paare gegen die Optionsmengen des Boards.

Bewusst **kein** freier Textscan nach dem Wort "Todo" ueber `.claude/`/`docs/`: "Todo" ist ein
zu gewoehnliches Wort, ein solcher Test waere Formulierungspolizei mit Falschmeldungen statt
einer Aussage ueber das Board. Ueber die Wertemenge ist `Todo` ohnehin miterschlagen - es ist
schlicht kein zulaessiger Wert mehr.

Zweiter Prueffall in derselben Datei: Jeder Ablauf-Skill mit Board-Schreibzugriff fuehrt den
Berichtsabschnitt `## Lokal nachzuholen` woertlich (Nachfolger der entsprechenden Zusicherung
aus ADR 0056, deren zweite Haelfte mit der Vorabmessung entfallen ist).

Kein echtes `gh`, kein Netzwerk - gelesen werden ausschliesslich Dateien dieses Repositories.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_WURZEL = Path(__file__).parents[2]

PROJEKT_NUMMER = "8"
PROJEKT_OWNER = "TheRealKoller"

# Die Optionsmengen des Felds am echten Board, plus die Platzhalterformen, die in der
# Befehlssammlung (`.claude/skills/github-board/SKILL.md`) als Vorlage stehen. `Todo` ist seit
# ADR 0057 keine Option des Felds `Status` mehr und deshalb hier nicht aufgefuehrt.
ERLAUBTE_WERTE: dict[str, frozenset[str]] = {
    "Status": frozenset(
        {"Unrefined", "Ready", "In Progress", "Review", "Done", "<Wert>"}
    ),
    "Priorität": frozenset({"Hoch", "Mittel", "Niedrig", "<Hoch|Mittel|Niedrig>"}),
}

# Die vier Ablauf-Skills mit Board-Schreibzugriff.
ABLAUF_SKILLS = ("capture", "refinement", "spec-writer", "ship-feature")

BERICHTSABSCHNITT = "## Lokal nachzuholen"

# Ein Befehl steht am Zeilenanfang; eine blosse *Erwaehnung* steht mitten im Fliesstext
# ("... kennt `gh project item-edit` die namensbasierte Form"). Ohne diese Verankerung meldete
# der Parser jede Prosa-Zeile, die das Kommando nennt, als Aufruf ohne --field.
#
# Vor dem Kommando zugelassen sind ausschliesslich Formen, die es weiterhin als Befehl lesbar
# lassen: Einrueckung, ein Listenpunkt, ein Inline-Code-Etikett wie `status-review`: (so stehen
# die Nachhol-Befehle in den Berichtsvorlagen), ein Shell-Prompt, ein oeffnender Backtick. Ohne
# den Listen-Zweig entgingen dem Test genau die Vorlagen unter `## Lokal nachzuholen`.
_AUFRUF = re.compile(
    r"^[ \t]*(?:[-*+][ \t]+)?(?:`[^`\n]*`:[ \t]*)?[`$]?[ \t]*gh project item-edit\b[^\n]*",
    re.MULTILINE,
)
_PROJEKT = re.compile(r"gh project item-edit\s+(\S+)")
_OWNER = re.compile(r"--owner\s+(\S+)")
# Werte kommen doppelt, einfach oder gar nicht in Anfuehrungszeichen vor. Die unquotierte Form
# wird ausdruecklich mit geparst: Ein zurueckgebliebenes `--value Todo` muss auffallen, nicht
# unbemerkt durch den Parser fallen, weil es keine Anfuehrungszeichen trug.
_FELD = re.compile(r"""--field\s+(?:"([^"]*)"|'([^']*)'|([^\s"']\S*))""")
_WERT = re.compile(r"""--value\s+(?:"([^"]*)"|'([^']*)'|([^\s"']\S*))""")


@dataclass(frozen=True)
class Aufruf:
    """Ein einzelner `gh project item-edit`-Aufruf, so wie er in einer Datei steht."""

    datei: str
    zeile: int
    rohtext: str
    projekt: str | None
    owner: str | None
    felder: tuple[str, ...]
    werte: tuple[str, ...]

    @property
    def fundstelle(self) -> str:
        return f"{self.datei}:{self.zeile}"


def _erste_gruppe(treffer: re.Match[str]) -> str:
    doppelt, einfach, blank = treffer.groups()
    return doppelt if doppelt is not None else (einfach if einfach is not None else blank)


def aufrufe_aus_text(text: str, datei: str = "<text>") -> list[Aufruf]:
    """Reine Funktion: sammelt die Board-Aufrufe eines Textes samt Fundstelle."""
    aufrufe: list[Aufruf] = []
    for treffer in _AUFRUF.finditer(text):
        rohtext = treffer.group(0)
        projekt = _PROJEKT.search(rohtext)
        owner = _OWNER.search(rohtext)
        aufrufe.append(
            Aufruf(
                datei=datei,
                zeile=text.count("\n", 0, treffer.start()) + 1,
                rohtext=rohtext,
                projekt=projekt.group(1) if projekt else None,
                owner=owner.group(1) if owner else None,
                felder=tuple(_erste_gruppe(t) for t in _FELD.finditer(rohtext)),
                werte=tuple(_erste_gruppe(t) for t in _WERT.finditer(rohtext)),
            )
        )
    return aufrufe


def verstoesse(aufrufe: list[Aufruf]) -> list[str]:
    """Reine Funktion: meldet je Verstoss Fundstelle und Grund."""
    befunde: list[str] = []
    for aufruf in aufrufe:
        if aufruf.projekt != PROJEKT_NUMMER:
            befunde.append(
                f"{aufruf.fundstelle}: Projektnummer {aufruf.projekt!r} statt "
                f"{PROJEKT_NUMMER!r} - der Aufruf zeigt auf ein anderes Board."
            )
        if aufruf.owner != PROJEKT_OWNER:
            befunde.append(
                f"{aufruf.fundstelle}: --owner {aufruf.owner!r} statt {PROJEKT_OWNER!r}."
            )
        if len(aufruf.felder) != 1 or len(aufruf.werte) != 1:
            befunde.append(
                f"{aufruf.fundstelle}: erwartet genau ein --field und ein --value, gefunden "
                f"{len(aufruf.felder)} bzw. {len(aufruf.werte)} ({aufruf.rohtext})."
            )
            continue
        feld, wert = aufruf.felder[0], aufruf.werte[0]
        if feld not in ERLAUBTE_WERTE:
            befunde.append(
                f"{aufruf.fundstelle}: unbekanntes Feld {feld!r}; das Board kennt "
                f"{sorted(ERLAUBTE_WERTE)}."
            )
            continue
        if wert not in ERLAUBTE_WERTE[feld]:
            befunde.append(
                f"{aufruf.fundstelle}: {wert!r} ist keine Option des Felds {feld!r}. "
                f"Zulaessig sind {sorted(ERLAUBTE_WERTE[feld])}."
            )
    return befunde


def aufrufe_im_abbild(abbild: Mapping[str, str]) -> list[Aufruf]:
    """Reine Funktion ueber ein Pfad->Text-Abbild; ein leeres Ergebnis ist ein Fehlerfall."""
    aufrufe: list[Aufruf] = []
    for datei in sorted(abbild):
        aufrufe.extend(aufrufe_aus_text(abbild[datei], datei))

    if not aufrufe:
        raise ValueError(
            "0 Treffer: keine einzige `gh project item-edit`-Zeile gefunden. Entweder ist der "
            "Suchraum kaputt, oder die Befehlsform hat sich geaendert - dann ist dieser Test "
            "mitzuziehen, sonst prueft er lautlos nichts mehr."
        )
    return aufrufe


def claude_dateien(wurzel: Path = REPO_WURZEL) -> dict[str, str]:
    """Duenner Leser: die von Git verwalteten Dateien unter `.claude/`.

    Ueber `git ls-files` statt `rglob`, damit nicht verwaltete Arbeitskopien (etwa ein
    Worktree unterhalb von `.claude/`) nicht in den Suchraum geraten.
    """
    ergebnis = subprocess.run(
        ["git", "ls-files", "-z", "--", ".claude"],
        cwd=wurzel,
        capture_output=True,
        check=True,
    )
    pfade = [pfad.decode("utf-8") for pfad in ergebnis.stdout.split(b"\0") if pfad]
    return {pfad: (wurzel / pfad).read_text(encoding="utf-8") for pfad in pfade}


def test_alle_board_aufrufe_nennen_gueltige_felder_und_werte() -> None:
    aufrufe = aufrufe_im_abbild(claude_dateien())

    befunde = verstoesse(aufrufe)

    assert not befunde, "Ungueltige Board-Befehlszeile(n) unter .claude/: " + "; ".join(befunde)


def test_der_suchraum_enthaelt_die_befehlssammlung() -> None:
    """Gegenprobe zum Leser: die Sammlung selbst muss im Suchraum liegen."""
    dateien = claude_dateien()

    assert ".claude/skills/github-board/SKILL.md" in dateien


@pytest.mark.parametrize("wert", ["Todo", "In progress", "done", "Erledigt"])
def test_ein_ungueltiger_statuswert_wird_gemeldet(wert: str) -> None:
    text = (
        f'gh project item-edit 8 --owner TheRealKoller --url <url> --field "Status" '
        f'--value "{wert}"\n'
    )

    befunde = verstoesse(aufrufe_aus_text(text, "skill.md"))

    assert len(befunde) == 1
    assert wert in befunde[0]


def test_ein_unquotierter_wert_faellt_nicht_durch_den_parser() -> None:
    text = "gh project item-edit 8 --owner TheRealKoller --url <url> --field Status --value Todo\n"

    befunde = verstoesse(aufrufe_aus_text(text, "skill.md"))

    assert len(befunde) == 1
    assert "'Todo'" in befunde[0]


@pytest.mark.parametrize(
    ("feld", "wert"),
    [
        ("Status", "Unrefined"),
        ("Status", "Ready"),
        ("Status", "In Progress"),
        ("Status", "Review"),
        ("Status", "Done"),
        ("Status", "<Wert>"),
        ("Priorität", "Hoch"),
        ("Priorität", "<Hoch|Mittel|Niedrig>"),
    ],
)
def test_die_gueltigen_werte_und_platzhalter_gelten_nicht_als_verstoss(
    feld: str, wert: str
) -> None:
    text = (
        f'gh project item-edit 8 --owner TheRealKoller --url <issue-url> --field "{feld}" '
        f'--value "{wert}"\n'
    )

    assert verstoesse(aufrufe_aus_text(text, "skill.md")) == []


def test_ein_unbekanntes_feld_wird_gemeldet() -> None:
    text = 'gh project item-edit 8 --owner TheRealKoller --field "Spalte" --value "Ready"\n'

    befunde = verstoesse(aufrufe_aus_text(text, "skill.md"))

    assert len(befunde) == 1
    assert "'Spalte'" in befunde[0]


def test_eine_falsche_projektnummer_wird_gemeldet() -> None:
    text = 'gh project item-edit 9 --owner TheRealKoller --field "Status" --value "Ready"\n'

    befunde = verstoesse(aufrufe_aus_text(text, "skill.md"))

    assert len(befunde) == 1
    assert "Projektnummer" in befunde[0]


def test_ein_fremder_owner_wird_gemeldet() -> None:
    text = 'gh project item-edit 8 --owner Fremd --field "Status" --value "Ready"\n'

    befunde = verstoesse(aufrufe_aus_text(text, "skill.md"))

    assert len(befunde) == 1
    assert "--owner" in befunde[0]


def test_ein_aufruf_ohne_feld_und_wert_wird_gemeldet() -> None:
    text = "gh project item-edit 8 --owner TheRealKoller --url <issue-url>\n"

    befunde = verstoesse(aufrufe_aus_text(text, "skill.md"))

    assert len(befunde) == 1
    assert "genau ein --field" in befunde[0]


def test_die_fundstelle_nennt_datei_und_zeile() -> None:
    text = 'Text\n\ngh project item-edit 8 --owner Fremd --field "Status" --value "Ready"\n'

    befunde = verstoesse(aufrufe_aus_text(text, "skills/x/SKILL.md"))

    assert befunde[0].startswith("skills/x/SKILL.md:3:")


def test_zwei_aufrufe_in_einer_datei_werden_einzeln_gelesen() -> None:
    text = (
        'gh project item-edit 8 --owner TheRealKoller --field "Status" --value "Ready"\n'
        'gh project item-edit 8 --owner TheRealKoller --field "Priorität" --value "Hoch"\n'
    )

    aufrufe = aufrufe_aus_text(text, "skill.md")

    assert [aufruf.zeile for aufruf in aufrufe] == [1, 2]
    assert verstoesse(aufrufe) == []


def test_eine_erwaehnung_im_fliesstext_gilt_nicht_als_aufruf() -> None:
    """Prosa nennt das Kommando, ruft es aber nicht - sonst meldet der Parser Falschbefunde."""
    text = "erst ab dort kennt `gh project item-edit` die namensbasierte Form.\n"

    assert aufrufe_aus_text(text, "skill.md") == []


@pytest.mark.parametrize(
    "zeile",
    [
        'gh project item-edit 8 --owner TheRealKoller --field "Status" --value "Ready"',
        '  gh project item-edit 8 --owner TheRealKoller --field "Status" --value "Ready"',
        '$ gh project item-edit 8 --owner TheRealKoller --field "Status" --value "Ready"',
        '`gh project item-edit 8 --owner TheRealKoller --field "Status" --value "Ready"`',
        '- gh project item-edit 8 --owner TheRealKoller --field "Status" --value "Ready"',
        '- `status-review`: `gh project item-edit 8 --owner TheRealKoller '
        '--field "Status" --value "Ready"`',
    ],
)
def test_ein_aufruf_am_zeilenanfang_wird_in_jeder_schreibform_gelesen(zeile: str) -> None:
    aufrufe = aufrufe_aus_text(zeile + "\n", "skill.md")

    assert len(aufrufe) == 1
    assert verstoesse(aufrufe) == []


def test_ein_suchraum_ohne_board_aufruf_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"0 Treffer"):
        aufrufe_im_abbild({"skills/x/SKILL.md": "Nur Prosa, kein Board-Aufruf.\n"})


@pytest.mark.parametrize("skill", ABLAUF_SKILLS)
def test_jeder_ablauf_skill_fuehrt_den_berichtsabschnitt_woertlich(skill: str) -> None:
    pfad = REPO_WURZEL / ".claude" / "skills" / skill / "SKILL.md"
    inhalt = pfad.read_text(encoding="utf-8")

    assert BERICHTSABSCHNITT in inhalt, (
        f"{pfad} fuehrt den Abschnitt {BERICHTSABSCHNITT!r} nicht mehr woertlich. Ohne ihn "
        "verschwindet ein fehlgeschlagener Board-Zugriff lautlos, statt als nachholbarer "
        "Schritt im Bericht zu stehen."
    )
