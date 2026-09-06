r"""Haelt den Release-Workflow frei von Step-Output-Ausdruecken und CI von Selbst-Merges.

Der Anlass (ADR 0060): `.github/workflows/release-please.yml` hatte einen zweiten Step, der den
Release-PR per `gh pr merge --auto` mergen sollte. GitHub Actions wertet die `env:`-Ausdruecke
eines Steps auch dann aus, wenn dessen `if:` zu false auswertet - `fromJson(steps.release.
outputs.pr).number` bekam ohne Release-PR einen leeren String und riss den ganzen Job als
Template-Fehler mit. Alle 172 Laeufe seit Bestehen des Workflows endeten so auf `failure`, das
Dauerrot verdeckte einen zweiten, unabhaengigen Defekt. Der Step ist ersatzlos entfallen: Daniel
prueft und mergt Release-PRs bewusst selbst.

Die Fehlerklasse ist unauffaellig - der Ausdruck sah durch das `if:` abgesichert aus. Ein
Kommentar im Workflow haette dieselbe Halbwertszeit wie der, der ueber 40 Laeufe hinweg niemanden
erreicht hat; die Regel haengt deshalb an diesem Test.

Vier Zusicherungen, drei Verbote und eine Bestandsgarantie:

1. **Kein Step-Output-Verweis** in `release-please.yml`: die Zeichenketten `steps.`, `needs.` und
   `fromJson(` kommen im kommentarfreien Inhalt ueberhaupt nicht vor. Bewusst ein
   Substring-Totalverbot statt eines Ausdruck-Regex - ein Muster wie `\$\{\{[^}]*\bsteps\.`
   bricht an jeder geschweiften Klammer im Ausdruck ab und uebersaehe genau die bewachte Klasse
   (`${{ format('{0}', steps.a.outputs.x) }}`), ebenso Zeilenumbrueche innerhalb von `${{ }}`.
   In einer 25-zeiligen Datei mit einem einzigen Zweck ist das Totalverbot zugleich schaerfer und
   robuster. `needs.` ist mitverboten, weil dieselbe Auswertungsfalle bei Job-Outputs identisch
   auftritt.
2. **Kein Selbst-Merge in irgendeinem Workflow** - repo-weit, weil die Zusage "CI mergt nichts von
   allein" dem Repository gilt und nicht einer Datei. Mit benannter Ausnahmeliste, damit ein
   spaeter bewusst gewolltes Auto-Merge (z.B. fuer Dependabot) eingetragen und begruendet wird,
   statt den Test aufzuweichen.
3. **Genau ein gepinnter Step**: genau eine `uses:`-Zeile, und die lautet
   `googleapis/release-please-action@<40 Hex>`. Das kodiert "der Workflow besteht aus genau einem
   Step" mit, ohne Steps ueber Einrueckung zu zaehlen, und haelt die Supply-Chain-Haertung aus
   ADR 0008 fest. 40-Hex-Muster statt festem SHA, damit ein Dependabot-Bump gruen bleibt.
4. **Der Workflow funktioniert noch** - Trigger, `with:`-Werte, referenzierte Dateien - und
   **kein Workflow verwendet `pull_request_target`**. Das sind **Sollzusagen aus Spec 0008, hier
   erstmals maschinell festgehalten**, kein neuer Umfang: Das `pull_request_target`-Verbot ist
   das schaerfste Muss-Kriterium jener Spec (das Repo ist public, ein solcher Trigger gaebe
   Fork-PRs Zugriff auf `RELEASE_PLEASE_TOKEN`) und hing bislang an einem Prosa-Kommentar in
   genau der Datei, die diese Story anfasst. Diese Zusicherung ist zugleich das Gegengewicht
   dazu, dass die ersten drei ausschliesslich Verbote sind: Eine mitgeloeschte `with:`-Zeile
   passierte sie alle und fiele erst nach dem Merge auf.

**Was dieser Test ausdruecklich NICHT beweist:** dass kein Workflow mergt. Er verhindert die
Rueckkehr des bekannten Musters, mehr nicht - eine ausreichend andere Schreibweise entginge ihm.
Ebenso wenig prueft er YAML-/Actions-Syntaxgueltigkeit oder Laufzeitverhalten; dafuer greift das
`push: main`-Ersatzmuster aus specs/architecture/0002-testkonzept.md (Negativ-Probe am eigenen
`ci:`-Merge, Positiv-Probe am naechsten releasable Merge).

Bewusst ohne YAML-Bibliothek: PyYAML ist in scripts/pyproject.toml keine Abhaengigkeit, und eine
neue externe Abhaengigkeit fuer vier Zusicherungen waere unverhaeltnismaessig - die Nachbartests
in diesem Verzeichnis arbeiten genauso textbasiert. Kein Netzwerk, kein echtes `gh`, kein
`actions`-Aufruf: gelesen werden ausschliesslich Dateien dieses Repositories.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path

import pytest

REPO_WURZEL = Path(__file__).parents[2]
WORKFLOW_VERZEICHNIS = REPO_WURZEL / ".github" / "workflows"
RELEASE_WORKFLOW_NAME = "release-please.yml"
RELEASE_WORKFLOW_PFAD = WORKFLOW_VERZEICHNIS / RELEASE_WORKFLOW_NAME

# Zusicherung 1: Substring-Totalverbot, klein geschrieben - verglichen wird gegen die
# kleingeschriebene Zeile, weil GitHub Ausdrucksfunktionen ohne Ruecksicht auf Gross-/
# Kleinschreibung aufloest ("fromjson(" ist derselbe Aufruf wie "fromJson(").
VERBOTENE_AUSDRUCKSTEILE = ("steps.", "needs.", "fromjson(")

# Zusicherung 2: Alle Muster tolerieren Gross-/Kleinschreibung und Mehrfach-Leerraum inklusive
# Zeilenumbruch (YAML-Faltung in "run: >"-Bloecken). "auto[-_ ]?merge" deckt die Marktplatz-
# Actions mit ab, die ein spaeterer Wiedereinbau am ehesten haette
# (peter-evans/enable-pull-request-automerge, pascalgn/automerge-action).
SELBST_MERGE_MUSTER = (
    re.compile(r"\bgh\s+pr\s+merge\b", re.IGNORECASE),
    re.compile(r"enable\s*Pull\s*Request\s*Auto\s*Merge", re.IGNORECASE),
    re.compile(r"pulls/[^/\s\"']+/merge\b", re.IGNORECASE),
    re.compile(r"auto[-_ ]?merge", re.IGNORECASE),
)

# Bewusst leer: Es gibt heute keinen gewollten automatisierten Merge-Pfad nach main (ADR 0060).
# Die Liste existiert als vorgesehener Weg fuer den Fall, dass spaeter einer entstehen soll -
# etwa ein auf Dependabot-PRs begrenztes Auto-Merge. Dann gehoert der Dateiname hier hinein,
# mit Begruendung wie bei den Nachbartests, statt dass die Muster oben aufgeweicht werden.
AUSNAHMEN: tuple[str, ...] = ()

# Zusicherung 3: 40-Hex statt festem SHA - ein Dependabot-Bump der Action soll gruen bleiben,
# ein Rueckfall auf den beweglichen Tag "v4" dagegen rot werden.
GEPINNTE_ACTION = re.compile(r"^googleapis/release-please-action@[0-9a-f]{40}$")
_USES_ZEILE = re.compile(r"^\s*(?:-\s+)?uses:\s*(?P<wert>\S+)")

# Nur fuer die Beispiele der Tests weiter unten: der heute gepinnte SHA und ein beliebiger
# zweiter, der einen kuenftigen Dependabot-Bump nachstellt.
ACTION = "googleapis/release-please-action"
SHA_HEUTE = "5c625bfb5d1ff62eadeeb3772007f7f66fdcf071"
SHA_KUENFTIG = "0123456789abcdef0123456789abcdef01234567"

# Zusicherung 4a: Trigger unveraendert. Der Workflow laeuft ausschliesslich auf Push nach main;
# jede Erweiterung ist eine Sicherheitsentscheidung und keine Nebenwirkung.
_TRIGGER_PUSH_MAIN = re.compile(
    r"^on:\s*$\n^\s+push:\s*$\n^\s+branches:\s*\[\s*main\s*\]\s*$", re.MULTILINE
)

# Zusicherung 4b: Ohne diese drei Zeilen laeuft die Action ins Leere bzw. ohne Token - ein zu
# weit gehendes Loeschen faellt sonst erst nach dem Merge auf.
PFLICHTZEILEN = (
    "token: ${{ secrets.RELEASE_PLEASE_TOKEN }}",
    "config-file: release-please-config.json",
    "manifest-file: .release-please-manifest.json",
)

# Zusicherung 4c: die von den beiden with:-Werten referenzierten Dateien, repo-relativ.
REFERENZIERTE_DATEIEN = ("release-please-config.json", ".release-please-manifest.json")

# Zusicherung 4d: das Muss-Kriterium aus Spec 0008 fuer dieses public Repository.
_PULL_REQUEST_TARGET = re.compile(r"pull_request_target", re.IGNORECASE)

# Selbstschutz: Eine kaputte Dateiaufzaehlung liesse alle Verbote still gruen werden.
MINDESTZAHL_WORKFLOWS = 2
PFLICHT_WORKFLOWS = ("ci.yml", RELEASE_WORKFLOW_NAME)

# Gegenprobe und zugleich der Rot-Nachweis dieses TDD-Zyklus: exakt die drei Zeilen, die mit
# ADR 0060 aus release-please.yml verschwunden sind. Treffen die Muster oben hier nicht, ist
# eine Nullmeldung dieses Tests kein Befund, sondern ein Defekt.
HISTORISCH_ENTFERNTE_ZEILEN = (
    "        if: steps.release.outputs.pr",
    "          PR_NUMBER: ${{ fromJson(steps.release.outputs.pr).number }}",
    '        run: gh pr merge --auto --squash "$PR_NUMBER"',
)


def wirksame_zeilen(text: str) -> list[str]:
    """Ersetzt ganzzeilige Kommentare durch Leerzeilen, laesst alles andere unberuehrt.

    Zwingend, und der wahrscheinlichste Selbst-Rotfall dieses Tests: Der Kopfkommentar von
    release-please.yml benennt die verbotenen Muster (`fromJson(steps...)`,
    `pull_request_target`) und wuerde den Test sonst mit genau der Dokumentation rot machen, die
    er erzwingen soll.

    Kommentarzeilen werden zu Leerzeilen statt entfernt, damit gemeldete Zeilennummern denen der
    echten Datei entsprechen - ein Befund ohne belastbare Fundstelle zwingt zum Nachsuchen.

    Inline-Kommentare werden ausdruecklich **nicht** abgeschnitten: Ein naives Abschneiden an
    jedem `#` wuerde an einem `#` innerhalb einer Zeichenkette Inhalt ausblenden und den Test
    damit stillschweigend schwaechen.
    """
    return ["" if zeile.lstrip().startswith("#") else zeile for zeile in text.splitlines()]


def wirksamer_text(text: str) -> str:
    """Der kommentarfreie Inhalt bei erhaltener Zeilenzahl - Suchraum aller Muster hier."""
    return "\n".join(wirksame_zeilen(text))


def _pruefe_nicht_leer(text: str, quelle: str) -> None:
    """Ein leerer Suchraum darf nie als 'nichts gefunden' durchgehen."""
    if not wirksamer_text(text).strip():
        raise ValueError(
            f"{quelle}: 0 wirksame Zeilen. Die Datei ist leer, besteht nur aus Kommentaren oder "
            "wurde umbenannt - in jedem Fall ist die Zusicherung ungeprueft, und ein gruener "
            "Test waere hier bedeutungslos."
        )


def _fundstellen(text: str, muster: re.Pattern[str]) -> list[tuple[int, str]]:
    """Treffer als (Zeilennummer der echten Datei, Fundtext)."""
    return [
        (text[: treffer.start()].count("\n") + 1, treffer.group(0))
        for treffer in muster.finditer(text)
    ]


def ausdrucks_fundstellen(text: str) -> list[str]:
    """Zusicherung 1: meldet jeden Vorkommnis von `steps.`, `needs.` oder `fromJson(`."""
    _pruefe_nicht_leer(text, RELEASE_WORKFLOW_NAME)

    befunde: list[str] = []
    for nummer, zeile in enumerate(wirksame_zeilen(text), start=1):
        klein = zeile.lower()
        befunde.extend(
            f"Zeile {nummer}: {teil!r} in {zeile.strip()!r}"
            for teil in VERBOTENE_AUSDRUCKSTEILE
            if teil in klein
        )
    return befunde


def selbst_merge_fundstellen(
    abbild: Mapping[str, str], ausnahmen: tuple[str, ...] = AUSNAHMEN
) -> list[str]:
    """Zusicherung 2: meldet Merge-Muster in einem Dateiname->Inhalt-Abbild der Workflows."""
    if not abbild:
        raise ValueError(
            "0 Workflow-Dateien im Suchraum: Damit ist die Merge-Freiheit ungeprueft. Entweder "
            "lief die Aufzaehlung im falschen Arbeitsverzeichnis, oder .github/workflows/ ist "
            "leer - ein leerer Suchraum darf nie als 'nichts gefunden' durchgehen."
        )

    befunde: list[str] = []
    for name in sorted(abbild):
        if name in ausnahmen:
            continue
        text = wirksamer_text(abbild[name])
        for muster in SELBST_MERGE_MUSTER:
            befunde.extend(
                f"{name}:{nummer}: {fund!r}" for nummer, fund in _fundstellen(text, muster)
            )
    return befunde


def uses_befunde(text: str) -> list[str]:
    """Zusicherung 3: genau eine `uses:`-Zeile, und die traegt die SHA-gepinnte Action."""
    _pruefe_nicht_leer(text, RELEASE_WORKFLOW_NAME)

    werte = [
        treffer.group("wert")
        for zeile in wirksame_zeilen(text)
        if (treffer := _USES_ZEILE.match(zeile))
    ]

    if len(werte) != 1:
        return [
            f"{len(werte)} 'uses:'-Zeilen gefunden ({werte}), erwartet genau eine. Der Workflow "
            "besteht bewusst aus genau einem Step (ADR 0060)."
        ]
    if not GEPINNTE_ACTION.match(werte[0]):
        return [
            f"'uses: {werte[0]}' ist nicht die auf einen 40-stelligen Commit-SHA gepinnte "
            "googleapis/release-please-action. Ein beweglicher Tag waere eine Supply-Chain-"
            "Regression gegenueber ADR 0008."
        ]
    return []


def pull_request_target_fundstellen(abbild: Mapping[str, str]) -> list[str]:
    """Zusicherung 4d: `pull_request_target` in keinem Workflow dieses public Repositories."""
    if not abbild:
        raise ValueError(
            "0 Workflow-Dateien im Suchraum: Damit ist das pull_request_target-Verbot "
            "ungeprueft - ein leerer Suchraum darf nie als 'nichts gefunden' durchgehen."
        )

    return [
        f"{name}:{nummer}: {fund!r}"
        for name in sorted(abbild)
        for nummer, fund in _fundstellen(wirksamer_text(abbild[name]), _PULL_REQUEST_TARGET)
    ]


def fehlende_pflichtzeilen(text: str) -> list[str]:
    """Zusicherung 4b: die drei `with:`-Werte, ohne die die Action nicht mehr taete, was sie soll.

    Ohne sie laeuft die Action ohne Token bzw. gegen die falsche Konfiguration.
    """
    _pruefe_nicht_leer(text, RELEASE_WORKFLOW_NAME)

    vorhanden = {zeile.strip() for zeile in wirksame_zeilen(text)}
    return [pflicht for pflicht in PFLICHTZEILEN if pflicht not in vorhanden]


def trigger_ist_push_main(text: str) -> bool:
    """Zusicherung 4a: unveraendert `on: push: branches: [main]`, nichts sonst davor."""
    _pruefe_nicht_leer(text, RELEASE_WORKFLOW_NAME)

    return _TRIGGER_PUSH_MAIN.search(wirksamer_text(text)) is not None


def release_workflow_text(pfad: Path = RELEASE_WORKFLOW_PFAD) -> str:
    """Duenner Leser fuer den echten Dateizustand; eine fehlende Datei scheitert laut."""
    return pfad.read_text(encoding="utf-8")


def workflow_abbild(verzeichnis: Path = WORKFLOW_VERZEICHNIS) -> dict[str, str]:
    """Duenner Leser: Dateiname -> Inhalt fuer alle Workflows, beide Endungsschreibweisen."""
    pfade = sorted(p for p in verzeichnis.glob("*.y*ml") if p.suffix in {".yml", ".yaml"})
    return {pfad.name: pfad.read_text(encoding="utf-8") for pfad in pfade}


# --- Zusicherung 1 ----------------------------------------------------------------------------


def test_der_release_workflow_verweist_auf_keinen_step_output() -> None:
    befunde = ausdrucks_fundstellen(release_workflow_text())

    assert not befunde, (
        f"{RELEASE_WORKFLOW_NAME} verweist wieder auf einen Step-/Job-Output: "
        f"{'; '.join(befunde)}.\nUrsache, nicht nur Fund: GitHub wertet die Ausdruecke eines "
        "Steps auch dann aus, wenn dessen 'if:' false ergibt. Ein fromJson() auf einem leeren "
        "Output reisst den gesamten Job als Template-Fehler mit - genau der Defekt, der 172 "
        "Laeufe rot gemacht hat (ADR 0060). Der Ausweg ist eine Revision jener Entscheidung "
        "samt neuer ADR, nicht das Aufweichen dieses Tests."
    )


@pytest.mark.parametrize("zeile", HISTORISCH_ENTFERNTE_ZEILEN[:2])
def test_die_historischen_ausdruckszeilen_wuerden_erkannt(zeile: str) -> None:
    """Gegenprobe: Ohne sie waere die Nullmeldung oben kein Befund, sondern ein defektes Muster."""
    assert ausdrucks_fundstellen(f"on:\n  push:\n{zeile}\n")


def test_ein_kopfkommentar_mit_den_verbotenen_woertern_macht_nicht_rot() -> None:
    """Der wahrscheinlichste Selbst-Rotfall: Die Doku benennt notwendig, was sie verbietet."""
    text = (
        "# Wer hier je einen zweiten Step ergaenzt: ein\n"
        "#   fromJson(steps.<id>.outputs.<x>)\n"
        "# auf leerem Output reisst den Job mit. 'if:' tut es nicht.\n"
        "on:\n  push:\n    branches: [main]\n"
    )

    assert ausdrucks_fundstellen(text) == []


def test_ein_eingerueckter_kommentar_zaehlt_ebenfalls_als_kommentar() -> None:
    assert ausdrucks_fundstellen("on:\n  push:\n      # fromJson(steps.release.outputs.pr)\n") == []


def test_inline_kommentare_werden_nicht_abgeschnitten() -> None:
    """Bewusste Grenze: Nur ganzzeilige Kommentare verschwinden, sonst liesse sich Inhalt tarnen."""
    befunde = ausdrucks_fundstellen("on:\n  push: x  # steps.release.outputs.pr\n")

    assert befunde == ["Zeile 2: 'steps.' in 'push: x  # steps.release.outputs.pr'"]


def test_die_meldung_nennt_die_zeilennummer_der_echten_datei() -> None:
    """Kommentarzeilen werden zu Leerzeilen, nicht entfernt - sonst verschoebe sich die Nummer."""
    text = "# Kommentar\n# noch einer\non:\n  x: ${{ needs.build.outputs.y }}\n"

    assert ausdrucks_fundstellen(text) == [
        "Zeile 4: 'needs.' in 'x: ${{ needs.build.outputs.y }}'"
    ]


@pytest.mark.parametrize(
    "ausdruck",
    [
        "${{ format('{0}', steps.a.outputs.x) }}",  # geschweifte Klammer im Ausdruck
        "${{\n        steps.a.outputs.x }}",  # Umbruch innerhalb von ${{ }}
        "${{ FROMJSON(needs.build.outputs.pr) }}",  # Gross-/Kleinschreibung
    ],
)
def test_faelle_an_denen_ein_ausdruck_regex_scheitern_wuerde(ausdruck: str) -> None:
    """Begruendet das Substring-Totalverbot: Diese drei entgingen einem `\\$\\{\\{[^}]*`-Muster."""
    assert ausdrucks_fundstellen(f"on:\n  push:\n  wert: {ausdruck}\n")


def test_ein_leerer_wirksamer_inhalt_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"0 wirksame Zeilen"):
        ausdrucks_fundstellen("# nur ein Kommentar\n\n   \n")


def test_eine_fehlende_datei_scheitert_laut(tmp_path: Path) -> None:
    """Umbenannt oder geloescht darf nicht heissen: gruen, weil nichts gefunden."""
    with pytest.raises(FileNotFoundError):
        release_workflow_text(tmp_path / "gibt-es-nicht.yml")


# --- Zusicherung 2 ----------------------------------------------------------------------------


def test_kein_workflow_mergt_von_allein() -> None:
    abbild = workflow_abbild()

    assert len(abbild) >= MINDESTZAHL_WORKFLOWS, (
        f"Nur {len(abbild)} Workflow-Dateien gefunden (erwartet: mindestens "
        f"{MINDESTZAHL_WORKFLOWS}). Die Aufzaehlung ist kaputt; ein Nullbefund dieses Tests "
        "waere dann bedeutungslos."
    )
    assert set(PFLICHT_WORKFLOWS) <= set(abbild), (
        f"Der Suchraum {sorted(abbild)} enthaelt nicht beide erwarteten Workflows "
        f"{PFLICHT_WORKFLOWS} - die Aufzaehlung sieht nicht, was sie sehen soll."
    )

    befunde = selbst_merge_fundstellen(abbild)

    assert not befunde, (
        f"Ein Workflow mergt wieder selbst: {'; '.join(befunde)}.\nSeit ADR 0060 gibt es keinen "
        "unbeaufsichtigten Merge-Pfad nach main mehr; Release-PRs prueft und mergt Daniel "
        "bewusst von Hand. Ein gewollter automatisierter Merge gehoert mit Begruendung in "
        "AUSNAHMEN - nicht in eine Aufweichung der Muster."
    )


@pytest.mark.parametrize("zeile", HISTORISCH_ENTFERNTE_ZEILEN[2:])
def test_die_historische_merge_zeile_wuerde_erkannt(zeile: str) -> None:
    """Gegenprobe gegen den tatsaechlich entfernten Aufruf."""
    assert selbst_merge_fundstellen({"release-please.yml": zeile})


@pytest.mark.parametrize(
    "inhalt",
    [
        "run: GH PR MERGE --auto 1",
        "run: gh  pr   merge --squash 1",
        "run: gh pr\n  merge --squash 1",
        "uses: peter-evans/enable-pull-request-automerge@v3",
        "uses: pascalgn/automerge-action@v0.16.4",
        "run: gh api -X PUT repos/o/r/pulls/12/merge",
        'run: curl -X PUT ".../pulls/$NUM/merge"',
        "with:\n  mutation: enablePullRequestAutoMerge",
        "with:\n  mutation: enablepullrequestautomerge",
        "# nicht hier, aber:\nrun: echo auto_merge",
    ],
)
def test_merge_muster_sind_schreibweisen_tolerant(inhalt: str) -> None:
    assert selbst_merge_fundstellen({"w.yml": inhalt})


@pytest.mark.parametrize(
    "inhalt",
    [
        "run: gh pr view 1 --json state",  # kein merge
        "run: git merge --ff-only main",  # kein PR-Merge ueber die API
        "run: gh pr create --title 'x'",
    ],
)
def test_harmlose_gh_und_git_aufrufe_sind_kein_befund(inhalt: str) -> None:
    assert selbst_merge_fundstellen({"w.yml": inhalt}) == []


def test_ein_merge_in_einem_ganzzeiligen_kommentar_ist_kein_befund() -> None:
    """Sonst waere der Kopfkommentar, der die Regel erklaert, selbst ihr Verstoss."""
    abbild = {"w.yml": "# frueher stand hier: gh pr merge --auto\non:\n"}

    assert selbst_merge_fundstellen(abbild) == []


def test_eine_eingetragene_ausnahme_wird_uebergangen() -> None:
    """Der vorgesehene Weg fuer ein spaeteres, bewusst gewolltes Auto-Merge."""
    abbild = {"dependabot-automerge.yml": "run: gh pr merge --auto --squash 1"}

    assert selbst_merge_fundstellen(abbild, ausnahmen=("dependabot-automerge.yml",)) == []
    assert selbst_merge_fundstellen(abbild) != []


def test_ein_leerer_workflow_suchraum_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"0 Workflow-Dateien"):
        selbst_merge_fundstellen({})


def test_der_leser_findet_beide_workflows_dieses_repositories() -> None:
    """Gegenprobe zum Leser selbst - inklusive der Endung .yaml, die hier nur niemand nutzt."""
    assert set(PFLICHT_WORKFLOWS) <= set(workflow_abbild())


def test_der_leser_erfasst_auch_die_endung_yaml(tmp_path: Path) -> None:
    (tmp_path / "a.yml").write_text("on: push\n", encoding="utf-8")
    (tmp_path / "b.yaml").write_text("on: push\n", encoding="utf-8")
    (tmp_path / "liesmich.md").write_text("gh pr merge\n", encoding="utf-8")

    assert sorted(workflow_abbild(tmp_path)) == ["a.yml", "b.yaml"]


# --- Zusicherung 3 ----------------------------------------------------------------------------


def test_genau_ein_step_mit_der_sha_gepinnten_action() -> None:
    befunde = uses_befunde(release_workflow_text())

    assert not befunde, "; ".join(befunde)


@pytest.mark.parametrize(
    "text",
    [
        f"steps:\n  - uses: {ACTION}@{SHA_HEUTE}\n",
        f"steps:\n  - uses: {ACTION}@{SHA_KUENFTIG} # v9.9.9\n",
        f"steps:\n  - id: x\n    uses: {ACTION}@{SHA_HEUTE}\n",
    ],
)
def test_ein_dependabot_bump_der_action_bleibt_gruen(text: str) -> None:
    """40-Hex-Muster statt festem SHA - eine neue Version darf den Test nicht rot machen."""
    assert uses_befunde(text) == []


@pytest.mark.parametrize(
    "text",
    [
        f"steps:\n  - uses: {ACTION}@v4\n",  # beweglicher Tag
        f"steps:\n  - uses: {ACTION}@5c625bfb\n",  # gekuerzter SHA
        f"steps:\n  - uses: boeser/release-please-action@{SHA_HEUTE}\n",  # andere Action
        f"steps:\n  - uses: {ACTION}@{SHA_HEUTE}\n  - uses: actions/checkout@v4\n",  # zwei Steps
        "on:\n  push:\n    branches: [main]\n",  # gar keine Action mehr
    ],
)
def test_abweichungen_vom_einen_gepinnten_step_werden_gemeldet(text: str) -> None:
    assert uses_befunde(text)


def test_eine_auskommentierte_uses_zeile_zaehlt_nicht_mit() -> None:
    text = f"steps:\n  # - uses: actions/checkout@v4\n  - uses: {ACTION}@{SHA_HEUTE}\n"

    assert uses_befunde(text) == []


# --- Zusicherung 4 ----------------------------------------------------------------------------


def test_der_trigger_bleibt_push_auf_main() -> None:
    assert trigger_ist_push_main(release_workflow_text()), (
        f"{RELEASE_WORKFLOW_NAME} laeuft nicht mehr genau auf 'push: branches: [main]'. Jede "
        "Erweiterung des Triggers ist eine Sicherheitsentscheidung (Spec 0008) und keine "
        "Nebenwirkung einer Workflow-Aenderung."
    )


@pytest.mark.parametrize(
    "text",
    [
        "on:\n  push:\n    branches: [ main ]\n",
        "on:\n  push:\n    branches: [main]\n\njobs:\n  x:\n    runs-on: ubuntu-latest\n",
    ],
)
def test_gleichwertige_schreibweisen_des_triggers_gelten(text: str) -> None:
    assert trigger_ist_push_main(text)


@pytest.mark.parametrize(
    "text",
    [
        "on:\n  pull_request:\n    branches: [main]\n",
        "on:\n  push:\n    branches: [main, develop]\n",
        "on:\n  push:\n    tags: ['v*']\n",
        "on: push\n",
    ],
)
def test_ein_geaenderter_trigger_wird_erkannt(text: str) -> None:
    assert not trigger_ist_push_main(text)


def test_die_drei_with_werte_sind_vorhanden() -> None:
    fehlend = fehlende_pflichtzeilen(release_workflow_text())

    assert not fehlend, (
        f"In {RELEASE_WORKFLOW_NAME} fehlen Pflichtzeilen: {fehlend}. Ohne sie laeuft die Action "
        "ohne Token bzw. gegen die falsche Konfiguration - ein zu weit gehendes Loeschen faellt "
        "sonst erst nach dem Merge auf."
    )


def test_eine_geloeschte_with_zeile_wird_gemeldet() -> None:
    text = (
        "with:\n"
        "  token: ${{ secrets.RELEASE_PLEASE_TOKEN }}\n"
        "  config-file: release-please-config.json\n"
    )

    assert fehlende_pflichtzeilen(text) == ["manifest-file: .release-please-manifest.json"]


@pytest.mark.parametrize("name", REFERENZIERTE_DATEIEN)
def test_die_referenzierten_konfigurationsdateien_existieren(name: str) -> None:
    assert (REPO_WURZEL / name).is_file(), (
        f"{RELEASE_WORKFLOW_NAME} verweist auf {name}, die Datei fehlt aber im Repository."
    )


def test_kein_workflow_verwendet_pull_request_target() -> None:
    abbild = workflow_abbild()

    assert set(PFLICHT_WORKFLOWS) <= set(abbild), (
        f"Der Suchraum {sorted(abbild)} enthaelt nicht beide erwarteten Workflows - die "
        "Aufzaehlung sieht nicht, was sie sehen soll."
    )

    befunde = pull_request_target_fundstellen(abbild)

    assert not befunde, (
        f"Ein Workflow verwendet 'pull_request_target': {'; '.join(befunde)}.\nDas Repository "
        "ist public - dieser Trigger laeuft im Kontext des Basis-Repositories und gaebe Fork-PRs "
        "Zugriff auf RELEASE_PLEASE_TOKEN (Muss-Kriterium aus Spec 0008)."
    )


def test_pull_request_target_wuerde_erkannt() -> None:
    """Gegenprobe: Das Verbot hing bis ADR 0060 an einem blossen Kommentar."""
    assert pull_request_target_fundstellen({"w.yml": "on:\n  pull_request_target:\n"}) == [
        "w.yml:2: 'pull_request_target'"
    ]


def test_der_kommentar_der_das_verbot_erklaert_ist_selbst_kein_verstoss() -> None:
    abbild = {"w.yml": "# nie auf pull_request_target erweitern\n"}

    assert pull_request_target_fundstellen(abbild) == []


def test_ein_leerer_suchraum_scheitert_auch_hier_laut() -> None:
    with pytest.raises(ValueError, match=r"0 Workflow-Dateien"):
        pull_request_target_fundstellen({})
