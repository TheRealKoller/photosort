r"""Waechter ueber die vier Versions-Fixierungen der Formatierer (K6, Spec 0400).

Dieselbe Zahl steht an vier Stellen: `ruff` in `backend/pyproject.toml` und `scripts/pyproject.toml`,
`prettier` in `frontend/package.json` und `e2e/package.json` (je plus Lockfile). Das ist der Preis
dafuer, dass jeder Baum fuer sich installierbar bleibt - `backend/` und `scripts/` sind getrennte
Python-Projekte mit getrennten CI-Jobs, `frontend/` und `e2e/` getrennte npm-Projekte mit
getrennten Lockfiles. Die Duplikation wird nicht weggeredet, sondern hier mechanisch gehalten
(ADR 0080 Abschnitt 8).

**Warum ueberhaupt exakt fixiert:** Am Bestand gemessen (ADR 0080, Kontext) liefen unter derselben
Angabe `ruff>=0.7` drei verschiedene Versionen in drei lokalen Umgebungen desselben Repositoriums
(`0.16.1`, `0.16.2`, `0.16.4`). `ruff` darf den Stable Style bei Minor-Bumps aendern, und Prettier
sagt ueber sich selbst, dass sogar ein Patch-Release die Ausgabe veraendern kann. Eine offene
untere Schranke fixiert nichts.

**Die eigentliche Substanz dieses Moduls sind die Negativtabellen, nicht die Pruefung am
Bestand.** Der Bestand ist gruen und belegt fuer sich genommen nichts: Er waere auch gruen, wenn
das Exaktheitsmuster jede Zeichenkette akzeptierte. Erst die parametrisierten Gegenproben zeigen,
dass das Muster etwas abweist - und sie sind der Grund, warum Exaktheit **positiv je Oekosystem**
formuliert ist statt als Zeichen-Blacklist. Die naheliegende Fassung "enthaelt kein `>=`, `~`,
`^`, `*`" hat ein Loch, durch das **beide** realistischen Fehlerformen passen: der nackte Eintrag
`ruff` ohne jeden Operator (PEP 508: "irgendeine Version") und das npm-`"latest"`. Beides ist das
Gegenteil einer Fixierung und wuerde von einer Blacklist durchgewunken.

**Strukturiert gelesen, nie per Regex ueber den Rohtext.** Beide `pyproject.toml` tragen
auskommentierte Zeilen; ein `grep` nach `ruff` zaehlte sie mit. Gelesen wird deshalb ueber
`tomllib` bzw. `json` - Stdlib in 3.12, keine neue Abhaengigkeit.
"""

from __future__ import annotations

import json
import re
import subprocess
import tomllib
from pathlib import Path

import pytest

REPO_WURZEL = Path(__file__).parents[2]

PYPROJEKTE = ("backend/pyproject.toml", "scripts/pyproject.toml")
NPM_PAKETE = ("frontend/package.json", "e2e/package.json")
LOCKFILES = ("frontend/package-lock.json", "e2e/package-lock.json")
PRETTIERRC = ".prettierrc.json"
PRETTIERIGNORE = ".prettierignore"

# (c) Exaktheit POSITIV je Oekosystem. Was diese beiden Muster durchlassen, ist genau eine
# Version und keine Menge von Versionen.
_PEP508_EXAKT = re.compile(r"^ruff\s*==\s*\d+\.\d+(\.\d+)?$")
_NPM_EXAKT = re.compile(r"^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$")

# (e) Dreizehn Quellen koennen /.prettierrc.json still ueberschatten. Der `"prettier"`-Schluessel
# in einer package.json ist nur eine davon; gemessen meldet `--find-config-path` dann
# `package.json` statt `../.prettierrc.json`, ohne Warnung und ohne Fehler.
PRETTIER_KONFIGURATIONSQUELLEN = (
    ".prettierrc",
    ".prettierrc.json",
    ".prettierrc.json5",
    ".prettierrc.yml",
    ".prettierrc.yaml",
    ".prettierrc.toml",
    ".prettierrc.js",
    ".prettierrc.cjs",
    ".prettierrc.mjs",
    "prettier.config.js",
    "prettier.config.cjs",
    "prettier.config.mjs",
    "prettier.config.ts",
)

# Die ruff-Entsprechung derselben Fehlerklasse: eine ruff.toml haette gegenueber dem
# [tool.ruff]-Abschnitt der pyproject.toml im selben Verzeichnis lautlos Vorrang.
RUFF_UEBERSCHATTENDE_DATEIEN = ("ruff.toml", ".ruff.toml")

NPM_SKRIPTE = ("format", "format:check")
IGNORE_FLAG = "--ignore-path ../.prettierignore"


# --- Leser -------------------------------------------------------------------------------------


def verwaltete_pfade(wurzel: Path = REPO_WURZEL) -> list[str]:
    ergebnis = subprocess.run(
        ["git", "ls-files", "-z"], cwd=wurzel, capture_output=True, check=True
    )
    return [pfad.decode("utf-8") for pfad in ergebnis.stdout.split(b"\0") if pfad]


def _lies(relativ: str) -> str:
    """Selbstschutz: eine fehlende Datei scheitert mit dem Pfad in der Meldung, nicht per KeyError."""
    pfad = REPO_WURZEL / relativ
    if not pfad.is_file():
        raise ValueError(
            f"{relativ} fehlt. Ohne diese Datei prueft der Waechter nichts und meldete trotzdem "
            "'sauber' - wurde sie umbenannt, gehoert die Konstante in diesem Modul nachgezogen."
        )
    return pfad.read_text(encoding="utf-8")


def pyproject_daten(relativ: str) -> dict[str, object]:
    return tomllib.loads(_lies(relativ))


def json_daten(relativ: str) -> dict[str, object]:
    return json.loads(_lies(relativ))


def ruff_angabe(relativ: str) -> str:
    """Der `dev`-Eintrag, dessen Paketname `ruff` lautet - strukturiert, nicht per Regex."""
    daten = pyproject_daten(relativ)
    projekt = daten.get("project")
    assert isinstance(projekt, dict), relativ
    optionale = projekt.get("optional-dependencies")
    assert isinstance(optionale, dict), relativ
    dev = optionale.get("dev")
    assert isinstance(dev, list), relativ

    treffer = [eintrag for eintrag in dev if paketname(str(eintrag)) == "ruff"]
    if len(treffer) != 1:
        raise ValueError(
            f"{relativ}: {len(treffer)} ruff-Eintraege unter project.optional-dependencies.dev "
            f"({treffer}). Genau einer wird erwartet; bei mehreren ist nicht entscheidbar, "
            "welcher gilt."
        )
    return str(treffer[0]).strip()


def paketname(eintrag: str) -> str:
    """Alles vor dem ersten Zeichen aus `=<>~!` (PEP 508), Extras und Marker abgeschnitten."""
    kopf = eintrag.split(";")[0].strip()
    return re.split(r"[=<>~!\[ ]", kopf, maxsplit=1)[0].strip()


def prettier_angabe(relativ: str) -> str:
    daten = json_daten(relativ)
    dev = daten.get("devDependencies")
    if not isinstance(dev, dict) or "prettier" not in dev:
        raise ValueError(
            f"{relativ} nennt prettier nicht unter devDependencies. Ohne die Deklaration "
            "installiert `npm ci` den Formatierer in diesem Baum nicht."
        )
    return str(dev["prettier"]).strip()


def lockfile_aufloesung(relativ: str) -> str:
    """Was `npm ci` tatsaechlich installiert - die Deklaration allein ist nicht die Wahrheit."""
    daten = json_daten(relativ)
    pakete = daten.get("packages")
    if not isinstance(pakete, dict) or "node_modules/prettier" not in pakete:
        raise ValueError(
            f"{relativ} loest node_modules/prettier nicht auf. `npm ci` installiert, was im "
            "Lockfile steht - fehlt der Eintrag, ist die Deklaration folgenlos."
        )
    eintrag = pakete["node_modules/prettier"]
    assert isinstance(eintrag, dict), relativ
    return str(eintrag.get("version", "")).strip()


def npm_skript(relativ: str, name: str) -> str:
    daten = json_daten(relativ)
    skripte = daten.get("scripts")
    if not isinstance(skripte, dict) or name not in skripte:
        raise ValueError(f"{relativ} fuehrt kein npm-Skript `{name}`.")
    return str(skripte[name]).strip()


# --- (a)/(b) Dieselbe Version je Oekosystem ----------------------------------------------------


def test_beide_python_baeume_nennen_dieselbe_ruff_version() -> None:
    angaben = {relativ: ruff_angabe(relativ) for relativ in PYPROJEKTE}
    assert len(set(angaben.values())) == 1, (
        f"Die beiden Python-Baeume nennen verschiedene ruff-Versionen: {angaben}. Dann "
        "formatieren sie verschieden, und einer der beiden CI-Jobs wird rot - je nachdem, "
        "welcher Baum zuletzt formatiert wurde."
    )


def test_beide_npm_baeume_nennen_dieselbe_prettier_version() -> None:
    angaben = {relativ: prettier_angabe(relativ) for relativ in NPM_PAKETE}
    assert len(set(angaben.values())) == 1, (
        f"Die beiden npm-Baeume nennen verschiedene prettier-Versionen: {angaben}. Prettier sagt "
        "ueber sich selbst, dass schon ein Patch-Release die Ausgabe veraendern kann."
    )


# --- (c) Exaktheit, positiv je Oekosystem ------------------------------------------------------


def test_die_ruff_angaben_sind_exakt() -> None:
    for relativ in PYPROJEKTE:
        angabe = ruff_angabe(relativ)
        assert _PEP508_EXAKT.fullmatch(angabe), (
            f"{relativ} nennt {angabe!r} - keine exakte Angabe. Erwartet wird genau "
            "`ruff==X.Y[.Z]`: keine offene Schranke, kein Wildcard, kein zweiter Clause, kein "
            "nackter Paketname."
        )


def test_die_prettier_angaben_sind_exakt() -> None:
    for relativ in NPM_PAKETE:
        angabe = prettier_angabe(relativ)
        assert _NPM_EXAKT.fullmatch(angabe), (
            f"{relativ} nennt {angabe!r} - keine exakte Angabe. Erwartet wird genau `X.Y.Z`: "
            "kein Caret, keine Tilde, kein Bereich, kein `latest`, kein npm:-Alias."
        )


@pytest.mark.parametrize(
    "unzulaessig",
    [
        "ruff",  # nackt: PEP 508 heisst das "irgendeine Version" - eine Blacklist laesst es durch
        "ruff>=0.7",
        "ruff>0.16",
        "ruff~=0.16.4",
        "ruff==0.16.*",
        "ruff==0.16.4,<0.17",
        "ruff===0.16.4",
        "ruff!=0.16.3",
        "ruff @ git+https://example.invalid/ruff.git",
    ],
)
def test_eine_unscharfe_ruff_angabe_wird_abgewiesen(unzulaessig: str) -> None:
    """Die eigentliche Substanz von (c) - am gruenen Bestand ist nichts davon zu sehen."""
    assert not _PEP508_EXAKT.fullmatch(unzulaessig)


@pytest.mark.parametrize(
    "unzulaessig",
    [
        "^3.9.6",
        "~3.9.6",
        ">=3.9.6",
        "3.x",
        "3.9",
        "*",
        "latest",
        "npm:prettier@3.9.6",
        "3.9.6 || 4.0.0",
        "github:prettier/prettier",
        "",
    ],
)
def test_eine_unscharfe_prettier_angabe_wird_abgewiesen(unzulaessig: str) -> None:
    assert not _NPM_EXAKT.fullmatch(unzulaessig)


def test_die_muster_lassen_die_gueltige_form_durch() -> None:
    """Gegenrichtung: Ein Muster, das alles abweist, waere von einem korrekten nicht zu
    unterscheiden - beide machten die Negativtabellen oben gruen."""
    assert _PEP508_EXAKT.fullmatch("ruff==0.16.4")
    assert _PEP508_EXAKT.fullmatch("ruff == 0.16.4")
    assert _PEP508_EXAKT.fullmatch("ruff==1.0")
    assert _NPM_EXAKT.fullmatch("3.9.6")
    assert _NPM_EXAKT.fullmatch("3.9.6-rc.1")


# --- (d)/(e) Genau eine Konfigurationsquelle ---------------------------------------------------


def test_keine_package_json_traegt_einen_prettier_schluessel() -> None:
    """Suchraum ist JEDE verwaltete package.json, nicht die beiden bekannten.

    Ein kuenftiger dritter npm-Baum soll nicht dadurch durchrutschen, dass niemand an die Liste
    denkt.
    """
    betroffen = [
        pfad
        for pfad in verwaltete_pfade()
        if Path(pfad).name == "package.json" and "prettier" in json_daten(pfad)
    ]
    assert not betroffen, (
        f"Diese package.json tragen einen `prettier`-Schluessel: {betroffen}. Er ueberschattet "
        "/.prettierrc.json still - `--find-config-path` meldet dann package.json, ohne Warnung "
        "und ohne Fehler."
    )


def test_es_gibt_genau_eine_prettier_konfigurationsquelle_und_sie_liegt_in_der_wurzel() -> None:
    quellen = [
        pfad for pfad in verwaltete_pfade() if Path(pfad).name in PRETTIER_KONFIGURATIONSQUELLEN
    ]
    assert quellen == [PRETTIERRC], (
        f"Erwartet genau {PRETTIERRC} in der Wurzel, gefunden: {quellen}. Dreizehn Dateinamen "
        "koennen die Wurzel-Konfiguration ueberschatten; welcher gewinnt, sieht man dem Baum "
        "nicht an."
    )


def test_es_gibt_genau_eine_prettierignore_und_sie_liegt_in_der_wurzel() -> None:
    treffer = [pfad for pfad in verwaltete_pfade() if Path(pfad).name == ".prettierignore"]
    assert treffer == [PRETTIERIGNORE], (
        f"Erwartet genau {PRETTIERIGNORE} in der Wurzel, gefunden: {treffer}. Beide npm-Skripte "
        "zeigen per --ignore-path auf diese eine Datei."
    )


def test_keine_verwaltete_ruff_toml_ueberschattet_die_pyproject_konfiguration() -> None:
    treffer = [
        pfad for pfad in verwaltete_pfade() if Path(pfad).name in RUFF_UEBERSCHATTENDE_DATEIEN
    ]
    assert not treffer, (
        f"Gefunden: {treffer}. Eine ruff.toml hat gegenueber dem [tool.ruff]-Abschnitt der "
        "pyproject.toml im selben Verzeichnis lautlos Vorrang - die gepruefte Konfiguration "
        "waere dann nicht die wirksame."
    )


# --- (f) Die Lockfile-Aufloesung ---------------------------------------------------------------


def test_die_lockfiles_loesen_prettier_auf_die_deklarierte_version_auf() -> None:
    """`npm ci` installiert, was im Lockfile steht - nicht, was die package.json deklariert."""
    deklariert = prettier_angabe(NPM_PAKETE[0])
    aufgeloest = {relativ: lockfile_aufloesung(relativ) for relativ in LOCKFILES}
    abweichend = {p: v for p, v in aufgeloest.items() if v != deklariert}
    assert not abweichend, (
        f"Deklariert ist {deklariert!r}, die Lockfiles loesen auf: {abweichend}. Ohne diese "
        "Zusicherung prueft der Waechter eine Zahl, die nicht die installierte ist."
    )


# --- (g) Beide npm-Skripte wortgleich, mit Flag ------------------------------------------------


@pytest.mark.parametrize("name", NPM_SKRIPTE)
def test_beide_baeume_fuehren_das_skript_wortgleich(name: str) -> None:
    befehle = {relativ: npm_skript(relativ, name) for relativ in NPM_PAKETE}
    assert len(set(befehle.values())) == 1, (
        f"Das Skript `{name}` lautet in den beiden Baeumen verschieden: {befehle}. Lokaler "
        "Befehl und CI-Pruefung lesen dann verschiedene Geltungsbereiche."
    )


@pytest.mark.parametrize("name", NPM_SKRIPTE)
def test_beide_skripte_tragen_die_ignore_pfad_angabe(name: str) -> None:
    """Faellt das Flag in EINEM Baum weg, erfasst dieser Lauf ploetzlich die Markdown-Dateien."""
    for relativ in NPM_PAKETE:
        befehl = npm_skript(relativ, name)
        assert IGNORE_FLAG in befehl, (
            f"{relativ}, Skript `{name}`: {befehl!r} enthaelt {IGNORE_FLAG!r} nicht. Prettier "
            "sucht die Ignore-Datei nicht aufwaerts; ohne das Flag gilt in diesem Baum die "
            "Vorgabe, und der Lauf erfasst still Dateien, die ausgeschlossen sein sollen."
        )


# --- (h) Eine Zeilenbreite im ganzen Projekt ---------------------------------------------------


def _ruff_abschnitt(relativ: str, *schluessel: str) -> object:
    daten: object = pyproject_daten(relativ)
    for stufe in ("tool", "ruff", *schluessel):
        assert isinstance(daten, dict), f"{relativ}: {stufe} fehlt"
        daten = daten.get(stufe)
    return daten


def test_eine_zeilenbreite_im_ganzen_projekt() -> None:
    breiten = {PRETTIERRC: json_daten(PRETTIERRC).get("printWidth")}
    for relativ in PYPROJEKTE:
        breiten[relativ] = _ruff_abschnitt(relativ, "line-length")  # type: ignore[assignment]
    assert len(set(breiten.values())) == 1 and None not in breiten.values(), (
        f"Verschiedene Zeilenbreiten: {breiten}. printWidth und line-length sind bewusst "
        "dieselbe Zahl - zwei Breiten waeren eine Regel, die man nachschlagen muss."
    )


def test_beide_python_baeume_nehmen_markdown_gleich_aus() -> None:
    werte = {relativ: _ruff_abschnitt(relativ, "format", "exclude") for relativ in PYPROJEKTE}
    assert len(set(map(str, werte.values()))) == 1 and None not in werte.values(), (
        f"Die [tool.ruff.format] exclude-Werte unterscheiden sich: {werte}. Markdown ist in "
        "beiden Baeumen ausgenommen (K2) - oder in keinem."
    )


def test_beide_python_baeume_setzen_dieselbe_e501_grenze() -> None:
    werte = {
        relativ: _ruff_abschnitt(relativ, "lint", "pycodestyle", "max-line-length")
        for relativ in PYPROJEKTE
    }
    assert len(set(map(str, werte.values()))) == 1 and None not in werte.values(), (
        f"Die max-line-length-Werte unterscheiden sich: {werte}. Der Formatierer darf die "
        "Zielbreite ueberschreiten, wo er nicht umbrechen kann; die Grenze dafuer gilt in beiden "
        "Baeumen gleich."
    )


# --- Selbstschutz ------------------------------------------------------------------------------


def test_alle_vier_versionsangaben_sind_nicht_leer_und_stammen_aus_vier_dateien() -> None:
    """Der wahrscheinlichste Defekt dieses Moduls: ein Parser, der still `None` liefert.

    `None == None` besteht - und damit bestuenden (a), (b) und (f), ohne irgendetwas zu wissen.
    """
    quellen = {
        **{relativ: ruff_angabe(relativ) for relativ in PYPROJEKTE},
        **{relativ: prettier_angabe(relativ) for relativ in NPM_PAKETE},
    }
    assert len(quellen) == 4, quellen
    leer = [pfad for pfad, wert in quellen.items() if not wert]
    assert not leer, f"Leere Versionsangabe aus: {leer}"


def test_die_package_json_aufzaehlung_findet_beide_bekannten_baeume() -> None:
    gefunden = [pfad for pfad in verwaltete_pfade() if Path(pfad).name == "package.json"]
    assert len(gefunden) >= 2, gefunden
    for bekannt in NPM_PAKETE:
        assert bekannt in gefunden, (
            f"{bekannt} fehlt in der Aufzaehlung ({gefunden}). Die repo-weiten Zusicherungen "
            "(d)/(e) pruefen dann an den beiden Baeumen vorbei, die es tatsaechlich gibt."
        )


@pytest.mark.parametrize(
    "leser",
    [pyproject_daten, json_daten, ruff_angabe, prettier_angabe, lockfile_aufloesung],
)
def test_eine_fehlende_datei_scheitert_unter_nennung_des_pfades(leser: object) -> None:
    with pytest.raises(ValueError, match=r"gibt-es-nicht\.toml"):
        leser("gibt-es-nicht.toml")  # type: ignore[operator]
