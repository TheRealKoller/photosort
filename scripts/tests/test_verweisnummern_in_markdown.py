"""Bindet bei einem Markdown-Verweis die genannte Nummer an die Nummer der Zieldatei.

Specs und ADRs tragen ihre Identitaet in der **Nummer**, und ein Verweis auf sie nennt diese
Nummer zweimal: einmal sichtbar im Linktext (`` [`0060`](…) ``) und einmal im Pfad
(`…/0060-slug.md`). Laufen die beiden auseinander, entsteht der teuerste Verweis, den es gibt:
einer, der aussieht, als truege er, und der jeden Leser an die falsche Entscheidung schickt. Ein
Klick geht woandershin als das Auge.

**Wie der Fehler entstanden ist, und warum ein Test die richtige Antwort darauf ist.** Am
2026-09-06 kollidierten zwei ADRs auf derselben Nummer (0059), weil zwei Branches parallel liefen.
Beim Aufloesen wurde eine der beiden auf 0060 gezogen und die Verweise per pauschaler Ersetzung
ueber die betroffenen Dateien nachgezogen. In den beiden **lebenden** Konzeptdokumenten war das
falsch: Sie handeln nicht von einer Sache, sondern von allen - und trugen deshalb auch Verweise
auf die *fremde* 0059. Die Ersetzung zog dort den Linktext auf `0060`, waehrend das Ziel weiter
auf `0059-modellwahl-…` zeigte. Zwei solche Stellen sind entstanden; ein automatisiertes Review
fand eine davon, die zweite fiel erst bei einem systematischen Abgleich auf.

**Die verallgemeinerte Lehre steht im Testkonzept und lautet:** Eine Umbenennung, die Nummern
traegt, braucht einen Test, der Text und Ziel gegeneinander bindet. Eine pauschale Ersetzung ueber
eine Datei ist nur so gut wie die Annahme, dass die Datei von einer Sache handelt - und lebende
Dokumente handeln von mehreren.

**Der Bestand ist sauber, dieser Test startet also gruen. Ein Rot-Lauf belegt hier deshalb
nichts.** Tragender Beleg ist allein die Mutationsprobe: am 2026-09-06 ein Linktext `0059` auf ein
`0060-`-Ziel gesetzt - der Test faerbte rot -, danach zurueckgenommen. Wer das Muster aendert,
wiederholt diese Probe, statt sie zu glauben. Der zweite Beleg ist der Selbstschutz weiter unten:
Weil der Erfolgsfall "nichts gefunden" ist, waere eine kaputte Dateiaufzaehlung oder ein kaputtes
Muster von einem echten Nullbefund nicht zu unterscheiden.

**Falsch-positiv-Flaeche, am Bestand ausgemessen (2026-09-06, vor der Formulierung):** 186 von Git
verwaltete Markdown-Dateien, 1633 Links insgesamt, davon **1087 Kandidaten** (Ziel ist eine
`.md`-Datei mit vierstelligem Nummernpraefix). Davon:

* **0** Kandidaten, deren Linktext gar keine vierstellige Zahl nennt - es gibt heute keinen
  Verweis der Form ``[Testkonzept](../architecture/0002-testkonzept.md)``. Solche Verweise werden
  trotzdem **uebersprungen** statt bemaengelt: Wer keine Nummer nennt, behauptet auch keine, und
  ein Zwang zur Nummer im Linktext waere Formulierungspolizei.
* **0** Kandidaten mit *mehreren* vierstelligen Zahlen im Linktext. Die Pruefung ist deshalb als
  Mengenzugehoerigkeit formuliert (die Zielnummer muss unter den genannten sein) - bei genau einer
  Zahl ist das Gleichheit, und ein kuenftiges ``[`0288`/`0339`](…/0339-….md)`` bleibt gruen, ohne
  dass jemand eine Ausnahme bauen muss.
* **0** Verweise der Gegenrichtung (Linktext nennt eine Nummer, Ziel ist eine `.md` **ohne**
  Nummernpraefix).
* **0** Verstoesse insgesamt. Es gibt im Bestand **keinen** Verweis, dessen Text bewusst eine
  andere Nummer nennt als sein Ziel - es war also keine Ausnahmeliste noetig, und es soll auch
  keine geben. Taucht je ein solcher Fall auf, ist er zu klaeren, nicht auszunehmen.

Nicht geprueft wird, ob das Ziel **existiert** - das ist eine andere Fehlerklasse (toter Link) mit
anderer Ausnahmelage: In eingefrorenen Momentaufnahmen sind tote Ziele bewusst hingenommen (siehe
Testkonzept, Sektion "Repo-weite Doku-Restrukturierung"), eine falsche Nummer dagegen ist in jeder
Zeitform falsch. Genau diese Trennschaerfe macht diese Zusicherung ausnahmefrei.

Kein Netzwerk - gelesen werden ausschliesslich Dateien dieses Repositories.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_WURZEL = Path(__file__).parents[2]

# Selbstschutz: Der Erfolgsfall dieses Tests ist "nichts gefunden". Eine kaputte Aufzaehlung oder
# ein kaputtes Muster liefert dasselbe Ergebnis wie ein sauberer Bestand. Beide Untergrenzen sind
# bewusst weit unter dem Ist-Stand (186 Dateien, 1087 Kandidaten) gewaehlt - sie fangen den
# Totalausfall, nicht jede geloeschte Datei.
MINDESTZAHL_MARKDOWN_DATEIEN = 100
MINDESTZAHL_KANDIDATEN = 500

_LINK = re.compile(r"\[(?P<text>[^\]\n]*)\]\((?P<ziel>[^)\s]+)\)")
# Ein Kandidat ist ein Verweis, dessen Ziel eine `.md`-Datei mit vierstelligem Nummernpraefix ist.
# Der Anker `(?:^|/)` bindet die Nummer an den **Dateinamen**, nicht an ein Verzeichnis: Ein Pfad
# wie `specs/0059/notizen.md` traegt keine Verweisnummer.
_ZIELNUMMER = re.compile(r"(?:^|/)(?P<nummer>\d{4})-[^/]*\.md$")
_TEXTNUMMER = re.compile(r"\d{4}")


@dataclass(frozen=True)
class Verweis:
    """Ein Markdown-Verweis auf eine nummerierte Datei, so wie er im Text steht."""

    datei: str
    zeile: int
    text: str
    ziel: str
    zielnummer: str

    @property
    def fundstelle(self) -> str:
        return f"{self.datei}:{self.zeile}"

    @property
    def genannte_nummern(self) -> frozenset[str]:
        return frozenset(_TEXTNUMMER.findall(self.text))


def verweise_aus_text(text: str, datei: str = "<text>") -> list[Verweis]:
    """Reine Funktion: sammelt die nummerierten Verweise eines Textes samt Fundstelle.

    Ein Anker (`#abschnitt`) am Ziel wird abgeschnitten - er gehoert nicht zum Dateinamen.
    Verweise, deren Ziel keine nummerierte `.md`-Datei ist (externe URLs, `docs/setup.md`,
    Issue-Links), sind keine Kandidaten und tauchen hier gar nicht erst auf.
    """
    verweise: list[Verweis] = []
    for nummer, zeile in enumerate(text.split("\n"), start=1):
        for treffer in _LINK.finditer(zeile):
            ziel = treffer.group("ziel").split("#")[0]
            zielnummer = _ZIELNUMMER.search(ziel)
            if not zielnummer:
                continue
            verweise.append(
                Verweis(
                    datei=datei,
                    zeile=nummer,
                    text=treffer.group("text"),
                    ziel=ziel,
                    zielnummer=zielnummer.group("nummer"),
                )
            )
    return verweise


def nummern_verstoesse(verweise: list[Verweis]) -> list[str]:
    """Reine Funktion: meldet je Verstoss Fundstelle, sichtbare Nummer und Zielnummer.

    Nennt der Linktext **keine** vierstellige Zahl, behauptet er auch keine Nummer - dann gibt es
    nichts zu binden, und der Verweis wird uebersprungen statt bemaengelt.
    """
    befunde: list[str] = []
    for verweis in verweise:
        genannt = verweis.genannte_nummern
        if not genannt:
            continue
        if verweis.zielnummer not in genannt:
            befunde.append(
                f"{verweis.fundstelle}: Der Linktext nennt {sorted(genannt)}, das Ziel ist aber "
                f"{verweis.zielnummer!r} ({verweis.ziel}). Ein Klick geht woandershin als das "
                "Auge - Text ans tatsaechliche Ziel binden, nicht umgekehrt."
            )
    return befunde


def verweise_im_abbild(abbild: Mapping[str, str]) -> list[Verweis]:
    """Reine Funktion ueber ein Pfad->Text-Abbild; ein leerer Suchraum ist ein Fehlerfall."""
    if not abbild:
        raise ValueError(
            "0 Dateien im Suchraum: Damit sind die Verweisnummern ungeprueft. Entweder lief die "
            "Dateiaufzaehlung im falschen Arbeitsverzeichnis, oder sie ist kaputt - ein leerer "
            "Suchraum darf nie als 'nichts gefunden' durchgehen."
        )

    verweise: list[Verweis] = []
    for datei in sorted(abbild):
        verweise.extend(verweise_aus_text(abbild[datei], datei))
    return verweise


def markdown_dateien(wurzel: Path = REPO_WURZEL) -> dict[str, str]:
    """Duenner Leser: **alle** von Git verwalteten Markdown-Dateien.

    Kein eingeschraenkter Suchraum und keine Ausnahme: Die Fehlerklasse kann ueberall auftreten,
    und anders als bei einem toten Ziel gibt es fuer eine falsche Nummer keine 'war damals
    richtig'-Lesart, die eine historische Datei ausnehmen wuerde.
    """
    ergebnis = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=wurzel,
        capture_output=True,
        check=True,
    )
    pfade = [pfad.decode("utf-8") for pfad in ergebnis.stdout.split(b"\0") if pfad]
    return {
        pfad: (wurzel / pfad).read_text(encoding="utf-8")
        for pfad in pfade
        if pfad.endswith(".md") and (wurzel / pfad).is_file()
    }


# --- Selbstschutz ------------------------------------------------------------------------


def test_der_suchraum_hat_eine_plausible_groesse() -> None:
    dateien = markdown_dateien()

    assert len(dateien) >= MINDESTZAHL_MARKDOWN_DATEIEN, (
        f"Nur {len(dateien)} verwaltete Markdown-Dateien gefunden (erwartet: mindestens "
        f"{MINDESTZAHL_MARKDOWN_DATEIEN}). Die Aufzaehlung ist kaputt; ein Nullbefund dieses "
        "Tests waere dann bedeutungslos."
    )


def test_das_muster_findet_ueberhaupt_verweise() -> None:
    """Ohne diese Untergrenze waere ein kaputtes Linkmuster von einem sauberen Bestand nicht zu
    unterscheiden - beide melden null Verstoesse."""
    verweise = verweise_im_abbild(markdown_dateien())

    assert len(verweise) >= MINDESTZAHL_KANDIDATEN, (
        f"Nur {len(verweise)} nummerierte Verweise gefunden (erwartet: mindestens "
        f"{MINDESTZAHL_KANDIDATEN}). Entweder ist das Linkmuster kaputt, oder die Verweisform hat "
        "sich geaendert - dann ist dieser Test mitzuziehen, sonst prueft er lautlos nichts mehr."
    )


# --- Die eigentliche Zusicherung ---------------------------------------------------------


def test_jeder_verweis_nennt_die_nummer_seines_ziels() -> None:
    befunde = nummern_verstoesse(verweise_im_abbild(markdown_dateien()))

    assert not befunde, (
        "Verweis mit falscher Nummer: " + "; ".join(befunde) + ". Es gibt hier bewusst **keine** "
        "Ausnahmeliste - eine falsche Nummer ist in jeder Zeitform falsch, auch in einer "
        "eingefrorenen Momentaufnahme."
    )


# --- Gegenproben an synthetischem Text ---------------------------------------------------


def test_ein_auseinandergelaufener_verweis_wird_gemeldet() -> None:
    """Der reale Fehlerfall: Eine pauschale Ersetzung zieht den Text, nicht das Ziel."""
    text = "ADR [`0060`](../decisions/0059-modellwahl-je-anbieter.md) sagt dazu …\n"

    befunde = nummern_verstoesse(verweise_aus_text(text, "specs/architecture/0002-x.md"))

    assert len(befunde) == 1
    assert befunde[0].startswith("specs/architecture/0002-x.md:1:")
    assert "'0059'" in befunde[0]


def test_der_erwartete_verweis_gilt_nicht_als_verstoss() -> None:
    text = "ADR [`0060`](../decisions/0060-ein-ort-fuer-jeden-github-zugriff.md)\n"

    assert nummern_verstoesse(verweise_aus_text(text, "x.md")) == []


@pytest.mark.parametrize(
    "zeile",
    [
        "Siehe [`0339`](./0339-ein-ort.md).",
        "Siehe [ADR 0339](../decisions/0339-ein-ort.md).",
        "Siehe [`decisions/0339-ein-ort.md`](../../specs/decisions/0339-ein-ort.md).",
        "Siehe [`0339`](./0339-ein-ort.md#abschnitt).",
    ],
)
def test_jede_gebraeuchliche_verweisform_wird_korrekt_gelesen(zeile: str) -> None:
    verweise = verweise_aus_text(zeile + "\n", "x.md")

    assert [v.zielnummer for v in verweise] == ["0339"]
    assert nummern_verstoesse(verweise) == []


def test_ein_linktext_ohne_nummer_behauptet_nichts() -> None:
    """Wer keine Nummer nennt, nennt auch keine falsche - Zwang zur Nummer waere Wortpolizei."""
    text = "Das [Testkonzept](../architecture/0002-testkonzept.md) sagt dazu …\n"

    verweise = verweise_aus_text(text, "x.md")

    assert len(verweise) == 1
    assert nummern_verstoesse(verweise) == []


def test_mehrere_nummern_im_linktext_gelten_als_erfuellt_wenn_die_zielnummer_dabei_ist() -> None:
    text = "Siehe [`0288`/`0339`](../features/0339-ein-ort.md).\n"

    assert nummern_verstoesse(verweise_aus_text(text, "x.md")) == []


def test_mehrere_nummern_ohne_die_zielnummer_werden_gemeldet() -> None:
    text = "Siehe [`0288`/`0327`](../features/0339-ein-ort.md).\n"

    befunde = nummern_verstoesse(verweise_aus_text(text, "x.md"))

    assert len(befunde) == 1
    assert "'0339'" in befunde[0]


@pytest.mark.parametrize(
    "zeile",
    [
        "Ein [externer Link](https://github.com/TheRealKoller/photosort/issues/339).",
        "Das [Setup](../../docs/setup.md) beschreibt das.",
        "Issue [`#339`](https://github.com/TheRealKoller/photosort/issues/339).",
        "Eine Notiz in [`specs/0059/notizen.md`](../0059/notizen.md).",
    ],
)
def test_ein_ziel_ohne_nummerierten_dateinamen_ist_kein_kandidat(zeile: str) -> None:
    """Nur ein Ziel, das seine Nummer im **Dateinamen** traegt, kann eine Nummer widersprechen."""
    assert verweise_aus_text(zeile + "\n", "x.md") == []


def test_zwei_verweise_in_einer_zeile_werden_einzeln_gelesen() -> None:
    text = (
        "Zwischen [`0057`](../decisions/0057-a.md) und [`0059`](../decisions/0060-b.md) "
        "besteht ein Unterschied.\n"
    )

    verweise = verweise_aus_text(text, "x.md")
    befunde = nummern_verstoesse(verweise)

    assert [v.zielnummer for v in verweise] == ["0057", "0060"]
    assert len(befunde) == 1
    assert "'0060'" in befunde[0]


def test_die_fundstelle_nennt_datei_und_zeile() -> None:
    text = "Zeile eins\n\nSiehe [`0059`](../decisions/0060-b.md).\n"

    befunde = nummern_verstoesse(verweise_aus_text(text, "specs/README.md"))

    assert befunde[0].startswith("specs/README.md:3:")


def test_ein_leerer_suchraum_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"0 Dateien"):
        verweise_im_abbild({})


def test_der_leser_findet_die_dateien_dieses_repositories() -> None:
    """Gegenprobe zum Leser selbst: Er muss die Verfassung des Projekts sehen."""
    dateien = markdown_dateien()

    assert "CLAUDE.md" in dateien
    assert "specs/architecture/0002-testkonzept.md" in dateien
