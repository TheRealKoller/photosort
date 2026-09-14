"""Prueft den Zuteiler `scripts/nummern.py` - Rechnung, Leser, Unterbefehle, Migrationskette.

Der Schwerpunkt liegt auf der **reinen Rechnung**: Sie laeuft ohne git, ohne Uhr und ohne Zufall
und bleibt damit gueltig, wenn die beteiligten Branches laengst geloescht sind. Der Leser wird
daneben gegen ein Wegwerf-Repositorium mit echten Arbeitsbaeumen gemessen.

**Zugesichert ist Injektivitaet als Eigenschaft, nicht als Fallliste.** Ueber einer
Kontrahentenmenge mit festen Zaehlstaenden ist die Abbildung Branchname -> Nummer injektiv; der
Test rechnet sie ueber **allen** Permutationen der Eingabereihenfolge nach. Eine Fallliste bliebe
gruen, sobald die Eingabereihenfolge das Ergebnis kippt - genau der Fehler, der zwei Seiten
verschiedene Nummern derselben Rechnung liefern liesse.

**Die beiden Gegenproben an den echten Vorfaellen messen im selben Lauf auch das Versagen der
abgeloesten Regel.** Ohne diese zweite Haelfte waeren sie Tautologien: Dass eine Rechnung zwei
verschiedene Zahlen liefert, sagt fuer sich genommen nicht, dass die Regel davor es nicht tat.
`alte_regel_naechste_freie` unten ist deshalb bewusst nachgebaut - ausschliesslich als
Messgegenstand, nie als Handlungsanweisung.

Kein Netzwerk. Jeder Unterprozess traegt eine Zeitgrenze; ein haengender Aufruf ist in CI ein
Stundenjob statt eines roten Tests.
"""

from __future__ import annotations

import itertools
import os
import re
import subprocess
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import pytest

ZEITGRENZE_SEKUNDEN = 120

# --- Nachbau der abgeloesten Regel, ausschliesslich als Messgegenstand -------------------------


def alte_regel_naechste_freie(basis: int, sichtbare_nummern: Collection[int]) -> int:
    """Die abgeloeste Vergabe: die naechste freie Nummer ueber dem, was die Seite sah.

    Sie kennt den Branchnamen nicht - dieselbe sichtbare Belegtmenge liefert jeder Seite
    dasselbe Ergebnis. Genau das ist ihr Versagen, und genau das messen die beiden Gegenproben
    an den echten Vorfaellen weiter unten.
    """
    kandidat = basis
    while kandidat in sichtbare_nummern:
        kandidat += 1
    return kandidat


def _nummern(
    modul: ModuleType, basis: int, gefuehrt: Mapping[str, Sequence[int]], branches: Sequence[str]
) -> list[int]:
    return [modul.zugeteilte_nummer(basis, gefuehrt, branch) for branch in branches]


# --- Basis ------------------------------------------------------------------------------------


def test_die_basis_ist_die_hoechste_nummer_plus_eins(nummern_module: ModuleType) -> None:
    assert nummern_module.basis_aus_nummern({1, 17, 105}, quelle="specs/decisions") == 106


def test_eine_leere_nummernmenge_scheitert_laut_statt_still(nummern_module: ModuleType) -> None:
    """Der stille Fall waere hier der schlimmste: Basis 1, ausgegeben wuerde `0001`."""
    with pytest.raises(nummern_module.ZuteilerFehler, match=r"specs/decisions"):
        nummern_module.basis_aus_nummern(set(), quelle="specs/decisions")


def test_dateinamen_ohne_nummernmuster_werden_gezaehlt_nicht_zitiert(
    nummern_module: ModuleType,
) -> None:
    """Ausgabehygiene: ein Dateiname geht nie roh in eine Meldung."""
    ablesung = nummern_module.nummern_aus_namen(
        ["0105-basis.md", "README.md", "0106-mit leerzeichen.md", "notizen.txt"]
    )

    assert ablesung.nummern == frozenset({105, 106})
    assert ablesung.gelesen == 4
    assert ablesung.verworfen == 2


# --- Kontrahenten und Rang --------------------------------------------------------------------


def test_ohne_kontrahenten_bleibt_die_basis_unveraendert(nummern_module: ModuleType) -> None:
    assert nummern_module.zugeteilte_nummer(106, {}, "feature/0485-nummern") == 106


def test_ein_branch_mit_nummer_unter_der_basis_ist_kein_kontrahent(
    nummern_module: ModuleType,
) -> None:
    """Sonst hielte ein laengst uebernommenes Dokument seine Nummer ein zweites Mal besetzt."""
    gefuehrt = {"feature/aelter": [101, 105], "feature/zzz-eigen": []}

    assert nummern_module.kontrahenten(106, gefuehrt, "feature/zzz-eigen") == (
        nummern_module.Kontrahent("feature/zzz-eigen", ()),
    )
    assert nummern_module.zugeteilte_nummer(106, gefuehrt, "feature/zzz-eigen") == 106


def test_ein_kontrahent_belegt_so_viele_nummern_wie_er_fuehrt(nummern_module: ModuleType) -> None:
    gefuehrt = {"feature/a-vorn": [106, 107], "feature/z-hinten": []}

    assert nummern_module.zugeteilte_nummer(106, gefuehrt, "feature/z-hinten") == 108


def test_nur_nummern_ab_der_basis_zaehlen_beim_belegen_mit(nummern_module: ModuleType) -> None:
    """Ein Kontrahent, der zusaetzlich eine uebernommene Nummer fuehrt, belegt sie nicht doppelt:
    sie steckt bereits in der Basis."""
    gefuehrt = {"feature/a-vorn": [104, 106], "feature/z-hinten": []}

    assert nummern_module.zugeteilte_nummer(106, gefuehrt, "feature/z-hinten") == 107


def test_der_eigene_branch_ist_immer_kontrahent_auch_ohne_gefuehrte_nummer(
    nummern_module: ModuleType,
) -> None:
    namen = [k.branch for k in nummern_module.kontrahenten(106, {}, "feature/ohne-datei")]

    assert namen == ["feature/ohne-datei"]


def test_dieselbe_nummer_zweimal_gefuehrt_zaehlt_einmal(nummern_module: ModuleType) -> None:
    """Mitten im Abgleich mit `main` listet `git ls-files --cached` denselben Pfad je Stage."""
    gefuehrt = {"feature/a-vorn": [106, 106, 107], "feature/z-hinten": []}

    assert nummern_module.zugeteilte_nummer(106, gefuehrt, "feature/z-hinten") == 108


# --- Ordnung ----------------------------------------------------------------------------------


def test_die_ordnung_ist_byteweise_nicht_locale_abhaengig(nummern_module: ModuleType) -> None:
    """In einer Locale mit Sortierregeln stuende `a-eins` vor `B-zwei`; byteweise nicht.

    Kippt die Ordnung mit der Locale der jeweiligen Sitzung, rechnen zwei Seiten verschieden -
    und die ganze Zusicherung ist still falsch.
    """
    gefuehrt = {"feature/B-zwei": [106], "feature/a-eins": [107]}

    namen = [k.branch for k in nummern_module.kontrahenten(106, gefuehrt, "feature/B-zwei")]

    assert namen == ["feature/B-zwei", "feature/a-eins"]
    assert nummern_module.zugeteilte_nummer(106, gefuehrt, "feature/B-zwei") == 106
    assert nummern_module.zugeteilte_nummer(106, gefuehrt, "feature/a-eins") == 107


@pytest.mark.parametrize(
    "namen",
    [
        ("feature/0485-a", "feature/0485-b"),
        ("feature/0485", "feature/0485-nachsatz"),
        ("feature-strich", "feature/schraegstrich"),
        ("feature_unterstrich", "feature/schraegstrich"),
    ],
)
def test_jede_paarung_von_trennzeichen_ordnet_byteweise(
    nummern_module: ModuleType, namen: tuple[str, str]
) -> None:
    gefuehrt = {name: [106] for name in namen}
    erwartet = sorted(namen, key=lambda name: name.encode("utf-8"))

    gemessen = [k.branch for k in nummern_module.kontrahenten(106, gefuehrt, namen[0])]

    assert gemessen == erwartet


# --- AK 3 (a): Injektivitaet als Eigenschaft ---------------------------------------------------

_FESTE_ZAEHLSTAENDE: Mapping[str, Sequence[int]] = {
    "feature/0469-sehenswuerdigkeiten": [106, 107],
    "feature/0474-ausschuss": [108],
    "feature/0485-nummernvergabe": [109],
    "chore/design-runde": [110, 111, 112],
}


def test_die_zuteilung_ist_ueber_allen_permutationen_injektiv(nummern_module: ModuleType) -> None:
    """AK 3 (a). Eine Fallliste bliebe gruen, sobald die Eingabereihenfolge das Ergebnis kippt."""
    branches = sorted(_FESTE_ZAEHLSTAENDE)
    erwartet = _nummern(nummern_module, 106, dict(_FESTE_ZAEHLSTAENDE), branches)

    assert len(set(erwartet)) == len(branches), f"Dublette in der Zuteilung: {erwartet}"

    for reihenfolge in itertools.permutations(branches):
        vertauscht = {name: _FESTE_ZAEHLSTAENDE[name] for name in reihenfolge}

        assert _nummern(nummern_module, 106, vertauscht, branches) == erwartet


def test_jede_seite_erhaelt_bei_wiederholung_dasselbe(nummern_module: ModuleType) -> None:
    """AK 4, zweite Haelfte: der Zuteiler ist eine Funktion, kein Zaehler mit Gedaechtnis."""
    for branch in _FESTE_ZAEHLSTAENDE:
        erster = nummern_module.zugeteilte_nummer(106, dict(_FESTE_ZAEHLSTAENDE), branch)
        zweiter = nummern_module.zugeteilte_nummer(106, dict(_FESTE_ZAEHLSTAENDE), branch)

        assert erster == zweiter


def test_ohne_jeden_gemergten_beteiligten_bleibt_das_ergebnis_dublettenfrei(
    nummern_module: ModuleType,
) -> None:
    """AK 4: Kein Beteiligter liegt auf `origin/main` - die Basis kennt keinen von ihnen."""
    aus_jeder_sicht = _nummern(
        nummern_module, 106, dict(_FESTE_ZAEHLSTAENDE), sorted(_FESTE_ZAEHLSTAENDE)
    )

    # chore/design-runde (3 Nummern), 0469 (2), 0474 (1), 0485 (1) - byteweise in dieser Folge.
    assert aus_jeder_sicht == [106, 109, 111, 112]
    assert len(set(aus_jeder_sicht)) == len(aus_jeder_sicht)


# --- AK 3 (c): das Fenster aus ADR 0108 Punkt 4 ------------------------------------------------


def test_im_fenster_rechnen_beide_dasselbe_und_der_naechste_lauf_loest_es_auf(
    nummern_module: ModuleType,
) -> None:
    """Zugesichertes Verhalten, keine Verletzung von AK 3.

    Solange eine Seite ihre Datei noch nicht angelegt hat, sieht die andere sie nicht und beide
    errechnen dieselbe Zahl. Sobald beide Dateien liegen, sehen beide dieselbe
    Kontrahentenmenge, und die rangniedrigere Seite behaelt.
    """
    im_fenster = {"feature/a-vorn": [106], "feature/b-mitte": [], "feature/c-hinten": []}

    assert nummern_module.zugeteilte_nummer(106, im_fenster, "feature/b-mitte") == 107
    assert nummern_module.zugeteilte_nummer(106, im_fenster, "feature/c-hinten") == 107

    beide_geschrieben = {
        "feature/a-vorn": [106],
        "feature/b-mitte": [107],
        "feature/c-hinten": [107],
    }

    assert nummern_module.zugeteilte_nummer(106, beide_geschrieben, "feature/b-mitte") == 107
    assert nummern_module.zugeteilte_nummer(106, beide_geschrieben, "feature/c-hinten") == 108


# --- AK 2: Befundzeilen ------------------------------------------------------------------------


def test_ohne_fremden_kontrahenten_gibt_es_keine_befundzeile(nummern_module: ModuleType) -> None:
    assert nummern_module.befundzeilen(106, {"feature/allein": []}, "feature/allein") == []


def test_je_kontrahierendem_branch_eine_zeile_mit_name_und_nummer(
    nummern_module: ModuleType,
) -> None:
    zeilen = nummern_module.befundzeilen(
        106, dict(_FESTE_ZAEHLSTAENDE), "feature/0485-nummernvergabe"
    )

    assert len(zeilen) == 3
    assert any("feature/0469-sehenswuerdigkeiten" in zeile for zeile in zeilen)
    assert any("0106" in zeile and "0107" in zeile for zeile in zeilen)
    assert all("feature/0485-nummernvergabe" not in zeile for zeile in zeilen)


# --- AK 9, Vorfall 1: die doppelt vergebene Dokumentnummer -------------------------------------

BASIS_VORFALL_1 = 106
HALTENDER_BRANCH = "feature/0469-verlaessliche-sehenswuerdigkeitsnamen"
EIGENER_BRANCH = "feature/0485-nummernvergabe-bei-parallelarbeit"

# Der veroeffentlichte Stand am 2026-09-14: `origin/main` endete bei 0105. Mehr sah die
# abgeloeste Regel nicht - die beiden 0106/0107 des Nachbarn lagen ungepusht in seinem
# Arbeitsbaum.
VEROEFFENTLICHT_VORFALL_1 = frozenset({101, 102, 103, 104, 105})


def test_gegenprobe_vorfall_1_die_rangregel_trennt_beide_seiten(
    nummern_module: ModuleType,
) -> None:
    gefuehrt = {HALTENDER_BRANCH: [106, 107], EIGENER_BRANCH: []}

    haltend = nummern_module.zugeteilte_nummer(BASIS_VORFALL_1, gefuehrt, HALTENDER_BRANCH)
    eigen = nummern_module.zugeteilte_nummer(BASIS_VORFALL_1, gefuehrt, EIGENER_BRANCH)

    assert HALTENDER_BRANCH.encode("utf-8") < EIGENER_BRANCH.encode("utf-8")
    assert (haltend, eigen) == (106, 108)


def test_gegenprobe_vorfall_1_die_abgeloeste_regel_gibt_beiden_dieselbe_nummer(
    nummern_module: ModuleType,
) -> None:
    """Die zweite Haelfte der Gegenprobe - ohne sie waere die erste eine Tautologie."""
    haltend_alt = alte_regel_naechste_freie(BASIS_VORFALL_1, VEROEFFENTLICHT_VORFALL_1)
    eigen_alt = alte_regel_naechste_freie(BASIS_VORFALL_1, VEROEFFENTLICHT_VORFALL_1)

    assert haltend_alt == eigen_alt == 106

    gefuehrt = {HALTENDER_BRANCH: [106, 107], EIGENER_BRANCH: []}
    neu = {
        nummern_module.zugeteilte_nummer(BASIS_VORFALL_1, gefuehrt, HALTENDER_BRANCH),
        nummern_module.zugeteilte_nummer(BASIS_VORFALL_1, gefuehrt, EIGENER_BRANCH),
    }

    assert len({haltend_alt, eigen_alt}) == 1, "die abgeloeste Regel kollidiert - so entstand 0485"
    assert len(neu) == 2, "die Rangregel muss genau hier trennen"


# --- AK 6: die Revisionskennung ----------------------------------------------------------------

# Fester Vektor, einmal ausgerechnet und hier festgeschrieben: Rechnete der Test den Hash selbst
# nach, pruefte er sich selbst und bliebe gruen, wenn Trenner oder Laenge kippen.
VEKTOR_BRANCH = "feature/0485-nummernvergabe-bei-parallelarbeit"
VEKTOR_SLUG = "nummernvergabe"
VEKTOR_KENNUNG = "411e5778672b"


def test_die_kennung_trifft_den_festen_vektor(nummern_module: ModuleType) -> None:
    assert nummern_module.revisionskennung(VEKTOR_BRANCH, VEKTOR_SLUG) == VEKTOR_KENNUNG


def test_dieselbe_eingabe_liefert_dieselbe_kennung(nummern_module: ModuleType) -> None:
    erste = nummern_module.revisionskennung(VEKTOR_BRANCH, VEKTOR_SLUG)
    zweite = nummern_module.revisionskennung(VEKTOR_BRANCH, VEKTOR_SLUG)

    assert erste == zweite


def test_verschiedener_branch_liefert_bei_identischem_slug_eine_andere_kennung(
    nummern_module: ModuleType,
) -> None:
    eine = nummern_module.revisionskennung("feature/a", "gleich")
    andere = nummern_module.revisionskennung("feature/b", "gleich")

    assert eine != andere


def test_der_nul_trenner_haelt_zwei_eingabepaare_auseinander(nummern_module: ModuleType) -> None:
    """Mutationsprobe auf den Trenner: ohne ihn waeren `("ab","c")` und `("a","bc")` dasselbe."""
    assert nummern_module.revisionskennung("ab", "c") != nummern_module.revisionskennung("a", "bc")


def test_die_kennung_ist_genau_zwoelf_kleinbuchstaben_hex(nummern_module: ModuleType) -> None:
    kennung = nummern_module.revisionskennung(VEKTOR_BRANCH, VEKTOR_SLUG)

    assert nummern_module.KENNUNGSFORM.fullmatch(kennung)
    assert len(kennung) == 12


def test_eine_kennung_falscher_form_wird_abgewiesen_bevor_sie_einen_dateinamen_bildet(
    nummern_module: ModuleType,
) -> None:
    """`re.fullmatch`, nie `.match`: `$` passt auch unmittelbar vor einem Zeilenumbruch."""
    for unzulaessig in ["411E5778672B", "411e5778672", "411e5778672bb", "411e5778672b\n", ""]:
        with pytest.raises(nummern_module.ZuteilerFehler):
            nummern_module.gepruefte_kennung(unzulaessig)


@pytest.mark.parametrize(
    "slug", ["ortsnamen", "duplikate-vergleichen", "a", "teil2", "0485-nummern"]
)
def test_ein_zulaessiger_slug_geht_durch(nummern_module: ModuleType, slug: str) -> None:
    assert nummern_module.gepruefter_slug(slug) == slug


@pytest.mark.parametrize(
    "slug",
    [
        "",
        "-fuehrender-strich",
        "endstrich-",
        "Gross",
        "mit leerzeichen",
        "mit_unterstrich",
        "pfad/trenner",
        "..",
        "../../etc/passwd",
        "doppel--strich",
        "umlaut-ae-ä",
        "slug\n",
        "x" * 61,
    ],
)
def test_ein_unzulaessiger_slug_wird_abgewiesen(nummern_module: ModuleType, slug: str) -> None:
    """Der Slug ist der einzige frei gewaehlte Wert, der in einen Dateinamen laeuft."""
    with pytest.raises(nummern_module.ZuteilerFehler):
        nummern_module.gepruefter_slug(slug)


# --- AK 9, Vorfall 2: die doppelt vergebene Revisionskennung -----------------------------------

VORFALL_2_BRANCH_A = "feature/0374-duplikate-vergleichen"
VORFALL_2_BRANCH_B = "feature/0434-ortsnamen-teil2"

# Die von Hand gewaehlte Hex-Folge, die beide Seiten am 2026-09-14 vergaben. Sie ist hier die
# gemessene zweite Haelfte der Gegenprobe: **ein** Wert fuer zwei Branches.
VORFALL_2_HANDGEWAEHLT = "d7e8f9a0b1c2"


@pytest.mark.parametrize("slug", ["duplikate", "gleicher-slug"])
def test_gegenprobe_vorfall_2_die_ableitung_trennt_beide_branches(
    nummern_module: ModuleType, slug: str
) -> None:
    a = nummern_module.revisionskennung(VORFALL_2_BRANCH_A, slug)
    b = nummern_module.revisionskennung(VORFALL_2_BRANCH_B, slug)

    assert a != b, "bei identischem Slug traegt allein der Branchname die Unterscheidung"
    assert a == nummern_module.revisionskennung(VORFALL_2_BRANCH_A, slug)
    assert b == nummern_module.revisionskennung(VORFALL_2_BRANCH_B, slug)
    assert all(nummern_module.KENNUNGSFORM.fullmatch(wert) for wert in (a, b))


def test_gegenprobe_vorfall_2_die_handgewaehlte_folge_war_fuer_beide_dieselbe(
    nummern_module: ModuleType,
) -> None:
    """Die zweite Haelfte der Gegenprobe - ohne sie waere die erste eine Tautologie."""
    handgewaehlt = {
        VORFALL_2_BRANCH_A: VORFALL_2_HANDGEWAEHLT,
        VORFALL_2_BRANCH_B: VORFALL_2_HANDGEWAEHLT,
    }
    abgeleitet = {
        branch: nummern_module.revisionskennung(branch, "duplikate") for branch in handgewaehlt
    }

    assert len(set(handgewaehlt.values())) == 1, "so sah der Vorfall aus: eine Folge, zwei Branches"
    assert len(set(abgeleitet.values())) == 2
    assert VORFALL_2_HANDGEWAEHLT not in set(abgeleitet.values())


# --- Das Wegwerf-Repositorium ------------------------------------------------------------------


@dataclass(frozen=True)
class Wegwerf:
    """Ein bares `origin` mit `main`, ein Haupt-Checkout und vier Nachbarn mit je eigenem
    Sichtbarkeitsgrad."""

    wurzel: Path
    origin: Path
    haupt: Path
    drin: Path
    nachbar_a: Path
    nachbar_b: Path
    pflege: Path


def _git(verzeichnis: Path, *args: str) -> subprocess.CompletedProcess[str]:
    ergebnis = subprocess.run(
        ["git", *args],
        cwd=verzeichnis,
        capture_output=True,
        text=True,
        timeout=ZEITGRENZE_SEKUNDEN,
        check=False,
    )
    assert ergebnis.returncode == 0, (
        f"Fixture-Aufbau gescheitert: git {' '.join(args)} in {verzeichnis} "
        f"-> {ergebnis.returncode}\n{ergebnis.stderr}"
    )
    return ergebnis


def _dokument(verzeichnis: Path, name: str) -> None:
    verzeichnis.mkdir(parents=True, exist_ok=True)
    (verzeichnis / name).write_text(f"# {name}\n", encoding="utf-8")


@pytest.fixture
def wegwerf(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Wegwerf:
    """Vier Nachbarn, jeder nur ueber genau die Quelle sichtbar, die er belegt.

    ```
    tmp_path/
      origin.git/                    bar, main, fuehrt specs/decisions/0101-0105  -> Basis 0106
      haupt/                         Klon, eigener Branch z/eigen, fuehrt 0110
      haupt/.claude/worktrees/drin/  Arbeitsbaum INNERHALB des Haupt-Checkouts, d/drin -> 0109
      nachbar-a/                     Arbeitsbaum a/committet -> 0106 committet und auf Platte
      nachbar-b/                     Arbeitsbaum b/angelegt  -> 0107 nur angelegt, kein add
      (ohne Arbeitsbaum)             gepushter Branch c/gepusht -> 0108, nur ueber ls-tree
    ```

    **Mutationsprobe, durchgefuehrt am 2026-09-14.** Je einmal wurde einer der beiden Lesewege
    in `erhebe_sicht` entfernt und der Lauf wiederholt:

    * ohne den `ls-tree`-Weg faellt `test_ein_gepushter_branch_ohne_arbeitsbaum_wird_zugerechnet`
      (0108 wird niemandem zugerechnet), waehrend der 0107-Fall gruen bleibt;
    * ohne den Verzeichnisweg faellt `test_eine_nur_angelegte_datei_wird_ihrem_branch_zugerechnet`
      (0107 fehlt ganz), waehrend der 0108-Fall gruen bleibt.

    Jedes Mal genau einer der beiden Faelle - ohne diese Probe belegte ein gruener Lauf nur, dass
    irgendein Weg getroffen hat.

    Saemtliche `GIT_*` der aufrufenden Umgebung werden entfernt und die Decke auf `tmp_path`
    gesetzt: Sonst richtete ein stehen gebliebenes `GIT_DIR` den Leser auf das echte
    PhotoSort-Repositorium, und der Test waere aus dem falschen Grund gruen. Jeder Unterprozess
    traegt eine Zeitgrenze.
    """
    for name in [n for n in os.environ if n.startswith("GIT_")]:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", os.devnull)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    monkeypatch.setenv("GIT_TERMINAL_PROMPT", "0")
    monkeypatch.setenv("GIT_AUTHOR_NAME", "PhotoSort Test")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "test@example.invalid")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "PhotoSort Test")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "test@example.invalid")

    ort = Wegwerf(
        wurzel=tmp_path,
        origin=tmp_path / "origin.git",
        haupt=tmp_path / "haupt",
        drin=tmp_path / "haupt" / ".claude" / "worktrees" / "drin",
        nachbar_a=tmp_path / "nachbar-a",
        nachbar_b=tmp_path / "nachbar-b",
        pflege=tmp_path / "pflege",
    )

    _git(tmp_path, "init", "--quiet", "--bare", "-b", "main", str(ort.origin))
    _git(tmp_path, "init", "--quiet", "-b", "main", str(ort.haupt))

    entscheidungen = ort.haupt / "specs" / "decisions"
    for name in ["0101-eins.md", "0102-zwei.md", "0105-basis.md"]:
        _dokument(entscheidungen, name)
    # Zwei Namen, an denen sich die Aufzaehlungsform entscheidet: Ohne `-z` verfremdet git den
    # Umlaut zu einer zitierten Folge, das Nummernmuster greift nicht mehr, und die Nummer faellt
    # still aus der Basis. Der Umlaut steht hier als echtes Zeichen - er IST der Pruefgegenstand.
    _dokument(entscheidungen, "0103-mit leerzeichen.md")
    _dokument(entscheidungen, "0104-gateführte-pipeline.md")
    _dokument(entscheidungen, "liesmich.md")
    _dokument(entscheidungen / "unterverzeichnis", "0150-tief.md")
    _dokument(ort.haupt / "specs" / "architecture", "0004-design.md")
    _git(ort.haupt, "add", "-A")
    _git(ort.haupt, "commit", "--quiet", "-m", "chore: Ausgangsstand")
    _git(ort.haupt, "remote", "add", "origin", str(ort.origin))
    _git(ort.haupt, "push", "--quiet", "origin", "main")

    _git(tmp_path, "clone", "--quiet", str(ort.origin), str(ort.pflege))
    _git(ort.pflege, "checkout", "--quiet", "-b", "c/gepusht")
    _dokument(ort.pflege / "specs" / "decisions", "0108-gepusht.md")
    _git(ort.pflege, "add", "-A")
    _git(ort.pflege, "commit", "--quiet", "-m", "docs: 0108")
    _git(ort.pflege, "push", "--quiet", "origin", "c/gepusht")

    _git(ort.haupt, "checkout", "--quiet", "-b", "z/eigen")
    _git(ort.haupt, "fetch", "--quiet", "origin")

    _git(ort.haupt, "worktree", "add", "--quiet", "-b", "a/committet", str(ort.nachbar_a), "main")
    _dokument(ort.nachbar_a / "specs" / "decisions", "0106-nachbar-a.md")
    _git(ort.nachbar_a, "add", "-A")
    _git(ort.nachbar_a, "commit", "--quiet", "-m", "docs: 0106")

    _git(ort.haupt, "worktree", "add", "--quiet", "-b", "b/angelegt", str(ort.nachbar_b), "main")
    _dokument(ort.nachbar_b / "specs" / "decisions", "0107-nachbar-b.md")

    _git(ort.haupt, "worktree", "add", "--quiet", "-b", "d/drin", str(ort.drin), "main")
    _dokument(ort.drin / "specs" / "decisions", "0109-drin.md")
    _git(ort.drin, "add", "-A")
    _git(ort.drin, "commit", "--quiet", "-m", "docs: 0109")

    _dokument(entscheidungen, "0110-eigen.md")
    return ort


# --- Die Basis kommt ausschliesslich von origin/main -------------------------------------------


def test_die_basis_kommt_aus_origin_main_nicht_aus_dem_eigenen_blick(
    nummern_module: ModuleType, wegwerf: Wegwerf
) -> None:
    """Haenge die Basis am eigenen Blick, rechnete jede Seite mit einer anderen."""
    assert nummern_module.erhebe_sicht(wegwerf.haupt, "decisions").basis == 106


def test_ein_name_mit_umlaut_und_leerzeichen_zaehlt_zur_basis(
    nummern_module: ModuleType, wegwerf: Wegwerf
) -> None:
    ablesung = nummern_module.nummern_auf_origin_main(wegwerf.haupt, "specs/decisions")

    assert {103, 104}.issubset(ablesung.nummern)


def test_ein_unterverzeichnis_zaehlt_nicht_mit(
    nummern_module: ModuleType, wegwerf: Wegwerf
) -> None:
    ablesung = nummern_module.nummern_auf_origin_main(wegwerf.haupt, "specs/decisions")

    assert 150 not in ablesung.nummern


def test_ein_fehlender_origin_main_scheitert_laut_statt_still(
    nummern_module: ModuleType, wegwerf: Wegwerf
) -> None:
    _git(wegwerf.haupt, "update-ref", "-d", "refs/remotes/origin/main")

    with pytest.raises(nummern_module.ZuteilerFehler):
        nummern_module.nummern_auf_origin_main(wegwerf.haupt, "specs/decisions")


def test_keine_meldung_zitiert_die_rohe_git_ausgabe(
    nummern_module: ModuleType, wegwerf: Wegwerf
) -> None:
    """Ausgabehygiene: `git remote get-url` kann ein Token tragen, `fatal:` traegt Pfade."""
    _git(wegwerf.haupt, "update-ref", "-d", "refs/remotes/origin/main")

    with pytest.raises(nummern_module.ZuteilerFehler) as befund:
        nummern_module.nummern_auf_origin_main(wegwerf.haupt, "specs/decisions")

    assert "fatal:" not in str(befund.value)


# --- Die Zurechnung, auf der die ganze Injektivitaet ruht --------------------------------------


def test_eine_committete_datei_wird_ihrem_branch_zugerechnet(
    nummern_module: ModuleType, wegwerf: Wegwerf
) -> None:
    sicht = nummern_module.erhebe_sicht(wegwerf.haupt, "decisions")

    assert 106 in set(sicht.gefuehrt["a/committet"])


def test_eine_nur_angelegte_datei_wird_ihrem_branch_zugerechnet(
    nummern_module: ModuleType, wegwerf: Wegwerf
) -> None:
    """Der Verzeichnisweg: 0107 ist nie `git add`-et und steht in keinem Tree."""
    sicht = nummern_module.erhebe_sicht(wegwerf.haupt, "decisions")

    assert 107 in set(sicht.gefuehrt["b/angelegt"])


def test_ein_gepushter_branch_ohne_arbeitsbaum_wird_zugerechnet(
    nummern_module: ModuleType, wegwerf: Wegwerf
) -> None:
    """Der `ls-tree`-Weg: c/gepusht hat kein Verzeichnis, das sich auflisten liesse."""
    sicht = nummern_module.erhebe_sicht(wegwerf.haupt, "decisions")

    assert 108 in set(sicht.gefuehrt["c/gepusht"])


def test_ein_arbeitsbaum_im_haupt_checkout_zaehlt_seinem_eigenen_branch(
    nummern_module: ModuleType, wegwerf: Wegwerf
) -> None:
    """Zu messen, weil es an `.git/info/exclude` haengt - einer Datei ausserhalb des
    Repositoriums."""
    sicht = nummern_module.erhebe_sicht(wegwerf.haupt, "decisions")

    assert 109 in set(sicht.gefuehrt["d/drin"])
    assert 109 not in set(sicht.gefuehrt["z/eigen"])


def test_der_eigene_arbeitsbaum_zaehlt_genau_einmal(
    nummern_module: ModuleType, wegwerf: Wegwerf
) -> None:
    sicht = nummern_module.erhebe_sicht(wegwerf.haupt, "decisions")
    gemessen = nummern_module.kontrahenten(sicht.basis, sicht.gefuehrt, "z/eigen")
    eigene = [k for k in gemessen if k.branch == "z/eigen"]

    assert len(eigene) == 1, "der eigene Arbeitsbaum steht in `git worktree list` und im Index"
    assert eigene[0].nummern == (110,), "0110 liegt in Index und Verzeichnis - und zaehlt einmal"


def test_der_eigene_branch_wird_aus_dem_arbeitsbaum_gelesen(
    nummern_module: ModuleType, wegwerf: Wegwerf
) -> None:
    assert nummern_module.eigener_branch(wegwerf.haupt) == "z/eigen"
    assert nummern_module.erhebe_sicht(wegwerf.haupt, "decisions").eigener_branch == "z/eigen"


def test_die_zuteilung_ueber_den_echten_leser_trifft_die_rangnummer(
    nummern_module: ModuleType, wegwerf: Wegwerf
) -> None:
    sicht = nummern_module.erhebe_sicht(wegwerf.haupt, "decisions")

    assert nummern_module.zugeteilte_nummer(sicht.basis, sicht.gefuehrt, "z/eigen") == 110
    assert nummern_module.zugeteilte_nummer(sicht.basis, sicht.gefuehrt, "a/committet") == 106


def test_der_leser_belegt_dass_ueberhaupt_gelesen_wurde(
    nummern_module: ModuleType, wegwerf: Wegwerf
) -> None:
    """Zaehler statt Abwesenheit: eine leere Menge ist von einer kaputten Aufzaehlung sonst
    nicht zu unterscheiden."""
    sicht = nummern_module.erhebe_sicht(wegwerf.haupt, "decisions")

    assert sicht.gelesen >= 6
    assert sicht.arbeitsbaeume == 4
    assert sicht.fremde_branches == 1


def test_die_symmetrie_beider_filter_am_eigenen_arbeitsbaum(
    nummern_module: ModuleType, wegwerf: Wegwerf
) -> None:
    """Dieselbe Verzeichnisebene, einmal ueber den Index und einmal aufgelistet."""
    ueber_git = nummern_module.nummern_im_index(wegwerf.haupt, "specs/decisions")
    aufgelistet = nummern_module.nummern_im_verzeichnis(wegwerf.haupt / "specs" / "decisions")

    assert ueber_git.nummern == aufgelistet.nummern


def test_der_zweite_nummernraum_wird_getrennt_gefuehrt(
    nummern_module: ModuleType, wegwerf: Wegwerf
) -> None:
    sicht = nummern_module.erhebe_sicht(wegwerf.haupt, "architecture")

    assert sicht.basis == 5
    assert sicht.verzeichnis == "specs/architecture"


# --- Reine Parser: die Formen, an denen eine Aufzaehlung zerbricht -----------------------------


def test_der_porcelain_parser_haelt_einen_zeilenumbruch_im_pfad_aus(
    nummern_module: ModuleType,
) -> None:
    rohdaten = (
        b"worktree /pfad/mit\nzeilenumbruch\x00HEAD abc\x00branch refs/heads/x\x00\x00"
        b"worktree /zweiter\x00HEAD def\x00branch refs/heads/y\x00\x00"
    )

    baeume = nummern_module.arbeitsbaeume_aus_porcelain(rohdaten)

    assert [baum.pfad for baum in baeume] == ["/pfad/mit\nzeilenumbruch", "/zweiter"]
    assert [baum.branch for baum in baeume] == ["x", "y"]


def test_ein_barer_eintrag_ist_kein_kontrahent(nummern_module: ModuleType) -> None:
    rohdaten = (
        b"worktree /bar\x00bare\x00\x00worktree /echt\x00HEAD a\x00branch refs/heads/x\x00\x00"
    )

    baeume = nummern_module.arbeitsbaeume_aus_porcelain(rohdaten)

    assert [baum.bar for baum in baeume] == [True, False]


def test_ein_raeumbarer_eintrag_wird_als_solcher_erkannt(nummern_module: ModuleType) -> None:
    rohdaten = b"worktree /weg\x00HEAD a\x00branch refs/heads/x\x00prunable gone\x00\x00"

    (baum,) = nummern_module.arbeitsbaeume_aus_porcelain(rohdaten)

    assert baum.raeumbar is True


def test_ein_losgeloester_head_ist_kein_leerer_branchname(nummern_module: ModuleType) -> None:
    """Ein leerer Name sortierte byteweise ganz vorn und schoebe alle anderen weiter."""
    rohdaten = b"worktree /los\x00HEAD abc\x00detached\x00\x00"

    (baum,) = nummern_module.arbeitsbaeume_aus_porcelain(rohdaten)

    assert baum.losgeloest is True
    assert baum.branch is None


def test_ein_nachbar_mit_losgeloestem_head_haelt_den_lauf_an(
    nummern_module: ModuleType, wegwerf: Wegwerf
) -> None:
    kopf = _git(wegwerf.nachbar_a, "rev-parse", "HEAD").stdout.strip()
    _git(wegwerf.nachbar_a, "checkout", "--quiet", "--detach", kopf)

    with pytest.raises(nummern_module.ZuteilerFehler, match=r"losgel"):
        nummern_module.erhebe_sicht(wegwerf.haupt, "decisions")


def test_die_pfeilform_von_origin_head_ist_kein_branchname(nummern_module: ModuleType) -> None:
    """`git branch -r` gaebe hier die Zeile `origin/HEAD -> origin/main` aus."""
    felder = [
        "refs/remotes/origin/HEAD",
        "refs/remotes/origin/feature/x",
        "refs/remotes/origin/main",
    ]

    assert nummern_module.branches_aus_refnamen(felder) == ("feature/x", "main")


def test_ein_veralteter_tracking_ref_faellt_ueber_seine_nummer_heraus(
    nummern_module: ModuleType, wegwerf: Wegwerf
) -> None:
    """Sein Tip ist nie Vorfahre von `origin/main`; getragen wird das allein davon, dass seine
    Nummer unter der Basis liegt."""
    _git(wegwerf.pflege, "checkout", "--quiet", "-b", "alt/squash-gemergt", "origin/main")
    _dokument(wegwerf.pflege / "specs" / "decisions", "0100-alt.md")
    _git(wegwerf.pflege, "add", "-A")
    _git(wegwerf.pflege, "commit", "--quiet", "-m", "docs: 0100")
    _git(wegwerf.pflege, "push", "--quiet", "origin", "alt/squash-gemergt")
    _git(wegwerf.haupt, "fetch", "--quiet", "origin")

    sicht = nummern_module.erhebe_sicht(wegwerf.haupt, "decisions")
    namen = [k.branch for k in nummern_module.kontrahenten(sicht.basis, sicht.gefuehrt, "z/eigen")]

    assert "alt/squash-gemergt" not in namen
    assert nummern_module.zugeteilte_nummer(sicht.basis, sicht.gefuehrt, "z/eigen") == 110


# --- Die Unterbefehle und ihre Exit-Codes ------------------------------------------------------

SKRIPT = Path(__file__).parents[1] / "nummern.py"


@dataclass(frozen=True)
class Lauf:
    code: int
    stdout: str
    stderr: str


def _laufe(verzeichnis: Path, *args: str) -> Lauf:
    fertig = subprocess.run(
        [str(SKRIPT), *args],
        cwd=verzeichnis,
        capture_output=True,
        text=True,
        timeout=ZEITGRENZE_SEKUNDEN,
        check=False,
    )
    return Lauf(fertig.returncode, fertig.stdout, fertig.stderr)


# Je Unterbefehl eine geschlossene Menge zulaessiger Exit-Codes. Ein unbekannter Code wird an
# keiner Aufrufstelle wie 0 behandelt.
ZULAESSIGE_CODES: Mapping[str, frozenset[int]] = {
    "vorschlag": frozenset({0, 10, 30}),
    "migration": frozenset({0, 10, 30}),
    "pruefen": frozenset({0, 10, 20, 30}),
    "kette": frozenset({0, 30}),
    "umhaengen": frozenset({0, 10, 30}),
}


def test_das_skript_ist_ausfuehrbar() -> None:
    assert SKRIPT.exists() and os.access(SKRIPT, os.X_OK)


def test_vorschlag_gibt_die_vierstellige_nummer_auf_stdout(wegwerf: Wegwerf) -> None:
    lauf = _laufe(wegwerf.haupt, "vorschlag", "decisions")

    assert lauf.stdout.strip() == "0110"


def test_vorschlag_meldet_kontention_mit_zehn_und_einer_zeile_je_branch(
    wegwerf: Wegwerf,
) -> None:
    lauf = _laufe(wegwerf.haupt, "vorschlag", "decisions")

    assert lauf.code == 10
    befunde = [zeile for zeile in lauf.stderr.splitlines() if "fuehrt" in zeile]
    assert len(befunde) == 4
    assert any("a/committet" in zeile and "0106" in zeile for zeile in befunde)


def test_ohne_kontention_endet_vorschlag_mit_null(wegwerf: Wegwerf) -> None:
    """Exit 0 entsteht an genau einer Stelle - dem einzigen Ausgang, der still falsch sein
    koennte."""
    lauf = _laufe(wegwerf.haupt, "vorschlag", "architecture")

    assert lauf.code == 0
    assert lauf.stdout.strip() == "0005"


def test_vorschlag_features_liefert_nie_eine_zahl(wegwerf: Wegwerf) -> None:
    """Ein Aufrufer, der stdout greppt, darf auch versehentlich keine Nummer bekommen."""
    lauf = _laufe(wegwerf.haupt, "vorschlag", "features")

    assert lauf.code != 0
    assert lauf.code in ZULAESSIGE_CODES["vorschlag"]
    assert not re.search(r"\d{4}", lauf.stdout)
    assert "Issue" in lauf.stderr


def test_ein_unbekannter_nummernraum_wird_abgewiesen(wegwerf: Wegwerf) -> None:
    lauf = _laufe(wegwerf.haupt, "vorschlag", "erfunden")

    assert lauf.code == 30
    assert not re.search(r"\d{4}", lauf.stdout)


def test_ein_unbekannter_unterbefehl_endet_nie_mit_null(wegwerf: Wegwerf) -> None:
    lauf = _laufe(wegwerf.haupt, "gibtesnicht")

    assert lauf.code != 0


def test_pruefen_meldet_die_kontention_mit_zehn(wegwerf: Wegwerf) -> None:
    lauf = _laufe(wegwerf.haupt, "pruefen")

    assert lauf.code == 10
    assert lauf.code in ZULAESSIGE_CODES["pruefen"]


def test_pruefen_belegt_auch_ohne_befund_dass_gelesen_wurde(wegwerf: Wegwerf) -> None:
    """Eine leere Ausgabe darf nie als "nichts gefunden" durchgehen - Zaehler statt
    Abwesenheit."""
    _git(wegwerf.haupt, "worktree", "remove", "--force", str(wegwerf.nachbar_a))
    _git(wegwerf.haupt, "worktree", "remove", "--force", str(wegwerf.nachbar_b))
    _git(wegwerf.haupt, "worktree", "remove", "--force", str(wegwerf.drin))
    _git(wegwerf.haupt, "update-ref", "-d", "refs/remotes/origin/c/gepusht")

    lauf = _laufe(wegwerf.haupt, "pruefen")

    assert lauf.code == 0
    assert re.search(r"\b\d+ Dateinamen", lauf.stdout)
    assert "1 Arbeitsbaum" in lauf.stdout


def test_pruefen_meldet_eine_echte_dublette_im_eigenen_baum_mit_zwanzig(
    wegwerf: Wegwerf,
) -> None:
    """20 ist von 10 an Ausgabe und Code unterscheidbar."""
    _dokument(wegwerf.haupt / "specs" / "decisions", "0110-zweite-vergabe.md")

    lauf = _laufe(wegwerf.haupt, "pruefen")

    assert lauf.code == 20
    assert "0110" in lauf.stdout
    assert "0110-eigen.md" in lauf.stdout and "0110-zweite-vergabe.md" in lauf.stdout


def test_keine_ausgabe_nennt_die_remote_url(wegwerf: Wegwerf) -> None:
    lauf = _laufe(wegwerf.haupt, "pruefen")

    assert str(wegwerf.origin) not in lauf.stdout + lauf.stderr
