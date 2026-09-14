#!/usr/bin/env python3
"""Zuteiler und Fruehwarnung fuer Dokumentnummern und Alembic-Revisionskennungen.

Zwei Sitzungen, die gleichzeitig in eigenen Arbeitsstaenden arbeiten, vergeben sonst dieselbe
Nummer: Die konkurrierende Vergabe liegt in einem Branch, der noch nirgends gepusht ist. Dieses
Skript rechnet die Nummer so aus, dass **beide Seiten fuer sich dasselbe Ergebnis erhalten** -
ohne Nachricht, ohne Sperre und ohne Wartepunkt (ADR 0108).

**Die Rechnung.** Basis ist die hoechste auf `origin/main` vergebene Nummer des Verzeichnisses
plus eins - nie der eigene Blick, sonst rechnet jede Seite mit einer anderen Basis. Kontrahenten
sind alle Branches, die im selben Nummernraum eine Nummer ab der Basis fuehren, zuzueglich des
eigenen; sortiert wird byteweise nach dem vollstaendigen Branchnamen. Zugeteilt wird dann in zwei
Gaengen: Jeder behaelt in Rangfolge seine niedrigste gefuehrte Nummer, und wer nichts behalten
konnte, bekommt die naechste Nummer ab der Basis, die kein Kontrahent fuehrt (siehe
`zuteilung_je_kontrahent`).

**In CI sieht der nachbarlesende Teil nichts**, weil es dort weder einen zweiten Arbeitsbaum noch
einen ungepushten Branch gibt. Eine gruene CI belegt die Fruehwarnung deshalb nicht.

Sicherheitsauflagen, die still brechen, wenn sie fallen (Spec 0485, S1-S8):

* Jeder Branchname und jeder Pfad geht als Listenelement an `subprocess.run`, nie ueber eine
  Shell, und jeder Aufruf mit einem Branchnamen als Tree-ish uebergibt den voll qualifizierten
  `refs/heads/<name>` bzw. schiebt `--end-of-options` davor - die Listenform allein genuegt
  nicht, weil git einen Branchnamen wie `-rf` sonst als Option liest. Ausfallrichtung ist keine
  Codeausfuehrung, sondern ein **unsichtbarer Kontrahent** - also genau die Doppelvergabe.
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
import sys
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


def zuteilung_je_kontrahent(
    basis: int, gefuehrt: Mapping[str, Sequence[int]], eigener_branch: str
) -> dict[str, int]:
    """Reine Funktion: die vollstaendige Zuteilung ueber der Kontrahentenmenge, in zwei Gaengen.

    **Erster Gang, in Rangfolge:** Jeder Kontrahent behaelt seine niedrigste sichtbar gefuehrte
    Nummer, sofern eine rangniedrigere Seite sie nicht schon beansprucht hat. Das ist der Fall
    aus ADR 0108 Punkt 4: Fuehren zwei Seiten dieselbe Nummer, behaelt sie die rangniedrigere.

    **Zweiter Gang, wieder in Rangfolge:** Wer nichts behalten konnte - weil er noch keine Datei
    angelegt hat oder weil eine rangniedrigere Seite seine Nummer hielt -, bekommt die naechste
    Nummer ab der Basis, die **kein** Kontrahent fuehrt und die in diesem Lauf noch niemand
    bekommen hat.

    **Gezaehlt wird nicht.** Eine Rechnung, die nur die Anzahl der von rangniedrigeren
    Kontrahenten gefuehrten Nummern auf die Basis addiert, ist ausschliesslich dann
    kollisionsfrei, wenn diese Nummern lueckenlos ab der Basis liegen. Eine Luecke entsteht ohne
    jede Handvergabe: Ein Branch ohne Arbeitsbaum und ohne `origin`-Gegenstueck ist nach Punkt 1
    kein Kontrahent mehr, und wer die Basisnummer fuehrte, hinterlaesst beim Verschwinden genau
    diese Luecke. Ab da teilte die Zaehlung Nummern zu, die andere Branches bereits fuehren.

    Die Zuteilung haengt nur an der Kontrahentenmenge, nicht daran, wer fragt: Jede Seite
    errechnet dieselbe Abbildung, ohne Nachricht und ohne Wartepunkt.
    """
    reihe = kontrahenten(basis, gefuehrt, eigener_branch)
    belegt = {nummer for kontrahent in reihe for nummer in kontrahent.nummern}

    vergeben: dict[str, int] = {}
    genommen: set[int] = set()
    offen: list[str] = []
    for kontrahent in reihe:
        behalten = [nummer for nummer in kontrahent.nummern if nummer not in genommen]
        if behalten:
            vergeben[kontrahent.branch] = behalten[0]
            genommen.add(behalten[0])
        else:
            offen.append(kontrahent.branch)

    naechste = basis
    for branch in offen:
        while naechste in belegt or naechste in genommen:
            naechste += 1
        vergeben[branch] = naechste
        genommen.add(naechste)
    return vergeben


def zugeteilte_nummer(
    basis: int, gefuehrt: Mapping[str, Sequence[int]], eigener_branch: str
) -> int:
    """Reine Funktion: die eigene Nummer aus der Zuteilung ueber der Kontrahentenmenge."""
    return zuteilung_je_kontrahent(basis, gefuehrt, eigener_branch)[eigener_branch]


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

    `--end-of-options` ist keine Stilfrage: Ohne es liest git einen Branchnamen, der wie eine
    Option aussieht (`-rf`), als Option und bricht ab - der Branch bliebe ein **unsichtbarer**
    Kontrahent. Ein solcher Name ist anlegbar: `git branch` weigert sich, `git update-ref` nicht.
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


def eigene_dokumente(wurzel: Path, verzeichnis: str) -> dict[int, tuple[str, ...]]:
    """Je Nummer die Dateinamen, die sie im eigenen Arbeitsbaum tragen.

    Eine Nummer mit zwei Namen ist die Dublette, die das Sicherheitsnetz in CI spaetestens beim
    Zusammenfuehren meldet - hier wird sie im laufenden Arbeitskontext sichtbar.
    """
    eigene = eigene_wurzel(wurzel)
    rohdaten = git_ausgabe(
        ["ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", verzeichnis],
        cwd=wurzel,
    )
    namen = {
        pfad.rpartition("/")[2]
        for pfad in nul_felder(rohdaten)
        if pfad.rpartition("/")[0] == verzeichnis
    }
    ort = eigene / verzeichnis
    if ort.is_dir():
        namen |= {
            eintrag.name for eintrag in os.scandir(ort) if eintrag.is_file(follow_symlinks=False)
        }
    je_nummer: dict[int, set[str]] = {}
    for name in namen:
        treffer = _DOKUMENTNAME.fullmatch(name)
        if treffer is not None:
            je_nummer.setdefault(int(treffer.group("nummer")), set()).add(name)
    return {nummer: tuple(sorted(namen)) for nummer, namen in je_nummer.items()}


# --- Die Migrationskette -----------------------------------------------------------------------

VERSIONSVERZEICHNIS = "backend/alembic/versions"

# Dieselben beiden Zeilenanfaenge, an denen `backend/tests/test_migration_chain.py` die Kennung
# liest. `alembic` wird bewusst keine Abhaengigkeit von `scripts/`; die Autoritaet ueber die
# echte Kette bleibt beim Netz im Backend, und ein Bindetest misst, dass beide ueber den echten
# Bestand dasselbe sagen.
_REVISIONSZEILEN = ("revision: str = ", "revision = ")
_VORGAENGERZEILEN = ("down_revision: ", "down_revision = ")


@dataclass(frozen=True)
class Migration:
    kennung: str
    unten: str | None
    pfad: Path


def _wert_der_zeile(zeile: str) -> str | None:
    wert = zeile.split("=", 1)[1].strip()
    return None if wert == "None" else wert.strip("\"'")


def migration_aus_datei(pfad: Path) -> Migration:
    """Zeilenparser statt Import: eine Migrationsdatei wird nie ausgefuehrt."""
    return migration_aus_text(pfad.read_text(encoding="utf-8"), pfad)


def migration_aus_text(text: str, pfad: Path) -> Migration:
    kennung: str | None = None
    unten: str | None = None
    for zeile in text.splitlines():
        if kennung is None and zeile.startswith(_REVISIONSZEILEN):
            kennung = _wert_der_zeile(zeile)
        elif zeile.startswith(_VORGAENGERZEILEN):
            unten = _wert_der_zeile(zeile)
    if kennung is None:
        raise ZuteilerFehler(
            f"Keine Revisionszeile in {pfad.name}. Ohne sie faellt die Datei aus jeder "
            "Kettenpruefung heraus, statt von ihr erfasst zu werden."
        )
    return Migration(gepruefte_kennung(kennung), unten, pfad)


def aufgeloeste_kette(versionen: Path) -> tuple[Migration, ...]:
    """Die Kette von unten nach oben, mit genau einem Fuss und genau einem Kopf.

    Ein mehrdeutiger Kopf wird gemeldet, nie geraten: Bei zwei Koepfen ist `head` mehrdeutig und
    `alembic upgrade head` - der Startbefehl des Backend-Containers - bricht ab.
    """
    eintraege = {
        gelesen.kennung: gelesen
        for gelesen in (migration_aus_datei(pfad) for pfad in sorted(versionen.glob("*.py")))
    }
    if not eintraege:
        raise ZuteilerFehler(f"Keine Migration in {VERSIONSVERZEICHNIS} gefunden.")

    fuesse = [eintrag for eintrag in eintraege.values() if eintrag.unten is None]
    if len(fuesse) != 1:
        raise ZuteilerFehler(
            f"{len(fuesse)} Migrationen ohne down_revision - die Kette hat nicht genau einen Fuss."
        )
    darueber: dict[str, list[Migration]] = {}
    for eintrag in eintraege.values():
        if eintrag.unten is not None:
            if eintrag.unten not in eintraege:
                raise ZuteilerFehler(
                    f"down_revision von {eintrag.pfad.name} zeigt auf eine Revision, die es "
                    "nicht gibt. Die Kette loest nicht auf."
                )
            darueber.setdefault(eintrag.unten, []).append(eintrag)

    kette = [fuesse[0]]
    while True:
        folger = darueber.get(kette[-1].kennung, [])
        if len(folger) > 1:
            raise ZuteilerFehler(
                f"{len(folger)} Migrationen haengen an {kette[-1].kennung} - die Kette hat mehr "
                "als einen Kopf, und 'head' ist damit mehrdeutig."
            )
        if not folger:
            break
        kette.append(folger[0])
    if len(kette) != len(eintraege):
        raise ZuteilerFehler(
            f"{len(eintraege)} Migrationen, aber nur {len(kette)} von unten erreichbar - die "
            "Kette faellt auseinander."
        )
    return tuple(kette)


def kopf_der_menge(eintraege: Iterable[Migration]) -> str:
    """Die eine Revision einer Menge, auf die keine andere derselben Menge zeigt."""
    vorhanden = tuple(eintraege)
    kennungen = {eintrag.kennung for eintrag in vorhanden}
    referenziert = {eintrag.unten for eintrag in vorhanden if eintrag.unten in kennungen}
    koepfe = sorted(kennungen - referenziert)
    if len(koepfe) != 1:
        raise ZuteilerFehler(
            f"{len(koepfe)} Koepfe statt einem - 'head' waere mehrdeutig, und hier wird "
            "angehalten statt geraten."
        )
    return koepfe[0]


def migrationen_auf_main(wurzel: Path) -> tuple[Migration, ...]:
    """Die Migrationen, die auf `origin/main` liegen - alles andere ist eigene Arbeit.

    Laesst sich diese Menge nicht bestimmen, wird angehalten statt umgehaengt: Aendert sich
    Kennung oder `down_revision` einer bereits ausgefuehrten Revision, findet
    `alembic upgrade head` beim Containerstart den Wert aus `alembic_version` nicht mehr.
    """
    rohdaten = git_ausgabe(
        [
            "ls-tree",
            "-r",
            "-z",
            "--name-only",
            "--end-of-options",
            ORIGIN_MAIN,
            "--",
            VERSIONSVERZEICHNIS,
        ],
        cwd=wurzel,
    )
    pfade = sorted(
        pfad for pfad in nul_felder(rohdaten) if pfad.rpartition("/")[0] == VERSIONSVERZEICHNIS
    )
    if not pfade:
        raise ZuteilerFehler(
            f"Keine Migration in {VERSIONSVERZEICHNIS} auf origin/main. Das ist 'nicht "
            "gemessen', nicht 'nichts umzuhaengen' - hier wird angehalten."
        )
    # Gelesen wird der Stand auf origin/main selbst, nicht die lokal daneben liegende Datei:
    # Eine auf main neu entstandene Migration liegt im eigenen Arbeitsbaum gar nicht, und ein
    # stilles Ueberspringen machte genau den verschobenen Kopf unsichtbar.
    return tuple(
        migration_aus_text(
            git_ausgabe(["show", "--end-of-options", f"{ORIGIN_MAIN}:{pfad}"], cwd=wurzel).decode(
                "utf-8"
            ),
            Path(pfad),
        )
        for pfad in pfade
    )


@dataclass(frozen=True)
class Kettenlage:
    """Die Lage, in der das Umhaengen entschieden wird - bewusst ohne aufgeloeste Kette.

    Genau dann, wenn umzuhaengen ist, liegt die Kette gegabelt vor (die eigene Migration und die
    von `main` haengen an derselben Revision). Eine Lage, die sich nur ueber eine aufloesbare
    Kette bestimmen liesse, waere in ihrem einzigen Anwendungsfall nicht bestimmbar.
    """

    alle: tuple[Migration, ...]
    uebernommen: frozenset[str]
    kopf_auf_main: str
    unterste_eigene: Migration | None

    @property
    def haengt_am_alten_kopf(self) -> bool:
        return self.unterste_eigene is not None and self.unterste_eigene.unten != self.kopf_auf_main


def alle_migrationen(versionen: Path) -> tuple[Migration, ...]:
    return tuple(migration_aus_datei(pfad) for pfad in sorted(versionen.glob("*.py")))


def kettenlage(wurzel: Path) -> Kettenlage:
    alle = alle_migrationen(eigene_wurzel(wurzel) / VERSIONSVERZEICHNIS)
    auf_main = migrationen_auf_main(wurzel)
    uebernommen = frozenset(eintrag.kennung for eintrag in auf_main)

    eigene = [eintrag for eintrag in alle if eintrag.kennung not in uebernommen]
    eigene_kennungen = {eintrag.kennung for eintrag in eigene}
    unterste = [eintrag for eintrag in eigene if eintrag.unten not in eigene_kennungen]
    if len(unterste) > 1:
        raise ZuteilerFehler(
            f"{len(unterste)} eigene Migrationen haengen unmittelbar an uebernommener Arbeit - "
            "welche die unterste ist, wird hier nicht geraten."
        )
    return Kettenlage(
        alle=alle,
        uebernommen=uebernommen,
        kopf_auf_main=kopf_der_menge(auf_main),
        unterste_eigene=unterste[0] if unterste else None,
    )


def haenge_um(wurzel: Path) -> str | None:
    """Haengt die unterste eigene Migration hinter den Kopf von `origin/main`.

    Angefasst wird ausschliesslich eine Revision, die von `origin/main` nicht erreichbar ist -
    eine bereits uebernommene nie. Mehrere eigene Migrationen behalten ihre interne Reihenfolge,
    weil nur die unterste umgehaengt wird.
    """
    lage = kettenlage(wurzel)
    if lage.unterste_eigene is None or not lage.haengt_am_alten_kopf:
        return None
    ziel = lage.unterste_eigene
    if ziel.kennung in lage.uebernommen:
        raise ZuteilerFehler(
            "Die umzuhaengende Revision liegt bereits auf origin/main - hier wird angehalten "
            "statt geschrieben."
        )
    neuer_kopf = gepruefte_kennung(lage.kopf_auf_main)
    zeilen = ziel.pfad.read_text(encoding="utf-8").splitlines(keepends=True)
    geschrieben = False
    for stelle, zeile in enumerate(zeilen):
        if zeile.startswith(_VORGAENGERZEILEN):
            schluessel, _, _ = zeile.partition("=")
            zeilen[stelle] = f'{schluessel.rstrip()} = "{neuer_kopf}"\n'
            geschrieben = True
            break
    if not geschrieben:
        raise ZuteilerFehler(f"Keine down_revision-Zeile in {ziel.pfad.name} - nichts umgehaengt.")
    ziel.pfad.write_text("".join(zeilen), encoding="utf-8")
    return f"{ziel.kennung} hinter {neuer_kopf} gehaengt"


# --- Die Unterbefehle --------------------------------------------------------------------------

_HILFE = (
    "Aufruf: nummern.py <vorschlag <decisions|architecture>|migration <slug>|pruefen|kette"
    "|umhaengen>"
)


_KOPF_VERSCHOBEN = (
    "Der Kopf von origin/main hat sich verschoben - 'umhaengen' haengt die unterste eigene "
    "Migration dahinter, ohne eine bereits uebernommene anzufassen."
)


def _meldung(text: str) -> None:
    print(text, file=sys.stderr)


def _dublettenzeilen(wurzel: Path, verzeichnis: str) -> list[str]:
    zeilen = []
    for nummer, namen in sorted(eigene_dokumente(wurzel, verzeichnis).items()):
        if len(namen) > 1:
            zeilen.append(
                f"{verzeichnis}: Die Nummer {nummer:04d} traegt im eigenen Arbeitsbaum "
                f"{len(namen)} Dateien: {', '.join(namen)}"
            )
    return zeilen


def befehl_vorschlag(wurzel: Path, raum: str) -> int:
    if raum == ABGELEHNTER_RAUM:
        _meldung(
            "Die Nummer einer Feature-Spec kommt vom GitHub-Issue und faellt nicht unter die "
            "Rangregel. Hier wird bewusst keine vergeben."
        )
        return EXIT_VORBEDINGUNG
    if raum not in NUMMERNRAEUME:
        _meldung(f"Unbekannter Nummernraum: {raum!r}. {_HILFE}")
        return EXIT_VORBEDINGUNG

    sicht = erhebe_sicht(wurzel, raum)
    nummer = zugeteilte_nummer(sicht.basis, sicht.gefuehrt, sicht.eigener_branch)
    print(f"{nummer:04d}")

    befunde = befundzeilen(sicht.basis, sicht.gefuehrt, sicht.eigener_branch)
    if not befunde:
        return EXIT_OK
    for zeile in befunde:
        _meldung(zeile)
    _meldung(
        "Die Zuteilung oben beruecksichtigt diese Kontrahenten bereits; jede Seite rechnet "
        "dasselbe, ohne Abstimmung. Die Datei jetzt anlegen - erst dadurch wird die Nummer "
        "fuer die Nachbarn sichtbar."
    )
    return EXIT_KONTENTION


def befehl_migration(wurzel: Path, slug: str) -> int:
    geprueft = gepruefter_slug(slug)
    branch = eigener_branch(wurzel)
    kennung = gepruefte_kennung(revisionskennung(branch, geprueft))
    lage = kettenlage(wurzel)
    print(f"revision: {kennung}")
    print(f"down_revision: {kopf_der_menge(lage.alle)}")
    if lage.haengt_am_alten_kopf:
        _meldung(_KOPF_VERSCHOBEN)
        return EXIT_KONTENTION
    return EXIT_OK


def befehl_kette(wurzel: Path) -> int:
    for eintrag in aufgeloeste_kette(eigene_wurzel(wurzel) / VERSIONSVERZEICHNIS):
        print(eintrag.kennung)
    return EXIT_OK


def befehl_umhaengen(wurzel: Path) -> int:
    bericht = haenge_um(wurzel)
    if bericht is None:
        print("Kette unveraendert: die unterste eigene Migration haengt am Kopf von origin/main")
        return EXIT_OK
    print(bericht)
    return EXIT_KONTENTION


def _kettenbefunde(wurzel: Path) -> list[str]:
    """Der Kettenteil von `pruefen` - still, wenn es hier gar keine Migrationen gibt."""
    if not (eigene_wurzel(wurzel) / VERSIONSVERZEICHNIS).is_dir():
        return []
    lage = kettenlage(wurzel)
    if not lage.haengt_am_alten_kopf or lage.unterste_eigene is None:
        return []
    return [
        f"{VERSIONSVERZEICHNIS}: {lage.unterste_eigene.kennung} haengt an "
        f"{lage.unterste_eigene.unten}, der Kopf von origin/main ist aber {lage.kopf_auf_main}. "
        f"{_KOPF_VERSCHOBEN}"
    ]


def befehl_pruefen(wurzel: Path) -> int:
    dubletten: list[str] = []
    kontention: list[str] = _kettenbefunde(wurzel)
    for raum, verzeichnis in NUMMERNRAEUME.items():
        sicht = erhebe_sicht(wurzel, raum)
        dubletten += _dublettenzeilen(wurzel, verzeichnis)
        kontention += befundzeilen(sicht.basis, sicht.gefuehrt, sicht.eigener_branch)
        baeume = (
            f"{sicht.arbeitsbaeume} Arbeitsbaum"
            if sicht.arbeitsbaeume == 1
            else f"{sicht.arbeitsbaeume} Arbeitsbaeume"
        )
        print(
            f"{verzeichnis}: {sicht.gelesen} Dateinamen gelesen, Basis {sicht.basis:04d}, "
            f"{baeume}, {sicht.fremde_branches} gepushte Branches"
        )
    for zeile in dubletten + kontention:
        print(zeile)
    if dubletten:
        return EXIT_DUBLETTE
    return EXIT_KONTENTION if kontention else EXIT_OK


def main(argv: Sequence[str]) -> int:
    if not argv:
        _meldung(_HILFE)
        return EXIT_VORBEDINGUNG
    befehl, rest = argv[0], argv[1:]
    try:
        if befehl == "vorschlag":
            if len(rest) != 1:
                _meldung(_HILFE)
                return EXIT_VORBEDINGUNG
            return befehl_vorschlag(Path.cwd(), rest[0])
        if befehl == "migration":
            if len(rest) != 1:
                _meldung(_HILFE)
                return EXIT_VORBEDINGUNG
            return befehl_migration(Path.cwd(), rest[0])
        if befehl == "pruefen" and not rest:
            return befehl_pruefen(Path.cwd())
        if befehl == "kette" and not rest:
            return befehl_kette(Path.cwd())
        if befehl == "umhaengen" and not rest:
            return befehl_umhaengen(Path.cwd())
    except ZuteilerFehler as grund:
        _meldung(str(grund))
        return EXIT_VORBEDINGUNG
    _meldung(f"Unbekannter Aufruf. {_HILFE}")
    return EXIT_VORBEDINGUNG


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
