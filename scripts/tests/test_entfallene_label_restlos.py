"""Haelt fest, dass die drei entfallenen Label im lebenden Anweisungsraum nicht wiederkehren.

Seit ADR 0101 wird ein Label genau dann vergeben, wenn seine Aussage nicht ohnehin fuer jedes
Issue gilt. `idee`, `feature` und `needs-spec` erfuellen das nicht und sind entfallen. Dieser
Waechter sichert zu, dass keiner der drei Namen als **vergebenes oder verlangtes Label** in den
Suchraum zurueckkehrt. Bei Verletzung wird der Lauf rot und benennt Datei, Zeile und Wert; ohne
ihn entstuende das Label beim naechsten Erfassen stillschweigend neu, weil es auf GitHub ohne
Gegenwehr wieder angelegt wird.

Er ist **kein Wortverbot ueber drei Namen** - das truege `feature` nicht (gemessen 2026-09-14: in
210 von 525 gelesenen Dateien legitim, `specs/features/`, "Feature-Spec", `feature/`-Zweig).
Getragen wird die Zusicherung vierteilig, jeder Teil so breit wie der Schaden reicht:

1. **`needs-spec`** - freie Wortsuche, unverankert. Am Bestand null legitime Vorkommen.
2. **`idee`** - Wortsuche mit Wortgrenze, **fallunterscheidend**: Deutsche Prosa schreibt "Idee"
   gross, die Kleinschreibung ist die Labelform. Genau **eine** Fundstelle ist kein Verstoss und
   wird pfadgebunden ausgenommen, das Modell-Vokabular unter `backend/src/photosort/assets/`.
3. **Label-Konstrukte statt Woerter** - traegt `feature` und schliesst zugleich die
   Gross-/Kleinschreib-Luecke von (2). Gesucht werden die beiden Formen, in denen ein Label
   vergeben oder verlangt wird: eine `labels:`-Angabe in **jeder von YAML akzeptierten Form**
   (Flow-Form `labels: [...]` **und** Blockform mit eingerueckten `- `-Zeilen) und ein Argument
   hinter `--label`/`--add-label`/`--remove-label`. Der Wert wird normalisiert und an `|` **und**
   `,` getrennt - so zerfallen `<idee|bug>` und `--label feature,bug` in Einzelwerte -, danach
   **fallunabhaengig** verglichen. Regexseitig, ohne YAML-Parser: `scripts/pyproject.toml` fuehrt
   PyYAML nicht. **Die Blockform ist tragend, nicht kosmetisch:** `feature` zurueck in die
   Issue-Vorlage, in Blockform geschrieben, traefe ohne sie keine der Pruefungen - (1) und (2)
   decken `feature` nach Konstruktion nicht ab.
4. **Backtick-Konstrukt** - `` `idee` ``, `` `feature` ``, `` `needs-spec` `` kleingeschrieben und
   exakt. Das ist die Form, in der Skill-Texte Labelnamen schreiben, und sie deckt den einen Weg
   ab, auf dem `feature` sonst unbewacht zurueckkaeme: den `mcp`-Weg im Operationskatalog, der
   Label in Prosa benennt und kein `--label`-Konstrukt kennt.

**Der Suchraum ist eine Negativliste: alles aus `git ls-files`, ausser `specs/**` und dieser Datei
selbst.** Genau eine Positivliste hat in diesem Repositorium schon einmal
`.github/ISSUE_TEMPLATE/*.yml` uebersehen - die Dateien, die nachweislich Label vergeben. Jeder
Ausschluss wird einzeln begruendet:

* **`specs/**`** liegt **notwendig** ausserhalb, nicht bequem: Sicherheits- und Testkonzept und
  sechs ADRs nennen die entfallenden Namen beschreibend weiter. Ein Textscan koennte lebende von
  historischer Nennung nicht trennen und zwaenge zum Umschreiben abgeschlossener Dokumente.
* **Diese Datei selbst** fuehrt die Namen als Erwartungsmenge und in jeder Gegenprobe. Der
  Ausschluss ist an den eigenen Pfad gebunden und wird gegen ihn geprueft.
* **Die Pfadausnahme von (2)** ist an ihren **Treffer** gebunden, nicht nur an ihren Pfad: Ein
  eigener Fall liest die reale Datei aus dem Suchraum und behauptet, dass das Muster dort trifft.
  Sonst ueberlebte die Ausnahme ein Ersetzen oder Umbenennen des Assets und deckte still die
  naechste echte Fundstelle.

Nicht als UTF-8 lesbare Dateien werden uebersprungen statt den Lauf abzubrechen (gemessen
2026-09-14: 545 gelistete Dateien, davon 525 gelesen, 19 uebersprungen).

**Alle vier Teile starten gruen**, weil ihr Erfolgsfall eine Abwesenheit ist; der triviale Lauf
belegt fuer sie nichts. Tragend sind die synthetischen Gegenproben je Muster und die
Mutationsprobe je Zusicherung. Dazu die Untergrenze fuer das **Gesehene** - und sie ist
**wertgebunden statt zaehlend**: Unter den gesehenen `labels:`-Angaben muss die von
`bug_report.yml` mit Wert `bug` sein, unter den Label-Argumenten des Katalogs das `bug` des
`issue-anlegen`-Aufrufs. Eine Zaehlgrenze haette hier null Reserve (genau eine `labels:`-Zeile,
genau drei Label-Argumente), faerbte bei jeder legitimen Aenderung rot und wuerde dann abgesenkt,
bis sie nichts mehr sagt.

**Benannt bleibende Luecke:** formloser Fliesstext ("das Label feature") wird von keinem der vier
Teile erfasst. Das ist zugedeckt-vs-benannt eine bewusste Entscheidung fuer benannt.

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

# Die drei entfallenen Namen. Kleingeschrieben, weil fallunabhaengig verglichen wird.
ENTFALLENE_LABEL = frozenset({"idee", "feature", "needs-spec"})

# Der Name ohne jede legitime Nennung im Suchraum - als einziger frei suchbar.
FREIES_WORT = "needs-spec"

KATALOG = ".claude/skills/github-access/SKILL.md"
CAPTURE = ".claude/skills/capture/SKILL.md"
REFINEMENT = ".claude/skills/refinement/SKILL.md"
BUG_VORLAGE = ".github/ISSUE_TEMPLATE/bug_report.yml"

ANLEGE_OPERATION = "issue-anlegen"

# Der Wert, an dem die Untergrenze fuer das Gesehene haengt - an beiden Orten derselbe.
GESEHENER_WERT = "bug"

# Maschinell erzeugtes Modell-Vokabular; der Eintrag `▁idee` traegt ein vorangestelltes U+2581,
# das kein `\w` ist - die Wortgrenze greift dort also. Die Ausnahme ist an ihren Treffer gebunden.
VOKABULAR_AUSNAHME = "backend/src/photosort/assets/label_embedder_tokenizer.json"

AUSGESCHLOSSENE_PRAEFIXE = ("specs/",)

WAECHTERDATEI = "scripts/tests/test_entfallene_label_restlos.py"

# Selbstschutz: bewusst weit unter dem Ist-Stand (gemessen 2026-09-14: 545 verwaltete Dateien,
# davon 19 nicht als UTF-8 lesbar und 246 unter `specs/`, also rund 525 im Suchraum) - faengt den
# Totalausfall der Aufzaehlung, nicht jede geloeschte Datei.
MINDESTZAHL_DATEIEN_IM_SUCHRAUM = 300

_NEEDS_SPEC = re.compile(re.escape(FREIES_WORT))

# Fallunterscheidend: `Idee` ist deutsche Prosa, `idee` ist die Labelform. Die Wortgrenze schliesst
# den Bindestrich ein, damit `Ideen-Inbox` oder `idee-neu` nicht als Wort durchgehen.
_IDEE = re.compile(r"(?<![\w-])idee(?![\w-])")

# Die Schreibweise, in der Skill-Texte Labelnamen fuehren. Exakt und kleingeschrieben - ein
# `` `Feature` `` in Prosa ist kein vergebenes Label.
_BACKTICK_LABEL = re.compile(r"`(?:" + "|".join(sorted(map(re.escape, ENTFALLENE_LABEL))) + r")`")

# `^[ \t]*labels:` ist am Zeilenanfang verankert und trennt damit die Label-Angabe von
# `fine_labels:`/`branch_labels:`, ohne dass eine Ausnahmeliste noetig waere.
_LABELS_KOPF = re.compile(r"^[ \t]*labels:(?P<rest>.*)$")
_BLOCK_EINTRAG = re.compile(r"^[ \t]*-[ \t]+(?P<wert>.+?)[ \t]*$")

# `--label`, `--add-label`, `--remove-label` in einem Muster. Das Leerzeichen hinter dem Schalter
# ist tragend: `` `--add-label`/`--remove-label` `` in Prosa ist kein Aufruf.
_LABEL_ARGUMENT = re.compile(r"--(?:add-|remove-)?label[ \t]+(?P<wert>\S+)")

# An `|` **und** `,` getrennt: `<idee|bug>` und `feature,bug` sind Mehrfachangaben.
_TRENNER = re.compile(r"[|,]")

# Anfuehrungszeichen, Backticks, spitze und eckige Klammern gehoeren zur Schreibweise, nicht zum
# Wert - `"feature"`, `` `idee` ``, `<bug>` und `["bug"]` meinen alle den blanken Namen.
_RANDZEICHEN = "\"'`<>[] \t"

_EINTRAG_KOPF = re.compile(r"^### `(?P<id>[^`\n]+)`", re.MULTILINE)
_ABSCHNITT = re.compile(r"^## ", re.MULTILINE)


# --- Reine Funktionen ---------------------------------------------------------------------


def normalisierte_werte(roh: str) -> list[str]:
    """Reine Funktion: eine Label-Angabe als Liste blanker Werte.

    An `|` und `,` zerlegt, danach je Teil die Schreibweise abgestreift. Leere Teile fallen weg.
    """
    return [wert for teil in _TRENNER.split(roh) if (wert := teil.strip(_RANDZEICHEN))]


def labels_angaben(text: str) -> list[tuple[int, str]]:
    """Reine Funktion: jeder Wert einer `labels:`-Angabe, mit seiner Zeilennummer.

    Beide von YAML akzeptierten Formen: der Rest hinter dem Doppelpunkt (Flow-Liste oder Skalar)
    und, wenn dort nichts steht, die folgenden eingerueckten `- `-Zeilen. Leer- und
    Kommentarzeilen unterbrechen die Blockliste nicht, eine Zeile anderer Form beendet sie.
    """
    zeilen = text.split("\n")
    angaben: list[tuple[int, str]] = []
    for stelle, zeile in enumerate(zeilen):
        kopf = _LABELS_KOPF.match(zeile)
        if not kopf:
            continue

        rest = kopf.group("rest").strip()
        if rest:
            angaben.extend((stelle + 1, wert) for wert in normalisierte_werte(rest))
            continue

        for folge in range(stelle + 1, len(zeilen)):
            roh = zeilen[folge]
            if not roh.strip() or roh.lstrip().startswith("#"):
                continue
            eintrag = _BLOCK_EINTRAG.match(roh)
            if not eintrag:
                break
            angaben.extend((folge + 1, wert) for wert in normalisierte_werte(eintrag.group("wert")))
    return angaben


def label_argumente(text: str) -> list[tuple[int, str]]:
    """Reine Funktion: jeder Wert hinter `--label`/`--add-label`/`--remove-label`."""
    return [
        (nummer, wert)
        for nummer, zeile in enumerate(text.split("\n"), start=1)
        for treffer in _LABEL_ARGUMENT.finditer(zeile)
        for wert in normalisierte_werte(treffer.group("wert"))
    ]


def _geprueftes_abbild(abbild: Mapping[str, str]) -> Mapping[str, str]:
    """Ein leerer Suchraum ist ein Fehlerfall mit eigener Meldung, kein stiller Nullbefund."""
    if not abbild:
        raise ValueError(
            "0 Dateien im Suchraum: Damit ist 'keiner der drei Namen kommt noch vor' ungeprueft. "
            "Entweder lief die Dateiaufzaehlung im falschen Arbeitsverzeichnis, oder sie ist "
            "kaputt - ein leerer Suchraum darf nie als 'nichts gefunden' durchgehen."
        )
    return abbild


def _treffer(abbild: Mapping[str, str], muster: re.Pattern[str], *, ausser: str = "") -> list[str]:
    befunde: list[str] = []
    for datei in sorted(_geprueftes_abbild(abbild)):
        if ausser and datei == ausser:
            continue
        for nummer, zeile in enumerate(abbild[datei].split("\n"), start=1):
            befunde.extend(f"{datei}:{nummer}: {fund!r}" for fund in muster.findall(zeile))
    return befunde


def freies_wort_befunde(abbild: Mapping[str, str]) -> list[str]:
    """Reine Funktion (1): jedes Vorkommen von `needs-spec`, unverankert."""
    return _treffer(abbild, _NEEDS_SPEC)


def idee_befunde(abbild: Mapping[str, str]) -> list[str]:
    """Reine Funktion (2): jedes kleingeschriebene `idee` als Wort, ausser im Modell-Vokabular."""
    return _treffer(abbild, _IDEE, ausser=VOKABULAR_AUSNAHME)


def backtick_befunde(abbild: Mapping[str, str]) -> list[str]:
    """Reine Funktion (4): jeder der drei Namen in Backticks, kleingeschrieben und exakt."""
    return _treffer(abbild, _BACKTICK_LABEL)


def label_konstrukt_befunde(abbild: Mapping[str, str]) -> list[str]:
    """Reine Funktion (3): jeder entfallene Name als Wert eines Label-Konstrukts.

    Fallunabhaengig verglichen - `--label Idee` vergibt dasselbe Label wie `--label idee`.
    """
    befunde: list[str] = []
    for datei in sorted(_geprueftes_abbild(abbild)):
        text = abbild[datei]
        werte = sorted([*labels_angaben(text), *label_argumente(text)])
        befunde.extend(
            f"{datei}:{nummer}: {wert!r}"
            for nummer, wert in werte
            if wert.lower() in ENTFALLENE_LABEL
        )
    return befunde


def eintragsblock(text: str, operation: str) -> str:
    """Reine Funktion: der Textblock einer Katalog-Operation.

    Er endet an der naechsten Operation **oder** am naechsten `##`-Abschnitt - ohne die zweite
    Grenze zoege der letzte Eintrag den Resttext der Datei in seinen Block.
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


# --- Duenner Leser ------------------------------------------------------------------------


def suchraum(wurzel: Path = REPO_WURZEL) -> dict[str, str]:
    """Alles von Git Verwaltete ausser `specs/**` und dieser Datei - als Pfad->Text-Abbild.

    Ueber `git ls-files` statt `rglob`, damit nicht verwaltete Arbeitskopien (etwa ein Worktree
    unterhalb von `.claude/`) nicht in den Suchraum geraten. Nicht als UTF-8 lesbare Dateien
    werden uebersprungen statt den Lauf abzubrechen; in ihnen wird kein Label vergeben.
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


# --- Selbstschutz -------------------------------------------------------------------------


def test_der_suchraum_hat_eine_plausible_groesse() -> None:
    """Eine kaputte Aufzaehlung darf nicht als Nullbefund durchgehen."""
    dateien = suchraum()

    assert len(dateien) >= MINDESTZAHL_DATEIEN_IM_SUCHRAUM, (
        f"Nur {len(dateien)} Dateien im Suchraum (erwartet: mindestens "
        f"{MINDESTZAHL_DATEIEN_IM_SUCHRAUM}). Die Aufzaehlung ist kaputt; ein Nullbefund dieses "
        "Waechters waere dann bedeutungslos."
    )


@pytest.mark.parametrize(
    ("pfad", "warum"),
    [
        (
            "CLAUDE.md",
            "die Verfassung des Projekts - sie liegt in keinem Verzeichnis und fiel aus jeder "
            "verzeichnisweisen Aufzaehlung heraus",
        ),
        (BUG_VORLAGE, "die eine Datei, die nach dieser Story noch eine `labels:`-Angabe fuehrt"),
        (KATALOG, "der eine Ort, an dem der Label-Wert als Literal steht"),
        (CAPTURE, "der Erfassungsweg, an dem das Typ-Label entfallen ist"),
        (REFINEMENT, "der Schaerfungsweg, der die Schreibmenge des Neuanlage-Pfads bildet"),
    ],
)
def test_ein_namentlicher_anker_liegt_im_suchraum(pfad: str, warum: str) -> None:
    """Namentliche Anker neben der Untergrenze: Sie treffen den Fall 'ein Zweig faellt weg'."""
    assert pfad in suchraum(), (
        f"{pfad} liegt nicht im Suchraum ({warum}). Eine Untergrenze allein faengt das nicht - "
        "sie bliebe erfuellt, waehrend ausgerechnet dieser Ort ungeprueft bleibt."
    )


def test_specs_liegen_nicht_im_suchraum() -> None:
    """Der Ausschluss ist notwendig, nicht bequem - sonst zwaenge ein Textscan zum Umschreiben."""
    unter_specs = [pfad for pfad in suchraum() if pfad.startswith(AUSGESCHLOSSENE_PRAEFIXE)]

    assert unter_specs == [], (
        f"{len(unter_specs)} Datei(en) unter `specs/` liegen im Suchraum, z.B. {unter_specs[:3]}. "
        "Dort nennen Sicherheits- und Testkonzept sowie sechs ADRs die entfallenden Namen "
        "beschreibend weiter; ein Treffer dort waere kein Verstoss, sondern Geschichte."
    )


def test_der_selbstausschluss_ist_an_den_eigenen_pfad_gebunden() -> None:
    """Ein Ausschluss, der auf einen Pfad zeigt, den es nicht gibt, nimmt nichts aus."""
    assert (REPO_WURZEL / WAECHTERDATEI).resolve() == Path(__file__).resolve(), (
        f"{WAECHTERDATEI} ist nicht der Pfad dieser Datei. Der Ausschluss ist dann zu einem "
        "fremden Pfad verrottet: Diese Datei liegt im Suchraum und faerbt mit ihren eigenen "
        "Gegenproben rot, waehrend die genannte Datei ungeprueft bleibt."
    )
    assert WAECHTERDATEI not in suchraum()


def test_die_pfadausnahme_trifft_in_der_realen_datei() -> None:
    """Die Ausnahme wird gegen ihren **Anlass** geprueft, nicht gegen ihren Namen.

    Wird das Asset ersetzt oder umbenannt, bliebe sonst eine Ausnahme stehen, die nichts mehr
    ausnimmt - und die naechste echte Fundstelle waere still gedeckt.
    """
    inhalt = (REPO_WURZEL / VOKABULAR_AUSNAHME).read_text(encoding="utf-8")

    assert _IDEE.search(inhalt), (
        f"Das `idee`-Muster trifft in {VOKABULAR_AUSNAHME} nicht mehr. Die Pfadausnahme hat damit "
        "keinen Anlass mehr und ist zu streichen, statt als blinder Deckel stehenzubleiben."
    )


def test_die_ausgenommene_datei_liegt_im_suchraum() -> None:
    """Nur was gelesen wird, kann ausgenommen werden - sonst ist die Ausnahme leer wahr."""
    assert VOKABULAR_AUSNAHME in suchraum()


# --- Untergrenze fuer das Gesehene, wertgebunden statt zaehlend -----------------------------


def test_die_labels_angabe_der_bug_vorlage_wird_gesehen() -> None:
    """Ohne diesen Wert traefe das `labels:`-Muster nirgends und meldete trotzdem 'sauber'."""
    werte = [wert for _, wert in labels_angaben(suchraum()[BUG_VORLAGE])]

    assert GESEHENER_WERT in werte, (
        f"Das `labels:`-Muster findet in {BUG_VORLAGE} kein {GESEHENER_WERT!r} (gesehen: {werte}). "
        "Ein Muster, das nirgends trifft, meldet einen sauberen Bestand und einen kaputten "
        "Scanner gleich. Gezaehlt wird hier bewusst nicht - genau eine `labels:`-Zeile haette "
        "null Reserve."
    )


def test_das_label_argument_des_anlege_aufrufs_wird_gesehen() -> None:
    """Dasselbe fuer das zweite Muster, gebunden an den Block, der es fuehrt."""
    block = eintragsblock(suchraum()[KATALOG], ANLEGE_OPERATION)
    werte = [wert for _, wert in label_argumente(block)]

    assert GESEHENER_WERT in werte, (
        f"Das `--label`-Muster findet im Block `{ANLEGE_OPERATION}` kein {GESEHENER_WERT!r} "
        f"(gesehen: {werte}). Entweder vergibt der Aufruf kein Label mehr - dann ist diese "
        "Untergrenze mitzuziehen -, oder das Muster ist kaputt und alle drei Namen kaemen "
        "unbemerkt zurueck."
    )


# --- Die vier Zusicherungen am Bestand ------------------------------------------------------


def test_needs_spec_kommt_nirgends_mehr_vor() -> None:
    befunde = freies_wort_befunde(suchraum())

    assert befunde == [], (
        f"{FREIES_WORT!r} steht noch im Suchraum: {befunde}. Der Bearbeitungsstand, den das Label "
        "andeutete, wird vom Board als Status gefuehrt; das Label ist entfallen."
    )


def test_idee_kommt_kleingeschrieben_nirgends_mehr_vor() -> None:
    befunde = idee_befunde(suchraum())

    assert befunde == [], (
        f"Kleingeschriebenes 'idee' steht noch im Suchraum: {befunde}. Jedes Issue beginnt als "
        "Idee - das Label sagt nichts aus, was nicht ohnehin fuer alle gilt (ADR 0101). Deutsche "
        "Prosa schreibt 'Idee' gross und ist davon unberuehrt."
    )


def test_kein_label_konstrukt_traegt_einen_entfallenen_wert() -> None:
    befunde = label_konstrukt_befunde(suchraum())

    assert befunde == [], (
        f"Ein Label-Konstrukt vergibt oder verlangt einen entfallenen Namen: {befunde}. Geprueft "
        f"werden `labels:`-Angaben (Flow- und Blockform) und Argumente hinter "
        "`--label`/`--add-label`/`--remove-label`, fallunabhaengig gegen "
        f"{sorted(ENTFALLENE_LABEL)}."
    )


def test_kein_backtick_konstrukt_traegt_einen_entfallenen_namen() -> None:
    befunde = backtick_befunde(suchraum())

    assert befunde == [], (
        f"Ein entfallener Labelname steht in Backticks: {befunde}. Das ist die Form, in der "
        "Skill-Texte Label benennen - und der einzige Weg, auf dem `feature` sonst unbewacht "
        "zurueckkaeme, weil der `mcp`-Weg kein `--label`-Konstrukt kennt."
    )


# --- Gegenproben je Muster: ohne sie waere jede Abwesenheit nie ausgeuebt --------------------


@pytest.mark.parametrize(
    ("zeile", "erwartet"),
    [
        ("gh issue create --label idee", "idee"),
        ("gh issue create --label <idee|bug>", "idee"),
        ("gh issue create --label Idee", "Idee"),
        ("gh issue edit <NNN> --add-label feature,bug", "feature"),
        ("gh issue edit <NNN> --remove-label needs-spec", "needs-spec"),
        ('gh issue create --label "feature"', "feature"),
    ],
)
def test_ein_label_argument_mit_entfallenem_wert_faellt_auf(zeile: str, erwartet: str) -> None:
    """Mehrfachangaben, Schreibweisen und Grossschreibung vergeben dasselbe Label."""
    befunde = label_konstrukt_befunde({KATALOG: zeile + "\n"})

    assert befunde == [f"{KATALOG}:1: {erwartet!r}"]


@pytest.mark.parametrize(
    ("text", "erwartet"),
    [
        ('labels: ["feature", "needs-spec"]\n', [(1, "feature"), (1, "needs-spec")]),
        ("labels: [feature]\n", [(1, "feature")]),
        ("labels:\n  - feature\n  - needs-spec\n", [(2, "feature"), (3, "needs-spec")]),
        ("labels:\n- feature\n", [(2, "feature")]),
        ('labels:\n  - "feature"\n', [(2, "feature")]),
        ("labels: feature\n", [(1, "feature")]),
    ],
)
def test_eine_labels_angabe_wird_in_jeder_yaml_form_gesehen(
    text: str, erwartet: list[tuple[int, str]]
) -> None:
    """Die Blockform ist tragend: `feature` traefe sonst keine der vier Pruefungen."""
    assert labels_angaben(text) == erwartet


def test_die_blockform_endet_an_der_naechsten_zeile_anderer_form() -> None:
    """Sonst zoege eine spaetere, fremde Liste ihre Werte in die Label-Angabe."""
    text = "labels:\n  - bug\nbody:\n  - type: markdown\n"

    assert labels_angaben(text) == [(2, "bug")]


def test_needs_spec_in_prosa_faellt_auf() -> None:
    """Der eine Name ohne legitime Nennung wird unverankert gesucht, nicht als Konstrukt."""
    abbild = {"docs/ai-workflow.md": "Text\nDas Issue bekommt needs-spec dazu.\n"}

    assert freies_wort_befunde(abbild) == ["docs/ai-workflow.md:2: 'needs-spec'"]


def test_ein_backtick_name_faellt_auf() -> None:
    abbild = {CAPTURE: "Setz `feature` und `idee`.\n"}

    assert backtick_befunde(abbild) == [f"{CAPTURE}:1: '`feature`'", f"{CAPTURE}:1: '`idee`'"]


def test_ein_kleingeschriebenes_idee_faellt_auf() -> None:
    abbild = {REFINEMENT: "Bekannt ist das idee-Label.\nBekannt ist idee aus dem Aufruf.\n"}

    assert idee_befunde(abbild) == [f"{REFINEMENT}:2: 'idee'"]


def test_die_pfadausnahme_gilt_nur_fuer_ihren_pfad() -> None:
    """Derselbe Inhalt an einem anderen Pfad ist ein Verstoss - die Ausnahme ist pfadgebunden."""
    inhalt = '        "▁idee",\n'

    assert idee_befunde({VOKABULAR_AUSNAHME: inhalt}) == []
    assert idee_befunde({"backend/src/photosort/labels.py": inhalt}) == [
        "backend/src/photosort/labels.py:1: 'idee'"
    ]


def test_ein_leerer_suchraum_scheitert_laut_statt_still() -> None:
    for pruefung in (
        freies_wort_befunde,
        idee_befunde,
        label_konstrukt_befunde,
        backtick_befunde,
    ):
        with pytest.raises(ValueError, match=r"0 Dateien"):
            pruefung({})


# --- Nicht-Treffer-Proben: die Zusicherung darf legitimen Bestand nicht einfangen ------------


@pytest.mark.parametrize(
    "zeile",
    [
        "Die Idee wird als Issue festgehalten.",
        "Ideen landen in der Inbox.",
        "Eine Grundidee ohne Wortgrenze.",
        "Der Zweig heisst `idee-neu` und ist kein Label.",
    ],
)
def test_deutsche_prosa_ueber_eine_idee_gilt_nicht_als_label(zeile: str) -> None:
    """Die Kleinschreibung ist die Labelform; alles andere ist Fliesstext."""
    assert idee_befunde({"docs/ai-workflow.md": zeile + "\n"}) == []


@pytest.mark.parametrize(
    "zeile",
    [
        "Die Spec liegt unter specs/features/0464-aussagende-labels.md.",
        "Der Zweig heisst feature/0464-aussagende-labels.",
        "Eine Feature-Spec beschreibt, was gebaut wird.",
        "Auf dem `gh`-Weg wirken `--add-label`/`--remove-label` additiv.",
    ],
)
def test_legitime_nennung_von_feature_gilt_nicht_als_label(zeile: str) -> None:
    """`feature` ist als Begriff legitim - getragen wird es deshalb nur als Konstrukt."""
    abbild = {"docs/ai-workflow.md": zeile + "\n"}

    assert label_konstrukt_befunde(abbild) == []
    assert backtick_befunde(abbild) == []


@pytest.mark.parametrize(
    "zeile",
    [
        '    fine_labels: ["feature"]',
        "branch_labels: Union[str, Sequence[str], None] = None",
        "    scene_labels: list[SceneLabel] = []",
    ],
)
def test_ein_anderes_feld_auf_labels_ist_keine_label_angabe(zeile: str) -> None:
    """Die Verankerung am Zeilenanfang trennt die Label-Angabe von gleichnamigen Feldern."""
    assert labels_angaben(zeile + "\n") == []


def test_ein_fehlender_eintrag_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"Kein Katalogeintrag"):
        eintragsblock("### `issue-lesen` — Beschreibung\n", ANLEGE_OPERATION)
