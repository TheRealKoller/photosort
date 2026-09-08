r"""Verhaltenstests fuer `scripts/merge-main-into-branch.sh` gegen echte temporaere Repositorien.

Geprueft wird ein Bash-Skript mit echter Verzweigung (ADR 0063, Spec 0338): fuenf
Vorbedingungen, eine Entscheidung vor dem eigentlichen Befehl, drei unterscheidbare Ausgaenge
(`0`/`10`/`20`) und eine Fehlerfamilie. Geprueft wird deshalb **Verhalten**, nicht Text: Das
Skript laeuft als Unterprozess mit absolutem Pfad, das Arbeitsverzeichnis ist ein frisch
gebautes temporaeres Repositorium mit einem baren zweiten Repositorium als `origin`. Kein
Netzwerk, kein echtes GitHub, kein `bats-core`/`shunit2` (Testkonzept, Sektion "Bash-Skript mit
echter Verzweigung").

**Umgebungsisolierung - die klassische Falle dieser Testbauart.** Jeder Unterprozess, auch der
des Skripts selbst, bekommt ein vollstaendig gesetztes Environment (`basis_env`):

* `GIT_AUTHOR_*`/`GIT_COMMITTER_*`, weil in CI **keine** Git-Identitaet konfiguriert ist und der
  Merge-Commit im Unterprozess des Skripts entsteht - ohne sie waeren diese Tests lokal gruen
  und in CI rot;
* `GIT_CONFIG_GLOBAL=/dev/null` und `GIT_CONFIG_SYSTEM=/dev/null`, damit nicht Daniels globale
  Konfiguration (`commit.gpgsign`, `merge.*`, `core.autocrlf`, Aliase) mitentscheidet;
* `git init -b main` **explizit** statt `init.defaultBranch` - der Vorgabewert ist
  maschinenabhaengig, und ein `master` in der Fixture liesse jeden Vorbedingungstest aus dem
  falschen Grund gruen werden;
* `GIT_CEILING_DIRECTORIES` auf das Elternverzeichnis der Spielplatz-Wurzel: Sicherheitsnetz,
  falls das Skript sein Ziel je aus dem eigenen Ablageort ableitete oder ein Test mit falschem
  `cwd` liefe - sonst merget er im **echten** PhotoSort-Repositorium;
* `GIT_TERMINAL_PROMPT=0`, `GIT_EDITOR=true` und ein Timeout an jedem Aufruf - ein haengendes
  git ist in CI ein Stundenjob, kein roter Test;
* saemtliche `GIT_*` der aufrufenden Umgebung werden **entfernt**, damit ein stehen gebliebenes
  `GIT_DIR` den Lauf nicht auf ein fremdes Repositorium richtet.

**Locale wird bewusst nicht gesetzt.** Alle Entscheidungen des Skripts fallen an Exit-Codes und
Dateizustaenden (`git merge-base --is-ancestor`, Existenz von `MERGE_HEAD`,
`git diff --diff-filter=U`), nie an Ausgabetexten. Ein `LC_ALL=C` hier wuerde eine
Textabhaengigkeit gerade *verdecken*; der ehrliche Pruefer ist der statische Abwesenheitstest auf
`Already up to date`/`CONFLICT` im Skripttext (siehe `test_main_abgleich_verdrahtung.py`).

**Der tragende Test ist `test_nach_dem_abgleich_zeigt_main_head_nur_die_dateien_des_branches`,
und er zaehlt nur mit seiner Gegenprobe** direkt darunter: Die stellt von Hand den Zustand der
naheliegenden Falschimplementierung her (`git fetch origin` ohne Refspec + `git merge
origin/main`) und weist nach, dass dieselbe Assertion dort rot wird. Ohne diese Haelfte
belegte der Test nur, dass eine Liste nicht leer ist.

Die Git-Mindestversion ist ein eigener Test mit Klartext-Fehlschlag, **kein** `skip` - ein
uebersprungener Prueflauf ist von einem bestandenen nicht zu unterscheiden.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_WURZEL = Path(__file__).parents[2]
SKRIPT = REPO_WURZEL / "scripts" / "merge-main-into-branch.sh"

EXIT_ENTHALTEN = 0
EXIT_UEBERNOMMEN = 10
EXIT_KONFLIKT = 20
BEKANNTE_AUSGAENGE = frozenset({EXIT_ENTHALTEN, EXIT_UEBERNOMMEN, EXIT_KONFLIKT})

# Wortgleich mit der Zeile im Skript. Sie steht hier ein zweites Mal, weil ein Prueferden
# Wortlaut festhalten muss, um ihn pruefen zu koennen; `scripts/tests/` ist deshalb aus dem
# Suchraum der Einmaligkeitspruefung ausgenommen (siehe test_main_abgleich_verdrahtung.py).
MERGE_NACHRICHT = "chore: Stand von main in den Feature-Branch übernehmen"

ZWEIG = "feature/0338-abgleich"
MINDEST_GIT_VERSION = (2, 32)
ZEITGRENZE_SEKUNDEN = 120

_CHECKOUT_NACH_MAIN = re.compile(r"^checkout: moving from .* to main$")


def basis_env(wurzel: Path) -> dict[str, str]:
    """Vollstaendig gesetztes Environment fuer jeden Unterprozess dieses Moduls.

    Ausgangspunkt ist `os.environ` **ohne** jede `GIT_*`-Variable: Alles, was git steuert, wird
    hier gesetzt, nichts geerbt. Locale bleibt bewusst unberuehrt (siehe Modul-Docstring).
    """
    env = {
        name: wert
        for name, wert in os.environ.items()
        if not name.startswith("GIT_") and not name.lower().endswith("_proxy")
    }
    env.update(
        {
            "HOME": str(wurzel),
            "GIT_AUTHOR_NAME": "PhotoSort Test",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "PhotoSort Test",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_CEILING_DIRECTORIES": str(wurzel.parent),
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_EDITOR": "true",
        }
    )
    return env


def _lauf(
    verzeichnis: Path, befehl: list[str], env: Mapping[str, str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        befehl,
        cwd=verzeichnis,
        env=dict(env),
        capture_output=True,
        text=True,
        timeout=ZEITGRENZE_SEKUNDEN,
        check=False,
    )


def schreibe(verzeichnis: Path, name: str, inhalt: str) -> None:
    (verzeichnis / name).write_text(inhalt, encoding="utf-8")


@dataclass(frozen=True)
class Spielplatz:
    """Ein Wegwerf-Repositorium mit barem `origin` und einem zweiten Klon zur `main`-Pflege."""

    wurzel: Path
    arbeit: Path
    origin: Path
    pflege: Path
    env: dict[str, str]

    def git(self, verzeichnis: Path, *args: str) -> subprocess.CompletedProcess[str]:
        ergebnis = _lauf(verzeichnis, ["git", *args], self.env)
        assert ergebnis.returncode == 0, (
            f"Fixture-Aufbau gescheitert: git {' '.join(args)} in {verzeichnis} "
            f"→ {ergebnis.returncode}\n{ergebnis.stderr}"
        )
        return ergebnis

    def ausgabe(self, verzeichnis: Path, *args: str) -> str:
        return self.git(verzeichnis, *args).stdout.strip()

    def skript(self) -> subprocess.CompletedProcess[str]:
        """Das Skript unter Pruefung: absoluter Pfad, cwd ist das temporaere Repositorium."""
        return _lauf(self.arbeit, [str(SKRIPT)], self.env)


def baue_spielplatz(wurzel: Path) -> Spielplatz:
    """Bares `origin` mit `main`, ein Arbeitsklon auf einem Feature-Branch, ein Pflegeklon."""
    wurzel.mkdir(parents=True, exist_ok=True)
    env = basis_env(wurzel)
    spielplatz = Spielplatz(
        wurzel=wurzel,
        arbeit=wurzel / "arbeit",
        origin=wurzel / "origin.git",
        pflege=wurzel / "pflege",
        env=env,
    )

    spielplatz.git(wurzel, "init", "--quiet", "--bare", "-b", "main", str(spielplatz.origin))
    spielplatz.git(wurzel, "init", "--quiet", "-b", "main", str(spielplatz.arbeit))

    schreibe(spielplatz.arbeit, "gemeinsam.txt", "Zeile aus dem Ausgangsstand\n")
    schreibe(spielplatz.arbeit, "liesmich.md", "# Wegwerf-Repositorium\n")
    spielplatz.git(spielplatz.arbeit, "add", "-A")
    spielplatz.git(spielplatz.arbeit, "commit", "--quiet", "-m", "chore: Ausgangsstand")
    spielplatz.git(spielplatz.arbeit, "remote", "add", "origin", str(spielplatz.origin))
    spielplatz.git(spielplatz.arbeit, "push", "--quiet", "origin", "main")
    spielplatz.git(wurzel, "clone", "--quiet", str(spielplatz.origin), str(spielplatz.pflege))

    spielplatz.git(spielplatz.arbeit, "checkout", "--quiet", "-b", ZWEIG)
    schreibe(spielplatz.arbeit, "feature.txt", "Arbeit des Feature-Branches\n")
    spielplatz.git(spielplatz.arbeit, "add", "-A")
    spielplatz.git(spielplatz.arbeit, "commit", "--quiet", "-m", "feat: Feature-Datei")
    return spielplatz


def auf_main(
    spielplatz: Spielplatz, nachricht: str, aenderung: Callable[[Path], None]
) -> None:
    """Laesst `main` im baren `origin` weiterlaufen - ueber den zweiten Klon, nie ueber `arbeit`."""
    spielplatz.git(spielplatz.pflege, "fetch", "--quiet", "origin")
    spielplatz.git(spielplatz.pflege, "checkout", "--quiet", "-B", "main", "origin/main")
    aenderung(spielplatz.pflege)
    spielplatz.git(spielplatz.pflege, "add", "-A")
    spielplatz.git(spielplatz.pflege, "commit", "--quiet", "-m", nachricht)
    spielplatz.git(spielplatz.pflege, "push", "--quiet", "origin", "main")


def auf_feature(
    spielplatz: Spielplatz, nachricht: str, aenderung: Callable[[Path], None]
) -> None:
    aenderung(spielplatz.arbeit)
    spielplatz.git(spielplatz.arbeit, "add", "-A")
    spielplatz.git(spielplatz.arbeit, "commit", "--quiet", "-m", nachricht)


def main_laeuft_weiter(spielplatz: Spielplatz) -> None:
    auf_main(
        spielplatz,
        "feat: Aenderung auf main",
        lambda ort: schreibe(ort, "auf-main.txt", "Zwischenzeitlich auf main entstanden\n"),
    )


def origin_refs(spielplatz: Spielplatz) -> str:
    """Saemtliche Refs des baren `origin` - nicht nur `main` (AK 7)."""
    return spielplatz.ausgabe(
        spielplatz.origin, "for-each-ref", "--format=%(refname) %(objectname)"
    )


def head_reflog(spielplatz: Spielplatz) -> list[str]:
    return spielplatz.ausgabe(spielplatz.arbeit, "reflog", "show", "HEAD", "--format=%gs").split(
        "\n"
    )


def main_wurde_ausgecheckt(spielplatz: Spielplatz) -> bool:
    return any(_CHECKOUT_NACH_MAIN.match(eintrag.strip()) for eintrag in head_reflog(spielplatz))


def branch_diff(spielplatz: Spielplatz) -> list[str]:
    """`git diff --name-only main...HEAD` - die Form, an der die gesamte Review-Phase haengt."""
    ausgabe = spielplatz.ausgabe(spielplatz.arbeit, "diff", "--name-only", "main...HEAD")
    return sorted(zeile for zeile in ausgabe.split("\n") if zeile)


@dataclass(frozen=True)
class Momentaufnahme:
    head: str
    zweig: str
    status: str
    commit_anzahl: str
    origin_refs: str | None


def momentaufnahme(spielplatz: Spielplatz) -> Momentaufnahme:
    return Momentaufnahme(
        head=spielplatz.ausgabe(spielplatz.arbeit, "rev-parse", "HEAD"),
        zweig=spielplatz.ausgabe(spielplatz.arbeit, "branch", "--show-current"),
        status=spielplatz.ausgabe(spielplatz.arbeit, "status", "--porcelain"),
        commit_anzahl=spielplatz.ausgabe(spielplatz.arbeit, "rev-list", "--count", "HEAD"),
        origin_refs=origin_refs(spielplatz) if spielplatz.origin.is_dir() else None,
    )


@pytest.fixture
def fabrik(tmp_path: Path) -> Iterator[Callable[[str], Spielplatz]]:
    """Baut beliebig viele unabhaengige Spielplaetze - die Gegenprobe braucht einen zweiten."""

    def _baue(name: str = "standard") -> Spielplatz:
        return baue_spielplatz(tmp_path / name)

    yield _baue


@pytest.fixture
def spielplatz(fabrik: Callable[[str], Spielplatz]) -> Spielplatz:
    return fabrik("standard")


# --- Umgebung ---------------------------------------------------------------------------------


def test_git_ist_neu_genug_fuer_diese_tests() -> None:
    """Klartext-Fehlschlag statt `skip`: Ein uebersprungener Prueflauf sieht aus wie ein gruener.

    `GIT_CONFIG_GLOBAL`/`GIT_CONFIG_SYSTEM` (die gesamte Isolation dieser Datei) gibt es erst ab
    Git 2.32.
    """
    ausgabe = subprocess.run(
        ["git", "--version"], capture_output=True, text=True, timeout=ZEITGRENZE_SEKUNDEN
    ).stdout
    treffer = re.search(r"(\d+)\.(\d+)", ausgabe)
    assert treffer is not None, f"Git-Version nicht erkennbar aus {ausgabe!r}"

    version = (int(treffer.group(1)), int(treffer.group(2)))
    assert version >= MINDEST_GIT_VERSION, (
        f"Git {version[0]}.{version[1]} ist zu alt: Diese Tests isolieren sich ueber "
        f"GIT_CONFIG_GLOBAL/GIT_CONFIG_SYSTEM (ab Git {MINDEST_GIT_VERSION[0]}."
        f"{MINDEST_GIT_VERSION[1]}). Mit aelterem git entscheidet die Konfiguration der "
        "Maschine mit, und ein gruener Lauf waere eine Aussage ueber sie statt ueber das Skript."
    )


def test_die_fixture_baut_ein_isoliertes_repositorium(spielplatz: Spielplatz) -> None:
    """Gegenprobe zur Fixture selbst: falscher Vorgabe-Branch faellt sonst nirgends auf."""
    assert spielplatz.ausgabe(spielplatz.arbeit, "branch", "--show-current") == ZWEIG
    assert spielplatz.ausgabe(spielplatz.arbeit, "rev-parse", "--abbrev-ref", "main") == "main"
    toplevel = Path(spielplatz.ausgabe(spielplatz.arbeit, "rev-parse", "--show-toplevel"))
    assert toplevel.resolve() == spielplatz.arbeit.resolve()
    assert branch_diff(spielplatz) == ["feature.txt"]


# --- Ausgang 0: No-Op -------------------------------------------------------------------------


def test_no_op_meldet_nichts_und_aendert_nichts(spielplatz: Spielplatz) -> None:
    """AK 3: `main` bereits Vorfahre → Exit 0, kein Merge, **stdout und stderr leer**."""
    vorher = momentaufnahme(spielplatz)

    ergebnis = spielplatz.skript()

    assert ergebnis.returncode == EXIT_ENTHALTEN
    assert ergebnis.stdout == "", f"stdout nicht leer: {ergebnis.stdout!r}"
    assert ergebnis.stderr == "", (
        f"stderr nicht leer: {ergebnis.stderr!r}. 'Keine Meldung' (AK 3) verlangt ein --quiet am "
        "fetch, der seinen Fortschritt sonst nach stderr schreibt."
    )
    assert momentaufnahme(spielplatz) == vorher
    assert not (spielplatz.arbeit / ".git" / "MERGE_HEAD").exists()


def test_no_op_bleibt_still_auch_wenn_der_fetch_den_lokalen_ref_vorspult(
    spielplatz: Spielplatz,
) -> None:
    """Der No-Op schweigt auch dann, wenn der fetch wirklich einen Ref vorspult (AK 3).

    Der naheliegende No-Op-Test unten prueft diese Zusage nur halb: Steht `main` still,
    transportiert der fetch nichts und schwiege selbst ohne jede Massnahme. Hier liegt der Stand
    von `main` bereits im Branch (ueber einen anderen lokalen Ref hereingeholt), waehrend der
    lokale `main`-Ref hinterherhinkt - der fetch spult ihn wirklich vor. Gemessen (2026-09-08)
    schreibt `git fetch` **jedes** Ref-Update nach stderr, auch ein rein lokales ohne
    Objekttransfer; ohne Gegenmassnahme im Skript ist AK 3 hier verletzt.

    Welche der beiden Massnahmen es ist - `--quiet` oder die Umleitung nach `/dev/null` - kann
    dieser Test nicht unterscheiden; beide erzeugen dieselbe Beobachtung. Dass das von AK 3
    ausdruecklich verlangte `--quiet` am fetch steht, ist eine Texteigenschaft und wird deshalb
    in `test_main_abgleich_verdrahtung.py` festgehalten.
    """
    main_laeuft_weiter(spielplatz)
    spielplatz.git(
        spielplatz.arbeit, "fetch", "--quiet", "origin", "main:refs/heads/uebernommen"
    )
    spielplatz.git(
        spielplatz.arbeit,
        "merge",
        "--no-ff",
        "--no-edit",
        "-m",
        "chore: Stand ueber einen anderen Weg uebernommen",
        "uebernommen",
    )
    main_vorher = spielplatz.ausgabe(spielplatz.arbeit, "rev-parse", "main")
    vorher = momentaufnahme(spielplatz)

    ergebnis = spielplatz.skript()

    assert ergebnis.returncode == EXIT_ENTHALTEN, ergebnis.stderr
    assert (ergebnis.stdout, ergebnis.stderr) == ("", ""), (
        "Der fetch hat hier wirklich einen Ref vorgespult - ungebremst steht sein Fortschritt "
        "damit auf stderr, und AK 3 ('keine Meldung') ist verletzt."
    )
    assert momentaufnahme(spielplatz) == vorher
    assert spielplatz.ausgabe(spielplatz.arbeit, "rev-parse", "main") != main_vorher, (
        "Der fetch hat den lokalen main-Ref nicht vorgespult - dann prueft dieser Test das "
        "--quiet nicht, sondern nur einen zweiten stillen No-Op."
    )


def test_zweiter_lauf_direkt_nach_dem_abgleich_ist_ein_no_op(spielplatz: Spielplatz) -> None:
    """Die realistischste Auspraegung: Schritt 6 hat abgeglichen, Schritt 8 ruft erneut auf."""
    main_laeuft_weiter(spielplatz)
    assert spielplatz.skript().returncode == EXIT_UEBERNOMMEN
    nach_dem_abgleich = momentaufnahme(spielplatz)

    ergebnis = spielplatz.skript()

    assert ergebnis.returncode == EXIT_ENTHALTEN
    assert (ergebnis.stdout, ergebnis.stderr) == ("", "")
    assert momentaufnahme(spielplatz) == nach_dem_abgleich


# --- Ausgang 10: sauberer Merge ---------------------------------------------------------------


def test_sauberer_merge_haengt_genau_einen_commit_mit_zwei_eltern_an(
    spielplatz: Spielplatz,
) -> None:
    """AK 4 in seiner pruefbaren Fassung: der alte Kopf ist erster Elternteil des neuen."""
    main_laeuft_weiter(spielplatz)
    vorher = momentaufnahme(spielplatz)

    ergebnis = spielplatz.skript()

    assert ergebnis.returncode == EXIT_UEBERNOMMEN, ergebnis.stderr
    nachher = momentaufnahme(spielplatz)
    assert nachher.head != vorher.head
    assert spielplatz.ausgabe(spielplatz.arbeit, "rev-parse", "HEAD^1") == vorher.head
    assert spielplatz.ausgabe(spielplatz.arbeit, "rev-parse", "HEAD^2") == spielplatz.ausgabe(
        spielplatz.arbeit, "rev-parse", "main"
    )
    assert nachher.status == ""
    assert nachher.zweig == ZWEIG
    assert spielplatz.ausgabe(spielplatz.arbeit, "log", "-1", "--format=%B").strip() == (
        MERGE_NACHRICHT
    )


def test_der_alte_kopf_bleibt_vorfahre_kein_commit_wird_umgeschrieben(
    spielplatz: Spielplatz,
) -> None:
    """AK 4: kein bestehender Commit-Hash aendert sich - Review-Threads bleiben verankert."""
    main_laeuft_weiter(spielplatz)
    alte_commits = spielplatz.ausgabe(spielplatz.arbeit, "rev-list", "HEAD").split("\n")

    assert spielplatz.skript().returncode == EXIT_UEBERNOMMEN

    neue_commits = spielplatz.ausgabe(spielplatz.arbeit, "rev-list", "HEAD").split("\n")
    assert set(alte_commits) <= set(neue_commits)
    assert (
        spielplatz.git(
            spielplatz.arbeit, "merge-base", "--is-ancestor", alte_commits[0], "HEAD"
        ).returncode
        == 0
    )


def test_nach_dem_abgleich_zeigt_main_head_nur_die_dateien_des_branches(
    spielplatz: Spielplatz,
) -> None:
    """AK 7b, der tragende Regressionstest - er zaehlt nur mit der Gegenprobe darunter.

    Sechs Stellen der Review-Phase vergleichen mit `git diff main...HEAD`. Die Drei-Punkt-Form
    bildet die Merge-Basis aus dem **lokalen** `main`-Ref; bliebe der stehen, bekaeme jede
    Review-Perspektive die zwischenzeitlich auf `main` entstandenen Dateien vorgelegt.
    """
    main_laeuft_weiter(spielplatz)

    assert spielplatz.skript().returncode == EXIT_UEBERNOMMEN

    assert spielplatz.ausgabe(spielplatz.arbeit, "rev-parse", "main") == spielplatz.ausgabe(
        spielplatz.arbeit, "rev-parse", "origin/main"
    )
    assert branch_diff(spielplatz) == ["feature.txt"], (
        "Der Review-Diff zeigt fremde Dateien. Der lokale main-Ref wurde nicht mitgezogen - "
        "aus 'git fetch origin main:main' ist vermutlich 'git fetch origin' geworden."
    )


def test_gegenprobe_ohne_refspec_zeigt_der_review_diff_fremde_dateien(
    fabrik: Callable[[str], Spielplatz],
) -> None:
    """Die zweite Haelfte des Tests darueber: die Falschimplementierung von Hand nachgestellt.

    `git fetch origin` (ohne Refspec) + `git merge origin/main` fuehrt zum selben Baum und zum
    selben Exit-Code, laesst aber den lokalen `main`-Ref stehen. Faerbt diese Assertion hier
    nicht rot, prueft der Test darueber nur, dass eine Liste nicht leer ist.
    """
    spielplatz = fabrik("gegenprobe")
    main_laeuft_weiter(spielplatz)

    spielplatz.git(spielplatz.arbeit, "fetch", "--quiet", "origin")
    spielplatz.git(
        spielplatz.arbeit, "merge", "--no-ff", "--no-edit", "-m", MERGE_NACHRICHT, "origin/main"
    )

    assert spielplatz.ausgabe(spielplatz.arbeit, "rev-parse", "main") != spielplatz.ausgabe(
        spielplatz.arbeit, "rev-parse", "origin/main"
    )
    assert branch_diff(spielplatz) == ["auf-main.txt", "feature.txt"]


def test_branch_vollstaendig_in_main_enthalten_bekommt_trotzdem_einen_merge_commit(
    spielplatz: Spielplatz,
) -> None:
    """`--no-ff`: Ohne es spulte der Feature-Branch auf `main` vor und leerte den Pull Request."""
    spielplatz.git(spielplatz.arbeit, "push", "--quiet", "origin", "HEAD:main")
    main_laeuft_weiter(spielplatz)
    vorher = momentaufnahme(spielplatz)

    ergebnis = spielplatz.skript()

    assert ergebnis.returncode == EXIT_UEBERNOMMEN, ergebnis.stderr
    assert spielplatz.ausgabe(spielplatz.arbeit, "rev-parse", "HEAD^1") == vorher.head
    assert spielplatz.ausgabe(spielplatz.arbeit, "rev-parse", "HEAD") != spielplatz.ausgabe(
        spielplatz.arbeit, "rev-parse", "main"
    )


def test_unversionierte_dateien_blockieren_den_abgleich_nicht(spielplatz: Spielplatz) -> None:
    """AK 10, letzter Satz: Ein Entwicklungslauf hat fast immer Streudateien."""
    main_laeuft_weiter(spielplatz)
    schreibe(spielplatz.arbeit, "streudatei.tmp", "unversioniert\n")

    ergebnis = spielplatz.skript()

    assert ergebnis.returncode == EXIT_UEBERNOMMEN, ergebnis.stderr
    assert (spielplatz.arbeit / "streudatei.tmp").is_file()
    assert spielplatz.ausgabe(spielplatz.arbeit, "status", "--porcelain") == "?? streudatei.tmp"


# --- Ausgang 20: Konflikt ---------------------------------------------------------------------


def konflikt_vorbereiten(spielplatz: Spielplatz, art: str) -> list[str]:
    """Stellt eine der drei Konfliktklassen her und liefert die erwarteten Konfliktpfade."""
    if art == "modify/modify":
        auf_main(
            spielplatz,
            "feat: Zeile auf main geaendert",
            lambda ort: schreibe(ort, "gemeinsam.txt", "Fassung von main\n"),
        )
        auf_feature(
            spielplatz,
            "feat: Zeile im Branch geaendert",
            lambda ort: schreibe(ort, "gemeinsam.txt", "Fassung des Branches\n"),
        )
        return ["gemeinsam.txt"]
    if art == "add/add":
        auf_main(
            spielplatz,
            "feat: Datei auf main angelegt",
            lambda ort: schreibe(ort, "neu.txt", "Fassung von main\n"),
        )
        auf_feature(
            spielplatz,
            "feat: Datei im Branch angelegt",
            lambda ort: schreibe(ort, "neu.txt", "Fassung des Branches\n"),
        )
        return ["neu.txt"]
    if art == "delete/modify":
        auf_main(
            spielplatz,
            "refactor: Datei auf main geloescht",
            lambda ort: (ort / "gemeinsam.txt").unlink(),
        )
        auf_feature(
            spielplatz,
            "feat: Zeile im Branch geaendert",
            lambda ort: schreibe(ort, "gemeinsam.txt", "Fassung des Branches\n"),
        )
        return ["gemeinsam.txt"]
    raise ValueError(f"unbekannte Konfliktklasse: {art}")


@pytest.mark.parametrize("art", ["modify/modify", "add/add", "delete/modify"])
def test_konflikt_meldet_genau_die_konfliktpfade(spielplatz: Spielplatz, art: str) -> None:
    """AK 5, Skript-Haelfte: Exit 20, `MERGE_HEAD` da, stdout = Konfliktpfade und sonst nichts."""
    erwartet = konflikt_vorbereiten(spielplatz, art)
    vorher = momentaufnahme(spielplatz)

    ergebnis = spielplatz.skript()

    assert ergebnis.returncode == EXIT_KONFLIKT, ergebnis.stderr
    assert ergebnis.stdout.splitlines() == erwartet
    assert ergebnis.stdout.endswith("\n")
    assert ergebnis.stderr == "", (
        f"stderr nicht leer: {ergebnis.stderr!r}. Bei Exit 20 gehen Konfliktpfade auf stdout, "
        "nie die rohe Ausgabe von 'git merge' (Sicherheitskonzept, Bedrohung 5)."
    )
    assert (spielplatz.arbeit / ".git" / "MERGE_HEAD").is_file()
    assert momentaufnahme(spielplatz).head == vorher.head
    assert origin_refs(spielplatz) == vorher.origin_refs


def test_bei_konflikt_liegt_die_feste_nachricht_in_merge_msg(spielplatz: Spielplatz) -> None:
    konflikt_vorbereiten(spielplatz, "modify/modify")

    assert spielplatz.skript().returncode == EXIT_KONFLIKT

    merge_msg = (spielplatz.arbeit / ".git" / "MERGE_MSG").read_text(encoding="utf-8")
    assert merge_msg.splitlines()[0] == MERGE_NACHRICHT


def test_der_dokumentierte_abschlussbefehl_erzeugt_genau_eine_zeile(
    spielplatz: Spielplatz,
) -> None:
    """Der in `developer.md` dokumentierte Weg wird ausgefuehrt, nicht angenommen (AK 8)."""
    konfliktpfade = konflikt_vorbereiten(spielplatz, "modify/modify")
    assert spielplatz.skript().returncode == EXIT_KONFLIKT

    schreibe(spielplatz.arbeit, "gemeinsam.txt", "Aufgeloeste Fassung\n")
    spielplatz.git(spielplatz.arbeit, "add", *konfliktpfade)
    spielplatz.git(spielplatz.arbeit, "commit", "--quiet", "--no-edit", "--cleanup=strip")

    nachricht = spielplatz.ausgabe(spielplatz.arbeit, "log", "-1", "--format=%B").strip()
    assert nachricht.splitlines() == [MERGE_NACHRICHT]
    assert "Conflicts" not in nachricht
    assert spielplatz.ausgabe(spielplatz.arbeit, "status", "--porcelain") == ""


def test_ohne_cleanup_strip_bliebe_die_konfliktliste_im_commit_body(
    fabrik: Callable[[str], Spielplatz],
) -> None:
    """Gegenprobe zum Test darueber: Die Zusage aus AK 8 haengt am Flag, nicht an der Absicht."""
    spielplatz = fabrik("ohne-strip")
    konfliktpfade = konflikt_vorbereiten(spielplatz, "modify/modify")
    assert spielplatz.skript().returncode == EXIT_KONFLIKT

    schreibe(spielplatz.arbeit, "gemeinsam.txt", "Aufgeloeste Fassung\n")
    spielplatz.git(spielplatz.arbeit, "add", *konfliktpfade)
    spielplatz.git(spielplatz.arbeit, "commit", "--quiet", "--no-edit")

    nachricht = spielplatz.ausgabe(spielplatz.arbeit, "log", "-1", "--format=%B").strip()
    assert len(nachricht.splitlines()) > 1
    assert "Conflicts" in nachricht


def test_merge_abort_stellt_den_ausgangszustand_her(spielplatz: Spielplatz) -> None:
    """AK 6, skriptseitig pruefbare Haelfte."""
    konflikt_vorbereiten(spielplatz, "modify/modify")
    vorher = momentaufnahme(spielplatz)
    diff_vorher = branch_diff(spielplatz)

    assert spielplatz.skript().returncode == EXIT_KONFLIKT
    spielplatz.git(spielplatz.arbeit, "merge", "--abort")

    nachher = momentaufnahme(spielplatz)
    assert nachher.head == vorher.head
    assert nachher.status == ""
    assert nachher.zweig == vorher.zweig
    assert branch_diff(spielplatz) == diff_vorher, (
        "Die Merge-Basis hat sich verschoben. Der lokale main-Ref bleibt nach dem Abbruch "
        "vorgespult - unschaedlich, weil die Merge-Basis der alte main-Stand bleibt."
    )
    assert not (spielplatz.arbeit / ".git" / "MERGE_HEAD").exists()


# --- Fehlerfamilie ----------------------------------------------------------------------------


def test_merge_scheitert_ohne_konflikt_endet_in_der_fehlerfamilie(
    spielplatz: Spielplatz,
) -> None:
    """AK 11: 'Merge-Exit ungleich 0' ist nicht 'Konflikt' (am Bestand mit Hook nachgestellt).

    Ein `pre-merge-commit`-Hook laesst `git merge` mit Exit 1 enden, `MERGE_HEAD` **existiert**,
    und es gibt **null** Pfade im Konfliktzustand. Wer das auf 20 abbildet, schickt den
    `developer` Konfliktmarker suchen, die es nicht gibt.
    """
    main_laeuft_weiter(spielplatz)
    hook = spielplatz.arbeit / ".git" / "hooks" / "pre-merge-commit"
    hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    vorher = momentaufnahme(spielplatz)

    ergebnis = spielplatz.skript()

    assert ergebnis.returncode not in BEKANNTE_AUSGAENGE, (
        f"Exit {ergebnis.returncode}: Der Merge ist gescheitert, ohne einen Pfad im "
        "Konfliktzustand zu hinterlassen - das ist die Fehlerfamilie, nicht Ausgang 20."
    )
    assert ergebnis.stdout == ""
    assert ergebnis.stderr.strip() != ""
    nachher = momentaufnahme(spielplatz)
    assert nachher.head == vorher.head
    assert nachher.status == ""
    assert not (spielplatz.arbeit / ".git" / "MERGE_HEAD").exists()


def git_shim(verzeichnis: Path, unterbefehl: str, rueckgabe: int) -> Path:
    """Legt ein `git` an, das genau einen Unterbefehl mit fester Rueckgabe scheitern laesst.

    Der einzige Weg, die gemessene Rueckgabe `128` von `git merge-base --is-ancestor`
    (unbekanntes Objekt/kaputtes Repositorium) reproduzierbar herzustellen: Ein von Hand
    zerstoertes Objekt repariert `git fetch` im selben Lauf wieder (am Bestand nachgemessen,
    2026-09-08 - der fetch laedt das fehlende Objekt nach und meldet danach sauber `1`).
    Alles ausser dem einen Unterbefehl laeuft unveraendert durch das echte git.
    """
    echtes_git = shutil.which("git")
    assert echtes_git is not None
    verzeichnis.mkdir(parents=True, exist_ok=True)
    shim = verzeichnis / "git"
    shim.write_text(
        f'#!/bin/sh\nif [ "$1" = "{unterbefehl}" ]; then exit {rueckgabe}; fi\n'
        f'exec "{echtes_git}" "$@"\n',
        encoding="utf-8",
    )
    shim.chmod(0o755)
    return verzeichnis


def test_eine_unklare_rueckgabe_von_merge_base_ist_kein_no_op(spielplatz: Spielplatz) -> None:
    """Sicherheitskonzept, Bedrohung 2: still falsch sein kann allein der Ausgang `0`.

    `git merge-base --is-ancestor` liefert gemessen `0` (Vorfahre), `1` (nicht) und `128`
    (unbekanntes Objekt/kaputtes Repositorium). Wird `128` wie `0` behandelt, meldet das Skript
    "main ist bereits enthalten" fuer ein Repositorium, in dem es gar nicht gemessen hat -
    `ship-feature` liefe weiter, pushte, und nichts wuerde rot.
    """
    main_laeuft_weiter(spielplatz)
    vorher = momentaufnahme(spielplatz)
    env = dict(spielplatz.env)
    shim = git_shim(spielplatz.wurzel / "shim", "merge-base", 128)
    env["PATH"] = f"{shim}{os.pathsep}{env['PATH']}"

    ergebnis = _lauf(spielplatz.arbeit, [str(SKRIPT)], env)

    assert ergebnis.returncode not in BEKANNTE_AUSGAENGE, (
        f"Exit {ergebnis.returncode} bei Rueckgabe 128 von 'merge-base --is-ancestor'. Weder "
        "'enthalten' noch 'nicht enthalten' - hier wurde nichts gemessen, und ein Exit 0 waere "
        "genau der eine fail-open-Ausgang aus Bedrohung 2."
    )
    assert "128" in ergebnis.stderr
    assert momentaufnahme(spielplatz) == vorher


def _unsauber_gestagt(spielplatz: Spielplatz) -> None:
    schreibe(spielplatz.arbeit, "gemeinsam.txt", "gestagte Aenderung\n")
    spielplatz.git(spielplatz.arbeit, "add", "gemeinsam.txt")


def _unsauber_ungestagt(spielplatz: Spielplatz) -> None:
    schreibe(spielplatz.arbeit, "gemeinsam.txt", "ungestagte Aenderung\n")


def _main_ausgecheckt(spielplatz: Spielplatz) -> None:
    spielplatz.git(spielplatz.arbeit, "checkout", "--quiet", "main")


def _losgeloester_head(spielplatz: Spielplatz) -> None:
    spielplatz.git(spielplatz.arbeit, "checkout", "--quiet", "--detach")


def _kein_origin(spielplatz: Spielplatz) -> None:
    spielplatz.git(spielplatz.arbeit, "remote", "remove", "origin")


def _fetch_schlaegt_fehl(spielplatz: Spielplatz) -> None:
    shutil.rmtree(spielplatz.origin)


def _origin_ohne_main(spielplatz: Spielplatz) -> None:
    spielplatz.git(spielplatz.origin, "branch", "-m", "main", "haupt")


def _main_nicht_vorspulbar(spielplatz: Spielplatz) -> None:
    main_laeuft_weiter(spielplatz)
    spielplatz.git(spielplatz.arbeit, "fetch", "--quiet", "origin", "main:main")
    spielplatz.git(spielplatz.pflege, "fetch", "--quiet", "origin")
    spielplatz.git(spielplatz.pflege, "checkout", "--quiet", "-B", "main", "origin/main")
    spielplatz.git(spielplatz.pflege, "reset", "--quiet", "--hard", "HEAD~1")
    schreibe(spielplatz.pflege, "umgeschrieben.txt", "main wurde umgeschrieben\n")
    spielplatz.git(spielplatz.pflege, "add", "-A")
    spielplatz.git(spielplatz.pflege, "commit", "--quiet", "-m", "feat: umgeschriebener Stand")
    spielplatz.git(spielplatz.pflege, "push", "--quiet", "--force", "origin", "main")


VORBEDINGUNGEN: tuple[tuple[str, Callable[[Spielplatz], None]], ...] = (
    ("unsauber_gestagt", _unsauber_gestagt),
    ("unsauber_ungestagt", _unsauber_ungestagt),
    ("main_ausgecheckt", _main_ausgecheckt),
    ("losgeloester_head", _losgeloester_head),
    ("kein_origin", _kein_origin),
    ("fetch_schlaegt_fehl", _fetch_schlaegt_fehl),
    ("origin_ohne_main", _origin_ohne_main),
    ("main_nicht_vorspulbar", _main_nicht_vorspulbar),
)


@pytest.mark.parametrize(
    ("name", "vorbereiten"), VORBEDINGUNGEN, ids=[eintrag[0] for eintrag in VORBEDINGUNGEN]
)
def test_verletzte_vorbedingung_bricht_ab_und_begruendet_es(
    spielplatz: Spielplatz, name: str, vorbereiten: Callable[[Spielplatz], None]
) -> None:
    """AK 10: Exit ausserhalb {0, 10, 20}, Zustand unveraendert, Begruendung auf stderr."""
    vorbereiten(spielplatz)
    vorher = momentaufnahme(spielplatz)

    ergebnis = spielplatz.skript()

    assert ergebnis.returncode not in BEKANNTE_AUSGAENGE, (
        f"Vorbedingung '{name}' fuehrte zu Exit {ergebnis.returncode} - ein bekannter Ausgang. "
        "Ein Exit 0 hiesse 'main ist bereits enthalten' fuer ein Repositorium, in dem gar nicht "
        "gemessen wurde (Sicherheitskonzept, Bedrohung 2)."
    )
    assert ergebnis.stderr.strip() != "", f"Vorbedingung '{name}' bricht ohne Begruendung ab."
    assert ergebnis.stdout == ""
    assert momentaufnahme(spielplatz) == vorher
    assert not (spielplatz.arbeit / ".git" / "MERGE_HEAD").exists()


def test_bei_nicht_vorspulbarem_main_bleibt_der_lokale_main_ref_stehen(
    spielplatz: Spielplatz,
) -> None:
    """Genauigkeitskorrektur der ADR: zugesichert ist der **lokale** Ref, nicht `origin/main`."""
    _main_nicht_vorspulbar(spielplatz)
    main_vorher = spielplatz.ausgabe(spielplatz.arbeit, "rev-parse", "main")

    assert spielplatz.skript().returncode not in BEKANNTE_AUSGAENGE

    assert spielplatz.ausgabe(spielplatz.arbeit, "rev-parse", "main") == main_vorher


def test_die_fehlermeldung_nennt_die_remote_url_nicht(spielplatz: Spielplatz) -> None:
    """Bedrohung 5: Ein credential-behafteter Remote waere in einer Fehlermeldung ein Leck."""
    spielplatz.git(
        spielplatz.arbeit,
        "remote",
        "set-url",
        "origin",
        "https://x-access-token:geheim@localhost:1/photosort.git",
    )

    ergebnis = spielplatz.skript()

    assert ergebnis.returncode not in BEKANNTE_AUSGAENGE
    assert "geheim" not in ergebnis.stderr
    assert "geheim" not in ergebnis.stdout
    assert "x-access-token" not in ergebnis.stderr


# --- Einbahnstrasse (AK 7), nach jedem Ausgang -------------------------------------------------


def _szenario_no_op(spielplatz: Spielplatz) -> int:
    return EXIT_ENTHALTEN


def _szenario_merge(spielplatz: Spielplatz) -> int:
    main_laeuft_weiter(spielplatz)
    return EXIT_UEBERNOMMEN


def _szenario_konflikt(spielplatz: Spielplatz) -> int:
    konflikt_vorbereiten(spielplatz, "modify/modify")
    return EXIT_KONFLIKT


def _szenario_fehler(spielplatz: Spielplatz) -> int:
    _unsauber_ungestagt(spielplatz)
    return -1


AUSGAENGE: tuple[tuple[str, Callable[[Spielplatz], int]], ...] = (
    ("no_op", _szenario_no_op),
    ("merge", _szenario_merge),
    ("konflikt", _szenario_konflikt),
    ("fehler", _szenario_fehler),
)


@pytest.mark.parametrize(
    ("name", "szenario"), AUSGAENGE, ids=[eintrag[0] for eintrag in AUSGAENGE]
)
def test_nach_jedem_ausgang_sind_die_origin_refs_unveraendert(
    spielplatz: Spielplatz, name: str, szenario: Callable[[Spielplatz], int]
) -> None:
    """AK 7: saemtliche Refs des `origin`, nicht nur `main` - das erfasst auch Fremd-Pushes."""
    erwarteter_ausgang = szenario(spielplatz)
    refs_vorher = origin_refs(spielplatz)
    zweig_vorher = spielplatz.ausgabe(spielplatz.arbeit, "branch", "--show-current")

    ergebnis = spielplatz.skript()

    if erwarteter_ausgang >= 0:
        assert ergebnis.returncode == erwarteter_ausgang, ergebnis.stderr
    else:
        assert ergebnis.returncode not in BEKANNTE_AUSGAENGE
    assert origin_refs(spielplatz) == refs_vorher, (
        f"Ausgang '{name}' hat Refs im origin veraendert. Das Skript pusht nie (AK 7)."
    )
    assert spielplatz.ausgabe(spielplatz.arbeit, "branch", "--show-current") == zweig_vorher
    assert not main_wurde_ausgecheckt(spielplatz), (
        f"Ausgang '{name}': 'main' wurde ausgecheckt. Das Skript arbeitet ausschliesslich auf "
        "dem bereits ausgecheckten Branch (AK 7)."
    )


def test_das_skript_arbeitet_im_aktuellen_verzeichnis_nicht_im_eigenen_ablageort(
    spielplatz: Spielplatz,
) -> None:
    """AK 7, zweiter Satz. Ein `cd $(dirname $0)` merget im echten PhotoSort-Repositorium."""
    echtes_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_WURZEL,
        capture_output=True,
        text=True,
        timeout=ZEITGRENZE_SEKUNDEN,
        check=True,
    ).stdout.strip()
    main_laeuft_weiter(spielplatz)

    assert spielplatz.skript().returncode == EXIT_UEBERNOMMEN

    danach = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_WURZEL,
        capture_output=True,
        text=True,
        timeout=ZEITGRENZE_SEKUNDEN,
        check=True,
    ).stdout.strip()
    assert danach == echtes_head
    toplevel = Path(spielplatz.ausgabe(spielplatz.arbeit, "rev-parse", "--show-toplevel"))
    assert toplevel.resolve() == spielplatz.arbeit.resolve()
