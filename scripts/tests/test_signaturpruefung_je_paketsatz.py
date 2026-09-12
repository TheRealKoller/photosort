r"""Jeder npm-Paketsatz des Repositoriums wird im Pruefauf signaturgeprueft installiert.

**Was gilt.** Ein *Paketsatz* ist ein von Git verwaltetes `package-lock.json` ausserhalb von
`node_modules` (heute `frontend` und `e2e`). Fuer jeden gilt in `.github/workflows/ci.yml`:
mindestens ein Schritt mit `npm ci` in seinem wirksamen Arbeitsverzeichnis, und **jeder** solche
Schritt hat als unmittelbaren Nachfolger im **selben Job** einen Schritt mit der `run:`-Nutzlast
genau `npm audit signatures` im **selben** wirksamen Arbeitsverzeichnis, ohne `if:`, ohne
`continue-on-error` und ohne `|| true` - alle drei liessen den Job gruen melden, obwohl die
Pruefung nicht greift. Die ersten beiden gelten auf **beiden** Ebenen, Schritt und Job: `if:` am
Job ueberspringt ihn ("skipped" statt rot), `continue-on-error` am Job entschaerft ihn. Dazu
traegt jeder Lockfile-Eintrag ausser dem Wurzeleintrag ein `resolved` unter
`https://registry.npmjs.org/` und ein `integrity`: Ein `file:`- oder `git+https:`-Eintrag waere
ein ungeprueftes Paket innerhalb eines geprueften Paketsatzes, denn `npm audit signatures`
ueberspringt ihn **still** und meldet Exit 0.

**Wofuer.** Die Paketsatzmenge wird abgeleitet (`git ls-files -z`), nicht gepflegt; es gibt keine
Ausnahmeliste, auch keine leere vorbereitete. Der Installationsaufruf in `frontend/Dockerfile` ist
ausdruecklich nicht erfasst (ADR 0088 Abschnitt 5, dort steht die Abwaegung dieser Ausnahme).
"Unmittelbar" ist eine Aussage ueber **Schritte**: Kommentar- und Leerzeilen zwischen beiden
brechen die Nachbarschaft nicht, ein dazwischengeschobener Schritt und eine Job-Grenze sehr wohl.
Das wirksame Arbeitsverzeichnis kommt aus zwei Quellen - dem Schritt selbst oder
`defaults.run.working-directory` des Jobs. Die dritte Quelle (`defaults:` auf Workflow-Ebene) wird
nicht unterstuetzt, sondern ihre Abwesenheit zugesichert; sonst rechnete der Leser nach einer
Umstellung weiter und lieferte ein Ergebnis, das niemand mehr als falsch erkennt.

**Bei Verletzung** wird der Job `demo-scripts` rot. Ein kuenftiger dritter Paketsatz faerbt ihn
rot, bis das Schritt-Paar ergaenzt ist - die Aufnahme wird entschieden, statt einzusickern.

**Nicht zugesichert:** dass die installierten Bytes zur geprueften Signatur gehoeren - `resolved`
und `integrity` gehen nicht in `npm audit signatures` ein. Ebenso nicht, dass der Schritt vor
jeder Ausfuehrung fremden Codes liegt: `npm ci` fuehrt Installationsskripte aus, bevor er laeuft.

**Selbstschutz.** Der Erfolgsfall ist "nichts gefunden", und der Struktur-Leser hier baut Jobs und
Schritte auf statt Zeilen zu filtern - ein Leser, der bei einem Defekt *nichts* zurueckgibt,
machte jede Abwesenheits-Assertion leer-gruen. Deshalb: Positiv-Assertions ueber die gelesene
Struktur (Zahl der Jobs, Schrittzahl je Job, Index des Signaturschritts), ein lautes `ValueError`
bei leerem Suchraum, und Gegenproben am zur Laufzeit **mutierten Textabbild des echten**
`ci.yml` - keine eingecheckte Fixture-Kopie, die still auseinanderliefe.

Textbasiert ohne YAML-Bibliothek wie die Nachbartests in diesem Verzeichnis. Kein Netz, keine
Ausfuehrung von Repository-Inhalt: gelesen werden Dateien dieses Repositoriums und `git ls-files`.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_WURZEL = Path(__file__).parents[2]
CI_WORKFLOW_NAME = ".github/workflows/ci.yml"
CI_WORKFLOW_PFAD = REPO_WURZEL / ".github" / "workflows" / "ci.yml"

LOCKFILE_NAME = "package-lock.json"
REGISTRY_PRAEFIX = "https://registry.npmjs.org/"

# Die Nutzlast des Signaturschritts, exakt: kein zusaetzliches Flag, keine Provenance-Forderung,
# keine Herabsetzung der Pruefstufe - und kein `|| true`, das hier als Nutzlast-Abweichung faellt.
SIGNATUR_NUTZLAST = "npm audit signatures"

# Erkennungsregel Installationsschritt: die ersten zwei Token einer Befehlszeile sind `npm ci`.
# Ein Muster auf dem Wort `install` statt auf den ersten Token schluege bei
# `npx playwright install --with-deps chromium` an.
_NPM_CI = re.compile(r"^npm\s+ci(?:\s|$)")
_NPM_INSTALLATIONSFAMILIE = re.compile(r"^npm\s+(?:ci|i|install|add)(?:\s|$)")
_SIGNATURAUFRUF = re.compile(r"^npm\s+audit\s+signatures(?:\s|$)")

_SCHLUESSEL = re.compile(r"^(?P<name>[A-Za-z0-9_.-]+):(?P<wert>.*)$")
_BLOCKSKALAR = re.compile(r"^(?P<art>[|>])[+-]?[0-9]*$")

# Positiv-Assertions ueber die gelesene Struktur. Die Mindestzahlen fangen den realistischen
# Leser-Defekt (nichts oder fast nichts gelesen); die exakten Schrittzahlen und Indizes stehen
# fuer die beiden Jobs, die die Zusicherung tragen.
MINDESTZAHL_JOBS = 5
MINDESTSCHRITTE_JE_JOB = 5
PFLICHT_JOBS = ("backend", "frontend", "demo-scripts", "docker-compose-check", "e2e")
PFLICHT_PAKETSAETZE = ("frontend", "e2e")
ERWARTETE_SCHRITTZAHL = {"frontend": 9, "e2e": 17}
ERWARTETER_INSTALLATIONSINDEX = {"frontend": 2, "e2e": 6}


# --- Leser: Zeilen, Bloecke, Schluessel --------------------------------------------------------


def wirksame_zeilen(text: str) -> list[str]:
    """Ersetzt ganzzeilige Kommentare durch Leerzeilen, laesst alles andere unberuehrt.

    Kommentarzeilen werden zu Leerzeilen statt entfernt, damit gemeldete Zeilennummern denen der
    echten Datei entsprechen. Nebeneffekt, der hier tragend ist: Ein Kommentar zwischen zwei
    Schritten kann die Nachbarschaft gar nicht brechen.
    """
    return ["" if zeile.lstrip().startswith("#") else zeile for zeile in text.splitlines()]


def nummerierte_zeilen(text: str) -> list[tuple[int, str]]:
    """(1-basierte Zeilennummer der echten Datei, wirksame Zeile)."""
    return list(enumerate(wirksame_zeilen(text), start=1))


def _pruefe_nicht_leer(menge: object, was: str) -> None:
    if not menge:
        raise ValueError(
            f"0 {was} im Suchraum: Damit ist die Zusicherung ungeprueft. Entweder lief die "
            "Ableitung im falschen Arbeitsverzeichnis, oder sie ist kaputt - ein leerer "
            "Suchraum darf nie als 'nichts gefunden' durchgehen."
        )


def _einrueckung(zeile: str) -> int:
    return len(zeile) - len(zeile.lstrip(" "))


def _oberste_ebene(zeilen: Sequence[tuple[int, str]]) -> int:
    tiefen = [_einrueckung(text) for _, text in zeilen if text.strip()]
    _pruefe_nicht_leer(tiefen, "wirksame Zeilen")
    return min(tiefen)


@dataclass(frozen=True)
class Eintrag:
    """Ein Schluessel auf der obersten Ebene eines Blocks, mit Inline-Wert und Unterblock."""

    name: str
    wert: str
    unterblock: tuple[tuple[int, str], ...]
    nummer: int


def _eintraege(zeilen: Sequence[tuple[int, str]]) -> list[Eintrag]:
    """Zerlegt einen Block in seine Schluessel der obersten Ebene.

    Alles, was tiefer eingerueckt ist als der Schluessel, gehoert zu dessen Unterblock - damit
    faellt der Inhalt eines Blockskalars (`run: |`) nicht mehr als eigener Schluessel auf. Ohne
    diese Trennung lasen die Muster unten in einem Shell-Skript mit, was dort nur Text ist.
    """
    if not zeilen:
        return []

    ebene = _oberste_ebene(zeilen)
    eintraege: list[Eintrag] = []
    index = 0
    while index < len(zeilen):
        nummer, text = zeilen[index]
        index += 1
        if not text.strip() or _einrueckung(text) != ebene:
            continue
        treffer = _SCHLUESSEL.match(text.strip())
        if treffer is None:
            continue
        unterblock: list[tuple[int, str]] = []
        while index < len(zeilen) and (
            not zeilen[index][1].strip() or _einrueckung(zeilen[index][1]) > ebene
        ):
            unterblock.append(zeilen[index])
            index += 1
        eintraege.append(
            Eintrag(
                name=treffer["name"],
                wert=treffer["wert"].strip(),
                unterblock=tuple(unterblock),
                nummer=nummer,
            )
        )
    return eintraege


def _eintrag(zeilen: Sequence[tuple[int, str]], name: str) -> Eintrag | None:
    for eintrag in _eintraege(zeilen):
        if eintrag.name == name:
            return eintrag
    return None


def _skalar(wert: str) -> str:
    return wert.strip().strip("\"'")


def _nutzlast(eintrag: Eintrag) -> str:
    """Die `run:`-Nutzlast: einzeiliger Skalar oder Blockskalar, Zeile fuer Zeile."""
    treffer = _BLOCKSKALAR.match(eintrag.wert)
    if eintrag.wert and treffer is None:
        return eintrag.wert
    zeilen = [text.strip() for _, text in eintrag.unterblock if text.strip()]
    # Gefaltete Blockskalare (`>`) fuegt YAML zu EINER Zeile zusammen - ein `npm` am Zeilenende
    # und ein `ci` in der Folgezeile sind dort derselbe Befehl. Ohne diese Unterscheidung saehe
    # der Leser zwei Zeilen und keinen Installationsschritt.
    if treffer is not None and treffer["art"] == ">":
        return " ".join(zeilen)
    return "\n".join(zeilen)


# --- Leser: Jobs und Schritte ------------------------------------------------------------------


@dataclass(frozen=True)
class Schritt:
    index: int
    beginn: int
    ende: int
    run: str | None
    working_directory: str | None
    schluessel: tuple[str, ...]

    @property
    def befehlszeilen(self) -> tuple[str, ...]:
        if self.run is None:
            return ()
        return tuple(
            zeile.strip()
            for zeile in self.run.splitlines()
            if zeile.strip() and not zeile.strip().startswith("#")
        )

    @property
    def ist_installation(self) -> bool:
        return any(_NPM_CI.match(zeile) for zeile in self.befehlszeilen)

    @property
    def ist_aus_der_installationsfamilie(self) -> bool:
        return any(_NPM_INSTALLATIONSFAMILIE.match(zeile) for zeile in self.befehlszeilen)

    @property
    def ist_signaturpruefung(self) -> bool:
        return any(_SIGNATURAUFRUF.match(zeile) for zeile in self.befehlszeilen)


@dataclass(frozen=True)
class Job:
    name: str
    beginn: int
    defaults_working_directory: str | None
    schritte: tuple[Schritt, ...]
    schluessel: tuple[str, ...]

    def wirksames_verzeichnis(self, schritt: Schritt) -> str:
        """Schritt-`working-directory`, sonst `defaults.run.working-directory`, sonst Repo-Wurzel."""
        roh = (
            schritt.working_directory
            if schritt.working_directory is not None
            else self.defaults_working_directory
        )
        return normalisiertes_verzeichnis(roh)


def normalisiertes_verzeichnis(wert: str | None) -> str:
    """`./frontend`, `frontend/` und `frontend/.` sind dasselbe; `frontends` ist es nicht.

    `None` (keine der beiden Quellen) ist die Repo-Wurzel und damit ein eigener, vergleichbarer
    Wert - nicht dieselbe Zeichenkette wie ein fehlender Eintrag.
    """
    if wert is None:
        return "."
    teile = [teil for teil in _skalar(wert).split("/") if teil not in ("", ".")]
    return "/".join(teile) or "."


def _schritt_aus_gruppe(index: int, gruppe: Sequence[tuple[int, str]]) -> Schritt:
    nummer, text = gruppe[0]
    strich = text.index("-")
    # Der Listenstrich wird durch ein Leerzeichen ersetzt: danach liegen alle Schluessel des
    # Schrittes auf derselben Einrueckung, auch der auf der Strichzeile.
    normalisiert = [(nummer, f"{text[:strich]} {text[strich + 1 :]}"), *gruppe[1:]]

    run: str | None = None
    verzeichnis: str | None = None
    schluessel: list[str] = []
    for eintrag in _eintraege(normalisiert):
        schluessel.append(eintrag.name)
        if eintrag.name == "run":
            run = _nutzlast(eintrag)
        elif eintrag.name == "working-directory":
            verzeichnis = _skalar(eintrag.wert)

    return Schritt(
        index=index,
        beginn=nummer,
        ende=max(n for n, t in gruppe if t.strip()),
        run=run,
        working_directory=verzeichnis,
        schluessel=tuple(schluessel),
    )


def _schritte_aus_block(zeilen: Sequence[tuple[int, str]]) -> tuple[Schritt, ...]:
    if not zeilen:
        return ()

    ebene = _oberste_ebene(zeilen)
    gruppen: list[list[tuple[int, str]]] = []
    for nummer, text in zeilen:
        if text.strip().startswith("- ") and _einrueckung(text) == ebene:
            gruppen.append([])
        if gruppen:
            gruppen[-1].append((nummer, text))
    return tuple(_schritt_aus_gruppe(index, gruppe) for index, gruppe in enumerate(gruppen))


def jobs_aus_text(text: str) -> tuple[Job, ...]:
    """Der Struktur-Leser: `ci.yml`-Text -> Jobs mit ihren Schritten, ohne YAML-Bibliothek."""
    zeilen = nummerierte_zeilen(text)
    _pruefe_nicht_leer([t for _, t in zeilen if t.strip()], "wirksame Zeilen")

    jobs_eintrag = _eintrag(zeilen, "jobs")
    if jobs_eintrag is None or not jobs_eintrag.unterblock:
        raise ValueError(
            f"Kein nicht-leerer 'jobs:'-Block in {CI_WORKFLOW_NAME} gefunden. Der Leser sieht "
            "nicht, was er sehen soll; jede Abwesenheits-Assertion waere hier leer-gruen."
        )

    jobs: list[Job] = []
    for eintrag in _eintraege(jobs_eintrag.unterblock):
        job_schluessel = tuple(unter.name for unter in _eintraege(eintrag.unterblock))
        defaults = _eintrag(eintrag.unterblock, "defaults")
        laufvorgaben = _eintrag(defaults.unterblock, "run") if defaults is not None else None
        verzeichnis = (
            _eintrag(laufvorgaben.unterblock, "working-directory")
            if laufvorgaben is not None
            else None
        )
        schritte = _eintrag(eintrag.unterblock, "steps")
        jobs.append(
            Job(
                name=eintrag.name,
                beginn=eintrag.nummer,
                defaults_working_directory=(
                    _skalar(verzeichnis.wert) if verzeichnis is not None else None
                ),
                schritte=_schritte_aus_block(schritte.unterblock) if schritte is not None else (),
                schluessel=job_schluessel,
            )
        )
    return tuple(jobs)


def ci_text(pfad: Path = CI_WORKFLOW_PFAD) -> str:
    """Duenner Leser fuer den echten Dateizustand; eine fehlende Datei scheitert laut."""
    return pfad.read_text(encoding="utf-8")


def verwaltete_pfade(wurzel: Path = REPO_WURZEL) -> list[str]:
    """Die von Git verwalteten Pfade, NUL-getrennt.

    NUL statt Zeilenumbruch, weil ein Pfad mit Zeilenumbruch sonst einen Paketsatz verbaerge und
    `core.quotePath` Sonderzeichen-Pfade in Anfuehrungszeichen liefert. `check=True`: ein
    `git`-Aufruf mit Exit != 0 bricht ab, statt eine leere Menge auszuwerten. Nie `rglob` - aus
    dem Haupt-Checkout saehe es die verbundenen Arbeitsbaeume unter `.claude/worktrees/` mit.
    """
    ergebnis = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=wurzel,
        capture_output=True,
        check=True,
    )
    return [pfad.decode("utf-8") for pfad in ergebnis.stdout.split(b"\0") if pfad]


def paketsaetze(pfade: Sequence[str]) -> list[str]:
    """Die abgeleitete Paketsatzmenge: Verzeichnisse verwalteter Lockfiles, normalisiert."""
    _pruefe_nicht_leer(pfade, "von Git verwaltete Pfade")
    return sorted(
        {
            normalisiertes_verzeichnis(str(Path(pfad).parent))
            for pfad in pfade
            if Path(pfad).name == LOCKFILE_NAME and "node_modules" not in Path(pfad).parts
        }
    )


def lockfile_abbild(
    saetze: Sequence[str], wurzel: Path = REPO_WURZEL
) -> dict[str, dict[str, object]]:
    """Paketsatz -> geparstes Lockfile. Unparsbar und fehlend scheitern laut, nicht still."""
    _pruefe_nicht_leer(saetze, "Paketsaetze")
    abbild: dict[str, dict[str, object]] = {}
    for satz in saetze:
        pfad = wurzel / satz / LOCKFILE_NAME
        roh = pfad.read_text(encoding="utf-8")
        try:
            abbild[f"{satz}/{LOCKFILE_NAME}"] = json.loads(roh)
        except json.JSONDecodeError as fehler:
            raise ValueError(f"{satz}/{LOCKFILE_NAME} ist nicht parsbar: {fehler}") from fehler
    return abbild


# --- Die Zusicherungen als reine Funktionen, die eine Befundliste liefern ----------------------


def fehlende_paketsaetze(jobs: Sequence[Job], saetze: Sequence[str]) -> list[str]:
    """Existenzhaelfte: Jeder Paketsatz hat einen `npm ci`-Schritt in seinem Verzeichnis."""
    _pruefe_nicht_leer(jobs, "Jobs")
    _pruefe_nicht_leer(saetze, "Paketsaetze")

    installiert = {
        job.wirksames_verzeichnis(schritt)
        for job in jobs
        for schritt in job.schritte
        if schritt.ist_installation
    }
    return [
        f"Paketsatz {satz!r}: kein Schritt mit `npm ci` in diesem Verzeichnis in "
        f"{CI_WORKFLOW_NAME}. Ein Paketsatz ohne Installationsschritt im Pruefauf wird dort auch "
        "nicht signaturgeprueft - das Schritt-Paar (`npm ci`, dann `npm audit signatures`) fehlt."
        for satz in saetze
        if satz not in installiert
    ]


def nachbarschafts_befunde(jobs: Sequence[Job], nur_verzeichnis: str | None = None) -> list[str]:
    """Nachbarschaftshaelfte: Auf jeden `npm ci`-Schritt folgt der Signaturschritt.

    Mit `nur_verzeichnis` auf die Installationsschritte genau eines Paketsatzes eingegrenzt -
    so gehoert jeder Paketsatz als eigener Testfall gemeldet, statt in einer Sammelmeldung.
    """
    _pruefe_nicht_leer(jobs, "Jobs")

    befunde: list[str] = []
    for job in jobs:
        for schritt in job.schritte:
            if not schritt.ist_installation:
                continue
            verzeichnis = job.wirksames_verzeichnis(schritt)
            if nur_verzeichnis is not None and verzeichnis != nur_verzeichnis:
                continue
            ort = f"{CI_WORKFLOW_NAME}:{schritt.beginn}: Job {job.name!r}"

            if schritt.index + 1 >= len(job.schritte):
                befunde.append(
                    f"{ort}: `npm ci` ist der letzte Schritt des Jobs - der Signaturschritt kann "
                    "nicht im selben Job folgen. Eine Job-Grenze bricht die Nachbarschaft."
                )
                continue

            nachfolger = job.schritte[schritt.index + 1]
            if not nachfolger.ist_signaturpruefung:
                befunde.append(
                    f"{ort}: auf `npm ci` folgt in Zeile {nachfolger.beginn} ein Schritt mit "
                    f"{nachfolger.run!r} statt `{SIGNATUR_NUTZLAST}`. Der Signaturschritt ist der "
                    "erste Schritt nach der Installation - vor Formatpruefung, Lint, Typpruefung, "
                    "Test und Build."
                )
                continue

            nachfolger_verzeichnis = job.wirksames_verzeichnis(nachfolger)
            if nachfolger_verzeichnis != verzeichnis:
                befunde.append(
                    f"{ort}: `npm ci` laeuft in {verzeichnis!r}, der Signaturschritt in Zeile "
                    f"{nachfolger.beginn} aber in {nachfolger_verzeichnis!r}. Die Pruefung liest "
                    "dann einen anderen Paketsatz, endet gruen und laesst diesen ungeprueft."
                )
    return befunde


ENTSCHAERFENDE_SCHLUESSEL = ("if", "continue-on-error")


def wirkungs_befunde(jobs: Sequence[Job]) -> list[str]:
    """Jeder Signaturschritt kann den Job rot machen und prueft ungemindert.

    Geprueft auf **beiden** Ebenen: `if:` und `continue-on-error` kennt GitHub Actions am Schritt
    wie am Job. `jobs.<id>.if` ueberspringt den ganzen Job - der Lauf meldet dann "skipped" statt
    rot -, `jobs.<id>.continue-on-error` entschaerft ihn. In beiden Faellen laeuft die
    Signaturpruefung nie.
    """
    _pruefe_nicht_leer(jobs, "Jobs")

    befunde: list[str] = []
    for job in jobs:
        if any(schritt.ist_signaturpruefung for schritt in job.schritte):
            befunde.extend(
                f"{CI_WORKFLOW_NAME}:{job.beginn}: Job {job.name!r} traegt `{schluessel}:` auf "
                "Job-Ebene und enthaelt einen Signaturschritt. Der Job wird dann uebersprungen "
                "oder entschaerft, die Pruefung laeuft nie, und der Lauf meldet nicht rot."
                for schluessel in ENTSCHAERFENDE_SCHLUESSEL
                if schluessel in job.schluessel
            )
        for schritt in job.schritte:
            if not schritt.ist_signaturpruefung:
                continue
            ort = f"{CI_WORKFLOW_NAME}:{schritt.beginn}: Job {job.name!r}, Signaturschritt"
            for schluessel in ENTSCHAERFENDE_SCHLUESSEL:
                if schluessel in schritt.schluessel:
                    befunde.append(
                        f"{ort}: traegt `{schluessel}:`. Damit meldet der Job gruen, obwohl die "
                        "Pruefung nicht greift oder gar nicht laeuft."
                    )
            nutzlast = (schritt.run or "").strip()
            if nutzlast != SIGNATUR_NUTZLAST:
                befunde.append(
                    f"{ort}: Nutzlast {nutzlast!r} statt genau {SIGNATUR_NUTZLAST!r}. Kein "
                    "zusaetzliches Flag, keine Provenance-Forderung, keine Herabsetzung der "
                    "Pruefstufe - und kein `|| true`, das den Exit-Code verschluckt."
                )
    return befunde


def installationsort_befunde(jobs: Sequence[Job], saetze: Sequence[str]) -> list[str]:
    """Nicht tragend: kein npm-Installationsaufruf ausserhalb der abgeleiteten Paketsatzmenge.

    Diese Zusicherung greift bei keiner realistischen Mutation zuerst - die Existenzhaelfte faengt
    dieselben Faelle frueher. Sie macht die Arbeitsverzeichnis-Rechnung ein zweites, unabhaengiges
    Mal beobachtbar und ist deshalb ausdruecklich *nicht tragend* markiert.
    """
    _pruefe_nicht_leer(jobs, "Jobs")
    _pruefe_nicht_leer(saetze, "Paketsaetze")

    return [
        f"{CI_WORKFLOW_NAME}:{schritt.beginn}: Job {job.name!r}: Installationsaufruf "
        f"{schritt.befehlszeilen!r} im Verzeichnis {job.wirksames_verzeichnis(schritt)!r}, das "
        f"kein abgeleiteter Paketsatz ist ({list(saetze)})."
        for job in jobs
        for schritt in job.schritte
        if schritt.ist_aus_der_installationsfamilie
        and job.wirksames_verzeichnis(schritt) not in saetze
    ]


def lockfile_befunde(abbild: Mapping[str, dict[str, object]]) -> list[str]:
    """Jeder Lockfile-Eintrag ausser dem Wurzeleintrag traegt Registry-`resolved` und `integrity`."""
    _pruefe_nicht_leer(abbild, "Lockfiles")

    befunde: list[str] = []
    for pfad, daten in sorted(abbild.items()):
        eintraege = daten.get("packages")
        if not isinstance(eintraege, dict) or not eintraege:
            befunde.append(
                f"{pfad}: kein nicht-leerer 'packages'-Block. Ohne ihn ist ungeprueft, woher die "
                "Pakete dieses Satzes kommen."
            )
            continue
        for name, eintrag in sorted(eintraege.items()):
            if name == "":
                continue
            if not isinstance(eintrag, dict):
                befunde.append(f"{pfad}: {name}: Eintrag ist kein Objekt")
                continue
            resolved = eintrag.get("resolved")
            integrity = eintrag.get("integrity")
            if not isinstance(resolved, str) or not resolved.startswith(REGISTRY_PRAEFIX):
                befunde.append(
                    f"{pfad}: {name}: resolved={resolved!r} liegt nicht unter "
                    f"{REGISTRY_PRAEFIX} - `npm audit signatures` ueberspringt einen nicht aus "
                    "der Registry aufgeloesten Eintrag STILL und meldet Exit 0."
                )
            if not isinstance(integrity, str) or not integrity:
                befunde.append(
                    f"{pfad}: {name}: kein 'integrity'. Die Bindung der installierten Bytes an "
                    "das Lockfile leistet allein `npm ci` ueber diesen Hash."
                )
    return befunde


def workflow_defaults_befunde(text: str) -> list[str]:
    """Auf Workflow-Ebene gibt es kein `defaults:` - die dritte Quelle wird nicht gerechnet."""
    eintrag = _eintrag(nummerierte_zeilen(text), "defaults")
    if eintrag is None:
        return []
    return [
        f"{CI_WORKFLOW_NAME}:{eintrag.nummer}: `defaults:` auf Workflow-Ebene. Der Leser dieses "
        "Tests rechnet das wirksame Arbeitsverzeichnis aus genau zwei Quellen (Schritt, Job) - "
        "mit einer dritten liefert er ein Ergebnis, das niemand mehr als falsch erkennt."
    ]


# --- Werkzeug fuer die Gegenproben: Mutationen am echten Text ----------------------------------


def _job(text: str, name: str) -> Job:
    for job in jobs_aus_text(text):
        if job.name == name:
            return job
    raise ValueError(f"Kein Job {name!r} in {CI_WORKFLOW_NAME} - der Leser sieht ihn nicht.")


def _schritt_der_rolle(text: str, job_name: str, *, signatur: bool) -> Schritt:
    rolle = "Signaturschritt" if signatur else "Installationsschritt (`npm ci`)"
    for schritt in _job(text, job_name).schritte:
        passt = schritt.ist_signaturpruefung if signatur else schritt.ist_installation
        if passt:
            return schritt
    raise ValueError(
        f"Job {job_name!r} hat keinen {rolle}. Eine Gegenprobe darf nicht gruen werden, weil ihr "
        "Ausgangsschritt fehlt."
    )


def _zeilen_ersetzen(text: str, beginn: int, ende: int, ersatz: Sequence[str]) -> str:
    """Ersetzt die 1-basierten Zeilen [beginn, ende] (inklusive) durch `ersatz`."""
    zeilen = text.splitlines()
    return "\n".join([*zeilen[: beginn - 1], *ersatz, *zeilen[ende:]]) + "\n"


def _schrittzeilen(text: str, schritt: Schritt) -> list[str]:
    return text.splitlines()[schritt.beginn - 1 : schritt.ende]


def ohne_schritt(text: str, job_name: str, *, signatur: bool) -> str:
    schritt = _schritt_der_rolle(text, job_name, signatur=signatur)
    return _zeilen_ersetzen(text, schritt.beginn, schritt.ende, [])


def mit_getauschtem_paar(text: str, job_name: str) -> str:
    """Installations- und Signaturschritt in umgekehrter Reihenfolge, alles andere unberuehrt."""
    installation = _schritt_der_rolle(text, job_name, signatur=False)
    signatur = _schritt_der_rolle(text, job_name, signatur=True)
    dazwischen = text.splitlines()[installation.ende : signatur.beginn - 1]
    return _zeilen_ersetzen(
        text,
        installation.beginn,
        signatur.ende,
        [*_schrittzeilen(text, signatur), *dazwischen, *_schrittzeilen(text, installation)],
    )


def mit_zeilen_hinter_dem_schritt(
    text: str, job_name: str, zeilen: Sequence[str], *, signatur: bool
) -> str:
    schritt = _schritt_der_rolle(text, job_name, signatur=signatur)
    return _zeilen_ersetzen(text, schritt.ende + 1, schritt.ende, zeilen)


def mit_zeilen_im_job(text: str, job_name: str, zeilen: Sequence[str]) -> str:
    """Ergaenzt Schluesselzeilen auf Job-Ebene, unmittelbar hinter der Job-Kopfzeile."""
    job = _job(text, job_name)
    return _zeilen_ersetzen(text, job.beginn + 1, job.beginn, zeilen)


def mit_zeilen_vor_dem_ersten_schritt(text: str, job_name: str, zeilen: Sequence[str]) -> str:
    erster = _job(text, job_name).schritte[0]
    return _zeilen_ersetzen(text, erster.beginn, erster.beginn - 1, zeilen)


def ohne_arbeitsverzeichnis(text: str, job_name: str, *, signatur: bool) -> str:
    schritt = _schritt_der_rolle(text, job_name, signatur=signatur)
    behalten = [
        zeile
        for zeile in _schrittzeilen(text, schritt)
        if not zeile.strip().startswith("working-directory:")
    ]
    return _zeilen_ersetzen(text, schritt.beginn, schritt.ende, behalten)


def mit_ersetzter_nutzlast(text: str, job_name: str, nutzlast: str) -> str:
    schritt = _schritt_der_rolle(text, job_name, signatur=True)
    ersatz = [
        f"{zeile.split('run:')[0]}run: {nutzlast}" if zeile.strip().startswith("run:") else zeile
        for zeile in _schrittzeilen(text, schritt)
    ]
    return _zeilen_ersetzen(text, schritt.beginn, schritt.ende, ersatz)


def ohne_schritte_nach_der_installation(text: str, job_name: str) -> str:
    """Macht `npm ci` zum letzten Schritt seines Jobs."""
    installation = _schritt_der_rolle(text, job_name, signatur=False)
    letzter = _job(text, job_name).schritte[-1]
    return _zeilen_ersetzen(text, installation.ende + 1, letzter.ende, [])


# Der Teilstring, der die Befundklasse "Job-Grenze" von der Klasse "falscher Nachfolger"
# unterscheidet. Eine Gegenprobe, die nur auf "irgendein Befund" prueft, waere auch dann gruen,
# wenn ihre Mutation an einer zweiten Stelle anschlaegt.
BEFUND_JOB_GRENZE = "letzte Schritt des Jobs"

SIGNATURSCHRITT_ZEILEN = (
    "      - name: Lieferkette - Registry-Signaturen pruefen",
    f"        run: {SIGNATUR_NUTZLAST}",
)
FREMDER_SCHRITT_ZEILEN = (
    "      - name: Dazwischengeschoben",
    "        run: echo unbeteiligt",
)


# --- Positiv-Assertions ueber die gelesene Struktur --------------------------------------------


def test_der_leser_findet_die_jobs_dieses_workflows() -> None:
    jobs = jobs_aus_text(ci_text())
    namen = [job.name for job in jobs]

    assert len(jobs) >= MINDESTZAHL_JOBS, (
        f"Nur {len(jobs)} Jobs gelesen ({namen}), erwartet mindestens {MINDESTZAHL_JOBS}. Der "
        "Struktur-Leser ist kaputt; jeder Nullbefund dieses Tests waere dann bedeutungslos."
    )
    assert set(PFLICHT_JOBS) <= set(namen), (
        f"Der Leser sieht {namen} und damit nicht alle erwarteten Jobs {list(PFLICHT_JOBS)}."
    )


@pytest.mark.parametrize("job_name", PFLICHT_JOBS)
def test_der_leser_findet_die_schritte_jedes_jobs(job_name: str) -> None:
    job = _job(ci_text(), job_name)

    assert len(job.schritte) >= MINDESTSCHRITTE_JE_JOB, (
        f"Job {job_name!r}: nur {len(job.schritte)} Schritte gelesen, erwartet mindestens "
        f"{MINDESTSCHRITTE_JE_JOB}. Ein Leser, der Schritte verliert, macht die "
        "Nachbarschaftspruefung leer-gruen."
    )
    assert all(schritt.schluessel for schritt in job.schritte), (
        f"Job {job_name!r}: ein gelesener Schritt hat keinen einzigen Schluessel - die "
        "Gruppierung der Listeneintraege stimmt nicht."
    )
    assert {"runs-on", "steps"} <= set(job.schluessel), (
        f"Job {job_name!r}: gelesene Schluessel {job.schluessel}. Sieht der Leser die Schluessel "
        "der Job-Ebene nicht, bliebe die Pruefung auf `if:`/`continue-on-error` dort leer-gruen."
    )


@pytest.mark.parametrize("job_name", sorted(ERWARTETE_SCHRITTZAHL))
def test_die_schrittzahl_der_beiden_paketsatz_jobs_ist_die_erwartete(job_name: str) -> None:
    """Exakt fuer die zwei Jobs, die die Zusicherung tragen - eine Abweichung ist zu bemerken."""
    job = _job(ci_text(), job_name)

    assert len(job.schritte) == ERWARTETE_SCHRITTZAHL[job_name], (
        f"Job {job_name!r} hat {len(job.schritte)} Schritte, erwartet "
        f"{ERWARTETE_SCHRITTZAHL[job_name]}. Entweder hat der Job einen Schritt bekommen oder "
        "verloren - dann gehoert die Zahl hier nachgezogen -, oder der Leser zaehlt falsch."
    )


@pytest.mark.parametrize("job_name", sorted(ERWARTETER_INSTALLATIONSINDEX))
def test_der_signaturschritt_steht_als_index_unmittelbar_hinter_der_installation(
    job_name: str,
) -> None:
    job = _job(ci_text(), job_name)
    erwartet = ERWARTETER_INSTALLATIONSINDEX[job_name]
    installation = _schritt_der_rolle(ci_text(), job_name, signatur=False)
    signatur = _schritt_der_rolle(ci_text(), job_name, signatur=True)

    assert installation.index == erwartet, (
        f"Job {job_name!r}: `npm ci` steht an Index {installation.index}, erwartet {erwartet}."
    )
    assert signatur.index == erwartet + 1, (
        f"Job {job_name!r}: der Signaturschritt steht an Index {signatur.index}, erwartet "
        f"{erwartet + 1} - unmittelbar hinter der Installation und vor allem uebrigen."
    )
    assert job.wirksames_verzeichnis(signatur) == job_name
    assert (signatur.run or "").strip() == SIGNATUR_NUTZLAST


def test_die_paketsatzmenge_wird_abgeleitet_und_findet_beide_saetze() -> None:
    saetze = paketsaetze(verwaltete_pfade())

    assert saetze, "0 Paketsaetze abgeleitet - die Ableitung ist kaputt, nicht das Repository."
    assert set(PFLICHT_PAKETSAETZE) <= set(saetze), (
        f"Die Ableitung liefert {saetze} und sieht damit nicht beide bekannten Paketsaetze "
        f"{list(PFLICHT_PAKETSAETZE)}. Zwei Kanarienvoegel, keine gepflegte Liste: bricht die "
        "Ableitung, faellt das hier auf statt still."
    )


# --- Zusicherung: Schritt-Paar je Paketsatz ----------------------------------------------------


@pytest.mark.parametrize("satz", paketsaetze(verwaltete_pfade()))
def test_jeder_paketsatz_wird_signaturgeprueft_installiert(satz: str) -> None:
    jobs = jobs_aus_text(ci_text())

    befunde = [
        *fehlende_paketsaetze(jobs, [satz]),
        *nachbarschafts_befunde(jobs, nur_verzeichnis=satz),
    ]

    assert not befunde, "\n".join(befunde)


@pytest.mark.parametrize("job_name", PFLICHT_PAKETSAETZE)
def test_der_installationsschritt_des_jobs_hat_den_signaturschritt_als_nachfolger(
    job_name: str,
) -> None:
    befunde = nachbarschafts_befunde([_job(ci_text(), job_name)])

    assert not befunde, "\n".join(befunde)


def test_jeder_installationsschritt_des_workflows_hat_den_signaturschritt_als_nachfolger() -> None:
    befunde = nachbarschafts_befunde(jobs_aus_text(ci_text()))

    assert not befunde, "\n".join(befunde)


def test_kein_paketsatz_bleibt_ohne_installationsschritt() -> None:
    text = ci_text()
    befunde = fehlende_paketsaetze(jobs_aus_text(text), paketsaetze(verwaltete_pfade()))

    assert not befunde, "\n".join(befunde)


def test_jeder_signaturschritt_kann_den_job_rot_machen() -> None:
    befunde = wirkungs_befunde(jobs_aus_text(ci_text()))

    assert not befunde, "\n".join(befunde)


def test_kein_installationsaufruf_ausserhalb_der_paketsatzmenge() -> None:
    text = ci_text()
    befunde = installationsort_befunde(jobs_aus_text(text), paketsaetze(verwaltete_pfade()))

    assert not befunde, "\n".join(befunde)


def test_der_workflow_hat_kein_defaults_auf_oberster_ebene() -> None:
    befunde = workflow_defaults_befunde(ci_text())

    assert not befunde, "\n".join(befunde)


# --- Zusicherung: jeder Lockfile-Eintrag kommt aus der Registry --------------------------------


def test_jeder_lockfile_eintrag_traegt_registry_resolved_und_integrity() -> None:
    befunde = lockfile_befunde(lockfile_abbild(paketsaetze(verwaltete_pfade())))

    assert not befunde, "\n".join(befunde)


def test_das_lockfile_abbild_enthaelt_beide_paketsaetze() -> None:
    abbild = lockfile_abbild(paketsaetze(verwaltete_pfade()))

    assert {f"{satz}/{LOCKFILE_NAME}" for satz in PFLICHT_PAKETSAETZE} <= set(abbild)
    for pfad, daten in abbild.items():
        eintraege = daten.get("packages")
        assert isinstance(eintraege, dict) and len(eintraege) > 1, (
            f"{pfad}: der 'packages'-Block ist leer oder fehlt - dann prueft die Zusicherung "
            "oben nichts und meldet trotzdem 'sauber'."
        )


@pytest.mark.parametrize(
    ("eintrag", "erwarteter_teil"),
    [
        ({"resolved": "file:../lokal", "integrity": "sha512-x"}, "liegt nicht unter"),
        ({"resolved": "git+https://example.invalid/x.git", "integrity": "sha512-x"}, "resolved"),
        (
            {"resolved": "https://registry.example.invalid/x.tgz", "integrity": "sha512-x"},
            "liegt nicht unter",
        ),
        ({"integrity": "sha512-x"}, "resolved=None"),
        ({"resolved": f"{REGISTRY_PRAEFIX}x/-/x-1.0.0.tgz"}, "kein 'integrity'"),
        ({"resolved": f"{REGISTRY_PRAEFIX}x/-/x-1.0.0.tgz", "integrity": ""}, "kein 'integrity'"),
    ],
)
def test_ein_nicht_aus_der_registry_aufgeloester_eintrag_wird_gemeldet(
    eintrag: dict[str, str], erwarteter_teil: str
) -> None:
    """Solche Eintraege ueberspringt `npm audit signatures` still - deshalb faengt sie dieser Test."""
    abbild = {"x/package-lock.json": {"packages": {"": {}, "node_modules/x": eintrag}}}

    befunde = lockfile_befunde(abbild)

    assert befunde and any(erwarteter_teil in befund for befund in befunde), befunde


def test_der_wurzeleintrag_braucht_kein_resolved() -> None:
    abbild: dict[str, dict[str, object]] = {
        "x/package-lock.json": {"packages": {"": {"name": "x", "version": "0.0.0"}}}
    }

    assert lockfile_befunde(abbild) == []


def test_ein_lockfile_ohne_packages_block_ist_ein_befund() -> None:
    assert lockfile_befunde({"x/package-lock.json": {"lockfileVersion": 3}})


# --- Gegenproben am mutierten Textabbild des echten ci.yml -------------------------------------


@pytest.mark.parametrize("job_name", PFLICHT_PAKETSAETZE)
def test_ein_entfernter_signaturschritt_wird_gemeldet(job_name: str) -> None:
    mutiert = ohne_schritt(ci_text(), job_name, signatur=True)

    assert nachbarschafts_befunde([_job(mutiert, job_name)])


@pytest.mark.parametrize("job_name", PFLICHT_PAKETSAETZE)
def test_eine_getauschte_reihenfolge_wird_gemeldet(job_name: str) -> None:
    """Der Signaturschritt VOR `npm ci` liefe ohne installierten Baum und sagt nichts zu."""
    mutiert = mit_getauschtem_paar(ci_text(), job_name)

    assert nachbarschafts_befunde([_job(mutiert, job_name)])


@pytest.mark.parametrize("job_name", PFLICHT_PAKETSAETZE)
def test_ein_dazwischengeschobener_schritt_wird_gemeldet(job_name: str) -> None:
    mutiert = mit_zeilen_hinter_dem_schritt(
        ci_text(), job_name, FREMDER_SCHRITT_ZEILEN, signatur=False
    )

    assert nachbarschafts_befunde([_job(mutiert, job_name)])


@pytest.mark.parametrize("job_name", PFLICHT_PAKETSAETZE)
def test_ein_dazwischengeschobener_kommentar_ist_kein_befund(job_name: str) -> None:
    """Unmittelbar ist eine Aussage ueber Schritte, nicht ueber Zeilen."""
    mutiert = mit_zeilen_hinter_dem_schritt(
        ci_text(),
        job_name,
        ("      # Ein Kommentar zwischen beiden Schritten bricht die Nachbarschaft nicht.", ""),
        signatur=False,
    )

    assert nachbarschafts_befunde([_job(mutiert, job_name)]) == []


def test_ein_verfaelschtes_arbeitsverzeichnis_am_signaturschritt_wird_gemeldet() -> None:
    """Der stillere Fall: laeuft gegen den e2e-Baum, endet gruen, `frontend` bleibt ungeprueft."""
    mutiert = mit_zeilen_hinter_dem_schritt(
        ci_text(), "frontend", ("        working-directory: e2e",), signatur=True
    )

    befunde = nachbarschafts_befunde([_job(mutiert, "frontend")])

    assert befunde and "'e2e'" in befunde[0], befunde


def test_eine_entfernte_arbeitsverzeichnis_zeile_am_installationsschritt_wird_gemeldet() -> None:
    """Eigener Codepfad: das wirksame Verzeichnis wird die Repo-Wurzel, `None` statt Zeichenkette."""
    mutiert = ohne_arbeitsverzeichnis(ci_text(), "e2e", signatur=False)
    job = _job(mutiert, "e2e")
    installation = _schritt_der_rolle(mutiert, "e2e", signatur=False)

    assert job.wirksames_verzeichnis(installation) == "."
    assert nachbarschafts_befunde([job])
    assert fehlende_paketsaetze([job], ["e2e"])


@pytest.mark.parametrize("job_name", PFLICHT_PAKETSAETZE)
def test_npm_ci_als_letzter_schritt_eines_jobs_ist_ein_befund_und_kein_indexerror(
    job_name: str,
) -> None:
    """Eine Ausnahme im Leser riss die Befunde der uebrigen Paketsaetze mit."""
    mutiert = ohne_schritte_nach_der_installation(ci_text(), job_name)
    job = _job(mutiert, job_name)

    assert job.schritte[-1].ist_installation
    befunde = nachbarschafts_befunde([job])

    assert befunde and BEFUND_JOB_GRENZE in befunde[0], befunde


def test_ein_signaturschritt_am_anfang_des_folgejobs_wird_gemeldet() -> None:
    """Die Job-Grenze bricht die Nachbarschaft, auch wenn KEIN Schritt dazwischen liegt.

    Die Mutation stellt genau diese Lage her: `npm ci` wird der letzte Schritt des
    `frontend`-Jobs, und der Signaturschritt wird der erste des Folgejobs. In der Schrittfolge
    des Workflows sind beide damit unmittelbare Nachbarn - zwischen ihnen steht nur die
    Job-Kopfzeile. Bliebe der Rest des `frontend`-Jobs stehen, meldete der Befund die
    dazwischenliegenden Schritte, und der Test belegte die Job-Grenze gerade nicht.
    """
    ohne_signatur = ohne_schritt(ci_text(), "frontend", signatur=True)
    gekuerzt = ohne_schritte_nach_der_installation(ohne_signatur, "frontend")
    mutiert = mit_zeilen_vor_dem_ersten_schritt(gekuerzt, "demo-scripts", SIGNATURSCHRITT_ZEILEN)

    # Die Mutation hat getan, was sie behauptet - sonst belegte die Assertion unten etwas anderes.
    schrittfolge = [
        (job.name, schritt) for job in jobs_aus_text(mutiert) for schritt in job.schritte
    ]
    installation = next(
        index
        for index, (name, schritt) in enumerate(schrittfolge)
        if name == "frontend" and schritt.ist_installation
    )
    signatur = next(
        index
        for index, (name, schritt) in enumerate(schrittfolge)
        if name == "demo-scripts" and schritt.ist_signaturpruefung
    )
    assert signatur == installation + 1, "kein unmittelbares Nachbarpaar in der Schrittfolge"
    assert schrittfolge[installation][0] != schrittfolge[signatur][0], "keine Job-Grenze dazwischen"

    befunde = nachbarschafts_befunde([_job(mutiert, "frontend")])

    assert len(befunde) == 1 and BEFUND_JOB_GRENZE in befunde[0], befunde


def test_ein_fiktiver_dritter_paketsatz_wird_als_fehlend_gemeldet() -> None:
    """Selbsterweiternd: die Menge ist abgeleitet, es gibt keine Ausnahmeliste."""
    jobs = jobs_aus_text(ci_text())
    saetze = [*paketsaetze(verwaltete_pfade()), "tools/widget"]

    befunde = fehlende_paketsaetze(jobs, saetze)

    assert befunde and all("tools/widget" in befund for befund in befunde), befunde


@pytest.mark.parametrize("schreibweise", ["./frontend", "frontend/", "frontend/."])
def test_gleichwertige_pfadschreibweisen_bleiben_gruen(schreibweise: str) -> None:
    mutiert = mit_zeilen_hinter_dem_schritt(
        ci_text(), "frontend", (f"        working-directory: {schreibweise}",), signatur=True
    )

    assert nachbarschafts_befunde([_job(mutiert, "frontend")]) == []


@pytest.mark.parametrize("schreibweise", ["frontends", "frontend/sub"])
def test_ein_anderes_verzeichnis_mit_aehnlichem_namen_wird_gemeldet(schreibweise: str) -> None:
    mutiert = mit_zeilen_hinter_dem_schritt(
        ci_text(), "frontend", (f"        working-directory: {schreibweise}",), signatur=True
    )

    assert nachbarschafts_befunde([_job(mutiert, "frontend")])


@pytest.mark.parametrize(
    "zeile",
    [
        "        continue-on-error: true",
        "        if: always()",
        "        if: github.event_name == 'push'",
    ],
)
def test_ein_nicht_blockierender_signaturschritt_wird_gemeldet(zeile: str) -> None:
    """Alle drei Formen liessen den Job gruen melden, obwohl die Pruefung nicht greift."""
    mutiert = mit_zeilen_hinter_dem_schritt(ci_text(), "e2e", (zeile,), signatur=True)

    assert wirkungs_befunde([_job(mutiert, "e2e")])


@pytest.mark.parametrize(
    ("zeile", "erwarteter_teil"),
    [
        ("    continue-on-error: true", "continue-on-error"),
        ("    if: github.event_name == 'push'", "if"),
        ("    if: always()", "if"),
    ],
)
def test_ein_nicht_blockierender_job_wird_gemeldet(zeile: str, erwarteter_teil: str) -> None:
    """Beide Schluessel kennt Actions auch auf JOB-Ebene, mit derselben Wirkung.

    `jobs.<id>.if` uebersprungen den ganzen Job - der Lauf meldet "skipped", nicht rot;
    `jobs.<id>.continue-on-error` entschaerft ihn. In beiden Faellen laeuft die Signaturpruefung
    nie, und ein Wächter, der nur die Schritt-Ebene liest, bliebe gruen.
    """
    mutiert = mit_zeilen_im_job(ci_text(), "frontend", (zeile,))

    befunde = wirkungs_befunde([_job(mutiert, "frontend")])

    assert befunde and any(erwarteter_teil in befund for befund in befunde), befunde


@pytest.mark.parametrize("job_name", PFLICHT_PAKETSAETZE)
def test_ein_job_ohne_diese_schluessel_ist_kein_befund(job_name: str) -> None:
    """Gegenprobe zur Job-Ebene: am unveraenderten Workflow darf sie nichts melden."""
    assert wirkungs_befunde([_job(ci_text(), job_name)]) == []


@pytest.mark.parametrize(
    "nutzlast",
    [
        "npm audit signatures || true",
        "npm audit signatures --audit-level=none",
        "npm audit signatures > /dev/null",
    ],
)
def test_eine_abgeschwaechte_nutzlast_wird_gemeldet(nutzlast: str) -> None:
    mutiert = mit_ersetzter_nutzlast(ci_text(), "e2e", nutzlast)

    assert wirkungs_befunde([_job(mutiert, "e2e")])


def test_ein_defaults_auf_workflow_ebene_wird_gemeldet() -> None:
    mutiert = "defaults:\n  run:\n    working-directory: frontend\n" + ci_text()

    assert workflow_defaults_befunde(mutiert)


# --- Gegenproben an den Erkennungsregeln -------------------------------------------------------


@pytest.mark.parametrize(
    "nutzlast",
    [
        "npm ci",
        "npm ci --omit=dev",
        "npm  ci",
        "|\n          set -euo pipefail\n          npm ci",
        "|\n          npm ci\n          echo fertig",
        ">\n          npm\n          ci",
    ],
)
def test_installationsschritte_werden_erkannt(nutzlast: str) -> None:
    text = f"jobs:\n  j:\n    steps:\n      - run: {nutzlast}\n"
    schritt = _job(text, "j").schritte[0]

    assert schritt.ist_installation, schritt


@pytest.mark.parametrize(
    "nutzlast",
    [
        "npx playwright install --with-deps chromium",
        "npm run build",
        "npm audit signatures",
        "echo 'npm ci' >&2",
        "|\n          # npm ci steht hier nur in einem Kommentar\n          echo nichts",
    ],
)
def test_kein_installationsschritt_wird_falsch_erkannt(nutzlast: str) -> None:
    text = f"jobs:\n  j:\n    steps:\n      - run: {nutzlast}\n"
    schritt = _job(text, "j").schritte[0]

    assert not schritt.ist_installation, schritt


def test_ein_schritt_ohne_run_hat_keine_befehlszeilen() -> None:
    text = "jobs:\n  j:\n    steps:\n      - uses: actions/checkout@v4\n"
    schritt = _job(text, "j").schritte[0]

    assert schritt.run is None
    assert schritt.befehlszeilen == ()
    assert not schritt.ist_installation and not schritt.ist_signaturpruefung


def test_ein_blockskalar_verbirgt_keinen_schluessel_des_schrittes() -> None:
    """Shell-Text in `run: |` darf nicht als `working-directory:`/`if:` des Schrittes gelesen werden."""
    text = (
        "jobs:\n  j:\n    steps:\n"
        "      - run: |\n"
        "          echo 'working-directory: e2e'\n"
        "          if: nicht wirklich\n"
        "        working-directory: frontend\n"
    )
    schritt = _job(text, "j").schritte[0]

    assert schritt.working_directory == "frontend"
    assert schritt.schluessel == ("run", "working-directory")


@pytest.mark.parametrize(
    ("wert", "erwartet"),
    [
        ("frontend", "frontend"),
        ("./frontend", "frontend"),
        ("frontend/", "frontend"),
        ("frontend/.", "frontend"),
        ('"frontend"', "frontend"),
        ("frontend/sub", "frontend/sub"),
        ("frontends", "frontends"),
        (None, "."),
        (".", "."),
    ],
)
def test_die_pfadnormalisierung_trifft_nur_dasselbe_verzeichnis(
    wert: str | None, erwartet: str
) -> None:
    assert normalisiertes_verzeichnis(wert) == erwartet


def test_das_arbeitsverzeichnis_am_schritt_schlaegt_die_job_vorgabe() -> None:
    text = (
        "jobs:\n  j:\n"
        "    defaults:\n      run:\n        working-directory: frontend\n"
        "    steps:\n"
        "      - run: npm ci\n"
        "      - run: npm audit signatures\n"
        "        working-directory: e2e\n"
    )
    job = _job(text, "j")

    assert job.wirksames_verzeichnis(job.schritte[0]) == "frontend"
    assert job.wirksames_verzeichnis(job.schritte[1]) == "e2e"


def test_die_paketsatzableitung_uebergeht_node_modules_und_fremde_dateien() -> None:
    pfade = [
        "frontend/package-lock.json",
        "e2e/package-lock.json",
        "frontend/node_modules/x/package-lock.json",
        "frontend/package.json",
        "docs/package-lock.json.md",
    ]

    assert paketsaetze(pfade) == ["e2e", "frontend"]


def test_ein_lockfile_in_der_repo_wurzel_waere_ein_eigener_paketsatz() -> None:
    assert paketsaetze(["package-lock.json"]) == ["."]


# --- Selbstschutz: leerer Suchraum, fehlende Datei ---------------------------------------------


def test_eine_leere_paketsatzmenge_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"0 Paketsaetze"):
        fehlende_paketsaetze(jobs_aus_text(ci_text()), [])


def test_eine_leere_jobmenge_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"0 Jobs"):
        nachbarschafts_befunde([])
    with pytest.raises(ValueError, match=r"0 Jobs"):
        wirkungs_befunde([])


def test_eine_leere_pfadliste_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"0 von Git verwaltete Pfade"):
        paketsaetze([])


def test_ein_leeres_lockfile_abbild_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"0 Lockfiles"):
        lockfile_befunde({})


def test_ein_workflow_ohne_jobs_block_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"jobs"):
        jobs_aus_text("name: ci\non:\n  push:\n    branches: [main]\n")


def test_ein_leerer_workflowtext_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"0 wirksame Zeilen"):
        jobs_aus_text("# nur ein Kommentar\n\n   \n")


def test_eine_fehlende_workflowdatei_scheitert_laut(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        ci_text(tmp_path / "gibt-es-nicht.yml")


def test_ein_fehlendes_lockfile_scheitert_laut(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        lockfile_abbild(["frontend"], wurzel=tmp_path)


def test_ein_unparsbares_lockfile_scheitert_laut(tmp_path: Path) -> None:
    (tmp_path / "frontend").mkdir()
    (tmp_path / "frontend" / LOCKFILE_NAME).write_text("{kein json", encoding="utf-8")

    with pytest.raises(ValueError, match=r"nicht parsbar"):
        lockfile_abbild(["frontend"], wurzel=tmp_path)


def test_ein_gescheiterter_git_aufruf_bricht_ab_statt_leer_zu_liefern(tmp_path: Path) -> None:
    """Ein leeres Ergebnis waere hier 'nichts gefunden' - und damit eine falsche Entlastung."""
    with pytest.raises(subprocess.CalledProcessError):
        verwaltete_pfade(tmp_path)


def test_ein_job_ohne_signaturschritt_scheitert_im_mutationswerkzeug_laut() -> None:
    """Die Gegenproben duerfen nicht gruen werden, weil ihr Ausgangsschritt fehlt."""
    with pytest.raises(ValueError, match=r"keinen Signaturschritt"):
        _schritt_der_rolle(ci_text(), "backend", signatur=True)
