"""Haelt die Dateinamen der drei Nummernraeume auf der dokumentierten Form.

`specs/README.md` verlangt fuer `features/`, `decisions/` und `architecture/` den Rumpf
`NNNN-[a-z0-9]+(-[a-z0-9]+)*`. Zwei Zusicherungen:

1. **Jedes `.md` unmittelbar in einem Nummernraum folgt dieser Form.** Grossbuchstaben,
   Leerzeichen, Punkte im Rumpf, Umlaute und andere Nicht-ASCII-Zeichen sind ausgeschlossen.
2. **Jeder Basename dort - auch Nicht-`.md` und Verzeichnisse - ist ASCII ohne Grossbuchstaben und
   ohne Leerraum.** Ohne die zweite entkaeme ein Umlaut-Name der ersten, indem er die Endung
   `.md` weglaesst: `0037-gateführte-notizen` waere dann ein Ordner, der nie geprueft wird.

Grund: Git quotet einen solchen Namen ohne `-z`, gibt ihn also als `"0037-gatef\\303\\274..."` aus,
und er faellt aus jeder Aufzaehlung, die auf dem sichtbaren Text aufbaut. Verweise treffen ihn nur
in genau einer Schreibweise; eine zweite Schreibweise (Umlaut oder `ue`) geht ins Leere. Deshalb
liest die Aufzaehlung `git ls-files -z` - **`-z` ist Pflicht**, nicht Bequemlichkeit.

**Wirksamkeitsbeleg, erster Lauf am 2026-11-16 (vor der Umbenennung), `cd scripts && pytest -q
tests/test_dateinamen_ohne_sonderzeichen.py`:**

$ cd scripts && pytest -q tests/test_dateinamen_ohne_sonderzeichen.py
[...]
E   AssertionError: specs/features/0037-gateführte-bewertungs-pipeline-mit-backfill.md: Position
E   11: 'ü' (U+00FC) - kein ASCII-Zeichen. [...]
FAILED tests/test_dateinamen_ohne_sonderzeichen.py::
    test_kein_basename_traegt_mehr_als_ascii_kleinbuchstaben_ohne_leerraum

Der Befund nennt Pfad, 1-basierte Zeichenposition, Zeichen, `U+XXXX` und die zulaessige Form,
stabil sortiert - ein Befund ohne diese vier Angaben laesst offen, ob der Name falsch oder die
Pruefung kaputt ist. Der synthetische `-z`-Nachweis unten belegt zusaetzlich, dass ein Umlaut-Pfad
unveraendert ankommt und nicht als Quotierung.

**Selbstschutz.** Der Erfolgsfall ist "nichts gefunden"; eine kaputte Aufzaehlung liefert dasselbe.
Dagegen stehen ein lauter Fehler bei leerem Suchraum (gesamt und je Verzeichnis), eine Untergrenze
je Verzeichnis und eine namentlich genannte Ankerdatei je Verzeichnis.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Iterable, Mapping
from pathlib import Path

import pytest

REPO_WURZEL = Path(__file__).parents[2]

NUMMERNSRAEUME: tuple[str, ...] = (
    "specs/architecture",
    "specs/decisions",
    "specs/features",
)

# Die dokumentierte Form aus specs/README.md, Abschnitt "Namenskonvention".
ERLAUBTE_DOKUMENTFORM = re.compile(r"^\d{4}-[a-z0-9]+(-[a-z0-9]+)*\.md$")
ERLAUBTE_FORM_TEXT = "NNNN-[a-z0-9]+(-[a-z0-9]+)*.md"

# Selbstschutz, bewusst weit unter dem Ist-Stand: Diese Grenzen fangen den Totalausfall der
# Aufzaehlung, nicht jede geloeschte Datei.
MINDESTZAHL_JE_VERZEICHNIS: Mapping[str, int] = {
    "specs/architecture": 2,
    "specs/decisions": 60,
    "specs/features": 80,
}

# Selbstschutz, zweite Form: Als Anker taugt kein Dokument, das selbst zur Umbenennung ansteht.
ANKERDATEI_JE_VERZEICHNIS: Mapping[str, str] = {
    "specs/architecture": "0002-testkonzept.md",
    "specs/decisions": "0001-tech-stack.md",
    "specs/features": "0001-opencloud-project-connection.md",
}


def verwaltete_pfade(wurzel: Path = REPO_WURZEL) -> list[str]:
    """Duenner Leser: von Git verwaltete **und** neu angelegte, nicht ignorierte Pfade.

    `--others` gehoert dazu, weil ein Verstoss in dem Moment entsteht, in dem die Datei angelegt
    wird - vor dem `git add`. Im CI-Checkout liefern beide Formen dasselbe.
    """
    ergebnis = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=wurzel,
        capture_output=True,
        check=True,
    )
    return [pfad.decode("utf-8") for pfad in ergebnis.stdout.split(b"\0") if pfad]


def basenamen_je_verzeichnis(
    pfade: Iterable[str],
) -> dict[str, dict[str, bool]]:
    """Reine Funktion: je Nummernraum `{basename: ist_datei}` der unmittelbar darin liegenden
    Eintraege. Verzeichnisse kommen ueber die tieferen Pfade mit herein (`ist_datei = False`)."""
    gefunden: dict[str, dict[str, bool]] = {raum: {} for raum in NUMMERNSRAEUME}
    for pfad in pfade:
        for raum in NUMMERNSRAEUME:
            prefix = raum + "/"
            if not pfad.startswith(prefix):
                continue
            rest = pfad[len(prefix) :]
            if not rest:
                continue
            kopf, trenner, _rest = rest.partition("/")
            gefunden[raum].setdefault(kopf, not trenner)
    return gefunden


def _form_hinweis(name: str) -> str:
    if name.endswith(".md"):
        return (
            f"Zulaessig ist ausschliesslich die Form {ERLAUBTE_FORM_TEXT} - vierstellige Nummer, "
            "Trennstrich, Rumpf aus Kleinbuchstaben und Ziffern mit einzelnen Trennstrichen."
        )
    return (
        "Zulaessig sind ASCII-Zeichen ohne Grossbuchstaben und ohne Leerraum; Dokumente tragen "
        f"zusaetzlich die Form {ERLAUBTE_FORM_TEXT}."
    )


def form_befunde(basenamen: Mapping[str, Mapping[str, bool]]) -> list[str]:
    """Reine Funktion: jedes `.md` unmittelbar in einem Nummernraum gegen die dokumentierte Form."""
    befunde: list[str] = []
    for raum in sorted(basenamen):
        for name in sorted(basenamen[raum]):
            if not basenamen[raum][name] or not name.endswith(".md"):
                continue
            if ERLAUBTE_DOKUMENTFORM.match(name):
                continue
            befunde.append(
                f"{raum}/{name}: Der Dateiname folgt nicht der Form. {_form_hinweis(name)}"
            )
    return befunde


def zeichen_befunde(basenamen: Mapping[str, Mapping[str, bool]]) -> list[str]:
    """Reine Funktion: jeder Basename auf ASCII, Kleinbuchstaben und fehlenden Leerraum.

    Geprueft wird **jedes** Zeichen, nicht nur das erste abweichende, damit ein Name mit zwei
    Verstoessen beide nennt. Die Reihenfolge ist stabil: Verzeichnis, Name, Position.
    """
    befunde: list[str] = []
    for raum in sorted(basenamen):
        for name in sorted(basenamen[raum]):
            for position, zeichen in enumerate(name, start=1):
                codepoint = ord(zeichen)
                if codepoint > 0x7F:
                    grund = "kein ASCII-Zeichen"
                elif zeichen.isupper():
                    grund = "Grossbuchstabe"
                elif zeichen.isspace():
                    grund = "Leerraum"
                else:
                    continue
                befunde.append(
                    f"{raum}/{name}: Position {position}: {zeichen!r} (U+{codepoint:04X}) - "
                    f"{grund}. {_form_hinweis(name)}"
                )
    return befunde


def suchraum_pruefen(basenamen: Mapping[str, Mapping[str, bool]]) -> None:
    """Ein leerer Suchraum ist ein lauter Fehlerfall, nie ein Nullbefund."""
    if not any(basenamen.get(raum) for raum in NUMMERNSRAEUME):
        raise ValueError(
            "0 Eintraege im Suchraum: Damit sind die Dateinamen ungeprueft. Entweder lief die "
            "Aufzaehlung im falschen Arbeitsverzeichnis, oder sie ist kaputt - ein leerer "
            "Suchraum darf nie als 'nichts gefunden' durchgehen."
        )
    leer = [raum for raum in NUMMERNSRAEUME if not basenamen.get(raum)]
    if leer:
        raise ValueError(
            f"Kein Eintrag in {', '.join(leer)}: Dieses Verzeichnis ist aus der Aufzaehlung "
            "gefallen und seine Namen sind ungeprueft."
        )
    for raum, mindestzahl in MINDESTZAHL_JE_VERZEICHNIS.items():
        if len(basenamen[raum]) < mindestzahl:
            raise ValueError(
                f"Nur {len(basenamen[raum])} Eintraege in {raum} (erwartet mindestens "
                f"{mindestzahl}). Die Aufzaehlung ist kaputt; ein Nullbefund waere bedeutungslos."
            )
    for raum, anker in ANKERDATEI_JE_VERZEICHNIS.items():
        if anker not in basenamen[raum]:
            raise ValueError(
                f"{raum}/{anker} steht nicht im gelesenen Bestand. Entweder ist das Verzeichnis "
                "aus der Aufzaehlung gefallen, oder der Anker wurde umbenannt - dann ist dieser "
                "Test mitzuziehen."
            )


def bestand(wurzel: Path = REPO_WURZEL) -> dict[str, dict[str, bool]]:
    basenamen = basenamen_je_verzeichnis(verwaltete_pfade(wurzel))
    suchraum_pruefen(basenamen)
    return basenamen


# --- Selbstschutz -------------------------------------------------------------------------


@pytest.mark.parametrize("raum", NUMMERNSRAEUME)
def test_jedes_verzeichnis_hat_eine_plausible_groesse(raum: str) -> None:
    assert len(bestand()[raum]) >= MINDESTZAHL_JE_VERZEICHNIS[raum]


@pytest.mark.parametrize("raum", NUMMERNSRAEUME)
def test_jedes_verzeichnis_enthaelt_seine_ankerdatei(raum: str) -> None:
    assert ANKERDATEI_JE_VERZEICHNIS[raum] in bestand()[raum]


def test_ein_leerer_suchraum_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"0 Eintraege"):
        suchraum_pruefen(basenamen_je_verzeichnis([]))


def test_ein_einzelnes_leeres_verzeichnis_scheitert_laut_statt_still() -> None:
    basenamen = basenamen_je_verzeichnis(
        ["specs/architecture/0002-a.md", "specs/decisions/0001-b.md"]
    )

    with pytest.raises(ValueError, match=r"Kein Eintrag in specs/features"):
        suchraum_pruefen(basenamen)


# --- Die eigentlichen Zusicherungen -------------------------------------------------------


def test_jedes_dokument_folgt_der_dokumentierten_form() -> None:
    befunde = form_befunde(bestand())

    assert not befunde, (
        "Dateiname in einem Nummernraum folgt nicht der dokumentierten Form:\n  "
        + "\n  ".join(befunde)
        + "\nDie Form steht in specs/README.md, Abschnitt 'Namenskonvention'. Die Datei wird "
        "umbenannt (`git mv`), nicht ausgenommen - ein Umlaut-Name ist auf Systemen mit anderer "
        "Zeichenkodierung nicht adressierbar."
    )


def test_kein_basename_traegt_mehr_als_ascii_kleinbuchstaben_ohne_leerraum() -> None:
    befunde = zeichen_befunde(bestand())

    assert not befunde, (
        "Datei- oder Verzeichnisname mit unzulaessigem Zeichen in einem Nummernraum:\n  "
        + "\n  ".join(befunde)
    )


# --- Gegenproben an synthetischem Material ------------------------------------------------


def _befunde(name: str) -> list[str]:
    basenamen = {"specs/features": {name: True}}
    return form_befunde(basenamen) + zeichen_befunde(basenamen)


@pytest.mark.parametrize(
    ("name", "erwartet"),
    [
        ("0037-gateführte-bewertungs-pipeline-mit-backfill.md", ("Position 11: 'ü' (U+00FC)",)),
        ("0069-groesse-ß.md", ("Position 14: 'ß' (U+00DF)",)),
        ("0069-Öffnung.md", ("Position 6: 'Ö' (U+00D6)",)),
        ("0069-café.md", ("Position 9: 'é' (U+00E9)",)),
        ("0069-аnsatz.md", ("Position 6: 'а' (U+0430)",)),
        ("0069-Gross.md", ("Position 6: 'G' (U+0047)",)),
        ("0069-mit leerzeichen.md", ("Position 9: ' ' (U+0020)",)),
        # NFD-zerlegt: das kombinierende Akut ist ein eigenes, Nicht-ASCII-Zeichen.
        ("0069-cafe\u0301.md", ("Position 10", "(U+0301)")),
        ("0069-mit_unterstrich.md", ("folgt nicht der Form",)),
        ("0069-punkt.im-rumpf.md", ("folgt nicht der Form",)),
        ("0069-doppel--bindestrich.md", ("folgt nicht der Form",)),
        ("00691-zu-lang.md", ("folgt nicht der Form",)),
        # `.MD` ist kein `.md`; getragen wird der Fall von der zweiten Zusicherung.
        ("0069-fehler.MD", ("Position 13: 'M' (U+004D)",)),
    ],
)
def test_jede_abweichende_schreibweise_wird_erkannt(name: str, erwartet: tuple[str, ...]) -> None:
    befunde = _befunde(name)

    fehlend = [teil for teil in erwartet if not any(teil in befund for befund in befunde)]
    assert not fehlend, (
        f"Die Schreibweise {name!r} muesste Befunde mit {fehlend!r} erzeugen; gefunden: "
        f"{befunde}. Faellt ein Fall aus der Tabelle, ist die Pruefung stiller geworden."
    )


def test_ein_sauberer_name_ist_kein_befund() -> None:
    assert _befunde("0037-gatefuehrte-bewertungs-pipeline-mit-backfill.md") == []


def test_ein_umlautpfad_kommt_mit_minus_z_unveraendert_an_und_erzeugt_einen_befund(
    tmp_path: Path,
) -> None:
    """Ohne `-z` gelesen kaeme der Pfad als `"0037-gatef\\303\\274..."` an - und passte auf keinen
    Vergleich. Der Wegwerf-Bestand belegt beides: unveraenderte Ankunft und den Befund."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    ordner = tmp_path / "specs" / "features"
    ordner.mkdir(parents=True)
    umlaut_name = "0037-gateführte-bewertungs-pipeline-mit-backfill.md"
    (ordner / umlaut_name).write_text("", encoding="utf-8")
    subprocess.run(["git", "add", "specs"], cwd=tmp_path, check=True)

    pfade = verwaltete_pfade(tmp_path)

    assert f"specs/features/{umlaut_name}" in pfade
    befunde = zeichen_befunde(basenamen_je_verzeichnis(pfade))
    assert any("Position 11: 'ü' (U+00FC)" in befund for befund in befunde), befunde
