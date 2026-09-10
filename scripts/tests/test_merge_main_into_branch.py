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

**Der tragende Test ist
`test_nach_dem_abgleich_zeigt_origin_main_head_nur_die_dateien_des_branches`, und er traegt seine
Gegenprobe im selben Lauf** (ADR 0075, Spec 0365): Dieselbe Messung ueber die
**alte** Basis (`main...HEAD`) liefert nachweislich die zwischenzeitlich auf `main` entstandene
Datei mit - genau der Grund, aus dem die acht Prosa-Fundstellen der Review-Phase mitwandern
mussten. Ohne diese zweite Haelfte belegte der Test nur, dass eine Liste nicht leer ist. Zur
selben Zusage gehoert `git merge-base --is-ancestor refs/remotes/origin/main HEAD` → `0`: Ohne
sie bliebe der schmale Diff auch dann gruen, wenn gar nichts uebernommen wurde (der veraltete
lokale `main` gemerged statt `origin/main` - die naheliegende Halbumsetzung).

**Zwei Fixture-Bauformen (Spec 0365).** Neben dem Einzel-Checkout gibt es den
**Zwei-Arbeitsbaum-Spielplatz**: Haupt-Checkout auf `main`, verbundener Arbeitsbaum
(`git worktree add`) auf dem Feature-Branch, das Skript laeuft im verbundenen. Das ist die
Regellage der Hintergrund-Laeufe, nicht ihr Sonderfall. Ueber beide Bauformen laeuft der
**Ausgangs-Kern** (`0`/`10`/`20`/Fehlerfamilie), weil der Arbeitsbaum genau zwei Dinge veraendert
- die Aufloesbarkeit von Refs und die Lage des Git-Verzeichnisses - und beide fallen
ausschliesslich an diesen Ausgaengen an. Der lange Rest bleibt einlaeufig; die
Vorbedingungs-Parametrisierung bleibt am Einzel-Checkout (`main` auszuchecken ist im verbundenen
Arbeitsbaum unmoeglich und erzeugte einen Fixture-Fehlschlag, den ein Leser fuer einen Befund
hielte).

**Im verbundenen Arbeitsbaum ist `.git` eine Datei.** `MERGE_HEAD`/`MERGE_MSG` liegen unter
`…/haupt/.git/worktrees/<name>/`. Jeder Zugriff darauf laeuft deshalb ueber
`git rev-parse --absolute-git-dir`, jeder Zugriff auf die Hooks ueber
`git rev-parse --git-common-dir` - **zwei verschiedene Helfer, nicht einer**: Hooks sind
gemeinsam, Zustandsdateien nicht.

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

# Wortgleich mit der Zeile im Skript. Sie steht hier ein zweites Mal, weil ein Pruefer den
# Wortlaut festhalten muss, um ihn pruefen zu koennen; `scripts/tests/` ist deshalb aus dem
# Suchraum der Einmaligkeitspruefung ausgenommen (siehe test_main_abgleich_verdrahtung.py).
MERGE_NACHRICHT = "chore: Stand von main in den Feature-Branch übernehmen"

ZWEIG = "feature/0338-abgleich"
MINDEST_GIT_VERSION = (2, 32)
ZEITGRENZE_SEKUNDEN = 120

# Voll qualifiziert, und das ist keine Stilfrage: Gemessen loest `git rev-parse origin/main` bei
# einem gleichnamigen lokalen Branch auf **diesen** auf - nur mit einer Warnung auf stderr. Ein
# Test, der unqualifiziert misst, prueft dann einen anderen Ref als das Skript.
TRACKING_REF = "refs/remotes/origin/main"
HAUPT_REF = "refs/heads/main"
ALTE_VERGLEICHSBASIS = HAUPT_REF

_CHECKOUT_NACH_MAIN = re.compile(r"^checkout: moving from .* to main$")

# Die beiden Lagen, in denen `git merge` ohne Konfliktpfad scheitert, sind fuer den Leser der
# Meldung verschieden - einmal wurde ein begonnener Merge zurueckgenommen, einmal hat nie einer
# begonnen. Geprueft wird nur dieser eine unterscheidende Halbsatz, nicht der ganze Wortlaut.
MELDUNG_RUECKNAHME = "zurueckgenommen"
MELDUNG_KEIN_MERGE_BEGONNEN = "ohne einen Merge zu beginnen"

# Der Ausgang "umgeschrieben" wird ab Spec 0365 **gemessen** statt aus einem Fetch-Fehlschlag
# geraten; die Meldung nennt deshalb genau diese eine Ursache statt der frueheren drei.
MELDUNG_UMGESCHRIEBEN = "umgeschrieben"


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


EINZEL = "einzel"
ZWEI_ARBEITSBAEUME = "zwei_arbeitsbaeume"
BAUFORMEN = (EINZEL, ZWEI_ARBEITSBAEUME)


@dataclass(frozen=True)
class Spielplatz:
    """Ein Wegwerf-Repositorium mit barem `origin` und einem zweiten Klon zur `main`-Pflege.

    `haupt` ist der Haupt-Checkout, `arbeit` das Verzeichnis, in dem das Skript laeuft. In der
    Bauform `einzel` sind beide dasselbe Verzeichnis; in der Bauform `zwei_arbeitsbaeume` haelt
    `haupt` den Branch `main` ausgecheckt und `arbeit` ist ein verbundener Arbeitsbaum auf dem
    Feature-Branch - die Regellage der Hintergrund-Laeufe.
    """

    wurzel: Path
    haupt: Path
    arbeit: Path
    origin: Path
    pflege: Path
    env: dict[str, str]
    bauform: str

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


def baue_spielplatz(wurzel: Path, bauform: str = EINZEL) -> Spielplatz:
    """Bares `origin` mit `main`, ein Haupt-Checkout, ein Pflegeklon - in einer der zwei Bauformen.

    `einzel`: Der Haupt-Checkout ist zugleich das Arbeitsverzeichnis und steht auf dem
    Feature-Branch. `zwei_arbeitsbaeume`: Der Haupt-Checkout bleibt auf `main` stehen, der
    Feature-Branch liegt in einem verbundenen Arbeitsbaum daneben - genau die Lage, in der
    `git fetch origin main:main` gemessen mit Exit 128 verweigert (ADR 0075, Messpunkt 1).
    """
    assert bauform in BAUFORMEN, f"unbekannte Bauform: {bauform}"
    wurzel.mkdir(parents=True, exist_ok=True)
    env = basis_env(wurzel)
    haupt = wurzel / "haupt"
    spielplatz = Spielplatz(
        wurzel=wurzel,
        haupt=haupt,
        arbeit=haupt if bauform == EINZEL else wurzel / "arbeit",
        origin=wurzel / "origin.git",
        pflege=wurzel / "pflege",
        env=env,
        bauform=bauform,
    )

    spielplatz.git(wurzel, "init", "--quiet", "--bare", "-b", "main", str(spielplatz.origin))
    spielplatz.git(wurzel, "init", "--quiet", "-b", "main", str(haupt))

    schreibe(haupt, "gemeinsam.txt", "Zeile aus dem Ausgangsstand\n")
    schreibe(haupt, "liesmich.md", "# Wegwerf-Repositorium\n")
    spielplatz.git(haupt, "add", "-A")
    spielplatz.git(haupt, "commit", "--quiet", "-m", "chore: Ausgangsstand")
    spielplatz.git(haupt, "remote", "add", "origin", str(spielplatz.origin))
    spielplatz.git(haupt, "push", "--quiet", "origin", "main")
    spielplatz.git(wurzel, "clone", "--quiet", str(spielplatz.origin), str(spielplatz.pflege))

    if bauform == EINZEL:
        spielplatz.git(haupt, "checkout", "--quiet", "-b", ZWEIG)
    else:
        spielplatz.git(haupt, "branch", ZWEIG)
        spielplatz.git(haupt, "worktree", "add", "--quiet", str(spielplatz.arbeit), ZWEIG)
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
    """Saemtliche Refs des baren `origin` - nicht nur `main` (AK 7, Spec 0338)."""
    return spielplatz.ausgabe(
        spielplatz.origin, "for-each-ref", "--format=%(refname) %(objectname)"
    )


def head_reflog(spielplatz: Spielplatz) -> list[str]:
    return spielplatz.ausgabe(spielplatz.arbeit, "reflog", "show", "HEAD", "--format=%gs").split(
        "\n"
    )


def main_wurde_ausgecheckt(spielplatz: Spielplatz) -> bool:
    return any(_CHECKOUT_NACH_MAIN.match(eintrag.strip()) for eintrag in head_reflog(spielplatz))


def branch_diff(spielplatz: Spielplatz, basis: str = TRACKING_REF) -> list[str]:
    """`git diff --name-only <basis>...HEAD` - die Form, an der die Review-Phase haengt.

    Vorgabe ist ab Spec 0365 der **Tracking-Ref**. Die alte Basis (`refs/heads/main`) bleibt als
    Parameter erreichbar, weil die tragende Gegenprobe genau sie im selben Lauf misst: Sie liefert
    nach dem Abgleich nachweislich die zwischenzeitlich auf `main` entstandene Datei mit.
    """
    ausgabe = spielplatz.ausgabe(spielplatz.arbeit, "diff", "--name-only", f"{basis}...HEAD")
    return sorted(zeile for zeile in ausgabe.split("\n") if zeile)


def git_verzeichnis(spielplatz: Spielplatz) -> Path:
    """Das Git-Verzeichnis des Arbeitsbaums - **nicht** `arbeit / ".git"`.

    Im verbundenen Arbeitsbaum ist `.git` eine Datei, und `MERGE_HEAD`/`MERGE_MSG` liegen unter
    `…/haupt/.git/worktrees/<name>/`. Ein Test, der stur `arbeit / ".git" / "MERGE_HEAD"` liest,
    prueft dort die Abwesenheit einer Datei, die dort nie liegen koennte - und ist gruen, ohne
    etwas zu messen.
    """
    return Path(spielplatz.ausgabe(spielplatz.arbeit, "rev-parse", "--absolute-git-dir"))


def gemeinsames_git_verzeichnis(spielplatz: Spielplatz) -> Path:
    """Das **gemeinsame** Git-Verzeichnis - der Ort der Hooks, und ein anderer als oben.

    `--absolute-git-dir` zeigt im verbundenen Arbeitsbaum auf dessen eigenes Zustandsverzeichnis,
    `--git-common-dir` auf das geteilte. Hooks liegen im geteilten; ein dort abgelegter
    `pre-merge-commit` wirkt auch fuer den verbundenen Arbeitsbaum.

    `--git-common-dir` liefert im Einzel-Checkout gemessen den **relativen** Pfad `.git`; er wird
    deshalb gegen das Arbeitsverzeichnis aufgeloest, nie gegen das des Testprozesses.
    """
    roh = Path(spielplatz.ausgabe(spielplatz.arbeit, "rev-parse", "--git-common-dir"))
    return roh if roh.is_absolute() else (spielplatz.arbeit / roh).resolve()


def merge_head(spielplatz: Spielplatz) -> Path:
    return git_verzeichnis(spielplatz) / "MERGE_HEAD"


def merge_msg(spielplatz: Spielplatz) -> Path:
    return git_verzeichnis(spielplatz) / "MERGE_MSG"


@dataclass(frozen=True)
class Momentaufnahme:
    head: str
    zweig: str
    status: str
    commit_anzahl: str
    main_ref: str
    origin_refs: str | None


def momentaufnahme(spielplatz: Spielplatz) -> Momentaufnahme:
    """Der Zustand des Arbeitsbaums samt `refs/heads/main` - **ohne** den Tracking-Ref.

    `refs/heads/main` gehoert hinein, weil das Skript ihn nie mehr anfasst (AK 8 der
    Spec 0365);
    `refs/remotes/origin/main` gehoert ausdruecklich **nicht** hinein - der bewegt sich
    planmaessig, und eine Gleichheitszusage darauf machte jeden gelungenen Abgleich rot.
    """
    return Momentaufnahme(
        head=spielplatz.ausgabe(spielplatz.arbeit, "rev-parse", "HEAD"),
        zweig=spielplatz.ausgabe(spielplatz.arbeit, "branch", "--show-current"),
        status=spielplatz.ausgabe(spielplatz.arbeit, "status", "--porcelain"),
        commit_anzahl=spielplatz.ausgabe(spielplatz.arbeit, "rev-list", "--count", "HEAD"),
        main_ref=spielplatz.ausgabe(spielplatz.arbeit, "rev-parse", HAUPT_REF),
        origin_refs=origin_refs(spielplatz) if spielplatz.origin.is_dir() else None,
    )


@dataclass(frozen=True)
class HauptZustand:
    """AK 8 (Spec 0365): was der Abgleich am Haupt-Checkout anrichtet - eigener Gegenstand."""

    main_ref: str
    head: str
    status: str


def haupt_zustand(spielplatz: Spielplatz) -> HauptZustand:
    return HauptZustand(
        main_ref=spielplatz.ausgabe(spielplatz.haupt, "rev-parse", HAUPT_REF),
        head=spielplatz.ausgabe(spielplatz.haupt, "rev-parse", "HEAD"),
        status=spielplatz.ausgabe(spielplatz.haupt, "status", "--porcelain"),
    )


def tracking_stand(spielplatz: Spielplatz) -> str:
    return spielplatz.ausgabe(spielplatz.arbeit, "rev-parse", TRACKING_REF)


@pytest.fixture
def fabrik(tmp_path: Path) -> Iterator[Callable[..., Spielplatz]]:
    """Baut beliebig viele unabhaengige Spielplaetze - manche Gegenprobe braucht einen zweiten."""

    def _baue(name: str = "standard", bauform: str = EINZEL) -> Spielplatz:
        return baue_spielplatz(tmp_path / name, bauform)

    yield _baue


@pytest.fixture
def spielplatz(fabrik: Callable[..., Spielplatz]) -> Spielplatz:
    return fabrik("standard")


@pytest.fixture
def zwei_arbeitsbaeume(fabrik: Callable[..., Spielplatz]) -> Spielplatz:
    """Die Regellage der Hintergrund-Laeufe: Haupt-Checkout auf `main`, Arbeit daneben."""
    return fabrik("zwei-arbeitsbaeume", ZWEI_ARBEITSBAEUME)


@pytest.fixture(params=BAUFORMEN, ids=BAUFORMEN)
def kern_spielplatz(
    request: pytest.FixtureRequest, fabrik: Callable[..., Spielplatz]
) -> Spielplatz:
    """Der Ausgangs-Kern (`0`/`10`/`20`/Fehlerfamilie) laeuft ueber **beide** Bauformen.

    AK 1 der Spec 0365 verlangt aus dem Arbeitsbaum heraus denselben Ausgang und denselben
    Zustand des Feature-Branches wie aus dem Haupt-Checkout heraus.
    """
    bauform = str(request.param)
    return fabrik(f"kern-{bauform}", bauform)


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


def test_die_fixture_baut_ein_isoliertes_repositorium(kern_spielplatz: Spielplatz) -> None:
    """Gegenprobe zur Fixture selbst: falscher Vorgabe-Branch faellt sonst nirgends auf."""
    spielplatz = kern_spielplatz
    assert spielplatz.ausgabe(spielplatz.arbeit, "branch", "--show-current") == ZWEIG
    assert spielplatz.ausgabe(spielplatz.arbeit, "rev-parse", "--abbrev-ref", HAUPT_REF) == "main"
    toplevel = Path(spielplatz.ausgabe(spielplatz.arbeit, "rev-parse", "--show-toplevel"))
    assert toplevel.resolve() == spielplatz.arbeit.resolve()
    assert branch_diff(spielplatz) == ["feature.txt"]


def test_die_zweite_bauform_haelt_main_im_haupt_checkout_ausgecheckt(
    zwei_arbeitsbaeume: Spielplatz,
) -> None:
    """Ohne diese Zusicherung ist der Zwei-Arbeitsbaum-Spielplatz nur ein zweites Verzeichnis."""
    spielplatz = zwei_arbeitsbaeume

    assert spielplatz.arbeit != spielplatz.haupt
    assert spielplatz.ausgabe(spielplatz.haupt, "branch", "--show-current") == "main"
    assert spielplatz.ausgabe(spielplatz.arbeit, "branch", "--show-current") == ZWEIG
    assert (spielplatz.arbeit / ".git").is_file(), (
        "Im verbundenen Arbeitsbaum ist `.git` eine Datei. Ist sie hier ein Verzeichnis, ist "
        "die Fixture kein verbundener Arbeitsbaum, und jede Zusage dieser Bauform ist leer."
    )
    assert git_verzeichnis(spielplatz) != gemeinsames_git_verzeichnis(spielplatz), (
        "Zustandsverzeichnis und gemeinsames Git-Verzeichnis fallen hier zusammen - dann sind "
        "die beiden Helfer austauschbar und der Test darueber ist bedeutungslos."
    )


def test_gegenprobe_die_alte_refspec_scheitert_im_verbundenen_arbeitsbaum(
    zwei_arbeitsbaeume: Spielplatz,
) -> None:
    """Der Beleg, dass die Fixture ueberhaupt die Lage aus Issue #365 herstellt (AK 6, Spec 0365).

    Ohne diese Gegenprobe belegen die Kern-Tests der zweiten Bauform nur, dass irgendein
    Repositorium funktioniert. Gemessen (ADR 0075, Messpunkt 1) verweigert git die alte Refspec
    mit Exit 128, sobald `refs/heads/main` in *irgendeinem* Arbeitsbaum ausgecheckt ist.
    """
    spielplatz = zwei_arbeitsbaeume
    main_laeuft_weiter(spielplatz)
    main_vorher = spielplatz.ausgabe(spielplatz.arbeit, "rev-parse", HAUPT_REF)

    ergebnis = _lauf(
        spielplatz.arbeit, ["git", "fetch", "--quiet", "origin", "main:main"], spielplatz.env
    )

    assert ergebnis.returncode == 128, (
        f"'git fetch origin main:main' endete mit {ergebnis.returncode} statt 128. Die Fixture "
        "stellt die Lage aus Issue #365 nicht her, und die Kern-Tests der zweiten Bauform "
        "belegen dann nur, dass irgendein Repositorium funktioniert."
    )
    assert spielplatz.ausgabe(spielplatz.arbeit, "rev-parse", HAUPT_REF) == main_vorher


def test_die_neue_refspec_laeuft_in_derselben_lage_durch(zwei_arbeitsbaeume: Spielplatz) -> None:
    """Die zweite Haelfte der Gegenprobe: nicht das Repositorium ist kaputt, die Refspec war es."""
    spielplatz = zwei_arbeitsbaeume
    main_laeuft_weiter(spielplatz)
    main_vorher = spielplatz.ausgabe(spielplatz.arbeit, "rev-parse", HAUPT_REF)

    ergebnis = _lauf(
        spielplatz.arbeit,
        ["git", "fetch", "--quiet", "origin", f"+refs/heads/main:{TRACKING_REF}"],
        spielplatz.env,
    )

    assert ergebnis.returncode == 0, ergebnis.stderr
    assert spielplatz.ausgabe(spielplatz.arbeit, "rev-parse", HAUPT_REF) == main_vorher
    assert haupt_zustand(spielplatz).status == ""


# --- Ausgang 0: No-Op -------------------------------------------------------------------------


def test_no_op_meldet_nichts_und_aendert_nichts(kern_spielplatz: Spielplatz) -> None:
    """AK 2/AK 4 (Spec 0365): `origin/main` Vorfahre → Exit 0, **stdout/stderr leer**."""
    spielplatz = kern_spielplatz
    vorher = momentaufnahme(spielplatz)

    ergebnis = spielplatz.skript()

    assert ergebnis.returncode == EXIT_ENTHALTEN, ergebnis.stderr
    assert ergebnis.stdout == "", f"stdout nicht leer: {ergebnis.stdout!r}"
    assert ergebnis.stderr == "", (
        f"stderr nicht leer: {ergebnis.stderr!r}. 'Keine Meldung' (AK 2 der Spec 0365) "
        "verlangt ein --quiet am "
        "fetch, der seinen Fortschritt sonst nach stderr schreibt."
    )
    assert momentaufnahme(spielplatz) == vorher
    assert not merge_head(spielplatz).exists()


def test_no_op_bleibt_still_auch_wenn_der_fetch_den_tracking_ref_vorspult(
    spielplatz: Spielplatz,
) -> None:
    """Der No-Op schweigt auch dann, wenn der fetch wirklich einen Ref vorspult (AK 2, Spec 0365).

    Der naheliegende No-Op-Test darueber prueft diese Zusage nur halb: Steht `main` still,
    transportiert der fetch nichts und schwiege selbst ohne jede Massnahme. Hier liegt der Stand
    von `main` bereits im Branch (ueber einen anderen lokalen Ref hereingeholt), waehrend der
    Tracking-Ref hinterherhinkt - der fetch spult ihn wirklich vor. Gemessen (2026-09-08)
    schreibt `git fetch` **jedes** Ref-Update nach stderr, auch ein rein lokales ohne
    Objekttransfer; ohne Gegenmassnahme im Skript ist AK 2 (Spec 0365) hier verletzt.

    **Der Vorlauf holt ueber den Pfad des baren `origin`, nicht ueber den Remote-Namen.** Ueber
    den Namen feuert die konfigurierte `remote.origin.fetch` opportunistisch mit und zieht
    `refs/remotes/origin/main` gleich mit hoch (ADR 0075, Messpunkt 6) - der Tracking-Ref waere
    dann schon aktuell, und dieser Test verloere **still** seinen Gegenstand.

    Welche der beiden Massnahmen es ist - `--quiet` oder die Umleitung nach `/dev/null` - kann
    dieser Test nicht unterscheiden; beide erzeugen dieselbe Beobachtung. Dass das von AK 2 der
    Spec 0365 ausdruecklich verlangte `--quiet` am fetch steht, ist eine Texteigenschaft und
    wird deshalb in `test_main_abgleich_verdrahtung.py` festgehalten.
    """
    main_laeuft_weiter(spielplatz)
    spielplatz.git(
        spielplatz.arbeit,
        "fetch",
        "--quiet",
        str(spielplatz.origin),
        "refs/heads/main:refs/heads/uebernommen",
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
    tracking_vorher = tracking_stand(spielplatz)
    vorher = momentaufnahme(spielplatz)

    ergebnis = spielplatz.skript()

    assert ergebnis.returncode == EXIT_ENTHALTEN, ergebnis.stderr
    assert (ergebnis.stdout, ergebnis.stderr) == ("", ""), (
        "Der fetch hat hier wirklich einen Ref vorgespult - ungebremst steht sein Fortschritt "
        "damit auf stderr, und AK 2 (Spec 0365, 'keine Meldung') ist verletzt."
    )
    assert momentaufnahme(spielplatz) == vorher
    assert tracking_stand(spielplatz) != tracking_vorher, (
        "Der fetch hat den Tracking-Ref nicht vorgespult - dann prueft dieser Test das --quiet "
        "nicht, sondern nur einen zweiten stillen No-Op."
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
    kern_spielplatz: Spielplatz,
) -> None:
    """AK 1 (Spec 0365), pruefbare Fassung: der alte Kopf ist erster Elternteil des neuen.

    Der **zweite** Elternteil wird gegen den Tracking-Ref geprueft, nicht gegen `refs/heads/main`:
    Der bleibt ab Spec 0365 auf dem alten Stand stehen, und ein Vergleich gegen ihn waere in
    genau dem Fall gruen, der hier ausgeschlossen werden soll (der veraltete lokale `main`
    gemerged statt `origin/main`).
    """
    spielplatz = kern_spielplatz
    main_laeuft_weiter(spielplatz)
    vorher = momentaufnahme(spielplatz)

    ergebnis = spielplatz.skript()

    assert ergebnis.returncode == EXIT_UEBERNOMMEN, ergebnis.stderr
    nachher = momentaufnahme(spielplatz)
    assert nachher.head != vorher.head
    assert spielplatz.ausgabe(spielplatz.arbeit, "rev-parse", "HEAD^1") == vorher.head
    assert spielplatz.ausgabe(spielplatz.arbeit, "rev-parse", "HEAD^2") == tracking_stand(
        spielplatz
    )
    assert nachher.status == ""
    assert nachher.zweig == ZWEIG
    assert nachher.main_ref == vorher.main_ref, (
        "`refs/heads/main` hat sich bewegt. Das Skript fasst ihn nie mehr an (AK 8, Spec 0365)."
    )
    assert spielplatz.ausgabe(spielplatz.arbeit, "log", "-1", "--format=%B").strip() == (
        MERGE_NACHRICHT
    )


def test_der_alte_kopf_bleibt_vorfahre_kein_commit_wird_umgeschrieben(
    spielplatz: Spielplatz,
) -> None:
    """AK 4 (Spec 0338): kein Commit-Hash aendert sich - Review-Threads bleiben verankert."""
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


def test_nach_dem_abgleich_zeigt_origin_main_head_nur_die_dateien_des_branches(
    kern_spielplatz: Spielplatz,
) -> None:
    """AK 3 (Spec 0365), der tragende Regressionstest - mit seiner Gegenprobe **im selben Lauf**.

    Acht Stellen der Review-Phase vergleichen ab Spec 0365 mit `git diff origin/main...HEAD`.
    Geprueft wird deshalb dreierlei nebeneinander: `origin/main` ist Vorfahre von `HEAD` (ohne
    diese Haelfte bliebe der schmale Diff auch dann gruen, wenn gar nichts uebernommen wurde),
    die neue Basis listet exakt die Branch-Dateien, und dieselbe Messung ueber die **alte** Basis
    liefert die zwischenzeitlich auf `main` entstandene Datei mit. Der dritte Punkt ist die
    Gegenprobe: Er belegt in einem Zug, dass die neue Assertion Zaehne hat *und* warum die acht
    Prosa-Fundstellen mitwandern mussten.
    """
    spielplatz = kern_spielplatz
    main_laeuft_weiter(spielplatz)

    assert spielplatz.skript().returncode == EXIT_UEBERNOMMEN

    assert (
        _lauf(
            spielplatz.arbeit,
            ["git", "merge-base", "--is-ancestor", TRACKING_REF, "HEAD"],
            spielplatz.env,
        ).returncode
        == 0
    ), (
        f"{TRACKING_REF} ist kein Vorfahre von HEAD - es wurde nichts uebernommen. Ohne diese "
        "Haelfte waere ein schmaler Diff auch dann gruen, wenn der veraltete lokale main "
        "gemerged wurde statt origin/main."
    )
    assert branch_diff(spielplatz) == ["feature.txt"], (
        "Der Review-Diff zeigt fremde Dateien. Gemerged wurde nicht der Tracking-Ref."
    )
    assert branch_diff(spielplatz, ALTE_VERGLEICHSBASIS) == ["auf-main.txt", "feature.txt"], (
        "Die **alte** Vergleichsbasis liefert hier dieselbe Liste wie die neue. Dann misst der "
        "Test darueber nichts: Genau dieser Unterschied ist der Grund, aus dem die acht "
        "Prosa-Fundstellen der Review-Phase auf 'origin/main...HEAD' umgestellt wurden."
    )


def test_branch_vollstaendig_in_main_enthalten_bekommt_trotzdem_einen_merge_commit(
    spielplatz: Spielplatz,
) -> None:
    """`--no-ff`: Ohne es spulte der Feature-Branch auf `main` vor und leerte den Pull Request.

    Verglichen wird gegen den **Tracking-Ref**. Gegen `refs/heads/main` waere die Zusage ab Spec
    0365 trivial gruen (der Ref bewegt sich nie mehr), und `--no-ff` pruefte nichts mehr.
    """
    spielplatz.git(spielplatz.arbeit, "push", "--quiet", "origin", "HEAD:main")
    main_laeuft_weiter(spielplatz)
    vorher = momentaufnahme(spielplatz)

    ergebnis = spielplatz.skript()

    assert ergebnis.returncode == EXIT_UEBERNOMMEN, ergebnis.stderr
    assert spielplatz.ausgabe(spielplatz.arbeit, "rev-parse", "HEAD^1") == vorher.head
    assert spielplatz.ausgabe(spielplatz.arbeit, "rev-parse", "HEAD") != tracking_stand(
        spielplatz
    )


def test_unversionierte_dateien_blockieren_den_abgleich_nicht(spielplatz: Spielplatz) -> None:
    """AK 10 (Spec 0338), letzter Satz: Ein Entwicklungslauf hat fast immer Streudateien."""
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
def test_konflikt_meldet_genau_die_konfliktpfade(kern_spielplatz: Spielplatz, art: str) -> None:
    """AK 5 (Spec 0338), Skript-Haelfte: Exit 20, `MERGE_HEAD` da, stdout = nur Pfade."""
    spielplatz = kern_spielplatz
    erwartet = konflikt_vorbereiten(spielplatz, art)
    vorher = momentaufnahme(spielplatz)

    ergebnis = spielplatz.skript()

    assert ergebnis.returncode == EXIT_KONFLIKT, ergebnis.stderr
    assert ergebnis.stdout.splitlines() == erwartet
    assert ergebnis.stdout.endswith("\n")
    assert ergebnis.stderr == "", (
        f"stderr nicht leer: {ergebnis.stderr!r}. Bei Exit 20 gehen Konfliktpfade auf stdout, "
        "nie die rohe Ausgabe von 'git merge' (Sicherheitskonzept, Bedrohung 3)."
    )
    assert merge_head(spielplatz).is_file()
    assert momentaufnahme(spielplatz).head == vorher.head
    assert momentaufnahme(spielplatz).main_ref == vorher.main_ref
    assert origin_refs(spielplatz) == vorher.origin_refs


def test_konfliktpfade_sind_repo_relativ_auch_aus_einem_unterverzeichnis(
    spielplatz: Spielplatz,
) -> None:
    """AK 5 (Spec 0338): 'repo-relativ'. Ohne Gegenmassnahme entscheidet darueber die Konfiguration.

    `diff.relative` schaltet die Ausgabe auf 'relativ zum Arbeitsverzeichnis' um. Ein so
    konfiguriertes Repositorium meldete `datei.txt` statt `unter/tiefer/datei.txt`, und der
    Folgeauftrag legte sein `git add` auf einen Pfad, den es vom Wurzelverzeichnis aus nicht
    gibt.
    """
    unterverzeichnis = spielplatz.arbeit / "unter" / "tiefer"
    unterverzeichnis.mkdir(parents=True)
    auf_feature(
        spielplatz,
        "feat: tief liegende Datei",
        lambda ort: schreibe(ort / "unter" / "tiefer", "datei.txt", "Ausgangsstand\n"),
    )
    spielplatz.git(spielplatz.arbeit, "push", "--quiet", "origin", "HEAD:main")
    auf_main(
        spielplatz,
        "feat: tief liegende Datei auf main geaendert",
        lambda ort: schreibe(ort / "unter" / "tiefer", "datei.txt", "Fassung von main\n"),
    )
    auf_feature(
        spielplatz,
        "feat: tief liegende Datei im Branch geaendert",
        lambda ort: schreibe(ort / "unter" / "tiefer", "datei.txt", "Fassung des Branches\n"),
    )
    spielplatz.git(spielplatz.arbeit, "config", "diff.relative", "true")

    ergebnis = _lauf(unterverzeichnis, [str(SKRIPT)], spielplatz.env)

    assert ergebnis.returncode == EXIT_KONFLIKT, ergebnis.stderr
    assert ergebnis.stdout.splitlines() == ["unter/tiefer/datei.txt"]


def test_ein_konfliktpfad_mit_umlaut_wird_unverfremdet_ausgegeben(
    spielplatz: Spielplatz,
) -> None:
    """Ohne Gegenmassnahme zitiert git den Pfad oktal (`"gem\\303\\244ss.txt"`)."""
    name = "gemäß.txt"
    auf_feature(
        spielplatz,
        "feat: Datei mit Umlaut",
        lambda ort: schreibe(ort, name, "Ausgangsstand\n"),
    )
    spielplatz.git(spielplatz.arbeit, "push", "--quiet", "origin", "HEAD:main")
    auf_main(
        spielplatz,
        "feat: Umlautdatei auf main geaendert",
        lambda ort: schreibe(ort, name, "Fassung von main\n"),
    )
    auf_feature(
        spielplatz,
        "feat: Umlautdatei im Branch geaendert",
        lambda ort: schreibe(ort, name, "Fassung des Branches\n"),
    )

    ergebnis = spielplatz.skript()

    assert ergebnis.returncode == EXIT_KONFLIKT, ergebnis.stderr
    assert ergebnis.stdout.splitlines() == [name]


def test_bei_konflikt_liegt_die_feste_nachricht_in_merge_msg(spielplatz: Spielplatz) -> None:
    konflikt_vorbereiten(spielplatz, "modify/modify")

    assert spielplatz.skript().returncode == EXIT_KONFLIKT

    nachricht = merge_msg(spielplatz).read_text(encoding="utf-8")
    assert nachricht.splitlines()[0] == MERGE_NACHRICHT


def test_der_dokumentierte_abschlussbefehl_erzeugt_genau_eine_zeile(
    spielplatz: Spielplatz,
) -> None:
    """Der in `developer.md` dokumentierte Weg wird ausgefuehrt (AK 8, Spec 0338)."""
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
    fabrik: Callable[..., Spielplatz],
) -> None:
    """Gegenprobe: Die Zusage aus AK 8 (Spec 0338) haengt am Flag, nicht an der Absicht."""
    spielplatz = fabrik("ohne-strip")
    konfliktpfade = konflikt_vorbereiten(spielplatz, "modify/modify")
    assert spielplatz.skript().returncode == EXIT_KONFLIKT

    schreibe(spielplatz.arbeit, "gemeinsam.txt", "Aufgeloeste Fassung\n")
    spielplatz.git(spielplatz.arbeit, "add", *konfliktpfade)
    spielplatz.git(spielplatz.arbeit, "commit", "--quiet", "--no-edit")

    nachricht = spielplatz.ausgabe(spielplatz.arbeit, "log", "-1", "--format=%B").strip()
    assert len(nachricht.splitlines()) > 1
    assert "Conflicts" in nachricht


def test_merge_abort_stellt_den_ausgangszustand_her(zwei_arbeitsbaeume: Spielplatz) -> None:
    """AK 6 (Spec 0338) und AK 8 (Spec 0365), skriptseitig pruefbare Haelfte.

    Der Tracking-Ref bleibt nach dem Abbruch auf dem geholten Stand stehen. Das ist unschaedlich
    und wird hier nachgerechnet statt geglaubt: Die Merge-Basis zwischen dem fortgeschriebenen
    `origin/main` und `HEAD` ist unveraendert der Abzweigpunkt, also liefert
    `git diff origin/main...HEAD` dieselbe Liste wie vor dem Lauf.
    """
    spielplatz = zwei_arbeitsbaeume
    konflikt_vorbereiten(spielplatz, "modify/modify")
    vorher = momentaufnahme(spielplatz)
    haupt_vorher = haupt_zustand(spielplatz)
    diff_vorher = branch_diff(spielplatz)

    assert spielplatz.skript().returncode == EXIT_KONFLIKT
    spielplatz.git(spielplatz.arbeit, "merge", "--abort")

    nachher = momentaufnahme(spielplatz)
    assert nachher.head == vorher.head
    assert nachher.status == ""
    assert nachher.zweig == vorher.zweig
    assert nachher.main_ref == vorher.main_ref
    assert branch_diff(spielplatz) == diff_vorher, (
        "Die Merge-Basis hat sich verschoben. Der Tracking-Ref bleibt nach dem Abbruch auf dem "
        "geholten Stand - unschaedlich, weil die Merge-Basis der Abzweigpunkt bleibt."
    )
    assert not merge_head(spielplatz).exists()
    assert haupt_zustand(spielplatz) == haupt_vorher, (
        "AK 8 (Spec 0365): Der Haupt-Checkout ist auch nach dem Abbruch unberuehrt."
    )


# --- Fehlerfamilie ----------------------------------------------------------------------------


def test_merge_scheitert_ohne_konflikt_endet_in_der_fehlerfamilie(
    kern_spielplatz: Spielplatz,
) -> None:
    """AK 11 (Spec 0338): 'Merge-Exit ungleich 0' ist nicht 'Konflikt' (Hook nachgestellt).

    Ein `pre-merge-commit`-Hook laesst `git merge` mit Exit 1 enden, `MERGE_HEAD` **existiert**,
    und es gibt **null** Pfade im Konfliktzustand. Wer das auf 20 abbildet, schickt den
    `developer` Konfliktmarker suchen, die es nicht gibt.

    Der Hook liegt unter `--git-common-dir`, nicht unter `--absolute-git-dir`: Hooks sind im
    verbundenen Arbeitsbaum gemeinsam, Zustandsdateien nicht. Am falschen Ort abgelegt liefe der
    Merge einfach durch, und der Test waere gruen, ohne seinen Gegenstand herzustellen.
    """
    spielplatz = kern_spielplatz
    main_laeuft_weiter(spielplatz)
    hook = gemeinsames_git_verzeichnis(spielplatz) / "hooks" / "pre-merge-commit"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    vorher = momentaufnahme(spielplatz)

    ergebnis = spielplatz.skript()

    assert ergebnis.returncode not in BEKANNTE_AUSGAENGE, (
        f"Exit {ergebnis.returncode}: Der Merge ist gescheitert, ohne einen Pfad im "
        "Konfliktzustand zu hinterlassen - das ist die Fehlerfamilie, nicht Ausgang 20."
    )
    assert ergebnis.stdout == ""
    assert MELDUNG_RUECKNAHME in ergebnis.stderr, (
        "Hier hat ein Merge tatsaechlich begonnen und wurde zurueckgenommen - die Meldung soll "
        f"das sagen: {ergebnis.stderr!r}"
    )
    nachher = momentaufnahme(spielplatz)
    assert nachher.head == vorher.head
    assert nachher.status == ""
    assert nachher.main_ref == vorher.main_ref
    assert not merge_head(spielplatz).exists()


def test_eine_kollidierende_unversionierte_datei_meldet_keine_ruecknahme(
    spielplatz: Spielplatz,
) -> None:
    """Die andere Haelfte von AK 10 (Spec 0338) - und der Zweig, auf dem ihre Begruendung ruht.

    "Unversionierte Dateien blockieren nicht" gilt, *weil* git bei einer echten Kollision von
    sich aus verweigert. Am Bestand gemessen (2026-09-08): `git merge` endet mit Rueckgabe 2,
    **ohne** einen Merge begonnen zu haben - `MERGE_HEAD` entsteht nie, und ein `git merge
    --abort` scheitert mit "There is no merge to abort". Eine Meldung, die hier eine Ruecknahme
    behauptet, beschreibt eine Handlung, die nicht stattgefunden hat; sie ist der Text, den
    `ship-feature` bei AK 6 (Spec 0338) unveraendert an Daniel weitergibt.
    """
    auf_main(
        spielplatz,
        "feat: neue Datei auf main",
        lambda ort: schreibe(ort, "kollision.txt", "Fassung von main\n"),
    )
    schreibe(spielplatz.arbeit, "kollision.txt", "unversionierte Streudatei\n")
    vorher = momentaufnahme(spielplatz)

    ergebnis = spielplatz.skript()

    assert ergebnis.returncode not in BEKANNTE_AUSGAENGE, (
        f"Exit {ergebnis.returncode}: git hat den Merge verweigert, ohne ihn zu beginnen - das "
        "ist die Fehlerfamilie."
    )
    assert ergebnis.stdout == ""
    assert not merge_head(spielplatz).exists()
    assert momentaufnahme(spielplatz) == vorher
    assert (spielplatz.arbeit / "kollision.txt").read_text(
        encoding="utf-8"
    ) == "unversionierte Streudatei\n"
    assert MELDUNG_KEIN_MERGE_BEGONNEN in ergebnis.stderr, (
        f"Die Meldung benennt die Lage nicht: {ergebnis.stderr!r}"
    )
    assert MELDUNG_RUECKNAHME not in ergebnis.stderr, (
        "Die Meldung behauptet eine Ruecknahme, die nicht stattgefunden hat: hier hat nie ein "
        f"Merge begonnen ({ergebnis.stderr!r})."
    )


def git_shim(
    verzeichnis: Path, unterbefehl: str, rueckgabe: int, meldung: str = ""
) -> Path:
    """Legt ein `git` an, das genau einen Unterbefehl mit fester Rueckgabe scheitern laesst.

    Der einzige Weg, die gemessene Rueckgabe `128` von `git merge-base --is-ancestor`
    (unbekanntes Objekt/kaputtes Repositorium) reproduzierbar herzustellen: Ein von Hand
    zerstoertes Objekt repariert `git fetch` im selben Lauf wieder (am Bestand nachgemessen,
    2026-09-08 - der fetch laedt das fehlende Objekt nach und meldet danach sauber `1`).
    Alles ausser dem einen Unterbefehl laeuft unveraendert durch das echte git.

    `meldung` stellt die **rohe git-Ausgabe auf stderr** nach, die das echte git im 128-Fall
    schreibt. Ohne sie liesse sich nicht messen, ob die auswertende Zeile ihre Ausgabe wirklich
    verschluckt - der Shim schwiege von sich aus, und der Test waere aus dem falschen Grund
    gruen.
    """
    echtes_git = shutil.which("git")
    assert echtes_git is not None
    verzeichnis.mkdir(parents=True, exist_ok=True)
    shim = verzeichnis / "git"
    ausgabe = f'  printf \'%s\\n\' "{meldung}" >&2\n' if meldung else ""
    shim.write_text(
        f'#!/bin/sh\nif [ "$1" = "{unterbefehl}" ]; then\n{ausgabe}  exit {rueckgabe}\nfi\n'
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


ROHE_GIT_MELDUNG = "fatal: Not a valid object name refs/remotes/origin/main"


@pytest.mark.parametrize("tracking_ref_vorhanden", [True, False], ids=["mit_vorher", "ohne_vorher"])
def test_keine_rohe_git_ausgabe_auf_dem_meldungskanal(
    spielplatz: Spielplatz, tracking_ref_vorhanden: bool
) -> None:
    """Sicherheitskonzept, Bedrohung 3: stderr traegt ausschliesslich selbst erzeugten Text.

    `ship-feature` uebernimmt diesen Kanal unveraendert in den Chat-Bericht und in eine
    `SendMessage`. Eine rohe git-Zeile dort ist nicht nur haesslich - in einer Umgebung mit
    credential-behaftetem Remote waere sie der Weg, auf dem ein Token nach draussen gerät.
    Beide Parametrisierungen treffen eine andere der beiden Rechnungen: mit gemerktem
    Vorher-Stand die Umschreib-Pruefung, ohne ihn die No-Op-Rechnung.
    """
    main_laeuft_weiter(spielplatz)
    if not tracking_ref_vorhanden:
        spielplatz.git(spielplatz.arbeit, "update-ref", "-d", TRACKING_REF)
    env = dict(spielplatz.env)
    shim = git_shim(spielplatz.wurzel / "shim", "merge-base", 128, ROHE_GIT_MELDUNG)
    env["PATH"] = f"{shim}{os.pathsep}{env['PATH']}"

    ergebnis = _lauf(spielplatz.arbeit, [str(SKRIPT)], env)

    assert ergebnis.returncode not in BEKANNTE_AUSGAENGE, ergebnis.stdout
    assert ROHE_GIT_MELDUNG not in ergebnis.stderr, (
        "Die rohe git-Ausgabe steht auf dem Meldungskanal. Die auswertende Zeile verschluckt "
        f"ihre Ausgabe nicht: {ergebnis.stderr!r}"
    )
    assert "fatal" not in ergebnis.stderr.lower()
    assert ergebnis.stderr.startswith("merge-main-into-branch: ")
    assert "128" in ergebnis.stderr
    assert ergebnis.stdout == ""


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


def _main_umgeschrieben(spielplatz: Spielplatz) -> None:
    """`main` auf `origin` wurde umgeschrieben, nachdem der Tracking-Ref regulaer geholt war.

    Der regulaere Vorlauf ist Teil des Falls, nicht Beiwerk: Ohne einen Vorher-Stand des
    Tracking-Refs hat das Skript nichts zu vergleichen und laeuft (richtigerweise) durch. Erst
    ein gemerkter Stand macht das Umschreiben messbar.
    """
    main_laeuft_weiter(spielplatz)
    spielplatz.git(
        spielplatz.arbeit, "fetch", "--quiet", "origin", f"+refs/heads/main:{TRACKING_REF}"
    )
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
    ("main_umgeschrieben", _main_umgeschrieben),
)


@pytest.mark.parametrize(
    ("name", "vorbereiten"), VORBEDINGUNGEN, ids=[eintrag[0] for eintrag in VORBEDINGUNGEN]
)
def test_verletzte_vorbedingung_bricht_ab_und_begruendet_es(
    spielplatz: Spielplatz, name: str, vorbereiten: Callable[[Spielplatz], None]
) -> None:
    """AK 10 (Spec 0338): Exit ausserhalb {0, 10, 20}, Zustand unveraendert, Begruendung auf stderr.

    Bewusst **nur** am Einzel-Checkout, nicht ueber beide Bauformen: `main` selbst auszuchecken
    ist im verbundenen Arbeitsbaum unmoeglich (gemessen Exit 128, "wird bereits von
    Arbeitsverzeichnis in … verwendet"). Diese Parametrisierung stumpf zu verdoppeln erzeugte
    einen Fixture-Fehlschlag, den ein Leser fuer einen Befund hielte.
    """
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
    assert not merge_head(spielplatz).exists()


# --- Die drei neuen Pflichtfaelle (Spec 0365): fail-open oder falsch eskaliert ----------------


def test_bei_umgeschriebenem_main_nennt_die_meldung_genau_diese_eine_ursache(
    spielplatz: Spielplatz,
) -> None:
    """Gemessen statt aus einem Fehlschlag geraten (ADR 0075, Messpunkt 5).

    Mit `+` laeuft der Fetch durch (Exit 0) und bewegt den Tracking-Ref; erst
    `git merge-base --is-ancestor <vorher> <nachher>` macht das Umschreiben sichtbar (Rueckgabe
    1). Der Preis der `+`-Form - im Abbruchfall steht der Tracking-Ref bereits auf dem
    umgeschriebenen Stand - wird hier als Zusage gemessen, nicht nur in der ADR zugegeben.
    """
    _main_umgeschrieben(spielplatz)
    tracking_vorher = tracking_stand(spielplatz)
    vorher = momentaufnahme(spielplatz)

    ergebnis = spielplatz.skript()

    assert ergebnis.returncode not in BEKANNTE_AUSGAENGE, ergebnis.stdout
    assert ergebnis.stdout == ""
    assert MELDUNG_UMGESCHRIEBEN in ergebnis.stderr, (
        "Die Meldung benennt die eine gemessene Ursache nicht. Sie darf hier gerade nicht mehr "
        f"drei moegliche Ursachen aufzaehlen: {ergebnis.stderr!r}"
    )
    assert "fatal" not in ergebnis.stderr.lower(), (
        "Rohe git-Ausgabe auf dem Meldungskanal (Sicherheitskonzept, Bedrohung 3): Die neuen "
        f"Pruefungen muessen ihre Ausgabe verschlucken. {ergebnis.stderr!r}"
    )
    assert momentaufnahme(spielplatz) == vorher
    assert tracking_stand(spielplatz) != tracking_vorher, (
        "Der Tracking-Ref hat sich nicht bewegt - dann misst dieser Test nicht die "
        "Umschreib-Pruefung, sondern einen gescheiterten Fetch."
    )


def test_gegenprobe_dieselbe_refspec_ohne_plus_scheitert_stumm(spielplatz: Spielplatz) -> None:
    """Die Begruendung fuer das `+`: ohne es Exit 1, Ref unveraendert - und wegen `--quiet` stumm.

    Genau diese Stummheit ist der Grund, warum die Umschreib-Pruefung im Skript selbst gerechnet
    wird, statt sich auf den Fehlschlag des Fetch zu verlassen.
    """
    _main_umgeschrieben(spielplatz)
    tracking_vorher = tracking_stand(spielplatz)

    ergebnis = _lauf(
        spielplatz.arbeit,
        ["git", "fetch", "--quiet", "origin", f"refs/heads/main:{TRACKING_REF}"],
        spielplatz.env,
    )

    assert ergebnis.returncode == 1
    assert (ergebnis.stdout, ergebnis.stderr) == ("", "")
    assert tracking_stand(spielplatz) == tracking_vorher


def test_ohne_vorhandenen_tracking_ref_laeuft_der_abgleich_regulaer_durch(
    spielplatz: Spielplatz,
) -> None:
    """Frischer Klon: **kein** Vorher-Stand heisst 'keine Messung', nicht 'Vorbedingung verletzt'.

    Gemessen liefert `git merge-base --is-ancestor "" <ref>` Rueckgabe 128. Ein ungepruefter
    leerer Wert machte damit jeden frischen Klon zu einem falschen Exit 30 - genau die Sorte
    Fehlmeldung, gegen die diese Story geschrieben ist.
    """
    main_laeuft_weiter(spielplatz)
    spielplatz.git(spielplatz.arbeit, "update-ref", "-d", TRACKING_REF)
    assert (
        _lauf(
            spielplatz.arbeit,
            ["git", "rev-parse", "--verify", "--quiet", TRACKING_REF],
            spielplatz.env,
        ).returncode
        != 0
    ), "Der Tracking-Ref existiert noch - dann stellt dieser Test seinen Gegenstand nicht her."

    ergebnis = spielplatz.skript()

    assert ergebnis.returncode == EXIT_UEBERNOMMEN, (
        f"Exit {ergebnis.returncode} ohne vorhandenen Tracking-Ref: {ergebnis.stderr!r}"
    )
    assert branch_diff(spielplatz) == ["feature.txt"]


def test_ohne_vorhandenen_tracking_ref_bleibt_der_no_op_ein_no_op(spielplatz: Spielplatz) -> None:
    """Dieselbe Lage am anderen Ausgang: Exit 0 bleibt Exit 0, still und ohne Merge."""
    spielplatz.git(spielplatz.arbeit, "update-ref", "-d", TRACKING_REF)

    ergebnis = spielplatz.skript()

    assert ergebnis.returncode == EXIT_ENTHALTEN, ergebnis.stderr
    assert (ergebnis.stdout, ergebnis.stderr) == ("", "")


def test_ein_gleichnamiger_lokaler_branch_kippt_den_ausgang_nicht(spielplatz: Spielplatz) -> None:
    """Bedrohung 2, der eine still falsche Ausgang: unqualifiziert meldete das Skript Exit 0.

    Gemessen loest `git rev-parse origin/main` bei existierendem `refs/heads/origin/main` auf
    **diesen** auf (nur eine Warnung auf stderr), und `merge-base --is-ancestor origin/main HEAD`
    meldete dann `0` - "main ist bereits enthalten" fuer einen Stand, den das Skript nie geholt
    hat. Voll qualifiziert meldet dieselbe Rechnung `1`.
    """
    spielplatz.git(spielplatz.arbeit, "branch", "origin/main", "HEAD")
    lokaler_stand = spielplatz.ausgabe(spielplatz.arbeit, "rev-parse", "refs/heads/origin/main")
    main_laeuft_weiter(spielplatz)

    ergebnis = spielplatz.skript()

    assert ergebnis.returncode == EXIT_UEBERNOMMEN, (
        f"Exit {ergebnis.returncode} statt {EXIT_UEBERNOMMEN}. Ein Exit 0 waere hier der "
        "fail-open-Ausgang: 'main ist bereits enthalten' fuer einen nie geholten Stand. "
        f"{ergebnis.stderr!r}"
    )
    assert branch_diff(spielplatz) == ["feature.txt"]
    assert spielplatz.ausgabe(spielplatz.arbeit, "rev-parse", "refs/heads/origin/main") == (
        lokaler_stand
    ), "Das Skript hat den gleichnamigen lokalen Branch angefasst."
    assert spielplatz.ausgabe(spielplatz.arbeit, "rev-parse", "HEAD^2") == tracking_stand(
        spielplatz
    )


def test_gegenprobe_unqualifiziert_meldete_der_gleichnamige_branch_bereits_enthalten(
    spielplatz: Spielplatz,
) -> None:
    """Die zweite Haelfte: ohne volle Qualifizierung ist die Rechnung nachweislich falsch."""
    spielplatz.git(spielplatz.arbeit, "branch", "origin/main", "HEAD")
    main_laeuft_weiter(spielplatz)
    spielplatz.git(
        spielplatz.arbeit, "fetch", "--quiet", "origin", f"+refs/heads/main:{TRACKING_REF}"
    )

    unqualifiziert = _lauf(
        spielplatz.arbeit,
        ["git", "merge-base", "--is-ancestor", "origin/main", "HEAD"],
        spielplatz.env,
    )
    qualifiziert = _lauf(
        spielplatz.arbeit,
        ["git", "merge-base", "--is-ancestor", TRACKING_REF, "HEAD"],
        spielplatz.env,
    )

    assert unqualifiziert.returncode == 0, (
        "Der unqualifizierte Name loest hier nicht mehr auf den lokalen Branch auf - dann misst "
        "der Test darueber die volle Qualifizierung nicht."
    )
    assert qualifiziert.returncode == 1


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


# --- Einbahnstrasse (AK 7, Spec 0338), nach jedem Ausgang -----------------------------------------


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
    """Einbahnstrasse: saemtliche Refs des `origin`, nicht nur `main` - erfasst auch Fremd-Pushes.

    Dazu ab Spec 0365 `refs/heads/main` in derselben Parametrisierung: Er ist nach **jedem**
    Ausgang unveraendert, weil das Skript ihn nie mehr schreibt (AK 8, Spec 0365).
    """
    erwarteter_ausgang = szenario(spielplatz)
    refs_vorher = origin_refs(spielplatz)
    main_vorher = spielplatz.ausgabe(spielplatz.arbeit, "rev-parse", HAUPT_REF)
    zweig_vorher = spielplatz.ausgabe(spielplatz.arbeit, "branch", "--show-current")

    ergebnis = spielplatz.skript()

    if erwarteter_ausgang >= 0:
        assert ergebnis.returncode == erwarteter_ausgang, ergebnis.stderr
    else:
        assert ergebnis.returncode not in BEKANNTE_AUSGAENGE
    assert origin_refs(spielplatz) == refs_vorher, (
        f"Ausgang '{name}' hat Refs im origin veraendert. Das Skript pusht nie."
    )
    assert spielplatz.ausgabe(spielplatz.arbeit, "rev-parse", HAUPT_REF) == main_vorher, (
        f"Ausgang '{name}' hat 'refs/heads/main' bewegt (AK 8, Spec 0365)."
    )
    assert spielplatz.ausgabe(spielplatz.arbeit, "branch", "--show-current") == zweig_vorher
    assert not main_wurde_ausgecheckt(spielplatz), (
        f"Ausgang '{name}': 'main' wurde ausgecheckt. Das Skript arbeitet ausschliesslich auf "
        "dem bereits ausgecheckten Branch."
    )


@pytest.mark.parametrize(
    ("name", "szenario"), AUSGAENGE, ids=[eintrag[0] for eintrag in AUSGAENGE]
)
def test_der_haupt_checkout_bleibt_nach_jedem_ausgang_unversehrt(
    zwei_arbeitsbaeume: Spielplatz, name: str, szenario: Callable[[Spielplatz], int]
) -> None:
    """AK 8 (Spec 0365): Zusicherung gegen den in ADR 0075 ausgeschlossenen Ausweg.

    Der wandernde Ref allein waere kein sichtbarer Schaden - der Schaden entsteht daran, dass
    Index und Arbeitsbaum des Haupt-Checkouts dabei stehen blieben. Daniel faende dort einen Berg
    vermeintlich geloeschter und geaenderter Dateien in einem Arbeitsverzeichnis, das diesen Lauf
    gar nichts angeht. Geprueft werden deshalb alle drei Groessen zusammen.
    """
    spielplatz = zwei_arbeitsbaeume
    erwarteter_ausgang = szenario(spielplatz)
    vorher = haupt_zustand(spielplatz)

    ergebnis = spielplatz.skript()

    if erwarteter_ausgang >= 0:
        assert ergebnis.returncode == erwarteter_ausgang, ergebnis.stderr
    else:
        assert ergebnis.returncode not in BEKANNTE_AUSGAENGE
    assert haupt_zustand(spielplatz) == vorher, (
        f"Ausgang '{name}' hat den Haupt-Checkout veraendert: {haupt_zustand(spielplatz)} statt "
        f"{vorher}."
    )


def test_das_skript_arbeitet_im_aktuellen_verzeichnis_nicht_im_eigenen_ablageort(
    spielplatz: Spielplatz,
) -> None:
    """AK 7 (Spec 0338), zweiter Satz. Ein `cd $(dirname $0)` merget im echten Repo."""
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
