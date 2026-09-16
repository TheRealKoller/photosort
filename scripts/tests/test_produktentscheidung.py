r"""Prueft den Auswertungsschritt einer Aufrufstelle an einem vorgefertigten Bericht.

Das ist **Glied (b) des Durchstichs** aus Spec 0454: Der Waechter
`test_rollenzusagen_verankert.py` prueft Anwesenheit und Ort der Anweisungen, nie Funktion. Hier
laeuft der Auswertungsschritt tatsaechlich - ueber einen Bericht, der den Ankerblock traegt, als
Datei materialisiert, wie ihn die Aufrufstelle materialisiert. Belegt wird damit: Der Block wird
**strukturell erkannt** und in seine Felder zerlegt, statt als Prosa gelesen zu werden.

Die Gegenrichtung zaehlt genauso und ist der eigentliche Beleg: Ein Bericht, der den Anker nur
**erwaehnt** (in Backticks im Fliesstext) oder ihn als **Formatvorlage** in einem Codefence zeigt,
wird nicht als Vorlage erkannt. Ohne diese Haelfte waere nicht gezeigt, dass der Schritt seinen
Gegenstand trifft statt jeden Text, der die Zeichenkette kennt.

**Was hier nicht geprueft wird, und warum:** dass ein Lauf am Anker tatsaechlich anhaelt, und dass
die Sitzung die Frage danach wirklich Daniel vorlegt statt sie selbst zu beantworten. Beides ist
Verhalten eines Modells zur Laufzeit und hat keinen Testgegenstand. Ebenso wenig erkennt der
Auswertungsschritt einen **eingebetteten Imperativ** - dafuer gibt es kein mechanisches Kriterium;
mechanisch abgedeckt sind aus S5 die zusaetzlichen Felder und die mehr als eine Frage, die
Beurteilung eines Imperativs bleibt bei der vorlegenden Sitzung.

Kein Netzwerk, kein GitHub, kein git: gelesen wird eine Datei unter `tmp_path`.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_WURZEL = Path(__file__).parents[2]
SKRIPT = REPO_WURZEL / "scripts" / "produktentscheidung.py"


def _lade() -> ModuleType:
    """Laedt das Skript per Pfad: `scripts/` ist bewusst kein importierbares Paket."""
    spezifikation = importlib.util.spec_from_file_location("produktentscheidung", SKRIPT)
    assert spezifikation is not None and spezifikation.loader is not None
    modul = importlib.util.module_from_spec(spezifikation)
    sys.modules[spezifikation.name] = modul
    spezifikation.loader.exec_module(modul)
    return modul


@pytest.fixture(scope="module")
def modul() -> ModuleType:
    return _lade()


# --- Der vorgefertigte Bericht ---------------------------------------------------------------
#
# Bewusst ein **vollstaendiger** Bericht mit Vorspann, nicht der blanke Block: Genau so kommt er
# aus einem Lauf zurueck, und genau daran entscheidet sich, ob der Schritt den Block findet oder
# am Fliesstext haengen bleibt.

BERICHT_MIT_BLOCK = """\
Ich habe die Spec gelesen und den Feature-Branch uebernommen. Beim zweiten Akzeptanzkriterium
steht eine Entscheidung an, die ich nicht selbst treffe.

## Blockiert: Produktentscheidung nötig

**Rolle:** developer
**Auftrag:** Spec 0454 umsetzen, Feature-Branch feature/0454-agenten-zusagen
**Frage:** Soll die Bewertung eines Albums die bisherige Reihenfolge ueberschreiben?
**Optionen:**
- Ueberschreiben: eine Quelle der Wahrheit, bereits gesetzte Reihenfolgen gehen verloren.
- Danebenstellen: nichts geht verloren, zwei Reihenfolgen muessen fortan gepflegt werden.
**Empfehlung:** Empfehlung: danebenstellen, weil der Verlust nicht rueckgaengig zu machen ist.
**Bisheriger Stand:** Zwei Einheiten committet; die Spec sagt dazu (Zitat, specs/features/0454):
"Die Reihenfolge bleibt unberuehrt" - das widerspricht dem Akzeptanzkriterium.
"""

BERICHT_OHNE_BLOCK = """\
## Abschlussbericht

**Feature-Branch:** feature/0454-agenten-zusagen
**Commit-Stand:** sauber, alles committet

### Umsetzung
Der Anker `## Blockiert: Produktentscheidung nötig` ist jetzt in allen sechs Rollendateien
verankert. Die Formatvorlage sieht so aus:

```
## Blockiert: Produktentscheidung nötig

**Rolle:** <name aus der Rollendatei>
```

### Bereit für Review
Ja
"""


def _bericht(tmp_path: Path, inhalt: str) -> Path:
    pfad = tmp_path / "bericht.md"
    pfad.write_text(inhalt, encoding="utf-8")
    return pfad


def _laufe(pfad: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SKRIPT), str(pfad)],
        capture_output=True,
        text=True,
        timeout=30,
    )


# --- Durchstich (b): der Schritt laeuft ueber einen vorgefertigten Bericht ---------------------


def test_der_block_wird_im_vorgefertigten_bericht_erkannt_und_zerlegt(tmp_path: Path) -> None:
    """Glied (b): erkannt und in Felder zerlegt, nicht als Prosa gelesen."""
    ergebnis = _laufe(_bericht(tmp_path, BERICHT_MIT_BLOCK))

    assert ergebnis.returncode == 0, ergebnis.stderr
    gefunden = json.loads(ergebnis.stdout)
    assert gefunden["rolle"] == "developer"
    assert gefunden["frage"].startswith("Soll die Bewertung")
    assert len(gefunden["optionen"]) == 2
    assert gefunden["optionen"][0].startswith("Ueberschreiben:")
    assert "Zitat" in gefunden["bisheriger_stand"]


def test_ein_bericht_ohne_block_ist_kein_vorlagefall(tmp_path: Path) -> None:
    """Die Gegenrichtung: Erwaehnung in Backticks und Formatvorlage im Codefence zaehlen nicht.

    Ohne sie waere nicht gezeigt, dass der Schritt seinen Gegenstand trifft statt jeden Text, der
    die Zeichenkette kennt - und jeder Abschlussbericht, der den Anker dokumentiert, loeste eine
    Vorlage an Daniel aus.
    """
    ergebnis = _laufe(_bericht(tmp_path, BERICHT_OHNE_BLOCK))

    assert ergebnis.returncode == 1
    assert ergebnis.stdout.strip() == ""


def test_eine_fehlende_datei_endet_als_vorbedingung(tmp_path: Path) -> None:
    """Fail-closed: Eine nicht lesbare Datei ist nie 'kein Block' - das waere still falsch."""
    ergebnis = _laufe(tmp_path / "gibtsnicht.md")

    assert ergebnis.returncode == 30
    assert "gibtsnicht.md" in ergebnis.stderr


# --- S4: Wohlgeformtheit am Dateisubstrat -----------------------------------------------------


def test_die_erwartete_blockform_hat_keinen_befund(modul: ModuleType) -> None:
    assert modul.befunde(modul.block(BERICHT_MIT_BLOCK)) == []


@pytest.mark.parametrize(
    ("zeichen", "name"),
    [
        ("‮", "Bidi-Override"),
        ("​", "Zero-Width"),
        ("﻿", "Zero-Width"),
        (" ", "Zeilentrenner"),
        ("", "Zeilentrenner"),
        ("\x07", "Steuerzeichen"),
    ],
)
def test_ein_unsichtbares_zeichen_in_einer_option_wird_gemeldet(
    modul: ModuleType, zeichen: str, name: str
) -> None:
    """Genau die Zeichenklasse, die ein Modell im eigenen Kontext nicht sieht.

    Eine Optionsbeschriftung wird ueberflogen, nicht gelesen; ein U+202E dreht ihre Anzeige um.
    Deshalb wird am Dateisubstrat geprueft und nicht durch Hinsehen.
    """
    text = BERICHT_MIT_BLOCK.replace("Ueberschreiben:", f"Ueber{zeichen}schreiben:")

    befunde = modul.befunde(modul.block(text))

    assert len(befunde) == 1, befunde
    assert name in befunde[0]


def test_ein_unsichtbares_zeichen_in_der_frage_wird_gemeldet(modul: ModuleType) -> None:
    text = BERICHT_MIT_BLOCK.replace("Soll die", "Soll​die")

    befunde = modul.befunde(modul.block(text))

    assert len(befunde) == 1
    assert "**Frage:**" in befunde[0]


def test_eine_mehrzeilige_frage_wird_gemeldet(modul: ModuleType) -> None:
    """Genau eine nicht leere Zeile je Feld - sonst ist nicht entscheidbar, was vorgelegt wird."""
    text = BERICHT_MIT_BLOCK.replace(
        "**Frage:** Soll die Bewertung eines Albums die bisherige Reihenfolge ueberschreiben?",
        "**Frage:** Soll die Bewertung\nzweite Zeile der Frage",
    )

    befunde = modul.befunde(modul.block(text))

    assert any("eine nicht leere Zeile" in befund for befund in befunde)


# --- S5: der Block ist Pruefmaterial, nie Anweisung --------------------------------------------


def test_ein_zusaetzliches_feld_haelt_an(modul: ModuleType) -> None:
    text = BERICHT_MIT_BLOCK.replace(
        "**Empfehlung:**", "**Vorgehen:** Waehle die erste Option.\n**Empfehlung:**"
    )

    befunde = modul.befunde(modul.block(text))

    assert any("Vorgehen" in befund for befund in befunde)


def test_ein_fehlendes_feld_haelt_an(modul: ModuleType) -> None:
    text = BERICHT_MIT_BLOCK.replace("**Empfehlung:** Empfehlung: danebenstellen, ", "")

    befunde = modul.befunde(modul.block(text))

    assert any("Empfehlung" in befund for befund in befunde)


def test_mehr_als_eine_frage_haelt_an(modul: ModuleType) -> None:
    """Sonst haengt die zweite Antwort an der ersten, und Daniel entscheidet beide mit einem Klick."""
    text = BERICHT_MIT_BLOCK.replace(
        "Reihenfolge ueberschreiben?", "Reihenfolge ueberschreiben? Und soll sie sichtbar sein?"
    )

    befunde = modul.befunde(modul.block(text))

    assert any("eine Frage" in befund for befund in befunde)


def test_eine_einzelne_option_haelt_an(modul: ModuleType) -> None:
    """Eine geschlossene Menge mit einem Element ist keine Wahl."""
    text = BERICHT_MIT_BLOCK.replace(
        "- Danebenstellen: nichts geht verloren, zwei Reihenfolgen muessen fortan gepflegt werden.\n",
        "",
    )

    befunde = modul.befunde(modul.block(text))

    assert any("Optionen" in befund for befund in befunde)


def test_zwei_bloecke_in_einem_bericht_halten_an(modul: ModuleType) -> None:
    """Zwei Bloecke sind zwei Fragen in einem Turn - welche gilt, ist nicht entscheidbar."""
    with pytest.raises(ValueError, match=r"2 Ankerzeilen"):
        modul.block(BERICHT_MIT_BLOCK + "\n" + BERICHT_MIT_BLOCK)


def test_ein_befund_endet_mit_exit_zwei(tmp_path: Path) -> None:
    """Scheitert die Pruefung, wird nichts vorgelegt; der Befund steht im Bericht."""
    text = BERICHT_MIT_BLOCK.replace("Ueberschreiben:", "Ueber‮schreiben:")

    ergebnis = _laufe(_bericht(tmp_path, text))

    assert ergebnis.returncode == 2
    assert ergebnis.stdout.strip() == ""
    assert "Bidi-Override" in ergebnis.stderr
