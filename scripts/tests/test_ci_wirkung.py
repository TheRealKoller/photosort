"""Wirkungspruefung der CI: was die Workflows tun, nicht wie sie formuliert sind.

Fuenf Aussagen, unabhaengig von Job-Namen, Schritt-Namen und der Zahl der Workflow-Dateien:

- `qualitaet-laeuft` - jeder Baum des Repositories laesst seine Qualitaetsbefehle laufen.
- `tests-je-baum` - jeder Baum laesst seine Tests laufen.
- `coverage-schwelle` - der Backend-Testlauf haengt an einer Coverage-Schwelle von mindestens 80.
- `nicht-ueberspringbar` - kein Qualitaetsschritt ist ueberspringbar oder nicht blockierend.
- `pr-ausloeser` - jeder Workflow mit Qualitaetsschritten laeuft auf `pull_request`.

Die Baeume und ihre Befehle werden aus dem Repository abgeleitet (`pyproject.toml`,
`package.json`), nicht aus einer Liste von Job-Namen. Ein Workflow, den der Leser nicht versteht,
ist ein lauter Fehler - nie ein stiller Teilerfolg.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

import pytest
from waechter import Befund, Bestand, Invariante, befund

WORKFLOW_RAUM = ".github/workflows"
SCHWELLE = 80

QUALITAETS_BEFEHLE = re.compile(r"^(ruff|mypy|pytest|npm)\b")
JOB_KOPF = re.compile(r"^  (?P<key>[a-z][a-z0-9-]*):\s*$")
SCHRITT_BEGINN = re.compile(
    r"^      - (?P<key>name|run|uses|if|continue-on-error):\s*(?P<wert>.*)$"
)
EIGENSCHAFT = re.compile(r"^        (?P<key>name|run|uses|if|continue-on-error):\s*(?P<wert>.*)$")
ARBEIT = re.compile(r"^        working-directory:\s*(?P<wert>\S+)\s*$")
UEBERSPRINGBAR = re.compile(r"^    (?P<key>if|continue-on-error):\s*(?P<wert>.*)$")
BLOCKMARKEN = {"|", ">", "|-", ">-"}

INVARIANTEN = (
    Invariante(
        "qualitaet-laeuft",
        "Jeder Baum mit `pyproject.toml` bzw. `package.json` laesst in der CI seine "
        "Qualitaetsbefehle laufen: ruff format --check, ruff check, bei Backend mypy, bei npm "
        "jedes vorhandene Skript der Qualitaetsmenge.",
    ),
    Invariante("tests-je-baum", "Jeder Baum laesst seine Tests laufen (pytest bzw. `npm test`)."),
    Invariante(
        "coverage-schwelle",
        "Der Backend-Testlauf traegt `--cov-fail-under=<n>` mit n >= 80.",
    ),
    Invariante(
        "nicht-ueberspringbar",
        "Kein Schritt und kein Job mit einem Qualitaetsbefehl traegt `if:` oder "
        "`continue-on-error: true`.",
    ),
    Invariante(
        "pr-ausloeser",
        "Jeder Workflow mit Qualitaetsschritten laeuft auf `pull_request`.",
    ),
)

INVARIANTEN_IDS = frozenset(invariante.id for invariante in INVARIANTEN)


@dataclass(frozen=True)
class Schritt:
    """Ein Schritt: Name, ausgeführter Text, Zeile seiner Ausführung und seine Abschalter."""

    datei: str
    zeile: int
    name: str
    run: str
    run_zeile: int
    abschalter: tuple[tuple[int, str], ...]


@dataclass(frozen=True)
class Job:
    """Ein Job: Key, Arbeitsverzeichnis, Schritte und die Abschalter auf Job-Ebene."""

    datei: str
    zeile: int
    key: str
    arbeit: str
    schritte: tuple[Schritt, ...]
    abschalter: tuple[tuple[int, str], ...]


@dataclass(frozen=True)
class Workflow:
    """Ein Workflow: Datei, Jobs und der `on:`-Abschnitt."""

    datei: str
    on_zeile: int
    on_text: str
    jobs: tuple[Job, ...]

    @property
    def laeuft_auf_pr(self) -> bool:
        return "pull_request" in self.on_text


def _eingerueckt(zeile: str) -> int:
    return len(zeile) - len(zeile.lstrip())


def _block(zeilen: list[str], start: int, einrueckung: int) -> tuple[str, int]:
    """Der eingerueckte Rumpf eines `|`-Blocks, zusammengefasst, und die Folgzeile."""
    teile: list[str] = []
    nummer = start
    while nummer < len(zeilen):
        zeile = zeilen[nummer]
        if zeile.strip() and _eingerueckt(zeile) <= einrueckung:
            break
        teile.append(zeile.strip())
        nummer += 1
    return "\n".join(teile), nummer


def _schritte(datei: str, zeilen: list[str], start: int) -> tuple[tuple[Schritt, ...], int]:
    """Die Schritte eines Jobs ab `start` und die erste Zeile nach dem Schritte-Abschnitt."""
    schritte: list[Schritt] = []
    eigenschaften: list[tuple[int, str, str]] = []
    nummer = start

    def abschliessen() -> None:
        if not eigenschaften:
            return
        name = next((wert.strip() for _, key, wert in eigenschaften if key == "name"), "")
        run_paare = [(zeile, wert) for zeile, key, wert in eigenschaften if key == "run"]
        run_zeile, run = run_paare[0] if run_paare else (eigenschaften[0][0], "")
        schritte.append(
            Schritt(
                datei=datei,
                zeile=eigenschaften[0][0],
                name=name,
                run=run.strip(),
                run_zeile=run_zeile,
                abschalter=tuple(
                    (zeile, f"{key}: {wert.strip()}")
                    for zeile, key, wert in eigenschaften
                    if key in {"if", "continue-on-error"}
                ),
            )
        )
        eigenschaften.clear()

    while nummer < len(zeilen):
        zeile = zeilen[nummer]
        if not zeile.strip():
            nummer += 1
            continue
        if zeile.lstrip().startswith("#"):
            nummer += 1
            continue
        passend = SCHRITT_BEGINN.match(zeile)
        if passend:
            abschliessen()
            key, wert = passend.group("key"), passend.group("wert")
            zeile_nummer = nummer + 1
            nummer += 1
            if wert.strip() in BLOCKMARKEN:
                wert, nummer = _block(zeilen, nummer, 8)
            eigenschaften.append((zeile_nummer, key, wert))
            continue
        passend = EIGENSCHAFT.match(zeile)
        if passend:
            key, wert = passend.group("key"), passend.group("wert")
            zeile_nummer = nummer + 1
            nummer += 1
            if wert.strip() in BLOCKMARKEN:
                wert, nummer = _block(zeilen, nummer, 8)
            eigenschaften.append((zeile_nummer, key, wert))
            continue
        if _eingerueckt(zeile) >= 8:
            # `with:`, `env:` und ihre Kinder tragen fuer die Wirkung nichts bei.
            nummer += 1
            continue
        if _eingerueckt(zeile) < 6:
            break
        raise ValueError(f"{datei}:{nummer + 1}: Zeile im Schritte-Abschnitt nicht verstanden.")
    abschliessen()
    return tuple(schritte), nummer


def _jobs(datei: str, text: str) -> tuple[Job, ...]:
    zeilen = text.split("\n")
    start = next((i for i, zeile in enumerate(zeilen) if zeile.rstrip() == "jobs:"), None)
    if start is None:
        raise ValueError(f"{datei}: kein `jobs:`-Abschnitt - Form nicht verstanden.")
    jobs: list[Job] = []
    nummer = start + 1
    while nummer < len(zeilen):
        zeile = zeilen[nummer]
        if not zeile.strip():
            nummer += 1
            continue
        passend = JOB_KOPF.match(zeile)
        if not passend:
            if zeile.startswith(" "):
                raise ValueError(f"{datei}:{nummer + 1}: Jobform nicht verstanden: {zeile!r}")
            break
        job_zeile = nummer + 1
        nummer += 1
        arbeit = ""
        schritte: tuple[Schritt, ...] = ()
        abschalter: list[tuple[int, str]] = []
        while nummer < len(zeilen):
            zeile = zeilen[nummer]
            if zeile.strip() and _eingerueckt(zeile) <= 2:
                break
            treffer = ARBEIT.match(zeile)
            if treffer:
                arbeit = treffer.group("wert")
            treffer = UEBERSPRINGBAR.match(zeile)
            if treffer:
                abschalter.append((nummer + 1, f"{treffer.group('key')}: {treffer.group('wert')}"))
            if zeile.rstrip() == "    steps:":
                schritte, nummer = _schritte(datei, zeilen, nummer + 1)
                continue
            nummer += 1
        jobs.append(
            Job(
                datei=datei,
                zeile=job_zeile,
                key=passend.group("key"),
                arbeit=arbeit,
                schritte=schritte,
                abschalter=tuple(abschalter),
            )
        )
    return tuple(jobs)


def _on_abschnitt(datei: str, text: str) -> tuple[int, str]:
    zeilen = text.split("\n")
    for nummer, zeile in enumerate(zeilen):
        if not zeile.startswith("on:"):
            continue
        rumpf, _ = _block(zeilen, nummer + 1, 0)
        return nummer + 1, "\n".join([zeile, rumpf])
    raise ValueError(f"{datei}: kein `on:`-Abschnitt - Form nicht verstanden.")


def workflows(bestand: Bestand) -> tuple[Workflow, ...]:
    """Alle Workflows des Bestands, gelesen ueber ihre Jobs - laut bei unverstandener Form."""
    ergebnis: list[Workflow] = []
    for datei in sorted(bestand):
        if not datei.startswith(f"{WORKFLOW_RAUM}/") or not datei.endswith((".yml", ".yaml")):
            continue
        text = bestand[datei]
        zeile, on_text = _on_abschnitt(datei, text)
        ergebnis.append(
            Workflow(datei=datei, on_zeile=zeile, on_text=on_text, jobs=_jobs(datei, text))
        )
    if not ergebnis:
        raise ValueError(
            "kein Workflow im Bestand - ein leerer Pruefraum macht jede Pruefung wahr."
        )
    return tuple(ergebnis)


def _baeume(bestand: Bestand) -> dict[str, str]:
    """Baumname -> Art, abgeleitet aus den Manifesten im Repository."""
    kandidaten = (
        ("backend", "python", "backend/pyproject.toml"),
        ("scripts", "python", "scripts/pyproject.toml"),
        ("frontend", "js", "frontend/package.json"),
        ("eye", "js", "eye/package.json"),
    )
    return {name: art for name, art, manifest in kandidaten if manifest in bestand}


def _pflichtbefehle(bestand: Bestand, baum: str, art: str) -> tuple[str, ...]:
    """Die Qualitaetsbefehle eines Baums, abgeleitet aus seinem Manifest."""
    if art == "python":
        befehle = ["ruff format --check", "ruff check", "pytest"]
        if baum == "backend":
            befehle.insert(2, "mypy")
        return tuple(befehle)
    skripte = json.loads(bestand[f"{baum}/package.json"]).get("scripts", {})
    return tuple(
        f"npm run {skript}"
        for skript in ("format:check", "lint", "typecheck", "test", "build")
        if skript in skripte
    )


def _jobs_je_baum(work: tuple[Workflow, ...], baum: str) -> list[Job]:
    return [job for workflow in work for job in workflow.jobs if job.arbeit.rstrip("/") == baum]


def _ausfuehrung(job: Job, befehl: str) -> Schritt | None:
    """Der Schritt, der den Befehl ausfuehrt - nur am Zeilenanfang, nicht in einem Echo."""
    formen = [befehl]
    if befehl.startswith("npm run "):
        formen.append(f"npm {befehl.removeprefix('npm run ')}")
    for schritt in job.schritte:
        if any(zeile.strip().startswith(tuple(formen)) for zeile in schritt.run.split("\n")):
            return schritt
    return None


def _gemeinter_schritt(job: Job, befehl: str) -> Schritt | None:
    """Der Schritt, der den Befehl dem Namen oder dem Text nach meint - Ort eines Befunds."""
    stichwort = befehl.split()[-1].lstrip("-")
    for schritt in job.schritte:
        if stichwort in schritt.name.lower() or stichwort in schritt.run.lower():
            return schritt
    return None


def _pruefe_befehl(jobs: list[Job], baum: str, befehl: str, invariante: str) -> list[Befund]:
    """Ein fehlender Befehl ist ein Befund an dem Schritt, der ihn dem Namen nach meint."""
    if any(_ausfuehrung(job, befehl) for job in jobs):
        return []
    for job in jobs:
        schritt = _gemeinter_schritt(job, befehl)
        if schritt is None:
            continue
        return [
            befund(
                schritt.datei,
                schritt.run_zeile,
                invariante,
                f"Baum '{baum}': Schritt '{schritt.name}' fuehrt `{befehl}` nicht aus.",
            )
        ]
    if jobs:
        return [
            befund(
                jobs[0].datei,
                jobs[0].zeile,
                invariante,
                f"Baum '{baum}': kein Schritt fuehrt `{befehl}` aus.",
            )
        ]
    return []


def _qualitaet_laeuft(bestand: Bestand, work: tuple[Workflow, ...]) -> list[Befund]:
    befunde: list[Befund] = []
    for baum, art in sorted(_baeume(bestand).items()):
        jobs = _jobs_je_baum(work, baum)
        for befehl in _pflichtbefehle(bestand, baum, art):
            befunde.extend(_pruefe_befehl(jobs, baum, befehl, "qualitaet-laeuft"))
    return befunde


def _tests_je_baum(bestand: Bestand, work: tuple[Workflow, ...]) -> list[Befund]:
    befunde: list[Befund] = []
    for baum, art in sorted(_baeume(bestand).items()):
        befehl = "pytest" if art == "python" else "npm run test"
        befunde.extend(_pruefe_befehl(_jobs_je_baum(work, baum), baum, befehl, "tests-je-baum"))
    return befunde


def _coverage_schwelle(bestand: Bestand, work: tuple[Workflow, ...]) -> list[Befund]:
    if "backend/pyproject.toml" not in bestand:
        return []
    for job in _jobs_je_baum(work, "backend"):
        schritt = _ausfuehrung(job, "pytest")
        if schritt is None:
            continue
        treffer = re.search(r"--cov-fail-under=(?P<wert>\d+)", schritt.run)
        if treffer is None:
            return [
                befund(
                    schritt.datei,
                    schritt.run_zeile,
                    "coverage-schwelle",
                    "Backend-Testlauf nennt keine Coverage-Schwelle - erwartet mindestens "
                    f"{SCHWELLE}.",
                )
            ]
        if int(treffer.group("wert")) < SCHWELLE:
            return [
                befund(
                    schritt.datei,
                    schritt.run_zeile,
                    "coverage-schwelle",
                    f"Backend-Testlauf traegt die Schwelle {treffer.group('wert')} - erwartet "
                    f"mindestens {SCHWELLE}.",
                )
            ]
    return []


def _nicht_ueberspringbar(work: tuple[Workflow, ...]) -> list[Befund]:
    befunde: list[Befund] = []
    for workflow in work:
        for job in workflow.jobs:
            if not any(QUALITAETS_BEFEHLE.match(schritt.run) for schritt in job.schritte):
                continue
            for nummer, text in job.abschalter:
                befunde.append(
                    befund(
                        job.datei,
                        nummer,
                        "nicht-ueberspringbar",
                        f"Job '{job.key}' traegt `{text}` - Qualitaet darf nicht ueberspringbar "
                        "sein.",
                    )
                )
            for schritt in job.schritte:
                if not QUALITAETS_BEFEHLE.match(schritt.run):
                    continue
                for nummer, text in schritt.abschalter:
                    befunde.append(
                        befund(
                            schritt.datei,
                            nummer,
                            "nicht-ueberspringbar",
                            f"Schritt '{schritt.name}' traegt `{text}` - Qualitaet darf nicht "
                            "ueberspringbar sein.",
                        )
                    )
    return befunde


def _pr_ausloeser(work: tuple[Workflow, ...]) -> list[Befund]:
    befunde: list[Befund] = []
    for workflow in work:
        traegt_qualitaet = any(
            QUALITAETS_BEFEHLE.match(schritt.run)
            for job in workflow.jobs
            for schritt in job.schritte
        )
        if traegt_qualitaet and not workflow.laeuft_auf_pr:
            befunde.append(
                befund(
                    workflow.datei,
                    workflow.on_zeile,
                    "pr-ausloeser",
                    "Workflow mit Qualitaetsschritten laeuft nicht auf `pull_request`.",
                )
            )
    return befunde


def pruefe(bestand: Bestand) -> list[Befund]:
    """Alle CI-Invarianten ueber einem Bestand - die eine Funktion dieses Waechters."""
    work = workflows(bestand)
    befunde: list[Befund] = []
    befunde.extend(_qualitaet_laeuft(bestand, work))
    befunde.extend(_tests_je_baum(bestand, work))
    befunde.extend(_coverage_schwelle(bestand, work))
    befunde.extend(_nicht_ueberspringbar(work))
    befunde.extend(_pr_ausloeser(work))
    return befunde


def test_der_bestand_erfuellt_alle_invarianten() -> None:
    """Der lebende Bestand haelt jede Invariante; die Verletzungsfaelle belegt `mutationen.py`."""
    befunde = pruefe(Bestand.aus_arbeitsbaum())

    assert not befunde, "CI-Befunde: " + "; ".join(f.meldung for f in befunde)


def test_ein_bestand_ohne_workflow_scheitert_laut() -> None:
    """Kein Workflow heisst: der Pruefraum ist leer - das ist ein Befund ueber den Leser."""
    with pytest.raises(ValueError, match="kein Workflow"):
        pruefe(Bestand({"README.md": "kein Workflow"}))
