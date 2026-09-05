"""Bindet den in docs/setup.md dokumentierten Setup-Script-Block an die Mindestversion.

Die Zielversion der `gh`-Installation existiert zwangslaeufig an zwei Orten: als autoritative
Prosa-Angabe in docs/setup.md (Label `**Mindestversion:**`) und als `GH_VERSION` im Setup-Script
der Cloud-Umgebung, das ausserhalb des Repositories in einer Weboberflaeche gepflegt wird. Die
dokumentierte Fassung dieses Scripts liegt in derselben Datei - dieser Test haelt beide Angaben
gegeneinander, damit eine Anhebung der Mindestversion ohne Nachziehen des Blocks sofort rot wird
statt still zu veralten. Seit ADR 0057 gibt es keine Konstante im Code mehr, an der die Angabe
haengen koennte; geprueft werden deshalb zwei Angaben innerhalb derselben Datei.

Weil zwei Angaben in derselben Datei einander auch eintraechtig auf einen zu niedrigen Wert
folgen koennten, kommt eine Untergrenze dazu: Erst gh 2.97.0 kennt die namensbasierte
`gh project item-edit --field/--value`-Form, an der der gesamte Board-Ablauf haengt. Ein Anheben
der dokumentierten Version beruehrt die Untergrenze nicht, nur ein Absenken darunter wird rot.

**Was diese Tests ausdruecklich NICHT zusichern:** dass der gepruefte Block je in die
Weboberflaeche der Cloud-Umgebung uebertragen wurde, und erst recht nicht, dass in irgendeiner
Umgebung tatsaechlich ein `gh` liegt. Eine gruene CI ist hier keine Aussage ueber eine
Remote-Session - dieser letzte Uebergang bleibt Handarbeit und ist in docs/setup.md als
Pflichtschritt benannt. Kein echtes `gh`, kein Netzwerk, keine Installation.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

SETUP_DOKU_PFAD = Path(__file__).parents[2] / "docs" / "setup.md"

# Untergrenze der Untergrenze: erst diese gh-Version kennt die namensbasierte
# `gh project item-edit --field/--value`-Form (cli/cli#13807, Release v2.97.0). Bewusst keine
# dritte zu pflegende Kopie der Zielversion - nur ein Absinken DARUNTER wird rot.
NAMENSBASIERTE_ITEM_EDIT_FORM_AB = (2, 97, 0)

# Zeilenanfangs-Anker (re.MULTILINE): nur eine echte Zuweisung zaehlt, keine Erwaehnung von
# GH_VERSION im Fliesstext ringsum (den es zwangslaeufig gibt, weil der Block erklaert wird) und
# keine auskommentierte Zeile. Toleriert werden die gleichwertigen Schreibweisen ("...", '...',
# ohne Anfuehrungszeichen) sowie nachlaufender Leerraum/Kommentar - an einer
# Anfuehrungszeichen-Variante darf keine CI scheitern. Erzwungen bleibt das dreiteilige
# Versionsformat: GH_VERSION="2.72" ergibt null Treffer und damit einen lauten Fehlschlag statt
# eines stillen Ungleich-Vergleichs.
_GH_VERSION_ZUWEISUNG = re.compile(
    r"""^GH_VERSION=(?P<q>["']?)(?P<version>\d+\.\d+\.\d+)(?P=q)""", re.MULTILINE
)


def gh_version_aus_text(text: str) -> str:
    """Liest genau eine GH_VERSION-Zuweisung; null und mehrere Treffer sind Fehlerfaelle."""
    treffer = [t.group("version") for t in _GH_VERSION_ZUWEISUNG.finditer(text)]

    if not treffer:
        raise ValueError(
            "0 Treffer: keine Zeile beginnt mit GH_VERSION=<x.y.z>. Entweder fehlt der "
            "dokumentierte Setup-Script-Block, oder die Variable/das Versionsformat hat sich "
            "geaendert - dann ist dieser Test mitzuziehen, sonst ist die Bindung an die "
            "dokumentierte Mindestversion lautlos weg."
        )
    if len(treffer) > 1:
        raise ValueError(
            f"{len(treffer)} Treffer ({', '.join(treffer)}): GH_VERSION wird mehrfach "
            "zugewiesen. Es darf genau einen Setup-Script-Block geben - bei mehreren ist nicht "
            "mehr entscheidbar, welcher in die Weboberflaeche der Cloud-Umgebung gehoert."
        )
    return treffer[0]


def gh_version_aus_doku(pfad: Path = SETUP_DOKU_PFAD) -> str:
    """Duenner Leser fuer die echte Datei - Umlaute/Gedankenstriche, daher utf-8 ausdruecklich."""
    try:
        return gh_version_aus_text(pfad.read_text(encoding="utf-8"))
    except ValueError as fehler:
        raise ValueError(f"{pfad}: {fehler}") from fehler


# Fuer die Zeichenvorrats-Pruefung wird der Block ausgeschnitten statt die Datei gescannt:
# docs/setup.md ist deutsche Prosa und fuehrt reichlich Nicht-ASCII (Umlaute, Gedankenstriche).
# Geprueft wird ausschliesslich die Kopiervorlage, die von Hand in ein Webformular wandert und
# dort als Root laeuft. Der Filter auf "GH_VERSION=" trennt sie von den uebrigen Codebloecken
# der Datei; eine allgemeine Block-Erkennung entsteht dadurch ausdruecklich nicht.
_BASH_BLOCK = re.compile(r"```bash\n(.*?)```", re.DOTALL)

# Zeilenumbruch und Tabulator sind der einzige erlaubte Steuerzeichen-Vorrat eines Shell-Blocks.
_ERLAUBTER_LEERRAUM = ("\n", "\t")


def setup_script_block_aus_text(text: str) -> str:
    """Schneidet den einen ```bash-Block aus, der GH_VERSION zuweist."""
    treffer = [block for block in _BASH_BLOCK.findall(text) if "GH_VERSION=" in block]

    if not treffer:
        raise ValueError(
            "0 Treffer: kein ```bash-Block enthaelt eine GH_VERSION-Zuweisung. Damit ist der "
            "Zeichenvorrat der Kopiervorlage ungeprueft - entweder fehlt der Block, oder die "
            "Fence-/Sprachauszeichnung hat sich geaendert."
        )
    if len(treffer) > 1:
        raise ValueError(
            f"{len(treffer)} Treffer: mehrere ```bash-Bloecke weisen GH_VERSION zu. Es darf "
            "genau eine Kopiervorlage geben - bei mehreren ist nicht mehr entscheidbar, welche "
            "in die Weboberflaeche der Cloud-Umgebung gehoert."
        )
    return treffer[0]


def setup_script_block_aus_doku(pfad: Path = SETUP_DOKU_PFAD) -> str:
    try:
        return setup_script_block_aus_text(pfad.read_text(encoding="utf-8"))
    except ValueError as fehler:
        raise ValueError(f"{pfad}: {fehler}") from fehler


def nicht_ascii_verstoesse(block: str) -> list[str]:
    """Meldet je Verstoss Position, Zeile, Zeichen und Codepoint.

    Eine rote Zeile ohne Codepoint ist bei unsichtbaren Zeichen wertlos - man sieht im
    Fehlerbericht sonst genau das, was man auch in der Datei nicht sieht.
    """
    verstoesse = []
    for position, zeichen in enumerate(block):
        if zeichen in _ERLAUBTER_LEERRAUM or 0x20 <= ord(zeichen) <= 0x7E:
            continue
        zeile = block.count("\n", 0, position) + 1
        verstoesse.append(f"Position {position} (Zeile {zeile}): {zeichen!r} U+{ord(zeichen):04X}")
    return verstoesse


# Zeilenanfangs-Anker (re.MULTILINE): Die Prosa-Angabe ist ein Vertrag, keine Formulierung -
# ein benanntes Label am Zeilenanfang mit genau einer dreiteiligen Version darin. Der Rest der
# Datei bleibt frei formulierbar; gelesen wird ausschliesslich diese eine Zeile. Damit ergibt
# "**Mindestversion:** gh 2.97" null Treffer und einen lauten Fehlschlag statt eines stillen
# Ungleich-Vergleichs.
_MINDESTVERSION_ZEILE = re.compile(r"^\*\*Mindestversion:\*\*.*$", re.MULTILINE)
_DREITEILIGE_VERSION = re.compile(r"\d+\.\d+\.\d+")


def mindestversion_aus_text(text: str) -> str:
    """Liest genau eine Label-Zeile mit genau einer Version; alles andere ist ein Fehlerfall."""
    zeilen = _MINDESTVERSION_ZEILE.findall(text)

    if not zeilen:
        raise ValueError(
            "0 Treffer: keine Zeile beginnt mit '**Mindestversion:**'. Entweder fehlt die "
            "autoritative Prosa-Angabe, oder ihr Label hat sich geaendert - dann ist dieser "
            "Test mitzuziehen, sonst ist die Bindung an den Setup-Script-Block lautlos weg."
        )
    if len(zeilen) > 1:
        raise ValueError(
            f"{len(zeilen)} Treffer: das Label '**Mindestversion:**' steht mehrfach in der "
            "Datei. Es darf genau eine autoritative Angabe geben - bei mehreren ist nicht mehr "
            "entscheidbar, welche gilt."
        )

    versionen = _DREITEILIGE_VERSION.findall(zeilen[0])

    if not versionen:
        raise ValueError(
            f"0 Treffer: die Zeile {zeilen[0]!r} nennt keine dreiteilige Version <x.y.z>. Eine "
            "zweiteilige Angabe wie '2.97' zaehlt bewusst nicht - sie waere sonst still "
            "ungleich dem dreiteiligen GH_VERSION-Wert."
        )
    if len(versionen) > 1:
        raise ValueError(
            f"{len(versionen)} Treffer ({', '.join(versionen)}): die Label-Zeile nennt mehrere "
            "Versionsangaben. Welche die Mindestversion ist, waere dann Auslegung - die erste "
            "zu nehmen ist geraten, nicht geprueft."
        )
    return versionen[0]


def mindestversion_aus_doku(pfad: Path = SETUP_DOKU_PFAD) -> str:
    try:
        return mindestversion_aus_text(pfad.read_text(encoding="utf-8"))
    except ValueError as fehler:
        raise ValueError(f"{pfad}: {fehler}") from fehler


def versions_tupel(version: str) -> tuple[int, ...]:
    return tuple(int(teil) for teil in version.split("."))


def test_der_dokumentierte_block_entspricht_der_dokumentierten_mindestversion() -> None:
    block_version = gh_version_aus_doku()
    mindestversion = mindestversion_aus_doku()

    assert block_version == mindestversion, (
        f"Der Setup-Script-Block in {SETUP_DOKU_PFAD} installiert gh {block_version}, die "
        f"Prosa-Angabe derselben Datei verlangt aber {mindestversion}. Massgeblich ist die "
        "Prosa-Angabe: den Block nachziehen und den neuen Wortlaut zusaetzlich in das "
        "Setup-Script der Cloud-Umgebung uebertragen."
    )


def test_die_dokumentierte_mindestversion_faellt_nicht_unter_die_untergrenze() -> None:
    """Zwei Angaben in derselben Datei koennen einander auch nach unten folgen."""
    mindestversion = mindestversion_aus_doku()

    assert versions_tupel(mindestversion) >= NAMENSBASIERTE_ITEM_EDIT_FORM_AB, (
        f"{SETUP_DOKU_PFAD} nennt gh {mindestversion} als Mindestversion. Erst "
        f"{'.'.join(str(teil) for teil in NAMENSBASIERTE_ITEM_EDIT_FORM_AB)} kennt die "
        "namensbasierte 'gh project item-edit --field/--value'-Form, an der seit ADR 0057 der "
        "gesamte Board-Ablauf haengt."
    )


def test_eine_fehlende_mindestversion_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"0 Treffer"):
        mindestversion_aus_text("Hier steht Prosa, aber kein Label.\n")


def test_ein_zweites_mindestversions_label_scheitert_laut() -> None:
    text = "**Mindestversion:** gh 2.97.0\ntext\n**Mindestversion:** gh 3.0.0\n"

    with pytest.raises(ValueError, match=r"2 Treffer"):
        mindestversion_aus_text(text)


def test_zwei_versionsangaben_in_der_label_zeile_scheitern_laut() -> None:
    text = "**Mindestversion:** gh 2.97.0, vorher 2.72.0\n"

    with pytest.raises(ValueError, match=r"2 Treffer \(2\.97\.0, 2\.72\.0\)"):
        mindestversion_aus_text(text)


@pytest.mark.parametrize("zeile", ["**Mindestversion:** gh 2.97", "**Mindestversion:** gh"])
def test_ein_unvollstaendiges_versionsformat_in_der_label_zeile_scheitert_laut(
    zeile: str,
) -> None:
    with pytest.raises(ValueError, match=r"0 Treffer"):
        mindestversion_aus_text(f"{zeile}\n")


def test_eine_erwaehnung_der_mindestversion_im_fliesstext_gilt_nicht_als_label() -> None:
    """Ohne Zeilenanfangs-Anker wuerde jede Prosa-Erwaehnung als zweiter Treffer zaehlen."""
    text = (
        "Die **Mindestversion:** 9.9.9 aus dem Fliesstext zaehlt nicht.\n"
        "**Mindestversion:** gh 2.97.0\n"
    )

    assert mindestversion_aus_text(text) == "2.97.0"


def test_die_meldung_der_mindestversion_nennt_die_gelesene_datei(tmp_path: Path) -> None:
    leere_doku = tmp_path / "setup.md"
    leere_doku.write_text("kein Label\n", encoding="utf-8")

    with pytest.raises(ValueError, match=re.escape(str(leere_doku))):
        mindestversion_aus_doku(leere_doku)


def test_ein_verschwundener_block_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"0 Treffer"):
        gh_version_aus_text("Hier steht Prosa, aber kein Setup-Script-Block.\n")


def test_ein_zweiter_block_scheitert_und_die_meldung_nennt_beide_werte() -> None:
    with pytest.raises(ValueError, match=r"2 Treffer \(2\.72\.0, 2\.80\.0\)"):
        gh_version_aus_text('GH_VERSION="2.72.0"\nirgendwas\nGH_VERSION="2.80.0"\n')


def test_die_meldung_nennt_die_gelesene_datei(tmp_path: Path) -> None:
    leere_doku = tmp_path / "setup.md"
    leere_doku.write_text("kein Block\n", encoding="utf-8")

    with pytest.raises(ValueError, match=re.escape(str(leere_doku))):
        gh_version_aus_doku(leere_doku)


def test_eine_erwaehnung_im_fliesstext_gilt_nicht_als_zuweisung() -> None:
    """Ohne Zeilenanfangs-Anker wuerde jede Prosa-Erwaehnung als zweiter Treffer zaehlen."""
    text = 'Der Block setzt GH_VERSION="9.9.9" - passend zu MIN_GH_VERSION.\nGH_VERSION="2.72.0"\n'

    assert gh_version_aus_text(text) == "2.72.0"


def test_eine_auskommentierte_zuweisung_zaehlt_nicht_mit() -> None:
    text = '# GH_VERSION="9.9.9"  (alt)\nGH_VERSION="2.72.0"\n'

    assert gh_version_aus_text(text) == "2.72.0"


@pytest.mark.parametrize(
    "zeile",
    [
        'GH_VERSION="2.72.0"',
        "GH_VERSION='2.72.0'",
        "GH_VERSION=2.72.0",
        'GH_VERSION="2.72.0"   # Zielversion',
    ],
)
def test_gleichwertige_schreibweisen_werden_toleriert(zeile: str) -> None:
    assert gh_version_aus_text(f"set -euo pipefail\n{zeile}\n") == "2.72.0"


@pytest.mark.parametrize("zeile", ['GH_VERSION="2.72"', 'GH_VERSION="latest"', "GH_VERSION="])
def test_ein_unvollstaendiges_versionsformat_ist_ein_lauter_fehlschlag(zeile: str) -> None:
    with pytest.raises(ValueError, match=r"0 Treffer"):
        gh_version_aus_text(f"{zeile}\n")


def test_der_dokumentierte_block_enthaelt_ausschliesslich_druckbares_ascii() -> None:
    """Der Block ist ein Kopiervorlagen-Angriffsziel: gerendert gelesen, als Root ausgefuehrt."""
    verstoesse = nicht_ascii_verstoesse(setup_script_block_aus_doku())

    assert not verstoesse, (
        f"Der Setup-Script-Block in {SETUP_DOKU_PFAD} enthaelt Zeichen ausserhalb des "
        f"druckbaren ASCII: {'; '.join(verstoesse)}. Unsichtbare Steuer-, Bidi- oder "
        "Nullbreiten-Zeichen ueberstehen Kopieren und Einfuegen und koennen im gerenderten "
        "Text verborgene Anweisungen tragen - der Block wird von Hand in ein Webformular "
        "uebertragen und laeuft dort als Root."
    )


def test_der_ausgeschnittene_block_ist_der_setup_script_block() -> None:
    """docs/setup.md fuehrt mehrere ```bash-Bloecke - geprueft wird genau dieser eine.

    Verankert an inhaltlichen Merkmalen der Kopiervorlage statt an ihrer ersten Zeile: Woran
    der Block beginnt, hat sich mit ADR 0054 bereits einmal geaendert (Kommentar statt
    "set -euo pipefail"), und eine Zusicherung, die bei jeder Umformatierung bricht, sagt
    nichts ueber die Identitaet des Blocks aus.
    """
    block = setup_script_block_aus_doku()

    assert "install -m 0755" in block
    assert "/usr/local/bin" in block
    assert "releases/download" in block


@pytest.mark.parametrize(
    ("zeichen", "codepoint"),
    [
        ("\u200b", "U+200B"),  # Zero-Width Space
        ("\u202e", "U+202E"),  # Right-to-Left Override
        ("\u00a0", "U+00A0"),  # Non-Breaking Space
        ("\x1b", "U+001B"),  # ESC, Beginn jeder ANSI-Sequenz
        ("\u2014", "U+2014"),  # Gedankenstrich, harmlos gemeint und trotzdem ein Verstoss
    ],
)
def test_ein_unsichtbares_zeichen_wird_mit_position_und_codepoint_gemeldet(
    zeichen: str, codepoint: str
) -> None:
    verstoesse = nicht_ascii_verstoesse(f'GH_VERSION="2.72.0"{zeichen}\ngh --version\n')

    assert len(verstoesse) == 1
    assert codepoint in verstoesse[0]
    assert "Position 19" in verstoesse[0]
    assert "Zeile 1" in verstoesse[0]


def test_zeilenumbruch_und_tabulator_gelten_nicht_als_verstoss() -> None:
    assert nicht_ascii_verstoesse("set -euo pipefail\n\tgh --version\n") == []


def test_ein_fehlender_bash_block_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"0 Treffer"):
        setup_script_block_aus_text("Nur Prosa, kein Codeblock.\n")


def test_ein_bash_block_ohne_gh_version_zaehlt_nicht_als_kopiervorlage() -> None:
    with pytest.raises(ValueError, match=r"0 Treffer"):
        setup_script_block_aus_text("```bash\ndocker compose up --build\n```\n")


def test_ein_zweiter_kopiervorlagen_block_scheitert_laut() -> None:
    text = '```bash\nGH_VERSION="2.72.0"\n```\ntext\n```bash\nGH_VERSION="2.80.0"\n```\n'

    with pytest.raises(ValueError, match=r"2 Treffer"):
        setup_script_block_aus_text(text)


def test_die_meldung_der_block_extraktion_nennt_die_gelesene_datei(tmp_path: Path) -> None:
    leere_doku = tmp_path / "setup.md"
    leere_doku.write_text("kein Block\n", encoding="utf-8")

    with pytest.raises(ValueError, match=re.escape(str(leere_doku))):
        setup_script_block_aus_doku(leere_doku)


# -- Kapselungsform: der Fehlschlag darf die Session nicht blockieren (ADR 0054 Abschnitt 2)

# Drei konkret benannte, kaputte Schreibweisen - keine Formulierungspolizei, sondern die
# Formen, deren Schaden gemessen ist:
#
# 1./2. "if ! ( set -e; ... )" und "( set -e; ... ) || warnen": bash unterdrueckt das set -e
#       im Rumpf einer Subshell, die Teil einer if-Bedingung bzw. einer ||/&&-Liste ist. Am
#       Block hiesse das, dass nach fehlgeschlagener Pruefsummenpruefung trotzdem entpackt und
#       nach /usr/local/bin installiert wird - die Absicherung waere nicht wirkungslos,
#       sondern schaedlich.
# 3.    "set -e..." auf oberster Ebene (nicht eingerueckt): die Rueckkehr zum Zustand, den
#       ADR 0054 behebt - ein Fehlschlag beendet dann das ganze Script, und die Session
#       startet nicht mehr.
#
# Die korrekte Form (Subshell allein, Auswertung danach ueber $?) wird bewusst NICHT positiv
# erzwungen: Das wuerde bei jeder harmlosen Umformatierung rot.
_SUBSHELL_IN_BEDINGUNG = re.compile(r"^[ \t]*(?:if|while|until)[ \t]+!?[ \t]*\(", re.MULTILINE)
_SUBSHELL_VOR_LISTE = re.compile(r"^[ \t]*\)[ \t]*(?:\|\||&&)", re.MULTILINE)
_ERREXIT_AUF_OBERSTER_EBENE = re.compile(r"^set[ \t]+-[a-z]*e", re.MULTILINE)


def kapselungs_verstoesse(block: str) -> list[str]:
    """Meldet die kaputten Kapselungsformen, die den Abbruch im Innern aushebeln wuerden."""
    befunde = []
    if _SUBSHELL_IN_BEDINGUNG.search(block):
        befunde.append(
            "Subshell als if-/while-/until-Bedingung: bash unterdrueckt darin das 'set -e', "
            "der Installationsteil liefe nach einem Fehlschlag weiter"
        )
    if _SUBSHELL_VOR_LISTE.search(block):
        befunde.append(
            "Subshell links einer '||'-/'&&'-Liste: bash unterdrueckt darin das 'set -e', "
            "der Installationsteil liefe nach einem Fehlschlag weiter"
        )
    if _ERREXIT_AUF_OBERSTER_EBENE.search(block):
        befunde.append(
            "'set -e' auf oberster Ebene: ein Fehlschlag beendet das ganze Setup-Script, "
            "womit die Cloud-Session nicht mehr startet"
        )
    return befunde


def test_der_block_haelt_die_vorgeschriebene_kapselungsform_ein() -> None:
    """Innen hart abbrechen, aussen mit 0 enden - beides zugleich, oder der Block ist kaputt."""
    verstoesse = kapselungs_verstoesse(setup_script_block_aus_doku())

    assert not verstoesse, (
        f"Der Setup-Script-Block in {SETUP_DOKU_PFAD} verletzt die in ADR 0054 Abschnitt 2 "
        f"vorgeschriebene Kapselung: {'; '.join(verstoesse)}. Vorgeschrieben ist die Subshell "
        "als eigenstaendiges Kommando mit anschliessender Auswertung ueber $?."
    )


@pytest.mark.parametrize(
    ("kaputt", "erwartet"),
    [
        ("if ! (\n  set -e\n  install\n); then\n  warnen\nfi\n", "if-"),
        ("  while (\n  set -e\n); do\n  :\ndone\n", "if-"),
        ("(\n  set -e\n  install\n) || warnen\n", "'||'-"),
        ("(\n  set -e\n) && weiter\n", "'||'-"),
        ("set -euo pipefail\ninstall\n", "oberster Ebene"),
        ("set -e\ninstall\n", "oberster Ebene"),
    ],
)
def test_jede_kaputte_kapselungsform_wird_erkannt(kaputt: str, erwartet: str) -> None:
    befunde = kapselungs_verstoesse(kaputt)

    assert befunde, f"nicht erkannt: {kaputt!r}"
    assert any(erwartet in befund for befund in befunde), befunde


def test_die_korrekte_form_gilt_nicht_als_verstoss() -> None:
    """Gegenprobe: eingeruecktes 'set -e' in einer allein stehenden Subshell ist der Zielzustand."""
    korrekt = (
        "set -uo pipefail\n"
        'if [ -n "$have" ] && [ 1 -eq 1 ]; then\n'
        "  echo ok\n"
        "fi\n"
        "(\n"
        "  set -eo pipefail\n"
        "  ( cd \"$tmp\" && awk '$2 == a' checksums.txt | sha256sum -c - )\n"
        ")\n"
        "status=$?\n"
        "command -v gh >/dev/null 2>&1 && gh --version || echo fehlt\n"
    )

    assert kapselungs_verstoesse(korrekt) == []
