"""Sichert zu, dass eine Dokumentnummer je Verzeichnis genau ein Dokument bezeichnet.

Specs, ADRs und Konzeptdokumente tragen ihre Identitaet in ihrer vierstelligen Nummer, und die
gebraeuchlichste Form, sie zu nennen, ist die blanke Zahl ("ADR 0069 Punkt 8") ohne Dateinamen.
Ist dieselbe Nummer zweimal vergeben, bezeichnet jede solche Nennung zwei Dokumente, und kein
Leser kann entscheiden, welches gemeint ist. Der Nachbartest
`test_verweisnummern_in_markdown.py` faengt das nicht: Er bindet den sichtbaren Linktext an seine
Zieldatei, und bei einer Dublette passt der Text zu **beiden** Zielen.

**Zwei Zusicherungen, die einander bedingen.** (1) Eindeutigkeit: keine zwei `.md` unmittelbar in
demselben der drei Verzeichnisse tragen dasselbe Nummernpraefix. (2) Praefix-Vollstaendigkeit:
jede `.md` unmittelbar in diesen Verzeichnissen traegt ueberhaupt ein vierstelliges Praefix. Ohne
die zweite entkaeme ein Dokument der ersten, indem es sein Praefix verliert und damit aus dem
Suchraum faellt. Preis: Eine kuenftige `README.md` in einem der drei Verzeichnisse faerbt rot -
bewusst so, denn eine Ausweitung der Namenskonvention soll entschieden werden statt einzusickern.

**Je Verzeichnis, nicht verzeichnisuebergreifend.** Die drei Nummernraeume ueberlappen von Bauart
wegen (eine Feature-Spec traegt die Nummer ihres Issues, ADR 0043; `decisions/` und
`architecture/` zaehlen je fuer sich). Gemessen fuehren 66 verschiedene Nummern mehr als ein
Verzeichnis - eine gemeinsame Pruefung waere an jeder von ihnen rot und sachlich falsch.

**Keine Ausnahmeliste, auch keine leere vorbereitete.** Eine gefundene Dublette wird aufgeloest,
nicht ausgenommen (ADR 0081). Eine Ausnahme, die nichts ausnimmt, ist eine Einladung, spaeter eine
echte danebenzustellen.

**Wirksamkeitsbeleg.** Tragend ist die dauerhafte synthetische Gegenprobe weiter unten, die auch
den Meldungstext prueft - sie laeuft nach jeder kuenftigen Aenderung am Muster noch. **Wer das
Muster aendert, erzeugt den Befund synthetisch nach, statt ihn zu glauben.** Der folgende Lauf
ergaenzt, was sie nicht leisten kann: die Verdrahtung ueber die ganze Kette an echten Daten. Er
ist beim Anlegen dieser Datei mit dem CI-Befehl (`pytest` im Verzeichnis `scripts/`, ohne Angabe
einer Testdatei) auf dem damals noch doppelt vergebenen Bestand entstanden und ist
unwiederbringlich - nach der Aufloesung der Dublette laesst er sich nicht erneut erzeugen:

$ cd scripts && pytest
[...]
=================================== FAILURES ===================================
_________ test_keine_nummer_ist_in_einem_verzeichnis_zweimal_vergeben __________
E   AssertionError: Doppelt vergebene Dokumentnummer: specs/decisions: Die Nummer
E   '0069' ist 2-fach vergeben:
E   specs/decisions/0069-ansichtsentwuerfe-als-handarbeit-mit-soll-struktur-im-repository.md,
E   specs/decisions/0069-nebenkategorien-mehrfachzugehoerigkeit-und-konfidenzgewichtete-rangfolge.md.
E   Jede blanke Nennung dieser Nummer bezeichnet damit mehr als ein Dokument - die
E   juengere Vergabe zieht auf die naechste freie Nummer um (ADR 0081). Es gibt hier
E   bewusst **keine** Ausnahmeliste - eine Dublette wird aufgeloest, nicht ausgenommen.
=========================== short test summary info ============================
FAILED tests/test_dokumentnummern_eindeutig.py::test_keine_nummer_ist_in_einem_verzeichnis_zweimal_vergeben
======================== 1 failed, 927 passed in 11.11s ========================

Die Meldung stand im Lauf in **einer** Zeile; oben ist sie allein zur Zeilenbreite umbrochen,
Wortlaut und Reihenfolge sind unveraendert. Der Lauf belegt in einem: dass die Pruefung im
regulaeren Pruefsatz mitlaeuft und ihn fehlschlagen laesst (nicht bloss warnt), und dass die
Meldung **alle** betroffenen Dateien vollstaendig nennt statt nur der mehrdeutigen Nummer.

Der oben zitierte alte Dateiname `0069-ansichtsentwuerfe-...` ist damit eine bewusste, historische
Nennung und die einzige ausserhalb von ADR 0081 und der Spec 0406. Wer nach Resten der
Umnummerierung sucht, zaehlt diese Stelle nicht als uebersehene Fundstelle.

**Selbstschutz.** Der Erfolgsfall dieser Pruefung ist "nichts gefunden"; eine kaputte
Dateiaufzaehlung liefert dasselbe Ergebnis wie ein sauberer Bestand. Dagegen stehen: ein lauter
Fehlerfall bei leerem Suchraum (insgesamt und je Verzeichnis), eine Untergrenze je Verzeichnis und
eine namentlich genannte Ankerdatei je Verzeichnis. Der Anker traegt den Fall, den die Untergrenze
nicht traegt: Bei `specs/architecture/` mit vier Dokumenten entartet jede Untergrenze, und nur der
Anker faengt es, wenn ein Verzeichnis ganz aus der Aufzaehlung faellt.

Kein Netzwerk - gelesen werden ausschliesslich Dateinamen des eigenen, von Git verwalteten
Bestandes.
"""

from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Iterable, Mapping
from pathlib import Path

import pytest

REPO_WURZEL = Path(__file__).parents[2]

# Die drei Nummernraeume. Nur unmittelbar darin liegende `.md`-Dateien sind Dokumente im Sinne
# dieser Zusicherung - Unterverzeichnisse und andere Dateitypen gibt es dort heute nicht und sie
# bleiben ausdruecklich ausserhalb, statt stillschweigend mitgeprueft zu werden.
GEPRUEFTE_VERZEICHNISSE: tuple[str, ...] = (
    "specs/architecture",
    "specs/decisions",
    "specs/features",
)

# Selbstschutz, bewusst weit unter dem Ist-Stand (4 / 82 / 113 am 2026-09-11): Diese Grenzen
# fangen den Totalausfall der Aufzaehlung, nicht jede geloeschte Datei.
MINDESTZAHL_JE_VERZEICHNIS: Mapping[str, int] = {
    "specs/architecture": 2,
    "specs/decisions": 60,
    "specs/features": 80,
}

# Selbstschutz, zweite Form: Bei vier Dokumenten entartet jede Untergrenze. Als Anker taugt kein
# Dokument, das selbst zur Umbenennung ansteht.
ANKERDATEI_JE_VERZEICHNIS: Mapping[str, str] = {
    "specs/architecture": "specs/architecture/0002-testkonzept.md",
    "specs/decisions": "specs/decisions/0001-tech-stack.md",
    "specs/features": "specs/features/0001-opencloud-project-connection.md",
}

# Vierstellige Nummer, Trennstrich, nicht-leerer Rumpf, `.md`. Eine fuenfstellige Zahl, ein
# fehlender Trennstrich oder Ziffern mitten im Namen sind **keine** Dokumentnummer.
_NUMMERNPRAEFIX = re.compile(r"^(?P<nummer>\d{4})-.+\.md$")


def dokumente_je_verzeichnis(pfade: Iterable[str]) -> dict[str, list[str]]:
    """Reine Funktion: ordnet repo-relative Pfade den drei geprueften Verzeichnissen zu.

    Pfade werden zu einer **Menge** zusammengefasst: `git ls-files --cached` listet einen
    unvereinigten Pfad mitten im Abgleich mit `main` mehrfach (eine Zeile je Stage). Ohne die
    Zusammenfassung meldete der Waechter genau dann eine Datei als Dublette ihrer selbst, wenn
    ohnehin gerade ein Konflikt aufzuloesen ist.

    Nur das **unmittelbare** Elternverzeichnis zaehlt, ein `specs/features/entwuerfe/x.md` faellt
    also heraus - ebenso jede Datei, die nicht auf `.md` endet.
    """
    gefunden: dict[str, set[str]] = {verzeichnis: set() for verzeichnis in GEPRUEFTE_VERZEICHNISSE}
    for pfad in pfade:
        verzeichnis, trenner, dateiname = pfad.rpartition("/")
        if not trenner or verzeichnis not in gefunden or not dateiname.endswith(".md"):
            continue
        gefunden[verzeichnis].add(pfad)
    return {verzeichnis: sorted(pfade) for verzeichnis, pfade in gefunden.items()}


def dubletten_befunde(dokumente: Mapping[str, list[str]]) -> list[str]:
    """Reine Funktion: meldet je doppelt vergebener Nummer **alle** betroffenen Dateien.

    Die Meldung nennt die vollstaendigen repo-relativen Pfade in stabiler Reihenfolge; die Nummer
    steht nur zusaetzlich dabei, denn sie ist genau das Mehrdeutige. Ein Befund entsteht erst ab
    zwei **verschiedenen** Pfaden.
    """
    befunde: list[str] = []
    for verzeichnis in sorted(dokumente):
        je_nummer: dict[str, set[str]] = {}
        for pfad in dokumente[verzeichnis]:
            treffer = _NUMMERNPRAEFIX.match(pfad.rpartition("/")[2])
            if treffer:
                je_nummer.setdefault(treffer.group("nummer"), set()).add(pfad)
        for nummer in sorted(je_nummer):
            betroffen = sorted(je_nummer[nummer])
            if len(betroffen) < 2:
                continue
            befunde.append(
                f"{verzeichnis}: Die Nummer {nummer!r} ist {len(betroffen)}-fach vergeben: "
                + ", ".join(betroffen)
                + ". Jede blanke Nennung dieser Nummer bezeichnet damit mehr als ein Dokument "
                "- die juengere Vergabe zieht auf die naechste freie Nummer um (ADR 0081)."
            )
    return befunde


def praefix_befunde(dokumente: Mapping[str, list[str]]) -> list[str]:
    """Reine Funktion: meldet jede `.md` ohne vierstelliges Nummernpraefix.

    Das ist keine Formalie, sondern das Schlupfloch der Eindeutigkeitszusage: Wer sein Praefix
    verliert, faellt aus der Gruppierung heraus, statt gemeldet zu werden.
    """
    befunde: list[str] = []
    for verzeichnis in sorted(dokumente):
        for pfad in dokumente[verzeichnis]:
            if not _NUMMERNPRAEFIX.match(pfad.rpartition("/")[2]):
                befunde.append(
                    f"{pfad}: kein vierstelliges Nummernpraefix der Form 'NNNN-'. Ohne Nummer "
                    "faellt das Dokument aus der Eindeutigkeitspruefung heraus, statt von ihr "
                    "erfasst zu werden."
                )
    return befunde


def suchraum_pruefen(dokumente: Mapping[str, list[str]]) -> None:
    """Ein leerer Suchraum ist ein lauter Fehlerfall, nie ein Nullbefund."""
    if not any(dokumente.get(verzeichnis) for verzeichnis in GEPRUEFTE_VERZEICHNISSE):
        raise ValueError(
            "0 Dokumente im Suchraum: Damit sind die Dokumentnummern ungeprueft. Entweder lief "
            "die Dateiaufzaehlung im falschen Arbeitsverzeichnis, oder sie ist kaputt - ein "
            "leerer Suchraum darf nie als 'nichts gefunden' durchgehen."
        )
    leer = [
        verzeichnis for verzeichnis in GEPRUEFTE_VERZEICHNISSE if not dokumente.get(verzeichnis)
    ]
    if leer:
        raise ValueError(
            f"Kein Dokument in {', '.join(leer)}: Dieses Verzeichnis ist aus der Aufzaehlung "
            "gefallen und seine Nummern sind ungeprueft - ein stiller Nullbefund waere hier das "
            "gefaehrlichere Ergebnis als ein Fehler."
        )


def verwaltete_pfade(wurzel: Path = REPO_WURZEL) -> list[str]:
    """Duenner Leser: von Git verwaltete **und** neu angelegte, nicht ignorierte Pfade.

    `--others` gehoert dazu, weil eine Dublette in dem Moment entsteht, in dem die Datei angelegt
    wird - vor dem `git add`; genau dann soll die Pruefung am lautesten sein. Im CI-Checkout
    liefern beide Formen dasselbe. `-z` trennt die Aufzaehlung nullterminiert, damit ein
    Dateiname mit Leerzeichen nicht zerfaellt.
    """
    ergebnis = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=wurzel,
        capture_output=True,
        check=True,
    )
    return [pfad.decode("utf-8") for pfad in ergebnis.stdout.split(b"\0") if pfad]


def dokumentbestand(wurzel: Path = REPO_WURZEL) -> dict[str, list[str]]:
    dokumente = dokumente_je_verzeichnis(verwaltete_pfade(wurzel))
    suchraum_pruefen(dokumente)
    return dokumente


# --- Selbstschutz ------------------------------------------------------------------------


@pytest.mark.parametrize("verzeichnis", GEPRUEFTE_VERZEICHNISSE)
def test_jedes_verzeichnis_hat_eine_plausible_groesse(verzeichnis: str) -> None:
    gefunden = dokumentbestand()[verzeichnis]
    erwartet = MINDESTZAHL_JE_VERZEICHNIS[verzeichnis]

    assert len(gefunden) >= erwartet, (
        f"Nur {len(gefunden)} Dokumente in {verzeichnis} gefunden (erwartet: mindestens "
        f"{erwartet}). Die Aufzaehlung ist kaputt; ein Nullbefund dieses Tests waere dann "
        "bedeutungslos."
    )


@pytest.mark.parametrize("verzeichnis", GEPRUEFTE_VERZEICHNISSE)
def test_jedes_verzeichnis_enthaelt_seine_ankerdatei(verzeichnis: str) -> None:
    """Bei vier Dokumenten entartet die Untergrenze - nur der Anker faengt ein ganz fehlendes
    Verzeichnis."""
    anker = ANKERDATEI_JE_VERZEICHNIS[verzeichnis]

    assert anker in dokumentbestand()[verzeichnis], (
        f"{anker} steht nicht im gelesenen Bestand von {verzeichnis}. Entweder ist das "
        "Verzeichnis aus der Aufzaehlung gefallen, oder der Anker wurde umbenannt - dann ist "
        "dieser Test mitzuziehen, sonst prueft er lautlos nichts mehr."
    )


def test_ein_leerer_suchraum_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"0 Dokumente"):
        suchraum_pruefen(dokumente_je_verzeichnis([]))


def test_ein_einzelnes_leeres_verzeichnis_scheitert_laut_statt_still() -> None:
    pfade = ["specs/architecture/0002-a.md", "specs/decisions/0001-b.md"]

    with pytest.raises(ValueError, match=r"Kein Dokument in specs/features"):
        suchraum_pruefen(dokumente_je_verzeichnis(pfade))


# --- Die eigentlichen Zusicherungen ------------------------------------------------------


def test_keine_nummer_ist_in_einem_verzeichnis_zweimal_vergeben() -> None:
    befunde = dubletten_befunde(dokumentbestand())

    assert not befunde, (
        "Doppelt vergebene Dokumentnummer: "
        + "; ".join(befunde)
        + " Es gibt hier bewusst **keine** Ausnahmeliste - eine Dublette wird aufgeloest, nicht "
        "ausgenommen."
    )


def test_jedes_dokument_traegt_ein_vierstelliges_nummernpraefix() -> None:
    befunde = praefix_befunde(dokumentbestand())

    assert not befunde, (
        "Dokument ohne Nummernpraefix: "
        + "; ".join(befunde)
        + " Soll die Namenskonvention dieser Verzeichnisse erweitert werden, ist das zu "
        "entscheiden und hier nachzuziehen - nicht auszunehmen."
    )


# --- Gegenproben an synthetischem Material -----------------------------------------------


def test_eine_dublette_wird_mit_beiden_vollstaendigen_dateinamen_gemeldet() -> None:
    """Der reale Fehlerfall, an dem diese Pruefung entstanden ist."""
    pfade = [
        "specs/decisions/0069-zweite-sache.md",
        "specs/decisions/0069-erste-sache.md",
        "specs/decisions/0070-etwas-anderes.md",
    ]

    befunde = dubletten_befunde(dokumente_je_verzeichnis(pfade))

    assert len(befunde) == 1
    assert befunde[0].startswith("specs/decisions: Die Nummer '0069' ist 2-fach vergeben: ")
    assert "specs/decisions/0069-erste-sache.md" in befunde[0]
    assert "specs/decisions/0069-zweite-sache.md" in befunde[0]
    assert "0070" not in befunde[0]


def test_die_meldung_nennt_die_dateien_in_stabiler_reihenfolge() -> None:
    """Die Eingabereihenfolge darf den Meldungstext nicht veraendern - sonst ist er nicht
    vergleichbar und diese Gegenprobe nicht wiederholbar."""
    pfade = ["specs/features/0300-b.md", "specs/features/0300-a.md"]

    befunde = dubletten_befunde(dokumente_je_verzeichnis(pfade))
    umgekehrt = dubletten_befunde(dokumente_je_verzeichnis(list(reversed(pfade))))

    assert befunde == umgekehrt
    assert "specs/features/0300-a.md, specs/features/0300-b.md" in befunde[0]


def test_drei_dateien_auf_derselben_nummer_werden_alle_genannt() -> None:
    pfade = [
        "specs/features/0051-a.md",
        "specs/features/0051-b.md",
        "specs/features/0051-c.md",
    ]

    befunde = dubletten_befunde(dokumente_je_verzeichnis(pfade))

    assert len(befunde) == 1
    assert "3-fach vergeben" in befunde[0]
    assert all(pfad in befunde[0] for pfad in pfade)


def test_dieselbe_nummer_in_verschiedenen_verzeichnissen_ist_kein_befund() -> None:
    """Die Nummernraeume ueberlappen von Bauart wegen - heute an 66 Nummern."""
    pfade = [
        "specs/decisions/0051-eine-entscheidung.md",
        "specs/features/0051-ein-feature.md",
        "specs/architecture/0051-ein-konzept.md",
    ]

    assert dubletten_befunde(dokumente_je_verzeichnis(pfade)) == []


def test_ein_unvereinigter_pfad_ist_keine_dublette_seiner_selbst() -> None:
    """`git ls-files --cached` listet mitten im Merge eine Zeile je Stage - gemessen dreimal."""
    pfade = ["specs/features/0406-a.md"] * 3

    assert dubletten_befunde(dokumente_je_verzeichnis(pfade)) == []
    assert dokumente_je_verzeichnis(pfade)["specs/features"] == ["specs/features/0406-a.md"]


@pytest.mark.parametrize(
    "pfad",
    [
        "specs/decisions/notizen.txt",
        "specs/decisions/0069-etwas.md.bak",
        "specs/features/entwuerfe/0069-etwas.md",
        "specs/README.md",
        "docs/0069-etwas.md",
    ],
)
def test_was_nicht_unmittelbar_als_markdown_darin_liegt_bleibt_draussen(pfad: str) -> None:
    dokumente = dokumente_je_verzeichnis([pfad])

    assert all(not eintraege for eintraege in dokumente.values())


@pytest.mark.parametrize(
    "dateiname",
    ["README.md", "00691-zu-lang.md", "0069etwas-ohne-trennstrich.md", "entwurf-0069-a.md"],
)
def test_ein_dokument_ohne_gueltiges_praefix_faellt_nicht_still_heraus(dateiname: str) -> None:
    """Der Fall darf nicht aus der Eindeutigkeitspruefung fallen - er faellt in die zweite
    Zusicherung."""
    pfad = f"specs/decisions/{dateiname}"
    dokumente = dokumente_je_verzeichnis([pfad])

    assert dubletten_befunde(dokumente) == []
    befunde = praefix_befunde(dokumente)
    assert len(befunde) == 1
    assert befunde[0].startswith(f"{pfad}: kein vierstelliges Nummernpraefix")


def test_ein_dateiname_mit_leerzeichen_zerfaellt_nicht() -> None:
    pfade = ["specs/features/0069-mit leerzeichen.md", "specs/features/0069-ohne.md"]

    dokumente = dokumente_je_verzeichnis(pfade)

    assert dokumente["specs/features"] == sorted(pfade)
    assert "specs/features/0069-mit leerzeichen.md" in dubletten_befunde(dokumente)[0]


def test_ein_sauberer_bestand_meldet_nichts() -> None:
    pfade = [
        "specs/architecture/0002-testkonzept.md",
        "specs/decisions/0069-a.md",
        "specs/decisions/0082-b.md",
        "specs/features/0406-c.md",
    ]
    dokumente = dokumente_je_verzeichnis(pfade)

    assert dubletten_befunde(dokumente) == []
    assert praefix_befunde(dokumente) == []


def test_der_leser_findet_die_dokumente_dieses_repositories() -> None:
    """Gegenprobe zum Leser selbst: Er muss den echten Bestand sehen, nicht nur etwas."""
    dokumente = dokumentbestand()

    assert "specs/architecture/0002-testkonzept.md" in dokumente["specs/architecture"]
    assert all(pfad.endswith(".md") for pfad in dokumente["specs/decisions"])


# --- Gegenprobe zum Leser an einem Wegwerf-Repositorium -----------------------------------


def _git(repo: Path, *args: str) -> None:
    ergebnis = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert ergebnis.returncode == 0, (
        f"Fixture-Aufbau gescheitert: git {' '.join(args)} -> {ergebnis.returncode}\n"
        f"{ergebnis.stderr}"
    )


@pytest.fixture
def wegwerf_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Ein Mini-Repositorium mit drei Dokumenten auf **derselben** Nummer, in drei Zustaenden.

    Saemtliche `GIT_*` der aufrufenden Umgebung werden entfernt und die Decke auf das
    Elternverzeichnis gesetzt: Sonst richtete ein stehen gebliebenes `GIT_DIR` den Leser auf das
    echte PhotoSort-Repositorium, und der Test waere aus dem falschen Grund gruen.
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

    repo = tmp_path / "repo"
    (repo / "specs" / "decisions").mkdir(parents=True)
    _git(repo, "init", "--quiet", "-b", "main")

    (repo / ".gitignore").write_text("*-ignoriert.md\n", encoding="utf-8")
    (repo / "specs" / "decisions" / "0001-committet.md").write_text("# 0001\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "--quiet", "-m", "chore: Ausgangsstand")

    (repo / "specs" / "decisions" / "0001-ungetrackt.md").write_text("# 0001\n", encoding="utf-8")
    (repo / "specs" / "decisions" / "0001-ignoriert.md").write_text("# 0001\n", encoding="utf-8")
    return repo


def test_eine_neue_datei_zaehlt_vor_dem_git_add_mit_eine_ignorierte_nicht(
    wegwerf_repo: Path,
) -> None:
    """Entwurfsentscheidung 2: Die Dublette entsteht beim Anlegen der Datei, nicht beim `add`.

    Beide Haelften haengen an je einem Schalter des Leseaufrufs. Faellt `--others` weg, wird der
    Waechter erst nach dem `git add` scharf - also genau dann nicht mehr, wenn er gebraucht wird.
    Faellt `--exclude-standard` weg, faerbt jede ignorierte Ablage rot. Ohne diesen Test bemerkt
    beides kein einziger Lauf.

    Mutationsprobe am 2026-09-11: Jeder der beiden Schalter wurde einzeln aus `verwaltete_pfade`
    entfernt; beide Male faerbte genau dieser Test rot, mit der jeweils zugehoerigen Meldung.
    Danach zurueckgenommen. Wer den Leseaufruf aendert, wiederholt die Probe, statt sie zu glauben.
    """
    pfade = set(verwaltete_pfade(wegwerf_repo))

    assert "specs/decisions/0001-committet.md" in pfade
    assert "specs/decisions/0001-ungetrackt.md" in pfade, "--others fehlt im Leseaufruf"
    assert "specs/decisions/0001-ignoriert.md" not in pfade, (
        "--exclude-standard fehlt im Leseaufruf"
    )

    befunde = dubletten_befunde(dokumente_je_verzeichnis(pfade))

    assert len(befunde) == 1
    assert "2-fach vergeben" in befunde[0]
    assert "specs/decisions/0001-ungetrackt.md" in befunde[0]
    assert "0001-ignoriert" not in befunde[0]
