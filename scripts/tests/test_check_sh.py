r"""Verhaltenstests fuer `scripts/check.sh` und die Verankerung des Befehls in `developer.md`.

Geprueft wird ein Bash-Skript mit echter Verzweigung (ADR 0081, Spec 0398): Es stellt je Baum
Vorbedingungen fest, ruft danach zehn Pruefbefehle auf, zaehlt die abgeschlossenen Laeufe mit und
setzt danach einen von drei Ausgaengen. Das Pruefen selbst ist Fremdverhalten und wird nicht
nachgebildet - geprueft werden die **Vorbedingungen**, die **abgesetzten Aufrufe**, der **Zaehler**
und die **Bilanz**.

**Der tragende Fall ist hier ein anderer als bei `format.sh`: „nichts aufgerufen" ist von „alles
sauber" nicht zu unterscheiden.** Beides endet mit Ausgang 0 und ohne Befund. Die einzige
wirksame Form dagegen ist die positive Zusicherung der **vollstaendigen** Aufrufliste
(`ZEHN_PRUEFUNGEN`) - nie der Exit-Code allein. Daraus folgt eine Falle im geteilten Helfer:
`Spielplatz.aufrufe()` liefert `[]`, wenn die Protokolldatei fehlt; jede „es wurde nichts
geschrieben"-Zusicherung waere dann gruen, weil die Aufzeichnung ausfiel. Wo Aufrufe erwartet
werden, steht deshalb die Liste selbst in der Zusicherung.

**Der stille Fall aus `format.sh` gilt hier unveraendert und wird eigenstaendig geprueft** (K11a):
`check.sh` traegt eine **zweite Kopie** der Pin-Extraktion, und ein gruener Test im Nachbarmodul
sagt ueber eine Kopie nichts.

**Zwei Textebenen, und sie sind nicht dieselbe** (Abschnitt 1):

* `wirksamer_skripttext()` - ganzzeilige Kommentare zu Leerzeilen. Der Kopfkommentar benennt
  genau das, was im Skriptkoerper nicht vorkommen darf, und machte die Pruefung sonst mit der
  Dokumentation rot, die sie erzwingen soll.
* `ausfuehrungstext()` - zusaetzlich einfach gequotete Zeichenketten geleert. Er traegt genau
  zwei Verbote, `npm ci` und `npm install`, und existiert wegen einer echten Kollision zweier
  Zusicherungen: K10 verlangt, dass die Meldung eines uebersprungenen TypeScript-Baums den
  Handgriff **`npm ci` woertlich** nennt; S3 verbietet `npm ci` im Skript. Beides zugleich geht
  nur, wenn das Verbot die **Ausfuehrungsposition** meint und nicht den Meldungstext. Die
  Abgrenzung ist nicht hemdsaermelig: Ohne `eval` - und `eval` ist selbst verboten - fuehrt aus
  einem einfach gequoteten Zeichenkettenliteral kein Weg zu einem ausgefuehrten Befehl. Alle
  uebrigen Verbote (`git `, `npx`, `prettier`, ...) bleiben total am wirksamen Skripttext, so wie
  die Spec sie fasst; keines von ihnen kommt in einer Meldung vor.

**Mutationsprobe ist hier die Evidenz, nicht die Zugabe** (Teststrategie der Spec): Die
statischen Pruefungen starten auf sauberem Bestand gruen, ein roter Erstlauf belegt nichts. Die
gefahrenen Koeder und ihr Ergebnis stehen im Abschlussbericht des Umsetzungslaufs.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable

import pytest
from conftest import (
    GEPINNTE_VERSION,
    PYTHON_BAEUME,
    REPO_WURZEL,
    SKRIPT_CHECK_SH,
    TS_BAEUME,
    Ergebnis,
    Spielplatz,
    laufe,
)

SKRIPT_REPO_RELATIV = SKRIPT_CHECK_SH
SKRIPT_PFAD = REPO_WURZEL / SKRIPT_REPO_RELATIV

# Die zehn Pruefungen, literal und in der Reihenfolge, in der `check.sh` sie absetzt - nie aus
# einer "CI-Reihenfolge" abgeleitet. Die stimmt nur innerhalb eines Baums: Die CI laeuft
# backend -> frontend -> demo-scripts -> e2e, check.sh laeuft backend -> scripts -> frontend ->
# e2e (Python vor TypeScript, wie format.sh). Die Zahl zehn ist tragend (K8).
ZEHN_PRUEFUNGEN: tuple[tuple[str, str, str], ...] = (
    ("backend", "ruff", "format --check ."),
    ("backend", "ruff", "check ."),
    ("backend", "mypy", "src"),
    ("scripts", "ruff", "format --check ."),
    ("scripts", "ruff", "check ."),
    ("frontend", "npm", "run format:check"),
    ("frontend", "npm", "run lint"),
    ("frontend", "npm", "run typecheck"),
    ("e2e", "npm", "run format:check"),
    ("e2e", "npm", "run typecheck"),
)

ATTRAPPEN = ("ruff", "npm", "mypy")

# Selbstschutz gegen einen leeren Suchraum: Ein Skripttext von 0 wirksamen Zeilen liesse jede
# statische Abwesenheitspruefung vakuum-gruen werden.
MINDESTZAHL_WIRKSAMER_ZEILEN = 40


def bezeichnung(pruefung: tuple[str, str, str]) -> str:
    """Wie die Bilanz ein (Baum, Pruefung)-Paar nennt."""
    baum, programm, argumente = pruefung
    return f"{baum}: {programm} {argumente}"


@pytest.fixture
def fabrik(spielplatz_fabrik: Callable[..., Spielplatz]) -> Callable[..., Spielplatz]:
    """Spielplaetze dieses Moduls: `check.sh`, mit `ruff`-, `npm`- und `mypy`-Attrappe."""

    def bauen(**kwargs: object) -> Spielplatz:
        kwargs.setdefault("attrappen", ATTRAPPEN)
        return spielplatz_fabrik(skript=SKRIPT_REPO_RELATIV, **kwargs)

    return bauen


# --- 1. Das Skript selbst ----------------------------------------------------------------------


def skripttext() -> str:
    return SKRIPT_PFAD.read_text(encoding="utf-8")


def wirksamer_skripttext() -> str:
    """Ganzzeilige Kommentare zu Leerzeilen, alles andere unberuehrt."""
    return "\n".join(
        "" if zeile.lstrip().startswith("#") else zeile for zeile in skripttext().splitlines()
    )


def ausfuehrungstext() -> str:
    """Zusaetzlich: der Inhalt einfach gequoteter Zeichenketten je Zeile geleert.

    Begruendung im Modul-Docstring. Die Ersetzung laeuft zeilenweise und nur ueber geschlossene
    Paare - ein ungerades Anfuehrungszeichen bleibt stehen, statt den Rest der Datei zu
    verschlucken.
    """
    return "\n".join(
        re.sub(r"'[^']*'", "''", zeile) for zeile in wirksamer_skripttext().splitlines()
    )


def test_das_skript_existiert_und_ist_ausfuehrbar() -> None:
    assert SKRIPT_PFAD.is_file(), (
        f"{SKRIPT_REPO_RELATIV} fehlt. docs/setup.md und .claude/agents/developer.md nennen den "
        "Pfad woertlich; ohne die Datei ist der Prueflauf je TDD-Einheit eine Sackgasse."
    )
    assert os.access(SKRIPT_PFAD, os.X_OK), (
        f"{SKRIPT_REPO_RELATIV} ist nicht ausfuehrbar (Modus "
        f"{SKRIPT_PFAD.stat().st_mode & 0o777:o}). Das Ausfuehrungsbit ist Teil des Commits."
    )


# --- 2. Der gute Fall --------------------------------------------------------------------------


def test_ein_sauberer_lauf_setzt_genau_die_zehn_pruefbefehle_ab(
    fabrik: Callable[..., Spielplatz],
) -> None:
    """K6: die vollstaendige, geordnete Aufrufliste samt Argumenten woertlich.

    Der Exit-Code allein traegt hier nichts: Ein Skript, das gar nichts aufruft, endet ebenso
    mit 0 und leerer Ausgabe.
    """
    spielplatz = fabrik()
    ergebnis = laufe(spielplatz)

    assert ergebnis.exit_code == 0, ergebnis.meldung
    assert spielplatz.pruefaufrufe() == list(ZEHN_PRUEFUNGEN), (
        "Erwartet werden genau diese zehn Aufrufe, in dieser Reihenfolge, je mit dem Baum als "
        f"Arbeitsverzeichnis. Protokoll: {spielplatz.aufrufe()}"
    )


def test_ein_sauberer_lauf_weist_zehn_abgeschlossene_pruefungen_aus(
    fabrik: Callable[..., Spielplatz],
) -> None:
    """K8/S1: Ausgang 0 wird verdient - die Bilanz nennt den Zaehlerstand."""
    spielplatz = fabrik()
    ergebnis = laufe(spielplatz)

    assert ergebnis.exit_code == 0, ergebnis.meldung
    assert "10 von 10" in ergebnis.meldung, (
        "Die Bilanz muss den Zaehlerstand nennen; ohne ihn ist 'nichts gefunden' von 'nichts "
        f"geprueft' in der Ausgabe nicht zu unterscheiden. Meldung: {ergebnis.meldung!r}"
    )


def test_die_baeume_kommen_aus_dem_ablageort_nicht_aus_dem_cwd(
    fabrik: Callable[..., Spielplatz],
) -> None:
    """K12: aus jedem Arbeitsverzeichnis heraus aufrufbar, immer dieselben vier Baeume."""
    spielplatz = fabrik()
    ergebnis = laufe(spielplatz, cwd=spielplatz.wurzel / "backend")

    assert ergebnis.exit_code == 0, ergebnis.meldung
    assert spielplatz.pruefaufrufe() == list(ZEHN_PRUEFUNGEN), spielplatz.aufrufe()


# --- 3. Phase 1: die ruff-Version je Python-Baum -----------------------------------------------


def ohne(*baeume: str) -> list[tuple[str, str, str]]:
    """Die zehn Pruefungen ohne die der genannten Baeume - die uebrigen laufen vollstaendig."""
    return [pruefung for pruefung in ZEHN_PRUEFUNGEN if pruefung[0] not in baeume]


@pytest.mark.parametrize("betroffener_baum", PYTHON_BAEUME)
def test_eine_abweichende_ruff_version_nimmt_nur_ihren_baum_aus_dem_lauf(
    fabrik: Callable[..., Spielplatz], betroffener_baum: str
) -> None:
    """Der Fall, der im Repositorium real vorlag: .venv aelter als der Pin, PATH aktuell.

    K10: Der betroffene Baum faellt aus dem Lauf, nicht der Lauf. Und die Vorbedingung ist hier
    aus dem Spiegelbild ihres Grundes in `format.sh` noetig - eine abweichende Version erzeugt
    dort einen Diff, den die CI nicht bestaetigt, und hier ein gruenes Ergebnis, das die CI nicht
    bestaetigt.
    """
    spielplatz = fabrik(venv_ruff_ausgabe_je_baum={betroffener_baum: "ruff 0.16.1"})
    ergebnis = laufe(spielplatz)

    assert ergebnis.exit_code == 1, ergebnis.meldung
    assert spielplatz.pruefaufrufe() == ohne(betroffener_baum), spielplatz.aufrufe()
    assert "0.16.1" in ergebnis.meldung and GEPINNTE_VERSION in ergebnis.meldung, (
        "Die Meldung muss beide Versionen nennen - gefundene und erwartete. Meldung: "
        f"{ergebnis.meldung!r}"
    )
    assert "install" in ergebnis.meldung.lower(), (
        f"Die Meldung muss den Handgriff nennen. Meldung: {ergebnis.meldung!r}"
    )
    assert betroffener_baum in ergebnis.meldung, ergebnis.meldung


def test_phase_2_ruft_dasselbe_binary_das_phase_1_geprueft_hat(
    fabrik: Callable[..., Spielplatz],
) -> None:
    """K11b: geprueft und aufgerufen duerfen nicht auseinanderfallen.

    Die `.venv` des Baums traegt die passende Version, der PATH ebenso. Wird die Version aus
    `.venv/bin/ruff` gelesen und danach das `ruff` vom PATH aufgerufen, ist die Pruefung aus
    Phase 1 bedeutungslos - und still.
    """
    spielplatz = fabrik(venv_ruff_ausgabe_je_baum={"scripts": f"ruff {GEPINNTE_VERSION}"})
    ergebnis = laufe(spielplatz)

    erwartet = str(spielplatz.wurzel / "scripts" / ".venv" / "bin" / "ruff")
    assert ergebnis.exit_code == 0, ergebnis.meldung
    assert spielplatz.herkunft("scripts", "ruff") == [erwartet, erwartet], (
        "Phase 2 muss dasselbe Binary aufrufen, dessen Version Phase 1 gelesen hat. Protokoll: "
        f"{spielplatz.rohe_aufrufe()}"
    )


@pytest.mark.parametrize(
    ("pin_zeile", "warum"),
    [
        (None, "kein ruff-Eintrag in der pyproject.toml"),
        ('"ruff>=0.7",', "offene untere Schranke statt exakter Angabe"),
        ('"ruff",', "nackter Eintrag ohne jeden Operator"),
        ('"ruff==0.16.*",', "Wildcard statt exakter Angabe"),
    ],
)
def test_ein_unlesbarer_pin_nimmt_seinen_baum_aus_dem_lauf(
    fabrik: Callable[..., Spielplatz], pin_zeile: str | None, warum: str
) -> None:
    spielplatz = fabrik(pin_je_baum={"backend": pin_zeile})
    ergebnis = laufe(spielplatz)

    assert ergebnis.exit_code == 1, (
        f"{warum}: Ohne verwertbaren Pin ist der Versionsvergleich bedeutungslos; der Baum gehoert "
        f"aus dem Lauf genommen, nicht mit irgendeiner Version geprueft. Meldung: "
        f"{ergebnis.meldung!r}"
    )
    assert spielplatz.pruefaufrufe() == ohne("backend"), spielplatz.aufrufe()
    assert "backend/pyproject.toml" in ergebnis.meldung, ergebnis.meldung
    assert '"ruff==' in ergebnis.meldung, (
        "Die Meldung muss die erwartete Form nennen und damit belegen, dass der Abbruch am "
        "unlesbaren Pin haengt - nicht zufaellig an einem Versionsunterschied, der nur deshalb "
        f"auffiel, weil die andere Seite gerade nicht leer war. Meldung: {ergebnis.meldung!r}"
    )


def test_leerer_pin_und_leere_versionsausgabe_bestehen_nicht_gegeneinander(
    fabrik: Callable[..., Spielplatz],
) -> None:
    """K11a: der stille Fall in Reinform, fuer `check.sh` eigenstaendig geprueft.

    `check.sh` traegt eine **zweite Kopie** der Extraktionslogik; der gleichnamige Test in
    `test_format_sh.py` sagt ueber sie nichts. Und die Nachbarfaelle stellen ihn nicht: Ist nur
    eine Seite leer, faellt auch ein naiver Entwurf am Unterschied gegen die nicht-leere
    Gegenseite auf. Erst wenn **beide** Extraktionen nichts liefern, besteht `"" == ""` - und
    beide Python-Baeume gingen als "geprueft und sauber" durch, obwohl die aufgerufene Version
    unbekannt ist.
    """
    spielplatz = fabrik(pin_je_baum={"backend": None, "scripts": None}, ruff_ausgabe="")
    ergebnis = laufe(spielplatz)

    assert ergebnis.exit_code == 1, (
        "Pin und gemessene Version sind beide leer. Ein roher Vergleich besteht - und beide "
        f"Python-Baeume liefen mit einer unbekannten Version. Meldung: {ergebnis.meldung!r}"
    )
    assert spielplatz.pruefaufrufe() == ohne("backend", "scripts"), spielplatz.aufrufe()
    assert "5 von 10" in ergebnis.meldung, (
        f"Die Bilanz muss den halben Lauf ausweisen. Meldung: {ergebnis.meldung!r}"
    )


def test_ein_mehrdeutiger_pin_nimmt_seinen_baum_aus_dem_lauf(
    fabrik: Callable[..., Spielplatz],
) -> None:
    spielplatz = fabrik(pin_je_baum={"backend": '"ruff==0.16.4",\n    "ruff==0.17.0",'})
    ergebnis = laufe(spielplatz)

    assert ergebnis.exit_code == 1, (
        "Zwei ruff-Angaben in derselben Datei: Welche gilt, ist nicht entscheidbar. Ein Skript, "
        f"das sich die erste greift, waehlt still. Meldung: {ergebnis.meldung!r}"
    )
    assert spielplatz.pruefaufrufe() == ohne("backend"), spielplatz.aufrufe()


@pytest.mark.parametrize(
    ("ausgabe", "warum"),
    [
        ("", "ruff --version schweigt"),
        ("ruff", "Ausgabe ohne Versionsnummer"),
        ("Fehler: Modul nicht gefunden", "Fremdausgabe statt Versionszeile"),
    ],
)
def test_eine_unlesbare_versionsausgabe_nimmt_ihre_baeume_aus_dem_lauf(
    fabrik: Callable[..., Spielplatz], ausgabe: str, warum: str
) -> None:
    spielplatz = fabrik(ruff_ausgabe=ausgabe)
    ergebnis = laufe(spielplatz)

    assert ergebnis.exit_code == 1, f"{warum}. Meldung: {ergebnis.meldung!r}"
    assert spielplatz.pruefaufrufe() == ohne("backend", "scripts"), spielplatz.aufrufe()


def test_ein_fehlgeschlagenes_ruff_version_nimmt_seine_baeume_aus_dem_lauf(
    fabrik: Callable[..., Spielplatz],
) -> None:
    spielplatz = fabrik(ruff_exit=127)
    ergebnis = laufe(spielplatz)

    assert ergebnis.exit_code == 1, ergebnis.meldung
    assert spielplatz.pruefaufrufe() == ohne("backend", "scripts"), spielplatz.aufrufe()


def test_ein_fehlendes_mypy_macht_backend_ungeprueft_statt_einen_befund(
    fabrik: Callable[..., Spielplatz],
) -> None:
    """K11c: ein fehlendes Werkzeug macht seinen Baum "nicht geprueft", nie "Befund".

    Ohne diese Vorbedingung endete ein fehlendes `mypy` als Aufruf mit Exit != 0 und damit als
    Befund - ununterscheidbar von echten Typfehlern.
    """
    spielplatz = fabrik(attrappen=("ruff", "npm"))
    ergebnis = laufe(spielplatz)

    assert ergebnis.exit_code == 1, (
        "Ein fehlendes Werkzeug ist ein Umgebungsmangel (Ausgang 1), kein Befund (Ausgang 2). "
        f"Meldung: {ergebnis.meldung!r}"
    )
    assert spielplatz.pruefaufrufe() == ohne("backend"), spielplatz.aufrufe()
    assert "mypy" in ergebnis.meldung and "backend" in ergebnis.meldung, ergebnis.meldung


# --- 4. Phase 1: die TypeScript-Baeume, und die Teilpruefung ------------------------------------


@pytest.mark.parametrize("fehlender_baum", TS_BAEUME)
def test_fehlendes_node_modules_nimmt_nur_seinen_baum_aus_dem_lauf(
    fabrik: Callable[..., Spielplatz], fehlender_baum: str
) -> None:
    """K10: uebersprungen, ausdruecklich gemeldet, mit Baum und Handgriff - und `npm ci` woertlich.

    `e2e` ist zugleich der **letzte** Baum: Seine verletzte Vorbedingung darf die neun bzw. acht
    Pruefungen davor nicht kosten.
    """
    spielplatz = fabrik(node_modules_je_baum={fehlender_baum: False})
    ergebnis = laufe(spielplatz)

    assert ergebnis.exit_code == 1, ergebnis.meldung
    assert spielplatz.pruefaufrufe() == ohne(fehlender_baum), spielplatz.aufrufe()
    assert "npm ci" in ergebnis.meldung, (
        "Die Meldung muss den Handgriff woertlich nennen - und zwar 'npm ci', nicht "
        f"'npm install': Das Lockfile ist die Fixierung. Meldung: {ergebnis.meldung!r}"
    )
    assert fehlender_baum in ergebnis.meldung, ergebnis.meldung
    assert "Nicht geprueft" in ergebnis.meldung, (
        "Ein uebersprungener Baum muss ausdruecklich als 'nicht geprueft' dastehen. 'konnte "
        f"nicht pruefen' darf nie wie 'geprueft und sauber' aussehen. Meldung: {ergebnis.meldung!r}"
    )


@pytest.mark.parametrize(
    ("baum", "fehlendes_skript"),
    [
        ("frontend", "format:check"),
        ("frontend", "lint"),
        ("frontend", "typecheck"),
        ("e2e", "format:check"),
        ("e2e", "typecheck"),
    ],
)
def test_ein_fehlendes_npm_skript_macht_seinen_baum_ungeprueft_statt_einen_befund(
    fabrik: Callable[..., Spielplatz], baum: str, fehlendes_skript: str
) -> None:
    """K11c: ein umbenanntes Skript ist ein Umgebungsmangel, kein Befund.

    Der Spielplatz legt den entfernten Namen als Koeder unter `devDependencies` ab. Ein Leser,
    der die ganze `package.json` nach dem Namen durchsucht, statt den `scripts`-Block
    abzugrenzen, haelt das Skript dann faelschlich fuer vorhanden - und der fehlgeschlagene
    `npm run`-Aufruf landete als Befund in der Bilanz.
    """
    vorhanden = tuple(
        name for name in ("format", "format:check", "lint", "typecheck") if name != fehlendes_skript
    )
    spielplatz = fabrik(npm_skripte_je_baum={baum: vorhanden})
    ergebnis = laufe(spielplatz)

    assert ergebnis.exit_code == 1, (
        "Ein fehlendes npm-Skript ist ein Umgebungsmangel (Ausgang 1), kein Befund (Ausgang 2) - "
        f"sonst ist es von einem echten Lint- oder Typfehler nicht zu unterscheiden. Meldung: "
        f"{ergebnis.meldung!r}"
    )
    assert spielplatz.pruefaufrufe() == ohne(baum), spielplatz.aufrufe()
    assert fehlendes_skript in ergebnis.meldung and baum in ergebnis.meldung, ergebnis.meldung


def test_alle_vier_baeume_ungeprueft_melden_null_von_zehn_und_nicht_sauber(
    fabrik: Callable[..., Spielplatz],
) -> None:
    """K10, der Extremfall - und die Lage im verbundenen Arbeitsbaum.

    Hier faellt zusammen, was der Zaehler tragen muss: Es gibt keinen Befund, also endet das
    Skript ohne jede Beanstandung. Ohne Zaehler waere das von einem sauberen Lauf nicht zu
    unterscheiden.
    """
    spielplatz = fabrik(
        ruff_ausgabe="ruff 0.16.1",
        node_modules_je_baum={"frontend": False, "e2e": False},
    )
    ergebnis = laufe(spielplatz)

    assert ergebnis.exit_code == 1, ergebnis.meldung
    assert spielplatz.pruefaufrufe() == [], (
        f"Kein Baum ist pruefbar, trotzdem wurde geprueft. Protokoll: {spielplatz.aufrufe()}"
    )
    assert "0 von 10" in ergebnis.meldung, ergebnis.meldung
    for baum in (*PYTHON_BAEUME, *TS_BAEUME):
        assert baum in ergebnis.meldung, (
            f"Der ungepruefte Baum {baum} fehlt in der Bilanz. Meldung: {ergebnis.meldung!r}"
        )
    assert "sauber" not in ergebnis.meldung, (
        "Ein Lauf ohne eine einzige Pruefung darf das Wort 'sauber' nicht in den Mund nehmen. "
        f"Meldung: {ergebnis.meldung!r}"
    )


# --- 5. Phase 2: Befunde, Zaehler und Bilanz ---------------------------------------------------


def befundzeilen(ergebnis: Ergebnis) -> list[str]:
    """Die Eintraege unter der Ueberschrift `Befunde:` - nichts sonst."""
    zeilen = ergebnis.stdout.splitlines()
    if "Befunde:" not in zeilen:
        return []
    gefunden: list[str] = []
    for zeile in zeilen[zeilen.index("Befunde:") + 1 :]:
        if not zeile.startswith("  - "):
            break
        gefunden.append(zeile[4:])
    return gefunden


@pytest.mark.parametrize(
    "rote_pruefung", ZEHN_PRUEFUNGEN, ids=[bezeichnung(p) for p in ZEHN_PRUEFUNGEN]
)
def test_jede_einzelne_pruefung_fuehrt_bei_fehlschlag_zu_ausgang_2(
    fabrik: Callable[..., Spielplatz], rote_pruefung: tuple[str, str, str]
) -> None:
    """K8, zehn Faelle statt einem.

    "Meldet Befunde" ist schon durch einen einzigen korrekt verdrahteten Aufruf erfuellt - neun
    blinde Stellen blieben unentdeckt. Geprueft wird deshalb je Pruefung einzeln: Ausgang 2, die
    Bilanz nennt genau dieses (Baum, Pruefung)-Paar und kein gruenes, und die uebrigen neun
    Aufrufe erfolgen trotzdem (K9).
    """
    spielplatz = fabrik(befunde=[rote_pruefung])
    ergebnis = laufe(spielplatz)

    assert ergebnis.exit_code == 2, (
        f"{bezeichnung(rote_pruefung)} ist rot, der Lauf endet aber mit {ergebnis.exit_code}. "
        f"Meldung: {ergebnis.meldung!r}"
    )
    assert befundzeilen(ergebnis) == [bezeichnung(rote_pruefung)], (
        f"Die Bilanz muss genau das rote Paar nennen - und kein gruenes. Meldung: "
        f"{ergebnis.meldung!r}"
    )
    assert spielplatz.pruefaufrufe() == list(ZEHN_PRUEFUNGEN), (
        "Ein roter Baum darf den Sammellauf nicht abbrechen; sonst entsteht genau die Schleife "
        f"(beheben, neu laufen, naechster Fund), die entfallen soll. Protokoll: "
        f"{spielplatz.aufrufe()}"
    )
    assert "10 von 10" in ergebnis.meldung, ergebnis.meldung


def test_zwei_rote_pruefungen_in_verschiedenen_baeumen_stehen_beide_in_der_bilanz(
    fabrik: Callable[..., Spielplatz],
) -> None:
    rote = [ZEHN_PRUEFUNGEN[0], ZEHN_PRUEFUNGEN[6]]
    spielplatz = fabrik(befunde=rote)
    ergebnis = laufe(spielplatz)

    assert ergebnis.exit_code == 2, ergebnis.meldung
    assert befundzeilen(ergebnis) == [bezeichnung(rote[0]), bezeichnung(rote[1])], ergebnis.meldung
    assert spielplatz.pruefaufrufe() == list(ZEHN_PRUEFUNGEN), spielplatz.aufrufe()


def test_ein_befund_schlaegt_einen_ungepruefen_baum_im_exit_code(
    fabrik: Callable[..., Spielplatz],
) -> None:
    """K8: Der Gleichstand geht an 2 - und die Bilanz nennt trotzdem beides.

    Exit-Codes ordnen nach erforderlicher Handlung: Ein Befund verlangt eine Aenderung am
    Arbeitsstand, die 1 nur eine an der Umgebung. Umgekehrt ginge Information verloren - wer 1
    bekaeme, installierte node_modules und meldete "war nur die Umgebung", waehrend der Befund
    die ganze Zeit dastand.
    """
    spielplatz = fabrik(befunde=[ZEHN_PRUEFUNGEN[0]], node_modules_je_baum={"e2e": False})
    ergebnis = laufe(spielplatz)

    assert ergebnis.exit_code == 2, ergebnis.meldung
    assert befundzeilen(ergebnis) == [bezeichnung(ZEHN_PRUEFUNGEN[0])], ergebnis.meldung
    assert "e2e" in ergebnis.meldung and "npm ci" in ergebnis.meldung, (
        "Der uebersprungene Baum muss trotz des Befunds in der Bilanz stehen; nur der Exit-Code "
        f"traegt allein das Dringendere. Meldung: {ergebnis.meldung!r}"
    )
    assert "8 von 10" in ergebnis.meldung, ergebnis.meldung


def test_ein_sauberer_lauf_schreibt_keine_einzige_datei(
    fabrik: Callable[..., Spielplatz],
) -> None:
    """K7, die Aufzeichnungsebene: keine Aufrufform schreibt.

    Die Zusicherung haengt nicht am leeren Ergebnis allein - das waere auch bei ausgefallener
    Aufzeichnung leer -, sondern daran, dass daneben die vollstaendige Aufrufliste steht.
    """
    spielplatz = fabrik()
    ergebnis = laufe(spielplatz)

    assert ergebnis.exit_code == 0, ergebnis.meldung
    assert spielplatz.pruefaufrufe() == list(ZEHN_PRUEFUNGEN), spielplatz.aufrufe()
    assert spielplatz.formatierlaeufe() == [], (
        "Ein Aufruf hat 'ruff format' ohne --check oder 'npm run format' ohne :check abgesetzt. "
        "Ein Pruefbefehl, der mitten im TDD-Zyklus Dateien umschreibt, veraendert den Stand, den "
        f"der Aufrufer gerade geprueft hat. Protokoll: {spielplatz.aufrufe()}"
    )


def test_die_typescript_pruefungen_laufen_ausschliesslich_als_npm_run_skript(
    fabrik: Callable[..., Spielplatz],
) -> None:
    """S2: nie als direkter prettier-/tsc-/oxlint-Aufruf.

    `--ignore-path ../.prettierignore` steckt im npm-Skript, und diese Datei ist die einzige
    Ausschlussquelle fuer Prettier. Ein direkter Aufruf aus `e2e/` stiege in `e2e/.auth/` ab;
    bei einem Parse-Fehler auf einer halb geschriebenen `state.json` stuende der dort
    gespeicherte, 30 Tage gueltige und nicht widerrufbare JWT im Code-Frame und damit im
    Protokoll des Laufs.
    """
    spielplatz = fabrik()
    laufe(spielplatz)

    ts_aufrufe = [
        (baum, programm, argumente)
        for baum, programm, argumente in spielplatz.pruefaufrufe()
        if baum in TS_BAEUME
    ]
    assert len(ts_aufrufe) == 5, spielplatz.aufrufe()
    for baum, programm, argumente in ts_aufrufe:
        assert programm == "npm" and argumente.startswith("run "), (
            f"{baum}: {programm} {argumente} - die TypeScript-Pruefungen laufen ausschliesslich "
            "als 'npm run <skript>'."
        )
