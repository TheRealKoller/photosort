"""Haelt deklarierten Satz, aufgeloeste Menge und CI-Verbraucher der Backend-Abhaengigkeiten zusammen.

`backend/pyproject.toml` deklariert, `backend/uv.lock` haelt die Aufloesung fest, und der Job
`backend` in `.github/workflows/ci.yml` ist der Verbraucher. Drei Zusicherungen, jede gegen eine
andere Art des Auseinanderlaufens:

1. **Deklaration gegen Aufloesung.** `[project].dependencies` und jedes Extra aus
   `[project].optional-dependencies` stehen mit normalisiertem Namen, Extras, Specifier und Marker
   in `[package.metadata].requires-dist` des Lock-Eintrags `photosort`; `requires-python` und
   `provides-extras` ebenso. Faengt: `pyproject.toml` geaendert und `uv lock` vergessen - und einen
   von Hand nachgezogenen `requires-dist`.
2. **Aufloesungskanten gegen Deklaration.** Die `dependencies`/`optional-dependencies`-Kanten des
   `photosort`-Eintrags nennen dieselbe Menge. Ohne diese zweite Zusicherung bliebe ein Lock
   inhaltlich falsch, waehrend die erste Zusicherung gruen meldet: ein nachgezogener
   `requires-dist` ueber veralteten Kanten.
3. **Der CI-Verbraucher liest die Aufloesung.** Der `run:`-Rumpf von `Install dependencies` im
   Job, der diesen Schritt traegt (heute `backend-test`; der Schluessel wird abgeleitet),
   exportiert genau einmal mit `--locked` und `--extra dev` und installiert genau einmal
   aus genau der Datei, die `-o` erzeugt, mit `--system` und `--no-deps`. Faengt: `--locked` zu
   `--frozen` abgeschwaecht, ein verlorenes `--no-deps` (`uv pip` loest dann wieder selbst auf),
   ein `-r` auf eine andere Datei.

**Kein Volldiff des `run:`-Rumpfs.** Eine zulaessige Umformulierung soll keinen Testdiff
erzwingen; geprueft sind die tragenden Formen einzeln. Ebenso wird hier **kein** `uv` aufgerufen:
`uv lock --check` rechnet gegen den Paketindex und machte aus einer Bestandszusicherung einen
Netztest. Den Erzeugungsnachweis fuehren `uv lock --check` lokal und `--locked` im CI-Rumpf; dieser
Waechter traegt stattdessen die Uebereinstimmung von Deklaration, Aufloesung und Verbraucher.

**Wirksamkeitsbeleg (2026-11-16, Mutationsreihe am Bestand, jede Mutation zurueckgenommen).**
Zusicherungen 1 und 2 sind am Bestand von Anfang an gruen, weil Manifest und Lock
uebereinstimmen; Zusicherung 3 war rot, solange `Install dependencies` noch
`uv pip install --system -e ".[dev]"` trug (`ValueError: Schritt 'Install dependencies' traegt
keinen run: |-Block`), und wurde mit der CI-Umstellung gruen. Ein gruener Test ohne Rot-Phase
traegt nichts, deshalb die Gegenprobe, `cd scripts && pytest -q tests/test_backend_lock_aktuell.py`:

| Eingriff | rot in |
|---|---|
| `"numpy>=1.26"` aus `[project].dependencies` entnommen | Zusicherung 1 und 2 |
| `fastapi>=0.115` zu `fastapi>=0.116` | Zusicherung 1 |
| `"ruff==0.16.4"` aus dem dev-Extra entnommen | Zusicherung 1 und 2 |
| `requests>=2.32` in Manifest **und** `requires-dist`, Kanten unveraendert | Zusicherung 2 |
| `uv export --frozen` statt `--locked` | Zusicherung 3 |
| `--no-deps` entfernt | Zusicherung 3 |
| `-r "$RUNNER_TEMP/andere.txt"` statt der `-o`-Datei | Zusicherung 3 |

Nach jeder Ruecknahme: `24 passed`, Pruefsummen von `pyproject.toml`, `uv.lock` und `ci.yml`
unveraendert. Die drei Rumpf-Mutationen stehen zusaetzlich als dauerhafte Gegenproben in dieser
Datei.
"""

from __future__ import annotations

import re
import shlex
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

REPO_WURZEL = Path(__file__).parents[2]

PYPROJECT_PFAD = "backend/pyproject.toml"
LOCK_PFAD = "backend/uv.lock"
CI_PFAD = ".github/workflows/ci.yml"

INSTALL_SCHRITT = "Install dependencies"

# Selbstschutz gegen eine abgeschnittene oder fremde Lockdatei: Der reale Stand traegt 112
# Eintraege (111 Registry-Pakete + `photosort`). Fuenfzig faengt den Totalausfall, nicht jede
# geloeschte Zeile.
MINDESTZAHL_PAKETE = 50

_UNGUELTIGE_ZEICHEN = re.compile(r"[^a-z0-9]+")


# --- Reine Funktionen: Namen und Anforderungen ---------------------------------------------


def normalisiere_name(name: str) -> str:
    """PEP 503: Lauf aus `-`, `_`, `.` wird zu einem `-`, alles klein."""
    return _UNGUELTIGE_ZEICHEN.sub("-", name.strip().lower()).strip("-")


@dataclass(frozen=True)
class Anforderung:
    """Eine Anforderung in der Form, in der beide Seiten verglichen werden koennen."""

    name: str
    extras: tuple[str, ...]
    specifier: str
    marker: str | None

    def schluessel(self) -> tuple[str, tuple[str, ...], str, str | None]:
        return (self.name, self.extras, self.specifier, self.marker)


_ANFORDERUNG = re.compile(
    r"^(?P<name>[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)"
    r"(?:\[(?P<extras>[^\]]*)\])?"
    r"(?P<specifier>.*)$"
)


def _extra_liste(roh: str) -> tuple[str, ...]:
    return tuple(sorted(normalisiere_name(teil) for teil in roh.split(",") if teil.strip()))


def _abweisende_form(text: str) -> str:
    return (
        f"Deklaration {text!r} traegt eine Form, die dieser Test nicht kennt. Er bricht hier laut "
        "ab, statt die Anforderung stillschweigend zu ueberspringen - eine uebersprungene "
        "Anforderung liesse Manifest und Lock unbemerkt auseinanderlaufen."
    )


def parse_anforderung(text: str, extra: str | None) -> Anforderung:
    """Zerlegt eine Deklaration aus `pyproject.toml`; unbekannte Formen brechen laut ab.

    Bekannt ist genau `name[extras]specifier` in den deklarierten Abhaengigkeiten sowie dieselbe
    Form in einem Extra. URL, Pfad, Git-Referenz und jeder Marker ausser dem erwarteten
    Extras-Marker sind unbekannt: Sie kaemen mit einer Semantik, die der Lock-Vergleich nicht
    abbildet, und ein stilles Uebergehen waere schlimmer als ein Abbruch.
    """
    if "@" in text:
        raise ValueError(_abweisende_form(text))
    ohne_marker, trenner, _marker = text.partition(";")
    if trenner:
        raise ValueError(_abweisende_form(text))
    if "/" in ohne_marker or "\\" in ohne_marker:
        raise ValueError(_abweisende_form(text))

    treffer = _ANFORDERUNG.match(ohne_marker.strip())
    if treffer is None:
        raise ValueError(_abweisende_form(text))
    specifier = "".join(treffer.group("specifier").split())
    if specifier and specifier[0] not in "<>=!~":
        raise ValueError(_abweisende_form(text))

    return Anforderung(
        name=normalisiere_name(treffer.group("name")),
        extras=_extra_liste(treffer.group("extras") or ""),
        specifier=specifier,
        marker=f"extra=='{normalisiere_name(extra)}'" if extra else None,
    )


def _normalisiere_marker(marker: str) -> str:
    """Vergleichsform eines Markers: ohne Leerraum, Anfuehrungszeichen vereinheitlicht."""
    return re.sub(r"\s+", "", marker).replace('"', "'")


def extra_aus_marker(marker: str | None) -> str | None:
    """Der Extras-Name aus einem Marker der Form `extra == 'dev'`; alles andere ist unbekannt."""
    if marker is None:
        return None
    treffer = re.fullmatch(r"extra=='([a-z0-9._-]+)'", marker)
    if treffer is None:
        raise ValueError(
            f"Marker {marker!r} ist keine reine Extra-Bedingung. Ein plattform- oder "
            "python-version-abhaengiger Marker aendert, welche Pakete eine Umgebung zieht; dieser "
            "Test kennt ihn nicht und bricht deshalb laut ab, statt ihn zu ueberspringen."
        )
    return normalisiere_name(treffer.group(1))


def deklarationen(pyproject: Mapping[str, Any]) -> dict[str, Anforderung]:
    """Der deklarierte Satz als `name -> Anforderung`; doppelte Namen brechen laut ab."""
    projekt = pyproject.get("project")
    if not isinstance(projekt, dict):
        raise ValueError("[project] fehlt in backend/pyproject.toml")

    roh: list[tuple[str, str | None]] = []
    for eintrag in _liste(projekt.get("dependencies"), "[project].dependencies"):
        roh.append((_text(eintrag, "[project].dependencies"), None))
    optionale = projekt.get("optional-dependencies") or {}
    if not isinstance(optionale, dict):
        raise ValueError("[project].optional-dependencies ist keine Tabelle")
    for extra, eintraege in optionale.items():
        for eintrag in _liste(eintraege, f"Extra {extra!r}"):
            roh.append((_text(eintrag, f"Extra {extra!r}"), str(extra)))

    ergebnis: dict[str, Anforderung] = {}
    for eintrag, extra in roh:
        anforderung = parse_anforderung(eintrag, extra)
        if anforderung.name in ergebnis:
            raise ValueError(
                f"Die Abhaengigkeit {anforderung.name!r} steht zweimal im deklarierten Satz. "
                "Welche der beiden Zeilen die Fixierung traegt, ist dann nicht entscheidbar."
            )
        ergebnis[anforderung.name] = anforderung
    if not ergebnis:
        raise ValueError("[project].dependencies ist leer - geprueft waere dann nichts.")
    return ergebnis


def requires_dist(eintrag: Mapping[str, Any]) -> dict[str, Anforderung]:
    """`[package.metadata].requires-dist` eines Lock-Eintrags als `name -> Anforderung`."""
    metadata = eintrag.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("Lock-Eintrag ohne [package.metadata]")
    roh = _liste(metadata.get("requires-dist"), "requires-dist")
    if not roh:
        raise ValueError(
            "requires-dist ist leer: Damit stuende die Aufloesung ohne jede Aussage ueber die "
            "deklarierten Abhaengigkeiten da."
        )
    ergebnis: dict[str, Anforderung] = {}
    for eintrag_roh in roh:
        if not isinstance(eintrag_roh, dict):
            raise ValueError(f"requires-dist-Eintrag {eintrag_roh!r} ist keine Tabelle")
        unbekannt = set(eintrag_roh) - {"name", "extras", "specifier", "marker"}
        if unbekannt:
            raise ValueError(f"unbekannte Felder in requires-dist: {sorted(unbekannt)}")
        name = normalisiere_name(str(eintrag_roh.get("name", "")))
        if not name:
            raise ValueError(f"requires-dist-Eintrag ohne Namen: {eintrag_roh!r}")
        marker = eintrag_roh.get("marker")
        anforderung = Anforderung(
            name=name,
            extras=tuple(sorted(normalisiere_name(teil) for teil in eintrag_roh.get("extras", []))),
            specifier="".join(str(eintrag_roh.get("specifier", "")).split()),
            marker=_normalisiere_marker(str(marker)) if marker is not None else None,
        )
        if name in ergebnis:
            raise ValueError(f"requires-dist nennt {name!r} zweimal")
        ergebnis[name] = anforderung
    return ergebnis


def kanten(eintrag: Mapping[str, Any]) -> set[tuple[str | None, str, tuple[str, ...]]]:
    """Die Abhaengigkeitskanten eines Lock-Eintrags: (extra, name, extras)."""
    ergebnis: set[tuple[str | None, str, tuple[str, ...]]] = set()
    for kante in _liste(eintrag.get("dependencies", []), "dependencies"):
        ergebnis.add(_kante(kante, None))
    optionale = eintrag.get("optional-dependencies") or {}
    if not isinstance(optionale, dict):
        raise ValueError("optional-dependencies ist keine Tabelle")
    for extra, kantenliste in optionale.items():
        for kante in _liste(kantenliste, f"optional-dependencies[{extra!r}]"):
            ergebnis.add(_kante(kante, str(extra)))
    return ergebnis


def _kante(kante: object, extra: str | None) -> tuple[str | None, str, tuple[str, ...]]:
    if not isinstance(kante, dict):
        raise ValueError(f"Lock-Kante {kante!r} ist keine Tabelle")
    unbekannt = set(kante) - {"name", "extra"}
    if unbekannt:
        raise ValueError(
            f"Lock-Kante {kante!r} traegt {sorted(unbekannt)}: Ein Marker an der Kante aendert, "
            "welche Umgebung das Paket zieht - diese Form kennt der Test nicht."
        )
    name = normalisiere_name(str(kante.get("name", "")))
    if not name:
        raise ValueError(f"Lock-Kante ohne Namen: {kante!r}")
    extras_roh = kante.get("extra", [])
    if not isinstance(extras_roh, list):
        raise ValueError(f"Lock-Kante {kante!r} traegt kein Extra als Liste")
    return (
        normalisiere_name(extra) if extra else None,
        name,
        tuple(sorted(normalisiere_name(str(teil)) for teil in extras_roh)),
    )


def deklarierte_kanten(
    pyproject: Mapping[str, Any],
) -> set[tuple[str | None, str, tuple[str, ...]]]:
    return {
        (extra_aus_marker(anforderung.marker), anforderung.name, anforderung.extras)
        for anforderung in deklarationen(pyproject).values()
    }


def photosort_eintrag(lock: Mapping[str, Any]) -> Mapping[str, Any]:
    """Der eine Lock-Eintrag des Projekts; 0 oder 2 Eintraege sind laute Fehler."""
    pakete = lock.get("package")
    if not isinstance(pakete, list):
        raise ValueError("uv.lock ohne [[package]]-Liste")
    if len(pakete) < MINDESTZAHL_PAKETE:
        raise ValueError(
            f"uv.lock traegt nur {len(pakete)} Pakete (erwartet mindestens {MINDESTZAHL_PAKETE}). "
            "Eine abgeschnittene Datei saehe in jeder Einzelpruefung wie ein sauberer Stand aus."
        )
    treffer = [
        paket for paket in pakete if normalisiere_name(str(paket.get("name", ""))) == "photosort"
    ]
    if len(treffer) != 1:
        raise ValueError(
            f"{len(treffer)} Eintraege fuer 'photosort' in uv.lock (erwartet genau einer). Bei 0 "
            "prueft der Vergleich nichts, bei 2 ist nicht entscheidbar, welcher die Aufloesung "
            "traegt."
        )
    return treffer[0]


def _liste(wert: object, bezeichnung: str) -> list[Any]:
    if wert is None:
        return []
    if not isinstance(wert, list):
        raise ValueError(f"{bezeichnung} ist keine Liste")
    return wert


def _text(wert: object, bezeichnung: str) -> str:
    if not isinstance(wert, str) or not wert.strip():
        raise ValueError(f"{bezeichnung} enthaelt {wert!r} statt einer Anforderung")
    return wert


# --- Reine Funktionen: der CI-Rumpf --------------------------------------------------------


def befehle(rumpf: str) -> list[list[str]]:
    """Die Shell-Befehle eines `run: |`-Rumpfs, Zeilenfortsetzungen zusammengezogen."""
    zeilen: list[str] = []
    puffer = ""
    for zeile in rumpf.splitlines():
        if zeile.rstrip().endswith("\\"):
            puffer += zeile.rstrip()[:-1] + " "
            continue
        puffer += zeile
        if puffer.strip():
            zeilen.append(puffer)
        puffer = ""
    if puffer.strip():
        zeilen.append(puffer)
    return [shlex.split(zeile) for zeile in zeilen]


def _wert(argv: list[str], kurz: str, lang: str) -> str | None:
    for index, arg in enumerate(argv):
        if arg in (kurz, lang):
            if index + 1 >= len(argv):
                raise ValueError(f"{arg} in {argv!r} ohne Wert")
            return argv[index + 1]
        if arg.startswith(lang + "="):
            return arg.partition("=")[2]
    return None


def rumpf_befunde(rumpf: str) -> list[str]:
    """Befunde am `run:`-Rumpf von `Install dependencies`; leer = fail-closed aus dem Lock."""
    befunde: list[str] = []
    if "${{" in rumpf:
        befunde.append(
            "Der Rumpf interpoliert einen Workflow-Ausdruck (`${{ }}`). In diesem Schritt ist "
            "keine PR-kontrollierte Zeichenkette erlaubt."
        )
    try:
        alle = befehle(rumpf)
    except ValueError as fehler:  # unausgeglichene Anfuehrungszeichen u.a.
        return [f"run:-Rumpf nicht lesbar: {fehler}"]

    exports = [argv for argv in alle if argv[:2] == ["uv", "export"]]
    installs = [argv for argv in alle if argv[:2] == ["uv", "pip"]]
    if len(exports) != 1:
        befunde.append(f"{len(exports)} `uv export`-Aufrufe (erwartet genau einer)")
    if len(installs) != 1:
        befunde.append(f"{len(installs)} `uv pip`-Aufrufe (erwartet genau einer)")
    if len(exports) != 1 or len(installs) != 1:
        return befunde

    export, install = exports[0], installs[0]
    zieldatei: str | None = None

    if "--frozen" in export:
        befunde.append(
            "`uv export` traegt `--frozen` statt `--locked`: Eine Abweichung zwischen "
            "Manifest und Lock fiele dann still durch."
        )
    if "--locked" not in export:
        befunde.append("`uv export` traegt kein `--locked`.")
    if _wert(export, "-e", "--extra") != "dev":
        befunde.append("`uv export` exportiert nicht das dev-Extra.")
    try:
        zieldatei = _wert(export, "-o", "--output-file")
    except ValueError as fehler:
        befunde.append(str(fehler))
    if not zieldatei:
        befunde.append("`uv export` nennt keine Ausgabedatei (`-o`).")

    if "--frozen" in install:
        befunde.append("`uv pip install` traegt `--frozen`.")
    if "--system" not in install:
        befunde.append("`uv pip install` traegt kein `--system`.")
    if "--no-deps" not in install:
        befunde.append(
            "`uv pip install` traegt kein `--no-deps`: uv loest dann beim Installieren erneut "
            "auf, und der Lock ist nicht mehr die einzige Quelle."
        )
    try:
        gelesen = _wert(install, "-r", "--requirement")
        installiert = _wert(install, "-e", "--editable")
    except ValueError as fehler:
        befunde.append(str(fehler))
    else:
        if zieldatei and gelesen != zieldatei:
            befunde.append(
                f"`uv pip install -r` liest {gelesen!r}, `uv export -o` schreibt {zieldatei!r}."
            )
        if installiert != ".":
            befunde.append(f"`uv pip install -e` zielt auf {installiert!r} statt auf '.'.")
    return befunde


# --- Duenne Leser --------------------------------------------------------------------------


def dateitext(pfad: str, wurzel: Path = REPO_WURZEL) -> str:
    """Duenner Leser; eine fehlende Datei scheitert laut."""
    return (wurzel / pfad).read_text(encoding="utf-8")


def lies_toml(pfad: str, wurzel: Path = REPO_WURZEL) -> dict[str, Any]:
    datei = wurzel / pfad
    if not datei.is_file():
        raise FileNotFoundError(
            f"{pfad} fehlt. Deklaration und Aufloesung sind dann ungeprueft - dieser Zustand ist "
            "ein Fehler, kein Nullbefund."
        )
    with datei.open("rb") as handle:
        return tomllib.load(handle)


def lock_daten(wurzel: Path = REPO_WURZEL) -> dict[str, Any]:
    daten = lies_toml(LOCK_PFAD, wurzel)
    photosort_eintrag(daten)  # Selbstschutz: Paketmenge und der eine Projekt-Eintrag
    return daten


_JOBS_KOPF = re.compile(r"^jobs:[ \t]*$", re.MULTILINE)
_TOP_KEY = re.compile(r"^  (?P<key>[a-z][a-z0-9-]*):$", re.MULTILINE)
_SCHRITT = re.compile(r"^      - ", re.MULTILINE)
_NAME = re.compile(r"^\s*name:\s*([^\n]+?)\s*$", re.MULTILINE)


def backend_job(text: str) -> str:
    """Der Job, der `Install dependencies` traegt - abgeleitet, nicht literal `backend`.

    Mit der Shard-Matrix (ADR 0151) liegt der Installationsschritt in `backend-test`, waehrend
    `backend` nur noch der Aggregator ist. Der Traeger wird ueber seinen Schritt gefunden, damit
    eine erneute Umbenennung nicht wieder eine gepflegte Job-Liste verlangt.
    """
    for kopf in _TOP_KEY.finditer(text):
        rest = text[kopf.end() :]
        naechster = _TOP_KEY.search(rest)
        block = rest[: naechster.start()] if naechster else rest
        if "      - " not in block:
            continue
        if any(schritt_name(teil) == INSTALL_SCHRITT for teil in schritte(block)):
            return block
    raise ValueError(f"Kein Job traegt den Schritt {INSTALL_SCHRITT!r}")


def schritte(job: str) -> list[str]:
    bloecke = _SCHRITT.split(job)[1:]
    if not bloecke:
        raise ValueError("Job ohne Schritte")
    return bloecke


def schritt_name(block: str) -> str | None:
    treffer = _NAME.search(block)
    return treffer.group(1) if treffer else None


def run_rumpf(block: str) -> str:
    """Der Inhalt eines `run: |`-Blocks, um zwei Einrueckungen ausgerueckt."""
    treffer = re.search(r"^        run: \|\n", block, re.MULTILINE)
    if treffer is None:
        raise ValueError(f"Schritt {schritt_name(block)!r} traegt keinen `run: |`-Block")
    zeilen: list[str] = []
    for zeile in block[treffer.end() :].splitlines():
        if zeile.strip() and not zeile.startswith("          "):
            break
        zeilen.append(zeile[2:] if zeile.strip() else "")
    if not zeilen:
        raise ValueError(f"Schritt {schritt_name(block)!r} hat einen leeren run:-Block")
    return "\n".join(zeilen)


def install_rumpf(ci: str) -> str:
    """Der `run:`-Rumpf von `Install dependencies` im tragenden Job; laut, wenn er fehlt."""
    for block in schritte(backend_job(ci)):
        if schritt_name(block) == INSTALL_SCHRITT:
            return run_rumpf(block)
    raise ValueError(f"Kein Job traegt den Schritt {INSTALL_SCHRITT!r}")


# --- Die eigentlichen Zusicherungen --------------------------------------------------------


def test_die_aufloesung_traegt_genau_den_deklarierten_satz() -> None:
    erwartet = deklarationen(lies_toml(PYPROJECT_PFAD))
    tatsaechlich = requires_dist(photosort_eintrag(lock_daten()))

    fehlend = sorted(set(erwartet) - set(tatsaechlich))
    ueberzaehlig = sorted(set(tatsaechlich) - set(erwartet))
    abweichend = sorted(
        name
        for name in set(erwartet) & set(tatsaechlich)
        if erwartet[name].schluessel() != tatsaechlich[name].schluessel()
    )
    assert not (fehlend or ueberzaehlig or abweichend), (
        f"uv.lock passt nicht zu backend/pyproject.toml. Nur im Manifest: {fehlend}. Nur im Lock: "
        f"{ueberzaehlig}. Abweichend (Extras/Specifier/Marker): "
        f"{[(name, erwartet[name].schluessel(), tatsaechlich[name].schluessel()) for name in abweichend]}. "
        "Nach jeder Aenderung an pyproject.toml gehoert `(cd backend && uv lock)` dazu, und "
        "backend/uv.lock in denselben Commit - eine von Hand nachgezogene requires-dist-Zeile "
        "waere keine Aufloesung."
    )


def test_requires_python_und_extras_stimmen_ueberein() -> None:
    pyproject = lies_toml(PYPROJECT_PFAD)
    lock = lock_daten()
    eintrag = photosort_eintrag(lock)
    metadata = eintrag["metadata"]

    assert lock.get("requires-python") == pyproject["project"]["requires-python"], (
        f"requires-python im Lock ist {lock.get('requires-python')!r}, im Manifest "
        f"{pyproject['project']['requires-python']!r}."
    )
    erwartete_extras = sorted(pyproject["project"].get("optional-dependencies") or {})
    assert sorted(metadata.get("provides-extras") or []) == erwartete_extras, (
        f"provides-extras im Lock ist {metadata.get('provides-extras')!r}, im Manifest stehen die "
        f"Extras {erwartete_extras}. Ein Extra, das im Lock fehlt, waere im CI-Export unsichtbar."
    )


def test_die_kanten_der_aufloesung_nennen_dieselben_abhaengigkeiten() -> None:
    erwartet = deklarierte_kanten(lies_toml(PYPROJECT_PFAD))
    tatsaechlich = kanten(photosort_eintrag(lock_daten()))

    fehlend = sorted(erwartet - tatsaechlich)
    ueberzaehlig = sorted(tatsaechlich - erwartet)
    assert not (fehlend or ueberzaehlig), (
        f"Die Kanten des photosort-Eintrags in uv.lock weichen von der Deklaration ab. Fehlend: "
        f"{fehlend}. Ueberzaehlig: {ueberzaehlig}. Ein nachgezogener requires-dist ueber solchen "
        "Kanten liesse das Lock inhaltlich falsch, waehrend der Manifest-Vergleich gruen meldet."
    )


def test_der_ci_installationsschritt_liest_die_aufloesung() -> None:
    befunde = rumpf_befunde(install_rumpf(dateitext(CI_PFAD)))

    assert not befunde, (
        "Der Schritt 'Install dependencies' im Backend-Testjob zieht die Abhaengigkeiten nicht "
        "fail-closed aus dem Lock: " + "; ".join(befunde)
    )


# --- Gegenproben an synthetischem Material -------------------------------------------------


def _lock(*eintraege: Mapping[str, Any]) -> dict[str, Any]:
    return {"package": [dict(eintrag) for eintrag in eintraege]}


def _photosort(
    requires: Iterable[Mapping[str, Any]], kantenn: Iterable[Any] = ()
) -> dict[str, Any]:
    return {
        "name": "photosort",
        "dependencies": list(kantenn),
        "metadata": {"requires-dist": list(requires)},
    }


@pytest.mark.parametrize(
    ("bezeichnung", "lock"),
    [
        ("keine Paketliste", {}),
        (
            "zu wenige Pakete",
            _lock(*[{"name": f"paket-{i}"} for i in range(MINDESTZAHL_PAKETE - 1)]),
        ),
        ("kein photosort", _lock({"name": "absl-py"})),
        (
            "zwei photosort",
            _lock(
                _photosort([{"name": "fastapi", "specifier": ">=0.115"}]),
                _photosort([{"name": "fastapi", "specifier": ">=0.115"}]),
            ),
        ),
        ("leeres requires-dist", _lock(_photosort([]))),
    ],
)
def test_eine_unbrauchbare_aufloesung_scheitert_laut(
    bezeichnung: str, lock: Mapping[str, Any]
) -> None:
    with pytest.raises(ValueError):
        photosort_eintrag(lock)


@pytest.mark.parametrize(
    "deklaration",
    [
        "paket @ https://example.invalid/paket-1.0.whl",
        "paket @ git+https://example.invalid/paket.git",
        "./lokales-paket",
        "paket; python_version < '3.13'",
        "paket; sys_platform == 'win32'",
    ],
)
def test_eine_unbekannte_anforderungsform_scheitert_laut(deklaration: str) -> None:
    with pytest.raises(ValueError):
        parse_anforderung(deklaration, None)


def test_ein_doppelter_name_in_der_deklaration_scheitert_laut() -> None:
    with pytest.raises(ValueError, match=r"zweimal"):
        deklarationen({"project": {"dependencies": ["fastapi>=0.115", "fastapi>=0.116"]}})


def test_ein_nachgezogener_requires_dist_ueber_veralteten_kanten_wird_erkannt() -> None:
    """Die zweite Zusicherung traegt genau den Fall, den die erste nicht sieht."""
    pyproject = {
        "project": {
            "dependencies": ["fastapi>=0.115", "numpy>=1.26"],
            "optional-dependencies": {"dev": ["pytest>=8.3"]},
        }
    }
    eintrag = _photosort(
        [
            {"name": "fastapi", "specifier": ">=0.115"},
            {"name": "numpy", "specifier": ">=1.26"},
            {"name": "pytest", "marker": "extra == 'dev'", "specifier": ">=8.3"},
        ],
        kantenn=[{"name": "fastapi"}],  # numpy-Kante fehlt
    )

    assert requires_dist(eintrag) == deklarationen(pyproject)
    assert kanten(eintrag) != deklarierte_kanten(pyproject)


@pytest.mark.parametrize(
    ("bezeichnung", "rumpf"),
    [
        (
            "frozen statt locked",
            'uv export --frozen --extra dev --no-hashes --no-emit-project -o "$T/x.txt"\n'
            'uv pip install --system --no-deps -r "$T/x.txt" -e .\n',
        ),
        (
            "ohne no-deps",
            'uv export --locked --extra dev --no-hashes --no-emit-project -o "$T/x.txt"\n'
            'uv pip install --system -r "$T/x.txt" -e .\n',
        ),
        (
            "abweichender -r-Pfad",
            'uv export --locked --extra dev --no-hashes --no-emit-project -o "$T/x.txt"\n'
            'uv pip install --system --no-deps -r "$T/y.txt" -e .\n',
        ),
        (
            "ohne locked",
            'uv export --extra dev --no-hashes --no-emit-project -o "$T/x.txt"\n'
            'uv pip install --system --no-deps -r "$T/x.txt" -e .\n',
        ),
        (
            "ohne dev-Extra",
            'uv export --locked --no-hashes --no-emit-project -o "$T/x.txt"\n'
            'uv pip install --system --no-deps -r "$T/x.txt" -e .\n',
        ),
        (
            "Workflow-Ausdruck im Rumpf",
            'uv export --locked --extra dev -o "${{ github.workspace }}/x.txt"\n'
            'uv pip install --system --no-deps -r "${{ github.workspace }}/x.txt" -e .\n',
        ),
        (
            "kein Export",
            'uv pip install --system --no-deps -r "$T/x.txt" -e .\n',
        ),
    ],
)
def test_ein_abgeschwaechter_installationsrumpf_wird_erkannt(bezeichnung: str, rumpf: str) -> None:
    assert rumpf_befunde(rumpf), f"Die Form {bezeichnung!r} muesste als Befund auffallen."


def test_der_erwartete_installationsrumpf_ist_kein_befund() -> None:
    rumpf = (
        'uv export --locked --extra dev --no-hashes --no-emit-project -o "$RUNNER_TEMP/backend.txt"\n'
        'uv pip install --system --no-deps -r "$RUNNER_TEMP/backend.txt" -e .\n'
    )

    assert rumpf_befunde(rumpf) == []
