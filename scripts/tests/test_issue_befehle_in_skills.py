"""Prueft die `gh issue`-Befehlszeilen in den Skill-/Agent-Dateien statisch.

Der Issue-Zugriff besteht aus einzelnen `gh`-Befehlen im Skill-Text; es gibt kein Werkzeug, das
einen Wert vor dem Absetzen pruefen koennte. Zwei Dinge fielen sonst erst zur Laufzeit auf -
mitten in einer Session, gegen ein oeffentliches Issue:

* Die **Form**: Freitext gelangt nie in eine Kommandozeile. Ein Titel geht ausschliesslich als
  ``--title "$(cat <pfad>)"`` hinein - die doppelten Anfuehrungszeichen sind tragend, ohne sie
  zerlegte die Shell den Dateiinhalt an Leerzeichen und expandierte Globs. Ein Body geht
  ausschliesslich ueber `--body-file`, und die schreibenden Verben tragen `--repo`.
* Die **Reihenfolge** in `refinement/SKILL.md`: Der Titel wird hinter dem Body und vor dem
  Statuswechsel auf `Ready` geschrieben. Rutschte die Titel-Stelle hinter die `Ready`-Stelle,
  erreichte das Issue den Status auch dann, wenn das Schreiben des Titels scheitert.

Die Reihenfolge-Pruefung ist seit ADR 0060 **ueber die Operations-IDs verankert**, nicht mehr
ueber Befehlszeilen: Die Befehle sind in den Katalog gezogen, die Reihenfolge ist aber eine
Eigenschaft des *Ablaufs* und gehoert ohnehin dorthin, wo der Ablauf steht. Sie ueberlebt den
Umbau damit als Aussage statt als Zeilennummer-Zufall. Bedingung (a) aus der Spec-0288-Sektion des
Testkonzepts ("ueber geparste Aufrufe, nie ueber `text.index`") bekommt dabei nur einen neuen
Gegenstand: An die Stelle des geparsten Aufrufs tritt die **Ausfuehrungsstelle**. Eine ID ist ein
Wort und steht auch in Prosa ("scheitert `issue-titel-schreiben`, entfaellt
`board-status-setzen`") - ohne eine maschinell erkennbare Form fiele die Aussage auf genau die
Textstellen-Suche zurueck, die (a) verbietet. Verbindliche Form deshalb: **Eine Ausfuehrungsstelle
nennt ihre ID zeilenanfangs-verankert in Backticks**, nach optionaler Einrueckung, einem
Listenpunkt oder einer Schrittnummer. Erwaehnungen im Fliesstext bleiben frei formulierbar und
zaehlen nicht.

Der frueher hier gefuehrte Fall "Titel und Body in *einem* Befehl" hat mit dem Umzug in den
Katalog einen staerkeren Gegenstand bekommen und steht deshalb nicht mehr in dieser Datei: Eine
kombinierte Operation braeuchte eine eigene ID, und die Menge der Katalog-IDs ist geschlossen
(`test_github_zugriff_an_einer_stelle.py`). Sie faellt dort auf, nicht erst an der Reihenfolge.

Bewusst **kein** Wortscan auf die inhaltlichen Zusagen des Ablaufs (passt der Titel noch, ist die
neue Fassung gut, nennt die Zusammenfassung beide Fassungen): Diese Zusagen haben im Repository
keinen Gegenstand, ein Textscan darauf waere Formulierungspolizei mit Falschmeldungen.

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

REPO = "TheRealKoller/photosort"

# Die Verben, die etwas am Issue veraendern: Sie tragen `--repo`, damit der Aufruf nicht vom
# zufaelligen Arbeitsverzeichnis der Session abhaengt. `view` ist ausgenommen - die beiden
# bestehenden Lese-Aufrufe tragen bewusst kein `--repo`.
SCHREIBENDE_VERBEN = frozenset({"create", "edit", "close", "comment"})
LESENDE_VERBEN = frozenset({"view"})

BEFEHLSSAMMLUNG = ".claude/skills/github-access/SKILL.md"
REFINEMENT = ".claude/skills/refinement/SKILL.md"

# Die drei Operationen, deren Reihenfolge das Ablauf-Gate aus Spec 0288 traegt.
BODY_OPERATION = "issue-body-schreiben"
TITEL_OPERATION = "issue-titel-schreiben"
STATUS_OPERATION = "board-status-setzen"
READY = "`Ready`"

# Ein Befehl steht am Zeilenanfang; eine blosse *Erwaehnung* steht mitten im Fliesstext. Vor dem
# Kommando zugelassen sind ausschliesslich Formen, die es weiterhin als Befehl lesbar lassen:
# Einrueckung, ein Listenpunkt, ein Inline-Code-Etikett wie `titel-edit`:, ein Shell-Prompt, ein
# oeffnender Backtick.
_AUFRUF = re.compile(
    r"^[ \t]*(?:[-*+][ \t]+)?(?:`[^`\n]*`:[ \t]*)?[`$]?[ \t]*"
    r"gh issue (?P<verb>[a-z][a-z-]*)\b(?P<rest>[^\n]*)",
    re.MULTILINE,
)
_REPO = re.compile(r"--repo\s+(\S+)")
# `--body\b` traefe auch `--body-file` (die Wortgrenze liegt vor dem Bindestrich) und meldete den
# korrekten Bestand als Verstoss. Dieselbe Falle gilt fuer `--title`, daher beide Male
# `(?![-\w])`.
_TITEL = re.compile(r"--title(?![-\w])")
_TITEL_WOHLGEFORMT = re.compile(r'--title\s+"\$\(cat\s+[^"\s)]+\)"')
_INLINE_BODY = re.compile(r"--body(?![-\w])")
_BODY_DATEI = re.compile(r"--body-file(?![-\w])")
# Eine Ausfuehrungsstelle: die Operations-ID in Backticks, am Zeilenanfang nach optionaler
# Einrueckung, einem Listenpunkt oder einer Schrittnummer. Der Rest der Zeile wird mitgefuehrt,
# weil der geschriebene *Wert* dort steht ("`board-status-setzen` mit Wert `Ready`") - ohne ihn
# liesse sich ein `Ready`-Statuswechsel nicht von einem `In Progress`-Statuswechsel trennen.
_AUSFUEHRUNGSSTELLE = re.compile(
    r"^[ \t]*(?:[-*+][ \t]+|\d+\.[ \t]+)?`(?P<id>[a-z][a-z-]*)`(?P<rest>[^\n]*)",
    re.MULTILINE,
)


@dataclass(frozen=True)
class Aufruf:
    """Ein einzelner `gh issue`-Aufruf, so wie er in einer Datei steht."""

    datei: str
    zeile: int
    verb: str
    rohtext: str
    repo: str | None

    @property
    def fundstelle(self) -> str:
        return f"{self.datei}:{self.zeile}"

    @property
    def schreibt_titel(self) -> bool:
        return bool(_TITEL.search(self.rohtext))

    @property
    def schreibt_body(self) -> bool:
        return bool(_BODY_DATEI.search(self.rohtext))


def aufrufe_aus_text(text: str, datei: str = "<text>") -> list[Aufruf]:
    """Reine Funktion: sammelt die `gh issue`-Aufrufe eines Textes samt Fundstelle.

    Eine Erwaehnung im Fliesstext wird daran erkannt, dass hinter dem Verb (ggf. nach
    Leerzeichen) ein schliessender Backtick steht: `` `gh issue create` wird dafuer nicht
    wiederholt`` ist Prosa, kein Aufruf ohne `--repo`.
    """
    aufrufe: list[Aufruf] = []
    for treffer in _AUFRUF.finditer(text):
        if treffer.group("rest").lstrip(" \t").startswith("`"):
            continue
        rohtext = treffer.group(0)
        repo = _REPO.search(rohtext)
        aufrufe.append(
            Aufruf(
                datei=datei,
                zeile=text.count("\n", 0, treffer.start()) + 1,
                verb=treffer.group("verb"),
                rohtext=rohtext,
                repo=repo.group(1) if repo else None,
            )
        )
    return aufrufe


def form_verstoesse(aufrufe: list[Aufruf]) -> list[str]:
    """Reine Funktion: meldet je Verstoss gegen die Befehlsform Fundstelle und Grund."""
    befunde: list[str] = []
    for aufruf in aufrufe:
        if aufruf.verb not in SCHREIBENDE_VERBEN | LESENDE_VERBEN:
            befunde.append(
                f"{aufruf.fundstelle}: unbekanntes Verb {aufruf.verb!r}. Bekannt sind "
                f"{sorted(SCHREIBENDE_VERBEN | LESENDE_VERBEN)} - entweder ein Tippfehler, oder "
                "dieser Test ist mitzuziehen."
            )
            continue
        if aufruf.verb in SCHREIBENDE_VERBEN and aufruf.repo != REPO:
            befunde.append(
                f"{aufruf.fundstelle}: --repo {aufruf.repo!r} statt {REPO!r} bei einem "
                f"schreibenden Aufruf ({aufruf.verb})."
            )
        if aufruf.schreibt_titel and not _TITEL_WOHLGEFORMT.search(aufruf.rohtext):
            befunde.append(
                f'{aufruf.fundstelle}: --title muss genau als --title "$(cat <pfad>)" '
                "geschrieben werden - die doppelten Anfuehrungszeichen sind tragend, und ein "
                f"Titel-Literal ist Freitext in einer Kommandozeile ({aufruf.rohtext})."
            )
        if _INLINE_BODY.search(aufruf.rohtext):
            befunde.append(
                f"{aufruf.fundstelle}: Bodies gehen ausschliesslich ueber --body-file, nie als "
                f"--body in der Kommandozeile ({aufruf.rohtext})."
            )
    return befunde


@dataclass(frozen=True)
class Ausfuehrungsstelle:
    """Eine Stelle, an der ein Ablauf eine Operation ausfuehrt - ID plus Rest der Zeile."""

    datei: str
    zeile: int
    id: str
    rest: str

    @property
    def fundstelle(self) -> str:
        return f"{self.datei}:{self.zeile}"


def ausfuehrungsstellen(text: str, datei: str = "<text>") -> list[Ausfuehrungsstelle]:
    """Reine Funktion: sammelt die Ausfuehrungsstellen eines Textes samt Fundstelle.

    Eine Erwaehnung im Fliesstext ("scheitert `issue-titel-schreiben`, entfaellt …") wird nicht
    mitgezaehlt: Sie steht nicht am Zeilenanfang. Die Trennung ist dieselbe wie bei den
    Befehlszeilen, nur auf IDs statt auf Kommandos.
    """
    return [
        Ausfuehrungsstelle(
            datei=datei,
            zeile=text.count("\n", 0, treffer.start()) + 1,
            id=treffer.group("id"),
            rest=treffer.group("rest"),
        )
        for treffer in _AUSFUEHRUNGSSTELLE.finditer(text)
    ]


def reihenfolge_verstoesse(text: str, datei: str = "<text>") -> list[str]:
    """Reine Funktion: prueft die Kette Body -> Titel -> `Ready` ueber Ausfuehrungsstellen.

    Ausdruecklich **nicht** ueber Textstellen (`text.index("issue-titel-schreiben")`): Der
    Skill-Text nennt beide IDs auch in Prosa, eine Suche nach der Zeichenkette kehrte die Aussage
    um. Beide Existenz-Zusicherungen haben eine eigene Meldung - ohne sie waere die
    Reihenfolge-Aussage leer wahr, sobald eine der beiden Stellen verschwindet.
    """
    stellen = ausfuehrungsstellen(text, datei)
    body = [stelle for stelle in stellen if stelle.id == BODY_OPERATION]
    titel = [stelle for stelle in stellen if stelle.id == TITEL_OPERATION]
    ready = [
        stelle
        for stelle in stellen
        if stelle.id == STATUS_OPERATION and READY in stelle.rest
    ]

    befunde: list[str] = []
    if not titel:
        befunde.append(
            f"{datei}: keine Ausfuehrungsstelle von `{TITEL_OPERATION}` gefunden. Ohne sie ist "
            "die Reihenfolge-Aussage leer wahr - der Ablauf schaerft den Issue-Titel nicht mehr. "
            "Eine Ausfuehrungsstelle nennt ihre ID zeilenanfangs-verankert in Backticks."
        )
    if not body:
        befunde.append(
            f"{datei}: keine Ausfuehrungsstelle von `{BODY_OPERATION}` gefunden. Der Body ist die "
            "fachliche Arbeit des Ablaufs; ohne ihn ist die Reihenfolge gegenstandslos."
        )
    if not titel or not body:
        return befunde

    if not body[0].zeile < titel[0].zeile:
        befunde.append(
            f"{titel[0].fundstelle}: `{TITEL_OPERATION}` steht nicht hinter `{BODY_OPERATION}` "
            f"({body[0].fundstelle}). Scheitert der Titel, soll der geschaerfte Body bereits am "
            "Issue stehen."
        )
    zu_frueh = [stelle.zeile for stelle in ready if stelle.zeile <= titel[0].zeile]
    if zu_frueh:
        befunde.append(
            f"{titel[0].fundstelle}: `{TITEL_OPERATION}` steht nicht vor jeder "
            f"Ausfuehrungsstelle von `{STATUS_OPERATION}` mit Wert {READY} (Zeile(n) "
            f"{zu_frueh}). Scheitert der Titel, darf das Issue `Ready` nicht mehr erreichen."
        )
    return befunde


def aufrufe_im_abbild(abbild: Mapping[str, str]) -> list[Aufruf]:
    """Reine Funktion ueber ein Pfad->Text-Abbild; ein leeres Ergebnis ist ein Fehlerfall."""
    aufrufe: list[Aufruf] = []
    for datei in sorted(abbild):
        aufrufe.extend(aufrufe_aus_text(abbild[datei], datei))

    if not aufrufe:
        raise ValueError(
            "0 Treffer: keine einzige `gh issue`-Zeile gefunden. Entweder ist der Suchraum "
            "kaputt, oder die Befehlsform hat sich geaendert - dann ist dieser Test mitzuziehen, "
            "sonst prueft er lautlos nichts mehr."
        )
    return aufrufe


def claude_dateien(wurzel: Path = REPO_WURZEL) -> dict[str, str]:
    """Duenner Leser: die von Git verwalteten Dateien unter `.claude/`.

    Ueber `git ls-files` statt `rglob`, damit nicht verwaltete Arbeitskopien (etwa ein Worktree
    unterhalb von `.claude/`) nicht in den Suchraum geraten.
    """
    ergebnis = subprocess.run(
        ["git", "ls-files", "-z", "--", ".claude"],
        cwd=wurzel,
        capture_output=True,
        check=True,
    )
    pfade = [pfad.decode("utf-8") for pfad in ergebnis.stdout.split(b"\0") if pfad]
    return {pfad: (wurzel / pfad).read_text(encoding="utf-8") for pfad in pfade}


def test_alle_issue_aufrufe_halten_die_verbindliche_form() -> None:
    aufrufe = aufrufe_im_abbild(claude_dateien())

    befunde = form_verstoesse(aufrufe)

    assert not befunde, "Unzulaessige `gh issue`-Befehlszeile(n) unter .claude/: " + "; ".join(
        befunde
    )


def test_der_suchraum_enthaelt_die_befehlssammlung() -> None:
    """Gegenprobe zum Leser: die Sammlung selbst muss im Suchraum liegen."""
    dateien = claude_dateien()

    assert BEFEHLSSAMMLUNG in dateien


def test_die_befehlssammlung_fuehrt_die_titel_befehlsform() -> None:
    """Gegenprobe: Ohne die Zeile in der Sammlung haette der Ablauf keine Vorlage."""
    aufrufe = aufrufe_aus_text(
        (REPO_WURZEL / BEFEHLSSAMMLUNG).read_text(encoding="utf-8"), BEFEHLSSAMMLUNG
    )

    titel_aufrufe = [a for a in aufrufe if a.verb == "edit" and a.schreibt_titel]

    assert titel_aufrufe, (
        f"{BEFEHLSSAMMLUNG} fuehrt keinen `gh issue edit --title`-Befehl mehr. Die Sammlung ist "
        "die einzige Stelle, an der die verbindliche Form steht."
    )
    assert form_verstoesse(titel_aufrufe) == []


def test_refinement_schreibt_den_titel_zwischen_body_und_ready() -> None:
    befunde = reihenfolge_verstoesse(
        (REPO_WURZEL / REFINEMENT).read_text(encoding="utf-8"), REFINEMENT
    )

    assert befunde == [], "; ".join(befunde)


@pytest.mark.parametrize(
    "titel_form",
    [
        '--title "Ein fester Titel"',
        "--title 'Ein fester Titel'",
        '--title "$TITEL"',
        '--title "${TITEL}"',
        "--title $(cat <titel-datei>)",
        "--title '$(cat <titel-datei>)'",
    ],
)
def test_eine_andere_titel_form_wird_gemeldet(titel_form: str) -> None:
    text = f"gh issue edit 42 --repo {REPO} {titel_form}\n"

    befunde = form_verstoesse(aufrufe_aus_text(text, "skill.md"))

    assert len(befunde) == 1
    assert "--title" in befunde[0]


def test_die_vorgeschriebene_titel_form_gilt_nicht_als_verstoss() -> None:
    text = f'gh issue edit 42 --repo {REPO} --title "$(cat <titel-datei>)"\n'

    assert form_verstoesse(aufrufe_aus_text(text, "skill.md")) == []


def test_ein_inline_body_wird_gemeldet() -> None:
    text = f'gh issue comment 42 --repo {REPO} --body "Freitext in der Kommandozeile"\n'

    befunde = form_verstoesse(aufrufe_aus_text(text, "skill.md"))

    assert len(befunde) == 1
    assert "--body-file" in befunde[0]


def test_body_file_gilt_nicht_als_inline_body() -> None:
    """`--body\\b` traefe auch `--body-file` - der korrekte Bestand waere rot."""
    text = f"gh issue edit 42 --repo {REPO} --body-file <pfad>\n"

    assert form_verstoesse(aufrufe_aus_text(text, "skill.md")) == []


def test_ein_fremdes_repo_wird_gemeldet() -> None:
    text = "gh issue edit 42 --repo Fremd/photosort --body-file <pfad>\n"

    befunde = form_verstoesse(aufrufe_aus_text(text, "skill.md"))

    assert len(befunde) == 1
    assert "--repo" in befunde[0]


def test_ein_schreibender_aufruf_ohne_repo_wird_gemeldet() -> None:
    text = 'gh issue close 42 --reason "not planned"\n'

    befunde = form_verstoesse(aufrufe_aus_text(text, "skill.md"))

    assert len(befunde) == 1
    assert "None" in befunde[0]


def test_ein_lesender_aufruf_darf_ohne_repo_stehen() -> None:
    text = "gh issue view 42 --json body,title,labels,state\n"

    assert form_verstoesse(aufrufe_aus_text(text, "skill.md")) == []


def test_die_json_feldliste_gilt_weder_als_titel_noch_als_body() -> None:
    """Gegenrichtung zur Regex-Falle: `--json body,title,...` traegt keine der beiden Optionen."""
    aufrufe = aufrufe_aus_text("gh issue view 42 --json body,title,labels,state\n", "skill.md")

    assert [(a.schreibt_titel, a.schreibt_body) for a in aufrufe] == [(False, False)]


def test_ein_unbekanntes_verb_wird_gemeldet() -> None:
    text = f"gh issue transfer 42 --repo {REPO}\n"

    befunde = form_verstoesse(aufrufe_aus_text(text, "skill.md"))

    assert len(befunde) == 1
    assert "unbekanntes Verb" in befunde[0]


def test_eine_erwaehnung_im_fliesstext_gilt_nicht_als_aufruf() -> None:
    """Prosa nennt das Kommando in Backticks, ruft es aber nicht - sonst Falschbefunde."""
    text = "`gh issue create` wird dafuer **nicht** wiederholt - das legte ein zweites an.\n"

    assert aufrufe_aus_text(text, "skill.md") == []


def test_die_fundstelle_nennt_datei_und_zeile() -> None:
    text = "Text\n\ngh issue edit 42 --repo Fremd/photosort --body-file <pfad>\n"

    befunde = form_verstoesse(aufrufe_aus_text(text, "skills/x/SKILL.md"))

    assert befunde[0].startswith("skills/x/SKILL.md:3:")


@pytest.mark.parametrize(
    "zeile",
    [
        f"gh issue edit 42 --repo {REPO} --body-file <pfad>",
        f"  gh issue edit 42 --repo {REPO} --body-file <pfad>",
        f"$ gh issue edit 42 --repo {REPO} --body-file <pfad>",
        f"`gh issue edit 42 --repo {REPO} --body-file <pfad>`",
        f"- gh issue edit 42 --repo {REPO} --body-file <pfad>",
        f"- `body-edit`: `gh issue edit 42 --repo {REPO} --body-file <pfad>`",
    ],
)
def test_ein_aufruf_am_zeilenanfang_wird_in_jeder_schreibform_gelesen(zeile: str) -> None:
    aufrufe = aufrufe_aus_text(zeile + "\n", "skill.md")

    assert len(aufrufe) == 1
    assert form_verstoesse(aufrufe) == []


def test_ein_suchraum_ohne_issue_aufruf_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"0 Treffer"):
        aufrufe_im_abbild({"skills/x/SKILL.md": "Nur Prosa, kein Issue-Aufruf.\n"})


_BODY_STELLE = f"- `{BODY_OPERATION}`"
_TITEL_STELLE = f"- `{TITEL_OPERATION}`"
_READY_STELLE = f"- `{STATUS_OPERATION}` mit Wert {READY}"
_IN_PROGRESS_STELLE = f"- `{STATUS_OPERATION}` mit Wert `In Progress`"


def test_die_erwartete_kette_gilt_nicht_als_verstoss() -> None:
    text = "\n".join([_BODY_STELLE, _TITEL_STELLE, _READY_STELLE]) + "\n"

    assert reihenfolge_verstoesse(text, "refinement.md") == []


def test_prosa_ueber_die_operationen_kehrt_die_reihenfolge_nicht_um() -> None:
    """Im Skill-Text stehen beide IDs auch in Fliesstext, weit vor den Ausfuehrungsstellen."""
    text = (
        f"Scheitert `{TITEL_OPERATION}`, entfaellt `{STATUS_OPERATION}` mit Wert {READY}.\n"
        f"Der Body (`{BODY_OPERATION}`) steht bewusst vorn.\n"
        + "\n".join([_BODY_STELLE, _TITEL_STELLE, _READY_STELLE])
        + "\n"
    )

    assert reihenfolge_verstoesse(text, "refinement.md") == []


def test_eine_titel_stelle_vor_der_body_stelle_wird_gemeldet() -> None:
    text = "\n".join([_TITEL_STELLE, _BODY_STELLE, _READY_STELLE]) + "\n"

    befunde = reihenfolge_verstoesse(text, "refinement.md")

    assert len(befunde) == 1
    assert "nicht hinter" in befunde[0]


def test_eine_titel_stelle_hinter_der_ready_stelle_wird_gemeldet() -> None:
    text = "\n".join([_BODY_STELLE, _READY_STELLE, _TITEL_STELLE]) + "\n"

    befunde = reihenfolge_verstoesse(text, "refinement.md")

    assert len(befunde) == 1
    assert "`Ready`" in befunde[0]


def test_eine_geloeschte_titel_stelle_wird_gemeldet() -> None:
    """Ohne diese Zusicherung waere die Reihenfolge-Aussage leer wahr."""
    text = "\n".join([_BODY_STELLE, _READY_STELLE]) + "\n"

    befunde = reihenfolge_verstoesse(text, "refinement.md")

    assert len(befunde) == 1
    assert TITEL_OPERATION in befunde[0]


def test_eine_geloeschte_body_stelle_wird_gemeldet() -> None:
    text = "\n".join([_TITEL_STELLE, _READY_STELLE]) + "\n"

    befunde = reihenfolge_verstoesse(text, "refinement.md")

    assert len(befunde) == 1
    assert BODY_OPERATION in befunde[0]


def test_ein_anderer_statuswert_gilt_nicht_als_ready_gate() -> None:
    """`In Progress` ist derselbe Operationsname - nur der Wert trennt die beiden Stellen."""
    text = "\n".join([_BODY_STELLE, _IN_PROGRESS_STELLE, _TITEL_STELLE, _READY_STELLE]) + "\n"

    assert reihenfolge_verstoesse(text, "refinement.md") == []


@pytest.mark.parametrize(
    "zeile",
    [
        f"`{BODY_OPERATION}`",
        f"  `{BODY_OPERATION}`",
        f"- `{BODY_OPERATION}`",
        f"* `{BODY_OPERATION}`",
        f"3. `{BODY_OPERATION}`",
    ],
)
def test_eine_ausfuehrungsstelle_wird_in_jeder_schreibform_gelesen(zeile: str) -> None:
    stellen = ausfuehrungsstellen(zeile + "\n", "skill.md")

    assert [stelle.id for stelle in stellen] == [BODY_OPERATION]


def test_eine_erwaehnung_im_fliesstext_ist_keine_ausfuehrungsstelle() -> None:
    text = f"Scheitert `{TITEL_OPERATION}`, gib die Meldung unveraendert weiter.\n"

    assert ausfuehrungsstellen(text, "skill.md") == []
