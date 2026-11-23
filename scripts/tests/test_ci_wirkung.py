"""Wirkungspruefung der CI: was die Workflows tun, nicht wie sie formuliert sind.

Acht Aussagen, unabhaengig von Job-Namen, Schritt-Namen und der Zahl der Workflow-Dateien:

- `qualitaet-laeuft` - jeder Baum des Repositories laesst seine Qualitaetsbefehle laufen.
- `tests-je-baum` - jeder Baum laesst seine Tests laufen.
- `coverage-schwelle` - jeder Backend-`pytest`-Schritt sammelt Coverage und traegt keine eigene
  Schwelle; genau ein Schritt fuehrt `coverage combine` und `coverage report --fail-under>=80`
  aus, sein Job traegt `if: always()` und prueft die Shard-Ergebnisse, und seine `needs`-Menge
  ist mengengleich zur Menge der Jobs mit `pytest`-Schritt.
- `testmenge-vollstaendig` - kein Testschritt waehlt Testfaelle ab; `--splits`/`--group` und
  Playwrights `--shard` kommen aus `strategy.job-total`/`matrix.shard`, und die Matrix ist
  lueckenlos.
- `required-kontext-stabil` - die fuenf geforderten Job-Schluessel existieren ohne
  `name:`-Override; jeder Job mit Qualitaetsbefehl ist geforderter Kontext, liegt in der
  `needs`-Huelle eines solchen oder steht namentlich in der Ausnahmemenge.
- `nicht-ueberspringbar` - kein Qualitaetsschritt ist ueberspringbar oder nicht blockierend.
- `pr-ausloeser` - jeder Workflow mit Qualitaetsschritten laeuft auf `pull_request`.
- `cache-und-artefakte` - der Image-Cache wird nur hinter dem Fork-Ausschluss geschrieben, sein
  Scope ist ein Literal, kein Job traegt `permissions:`, kein Qualitaetsjob liest `secrets.*`,
  Coverage-Artefakte bleiben im selben Lauf, und die Gate-Version stammt aus `backend/uv.lock`.

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
GEFORDERTE_KONTEXTE = ("backend", "frontend", "docker-compose-check", "e2e", "demo-scripts")
# Die Branch Protection fuehrt fuenf Kontexte (specs/architecture/0003-securitykonzept.md). Der
# Job `eye` (Spec 0609) fuehrt `npm test` aus, ist aber bewusst keiner davon; ein weiterer
# Quality-Job ausserhalb der needs-Huelle waere dagegen ein Befund. Die Ausnahme steht deshalb
# namentlich hier, statt still uebergangen zu werden.
AUSGENOMMENE_QUALITAETSJOBS = frozenset({"eye"})
CACHE_LESE_DATEI = "docker-compose.ci-cache.yml"
CACHE_SCHREIB_DATEI = "docker-compose.ci-cache-write.yml"
SEKRETNAME = re.compile(r"(TOKEN|KEY|PASSWORD|SECRET)", re.IGNORECASE)
MODELL_MANIFEST = "backend/src/photosort/model_assets.py"
DOCKERIGNORE = "backend/.dockerignore"
BACKEND_DOCKERFILE = "backend/Dockerfile"
COVERAGE_FIXIERUNG = re.compile(r"coverage==\d")
OVERLAY_ZEILE = re.compile(
    r"^(services:"
    r"|  (backend|worker|frontend):"
    r"|    build:"
    r"|      (cache_from|cache_to):"
    r"|        - type=gha,scope=photosort-images(,mode=min)?)$"
)

QUALITAETS_BEFEHLE = re.compile(r"^(ruff|mypy|pytest|npm)\b")
JOB_KOPF = re.compile(r"^  (?P<key>[a-z][a-z0-9-]*):\s*$")
SCHRITT_BEGINN = re.compile(
    r"^      - (?P<key>name|run|uses|if|continue-on-error):\s*(?P<wert>.*)$"
)
EIGENSCHAFT = re.compile(r"^        (?P<key>name|run|uses|if|continue-on-error):\s*(?P<wert>.*)$")
MIT_KOPF = re.compile(r"^        with:\s*$")
MIT_EINTRAG = re.compile(r"^ {10}(?P<key>[A-Za-z0-9_.-]+):\s*(?P<wert>.*)$")
ARBEIT = re.compile(r"^        working-directory:\s*(?P<wert>\S+)\s*$")
UEBERSPRINGBAR = re.compile(r"^    (?P<key>if|continue-on-error):\s*(?P<wert>.*)$")
BLOCKMARKEN = {"|", ">", "|-", ">-"}

SPLITS = re.compile(r"--splits(?:=|\s+)\$\{\{\s*strategy\.job-total\s*\}\}")
GROUP = re.compile(r"--group(?:=|\s+)\$\{\{\s*matrix\.shard\s*\}\}")
PLAYWRIGHT_SHARD = re.compile(
    r"--shard(?:=|\s+)\$\{\{\s*matrix\.shard\s*\}\}/\$\{\{\s*strategy\.job-total\s*\}\}"
)
KURZE_AUSWAHL = ("-k", "-m", "-x")
LANGE_AUSWAHL = ("--deselect", "--ignore", "--last-failed", "--collect-only", "--maxfail")
PLAYWRIGHT_AUSWAHL = ("--grep", "--project")
NPM_TEST = re.compile(r"npm\s+(?:run\s+)?test(?:\s|$)")

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
        "Jeder Backend-`pytest`-Schritt sammelt Coverage (`--cov=photosort`) und traegt keine "
        "eigene Schwelle; genau ein Schritt fuehrt `coverage combine` und "
        "`coverage report --fail-under=<n>` mit n >= 80 aus. Dessen Job traegt `if: always()`, "
        "prueft die Shard-Ergebnisse ausdruecklich, hat dieselbe `needs`-Menge wie die Jobs mit "
        "`pytest`-Schritt und traegt kein `continue-on-error`.",
    ),
    Invariante(
        "testmenge-vollstaendig",
        "Kein Testschritt waehlt Testfaelle ab (`-k`, `-m`, `--deselect`, `--ignore`, "
        "`--last-failed`, `--collect-only`, `-x`, `--maxfail`); `--splits` kommt aus "
        "`strategy.job-total`, `--group` aus `matrix.shard`, die Shard-Matrix ist lueckenlos "
        "1..n, und Playwrights `--shard` stammt aus derselben Matrix - ohne `--grep`/`--project`.",
    ),
    Invariante(
        "required-kontext-stabil",
        "Die fuenf geforderten Job-Schluessel existieren ohne `name:`-Override; jeder Job mit "
        "Qualitaetsbefehl ist geforderter Kontext, liegt in der `needs`-Huelle eines solchen "
        "oder steht namentlich in der Ausnahmemenge.",
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
    Invariante(
        "cache-und-artefakte",
        "Coverage-Version im Aggregator stammt aus `backend/uv.lock`, und weder Dockerfiles noch "
        "`build.args` tragen einen secret-artigen Namen.",
    ),
    Invariante(
        "modell-assets-geprueft",
        "Jede Datei aus `MODEL_ASSETS` steht in `backend/.dockerignore`, und der Dockerfile ruft "
        "den SHA256-geprueften Download vor dem finalen Projekt-Install (`pip install ... "
        "--no-deps .`) auf - sonst fehlen die Assets beim Packaging oder stammen ungeprueft aus "
        "dem Build-Kontext.",
    ),
)

INVARIANTEN_IDS = frozenset(invariante.id for invariante in INVARIANTEN)


@dataclass(frozen=True)
class Schritt:
    """Ein Schritt: Name, Aktion, Text, Ort und seine Abschalter."""

    datei: str
    zeile: int
    name: str
    uses: str
    run: str
    run_zeile: int
    mit: tuple[tuple[int, str, str], ...]
    abschalter: tuple[tuple[int, str], ...]

    @property
    def befehlszeilen(self) -> tuple[str, ...]:
        return tuple(
            gestrichen
            for gestrichen in (zeile.strip() for zeile in self.run.split("\n"))
            if gestrichen and not gestrichen.startswith("#")
        )

    @property
    def ist_qualitaet(self) -> bool:
        return any(QUALITAETS_BEFEHLE.match(zeile) for zeile in self.befehlszeilen)

    def mit_wert(self, key: str) -> str | None:
        return next((wert for _, schluessel, wert in self.mit if schluessel == key), None)

    def mit_ort(self, key: str) -> int:
        return next((zeile for zeile, schluessel, _ in self.mit if schluessel == key), self.zeile)


@dataclass(frozen=True)
class Job:
    """Ein Job: Key, Arbeitsverzeichnis, Abhaengigkeiten, Matrix, Umgebung und Schritte."""

    datei: str
    zeile: int
    key: str
    arbeit: str
    needs: tuple[str, ...]
    needs_zeile: int
    matrix: tuple[tuple[str, tuple[str, ...]], ...]
    matrix_zeilen: tuple[tuple[str, int], ...]
    env: tuple[tuple[str, str], ...]
    roh: str
    schritte: tuple[Schritt, ...]
    abschalter: tuple[tuple[int, str], ...]

    def matrix_werte(self, achse: str) -> tuple[str, ...]:
        return dict(self.matrix).get(achse, ())

    def matrix_zeile(self, achse: str) -> int:
        return dict(self.matrix_zeilen).get(achse, self.zeile)

    def env_wert(self, name: str) -> str | None:
        return dict(self.env).get(name)

    @property
    def if_werte(self) -> tuple[str, ...]:
        return tuple(
            text.split(":", 1)[1].strip() for _, text in self.abschalter if text.startswith("if:")
        )

    @property
    def ist_qualitaetsjob(self) -> bool:
        return any(schritt.ist_qualitaet for schritt in self.schritte)


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


def _skalar(wert: str) -> str:
    return wert.strip().strip("'\"")


def _liste(wert: str) -> tuple[str, ...]:
    inhalt = wert.strip()
    if inhalt.startswith("[") and inhalt.endswith("]"):
        inhalt = inhalt[1:-1]
    return tuple(_skalar(teil) for teil in inhalt.split(",") if teil.strip())


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
    mit: list[tuple[int, str, str]] = []
    im_mit = False
    nummer = start

    def abschliessen() -> None:
        nonlocal im_mit
        if not eigenschaften:
            mit.clear()
            im_mit = False
            return
        name = next((wert.strip() for _, key, wert in eigenschaften if key == "name"), "")
        uses = next((wert.strip() for _, key, wert in eigenschaften if key == "uses"), "")
        run_paare = [(zeile, wert) for zeile, key, wert in eigenschaften if key == "run"]
        run_zeile, run = run_paare[0] if run_paare else (eigenschaften[0][0], "")
        schritte.append(
            Schritt(
                datei=datei,
                zeile=eigenschaften[0][0],
                name=name,
                uses=uses,
                run=run.strip(),
                run_zeile=run_zeile,
                mit=tuple(mit),
                abschalter=tuple(
                    (zeile, f"{key}: {wert.strip()}")
                    for zeile, key, wert in eigenschaften
                    if key in {"if", "continue-on-error"}
                ),
            )
        )
        eigenschaften.clear()
        mit.clear()
        im_mit = False

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
        if MIT_KOPF.match(zeile):
            im_mit = True
            nummer += 1
            continue
        if im_mit:
            eintrag = MIT_EINTRAG.match(zeile)
            if eintrag:
                mit.append((nummer + 1, eintrag.group("key"), eintrag.group("wert").strip()))
                nummer += 1
                continue
            if _eingerueckt(zeile) >= 10:
                nummer += 1
                continue
            im_mit = False
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
            # `with:`-Kinder, `env:`-Kinder und aehnliches tragen fuer die Wirkung nichts bei.
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
        if not zeile.strip() or zeile.lstrip().startswith("#"):
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
        needs: tuple[str, ...] = ()
        needs_zeile = 0
        matrix: dict[str, tuple[str, ...]] = {}
        matrix_zeilen: dict[str, int] = {}
        env: dict[str, str] = {}
        abschalter: list[tuple[int, str]] = []
        schritte: tuple[Schritt, ...] = ()
        roh: list[str] = [zeile]
        bereich = ""
        achse = ""
        while nummer < len(zeilen):
            zeile = zeilen[nummer]
            if zeile.strip() and _eingerueckt(zeile) <= 2:
                break
            roh.append(zeile)
            if not zeile.strip() or zeile.lstrip().startswith("#"):
                nummer += 1
                continue
            tiefe = _eingerueckt(zeile)
            treffer = ARBEIT.match(zeile)
            if treffer:
                arbeit = treffer.group("wert")
            if tiefe == 4:
                bereich = ""
                achse = ""
                gestrichen = zeile.strip()
                if gestrichen == "steps:":
                    schritte, ende = _schritte(datei, zeilen, nummer + 1)
                    roh.extend(zeilen[nummer + 1 : ende])
                    nummer = ende
                    continue
                treffer = UEBERSPRINGBAR.match(zeile)
                if treffer:
                    abschalter.append(
                        (nummer + 1, f"{treffer.group('key')}: {treffer.group('wert')}")
                    )
                if gestrichen.startswith("needs:"):
                    needs_zeile = nummer + 1
                    wert = gestrichen.split(":", 1)[1].strip()
                    if wert.startswith("["):
                        needs = _liste(wert)
                    elif wert:
                        needs = (_skalar(wert),)
                    else:
                        bereich = "needs"
                elif gestrichen.startswith("strategy:"):
                    bereich = "strategy"
                elif gestrichen == "env:":
                    bereich = "env"
                nummer += 1
                continue
            if tiefe == 6:
                gestrichen = zeile.strip()
                if bereich == "needs" and gestrichen.startswith("- "):
                    needs = (*needs, _skalar(gestrichen[2:]))
                elif bereich == "env":
                    key, _, wert = gestrichen.partition(":")
                    env[key.strip()] = _skalar(wert)
                elif bereich == "strategy" and gestrichen.startswith("matrix:"):
                    bereich = "matrix"
                nummer += 1
                continue
            if tiefe == 8 and bereich == "matrix":
                key, _, wert = zeile.strip().partition(":")
                achse = key.strip()
                matrix_zeilen[achse] = nummer + 1
                wert = wert.strip()
                if wert.startswith("["):
                    matrix[achse] = _liste(wert)
                    achse = ""
                elif not wert:
                    matrix[achse] = ()
                else:
                    matrix[achse] = (_skalar(wert),)
                    achse = ""
                nummer += 1
                continue
            if tiefe == 10 and bereich == "matrix" and achse and zeile.strip().startswith("- "):
                matrix[achse] = (*matrix[achse], _skalar(zeile.strip()[2:]))
                nummer += 1
                continue
            nummer += 1
        jobs.append(
            Job(
                datei=datei,
                zeile=job_zeile,
                key=passend.group("key"),
                arbeit=arbeit,
                needs=needs,
                needs_zeile=needs_zeile or job_zeile,
                matrix=tuple(matrix.items()),
                matrix_zeilen=tuple(matrix_zeilen.items()),
                env=tuple(env.items()),
                roh="\n".join(roh),
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
        if any(zeile.startswith(tuple(formen)) for zeile in schritt.befehlszeilen):
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


def _pytest_paare(work: tuple[Workflow, ...]) -> list[tuple[Job, Schritt]]:
    """Jeder `pytest`-Schritt der Backend-Jobs - mit seinem Job."""
    return [
        (job, schritt)
        for job in _jobs_je_baum(work, "backend")
        for schritt in job.schritte
        if any(zeile.startswith("pytest") for zeile in schritt.befehlszeilen)
    ]


def _coverage_schwelle(bestand: Bestand, work: tuple[Workflow, ...]) -> list[Befund]:
    if "backend/pyproject.toml" not in bestand:
        return []
    befunde: list[Befund] = []
    shard_paare = _pytest_paare(work)
    for _job, schritt in shard_paare:
        if "--cov-fail-under" in schritt.run:
            befunde.append(
                befund(
                    schritt.datei,
                    schritt.run_zeile,
                    "coverage-schwelle",
                    "Ein Testschritt traegt `--cov-fail-under` - die Schwelle gehoert auf die "
                    "Vereinigung aller Shards, nicht auf eine Teilmenge.",
                )
            )
        if "--cov=photosort" not in schritt.run:
            befunde.append(
                befund(
                    schritt.datei,
                    schritt.run_zeile,
                    "coverage-schwelle",
                    "Ein Backend-Testschritt sammelt keine Coverage (`--cov=photosort` fehlt).",
                )
            )
    pytest_jobs = {job.key for job, _ in shard_paare}
    if not pytest_jobs:
        return befunde

    gates: list[tuple[Job, Schritt, bool, list[str]]] = []
    for workflow in work:
        for job in workflow.jobs:
            for schritt in job.schritte:
                combine = any("coverage combine" in zeile for zeile in schritt.befehlszeilen)
                report = [zeile for zeile in schritt.befehlszeilen if "coverage report" in zeile]
                if combine or report:
                    gates.append((job, schritt, combine, report))
    if len(gates) != 1:
        ort = shard_paare[0][1]
        befunde.append(
            befund(
                ort.datei,
                ort.run_zeile,
                "coverage-schwelle",
                "Erwartet genau ein Schritt mit `coverage combine` und `coverage report "
                f"--fail-under={SCHWELLE}` - gefunden {len(gates)}.",
            )
        )
        return befunde

    job, schritt, combine, report = gates[0]
    if not combine:
        befunde.append(
            befund(
                schritt.datei,
                schritt.run_zeile,
                "coverage-schwelle",
                "Der Gate-Schritt fuehrt `coverage combine` nicht aus.",
            )
        )
    if not report:
        befunde.append(
            befund(
                schritt.datei,
                schritt.run_zeile,
                "coverage-schwelle",
                "Der Gate-Schritt bewertet die Vereinigung nicht (`coverage report` fehlt).",
            )
        )
    else:
        wert = next(
            (
                int(treffer.group(1))
                for zeile in report
                if (treffer := re.search(r"--fail-under=(\d+)", zeile))
            ),
            None,
        )
        if wert is None:
            befunde.append(
                befund(
                    schritt.datei,
                    schritt.run_zeile,
                    "coverage-schwelle",
                    f"`coverage report` traegt keine Schwelle - erwartet mindestens {SCHWELLE}.",
                )
            )
        elif wert < SCHWELLE:
            befunde.append(
                befund(
                    schritt.datei,
                    schritt.run_zeile,
                    "coverage-schwelle",
                    f"Die Gate-Schwelle {wert} liegt unter {SCHWELLE}.",
                )
            )
    if not any("always()" in wert.replace(" ", "") for wert in job.if_werte):
        befunde.append(
            befund(
                job.datei,
                job.zeile,
                "coverage-schwelle",
                "Der Gate-Job traegt kein `if: always()` - ein gescheiterter Shard wuerde ihn "
                "ueberspringen, und ein uebersprungener Job erfuellt keine Required-Pruefung.",
            )
        )
    if any("continue-on-error" in text for _, text in job.abschalter) or any(
        "continue-on-error" in text for _, text in schritt.abschalter
    ):
        befunde.append(
            befund(
                job.datei,
                job.zeile,
                "coverage-schwelle",
                "Der Gate-Job oder sein Gate-Schritt traegt `continue-on-error` - die Schwelle "
                "entscheidet dann nicht mehr ueber den Ausgang.",
            )
        )
    if set(job.needs) != pytest_jobs:
        befunde.append(
            befund(
                job.datei,
                job.needs_zeile,
                "coverage-schwelle",
                f"Die `needs` des Gate-Jobs {sorted(job.needs)} sind nicht mengengleich zu den "
                f"Jobs mit `pytest`-Schritt {sorted(pytest_jobs)}.",
            )
        )
    else:
        for name in sorted(pytest_jobs):
            if not any(
                f"needs.{name}.result" in zeile
                for kandidat in job.schritte
                for zeile in kandidat.befehlszeilen
            ):
                befunde.append(
                    befund(
                        schritt.datei,
                        schritt.run_zeile,
                        "coverage-schwelle",
                        f"Der Gate-Job prueft das Ergebnis von `{name}` nicht ausdruecklich "
                        f"(`needs.{name}.result` fehlt).",
                    )
                )
    return befunde


def _flag(zeile: str, name: str) -> bool:
    return re.search(rf"(?:^|\s){re.escape(name)}(?=\s|=|$)", zeile) is not None


def _testmenge_vollstaendig(work: tuple[Workflow, ...]) -> list[Befund]:
    befunde: list[Befund] = []
    for workflow in work:
        for job in workflow.jobs:
            for schritt in job.schritte:
                for zeile in schritt.befehlszeilen:
                    pytest_zeile = zeile.startswith("pytest")
                    npm_test = NPM_TEST.match(zeile) is not None
                    if not (pytest_zeile or npm_test):
                        continue
                    for flag in (*KURZE_AUSWAHL, *LANGE_AUSWAHL):
                        if _flag(zeile, flag):
                            befunde.append(
                                befund(
                                    schritt.datei,
                                    schritt.run_zeile,
                                    "testmenge-vollstaendig",
                                    f"`{flag}` waehlt Testfaelle ab - die Pruefung fuehrt die "
                                    "gesamte Testmenge aus.",
                                )
                            )
                    if npm_test:
                        for flag in PLAYWRIGHT_AUSWAHL:
                            if _flag(zeile, flag):
                                befunde.append(
                                    befund(
                                        schritt.datei,
                                        schritt.run_zeile,
                                        "testmenge-vollstaendig",
                                        f"`{flag}` waehlt Browser-Faelle ab.",
                                    )
                                )
                    if pytest_zeile:
                        for flag, muster in (("--splits", SPLITS), ("--group", GROUP)):
                            if _flag(zeile, flag) and muster.search(zeile) is None:
                                befunde.append(
                                    befund(
                                        schritt.datei,
                                        schritt.run_zeile,
                                        "testmenge-vollstaendig",
                                        f"`{flag}` ist nicht an "
                                        "`strategy.job-total`/`matrix.shard` gebunden.",
                                    )
                                )
                    if npm_test and _flag(zeile, "--shard") and not PLAYWRIGHT_SHARD.search(zeile):
                        befunde.append(
                            befund(
                                schritt.datei,
                                schritt.run_zeile,
                                "testmenge-vollstaendig",
                                "Playwrights `--shard` ist nicht an "
                                "`matrix.shard`/`strategy.job-total` gebunden.",
                            )
                        )

            werte = job.matrix_werte("shard")
            if not werte:
                continue
            zahlen = sorted(int(wert) if wert.isdigit() else -1 for wert in werte)
            if zahlen != list(range(1, len(werte) + 1)):
                befunde.append(
                    befund(
                        job.datei,
                        job.matrix_zeile("shard"),
                        "testmenge-vollstaendig",
                        f"Die Shard-Matrix {list(werte)} ist nicht lueckenlos 1..{len(werte)}.",
                    )
                )
            test_schritte = [
                schritt
                for schritt in job.schritte
                if any(
                    zeile.startswith("pytest") or NPM_TEST.match(zeile)
                    for zeile in schritt.befehlszeilen
                )
            ]
            if not test_schritte:
                befunde.append(
                    befund(
                        job.datei,
                        job.zeile,
                        "testmenge-vollstaendig",
                        f"Job '{job.key}' traegt eine Shard-Matrix, aber keinen Testschritt.",
                    )
                )
            for schritt in test_schritte:
                for zeile in schritt.befehlszeilen:
                    if zeile.startswith("pytest"):
                        fehlt = [
                            flag
                            for flag, muster in (("--splits", SPLITS), ("--group", GROUP))
                            if muster.search(zeile) is None
                        ]
                    else:
                        fehlt = [] if PLAYWRIGHT_SHARD.search(zeile) else ["--shard"]
                    if fehlt:
                        befunde.append(
                            befund(
                                schritt.datei,
                                schritt.run_zeile,
                                "testmenge-vollstaendig",
                                f"Ein Shard-Testschritt traegt {fehlt} nicht in der Form aus "
                                "`strategy.job-total`/`matrix.shard`.",
                            )
                        )
    return befunde


def _needs_huelle(jobs: dict[str, Job]) -> set[str]:
    """Die transitive `needs`-Huelle der geforderten Kontexte."""
    huelle: set[str] = set()
    offen = [key for key in GEFORDERTE_KONTEXTE if key in jobs]
    while offen:
        key = offen.pop()
        for abhaengig in jobs[key].needs:
            if abhaengig in huelle:
                continue
            huelle.add(abhaengig)
            if abhaengig in jobs:
                offen.append(abhaengig)
    return huelle


def _required_kontext_stabil(work: tuple[Workflow, ...]) -> list[Befund]:
    befunde: list[Befund] = []
    for workflow in work:
        if not any(job.ist_qualitaetsjob for job in workflow.jobs):
            # pr-titel und release-please tragen keinen Qualitaetsbefehl und damit den Vertrag
            # der fuenf Kontexte nicht.
            continue
        jobs = {job.key: job for job in workflow.jobs}
        for key in GEFORDERTE_KONTEXTE:
            if key in jobs:
                continue
            naechster = next((job for job in workflow.jobs if job.key.startswith(key)), None)
            befunde.append(
                befund(
                    workflow.datei,
                    naechster.zeile if naechster is not None else workflow.on_zeile,
                    "required-kontext-stabil",
                    f"Der geforderte Kontext `{key}` fehlt als Job-Schluessel - ein Required "
                    "Check bliebe auf 'Expected' stehen.",
                )
            )
        for key in GEFORDERTE_KONTEXTE:
            job = jobs.get(key)
            if job is None:
                continue
            if re.search(r"(?m)^    name:", job.roh):
                befunde.append(
                    befund(
                        job.datei,
                        job.zeile,
                        "required-kontext-stabil",
                        f"Job `{key}` traegt einen `name:`-Override - der Check heisst dann "
                        "anders als der geforderte Kontext.",
                    )
                )
        huelle = _needs_huelle(jobs)
        for job in workflow.jobs:
            if not job.ist_qualitaetsjob:
                continue
            if job.key in GEFORDERTE_KONTEXTE or job.key in huelle:
                continue
            if job.key in AUSGENOMMENE_QUALITAETSJOBS:
                continue
            befunde.append(
                befund(
                    job.datei,
                    job.zeile,
                    "required-kontext-stabil",
                    f"Job `{job.key}` fuehrt Qualitaetsbefehle aus, ist aber kein geforderter "
                    "Kontext und liegt in keiner `needs`-Huelle eines solchen - ein Fehlschlag "
                    "blockiert keinen Merge.",
                )
            )
    return befunde


def _nicht_ueberspringbar(work: tuple[Workflow, ...]) -> list[Befund]:
    befunde: list[Befund] = []
    for workflow in work:
        for job in workflow.jobs:
            if not job.ist_qualitaetsjob:
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
                if not schritt.ist_qualitaet:
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
        traegt_qualitaet = any(job.ist_qualitaetsjob for job in workflow.jobs)
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


def _overlay_befunde(datei: str, text: str) -> list[Befund]:
    befunde: list[Befund] = []
    for nummer, zeile in enumerate(text.split("\n"), 1):
        if not zeile.strip() or zeile.lstrip().startswith("#"):
            continue
        if not OVERLAY_ZEILE.match(zeile):
            befunde.append(
                befund(
                    datei,
                    nummer,
                    "cache-und-artefakte",
                    "Das Cache-Overlay ist nicht inhaltsgeschlossen - erlaubt sind nur "
                    "`services.*.build.cache_from`/`cache_to` mit Scope-Literal.",
                )
            )
        for treffer in re.finditer(r"scope=([^,\s]+)", zeile):
            if "${{" in treffer.group(1):
                befunde.append(
                    befund(
                        datei,
                        nummer,
                        "cache-und-artefakte",
                        "Der Cache-Scope ist kein Literal - ein fremder PR koennte ihn waehlen.",
                    )
                )
    return befunde


def _build_arg_schluessel(text: str) -> list[tuple[int, str]]:
    """Die Schluesselnamen unter `services.*.build.args` einer Compose-Datei."""
    ergebnis: list[tuple[int, str]] = []
    im_build = False
    im_args = False
    args_tiefe = 0
    for nummer, zeile in enumerate(text.split("\n"), 1):
        gestrichen = zeile.strip()
        if not gestrichen or gestrichen.startswith("#"):
            continue
        tiefe = _eingerueckt(zeile)
        if gestrichen.startswith("build:"):
            im_build = True
            im_args = False
            continue
        if im_build and gestrichen.startswith("args:"):
            im_args = True
            args_tiefe = tiefe
            continue
        if im_args:
            if tiefe <= args_tiefe:
                im_args = False
                im_build = False
            else:
                ergebnis.append((nummer, gestrichen.split(":", 1)[0].strip()))
                continue
        if im_build and tiefe <= 4:
            im_build = False
    return ergebnis


def _cache_und_artefakte(bestand: Bestand, work: tuple[Workflow, ...]) -> list[Befund]:
    befunde: list[Befund] = []
    for datei, text in sorted(bestand.items()):
        if not datei.endswith((".yml", ".yaml")) or datei == CACHE_SCHREIB_DATEI:
            continue
        for nummer, zeile in enumerate(text.split("\n"), 1):
            if zeile.lstrip().startswith("#"):
                continue
            if "cache_to" in zeile:
                befunde.append(
                    befund(
                        datei,
                        nummer,
                        "cache-und-artefakte",
                        "`cache_to` steht nur im Schreib-Overlay "
                        "`docker-compose.ci-cache-write.yml`, das ausschliesslich hinter dem "
                        "Fork-Ausschluss haengt.",
                    )
                )

    for datei in (CACHE_LESE_DATEI, CACHE_SCHREIB_DATEI):
        if datei not in bestand:
            befunde.append(
                befund(
                    work[0].datei,
                    work[0].on_zeile,
                    "cache-und-artefakte",
                    f"Das Cache-Overlay `{datei}` fehlt - die Images bauen dann ohne Cache.",
                )
            )
            continue
        befunde.extend(_overlay_befunde(datei, bestand[datei]))

    schreib_stellen = [
        (job, schritt)
        for workflow in work
        for job in workflow.jobs
        for schritt in job.schritte
        if CACHE_SCHREIB_DATEI in schritt.run
    ]
    if len(schreib_stellen) != 1:
        befunde.append(
            befund(
                work[0].datei,
                work[0].on_zeile,
                "cache-und-artefakte",
                f"Das Schreib-Overlay wird an {len(schreib_stellen)} Stellen gesetzt - erwartet "
                "genau eine, hinter dem Fork-Ausschluss.",
            )
        )
    for _job, schritt in schreib_stellen:
        if "GITHUB_ENV" not in schritt.run or "CACHE_SCHREIBEN" not in schritt.run:
            befunde.append(
                befund(
                    schritt.datei,
                    schritt.run_zeile,
                    "cache-und-artefakte",
                    "Der Schreibpfad wird nicht als `$GITHUB_ENV`-Bedingung gesetzt - ein "
                    "`if:` am Build-Schritt waere der verbotene Weg.",
                )
            )
        if "head.repo.fork" not in schritt.run or '!= "true"' not in schritt.run:
            befunde.append(
                befund(
                    schritt.datei,
                    schritt.run_zeile,
                    "cache-und-artefakte",
                    "Der Fork-Ausschluss fehlt: `github.event.pull_request.head.repo.fork` muss "
                    "den Schreibpfad sperren.",
                )
            )
        if schritt.abschalter:
            befunde.append(
                befund(
                    schritt.datei,
                    schritt.abschalter[0][0],
                    "cache-und-artefakte",
                    "Der Fork-Ausschluss steht als `if:` am Schritt statt als "
                    "`$GITHUB_ENV`-Bedingung.",
                )
            )
    # Das Schreib-Literal (`cache-to=type=gha…`) steht an genau einer Stelle, und zwar im
    # Schreibpfad-Schritt hinter dem Fork-Ausschluss. Der Bake-Aufruf selbst darf es nicht
    # tragen: ein Literal am Build-Schritt schriebe auch fuer Fork-Pull-Requests.
    literale = [
        (job, schritt, nummer)
        for workflow in work
        for job in workflow.jobs
        for schritt in job.schritte
        for nummer, zeile in enumerate(schritt.run.split("\n"), schritt.run_zeile + 1)
        if "cache-to=type=gha" in zeile
    ]
    erlaubt = {(job.key, schritt.zeile) for job, schritt in schreib_stellen}
    ausserhalb = [
        (job, schritt, nummer)
        for job, schritt, nummer in literale
        if (job.key, schritt.zeile) not in erlaubt
    ]
    if len(literale) != 1 or ausserhalb:
        if ausserhalb:
            ort_job, ort_schritt, ort_nummer = ausserhalb[0]
        elif literale:
            ort_job, ort_schritt, ort_nummer = literale[0]
        else:
            ort_job, ort_schritt = schreib_stellen[0]
            ort_nummer = ort_schritt.run_zeile
        befunde.append(
            befund(
                ort_job.datei,
                ort_nummer,
                "cache-und-artefakte",
                "Das Cache-Schreib-Literal (`cache-to=type=gha…`) steht nicht an genau einer "
                "Stelle im Fork-geschuetzten Schreibpfad-Schritt.",
            )
        )

    for workflow in work:
        for job in workflow.jobs:
            for index, zeile in enumerate(job.roh.split("\n")):
                if re.match(r"^    permissions:", zeile):
                    befunde.append(
                        befund(
                            job.datei,
                            job.zeile + index,
                            "cache-und-artefakte",
                            f"Job `{job.key}` traegt einen eigenen `permissions:`-Block - die "
                            "Workflow-Rechte bleiben `contents: read`.",
                        )
                    )
            if job.ist_qualitaetsjob and "secrets." in job.roh:
                befunde.append(
                    befund(
                        job.datei,
                        job.zeile,
                        "cache-und-artefakte",
                        f"Job `{job.key}` liest `secrets.*` und traegt einen Qualitaetsbefehl.",
                    )
                )
            for schritt in job.schritte:
                if "download-artifact" in schritt.uses:
                    for key in ("run-id", "github-token"):
                        if schritt.mit_wert(key):
                            befunde.append(
                                befund(
                                    schritt.datei,
                                    schritt.mit_ort(key),
                                    "cache-und-artefakte",
                                    f"`download-artifact` traegt `{key}` - Coverage-Daten "
                                    "duerfen nur aus demselben Workflow-Lauf stammen.",
                                )
                            )
                if "download-artifact" in schritt.uses or "upload-artifact" in schritt.uses:
                    for key in ("name", "pattern"):
                        wert = schritt.mit_wert(key) or ""
                        if "head_ref" in wert or "ref_name" in wert:
                            befunde.append(
                                befund(
                                    schritt.datei,
                                    schritt.mit_ort(key),
                                    "cache-und-artefakte",
                                    f"Artefakt-{key} enthaelt `head_ref`/`ref_name` - Namen "
                                    "tragen nur Workflow-Literale und `matrix.*`.",
                                )
                            )
                if "gh run download" in schritt.run:
                    befunde.append(
                        befund(
                            schritt.datei,
                            schritt.run_zeile,
                            "cache-und-artefakte",
                            "`gh run download` zieht fremde Laeufe heran - Artefakte bleiben im "
                            "selben Workflow-Lauf.",
                        )
                    )

    gate_jobs = {
        job.key: job
        for workflow in work
        for job in workflow.jobs
        if any("coverage combine" in schritt.run for schritt in job.schritte)
    }
    for key, job in sorted(gate_jobs.items()):
        if "uv.lock" not in job.roh or "tomllib" not in job.roh:
            befunde.append(
                befund(
                    job.datei,
                    job.zeile,
                    "cache-und-artefakte",
                    f"Der Gate-Job `{key}` leitet die Coverage-Version nicht aus "
                    "`backend/uv.lock` ab - ein zweiter Pin liesse den Entscheider ohne "
                    "Repo-Diff wechseln.",
                )
            )
    for workflow in work:
        for job in workflow.jobs:
            for schritt in job.schritte:
                if COVERAGE_FIXIERUNG.search(schritt.run):
                    befunde.append(
                        befund(
                            schritt.datei,
                            schritt.run_zeile,
                            "cache-und-artefakte",
                            "`coverage` ist hart fixiert - die Version kommt aus `backend/uv.lock`.",
                        )
                    )

    for datei, text in sorted(bestand.items()):
        if "docker-compose" in datei and datei.endswith((".yml", ".yaml")):
            for nummer, key in _build_arg_schluessel(text):
                if SEKRETNAME.search(key):
                    befunde.append(
                        befund(
                            datei,
                            nummer,
                            "cache-und-artefakte",
                            f"`build.args` traegt den secret-artigen Namen `{key}`.",
                        )
                    )
        if datei.rsplit("/", 1)[-1].startswith("Dockerfile"):
            for nummer, zeile in enumerate(text.split("\n"), 1):
                treffer = re.match(r"\s*(?:ARG|ENV)\s+([A-Za-z0-9_]+)", zeile)
                if treffer and SEKRETNAME.search(treffer.group(1)):
                    befunde.append(
                        befund(
                            datei,
                            nummer,
                            "cache-und-artefakte",
                            f"Dockerfile traegt den secret-artigen Namen `{treffer.group(1)}` "
                            "als `ARG`/`ENV`.",
                        )
                    )
    return befunde


def _modell_assets_geprueft(bestand: Bestand) -> list[Befund]:
    """Download vor dem finalen Projekt-Install; keine .onnx aus dem Build-Kontext."""
    if MODELL_MANIFEST not in bestand or BACKEND_DOCKERFILE not in bestand:
        return []
    befunde: list[Befund] = []
    dateinamen = re.findall(r'filename="([^"]+)"', bestand[MODELL_MANIFEST])
    if not dateinamen:
        return [
            befund(
                MODELL_MANIFEST,
                1,
                "modell-assets-geprueft",
                "Kein Asset im Manifest gelesen - die Pruefung waere leer wahr.",
            )
        ]
    ignore_zeilen = bestand.get(DOCKERIGNORE, "").split("\n")
    for name in dateinamen:
        pfad = f"src/photosort/assets/{name}"
        nummer = next(
            (zeile for zeile, text in enumerate(ignore_zeilen, 1) if pfad in text),
            0,
        )
        aktiv = nummer > 0 and not ignore_zeilen[nummer - 1].lstrip().startswith("#")
        if not aktiv:
            befunde.append(
                befund(
                    DOCKERIGNORE,
                    nummer or 1,
                    "modell-assets-geprueft",
                    f"`{pfad}` fehlt in `backend/.dockerignore` (oder ist auskommentiert) - ein "
                    "lokaler Build-Kontext ueberschriebe dann den SHA256-geprueften Download mit "
                    "einer ungeprueften Kopie.",
                )
            )
    dockerfile = bestand[BACKEND_DOCKERFILE].split("\n")
    # Nur `RUN`-Zeilen tragen die Reihenfolge: Das `COPY scripts/fetch_model_assets.py` nennt
    # denselben Dateinamen, ist aber kein Download.
    run_zeilen = [
        (zeile, text) for zeile, text in enumerate(dockerfile, 1) if re.match(r"^\s*RUN\b", text)
    ]
    downloads = [zeile for zeile, text in run_zeilen if "fetch_model_assets.py" in text]
    installs = [
        zeile for zeile, text in run_zeilen if "pip install" in text and "--no-deps ." in text
    ]
    if not downloads:
        return [
            *befunde,
            befund(
                BACKEND_DOCKERFILE,
                1,
                "modell-assets-geprueft",
                "Der Dockerfile ruft `scripts/fetch_model_assets.py` in keiner `RUN`-Zeile auf - "
                "die Assets kaemen dann aus dem Build-Kontext statt aus dem geprueften Download.",
            ),
        ]
    if not installs:
        return [
            *befunde,
            befund(
                BACKEND_DOCKERFILE,
                1,
                "modell-assets-geprueft",
                "Kein finaler Projekt-Install (`pip install ... --no-deps .`) gefunden - die "
                "Reihenfolge des Downloads laesst sich dann nicht pruefen.",
            ),
        ]
    install = installs[-1]
    for download in downloads:
        if download > install:
            befunde.append(
                befund(
                    BACKEND_DOCKERFILE,
                    download,
                    "modell-assets-geprueft",
                    "Der gepruefte Asset-Download steht nach dem finalen Projekt-Install - die "
                    "Assets fehlen dann beim Packaging ueber `[tool.setuptools.package-data]`.",
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
    befunde.extend(_testmenge_vollstaendig(work))
    befunde.extend(_required_kontext_stabil(work))
    befunde.extend(_nicht_ueberspringbar(work))
    befunde.extend(_pr_ausloeser(work))
    befunde.extend(_cache_und_artefakte(bestand, work))
    befunde.extend(_modell_assets_geprueft(bestand))
    return befunde


def test_der_bestand_erfuellt_alle_invarianten() -> None:
    """Der lebende Bestand haelt jede Invariante; die Verletzungsfaelle belegt `mutationen.py`."""
    befunde = pruefe(Bestand.aus_arbeitsbaum())

    assert not befunde, "CI-Befunde: " + "; ".join(f.meldung for f in befunde)


def test_ein_bestand_ohne_workflow_scheitert_laut() -> None:
    """Kein Workflow heisst: der Pruefraum ist leer - das ist ein Befund ueber den Leser."""
    with pytest.raises(ValueError, match="kein Workflow"):
        pruefe(Bestand({"README.md": "kein Workflow"}))
