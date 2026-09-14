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

import hashlib
import os
import re
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

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

# Die Form, in der der Zeilenparser von `backend/tests/test_migration_chain.py` die Kennung
# sieht. Faellt sie, sieht das bestehende Sicherheitsnetz die neuen Kennungen still nicht mehr.
KENNUNGSFORM = re.compile(r"[0-9a-f]{12}")

# Kleinbuchstaben, Ziffern, einfache Bindestriche, kein fuehrender/abschliessender Strich. Der
# Slug ist der einzige frei gewaehlte Wert, der von aussen in einen Dateinamen laeuft: kein
# Pfadtrenner, kein `..`, kein fuehrender Bindestrich.
SLUGFORM = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
SLUG_HOECHSTLAENGE = 60


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


# --- Alembic: die Kennung ----------------------------------------------------------------------


def revisionskennung(branch: str, slug: str) -> str:
    """Die ersten zwoelf Hex-Zeichen aus `sha256(<Branch> + NUL + <Slug>)`.

    Der Branchname ist ohne Abstimmung eindeutig, weil git denselben Branch nie in zwei
    Arbeitsbaeumen auscheckt; eine doppelt vergebene Kennung ist damit nicht mehr aufzuloesen,
    sondern ausgeschlossen. Der NUL-Trenner schliesst aus, dass zwei verschiedene Eingabepaare
    (`"ab"`/`"c"` und `"a"`/`"bc"`) auf dieselbe Kennung fallen.
    """
    roh = hashlib.sha256(branch.encode("utf-8") + b"\0" + slug.encode("utf-8")).hexdigest()
    return roh[:12]


def gepruefte_kennung(kennung: str) -> str:
    """Prueft die eigene Ausgabe, bevor sie einen Dateinamen bildet."""
    if KENNUNGSFORM.fullmatch(kennung) is None:
        raise ZuteilerFehler(
            f"Die Revisionskennung hat nicht die Form von zwoelf Kleinbuchstaben-Hex "
            f"(Laenge {len(kennung)}). In dieser Form sieht der Zeilenparser von "
            "backend/tests/test_migration_chain.py sie nicht mehr."
        )
    return kennung


def gepruefter_slug(slug: str) -> str:
    """Prueft den einzigen frei gewaehlten Wert, der in einen Dateinamen laeuft."""
    if len(slug) > SLUG_HOECHSTLAENGE or SLUGFORM.fullmatch(slug) is None:
        raise ZuteilerFehler(
            f"Unzulaessiger Slug (Laenge {len(slug)}). Zulaessig sind hoechstens "
            f"{SLUG_HOECHSTLAENGE} Zeichen aus Kleinbuchstaben und Ziffern, getrennt durch "
            "einfache Bindestriche - kein Pfadtrenner, kein '..', kein fuehrender Bindestrich."
        )
    return slug


# --- Der Leser: vier Quellen, keine davon mit einem `cd` in einen fremden Arbeitsbaum ----------

ZEITGRENZE_SEKUNDEN = 60

# Der zweite Eingabekanal. Mit gesetztem GIT_DIR/GIT_WORK_TREE lasen sowohl `git ls-tree` als
# auch `git worktree list --porcelain` gemessen ein **fremdes** Repositorium - die Basis kaeme
# still aus dem falschen Nummernraum.
UMGEBUNG_ENTFERNT: tuple[str, ...] = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_COMMON_DIR",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_CONFIG_COUNT",
)

_FERNPRAEFIX = "refs/remotes/origin/"
ORIGIN_MAIN = f"{_FERNPRAEFIX}main"


@dataclass(frozen=True)
class Arbeitsbaum:
    pfad: str
    branch: str | None
    bar: bool
    losgeloest: bool
    raeumbar: bool


@dataclass(frozen=True)
class Sicht:
    """Was ein Lauf gesehen hat, samt Zaehler darueber, dass ueberhaupt gelesen wurde."""

    verzeichnis: str
    basis: int
    eigener_branch: str
    gefuehrt: Mapping[str, tuple[int, ...]]
    gelesen: int
    arbeitsbaeume: int
    fremde_branches: int


def gesaeuberte_umgebung() -> dict[str, str]:
    return {name: wert for name, wert in os.environ.items() if name not in UMGEBUNG_ENTFERNT}


def git_ausgabe(args: Sequence[str], *, cwd: Path) -> bytes:
    """Ein `git`-Aufruf ohne Shell, mit gesaeuberter Umgebung und Zeitgrenze.

    Eine unerwartete Rueckgabe haelt den Lauf an und wird nie als "keine Nummern gefunden"
    verbucht. Die Meldung nennt den Unterbefehl und die Rueckgabe, nie die Ausgabe von `git`:
    ein `fatal:`-Text traegt Pfade, `git remote get-url` kann ein Token tragen.
    """
    try:
        fertig = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            env=gesaeuberte_umgebung(),
            capture_output=True,
            timeout=ZEITGRENZE_SEKUNDEN,
            check=False,
        )
    except subprocess.TimeoutExpired as grund:
        raise ZuteilerFehler(f"git {args[0]} hat die Zeitgrenze ueberschritten") from grund
    if fertig.returncode != 0:
        raise ZuteilerFehler(
            f"git {args[0]} endete mit {fertig.returncode}. Damit ist dieser Stand nicht "
            "gemessen; ein geratener Nullbefund vergaebe eine belegte Nummer."
        )
    return fertig.stdout


def nul_felder(rohdaten: bytes) -> list[str]:
    """NUL-getrennte Felder. `for-each-ref` haengt je Satz zusaetzlich einen Zeilenumbruch an;
    ein Branchname kann keinen tragen (`git check-ref-format`), ein Arbeitsbaumpfad schon -
    deshalb wird nur der fuehrende Umbruch abgestreift."""
    return [feld.decode("utf-8").lstrip("\n") for feld in rohdaten.split(b"\0") if feld.strip()]


def arbeitsbaeume_aus_porcelain(rohdaten: bytes) -> tuple[Arbeitsbaum, ...]:
    """Reine Funktion: `git worktree list --porcelain -z` zu Eintraegen.

    Ohne `-z` zerbricht die Form an einem Zeilenumbruch im Arbeitsbaumpfad. Ein `detached`
    liefert **keinen** leeren Branchnamen: Der sortierte byteweise ganz vorn und schoebe jeden
    anderen Kontrahenten um eine Nummer weiter.
    """
    baeume: list[Arbeitsbaum] = []
    pfad: str | None = None
    branch: str | None = None
    bar = False
    losgeloest = False
    raeumbar = False
    for feld in rohdaten.split(b"\0"):
        text = feld.decode("utf-8")
        if text == "":
            if pfad is not None:
                baeume.append(Arbeitsbaum(pfad, branch, bar, losgeloest, raeumbar))
            pfad, branch, bar, losgeloest, raeumbar = None, None, False, False, False
            continue
        schluessel, _, wert = text.partition(" ")
        if schluessel == "worktree":
            pfad = wert
        elif schluessel == "branch":
            branch = wert.removeprefix("refs/heads/")
        elif schluessel == "bare":
            bar = True
        elif schluessel == "detached":
            losgeloest = True
        elif schluessel == "prunable":
            raeumbar = True
    if pfad is not None:
        baeume.append(Arbeitsbaum(pfad, branch, bar, losgeloest, raeumbar))
    return tuple(baeume)


def branches_aus_refnamen(refnamen: Iterable[str]) -> tuple[str, ...]:
    """Reine Funktion: Tracking-Refs zu Branchnamen, ohne den symbolischen `origin/HEAD`.

    `git branch -r` gaebe hier die Zeile `origin/HEAD -> origin/main` aus, die kein Branchname
    ist - deshalb `git for-each-ref`.
    """
    namen = []
    for refname in refnamen:
        if not refname.startswith(_FERNPRAEFIX):
            continue
        name = refname[len(_FERNPRAEFIX) :]
        if name == "HEAD":
            continue
        namen.append(name)
    return tuple(sorted(set(namen), key=lambda name: name.encode("utf-8")))


def nummern_aus_pfaden(pfade: Iterable[str], verzeichnis: str) -> Ablesung:
    """Reine Funktion: repo-relative Pfade zu Nummern - nur die unmittelbare Ebene."""
    namen = []
    for pfad in pfade:
        elter, trenner, name = pfad.rpartition("/")
        if trenner and elter == verzeichnis:
            namen.append(name)
    return nummern_aus_namen(namen)


def eigener_branch(wurzel: Path) -> str:
    rohdaten = git_ausgabe(["symbolic-ref", "--quiet", "HEAD"], cwd=wurzel)
    return rohdaten.decode("utf-8").strip().removeprefix("refs/heads/")


def eigene_wurzel(wurzel: Path) -> Path:
    rohdaten = git_ausgabe(["rev-parse", "--show-toplevel"], cwd=wurzel)
    return Path(rohdaten.decode("utf-8").strip())


def nummern_eines_refs(wurzel: Path, ref: str, verzeichnis: str) -> Ablesung:
    """Der committete Stand eines Branches, gelesen aus dem eigenen Arbeitsbaum heraus.

    `--end-of-options` ist keine Stilfrage: Gemessen endet
    `git ls-tree -r --name-only -rf -- specs/decisions` mit 129, waehrend derselbe Aufruf mit
    `--end-of-options` sauber durchlaeuft. Ohne die Absicherung bliebe ein Branch mit einem
    Namen, der wie eine Option aussieht, ein **unsichtbarer** Kontrahent.
    """
    rohdaten = git_ausgabe(
        ["ls-tree", "-r", "-z", "--name-only", "--end-of-options", ref, "--", verzeichnis],
        cwd=wurzel,
    )
    return nummern_aus_pfaden(nul_felder(rohdaten), verzeichnis)


def nummern_auf_origin_main(wurzel: Path, verzeichnis: str) -> Ablesung:
    return nummern_eines_refs(wurzel, ORIGIN_MAIN, verzeichnis)


def nummern_im_index(wurzel: Path, verzeichnis: str) -> Ablesung:
    """Der eigene Arbeitsbaum, einschliesslich noch nicht hinzugefuegter Dateien.

    `--others` faengt die Datei **vor** dem `git add` - genau dann entsteht die Dublette. Mitten
    im Abgleich mit `main` listet `--cached` denselben Pfad je Stage mehrfach; die Nummern
    landen in einer Menge.
    """
    rohdaten = git_ausgabe(
        ["ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", verzeichnis],
        cwd=wurzel,
    )
    return nummern_aus_pfaden(nul_felder(rohdaten), verzeichnis)


def nummern_im_verzeichnis(pfad: Path) -> Ablesung:
    """Eine Verzeichnisebene eines Arbeitsbaums - nur Dateinamen, nie Dateiinhalte.

    Derselbe Namensfilter wie beim Blick auf den eigenen Arbeitsbaum. Wendete die
    Nachbarauflistung einen anderen an, zaehlten zwei Seiten dieselbe Datei verschieden, und
    jede darauf gebaute Determinismus-Zusage waere still falsch.
    """
    if not pfad.is_dir():
        return Ablesung(frozenset(), 0, 0)
    return nummern_aus_namen(
        eintrag.name for eintrag in os.scandir(pfad) if eintrag.is_file(follow_symlinks=False)
    )


def fremde_arbeitsbaeume(wurzel: Path, eigene: Path) -> tuple[Arbeitsbaum, ...]:
    rohdaten = git_ausgabe(["worktree", "list", "--porcelain", "-z"], cwd=wurzel)
    aufgeloest = eigene.resolve()
    fremde = []
    for baum in arbeitsbaeume_aus_porcelain(rohdaten):
        if baum.bar or Path(baum.pfad).resolve() == aufgeloest:
            continue
        if baum.losgeloest or baum.branch is None:
            raise ZuteilerFehler(
                f"Ein Nachbar-Arbeitsbaum steht auf einem losgeloesten HEAD ({baum.pfad}). "
                "Seine Nummern lassen sich keinem Branch zurechnen, und ein leerer Name "
                "sortierte byteweise ganz vorn - hier wird angehalten statt geraten."
            )
        fremde.append(baum)
    return tuple(fremde)


def gepushte_branches(wurzel: Path) -> tuple[str, ...]:
    """Jeder gepushte Branch, der nicht in `origin/main` enthalten ist.

    Massgeblich ist `--no-merged origin/main`: Gesucht sind die Branches, deren Arbeit dort noch
    **nicht** liegt.
    """
    rohdaten = git_ausgabe(
        [
            "for-each-ref",
            "--format=%(refname)%00",
            "--no-merged",
            ORIGIN_MAIN,
            "refs/remotes/origin/",
        ],
        cwd=wurzel,
    )
    return branches_aus_refnamen(nul_felder(rohdaten))


def erhebe_sicht(wurzel: Path, raum: str) -> Sicht:
    """Alle vier Quellen zu einer Sicht - ohne Schreibzugriff und ohne Wartepunkt.

    Kein `cd` und kein `git -C` in einen fremden Arbeitsbaum: dessen Index gehoert einer parallel
    laufenden Sitzung. Gelesen wird von dort nur die eine Verzeichnisebene, und nur Dateinamen.
    """
    verzeichnis = NUMMERNRAEUME[raum]
    eigene = eigene_wurzel(wurzel)
    eigen = eigener_branch(wurzel)

    basis_ablesung = nummern_auf_origin_main(wurzel, verzeichnis)
    gelesen = basis_ablesung.gelesen
    gefuehrt: dict[str, set[int]] = {eigen: set()}

    eigene_ablesung = nummern_im_index(wurzel, verzeichnis)
    aufgelistet = nummern_im_verzeichnis(eigene / verzeichnis)
    gefuehrt[eigen] |= set(eigene_ablesung.nummern) | set(aufgelistet.nummern)
    gelesen += eigene_ablesung.gelesen

    baeume = fremde_arbeitsbaeume(wurzel, eigene)
    for baum in baeume:
        assert baum.branch is not None
        aus_tree = nummern_eines_refs(wurzel, f"refs/heads/{baum.branch}", verzeichnis)
        nachbarschaft = nummern_im_verzeichnis(Path(baum.pfad) / verzeichnis)
        gefuehrt.setdefault(baum.branch, set())
        gefuehrt[baum.branch] |= set(aus_tree.nummern) | set(nachbarschaft.nummern)
        gelesen += aus_tree.gelesen + nachbarschaft.gelesen

    fremde = tuple(name for name in gepushte_branches(wurzel) if name not in gefuehrt)
    for name in fremde:
        aus_tree = nummern_eines_refs(wurzel, f"{_FERNPRAEFIX}{name}", verzeichnis)
        gefuehrt.setdefault(name, set())
        gefuehrt[name] |= set(aus_tree.nummern)
        gelesen += aus_tree.gelesen

    return Sicht(
        verzeichnis=verzeichnis,
        basis=basis_aus_nummern(basis_ablesung.nummern, quelle=verzeichnis),
        eigener_branch=eigen,
        gefuehrt={name: tuple(sorted(nummern)) for name, nummern in gefuehrt.items()},
        gelesen=gelesen,
        arbeitsbaeume=len(baeume) + 1,
        fremde_branches=len(fremde),
    )
