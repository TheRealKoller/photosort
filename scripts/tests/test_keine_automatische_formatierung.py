r"""Waechter gegen jede eingecheckte Datei, die ein Kommando automatisch ausloest (K8, Spec 0400).

**Das Modul traegt seit Spec 0398 (K5) eine zweite Zusage, und sie ist breiter als die erste:
keine eingecheckte Datei loest ein Kommando ohne Zutun des Agenten aus** - nicht nur keine
Formatierung. Wer dieses Modul spaeter auf "Formatierung" zurueckschneidet, nimmt die einzige
mechanische Zusage jener Story still mit. Eine fuenfte Musterfamilie entsteht dafuer
ausdruecklich nicht: Die vier Familien pruefen repoweite **Form**; "dieses Skript installiert
keinen Hook" ist eine **Verhaltens**aussage ueber eine Datei und steht als Totalverbot in deren
eigenem Test (`test_check_sh.py`).

`scripts/format.sh` ist ein Handgriff, kein Automatismus. Der Grund steht in ADR 0080
Abschnitt 12: Ein Hook, der beim Commit still Dateien umschreibt, veraendert einen Stand, den der
Aufrufer gerade geprueft hat - bei einem Agenten-Lauf heisst das, dass der committete Inhalt nicht
mehr der ist, gegen den die Tests liefen. Die **Abwesenheit** einer solchen Datei ist die einzige
Zusage dieser Story, die von einem Lauf, der sie bricht, nicht bemerkt wuerde. Ein Test ist hier
keine Zugabe, sondern die einzige wirksame Form.

**Der naheliegende Entwurf scheitert, und das ist der tragende Punkt.** Ein Volltextscan nach
`husky`/`lefthook`/`pre-commit`/`simple-git-hooks` ist am eigenen Bestand sofort rot: Genau diese
Woerter stehen legitim in Spec 0400, in ADR 0080 und im Testkonzept. Eine `specs/`-Ausnahme naehme
ausgerechnet den Ort aus, an dem spaeter jemand eine Hook-Datei ablegen koennte. Geprueft werden
deshalb **Pfade, Dateinamen und strukturierte Konfigurationsschluessel** - Form statt Text. Nur
Familie 4 ist ein Textscan, und sie zielt nicht auf den Begriff, sondern auf die **scharf
schaltende Form** (siehe dort).

**Suchraum:** `git ls-files -z` ueber das ganze Repository, duenner Leser nach dem Vorbild von
`verwaltete_dateien()` in `test_board_referenzfreiheit.py` - **nie `rglob`**. Gemessen am Bestand
(2026-09-11): `rglob` saehe aus dem Haupt-Checkout heraus ein Vielfaches, weil verbundene
Arbeitsbaeume unter `.claude/worktrees/` und nicht verwaltete Arbeitskopien hineinfallen; der Test
waere dann rot aus einem Grund, der mit seinem Gegenstand nichts zu tun hat - und in CI (frischer
Klon) fiele das nie auf. Zweiter Leser fuer die strukturierten Dateien ueber `json` und `tomllib`
(Stdlib in 3.12, keine neue Abhaengigkeit - konsistent mit dem Verzicht auf PyYAML in den
Nachbartests).

**Messwerte am Bestand (2026-09-11), zum Nachrechnen statt zum Glauben:**

* 669 verwaltete Pfade.
* Familie 2 (Git-Hook-Namen): **0 Treffer** ueber alle 669 Pfade - keine Ausnahme noetig.
* Familie 4 (scharf schaltende `core.hooksPath`-Form): **0 Treffer** ausserhalb der Ausnahmen.
  Der blosse Begriff `core.hooksPath` kommt dagegen in **7** verwalteten Dateien vor, zwei davon
  ausserhalb von `specs/` (`scripts/merge-main-into-branch.sh` und
  `scripts/tests/test_main_abgleich_verdrahtung.py`) - beide rein defensiv, sie beschreiben die
  Bedrohung, statt einen Hook zu setzen. Siehe Familie 4.

**Mutationsprobe, verbindlich gefuehrt (2026-09-11).** Der triviale Rot-Lauf zu Beginn belegt hier
nichts - der Bestand ist sauber, der Test startet gruen. Nach Gruen wurde deshalb je Familie ein
echter Koeder im Arbeitsbaum angelegt, rot gesehen und zurueckgenommen: `.husky/pre-commit`;
`tools/git/pre-commit`; `"prepare": "husky"` in `frontend/package.json`; eine
`scripts/setup-hooks.sh` mit `git config core.hooksPath .githooks`. Wer diese Datei aendert,
wiederholt das - die parametrisierten Gegenproben unten laufen auf synthetischen Abbildern und
belegen die Musterlogik, nicht die Verdrahtung mit dem echten Repositorium.
"""

from __future__ import annotations

import json
import subprocess
import tomllib
from collections.abc import Mapping
from pathlib import Path

import pytest

REPO_WURZEL = Path(__file__).parents[2]

# Selbstschutz: eine kaputte Dateiaufzaehlung liesse jedes Totalverbot still gruen werden.
MINDESTZAHL_VERWALTETER_PFADE = 400

# --- Familie 1: verbotene Pfade und Dateinamen -------------------------------------------------

VERBOTENE_PRAEFIXE = (".husky/", ".githooks/", ".hooks/")

VERBOTENE_DATEINAMEN = frozenset(
    {
        ".pre-commit-config.yaml",
        ".pre-commit-config.yml",
        "lefthook.yml",
        "lefthook.yaml",
        "lefthook.toml",
        "lefthook.json",
        ".lefthook.yml",
        ".lefthook.yaml",
        ".lefthook.toml",
        ".lefthook.json",
        "lefthook-local.yml",
        "lefthook-local.yaml",
        "lefthook-local.toml",
        "lefthook-local.json",
        ".simple-git-hooks.json",
        "simple-git-hooks.json",
        "simple-git-hooks.js",
        "simple-git-hooks.cjs",
    }
)

# --- Familie 2: Git-Hook-Namen als geschlossene Menge -------------------------------------------

# Der Kern dieser Familie: `core.hooksPath` kann auf JEDES Verzeichnis zeigen, ein Pfadpraefix
# faengt das nicht. Die Hook-Namen sind aber eine dokumentierte, geschlossene Menge (githooks(5)),
# und ein Dateiname aus dieser Menge hat im Repositorium keinen anderen legitimen Grund.
GIT_HOOK_NAMEN = frozenset(
    {
        "applypatch-msg",
        "pre-applypatch",
        "post-applypatch",
        "pre-commit",
        "pre-merge-commit",
        "prepare-commit-msg",
        "commit-msg",
        "post-commit",
        "pre-rebase",
        "post-checkout",
        "post-merge",
        "pre-push",
        "pre-receive",
        # `update` steht bewusst mit drin: ein Fundstueck namens `update` ohne Endung ist ein
        # richtiger Alarm, kein Fehlalarm - es ist der Name eines serverseitigen Hooks.
        "update",
        "proc-receive",
        "post-receive",
        "post-update",
        "reference-transaction",
        "push-to-checkout",
        "pre-auto-gc",
        "post-rewrite",
        "sendemail-validate",
        "fsmonitor-watchman",
        "p4-changelist",
        "p4-prepare-changelist",
        "p4-post-changelist",
        "p4-pre-submit",
        "post-index-change",
    }
)

# --- Familie 3: strukturierte Konfigurationsschluessel ------------------------------------------

# (3a) Totalverbot statt Kontextanalyse ("prueft das Skript, ob es einen Hook installiert?") -
# dieselbe Begruendung wie beim Substring-Totalverbot in test_main_abgleich_verdrahtung.py: In
# einer Datei mit einem Zweck schlaegt die Totalaussage die Kontextanalyse. Kosten heute: null,
# keine verwaltete package.json fuehrt einen dieser Schluessel.
VERBOTENE_NPM_LEBENSZYKLEN = ("preinstall", "install", "postinstall", "prepare")

# (3b) faengt den Vektor VOR der Hook-Datei: Das Werkzeug kommt zuerst als Abhaengigkeit.
HOOK_WERKZEUGE = frozenset(
    {
        "husky",
        "lefthook",
        "simple-git-hooks",
        "pre-commit",
        "lint-staged",
        "pretty-quick",
        "@lefthook/cli",
        "yorkie",
    }
)

# (3c) Editor-/Agenten-Konfiguration mit Formatier-Ausloeser. Am Bestand ist KEINE dieser Dateien
# verwaltet; geprueft wird also nur, *falls* eine auftaucht. Das ist die Stelle mit dem
# Testkonzept-Vorbehalt "ein Muster ohne moegliche Gegenprobe wird nicht heimlich mitgefuehrt":
# Die Gegenprobe ist hier notgedrungen synthetisch, und genau das steht deshalb hier.
# `.claude/settings.local.json` ist nicht verwaltet und faellt ueber `git ls-files` korrekt heraus
# - das ist gewollt, eine lokale Einstellung wirkt nicht auf fremde Sessions.
VSCODE_EINSTELLUNGEN = ".vscode/settings.json"
VSCODE_AUSLOESER = ("editor.formatOnSave", "editor.codeActionsOnSave")
CLAUDE_EINSTELLUNGEN = ".claude/settings.json"

# Die vier Konfigurationspfade, gegen die Familie 3 am echten Bestand tatsaechlich etwas prueft.
BEKANNTE_KONFIGURATIONEN = (
    "frontend/package.json",
    "e2e/package.json",
    "backend/pyproject.toml",
    "scripts/pyproject.toml",
)

# --- Familie 4: der eine Textscan --------------------------------------------------------------

# Gesucht wird NICHT der Begriff, sondern die scharf schaltende FORM. Das ist dieselbe Regel wie
# oben, eine Ebene tiefer angewandt: Ist der verbotene Begriff *als Begriff* legitim, ist das
# Verbot kein Wortverbot. Gemessen am Bestand nennen zwei Dateien ausserhalb von `specs/` den
# Bezeichner rein defensiv - scripts/merge-main-into-branch.sh erklaert in einem Kommentar, warum
# es GIT_CONFIG_COUNT aus der Umgebung entfernt, und test_main_abgleich_verdrahtung.py prueft
# genau das. Beide beschreiben die Bedrohung, statt einen Hook zu setzen.
#
# Eine Pfad-Ausnahme fuer diese zwei waere die schlechtere Loesung: Sie blendete ausgerechnet die
# Datei, die Git-Umgebungsvariablen anfasst, fuer diese Pruefung vollstaendig aus. Stattdessen
# verlangt das Muster, dass dem Bezeichner ein WERT zugewiesen wird - das ist der Unterschied
# zwischen "man koennte core.hooksPath unterschieben" und "hier wird core.hooksPath gesetzt".
# Erfasst werden beide realistischen Formen: der Einrichtungsbefehl (`git config core.hooksPath
# .githooks`) und die Zuweisung in git-config-Syntax (`hooksPath = .githooks` unter `[core]` bzw.
# `core.hooksPath=...`).
#
# **Die Wege sind ERHOBEN, nicht eingefallen** (Copilot-Finding zu PR #409). Der erste Entwurf
# deckte zwei Formen ab, weil mir zwei eingefallen waren; eine dritte - die Umgebungsvariablen-
# Form - lag offen im Repository (`scripts/merge-main-into-branch.sh` macht
# `unset GIT_CONFIG_COUNT`) und wurde trotzdem uebersehen. Deshalb wurde die Frage danach in
# einem Wegwerf-Repositorium ausgemessen statt beantwortet: Jeder Weg wurde real gefahren, bis
# ein Hook nachweislich lief. Ergebnis (2026-09-11, git aus dem Systempfad) - ALLE SECHS
# schalten einen Hook scharf:
#
#   A  git config core.hooksPath <dir>                      -> Alternative 3
#   B  [core] + hooksPath = <dir> in einer Konfigdatei      -> Alternative 1
#   C  GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.hooksPath   -> Alternative 2  (fehlte!)
#      GIT_CONFIG_VALUE_0=<dir>
#   D  git -c core.hooksPath=<dir> <befehl>                 -> Alternative 1
#   E  GIT_CONFIG_GLOBAL=<datei> mit [core] hooksPath       -> siehe unten
#   F  Schreibzugriff nach .git/hooks/<name>                -> Alternative 4  (fehlte!)
#
# Die vier Alternativen:
#
#   1. `hooksPath` unmittelbar gefolgt von einer ZUWEISUNG. Deckt `core.hooksPath=<dir>`,
#      `git -c core.hooksPath=<dir>` und die Konfigdatei-Syntax ab, bei der `[core]` und
#      `hooksPath = <dir>` auf VERSCHIEDENEN Zeilen stehen - ein Muster, das `core\.hooksPath` am
#      Stueck verlangt, findet diese Form nicht.
#   2. Der Bezeichner als WERT einer Zuweisung. Das ist die uebersehene Form C: In
#      `GIT_CONFIG_KEY_0=core.hooksPath` steht er rechts vom Gleichheitszeichen, Alternative 1
#      greift dort also prinzipiell nicht.
#   3. Der Bezeichner als Argument von `git config` (Flags dazwischen erlaubt).
#   4. Ein Pfad nach `.git/hooks/`. Form F braucht `core.hooksPath` ueberhaupt nicht - sie legt
#      die Hook-Datei direkt an der Vorgabestelle ab. Am Bestand gemessen: 0 Treffer, keine
#      Ausnahme noetig.
#
# **Form E braucht bewusst KEIN eigenes Muster, und das ist ein Argument, kein Versehen.** Das
# Scharfschalten passiert dort nicht in der Zeile mit `GIT_CONFIG_GLOBAL=`, sondern in der Datei,
# auf die sie zeigt - und die traegt `[core]`/`hooksPath = <dir>`, faellt also unter
# Alternative 1, sobald sie verwaltet ist. Ist sie nicht verwaltet, liegt sie ausserhalb dessen,
# was K8 zusichert ("keine EINGECHECKTE Datei loest aus"). Ein Muster auf `GIT_CONFIG_GLOBAL=`
# waere zudem ein Fehlalarm auf `test_merge_main_into_branch.py`, das die Variable zur
# Test-Isolation auf `/dev/null` setzt - defensiv, nicht scharf schaltend.
#
# Ausdruecklich NICHT "Bezeichner gefolgt von irgendeinem Wort": Ein frueherer Entwurf verlangte
# `core\.hooksPath\s+\S` und meldete damit die deutsche Prosa "laesst sich core.hooksPath
# unterschieben" als Befund - ein Fehlalarm auf genau der defensiven Erwaehnung, um derentwillen
# das Muster ueberhaupt geschaerft wurde. Beide Fehlalarm-Richtungen stehen unten als Gegenprobe.
#
# **Bekannte Restschwaeche, benannt statt verschwiegen:** Ein Schreibzugriff, der das
# Hook-Verzeichnis nicht literal nennt, sondern ausrechnet
# (`cp x "$(git rev-parse --git-path hooks)/pre-commit"`), faellt durch alle vier Alternativen.
# Verfolgt wird das nicht - der Bedrohungsraum dieser Story ist die unabsichtliche Einfuehrung,
# nicht die Verschleierung. Als zweite Reihe greift dort Familie 2: Die Quelldatei eines Hooks
# traegt praktisch immer dessen Namen.
_HOOKSPATH_SCHARF = (
    rb"hooksPath\s*[=:]\s*\S"  # 1: core.hooksPath=<wert>, hooksPath = <wert> unter [core]
    rb"|=\s*[\"']?core\.hooksPath\b"  # 2: GIT_CONFIG_KEY_n=core.hooksPath
    rb"|git\s+config\b[^\n]*?\bcore\.hooksPath\b"  # 3: git config [--flags] core.hooksPath <wert>
    rb"|\.git/hooks/\S"  # 4: Schreibzugriff an die Vorgabestelle
)

# `CHANGELOG.md` und `specs/` duerfen den Einrichtungsbefehl woertlich zitieren - Spec 0400 tut
# das selbst, um zu erklaeren, wogegen dieser Test antritt. Die Testdatei selbst traegt die
# Koederzeichenketten und faellt aus demselben Grund heraus.
FAMILIE4_AUSNAHMEN = (
    "CHANGELOG.md",
    "specs/",
    "scripts/tests/test_keine_automatische_formatierung.py",
)


# --- Leser -------------------------------------------------------------------------------------


def verwaltete_pfade(wurzel: Path = REPO_WURZEL) -> list[str]:
    """Duenner Leser: die von Git verwalteten Pfade, nullbyte-getrennt (Leerzeichen im Namen)."""
    ergebnis = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=wurzel,
        capture_output=True,
        check=True,
    )
    return [pfad.decode("utf-8") for pfad in ergebnis.stdout.split(b"\0") if pfad]


def abbild_des_repos(wurzel: Path = REPO_WURZEL) -> dict[str, bytes]:
    """Pfad -> Inhalt als BYTES: Der Suchraum enthaelt Binaerdateien (Modelle, Bilder)."""
    abbild: dict[str, bytes] = {}
    for relativ in verwaltete_pfade(wurzel):
        pfad = wurzel / relativ
        if pfad.is_file():
            abbild[relativ] = pfad.read_bytes()
    return abbild


def strukturierte_konfiguration(wurzel: Path = REPO_WURZEL) -> dict[str, dict[str, object]]:
    """Pfad -> geparster Inhalt fuer jede verwaltete package.json/pyproject.toml/Editor-Konfig.

    Eine unparsbare Datei ist ein Fehlerfall mit eigener Meldung, kein stilles Ueberspringen -
    sonst prueft Familie 3 nichts und meldet trotzdem "sauber".
    """
    interessant = {"package.json", "pyproject.toml"}
    konfiguration: dict[str, dict[str, object]] = {}
    for relativ in verwaltete_pfade(wurzel):
        name = Path(relativ).name
        if name not in interessant and relativ not in (VSCODE_EINSTELLUNGEN, CLAUDE_EINSTELLUNGEN):
            continue
        pfad = wurzel / relativ
        if not pfad.is_file():
            continue
        roh = pfad.read_text(encoding="utf-8")
        try:
            konfiguration[relativ] = (
                tomllib.loads(roh) if name.endswith(".toml") else json.loads(roh)
            )
        except (json.JSONDecodeError, tomllib.TOMLDecodeError) as fehler:
            raise ValueError(f"{relativ} ist nicht parsbar: {fehler}") from fehler
    return konfiguration


# --- Die vier Musterfamilien als reine Funktionen ----------------------------------------------


def _pruefe_nicht_leer(menge: object, was: str) -> None:
    if not menge:
        raise ValueError(
            f"0 {was} im Suchraum: Damit ist die Zusicherung ungeprueft. Entweder lief die "
            "Aufzaehlung im falschen Arbeitsverzeichnis, oder sie ist kaputt - ein leerer "
            "Suchraum darf nie als 'nichts gefunden' durchgehen."
        )


def familie1_befunde(pfade: list[str]) -> list[str]:
    """Verbotene Pfadpraefixe und Dateinamen."""
    _pruefe_nicht_leer(pfade, "Pfade")
    befunde = []
    for pfad in sorted(pfade):
        if any(pfad.startswith(praefix) for praefix in VERBOTENE_PRAEFIXE):
            befunde.append(f"{pfad}: liegt unter einem Hook-Verzeichnis")
        if Path(pfad).name in VERBOTENE_DATEINAMEN:
            befunde.append(f"{pfad}: Konfigurationsdatei eines Hook-Werkzeugs")
    return befunde


def familie2_befunde(pfade: list[str]) -> list[str]:
    """Git-Hook-Namen an beliebiger Stelle - `stem` UND `name`, damit `pre-commit.sh` mitfaellt."""
    _pruefe_nicht_leer(pfade, "Pfade")
    return [
        f"{pfad}: traegt den Namen eines Git-Hooks"
        for pfad in sorted(pfade)
        if Path(pfad).stem in GIT_HOOK_NAMEN or Path(pfad).name in GIT_HOOK_NAMEN
    ]


def familie3_befunde(konfiguration: Mapping[str, dict[str, object]]) -> list[str]:
    """Strukturierte Konfigurationsschluessel, als Totalverbot."""
    _pruefe_nicht_leer(konfiguration, "Konfigurationsdateien")
    befunde: list[str] = []
    for pfad, daten in sorted(konfiguration.items()):
        name = Path(pfad).name

        if name == "package.json":
            skripte = daten.get("scripts") or {}
            if isinstance(skripte, dict):
                for schluessel in VERBOTENE_NPM_LEBENSZYKLEN:
                    if schluessel in skripte:
                        befunde.append(f"{pfad}: npm-Lebenszyklus-Skript `{schluessel}`")
            for block in ("dependencies", "devDependencies"):
                abhaengigkeiten = daten.get(block) or {}
                if isinstance(abhaengigkeiten, dict):
                    for werkzeug in sorted(HOOK_WERKZEUGE & set(abhaengigkeiten)):
                        befunde.append(f"{pfad}: Hook-Werkzeug `{werkzeug}` unter {block}")

        if name == "pyproject.toml":
            projekt = daten.get("project") or {}
            if isinstance(projekt, dict):
                gruppen: list[object] = [projekt.get("dependencies") or []]
                optionale = projekt.get("optional-dependencies") or {}
                if isinstance(optionale, dict):
                    gruppen.extend(optionale.values())
                for gruppe in gruppen:
                    if not isinstance(gruppe, list):
                        continue
                    for eintrag in gruppe:
                        if not isinstance(eintrag, str):
                            continue
                        paket = eintrag.split(";")[0].strip()
                        for zeichen in "=<>~!@[ ":
                            paket = paket.split(zeichen)[0]
                        if paket in HOOK_WERKZEUGE:
                            befunde.append(f"{pfad}: Hook-Werkzeug `{paket}` als Abhaengigkeit")

        if pfad == VSCODE_EINSTELLUNGEN:
            for schluessel in VSCODE_AUSLOESER:
                if schluessel in daten:
                    befunde.append(f"{pfad}: Formatier-Ausloeser `{schluessel}`")

        if pfad == CLAUDE_EINSTELLUNGEN and "hooks" in daten:
            befunde.append(f"{pfad}: Schluessel `hooks`")

    return befunde


def familie4_befunde(abbild: Mapping[str, bytes]) -> list[str]:
    """Der eine Textscan: die scharf schaltende `core.hooksPath`-Form, nicht der Begriff."""
    import re

    _pruefe_nicht_leer(abbild, "Dateien")
    muster = re.compile(_HOOKSPATH_SCHARF)
    befunde = []
    for pfad, inhalt in sorted(abbild.items()):
        if any(pfad == a or pfad.startswith(a) for a in FAMILIE4_AUSNAHMEN):
            continue
        treffer = muster.search(inhalt)
        if treffer is not None:
            zeile = inhalt[: treffer.start()].count(b"\n") + 1
            befunde.append(f"{pfad}:{zeile}: setzt core.hooksPath scharf")
    return befunde


# --- 1. Der echte Bestand ----------------------------------------------------------------------


def test_kein_hook_verzeichnis_und_keine_hook_werkzeug_konfiguration() -> None:
    befunde = familie1_befunde(verwaltete_pfade())
    assert not befunde, (
        "Eingecheckte Hook-Konfiguration gefunden:\n  " + "\n  ".join(befunde) + "\n"
        "Formatierung wird in diesem Repository von Hand angestossen (scripts/format.sh) und in "
        "CI geprueft - nie beim Commit. Ein Hook, der still schreibt, veraendert einen Stand, den "
        "der Aufrufer gerade geprueft hat."
    )


def test_keine_datei_traegt_den_namen_eines_git_hooks() -> None:
    befunde = familie2_befunde(verwaltete_pfade())
    assert not befunde, (
        "Datei mit Git-Hook-Namen gefunden:\n  " + "\n  ".join(befunde) + "\n"
        "core.hooksPath kann auf jedes Verzeichnis zeigen - ein Pfadpraefix faengt das nicht, "
        "der Dateiname schon."
    )


def test_keine_konfiguration_installiert_oder_startet_einen_hook() -> None:
    befunde = familie3_befunde(strukturierte_konfiguration())
    assert not befunde, (
        "Konfiguration mit Hook-/Formatier-Ausloeser gefunden:\n  " + "\n  ".join(befunde) + "\n"
        "Das Werkzeug kommt zuerst als Abhaengigkeit und erst danach als Hook-Datei - diese "
        "Familie faengt den Vektor davor."
    )


def test_keine_datei_schaltet_core_hookspath_scharf() -> None:
    befunde = familie4_befunde(abbild_des_repos())
    assert not befunde, (
        "core.hooksPath wird gesetzt:\n  " + "\n  ".join(befunde) + "\n"
        "Ein eingecheckter Einrichtungsbefehl ist der einzige Weg, wie eine verwaltete Datei "
        "einen Hook scharf schaltet, ohne dass die Hook-Datei selbst verwaltet ist."
    )


# --- 2. Selbstschutz ---------------------------------------------------------------------------


def test_der_suchraum_hat_eine_plausible_groesse() -> None:
    """Faengt den Totalausfall der Aufzaehlung, nicht jede geloeschte Datei."""
    pfade = verwaltete_pfade()
    assert len(pfade) >= MINDESTZAHL_VERWALTETER_PFADE, (
        f"Nur {len(pfade)} verwaltete Pfade (Ist am 2026-09-11: 669). Unterhalb von "
        f"{MINDESTZAHL_VERWALTETER_PFADE} ist nicht mehr plausibel, dass die Aufzaehlung "
        "funktioniert - und ein zu kleiner Suchraum laesst jedes Totalverbot still gruen werden."
    )


def test_die_gepruefte_konfiguration_liegt_im_suchraum() -> None:
    """Familie 3 prueft sonst nichts und meldet trotzdem 'sauber'."""
    konfiguration = strukturierte_konfiguration()
    fehlend = [pfad for pfad in BEKANNTE_KONFIGURATIONEN if pfad not in konfiguration]
    assert not fehlend, (
        f"Diese Konfigurationsdateien fehlen im Abbild: {fehlend}. Familie 3 prueft dann gegen "
        "nichts. Wurden sie umbenannt, gehoert die Liste nachgezogen."
    )


def test_die_konfiguration_wurde_wirklich_geparst() -> None:
    """Ein Parser, der still `{}` liefert, macht jedes Totalverbot vakuum-gruen."""
    konfiguration = strukturierte_konfiguration()
    frontend = konfiguration["frontend/package.json"]
    skripte = frontend.get("scripts")
    assert isinstance(skripte, dict) and "build" in skripte, (
        "frontend/package.json hat keinen nicht-leeren scripts-Block mit `build`. Entweder ist "
        f"die Datei umgebaut, oder der Parser liefert Leeres (gelesen: {skripte!r}) - im zweiten "
        "Fall ist Familie 3 wertlos, ohne es zu melden."
    )


@pytest.mark.parametrize(
    ("funktion", "leeres"),
    [
        (familie1_befunde, []),
        (familie2_befunde, []),
        (familie3_befunde, {}),
        (familie4_befunde, {}),
    ],
)
def test_ein_leerer_suchraum_scheitert_laut_statt_still(funktion: object, leeres: object) -> None:
    with pytest.raises(ValueError, match=r"^0 "):
        funktion(leeres)  # type: ignore[operator]


# --- 3. Gegenprobe je Musterfamilie ------------------------------------------------------------

_UNVERFAENGLICHE_PFADE = [
    ".github/workflows/ci.yml",
    ".github/pull_request_template.md",
    "scripts/format.sh",
    "frontend/package.json",
    "backend/src/photosort/main.py",
]


@pytest.mark.parametrize(
    ("koeder", "warum"),
    [
        (".husky/pre-commit", "husky-Hook-Verzeichnis"),
        (".githooks/pre-commit", "eigenes Hook-Verzeichnis"),
        (".pre-commit-config.yaml", "pre-commit-Konfiguration"),
        ("lefthook.yml", "lefthook-Konfiguration"),
        ("frontend/.simple-git-hooks.json", "simple-git-hooks-Konfiguration"),
    ],
)
def test_familie1_faerbt_bei_einem_koeder_rot(koeder: str, warum: str) -> None:
    assert familie1_befunde([*_UNVERFAENGLICHE_PFADE, koeder]), warum


@pytest.mark.parametrize(
    ("koeder", "warum"),
    [
        ("tools/git/pre-commit", "Hook ausserhalb jedes bekannten Verzeichnisses"),
        ("tools/git/pre-commit.sh", "stem statt name - deshalb wird beides verglichen"),
        ("irgendwo/commit-msg", "anderer Hook-Name derselben Menge"),
        ("build/update", "serverseitiger Hook-Name ohne Endung"),
    ],
)
def test_familie2_faerbt_bei_einem_koeder_rot(koeder: str, warum: str) -> None:
    assert familie2_befunde([*_UNVERFAENGLICHE_PFADE, koeder]), warum


@pytest.mark.parametrize(
    ("pfad", "inhalt", "warum"),
    [
        ("frontend/package.json", {"scripts": {"prepare": "husky"}}, "prepare installiert Hooks"),
        ("frontend/package.json", {"scripts": {"postinstall": "lefthook install"}}, "postinstall"),
        ("e2e/package.json", {"devDependencies": {"husky": "^9"}}, "Werkzeug als Abhaengigkeit"),
        ("e2e/package.json", {"dependencies": {"lint-staged": "^15"}}, "Werkzeug als Laufzeitdep"),
        (
            "backend/pyproject.toml",
            {"project": {"optional-dependencies": {"dev": ["pre-commit>=3"]}}},
            "Hook-Werkzeug im Python-Baum",
        ),
        (
            "backend/pyproject.toml",
            {"project": {"dependencies": ["pre-commit"]}},
            "ohne Versionsangabe, deshalb wird der Paketname freigeschnitten",
        ),
        (
            VSCODE_EINSTELLUNGEN,
            {"editor.formatOnSave": True},
            "Editor formatiert beim Speichern",
        ),
        (
            VSCODE_EINSTELLUNGEN,
            {"editor.codeActionsOnSave": {"source.fixAll": "explicit"}},
            "Editor-Aktion beim Speichern",
        ),
        (CLAUDE_EINSTELLUNGEN, {"hooks": {"PostToolUse": []}}, "Agenten-Hook"),
    ],
)
def test_familie3_faerbt_bei_einem_koeder_rot(
    pfad: str, inhalt: dict[str, object], warum: str
) -> None:
    gesund = {"frontend/package.json": {"scripts": {"build": "vite build"}}}
    assert familie3_befunde({**gesund, pfad: inhalt}), warum


@pytest.mark.parametrize(
    ("inhalt", "warum"),
    [
        (b"git config core.hooksPath .githooks\n", "Weg A: Einrichtungsbefehl"),
        (b'git config --local core.hooksPath "tools/git"\n', "Weg A mit Flag und Quotes"),
        (b"[core]\n  hooksPath = .githooks\n", "Weg B: Konfigdatei, Schluessel auf eigener Zeile"),
        (
            b"GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.hooksPath GIT_CONFIG_VALUE_0=hooks-probe\n",
            "Weg C: Umgebungsvariablen-Form - der Bezeichner steht RECHTS vom "
            "Gleichheitszeichen, und genau daran ist der erste Entwurf vorbeigelaufen",
        ),
        (
            b'GIT_CONFIG_KEY_0="core.hooksPath"\n',
            "Weg C mit Anfuehrungszeichen",
        ),
        (b"git -c core.hooksPath=.githooks commit\n", "Weg D: -c am Aufruf"),
        (b"core.hooksPath=.githooks\n", "Zuweisung ohne Leerzeichen"),
        (
            b"cp tools/formatier-hook .git/hooks/pre-commit\n",
            "Weg F: braucht core.hooksPath gar nicht, legt den Hook an die Vorgabestelle",
        ),
        (
            b'install -m 755 x "$REPO/.git/hooks/post-merge"\n',
            "Weg F mit anderem Hook-Namen",
        ),
    ],
)
def test_familie4_faerbt_bei_einem_koeder_rot(inhalt: bytes, warum: str) -> None:
    assert familie4_befunde({"scripts/setup-hooks.sh": inhalt}), warum


# --- 4. Die Gegenrichtung ----------------------------------------------------------------------
#
# Ohne diese zweite Richtung waere ein Muster, das ALLES trifft, von einem korrekten nicht zu
# unterscheiden - und der Test bestuende aus vier gruenen Zusicherungen ohne Aussage.


def test_der_bestand_wird_nicht_faelschlich_gemeldet() -> None:
    """Unverfaengliche Nachbardateien loesen keine der vier Familien aus."""
    assert familie1_befunde(_UNVERFAENGLICHE_PFADE) == []
    assert familie2_befunde(_UNVERFAENGLICHE_PFADE) == []
    assert familie3_befunde({"frontend/package.json": {"scripts": {"build": "vite build"}}}) == []
    assert familie4_befunde({".github/workflows/ci.yml": b"- run: ruff format --check .\n"}) == []


@pytest.mark.parametrize(
    ("inhalt", "warum"),
    [
        (
            b"# ueber GIT_CONFIG_COUNT laesst sich core.hooksPath unterschieben.\n",
            "die defensive Erwaehnung in scripts/merge-main-into-branch.sh",
        ),
        (
            b'"Branch eines anderen Repositoriums, ueber GIT_CONFIG_COUNT laesst sich '
            b'core.hooksPath "\n"unterschieben."\n',
            "dieselbe Erwaehnung in test_main_abgleich_verdrahtung.py, ueber zwei Zeilen",
        ),
        (
            b"unset GIT_DIR GIT_WORK_TREE GIT_COMMON_DIR GIT_INDEX_FILE GIT_OBJECT_DIRECTORY \\\n"
            b"    GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_CONFIG_COUNT\n",
            "das `unset` selbst - es ENTFERNT den Weg C, es oeffnet ihn nicht; ein Muster auf "
            "dem blossen Variablennamen machte ausgerechnet die Gegenmassnahme zum Befund",
        ),
        (
            b'"GIT_CONFIG_GLOBAL": "/dev/null",\n"GIT_CONFIG_SYSTEM": "/dev/null",\n',
            "Test-Isolation in test_merge_main_into_branch.py: schneidet fremde Konfiguration "
            "ab, statt eine unterzuschieben - Weg E wird bewusst ueber die Zieldatei erfasst",
        ),
    ],
)
def test_familie4_meldet_die_blosse_erwaehnung_nicht(inhalt: bytes, warum: str) -> None:
    """Das Muster zielt auf die scharf schaltende Form, nicht auf den Bezeichner.

    Beide Zeichenketten stehen so im echten Bestand. Eine Pfad-Ausnahme fuer diese zwei Dateien
    waere die schlechtere Loesung gewesen: Sie blendete ausgerechnet das Skript, das
    Git-Umgebungsvariablen anfasst, fuer diese Pruefung vollstaendig aus.
    """
    assert familie4_befunde({"scripts/merge-main-into-branch.sh": inhalt}) == [], warum
