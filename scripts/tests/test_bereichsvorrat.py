"""Haelt fest, dass der Bereichsvorrat eines Issues an genau einer Stelle steht.

Seit ADR 0085 ist der Bereich eines Issues ein GitHub-Label mit dem Praefix `bereich:`. Der
Vorrat ist eine **geschlossene** Menge und steht als Literal in einer Zeile fester Form im
Operationskatalog (`.claude/skills/github-access/SKILL.md`); Ablauf-Skills nennen ausschliesslich
die Operations-ID, nie einen der Werte. Vier Zusicherungen tragen das:

* **(a)** Genau **eine** Zeile fester Form traegt den Vorrat, verglichen gegen eine eingefrorene
  Menge. "Genau eine" statt "mindestens eine": Eine zweite Vorrat-Zeile ist ein Widerspruch und
  muss laut auffallen, statt sich mit der ersten gegenseitig zu verdecken.
* **(b)** Kein `bereich:`-Wert ausserhalb des Katalogs, unverankert gesucht.
* **(c)** `refinement` fuehrt eine Ausfuehrungsstelle von `issue-bereich-setzen` an der richtigen
  Kettenposition. Diese Zusicherung liegt **nicht hier**, sondern in
  `test_issue_befehle_in_skills.py` - dort steht die Kette Body -> Titel -> Bereich -> Board
  vollstaendig, und eine zweite Fassung daneben liefe mit der naechsten Aenderung auseinander.
* **(d)** `capture` nennt weder die Operation noch einen Wert. Die Leere beim Erfassen ist das
  Fehlen eines Schritts, geprueft als Abwesenheit.

**Der Suchraum von (b) ist eine Negativliste: alles, was `git ls-files` liefert, ausser `specs/**`
und dieser Datei selbst.** Eine Positivliste waere hier die falsche Bauart, und das ist im Review
am Bestand belegt worden, nicht befuerchtet: Die erste Fassung zaehlte `.claude/**`, `CLAUDE.md`
und `docs/**` auf und uebersah `.github/ISSUE_TEMPLATE/*.yml` - Dateien, die **nachweislich Label
vergeben** (`labels: ["bug"]`, `labels: ["feature", "needs-spec"]`). Ein Bereichswert in einer
solchen `labels:`-Zeile ist genau der zweite Wahrheitsort, den (b) verhindern soll; die Probe
blieb gruen. **Regel:** Eine Positivliste waechst nicht mit - jeder kuenftige Ort faellt durch,
und der Waechter bleibt dabei gruen. Ein Ausschluss wird einzeln begruendet:

* **`specs/**`** sind eingefrorene Momentaufnahmen; Spec 0259 und ADR 0085 nennen den Vorrat
  selbst. Ein Textscan koennte lebende und historische Nennung dort nicht trennen und wuerde zum
  Umschreiben von Geschichte zwingen - dieselbe Begruendung wie beim Abschnittszitat-Scan in
  `test_github_zugriff_an_einer_stelle.py`.
* **Diese Datei selbst** fuehrt die Werte als Erwartungsmenge und in jeder Gegenprobe. Der
  Ausschluss ist an den eigenen Pfad gebunden und wird gegen ihn geprueft, damit er nicht zu
  einem Pfad verrottet, den es nicht mehr gibt.

Nicht als UTF-8 lesbare Dateien (Bilder, Modelldateien - gemessen 2026-09-11: 19 von 688) werden
uebersprungen. Das ist eine bewusste Grenze, kein Versehen: Ein Label-Vorrat wird nicht in einer
`.tflite` dokumentiert, und ein Leser, der an der ersten Bilddatei abbricht, prueft gar nichts.

**Warum die Praefixbindung die Pruefbarkeit ueberhaupt traegt.** Ein Scan nach den blanken Werten
ist unmoeglich: `ai-workflow` ist der Dateiname `docs/ai-workflow.md`, und `design`, `backend`,
`frontend`, `pipeline`, `infra` sind Alltagswoerter dieses Projekts. Ein Wortverbot waere am
eigenen Bestand sofort rot und wuerde so lange abgeschwaecht, bis es nichts mehr aussagt.
`bereich:` ist deshalb die Bedingung dafuer, dass (b) existieren kann - und die Praefixbindung
damit Teil des Akzeptanzkriteriums, nicht Umsetzungsdetail.

**(b) und (d) starten gruen**, weil ihr Erfolgsfall eine Abwesenheit ist; der triviale Lauf zu
Beginn belegt fuer sie nichts. Tragender Nachweis ist allein die Mutationsprobe (Spec 0259,
Familien F2 und F4: `bereich:frontend` und `bereich:doku` je einmal in
`.claude/skills/spec-writer/SKILL.md` **und** in `docs/ai-workflow.md`; Operation und Wert je
einmal in `capture` - alle rot gesehen, alle zurueckgenommen). Dazu kommt die Untergrenze fuer
das **Gesehene**: Das `bereich:`-Muster muss im Katalog mindestens sechs Vorkommen finden, sonst
ist ein kaputtes Muster von einem sauberen Bestand nicht unterscheidbar.

Kein echtes `gh`, kein Netzwerk, keine MCP-Werkzeuge - gelesen werden ausschliesslich Dateien
dieses Repositories.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Mapping
from pathlib import Path

import pytest

REPO_WURZEL = Path(__file__).parents[2]

# Der eine erlaubte Ort. Jede andere Datei des Suchraums ist wertfrei.
KATALOG = ".claude/skills/github-access/SKILL.md"
CAPTURE = ".claude/skills/capture/SKILL.md"

BEREICH_OPERATION = "issue-bereich-setzen"

# Die eingefrorene Erwartungsmenge. Zusammen mit der Vorrat-Zeile im Katalog ist sie das Paar,
# das ADR 0085 Abschnitt 3 "bewusste Ergaenzung" nennt: Ein siebter Wert faerbt rot, bis er an
# beiden Stellen steht. Der Buchhaltungs-Vorbehalt gegen Konstantenvergleiche gilt hier
# ausdruecklich nicht - die Menge selbst *ist* die Zusage ("geschlossen").
ERWARTETER_VORRAT = frozenset(
    {
        "bereich:frontend",
        "bereich:backend",
        "bereich:pipeline",
        "bereich:ai-workflow",
        "bereich:design",
        "bereich:infra",
    }
)

# Der Suchraum ist alles, was Git verwaltet - abzueglich genau dieser Praefixe. Negativliste
# statt Aufzaehlung: Eine Positivliste waechst nicht mit, und ein Ort, der ihr fehlt, faellt
# nicht auf, weil der Waechter dort schlicht nicht hinsieht.
AUSGESCHLOSSENE_PRAEFIXE = ("specs/",)

# Diese Datei fuehrt die Werte als Erwartungsmenge und in jeder Gegenprobe. Der Ausschluss ist
# an den eigenen Pfad gebunden und wird gegen ihn geprueft (siehe Selbstschutz unten).
WAECHTERDATEI = "scripts/tests/test_bereichsvorrat.py"

# Selbstschutz: bewusst weit unter dem Ist-Stand (gemessen 2026-09-11: 688 verwaltete Dateien,
# davon 19 nicht als UTF-8 lesbar und 214 unter `specs/`, also rund 454 im Suchraum) - faengt den
# Totalausfall der Aufzaehlung, nicht jede geloeschte Datei.
MINDESTZAHL_DATEIEN_IM_SUCHRAUM = 300

# Untergrenze fuer das *Gesehene*, nicht fuer den gelesenen Raum: Ein Muster, das nirgends
# trifft, meldet einen sauberen Bestand und einen kaputten Scanner gleich.
MINDESTZAHL_VORKOMMEN_IM_KATALOG = 6

# Die Vorrat-Zeile wird ueber ihren **Zeilenanfang** erkannt, nicht ueber ihren vollstaendigen
# Wortlaut: Eine zweite Zeile, die den Vorrat leicht anders einleitet, soll als Dublette
# auffallen und nicht am Muster vorbeirutschen.
_VORRAT_ZEILE = re.compile(r"^\*\*Bereichsvorrat(?P<rest>[^\n]*)$", re.MULTILINE)

# **Zwei Muster mit zwei Aufgaben.** Sie sehen aehnlich aus und duerfen nicht zusammengelegt
# werden - ihre Fehlerrichtungen sind entgegengesetzt:
#
# * `_VORRATS_WERT` liest die Formzeile und prueft die Label-Argumente des `gh`-Wegs. Hier ist
#   **eng** richtig: Was dort steht, soll wohlgeformt sein, und ein Wert, der es nicht ist, faellt
#   ueber den Vergleich gegen die eingefrorene Menge auf.
# * `_FREMDER_WERT` sucht **ausserhalb** des Katalogs. Hier ist eng **falsch**, und das ist im
#   Copilot-Review belegt worden: `bereich:Frontend`, `bereich:1` und `bereich:FOO` sind genau
#   das, was die Abwesenheit verhindern soll - ein zweiter Wahrheitsort -, passierten das enge
#   Muster aber unbemerkt. Dieselbe Klasse wie die Positivliste im Suchraum: **Die Zusicherung war
#   enger als ihr Zweck.** Ein Abwesenheits-Scan wird deshalb so breit formuliert, wie der Schaden
#   reicht, nicht so eng wie der erwuenschte Wert.
#
# Beide teilen den Lookbehind, der den Wert vom deutschen Fliesstext trennt: "Anwendungsbereich:"
# und "Der Bereich:" sind keine Werte, `bereich:design` ist einer. Der breite Matcher verlangt
# mindestens ein Wortzeichen hinter dem Doppelpunkt - ein blosses "bereich:" am Zeilenende ist
# kein vergebener Wert.
_VORRATS_WERT = re.compile(r"(?<![\w-])bereich:[a-z][a-z0-9-]*")
_FREMDER_WERT = re.compile(r"(?<![\w-])bereich:[\w-]+")

_EINTRAG_KOPF = re.compile(r"^### `(?P<id>[^`\n]+)`", re.MULTILINE)
_ABSCHNITT = re.compile(r"^## ", re.MULTILINE)
_LABEL_ARGUMENT = re.compile(r"--(?:add|remove)-label\s+(?P<wert>\S+)")
# Eine Nachhol-Zeile hat im Katalog eine feste Form: Listenpunkt, Operations-ID in Backticks,
# Doppelpunkt, `gh`-Befehl. Genau diese Form darf im Block dieser Operation nicht vorkommen.
_NACHHOL_ZEILE = re.compile(rf"^- `{re.escape(BEREICH_OPERATION)}`:\s*`gh ", re.MULTILINE)
KEINE_NACHHOL_MARKIERUNG = "keine Nachhol-Zeile"


# --- Reine Funktionen ---------------------------------------------------------------------


def vorrat_zeilen(text: str) -> list[str]:
    """Reine Funktion: die Restinhalte aller Zeilen fester Form, in Fundreihenfolge."""
    return [treffer.group("rest") for treffer in _VORRAT_ZEILE.finditer(text)]


def vorrat_aus_text(text: str) -> frozenset[str]:
    """Reine Funktion: der Vorrat der **einen** Formzeile.

    Keine Zeile und mehr als eine Zeile sind beides laute Fehlerfaelle mit eigener Meldung - ein
    stiller Nullbefund waere hier dasselbe wie eine bestandene Pruefung.
    """
    zeilen = vorrat_zeilen(text)
    if len(zeilen) != 1:
        raise ValueError(
            f"{len(zeilen)} Zeilen der Form '**Bereichsvorrat …' gefunden, erwartet genau eine. "
            "Null heisst: Der Vorrat steht nirgends mehr als Literal, und die Erwartungsmenge "
            "dieses Tests prueft nichts. Mehr als eine heisst: Es gibt zwei Wahrheitsorte, die "
            "auseinanderlaufen koennen."
        )
    return frozenset(_VORRATS_WERT.findall(zeilen[0]))


def werte_ausserhalb_des_katalogs(abbild: Mapping[str, str]) -> list[str]:
    """Reine Funktion: meldet jeden `bereich:`-Wert ausserhalb von `KATALOG`.

    Ein leerer Suchraum ist ein Fehlerfall mit eigener Meldung, kein stiller Nullbefund.
    """
    if not abbild:
        raise ValueError(
            "0 Dateien im Suchraum: Damit ist 'nur ein Ort nennt die Werte' ungeprueft. Entweder "
            "lief die Dateiaufzaehlung im falschen Arbeitsverzeichnis, oder sie ist kaputt - ein "
            "leerer Suchraum darf nie als 'nichts gefunden' durchgehen."
        )

    befunde: list[str] = []
    for datei in sorted(abbild):
        if datei == KATALOG:
            continue
        for nummer, zeile in enumerate(abbild[datei].split("\n"), start=1):
            befunde.extend(f"{datei}:{nummer}: {wert!r}" for wert in _FREMDER_WERT.findall(zeile))
    return befunde


def nennungen(abbild: Mapping[str, str], begriff: str) -> list[str]:
    """Reine Funktion: je Vorkommen eines Begriffs seine Fundstelle."""
    return [
        f"{datei}:{nummer}"
        for datei in sorted(abbild)
        for nummer, zeile in enumerate(abbild[datei].split("\n"), start=1)
        if begriff in zeile
    ]


def eintragsblock(text: str, operation: str) -> str:
    """Reine Funktion: der Textblock einer Katalog-Operation.

    Er endet an der naechsten Operation **oder** am naechsten `##`-Abschnitt - ohne die zweite
    Grenze zoege der letzte Eintrag den Resttext der Datei in seinen Block und bestuende jede
    Block-Zusicherung zufaellig.
    """
    koepfe = list(_EINTRAG_KOPF.finditer(text))
    for nummer, kopf in enumerate(koepfe):
        if kopf.group("id") != operation:
            continue
        grenzen = [len(text)]
        if nummer + 1 < len(koepfe):
            grenzen.append(koepfe[nummer + 1].start())
        naechster_abschnitt = _ABSCHNITT.search(text, kopf.end())
        if naechster_abschnitt:
            grenzen.append(naechster_abschnitt.start())
        return text[kopf.start() : min(grenzen)]

    raise ValueError(
        f"Kein Katalogeintrag `{operation}` gefunden. Entweder ist die Operation verschwunden, "
        "oder die Eintragsform hat sich geaendert - dann ist dieser Test mitzuziehen, sonst "
        "prueft er lautlos nichts mehr."
    )


def label_argumente(block: str) -> list[str]:
    """Reine Funktion: die Werte hinter `--add-label`/`--remove-label` eines Blocks."""
    return [treffer.group("wert") for treffer in _LABEL_ARGUMENT.finditer(block)]


# --- Duenne Leser -------------------------------------------------------------------------


def suchraum(wurzel: Path = REPO_WURZEL) -> dict[str, str]:
    """Alles von Git Verwaltete ausser `specs/**` und dieser Datei - als Pfad->Text-Abbild.

    Ueber `git ls-files` statt `rglob`, damit nicht verwaltete Arbeitskopien (etwa ein Worktree
    unterhalb von `.claude/`) nicht in den Suchraum geraten. Nicht als UTF-8 lesbare Dateien
    werden uebersprungen statt den Lauf abzubrechen; in ihnen wird kein Label-Vorrat
    dokumentiert.
    """
    ergebnis = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=wurzel,
        capture_output=True,
        check=True,
    )
    pfade = [pfad.decode("utf-8") for pfad in ergebnis.stdout.split(b"\0") if pfad]

    abbild: dict[str, str] = {}
    for pfad in pfade:
        if pfad == WAECHTERDATEI or pfad.startswith(AUSGESCHLOSSENE_PRAEFIXE):
            continue
        try:
            abbild[pfad] = (wurzel / pfad).read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue
    return abbild


def katalogtext(wurzel: Path = REPO_WURZEL) -> str:
    """Duenner Leser fuer den einen erlaubten Ort."""
    return (wurzel / KATALOG).read_text(encoding="utf-8")


# --- Selbstschutz -------------------------------------------------------------------------


def test_der_suchraum_hat_eine_plausible_groesse() -> None:
    """Eine kaputte Aufzaehlung darf nicht als Nullbefund durchgehen."""
    dateien = suchraum()

    assert len(dateien) >= MINDESTZAHL_DATEIEN_IM_SUCHRAUM, (
        f"Nur {len(dateien)} Dateien im Suchraum (erwartet: mindestens "
        f"{MINDESTZAHL_DATEIEN_IM_SUCHRAUM}). Die Aufzaehlung ist kaputt; ein Nullbefund dieses "
        "Tests waere dann bedeutungslos."
    )


def test_der_katalog_und_capture_liegen_im_suchraum() -> None:
    """Beide geprueften Orte muessen im aufgezaehlten Bestand liegen, nicht bloss gelesen werden."""
    dateien = suchraum()

    assert KATALOG in dateien, (
        f"{KATALOG} liegt nicht im Suchraum. Dann prueft der Abwesenheits-Test einen Raum, in dem "
        "der erlaubte Ort gar nicht vorkommt - und seine Nullmeldung sagt nichts."
    )
    assert CAPTURE in dateien, (
        f"{CAPTURE} liegt nicht im Suchraum. Zusicherung (d) waere dann leer wahr: Sie prueft "
        "eine Abwesenheit in einer Datei, die niemand gelesen hat."
    )


@pytest.mark.parametrize(
    ("pfad", "warum"),
    [
        (
            "CLAUDE.md",
            "die Verfassung des Projekts - sie liegt in keinem Verzeichnis und fiel aus jeder "
            "verzeichnisweisen Aufzaehlung heraus",
        ),
        (
            "docs/ai-workflow.md",
            "dort wird der Ablauf beschrieben, ein Wert sickert hier am ehesten ein",
        ),
        (
            ".github/ISSUE_TEMPLATE/feature_request.yml",
            "eine `labels:`-Zeile vergibt Label - genau der zweite Wahrheitsort, den die "
            "erste, aufzaehlende Fassung dieses Waechters uebersehen hat",
        ),
    ],
)
def test_ein_belegter_ort_der_labelvergabe_liegt_im_suchraum(pfad: str, warum: str) -> None:
    """Namentliche Anker neben der Untergrenze: Sie treffen den Fall 'ein Zweig faellt weg'."""
    assert pfad in suchraum(), (
        f"{pfad} liegt nicht im Suchraum ({warum}). Eine Untergrenze allein faengt das nicht - "
        "sie bliebe erfuellt, waehrend ausgerechnet dieser Ort ungeprueft bleibt."
    )


def test_specs_liegt_nicht_im_suchraum() -> None:
    """Der eine begruendete Ausschluss - und er ist gewollt, nicht vergessen."""
    dateien = suchraum()

    assert not [pfad for pfad in dateien if pfad.startswith("specs/")], (
        "`specs/**` liegt im Suchraum. Dort stehen eingefrorene Momentaufnahmen, und Spec 0259 "
        "wie ADR 0085 nennen den Vorrat selbst - der Waechter wuerde zum Umschreiben von "
        "Geschichte zwingen."
    )


def test_die_waechterdatei_schliesst_sich_unter_ihrem_eigenen_pfad_aus() -> None:
    """Ein Selbstausschluss, der auf einen toten Pfad zeigt, nimmt nichts aus - und faellt auf."""
    assert Path(__file__).resolve().relative_to(REPO_WURZEL.resolve()).as_posix() == WAECHTERDATEI

    assert WAECHTERDATEI not in suchraum(), (
        f"{WAECHTERDATEI} liegt im Suchraum. Sie fuehrt die Werte als Erwartungsmenge und in "
        "jeder Gegenprobe; der Waechter meldete sich selbst."
    )


@pytest.mark.parametrize("muster", [_VORRATS_WERT, _FREMDER_WERT], ids=["vorrat", "fremd"])
def test_jedes_muster_findet_im_katalog_mindestens_sechs_vorkommen(muster: re.Pattern[str]) -> None:
    """Untergrenze fuer das Gesehene - sonst ist ein kaputtes Muster ein sauberer Bestand.

    Je Muster einzeln: Der breite Matcher traegt den Abwesenheits-Scan und wird am Bestand sonst
    nie ausgeuebt, weil dort ausserhalb des Katalogs null Vorkommen liegen.
    """
    treffer = muster.findall(katalogtext())

    assert len(treffer) >= MINDESTZAHL_VORKOMMEN_IM_KATALOG, (
        f"Das Muster {muster.pattern!r} findet im Katalog nur {len(treffer)} Vorkommen (erwartet: "
        f"mindestens {MINDESTZAHL_VORKOMMEN_IM_KATALOG}). Der Erfolgsfall des Abwesenheits-Tests "
        "ist 'nichts gefunden' - ohne diese Untergrenze waere ein kaputtes Muster davon nicht zu "
        "unterscheiden."
    )


# --- (a) Der Vorrat steht in genau einer Zeile fester Form --------------------------------


def test_genau_eine_zeile_fester_form_traegt_den_vorrat() -> None:
    zeilen = vorrat_zeilen(katalogtext())

    assert len(zeilen) == 1, (
        f"{len(zeilen)} Zeilen der Form '**Bereichsvorrat …' im Katalog, erwartet genau eine. "
        "Eine zweite Vorrat-Zeile ist ein Widerspruch und muss laut auffallen."
    )


def test_der_vorrat_ist_die_eingefrorene_menge() -> None:
    vorrat = vorrat_aus_text(katalogtext())

    assert vorrat == ERWARTETER_VORRAT, (
        f"Fehlend: {sorted(ERWARTETER_VORRAT - vorrat)}; unerwartet: "
        f"{sorted(vorrat - ERWARTETER_VORRAT)}. Der Vorrat ist geschlossen: Ein neuer Wert kommt "
        "ueber die Aenderung dieser Zeile **und** dieser Erwartungsmenge hinzu - dieses Paar ist "
        "die bewusste Ergaenzung, nicht die eine oder die andere Seite."
    )


# --- (b) Kein Wert ausserhalb des Katalogs ------------------------------------------------


def test_kein_bereichswert_ausserhalb_des_katalogs() -> None:
    befunde = werte_ausserhalb_des_katalogs(suchraum())

    assert not befunde, (
        f"`bereich:`-Wert(e) ausserhalb von {KATALOG}: {'; '.join(befunde)}. Ablauf-Skills und "
        "Dokumentation nennen ausschliesslich die Operations-ID; eine zweite Stelle mit Werten "
        "laeuft von der ersten weg."
    )


# --- (d) `capture` nennt weder die Operation noch einen Wert -------------------------------


def test_capture_nennt_die_operation_nicht() -> None:
    """Die Leere beim Erfassen ist das Fehlen eines Schritts, nicht ein neuer Schritt."""
    fundstellen = nennungen({CAPTURE: suchraum()[CAPTURE]}, BEREICH_OPERATION)

    assert not fundstellen, (
        f"`{BEREICH_OPERATION}` kommt in {CAPTURE} vor ({fundstellen}). Der Bereich entsteht beim "
        "Schaerfen, nicht beim Erfassen - `capture` stellt keine inhaltliche Frage und koennte "
        "ihn nicht ableiten."
    )


def test_capture_nennt_keinen_bereichswert() -> None:
    fundstellen = werte_ausserhalb_des_katalogs({CAPTURE: suchraum()[CAPTURE]})

    assert not fundstellen, (
        f"`bereich:`-Wert(e) in {CAPTURE}: {'; '.join(fundstellen)}. Auch ein Beispielwert ist "
        "ein zweiter Wahrheitsort."
    )


# --- Zwei Eigenschaften des Eintrags selbst ------------------------------------------------


def test_der_eintrag_traegt_keine_nachhol_zeile() -> None:
    """Ihr Fehlschlag haelt die Story zurueck - er ist nichts, was sich nachholen liesse."""
    block = eintragsblock(katalogtext(), BEREICH_OPERATION)

    assert not _NACHHOL_ZEILE.search(block), (
        f"`{BEREICH_OPERATION}` fuehrt eine Nachhol-Zeile. Sie ist ein Issue-Zugriff, der remote "
        "traegt; ihr Fehlschlag ist ein echter Fehlschlag, nach dem der Abschluss als Ganzes "
        "wiederholt wird - unter `## Lokal nachzuholen` steht nur, was sich ohne diese "
        "Wiederholung nachholen laesst."
    )
    assert KEINE_NACHHOL_MARKIERUNG in block, (
        f"`{BEREICH_OPERATION}` fuehrt keine Nachhol-Zeile und sagt auch nicht, warum. Eine "
        "stille Auslassung ist von einer vergessenen Zeile nicht unterscheidbar."
    )


def test_das_label_argument_traegt_weder_variable_noch_substitution() -> None:
    """Der Wert kommt aus einem geschlossenen Vokabular - Regel 4.1 greift dort nicht.

    Geprueft wird das nicht ueber ein Verbot von `$` und Backtick, sondern positiv: Jedes
    Label-Argument **ist** ein Wert des Vorrats. Ein Verbot liesse jede andere Form durch, die
    niemand vorhergesehen hat; die Zugehoerigkeit zum Vorrat schliesst sie alle aus.
    """
    block = eintragsblock(katalogtext(), BEREICH_OPERATION)
    argumente = label_argumente(block)

    assert argumente, (
        f"Der Block von `{BEREICH_OPERATION}` fuehrt kein `--add-label`/`--remove-label`-Argument "
        "mehr. Dann ist diese Zusicherung leer wahr und die verbindliche `gh`-Form steht nirgends."
    )
    fremd = [wert for wert in argumente if wert not in ERWARTETER_VORRAT]
    assert not fremd, (
        f"Label-Argument(e) ausserhalb des Vorrats: {fremd}. Erlaubt ist ausschliesslich ein "
        f"Literal aus {sorted(ERWARTETER_VORRAT)} - keine Variable, keine Substitution, kein "
        "Platzhalter."
    )


# --- Gegenproben an synthetischem Text ----------------------------------------------------


_FORMZEILE = (
    "**Bereichsvorrat (geschlossen):** `bereich:frontend`, `bereich:backend`, "
    "`bereich:pipeline`, `bereich:ai-workflow`, `bereich:design`, `bereich:infra`\n"
)


def test_die_erwartete_formzeile_liefert_die_erwartete_menge() -> None:
    assert vorrat_aus_text(f"### `x`\n\n{_FORMZEILE}\nProsa.\n") == ERWARTETER_VORRAT


def test_ein_siebter_wert_faellt_auf() -> None:
    text = _FORMZEILE.rstrip("\n") + ", `bereich:doku`\n"

    assert vorrat_aus_text(text) != ERWARTETER_VORRAT
    assert "bereich:doku" in vorrat_aus_text(text)


def test_ein_entfernter_wert_faellt_auf() -> None:
    text = _FORMZEILE.replace(", `bereich:infra`", "")

    assert vorrat_aus_text(text) == ERWARTETER_VORRAT - {"bereich:infra"}


def test_eine_zweite_vorrat_zeile_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"2 Zeilen"):
        vorrat_aus_text(_FORMZEILE + _FORMZEILE)


def test_eine_fehlende_vorrat_zeile_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"0 Zeilen"):
        vorrat_aus_text("### `issue-bereich-setzen`\n\nNur Prosa.\n")


def test_eine_abweichend_eingeleitete_zweite_zeile_gilt_als_dublette() -> None:
    """Erkannt wird der Zeilenanfang, nicht der volle Wortlaut - sonst rutschte sie vorbei."""
    text = _FORMZEILE + "**Bereichsvorrat, zweite Fassung:** `bereich:doku`\n"

    assert len(vorrat_zeilen(text)) == 2


@pytest.mark.parametrize(
    "zeile",
    [
        "Setz `bereich:frontend` an das Issue.",
        "- `bereich:ai-workflow`",
        "Beispiel: bereich:doku (ein Wert, den es nicht gibt)",
        "Werte sind bereich:design und bereich:infra.",
    ],
)
def test_ein_wert_wird_an_beliebiger_stelle_der_zeile_gefunden(zeile: str) -> None:
    """Unverankert: Im geprueften Raum ist kein Vorkommen legitim, auch keines in Prosa."""
    assert werte_ausserhalb_des_katalogs({".claude/skills/x/SKILL.md": zeile + "\n"})


@pytest.mark.parametrize(
    "wert",
    ["bereich:Frontend", "bereich:FOO", "bereich:1", "bereich:Ai-Workflow", "bereich:tippfehler"],
)
def test_ein_nicht_wohlgeformter_wert_faellt_dem_aussenscan_trotzdem_auf(wert: str) -> None:
    """Copilot-Befund: Die Zusicherung war enger als ihr Zweck.

    Ein zweiter Wahrheitsort ist ein zweiter Wahrheitsort, auch wenn der Wert dort falsch
    geschrieben ist - erst recht dann, denn er passt auf keines der sechs Label und erzeugt beim
    Setzen entweder einen lauten Fehlschlag (`gh`) oder ein still angelegtes Label (`mcp`).
    """
    befunde = werte_ausserhalb_des_katalogs({".github/ISSUE_TEMPLATE/x.yml": f'labels: ["{wert}"]'})

    assert befunde == [f".github/ISSUE_TEMPLATE/x.yml:1: '{wert}'"]


@pytest.mark.parametrize("wert", ["bereich:Frontend", "bereich:FOO", "bereich:1"])
def test_der_vorratsparser_bleibt_eng(wert: str) -> None:
    """Gegenrichtung: Waeren beide Muster gleich breit, taugte keines mehr fuer seine Aufgabe.

    Ein nicht wohlgeformter Wert in der Formzeile darf nicht als gueltiger Vorratswert gelesen
    werden - er faellt dann als *fehlender* Wert gegen die eingefrorene Menge auf, und die
    Meldung nennt die richtige Ursache.
    """
    assert _VORRATS_WERT.findall(wert) != [wert]
    assert _FREMDER_WERT.findall(wert) == [wert]


@pytest.mark.parametrize(
    "zeile",
    [
        "Fuehr `issue-bereich-setzen` aus.",
        "Der Bereich: die Oberflaeche, das Backend, die Verarbeitungskette.",
        "Anwendungsbereich: Fotos.",
        "Ein Praefix wie `bereich-` ist kein Wert.",
        "Zustaendigkeitsbereich: Daniel.",
    ],
)
def test_prosa_ueber_den_bereich_gilt_nicht_als_wert(zeile: str) -> None:
    """Deutscher Fliesstext haengt `bereich` an ein Wort oder schreibt es gross."""
    assert werte_ausserhalb_des_katalogs({".claude/skills/x/SKILL.md": zeile + "\n"}) == []


def test_der_katalog_selbst_wird_uebergangen() -> None:
    assert werte_ausserhalb_des_katalogs({KATALOG: _FORMZEILE}) == []


def test_eine_andere_datei_wird_nicht_uebergangen() -> None:
    abbild = {KATALOG: _FORMZEILE, "docs/ai-workflow.md": "Text\nSetz bereich:design.\n"}

    befunde = werte_ausserhalb_des_katalogs(abbild)

    assert befunde == ["docs/ai-workflow.md:2: 'bereich:design'"]


@pytest.mark.parametrize(
    "pfad",
    [
        ".github/ISSUE_TEMPLATE/feature_request.yml",
        ".github/workflows/ci.yml",
        "backend/src/photosort/labels.py",
        "frontend/src/api/client.ts",
        "README.md",
    ],
)
def test_ein_wert_ausserhalb_der_frueheren_drei_zweige_faellt_auf(pfad: str) -> None:
    """Die Regression zur ersten, aufzaehlenden Fassung - sie sah keinen dieser Orte.

    Ein Issue-Formular mit `labels: ["bereich:frontend"]` ist ein zweiter Wahrheitsort und
    verletzt Akzeptanzkriterium 1; unter der Positivliste blieb genau das gruen.
    """
    abbild = {KATALOG: _FORMZEILE, pfad: 'labels: ["bug", "bereich:frontend"]\n'}

    assert werte_ausserhalb_des_katalogs(abbild) == [f"{pfad}:1: 'bereich:frontend'"]


def test_ein_leerer_suchraum_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"0 Dateien"):
        werte_ausserhalb_des_katalogs({})


def test_eine_operations_nennung_in_capture_wird_gefunden() -> None:
    """Positivfall synthetisch - im Bestand gibt es null legitime Vorkommen."""
    abbild = {CAPTURE: f"Schritt 5:\n- `{BEREICH_OPERATION}`\n"}

    assert nennungen(abbild, BEREICH_OPERATION) == [f"{CAPTURE}:2"]


def test_ein_block_endet_am_naechsten_eintrag() -> None:
    text = (
        "### `issue-bereich-setzen` — Beschreibung\n\n"
        f"{_FORMZEILE}"
        "### `issue-body-schreiben` — Beschreibung\n\n"
        "- `issue-bereich-setzen`: `gh issue edit <NNN>`\n"
    )

    block = eintragsblock(text, BEREICH_OPERATION)

    assert "issue-body-schreiben" not in block
    assert not _NACHHOL_ZEILE.search(block)


def test_ein_block_endet_am_naechsten_abschnitt() -> None:
    text = (
        "### `issue-bereich-setzen` — Beschreibung\n\n"
        f"{_FORMZEILE}"
        "\n## Die vier Haertungsregeln\n\n"
        "- `issue-bereich-setzen`: `gh issue edit <NNN>`\n"
    )

    assert "Haertungsregeln" not in eintragsblock(text, BEREICH_OPERATION)


def test_eine_nachhol_zeile_im_block_wird_erkannt() -> None:
    """Gegenprobe zum Muster: Ohne sie waere die Abwesenheits-Aussage nie ausgeuebt."""
    text = (
        "### `issue-bereich-setzen` — Beschreibung\n\n"
        "- `issue-bereich-setzen`: `gh issue edit <NNN> --repo TheRealKoller/photosort`\n"
    )

    assert _NACHHOL_ZEILE.search(eintragsblock(text, BEREICH_OPERATION))


def test_ein_fehlender_eintrag_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"Kein Katalogeintrag"):
        eintragsblock("### `issue-lesen` — Beschreibung\n", BEREICH_OPERATION)


@pytest.mark.parametrize(
    "argument",
    ["$BEREICH", "${BEREICH}", '"$(cat <bereich-datei>)"', "<Bereich>", "bereich:doku"],
)
def test_ein_label_argument_ausserhalb_des_vorrats_faellt_auf(argument: str) -> None:
    block = f"### `issue-bereich-setzen`\n\ngh issue edit <NNN> --add-label {argument}\n"

    assert [wert for wert in label_argumente(block) if wert not in ERWARTETER_VORRAT]


def test_ein_literales_label_argument_gilt_nicht_als_verstoss() -> None:
    block = (
        "### `issue-bereich-setzen`\n\n"
        "gh issue edit <NNN> --add-label bereich:frontend --remove-label bereich:backend\n"
    )

    assert label_argumente(block) == ["bereich:frontend", "bereich:backend"]
    assert not [wert for wert in label_argumente(block) if wert not in ERWARTETER_VORRAT]
