#!/usr/bin/env python3
"""Zuteiler und Fruehwarnung fuer Dokumentnummern und Alembic-Revisionskennungen.

Zwei Sitzungen, die gleichzeitig in eigenen Arbeitsstaenden arbeiten, vergeben sonst dieselbe
Nummer: Die konkurrierende Vergabe liegt in einem Branch, der noch nirgends gepusht ist. Dieses
Skript rechnet die Nummer so aus, dass **beide Seiten fuer sich dasselbe Ergebnis erhalten** -
ohne Nachricht, ohne Sperre und ohne Wartepunkt (ADR 0108).

**Die Rechnung.** Basis ist die hoechste auf `origin/main` vergebene Nummer des Verzeichnisses
plus eins - nie der eigene Blick, sonst rechnet jede Seite mit einer anderen Basis. Kontrahenten
sind alle Branches, die im selben Nummernraum eine Nummer ab der Basis fuehren, zuzueglich des
eigenen; sortiert wird byteweise nach dem vollstaendigen Branchnamen. Die eigene Nummer ist die
Basis plus die Summe der Nummern, die rangniedrigere Kontrahenten sichtbar fuehren.

**In CI sieht der nachbarlesende Teil nichts**, weil es dort weder einen zweiten Arbeitsbaum noch
einen ungepushten Branch gibt. Eine gruene CI belegt die Fruehwarnung deshalb nicht.

Sicherheitsauflagen, die still brechen, wenn sie fallen (Spec 0485, S1-S8):

* Jeder Branchname und jeder Pfad geht als Listenelement an `subprocess.run`, nie ueber eine
  Shell, und jeder Aufruf mit einem Branchnamen als Tree-ish uebergibt den voll qualifizierten
  `refs/heads/<name>` bzw. schiebt `--end-of-options` davor. Die Listenform allein genuegt nicht:
  `git ls-tree -r --name-only -rf -- specs/decisions` endet gemessen mit 129. Ausfallrichtung ist
  keine Codeausfuehrung, sondern ein **unsichtbarer Kontrahent** - also genau die Doppelvergabe.
* Die Umgebung ist der zweite Eingabekanal: Vor jedem `git`-Aufruf werden `GIT_DIR`,
  `GIT_WORK_TREE`, `GIT_COMMON_DIR`, `GIT_INDEX_FILE`, `GIT_OBJECT_DIRECTORY`,
  `GIT_ALTERNATE_OBJECT_DIRECTORIES` und `GIT_CONFIG_COUNT` entfernt. Sonst liest der Zuteiler
  ein fremdes Repositorium und die Basis kommt aus dem falschen Nummernraum.
* Gelesen wird NUL-getrennt (`-z`), und die Branchliste ueber `git for-each-ref` statt
  `git branch -r`: Ohne `-z` verfremdet git einen Namen mit Umlaut zu `"...\\303\\244..."`, das
  Nummernmuster greift nicht mehr, und der Kontrahent wird unsichtbar.
* Fail-closed an jedem Ausgang: Von 0/10/20/30 kann allein die 0 still falsch sein, und sie
  entsteht an genau einer Stelle. Eine unerwartete Rueckgabe von `git` haelt den Lauf an und wird
  nie als "keine Nummern gefunden" verbucht.
* Die eigene Ausgabe wird geprueft, bevor sie einen Dateinamen bildet: Kennung gegen
  `^[0-9a-f]{12}$`, Slug gegen ein geschlossenes Muster, beides per `re.fullmatch` - `$` passt
  auch unmittelbar vor einem abschliessenden Zeilenumbruch.
* Umgehaengt werden ausschliesslich Revisionen, die von `origin/main` nicht erreichbar sind;
  laesst sich diese Menge nicht bestimmen, wird angehalten statt umgehaengt. Aendert sich Kennung
  oder `down_revision` einer bereits ausgefuehrten Revision, findet `alembic upgrade head` beim
  Containerstart den Wert aus `alembic_version` nicht mehr und das Backend startet nicht.
* Ausserhalb des eigenen Arbeitsbaums wird gelesen, nicht geschrieben, und nur benannt, nicht
  geoeffnet: kein `cd` und kein `git -C` in einen fremden Arbeitsbaum, keine Rekursion, nur die
  eine Verzeichnisebene des Nummernraums, nur Dateinamen.
* Ausgabehygiene: selbst erzeugter Text und gepruefte Token, nie rohe `git`-Ausgabe. Ein
  Dateiname, der das Nummernmuster nicht besteht, wird gezaehlt, nicht zitiert.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

# Exit-Codes wie in `merge-main-into-branch.sh`: 0 ist der einzige Ausgang ohne Handlungsbedarf.
EXIT_OK = 0
EXIT_KONTENTION = 10
EXIT_DUBLETTE = 20
EXIT_VORBEDINGUNG = 30

# Die Nummernraeume, die dieser Zuteiler bedient. `specs/features` steht bewusst nicht hier:
# Dort vergibt GitHub die Nummer mit dem Issue, und zwei Laeufe koennen sie nicht doppelt ziehen.
NUMMERNRAEUME: Mapping[str, str] = {
    "decisions": "specs/decisions",
    "architecture": "specs/architecture",
}
ABGELEHNTER_RAUM = "features"

# Vierstellige Nummer, Trennstrich, nicht-leerer Rumpf, `.md` - dasselbe Muster, an dem
# `test_dokumentnummern_eindeutig.py` die Eindeutigkeit misst.
_DOKUMENTNAME = re.compile(r"^(?P<nummer>\d{4})-.+\.md$")


class ZuteilerFehler(Exception):
    """Ein Zustand, der nicht gemessen werden konnte - nie ein Nullbefund."""


@dataclass(frozen=True)
class Ablesung:
    """Was eine Quelle hergab, samt Beleg, dass ueberhaupt gelesen wurde.

    `gelesen` und `verworfen` tragen den Selbstschutz: Eine leere Nummernmenge ist von einer
    kaputten Aufzaehlung sonst nicht zu unterscheiden.
    """

    nummern: frozenset[int]
    gelesen: int
    verworfen: int


@dataclass(frozen=True)
class Kontrahent:
    branch: str
    nummern: tuple[int, ...]


def nummern_aus_namen(namen: Iterable[str]) -> Ablesung:
    """Reine Funktion: Dateinamen einer Verzeichnisebene zu Nummern.

    Gefiltert wird ausschliesslich ueber den Namen - derselbe Filter fuer den eigenen
    Arbeitsbaum und fuer die Auflistung eines Nachbarn. Wendeten beide Seiten verschiedene
    Filter an, zaehlten sie dieselbe Datei verschieden, und jede darauf gebaute
    Determinismus-Zusage waere still falsch.
    """
    nummern: set[int] = set()
    gelesen = 0
    verworfen = 0
    for name in namen:
        gelesen += 1
        treffer = _DOKUMENTNAME.fullmatch(name)
        if treffer is None:
            verworfen += 1
            continue
        nummern.add(int(treffer.group("nummer")))
    return Ablesung(frozenset(nummern), gelesen, verworfen)


def basis_aus_nummern(nummern: Iterable[int], *, quelle: str) -> int:
    """Reine Funktion: hoechste Nummer plus eins, lauter Fehler bei leerer Menge.

    Der stille Fall waere hier der schlimmste: Basis 1, ausgegeben wuerde `0001` - eine Nummer,
    die im Bestand jedes Nummernraums seit Jahren vergeben ist.
    """
    vorhanden = sorted(nummern)
    if not vorhanden:
        raise ZuteilerFehler(
            f"Keine einzige Nummer in {quelle} auf origin/main gefunden. Damit ist die Basis "
            "nicht gemessen, und eine geratene Basis vergaebe eine laengst belegte Nummer."
        )
    return vorhanden[-1] + 1


def kontrahenten(
    basis: int, gefuehrt: Mapping[str, Sequence[int]], eigener_branch: str
) -> tuple[Kontrahent, ...]:
    """Reine Funktion: alle Branches mit einer Nummer ab der Basis, plus der eigene.

    Byteweise sortiert (`str.encode`), nicht ueber die Locale der jeweiligen Sitzung: Kippte die
    Ordnung mit der Locale, rechneten zwei Seiten verschieden.
    """
    gefunden: dict[str, tuple[int, ...]] = {}
    for branch, nummern in gefuehrt.items():
        ab_basis = tuple(sorted({nummer for nummer in nummern if nummer >= basis}))
        if ab_basis or branch == eigener_branch:
            gefunden[branch] = ab_basis
    gefunden.setdefault(eigener_branch, ())
    return tuple(
        Kontrahent(branch, gefunden[branch])
        for branch in sorted(gefunden, key=lambda name: name.encode("utf-8"))
    )


def zugeteilte_nummer(
    basis: int, gefuehrt: Mapping[str, Sequence[int]], eigener_branch: str
) -> int:
    """Reine Funktion: Basis plus alles, was rangniedrigere Kontrahenten sichtbar fuehren."""
    schluessel = eigener_branch.encode("utf-8")
    belegt = sum(
        len(kontrahent.nummern)
        for kontrahent in kontrahenten(basis, gefuehrt, eigener_branch)
        if kontrahent.branch.encode("utf-8") < schluessel
    )
    return basis + belegt


def befundzeilen(
    basis: int, gefuehrt: Mapping[str, Sequence[int]], eigener_branch: str
) -> list[str]:
    """Reine Funktion: je kontrahierendem fremden Branch eine Zeile mit Name und Nummern."""
    schluessel = eigener_branch.encode("utf-8")
    zeilen: list[str] = []
    for kontrahent in kontrahenten(basis, gefuehrt, eigener_branch):
        if kontrahent.branch == eigener_branch or not kontrahent.nummern:
            continue
        rang = "vor" if kontrahent.branch.encode("utf-8") < schluessel else "nach"
        gefuehrte = ", ".join(f"{nummer:04d}" for nummer in kontrahent.nummern)
        zeilen.append(f"{kontrahent.branch} fuehrt {gefuehrte} und rangiert {rang} dem eigenen")
    return zeilen
