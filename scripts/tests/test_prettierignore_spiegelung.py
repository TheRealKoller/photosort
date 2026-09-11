r"""Waechter ueber die Spiegelung der `.gitignore`-Eintraege in `/.prettierignore` (K11, Spec 0400).

**Die Zusicherung.** Beide npm-Skripte rufen Prettier mit `--ignore-path ../.prettierignore` auf.
Dieses Flag **ersetzt** Prettiers Vorgabe vollstaendig, statt sie zu ergaenzen (gemessen, ADR 0080
Abschnitt 7) - damit entfaellt die `.gitignore`-Auswertung, und `/.prettierignore` ist die einzige
Ausschlussquelle. Jeder `.gitignore`-Eintrag, der unterhalb von `frontend/` oder `e2e/` greift und
eine von Prettier unterstuetzte Endung treffen kann, muss dort gespiegelt sein - auch jeder
kuenftige.

**Warum das ein Waechter sein muss und keine Konvention.** Das ist die Zusicherung dieser Story,
die **still** bricht. Ein fehlender Eintrag faellt lokal nur als "eine Datei mehr formatiert" auf
und in CI ueberhaupt nicht, weil die betroffenen Verzeichnisse dort zum Pruefzeitpunkt nicht
existieren. Der Schaden ist an einer Stelle konkret vermessen: Ohne `e2e/.auth/` erfasst ein
lokaler `--write`-Lauf aus `e2e/` die Datei `.auth/state.json` mit dem gespeicherten, 30 Tage
gueltigen und nicht widerrufbaren JWT und **schreibt sie neu**; bei einem Parse-Fehler gibt
Prettier zudem einen Code-Frame **mit dem Dateiinhalt** aus.

**Die Erwartung wird abgeleitet, nicht aufgeschrieben** (Entscheidung Daniels, 2026-09-11). Eine
Literalliste waere eine zweite Quelle der Wahrheit: Sie ginge mit dem naechsten `.gitignore`-Eintrag
still auseinander, und genau dagegen tritt dieser Test an. Gelesen werden stattdessen die
verwalteten `.gitignore`-Dateien, und jeder Eintrag, der die beiden Kriterien erfuellt, muss sich
in `/.prettierignore` wiederfinden.

**Die beiden Kriterien - und der Fehler, den sie verhindern.** Ein Eintrag ist
spiegelungspflichtig, wenn er (1) unterhalb von `frontend/` oder `e2e/` greifen kann und (2) eine
von Prettier parsbare Datei treffen kann. Fuer (2) ist die **Verzeichnisfrage** massgeblich, nicht
die Endungsfrage - und das ist die Stelle, an der im Review einmal falsch abgebogen wurde: Ein
Eintrag wie `logs` oder `.idea` sieht nach einer Endung aus, die Prettier nicht kennt, trifft aber
ein *Verzeichnis*, in dem eine `.json` liegen kann. Wer nach Endungen filtert, findet allein
`.vscode/` und haelt die Spiegelung faelschlich fuer vollstaendig. Ein Datei-Glob ist nur dann
spiegelungspflichtig, wenn er den Dateinamen **nicht** nach hinten abschliesst: `*.ntvs*` trifft
`foo.ntvs.json`, waehrend `*.log`, `*.local`, `*.suo`, `*.sln`, `*.sw?`, `.DS_Store` und
`.coverage` das strukturell nicht koennen.

**Zusaetzlich fest zugesichert: die fuenf sicherheitsrelevanten `e2e/`-Verzeichnisse** als
Mindestmenge. Sie haengen nicht an der Ableitung, damit ein Defekt im `.gitignore`-Leser sie nicht
mitreisst - bei ihnen ist der Schaden benennbar, und eine abgeleitete Erwartung, die versehentlich
leer wird, duerfte hier nicht gruen sein.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

REPO_WURZEL = Path(__file__).parents[2]
PRETTIERIGNORE = ".prettierignore"

# Die Baeume, in denen Prettier laeuft. Nur was hier greifen kann, ist spiegelungspflichtig.
PRETTIER_BAEUME = ("frontend", "e2e")

# Mindestmenge, bewusst literal: der Sicherheitsbefund S1. `.auth/state.json` traegt ein 30 Tage
# gueltiges, nicht widerrufbares JWT, die Playwright-Artefakte tragen Traces mit Netzwerkinhalten
# samt Login-Request und localStorage-Zustand.
SICHERHEITSRELEVANTE_VERZEICHNISSE = (
    "e2e/.auth/",
    "e2e/artifacts/",
    "e2e/test-results/",
    "e2e/playwright-report/",
    "e2e/scratch/",
)

# Endungen, fuer die Prettier einen Parser mitbringt. ABGELEITET, nicht gepflegt: Der Datenstand
# wird aus `prettier --support-info` erzeugt und von `frontend/src/prettierSupportInfo.test.ts`
# gegen das tatsaechlich installierte Prettier abgeglichen.
#
# **Warum ein eingecheckter Datenstand und kein Aufruf zur Laufzeit** (Copilot-Finding zu
# PR #409): Der CI-Job `demo-scripts`, in dem dieses Modul laeuft, hat weder Node noch
# node_modules - `prettier --support-info` ist von hier aus nicht erreichbar. Der Job `frontend`
# erreicht es und haelt den Datenstand ehrlich. Beide Jobs laufen bei jedem Pull Request, keine
# Haelfte haengt an einem `skip`.
#
# **Vorher stand hier eine handverlesene Auswahl** mit dem Kommentar "gekuerzt auf die, die in
# einem Artefaktverzeichnis dieses Projekts realistisch auftreten" - 25 von 115 Endungen, es
# fehlten unter anderem `.gql`, `.graphqls`, `.markdown`, `.geojson`, `.htm`, `.pcss`. Das war
# genau die Ermessensentscheidung ueber den "realistischen" Fall, die fuer diese Story
# ausgeschlossen ist, und sie wirkte in die **gefaehrliche** Richtung: Eine zu kurze Liste
# fordert zu WENIG Spiegelung.
_DATENSTAND_PFAD = Path(__file__).parent / "prettier_endungen.json"


def parsbare_endungen() -> tuple[str, ...]:
    if not _DATENSTAND_PFAD.is_file():
        raise ValueError(
            f"{_DATENSTAND_PFAD.name} fehlt. Ohne den Datenstand kann dieses Modul nicht "
            "entscheiden, ob ein Datei-Glob eine parsbare Datei treffen kann - und eine "
            "stillschweigend leere Menge forderte gar keine Spiegelung mehr. Neu erzeugen: "
            "cd frontend && ./node_modules/.bin/prettier --support-info"
        )
    daten = json.loads(_DATENSTAND_PFAD.read_text(encoding="utf-8"))
    endungen = daten.get("extensions")
    if not isinstance(endungen, list) or not endungen:
        raise ValueError(f"{_DATENSTAND_PFAD.name} fuehrt keine Endungen: {endungen!r}")
    return tuple(endungen)


PARSBARE_ENDUNGEN = parsbare_endungen()


# --- Leser -------------------------------------------------------------------------------------


def verwaltete_pfade(wurzel: Path = REPO_WURZEL) -> list[str]:
    ergebnis = subprocess.run(
        ["git", "ls-files", "-z"], cwd=wurzel, capture_output=True, check=True
    )
    return [pfad.decode("utf-8") for pfad in ergebnis.stdout.split(b"\0") if pfad]


def gitignore_dateien(wurzel: Path = REPO_WURZEL) -> dict[str, list[str]]:
    """Pfad -> wirksame Eintraege je verwalteter `.gitignore`. Kommentare und Leerzeilen raus."""
    dateien: dict[str, list[str]] = {}
    for relativ in verwaltete_pfade(wurzel):
        if Path(relativ).name != ".gitignore":
            continue
        eintraege = [
            zeile.strip()
            for zeile in (wurzel / relativ).read_text(encoding="utf-8").splitlines()
            if zeile.strip() and not zeile.strip().startswith("#")
        ]
        dateien[relativ] = eintraege
    return dateien


def prettierignore_eintraege(wurzel: Path = REPO_WURZEL) -> list[str]:
    pfad = wurzel / PRETTIERIGNORE
    if not pfad.is_file():
        raise ValueError(
            f"{PRETTIERIGNORE} fehlt. Ohne sie ist --ignore-path in beiden npm-Skripten ein "
            "Verweis ins Leere, und der Formatierer laeuft ohne jeden Ausschluss."
        )
    return [
        zeile.strip()
        for zeile in pfad.read_text(encoding="utf-8").splitlines()
        if zeile.strip() and not zeile.strip().startswith("#")
    ]


# --- Die Ableitung als reine Funktionen --------------------------------------------------------


def ist_datei_glob(eintrag: str) -> bool:
    """Ein Muster ohne Schraegstrich, das mit `*` beginnt - also auf Dateinamen zielt."""
    return "/" not in eintrag.rstrip("/") and eintrag.startswith("*")


def kann_parsbares_treffen(eintrag: str) -> bool:
    """Kann dieser Eintrag eine von Prettier parsbare Datei erfassen?

    Fuer alles, was ein VERZEICHNIS treffen kann, lautet die Antwort ja - in einem Verzeichnis
    kann jede Endung liegen. Nur bei einem Datei-Glob entscheidet die Form: Schliesst er den
    Namen nach hinten ab (`*.log`), kann keine parsbare Endung mehr folgen; laesst er hinten
    offen (`*.ntvs*`), sehr wohl.
    """
    if not ist_datei_glob(eintrag):
        return True
    if eintrag.endswith("*"):
        return True
    return any(eintrag.endswith(endung) for endung in PARSBARE_ENDUNGEN)


def greift_unter_prettier_baum(eintrag: str, gitignore_pfad: str) -> bool:
    """Kann der Eintrag unterhalb von frontend/ oder e2e/ greifen?

    Drei Faelle, und der mittlere ist der, den ein fluechtiger Blick verfehlt:

    * Die `.gitignore` liegt SELBST in einem Prettier-Baum (`frontend/.gitignore`) - dann greift
      jeder ihrer Eintraege dort.
    * Sie liegt in der Wurzel und der Eintrag traegt einen Schraegstrich nur am Ende oder gar
      keinen (`node_modules/`, `logs`) - solche Muster greifen auf JEDER Ebene, also auch unter
      den beiden Baeumen.
    * Sie liegt in der Wurzel und der Eintrag ist verankert (`e2e/.auth/`, `backend/src/...`) -
      dann greift er nur, wenn er auf einen der Baeume zeigt.
    """
    verzeichnis = str(Path(gitignore_pfad).parent)
    if verzeichnis.split("/")[0] in PRETTIER_BAEUME:
        return True
    if verzeichnis != ".":
        return False
    rumpf = eintrag.rstrip("/").lstrip("!")
    if "/" not in rumpf:
        return True
    return rumpf.split("/")[0] in PRETTIER_BAEUME


def spiegelungspflichtig(dateien: dict[str, list[str]]) -> dict[str, str]:
    """Eintrag -> Herkunftsdatei, fuer jeden Eintrag, der gespiegelt gehoert."""
    if not dateien:
        raise ValueError(
            "0 .gitignore-Dateien im Suchraum: Damit ist die Spiegelung ungeprueft. Ein leerer "
            "Suchraum darf nie als 'nichts zu spiegeln' durchgehen."
        )
    pflichtig: dict[str, str] = {}
    for pfad, eintraege in sorted(dateien.items()):
        for eintrag in eintraege:
            if eintrag.startswith("!"):
                continue  # Wiedereinschluss: gitignore-Semantik laesst ihn unterhalb eines
                # ausgeschlossenen Verzeichnisses ohnehin nicht wirken (nachgemessen).
            if not greift_unter_prettier_baum(eintrag, pfad):
                continue
            if not kann_parsbares_treffen(eintrag):
                continue
            pflichtig.setdefault(_normalisiert(eintrag), pfad)
    return pflichtig


def _normalisiert(eintrag: str) -> str:
    """Vergleichsform: ohne fuehrenden/abschliessenden Schraegstrich und ohne abschliessendes `/*`.

    Drei Schreibweisen meinen fuer diesen Zweck dasselbe, und alle drei kommen im Bestand vor:
    `dist`, `dist/` und `dist/*`. Die Verzeichnisform schliesst mindestens so viel aus wie die
    Sternform - `/.prettierignore` darf also `.vscode/` schreiben, wo `frontend/.gitignore`
    `.vscode/*` sagt. Ohne diese Normalisierung meldete der Test Befunde, die es nicht gibt, und
    der naheliegende Weg, sie loszuwerden, waere eine Ausnahmeliste gewesen.
    """
    rumpf = eintrag.strip()
    if rumpf.endswith("/*"):
        rumpf = rumpf[:-2]
    return rumpf.strip("/")


def _zulaessige_formen(eintrag: str, herkunft: str) -> set[str]:
    """Die Schreibweisen, in denen dieser Eintrag in `/.prettierignore` stehen darf.

    Eine `.gitignore` in einem Unterverzeichnis gilt relativ zu diesem Verzeichnis. Ihr Eintrag
    `dist-ssr` darf in der Wurzeldatei deshalb als `frontend/dist-ssr/` stehen - praeziser als die
    nackte Form und genau das, was der Bestand tut. Die nackte Form bleibt ebenfalls zulaessig:
    Sie greift auf jeder Ebene und schliesst damit mehr aus, nicht weniger.
    """
    formen = {_normalisiert(eintrag)}
    verzeichnis = str(Path(herkunft).parent)
    if verzeichnis != ".":
        formen.add(_normalisiert(f"{verzeichnis}/{eintrag}"))
    return formen


def fehlende_spiegelungen(dateien: dict[str, list[str]], gespiegelt: list[str]) -> list[str]:
    if not gespiegelt:
        raise ValueError(
            f"0 Eintraege in {PRETTIERIGNORE}: Der Formatierer laeuft dann ohne jeden Ausschluss "
            "- ein leerer Ausschluss darf nie als 'alles gespiegelt' durchgehen."
        )
    vorhanden = {_normalisiert(eintrag) for eintrag in gespiegelt}
    return [
        f"{eintrag} (aus {herkunft})"
        for eintrag, herkunft in sorted(spiegelungspflichtig(dateien).items())
        if not (_zulaessige_formen(eintrag, herkunft) & vorhanden)
    ]


# --- 1. Die Ableitung am echten Bestand --------------------------------------------------------


def test_jeder_einschlaegige_gitignore_eintrag_ist_gespiegelt() -> None:
    fehlend = fehlende_spiegelungen(gitignore_dateien(), prettierignore_eintraege())
    assert not fehlend, (
        "Diese .gitignore-Eintraege fehlen in /.prettierignore:\n  "
        + "\n  ".join(fehlend)
        + "\n\n--ignore-path ersetzt Prettiers Vorgabe vollstaendig; was hier fehlt, ist fuer "
        "den Formatierer sichtbar. Ein lokaler `npm run format`-Lauf schreibt solche Dateien um, "
        "und in CI faellt es nicht auf, weil die Verzeichnisse dort nicht existieren."
    )


@pytest.mark.parametrize("verzeichnis", SICHERHEITSRELEVANTE_VERZEICHNISSE)
def test_die_sicherheitsrelevanten_verzeichnisse_sind_fest_zugesichert(verzeichnis: str) -> None:
    """Mindestmenge, unabhaengig von der Ableitung.

    Haengt diese Zusicherung an derselben Ableitung wie alles andere, reisst ein Defekt im
    .gitignore-Leser sie mit - und ausgerechnet die fuenf Verzeichnisse, bei denen der Schaden
    benennbar ist, waeren still ungeprueft.
    """
    vorhanden = {_normalisiert(eintrag) for eintrag in prettierignore_eintraege()}
    assert _normalisiert(verzeichnis) in vorhanden, (
        f"{verzeichnis} fehlt in /.prettierignore. Gemessen: Ohne diesen Eintrag erfasst ein "
        "lokaler Lauf aus e2e/ die Datei .auth/state.json mit dem gespeicherten JWT und schreibt "
        "sie bei --write neu."
    )


# --- 2. Selbstschutz ---------------------------------------------------------------------------


def test_der_gitignore_suchraum_enthaelt_die_bekannten_dateien() -> None:
    """Ohne diese Pruefung koennte die Ableitung gegen eine leere Menge laufen und 'sauber' melden."""
    dateien = gitignore_dateien()
    assert ".gitignore" in dateien, dateien.keys()
    assert "frontend/.gitignore" in dateien, (
        f"frontend/.gitignore fehlt im Suchraum ({list(dateien)}). Genau dort steht der "
        ".vscode/*-Eintrag, dessen Spiegelung dieser Test halten soll."
    )
    for pfad, eintraege in dateien.items():
        assert eintraege, f"{pfad} wurde als leer gelesen - der Leser ist kaputt."


def test_der_endungs_datenstand_ist_vollstaendig_statt_handverlesen() -> None:
    """Selbstschutz gegen den Rueckfall in eine gepflegte Auswahl.

    Die Zahl steht hier als Untergrenze, nicht als Gleichheit: Ein Prettier-Wechsel darf die
    Menge veraendern, ohne diesen Test zu brechen - dafuer ist
    `frontend/src/prettierSupportInfo.test.ts` zustaendig, und der faerbt bei einer Abweichung
    laut rot. Was hier gefangen wird, ist der Rueckfall auf eine Handauswahl (vorher: 25 von 115)
    und ein Leser, der still eine leere Menge liefert.
    """
    assert len(PARSBARE_ENDUNGEN) > 100, (
        f"Nur {len(PARSBARE_ENDUNGEN)} Endungen im Datenstand. Vor dem Copilot-Finding zu "
        "PR #409 standen hier 25 handverlesene von 115 - eine zu kurze Menge fordert zu WENIG "
        "Spiegelung, und genau das ist die gefaehrliche Richtung."
    )
    for endung in (".gql", ".geojson", ".htm", ".markdown", ".pcss"):
        assert endung in PARSBARE_ENDUNGEN, (
            f"{endung} fehlt - sie gehoerte zu den 90, die die fruehere Handauswahl ausliess."
        )


def test_ein_glob_mit_einer_frueher_fehlenden_endung_wird_jetzt_gefordert() -> None:
    """Mutationsprobe zum Copilot-Finding, gegen genau die Luecke von damals.

    `*.gql` ist Copilots eigenes Beispiel. Mit der handverlesenen Menge war `.gql` unbekannt,
    der Glob galt als unbedenklich, und ein `.gitignore`-Eintrag `*.gql*` haette keine
    Spiegelung verlangt.
    """
    for glob in ("*.gql", "*.geojson", "*.markdown"):
        assert _normalisiert(glob) in spiegelungspflichtig({".gitignore": [glob]}), glob


def test_die_ableitung_liefert_eine_nicht_leere_pflichtmenge() -> None:
    """Eine Ableitung, die nichts fordert, ist von einer erfuellten nicht zu unterscheiden."""
    pflichtig = spiegelungspflichtig(gitignore_dateien())
    assert len(pflichtig) >= 5, (
        f"Nur {len(pflichtig)} spiegelungspflichtige Eintraege abgeleitet: {sorted(pflichtig)}. "
        "Dann prueft der Test oben praktisch nichts."
    )


@pytest.mark.parametrize(
    ("funktion", "leeres"),
    [(spiegelungspflichtig, {}), (fehlende_spiegelungen, {})],
)
def test_ein_leerer_suchraum_scheitert_laut_statt_still(funktion: object, leeres: object) -> None:
    with pytest.raises(ValueError, match=r"^0 "):
        if funktion is fehlende_spiegelungen:
            fehlende_spiegelungen({"x": ["a"]}, [])
        else:
            funktion(leeres)  # type: ignore[operator]


# --- 3. Gegenprobe: die Ableitung fordert das Richtige -----------------------------------------


@pytest.mark.parametrize(
    ("pfad", "eintrag", "warum"),
    [
        (".gitignore", "e2e/.auth/", "verankert auf einen Prettier-Baum"),
        (".gitignore", "node_modules/", "ohne Verankerung - greift auf jeder Ebene"),
        (".gitignore", "logs", "Verzeichnis ohne Schraegstrich - der Fall, der uebersehen wird"),
        (".gitignore", ".vscode/", "Punktverzeichnis mit .json darin"),
        (".gitignore", "*.ntvs*", "Datei-Glob, hinten offen - trifft foo.ntvs.json"),
        ("frontend/.gitignore", "dist", "liegt selbst im Prettier-Baum"),
        ("frontend/.gitignore", ".idea", "Verzeichnis, Endung taeuscht"),
        (
            ".gitignore",
            "example-pictures/",
            "Schraegstrich NUR am Ende - greift auf jeder Ebene, also auch "
            "frontend/example-pictures/. Sah beim Schreiben dieses Tests nach einem "
            "Wurzel-Verzeichnis aus und ist keines.",
        ),
        (
            ".gitignore",
            ".DS_Store",
            "nackter Name ohne Schraegstrich: git unterscheidet nicht zwischen Datei und "
            "Verzeichnis, ein Verzeichnis dieses Namens koennte eine .json tragen. Die Regel "
            "bleibt an dieser Stelle bewusst mechanisch, statt 'das ist doch eine Datei' zu "
            "urteilen - dieselbe Entscheidung wie bei der Liste insgesamt.",
        ),
        (
            "frontend/.gitignore",
            "npm-debug.log*",
            "Datei-Glob, hinten offen - trifft npm-debug.log.json, anders als das benachbarte "
            "*.log",
        ),
    ],
)
def test_ein_einschlaegiger_eintrag_wird_gefordert(pfad: str, eintrag: str, warum: str) -> None:
    assert _normalisiert(eintrag) in spiegelungspflichtig({pfad: [eintrag]}), warum


@pytest.mark.parametrize(
    ("pfad", "eintrag", "warum"),
    [
        (".gitignore", "backend/src/photosort/assets/x.onnx", "verankert auf einen fremden Baum"),
        (".gitignore", "design/penpot/ansichten/", "verankert, nicht auf einen Prettier-Baum"),
        (".gitignore", "*.log", "Datei-Glob, hinten abgeschlossen"),
        (".gitignore", "*.local", "dito"),
        (".gitignore", "*.sw?", "dito, Platzhalter aendert die Endung nicht"),
        (".gitignore", "*.suo", "dito"),
        (
            "frontend/.gitignore",
            "!.vscode/extensions.json",
            "Wiedereinschluss, nachgemessen wirkungslos",
        ),
    ],
)
def test_ein_nicht_einschlaegiger_eintrag_wird_nicht_gefordert(
    pfad: str, eintrag: str, warum: str
) -> None:
    """Die Gegenrichtung: Eine Ableitung, die ALLES fordert, waere von einer korrekten nicht zu
    unterscheiden - und machte /.prettierignore zur Kopie der .gitignore."""
    assert _normalisiert(eintrag) not in spiegelungspflichtig({pfad: [eintrag]}), warum


def test_ein_fehlender_eintrag_wird_gemeldet() -> None:
    """Der Koederzustand: Die Ableitung fordert etwas, das in /.prettierignore fehlt."""
    fehlend = fehlende_spiegelungen(
        {".gitignore": ["e2e/.auth/", "node_modules/"]}, ["node_modules/"]
    )
    assert fehlend == ["e2e/.auth (aus .gitignore)"], fehlend


def test_die_schraegstrich_form_ist_kein_unterschied() -> None:
    """`dist` in der .gitignore und `dist/` in /.prettierignore sind dasselbe Muster.

    Ohne diese Normalisierung meldete der Test einen Befund, den es nicht gibt - und der
    naheliegende Weg, ihn loszuwerden, waere eine Ausnahmeliste gewesen.
    """
    assert fehlende_spiegelungen({"frontend/.gitignore": ["dist"]}, ["dist/"]) == []
    assert fehlende_spiegelungen({"frontend/.gitignore": ["dist/"]}, ["dist"]) == []
