"""Das GETIPPTE Bezugskommando: holt den GeoNames-Datensatz und legt daraus die Auszüge ab, die
der Auflöser und die Ortsprüfung im Betrieb lesen.

Aufruf über die Container-Konsole, einmal je Volume::

    docker compose exec backend python -m photosort.place_dataset

Es bezieht `allCountries.zip` (rund 400 MB), bildet daraus ZWEI Auszüge, löscht das Archiv wieder
und legt je Auszug seinen SHA256 daneben. Gemessen (2026-09-14): Der Ortsauszug hat 5.770.883
Zeilen, 223 MB, gzip-gepackt 69 MB, ein vollständiger Lese-Durchgang dauert 3,3 s. Der zweite
Auszug für die Sehenswürdigkeitsnamen (Klassen `S`/`T`/`L`/`H`/`V` PLUS `alternatenames`) hat
7,62 Mio. Zeilen, rund 659 MB roh, rund 204 MB gepackt; das Volume trägt danach rund 273 MB
(ADR 0123 Punkt 1).

BEIDE AUSZÜGE ENTSTEHEN AUS EINEM BEZUG UND EINEM DURCHGANG: Archiv einmal laden, einmal
entpacken, in einem Durchgang beide Zieldateien schreiben. Zwei Durchgänge über dieselbe 400-MB-
Datei wären eine Verdopplung ohne Gegenwert; getrennt bleiben die Dateien trotzdem, damit ein
fehlender Sehenswürdigkeits-Auszug für sich feststellbar ist.

EIN AUSZUG IST EINE GEONAMES-DATEI MIT GELEERTEN SPALTEN, kein eigenes Format: Er behält die
Spaltenpositionen des Originals und lässt die ungebrauchten Felder leer. Damit liest ihn
`geonames.parse_geonames_line` bzw. `geonames.parse_landmark_line` unverändert, und die Gleichheit
zum gemessenen Verhalten ist strukturell statt argumentiert - dieselben Zeilen, dieselben Felder,
derselbe Parser (`tests/test_place_dataset.py::TestTheExtractBehavesLikeTheRawFile`,
`::TestTheSecondExtractBehavesLikeTheRawFile`).

DIESES KOMMANDO BLEIBT VON JEDEM AUTOMATISCHEN PFAD FERN - kein Aufrufpfad aus `main.py`/
`worker.py`, kein Endpunkt, kein Compose-`command`, dieselbe Auflage und derselbe Nachweis wie bei
`place_probe.py`. Ein 400-MB-Abruf tritt nur ein, wenn er getippt wird.

KEIN SHELLSKRIPT AUF DEM HOST: Auf dem Server gibt es keine Shell, nur eine Oberfläche für Docker
Compose und eine Container-Konsole. Eine zweite Fassung desselben Ablaufs driftet, und die auf dem
Server unbrauchbare wäre die schlechtere (ADR 0105 Punkt 3).

SICHERHEIT:

* Die Quell-Adresse ist eine KONSTANTE, der Zielpfad eine Betriebseinstellung - beides nie ein
  Wert aus Datenbank oder Request, kein SSRF-Pfad. Entpackt wird genau ein BENANNTER Eintrag des
  Archivs, nie dessen Verzeichnis: kein Pfad aus fremden Daten. Der zweite Zielname entsteht
  ABGELEITET (`geonames.landmark_dataset_path`), nie aus einer Eingabe.
* DER ERSTBEZUG BLEIBT UNGESCHÜTZT. GeoNames erzeugt das Archiv nächtlich neu und veröffentlicht
  keine Prüfsummen; es gibt keinen vertrauenswürdigen Sollwert, gegen den sich pinnen ließe. Der
  Hash entsteht deshalb hier, aus dem erzeugten Auszug, und trägt ab da jede spätere Prüfung. Eine
  an der Quelle oder auf dem Weg veränderte Datei würde als Sollwert übernommen - bewusst
  akzeptiertes Restrisiko (Daniel, 2026-09-14), getragen davon, dass der Schaden auf falsche
  Ortsnamen in Überschriften begrenzt bleibt. Mit dem zweiten Auszug bestimmt derselbe Abruf ab
  hier mit, OB eine Überschrift entsteht; die Klasse des Restrisikos ändert das nicht.
* Die Spaltenreduktion ist DATENSPARSAMKEIT, keine Injektionsabwehr: gegen Injektion tragen die
  Sanitisierung und die Längengrenze in `places.py` bzw. `landmark.py`.
* LOGGING: Dieses Kommando schreibt kein Log. Seine Ausgabe trägt Zahlen und Pfade, nie einen
  Ortsnamen und nie eine Koordinate.
"""

from __future__ import annotations

import argparse
import gzip
import io
import sys
import zipfile
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import TextIO

import httpx

from photosort.config import settings
from photosort.geonames import (
    GEONAMES_FEATURE_CLASS_FIELD,
    GEONAMES_FIELD_COUNT,
    GEONAMES_KEPT_FEATURE_CLASSES,
    GEONAMES_KEPT_FIELDS,
    GEONAMES_LANDMARK_FEATURE_CLASSES,
    GEONAMES_LANDMARK_KEPT_FIELDS,
    dataset_hash_path,
    landmark_dataset_path,
    sha256_of,
)

# Eine Extraktor-Funktion: eine Rohzeile als Auszugs-Zeile, oder `None`. Je Auszug eine; die
# Zielzuordnung liegt bei `write_extracts`.
LineExtractor = Callable[[str], str | None]

# Die Quell-Adresse als KONSTANTE (S9) - nie ein Wert aus Datenbank, Request oder Parameter.
GEONAMES_ARCHIVE_URL = "https://download.geonames.org/export/dump/allCountries.zip"

# Der eine benannte Eintrag, der aus dem Archiv gelesen wird. Ausdruecklich kein Durchlauf ueber
# das Verzeichnis des Archivs: der Pfad, unter dem geschrieben oder gelesen wird, stammt nie aus
# fremden Daten.
GEONAMES_ARCHIVE_MEMBER = "allCountries.txt"

# Zeitgrenze der Verbindung. Grosszuegig, weil 400 MB uebertragen werden; sie begrenzt das
# Ausbleiben einer Antwort, nicht die Dauer der Uebertragung.
_CONNECT_TIMEOUT_SECONDS = 30.0
_DOWNLOAD_CHUNK_BYTES = 1024 * 1024


def extract_line(line: str) -> str | None:
    """Eine Rohzeile als ORTSAUSZUGS-Zeile, oder `None`, wenn sie nicht in den Auszug gehoert.

    Behalten werden die Zeilen der Feature-Klassen `P` und `A` und darin die fuenf gelesenen
    Felder an UNVERAENDERTER Spaltenposition; alle uebrigen Felder werden geleert. Die
    Feldpositionen kommen aus `geonames.py`, also von der lesenden Seite - eine zweite Feldliste
    hier koennte gegen den Parser driften, und genau darauf ruht die Gleichheit beider Fassungen."""
    fields = line.rstrip("\n").split("\t")
    if len(fields) < GEONAMES_FIELD_COUNT:
        return None
    if fields[GEONAMES_FEATURE_CLASS_FIELD] not in GEONAMES_KEPT_FEATURE_CLASSES:
        return None
    return "\t".join(
        value if index in GEONAMES_KEPT_FIELDS else "" for index, value in enumerate(fields)
    )


def extract_landmark_line(line: str) -> str | None:
    """Eine Rohzeile als SEHENSWUERDIGKEITSAUSZUGS-Zeile, oder `None`.

    Dieselbe Formatregel wie `extract_line`, mit den Klassen `S`/`T`/`L`/`H`/`V` und
    `alternatenames` zusaetzlich in den gelesenen Feldern: Ohne dieses Feld fielen 33 von 50
    gemessenen Namen durch (ADR 0123 Punkt 1). `asciiname` bleibt ungenutzt - in der Messung war
    kein Name allein ueber dieses Feld auffindbar, den `alternatenames` nicht auch liefert."""
    fields = line.rstrip("\n").split("\t")
    if len(fields) < GEONAMES_FIELD_COUNT:
        return None
    if fields[GEONAMES_FEATURE_CLASS_FIELD] not in GEONAMES_LANDMARK_FEATURE_CLASSES:
        return None
    return "\t".join(
        value if index in GEONAMES_LANDMARK_KEPT_FIELDS else ""
        for index, value in enumerate(fields)
    )


def write_extracts(lines: Iterable[str], targets: Mapping[Path, LineExtractor]) -> dict[Path, int]:
    """EIN Durchgang durch `lines`, je Ziel ein gzip-gepackter Auszug samt SHA256 daneben.

    Rueckgabe: die Zeilenzahl je Ziel. Die Reihenfolge der Ziele ist die der Zuordnung.

    Der Hash entsteht AUS DER GESCHRIEBENEN DATEI, nicht aus dem Speicherinhalt - geprueft wird
    spaeter genau die Datei, die gelesen wird. Das Schreiben der Hashes steht nach dem Schliessen
    ALLER Zieldateien: erst dann ist jede vollstaendig."""
    opened: list[tuple[TextIO, LineExtractor, Path]] = []
    written: dict[Path, int] = {}
    try:
        for target, extract in targets.items():
            target.parent.mkdir(parents=True, exist_ok=True)
            opened.append((gzip.open(target, "wt", encoding="utf-8"), extract, target))
            written[target] = 0
        for line in lines:
            for handle, extract, target in opened:
                extracted = extract(line)
                if extracted is None:
                    continue
                handle.write(extracted + "\n")
                written[target] += 1
    finally:
        for handle, _extract, _target in opened:
            handle.close()
    for target in targets:
        dataset_hash_path(target).write_text(sha256_of(target) + "\n", encoding="utf-8")
    return written


def _download_archive(target: Path) -> None:
    """Laedt das Archiv stueckweise auf die Platte - nie in den Speicher: es misst rund 400 MB."""
    with httpx.stream(
        "GET",
        GEONAMES_ARCHIVE_URL,
        timeout=httpx.Timeout(None, connect=_CONNECT_TIMEOUT_SECONDS),
        follow_redirects=True,
    ) as response:
        response.raise_for_status()
        with target.open("wb") as handle:
            for chunk in response.iter_bytes(_DOWNLOAD_CHUNK_BYTES):
                handle.write(chunk)


def build_dataset(target: Path, landmark_target: Path) -> dict[Path, int]:
    """Bezug, beide Auszüge, beide Hashes - und danach ist das Archiv wieder fort.

    Das Archiv liegt neben dem Ortsauszug und wird in JEDEM Ausgang geloescht: es misst rund
    400 MB, und ein liegengebliebenes Archiv fuellte das Volume ohne Nutzen. Beide Ziele werden in
    EINEM Durchgang ueber den entpackten Eintrag geschrieben."""
    target.parent.mkdir(parents=True, exist_ok=True)
    landmark_target.parent.mkdir(parents=True, exist_ok=True)
    archive = target.with_name("allCountries.zip")
    kept: dict[Path, int] = {}
    try:
        print(f"Beziehe {GEONAMES_ARCHIVE_URL} (rund 400 MB)...")
        _download_archive(archive)
        print("Bilde die Auszuege (P/A bzw. S/T/L/H/V, ungebrauchte Spalten geleert)...")
        with zipfile.ZipFile(archive) as bundle, bundle.open(GEONAMES_ARCHIVE_MEMBER) as member:
            kept = write_extracts(
                io.TextIOWrapper(member, encoding="utf-8", errors="replace"),
                {target: extract_line, landmark_target: extract_landmark_line},
            )
    finally:
        archive.unlink(missing_ok=True)
    return kept


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m photosort.place_dataset",
        description=(
            "Bezieht den GeoNames-Datensatz und legt BEIDE Auszuege samt SHA256 ab. Einmal je "
            "Volume - ein 400-MB-Abruf tritt nur ein, wenn er getippt wird."
        ),
    )
    parser.add_argument(
        "--pfad",
        default=None,
        help=(
            "Zielpfad des Ortsauszugs. Ohne Angabe gilt die Betriebseinstellung "
            "PLACE_DATASET_PATH (Vorgabe: der Pfad auf dem Volume)."
        ),
    )
    parser.add_argument(
        "--sehenswuerdigkeits-pfad",
        dest="sehenswuerdigkeits_pfad",
        default=None,
        help=(
            "Zielpfad des Sehenswuerdigkeitsauszugs. Ohne Angabe die Geschwisterdatei neben dem "
            "Ortsauszug (geonames.landmark_dataset_path) - keine eigene Betriebseinstellung."
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Verdrahtung + Exit-Code. `argv` ist injizierbar - kein `sys.argv`-Zugriff im Testpfad."""
    args = _build_parser().parse_args(argv)
    target = Path(args.pfad) if args.pfad else Path(settings.place_dataset_path)
    landmark_target = (
        Path(args.sehenswuerdigkeits_pfad)
        if args.sehenswuerdigkeits_pfad
        else landmark_dataset_path(target)
    )
    try:
        kept = build_dataset(target, landmark_target)
    except (OSError, httpx.HTTPError, zipfile.BadZipFile) as exc:
        # Nur der Fehlertyp, nie die Meldung: sie kann einen Pfad oder eine Adresse tragen, und
        # der Abbruch ist ohnehin nur ueber die Bedingung zu beheben (Muster place_probe.py).
        print(f"Fehler: Bezug fehlgeschlagen ({type(exc).__name__}).", file=sys.stderr)
        return 1
    print(f"Fertig. {kept[target]} Zeilen im Ortsauszug: {target}")
    print(f"Fertig. {kept[landmark_target]} Zeilen im Sehenswuerdigkeitsauszug: {landmark_target}")
    print(f"SHA256 abgelegt: {dataset_hash_path(target)}")
    print(f"SHA256 abgelegt: {dataset_hash_path(landmark_target)}")
    print("Beide Auszuege werden vor jedem Gebrauch dagegen geprueft; bei Abweichung entsteht kein")
    print("Auflöser bzw. keine Ortspruefung und kein Ersatzweg - die Events behalten dann Nummer")
    print("und Zeitspanne bzw. ihre Namen.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
