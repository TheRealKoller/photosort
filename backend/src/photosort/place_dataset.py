"""Das GETIPPTE Bezugskommando: holt den GeoNames-Datensatz und legt daraus den Auszug ab, den
der Auflöser im Betrieb liest.

Aufruf über die Container-Konsole, einmal je Volume::

    docker compose exec backend python -m photosort.place_dataset

Es bezieht `allCountries.zip` (rund 400 MB), bildet daraus den Auszug, löscht das Archiv wieder
und legt den SHA256 des Auszugs daneben. Gemessen (2026-09-14): 5.770.883 Zeilen, 223 MB,
gzip-gepackt 69 MB; ein vollständiger Lese-Durchgang dauert 3,3 s.

DER AUSZUG IST EINE GEONAMES-DATEI MIT GELEERTEN SPALTEN, kein eigenes Format: Er behält die
Spaltenpositionen des Originals und lässt die ungebrauchten Felder leer. Damit liest ihn
`geonames.parse_geonames_line` unverändert, und die Gleichheit zum gemessenen Verhalten ist
strukturell statt argumentiert - dieselben Zeilen, dieselben Felder, derselbe Parser
(`tests/test_place_dataset.py::TestTheExtractBehavesLikeTheRawFile`).

DIESES KOMMANDO BLEIBT VON JEDEM AUTOMATISCHEN PFAD FERN - kein Aufrufpfad aus `main.py`/
`worker.py`, kein Endpunkt, kein Compose-`command`, dieselbe Auflage und derselbe Nachweis wie bei
`place_probe.py`. Ein 400-MB-Abruf tritt nur ein, wenn er getippt wird.

KEIN SHELLSKRIPT AUF DEM HOST: Auf dem Server gibt es keine Shell, nur eine Oberfläche für Docker
Compose und eine Container-Konsole. Eine zweite Fassung desselben Ablaufs driftet, und die auf dem
Server unbrauchbare wäre die schlechtere (ADR 0105 Punkt 3).

SICHERHEIT:

* Die Quell-Adresse ist eine KONSTANTE, der Zielpfad eine Betriebseinstellung - beides nie ein
  Wert aus Datenbank oder Request, kein SSRF-Pfad. Entpackt wird genau ein BENANNTER Eintrag des
  Archivs, nie dessen Verzeichnis: kein Pfad aus fremden Daten.
* DER ERSTBEZUG BLEIBT UNGESCHÜTZT. GeoNames erzeugt das Archiv nächtlich neu und veröffentlicht
  keine Prüfsummen; es gibt keinen vertrauenswürdigen Sollwert, gegen den sich pinnen ließe. Der
  Hash entsteht deshalb hier, aus dem erzeugten Auszug, und trägt ab da jede spätere Prüfung. Eine
  an der Quelle oder auf dem Weg veränderte Datei würde als Sollwert übernommen - bewusst
  akzeptiertes Restrisiko (Daniel, 2026-09-14), getragen davon, dass der Schaden auf falsche
  Ortsnamen in Überschriften begrenzt bleibt.
* Die Spaltenreduktion ist DATENSPARSAMKEIT, keine Injektionsabwehr: gegen Injektion tragen die
  Sanitisierung und die Längengrenze in `places.py`.
* LOGGING: Dieses Kommando schreibt kein Log. Seine Ausgabe trägt Zahlen und Pfade, nie einen
  Ortsnamen und nie eine Koordinate.
"""

from __future__ import annotations

import argparse
import gzip
import io
import sys
import zipfile
from collections.abc import Iterable, Sequence
from pathlib import Path

import httpx

from photosort.config import settings
from photosort.geonames import (
    GEONAMES_FEATURE_CLASS_FIELD,
    GEONAMES_FIELD_COUNT,
    GEONAMES_KEPT_FEATURE_CLASSES,
    GEONAMES_KEPT_FIELDS,
    dataset_hash_path,
    sha256_of,
)

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
    """Eine Rohzeile als AUSZUGS-Zeile, oder `None`, wenn sie nicht in den Auszug gehoert.

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


def write_extract(lines: Iterable[str], target: Path) -> int:
    """Schreibt den gzip-gepackten Auszug und legt seinen SHA256 daneben. Rueckgabe: Zeilenzahl.

    Der Hash entsteht AUS DER GESCHRIEBENEN DATEI, nicht aus dem Speicherinhalt - geprueft wird
    spaeter genau die Datei, die gelesen wird."""
    target.parent.mkdir(parents=True, exist_ok=True)
    kept = 0
    with gzip.open(target, "wt", encoding="utf-8") as handle:
        for line in lines:
            extracted = extract_line(line)
            if extracted is None:
                continue
            handle.write(extracted + "\n")
            kept += 1
    dataset_hash_path(target).write_text(sha256_of(target) + "\n", encoding="utf-8")
    return kept


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


def build_dataset(target: Path) -> int:
    """Bezug, Auszug, Hash - und danach ist das Archiv wieder fort.

    Das Archiv liegt neben dem Auszug und wird in JEDEM Ausgang geloescht: es misst rund 400 MB,
    und ein liegengebliebenes Archiv fuellte das Volume ohne Nutzen."""
    target.parent.mkdir(parents=True, exist_ok=True)
    archive = target.with_name("allCountries.zip")
    try:
        print(f"Beziehe {GEONAMES_ARCHIVE_URL} (rund 400 MB)...")
        _download_archive(archive)
        print("Bilde den Auszug (Klassen P und A, ungebrauchte Spalten geleert)...")
        with zipfile.ZipFile(archive) as bundle, bundle.open(GEONAMES_ARCHIVE_MEMBER) as member:
            kept = write_extract(
                io.TextIOWrapper(member, encoding="utf-8", errors="replace"), target
            )
    finally:
        archive.unlink(missing_ok=True)
    return kept


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m photosort.place_dataset",
        description=(
            "Bezieht den GeoNames-Datensatz und legt den Auszug samt SHA256 ab. Einmal je "
            "Volume - ein 400-MB-Abruf tritt nur ein, wenn er getippt wird."
        ),
    )
    parser.add_argument(
        "--pfad",
        default=None,
        help=(
            "Zielpfad des Auszugs. Ohne Angabe gilt die Betriebseinstellung "
            "PLACE_DATASET_PATH (Vorgabe: der Pfad auf dem Volume)."
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Verdrahtung + Exit-Code. `argv` ist injizierbar - kein `sys.argv`-Zugriff im Testpfad."""
    args = _build_parser().parse_args(argv)
    target = Path(args.pfad) if args.pfad else Path(settings.place_dataset_path)
    try:
        kept = build_dataset(target)
    except (OSError, httpx.HTTPError, zipfile.BadZipFile) as exc:
        # Nur der Fehlertyp, nie die Meldung: sie kann einen Pfad oder eine Adresse tragen, und
        # der Abbruch ist ohnehin nur ueber die Bedingung zu beheben (Muster place_probe.py).
        print(f"Fehler: Bezug fehlgeschlagen ({type(exc).__name__}).", file=sys.stderr)
        return 1
    print(f"Fertig. {kept} Zeilen im Auszug: {target}")
    print(f"SHA256 abgelegt: {dataset_hash_path(target)}")
    print("Der Auszug wird vor jedem Gebrauch dagegen geprueft; bei Abweichung entsteht kein")
    print("Auflöser und kein Ersatzweg - die Events behalten dann Nummer und Zeitspanne.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
