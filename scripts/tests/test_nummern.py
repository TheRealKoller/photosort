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
from collections.abc import Collection, Mapping, Sequence
from types import ModuleType

import pytest

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
