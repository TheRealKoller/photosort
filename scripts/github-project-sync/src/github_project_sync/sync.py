"""Orchestrierung des Zwei-Wege-Sync-Laufs fuer Feature-Specs sowie der dateilosen Story-Stufe.

Verdrahtet die reinen Bausteine (spec_parser, roadmap_parser, hashing, classify, issue_body,
state) mit dem GhAdapter-Protokoll. Siehe specs/features/0031-zweiwege-sync-specs-github-projekt.md,
specs/features/0059-story-lebenszyklus-github-issues.md und
ADR decisions/0017-github-projects-v2-spec-sync.md /
ADR decisions/0036-github-issue-natives-story-refinement-inbox-entfaellt.md.

Seit Spec 0059 gibt es zwei strukturell unterschiedliche Pfade: `run_sync()` fuer den
bidirektionalen Feature-Spec-Sync (unveraendert gegenueber ADR 0017, plus Prioritaets-Push fuer
issue-referenzierte Roadmap-Zeilen im Vollauf) sowie drei dateilose Story-Funktionen
(`create_story_issue`, `sync_story`, `show_story_status`), die ausschliesslich gegen den
`stories`-Namensraum der Zustandsdatei arbeiten - kein Pull/Konflikt-Handling noetig, da eine
Story nur eine einzige Kopie der Wahrheit hat (das GitHub-Issue selbst, siehe ADR 0036, Kontext).
Der vorherige, bidirektionale Inbox-Pfad (`_sync_one_inbox`, `--only inbox:NNNN`,
`--supersede-inbox`) wurde ersatzlos entfernt.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from github_project_sync.classify import SyncClassification, SyncStateEntry, classify
from github_project_sync.gh_adapter import (
    STATUS_FIELD_NAME,
    GhAdapter,
    GhAdapterError,
    Project,
    ProjectFields,
)
from github_project_sync.hashing import push_state_hash, text_hash
from github_project_sync.issue_body import (
    build_issue_body,
    extract_content_zone_from_issue_body,
    parse_marker,
)
from github_project_sync.roadmap_parser import parse_roadmap_priorities
from github_project_sync.spec_parser import (
    parse_spec_file,
    replace_content_zone,
    set_status_line,
    validate_spec_number,
)
from github_project_sync.state import (
    NestedState,
    StateDict,
    StoryStateEntry,
    find_orphaned_numbers,
    load_state,
    save_state,
    validate_issue_number_key,
)

Resolution = Literal["keep_spec", "keep_issue"]

_OPEN_STATUSES = {"Proposed", "Accepted"}
_CLOSED_STATUSES = {"Implemented", "Superseded"}
_VALID_STATUSES = _OPEN_STATUSES | _CLOSED_STATUSES

# Seit Spec 0060 / ADR decisions/0037-status-lebenszyklus-umsetzungsfortschritt-pr-merge-
# erkennung.md, Abschnitt 2: das Board-Status-Feld ist keine 1:1-Kopie des Datei-Status mehr,
# sondern eine Baseline-Projektion (Datei-Status -> Board-Wert), optional verfeinert durch einen
# in specs/.github-sync-state.json persistierten Laufzeit-Override ("In Progress"/"Review") -
# der Override wirkt strukturell nur, solange die Baseline "Todo" ist (siehe _apply_fields()).
# "Superseded" ist bewusst NICHT Teil dieser Tabelle (bleibt eigener Sonderfall: Feld leeren +
# Label, ADR 0030 Abschnitt 2).
_BOARD_STATUS_BASELINE = {"Proposed": "Todo", "Accepted": "Todo", "Implemented": "Done"}
_RUNTIME_OVERRIDE_STATUSES = {"In Progress", "Review"}
# Story-Ebene (ADR 0037, Abschnitt 6): kein Baseline/Override-Modell noetig (keine lokale Datei,
# aus der sich der Status rekonstruieren liesse) - deshalb eine eigene, engere Werteliste statt
# der vollen STATUS_OPTIONS (die jetzt auch die drei Feature-only-Werte enthaelt).
_STORY_VALID_STATUSES = {"Unrefined", "Ready", "Done"}

_ORPHAN_CLOSE_COMMENT = "Spec-Datei wurde entfernt."

_ISSUE_ONLY_PREFIX = "issue:"

# Labels: Superseded verschwindet als Feldwert und wird stattdessen ein Label (ADR 0030,
# Abschnitt 2); Idee/Bug bilden den Story-**Typ:** ab (aehnlich ADR 0030, Abschnitt 6, jetzt fuer
# Story-Issues statt Inbox-Dateien). "bug" existiert im Repo bereits (wiederverwendet statt eines
# eigenen, spezifischeren Labels).
_LABEL_SUPERSEDED = "superseded"
_LABEL_IDEE = "idee"
_LABEL_BUG = "bug"
_MANAGED_FEATURE_LABELS: frozenset[str] = frozenset({_LABEL_SUPERSEDED})
_MANAGED_STORY_LABELS: frozenset[str] = frozenset({_LABEL_IDEE, _LABEL_BUG})
_STORY_TYPE_TO_LABEL = {"idee": _LABEL_IDEE, "bug": _LABEL_BUG}
_LABEL_PROVISIONING = {
    _LABEL_SUPERSEDED: {
        "description": "Spec wurde durch eine neuere abgeloest.",
        "color": "cfd3d7",
    },
    _LABEL_IDEE: {
        "description": "Story-Issue: neue Idee, noch ungeschaerft/in Verfeinerung.",
        "color": "0e8a16",
    },
    _LABEL_BUG: {
        "description": "Something isn't working",
        "color": "d73a4a",
    },
}


class SyncError(RuntimeError):
    """Ein Sync-Lauf konnte nicht wie angefragt ausgefuehrt werden.

    Z.B. eine unbekannte --only-Spec-Nummer.
    """


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class ConflictDiff:
    local_content_zone: str
    remote_content_zone: str


@dataclass(frozen=True)
class SpecSyncResult:
    number: str
    title: str
    issue_number: int | None
    classification: SyncClassification | None
    aborted_reason: str | None = None
    priority_warning: str | None = None
    conflict: ConflictDiff | None = None
    pulled_content_zone: str | None = None
    # Seit Spec 0060 / ADR 0037, Abschnitt 5: gesetzt, wenn dieser Lauf gerade eine automatische
    # PR-Merge-Erkennung fuer diese Spec ausgefuehrt hat (Signal an den aufrufenden Skill, z.B.
    # fuer den requirements-engineer-Aufruf zum Verschieben der Roadmap-Zeile).
    finalized_from_pr: int | None = None


@dataclass(frozen=True)
class OrphanCleanup:
    number: str
    issue_number: int


@dataclass(frozen=True)
class AdoptedResult:
    """Ergebnis von `--only NNNN --adopt-issue MMM` (Story -> Feature-Spec-Uebergang)."""

    spec_number: str
    issue_number: int


@dataclass(frozen=True)
class SyncRunResult:
    specs: list[SpecSyncResult]
    orphaned: list[OrphanCleanup]
    adopted: AdoptedResult | None = None


def _parse_only(value: str | None) -> str | None:
    """Bare "NNNN" (Feature-Scope) oder None fuer einen vollen Lauf. Ein "issue:NNN"-Scope wird
    NICHT hier behandelt - das ist Aufgabe von cli.py, das dafuer direkt sync_story()/
    show_story_status() aufruft, ohne je run_sync() zu erreichen (siehe Modul-Docstring)."""
    if value is None:
        return None
    validate_spec_number(value)
    return value


def _reconcile_labels(
    gh: GhAdapter,
    issue_number: int,
    *,
    current: frozenset[str],
    desired: frozenset[str],
    managed: frozenset[str],
) -> None:
    """Setzt/entfernt nur Labels aus 'managed' - fremd gesetzte Labels bleiben unangetastet."""
    add = desired - current
    remove = (current & managed) - desired
    if add or remove:
        gh.set_issue_labels(issue_number, add=add, remove=remove)


def _apply_priority_only(
    gh: GhAdapter, project: Project, fields: ProjectFields, item_id: str, priority: str | None
) -> None:
    if priority is None:
        gh.clear_item_field(project, item_id=item_id, field_id=fields.priority_field_id)
        return

    priority_option_id = fields.priority_options.get(priority)
    if priority_option_id is None:
        raise SyncError(
            f"Project-Feld 'Priorität' hat keine Option fuer {priority!r} (vorhanden: "
            f"{sorted(fields.priority_options)}). Vermutlich wurden die Feld-Optionen manuell "
            "im GitHub Project veraendert - bitte das Prioritaets-Feld reparieren, bevor der "
            "Sync erneut laeuft."
        )
    gh.set_item_single_select(
        project, item_id=item_id, field_id=fields.priority_field_id, option_id=priority_option_id
    )


def _apply_status_only(
    gh: GhAdapter, project: Project, fields: ProjectFields, item_id: str, *, status: str
) -> None:
    status_option_id = fields.status_options.get(status)
    if status_option_id is None:
        raise SyncError(
            f"Project-Feld 'Status' hat keine Option fuer {status!r} (vorhanden: "
            f"{sorted(fields.status_options)}). Vermutlich wurden die Feld-Optionen manuell im "
            "GitHub Project veraendert - bitte das Status-Feld reparieren, bevor der Sync "
            "erneut laeuft."
        )
    gh.set_item_single_select(
        project, item_id=item_id, field_id=fields.status_field_id, option_id=status_option_id
    )


def _apply_fields(
    gh: GhAdapter,
    project: Project,
    fields: ProjectFields,
    item_id: str,
    *,
    status: str,
    priority: str | None,
    runtime_status: str | None = None,
) -> None:
    # Board-Drift (Daniel/ein Dritter bearbeitet die Optionen eines Project-Felds manuell) darf
    # nie still hingenommen werden - ensure_fields() uebernimmt ein bereits existierendes Feld
    # unveraendert, auch wenn dessen Optionen nicht mehr zu STATUS_OPTIONS/PRIORITY_OPTIONS
    # passen. Ein No-Op (Status) bzw. ein faelschliches Leeren (Prioritaet trotz vorhandenem
    # Wert) waere genau die Art von unbemerktem Abweichen, die ADR 0017 (Status/Prioritaet als
    # bei jedem Lauf durchgesetzte Einbahnstrasse) verhindern soll - deshalb hart abbrechen statt
    # stillschweigend weiterzumachen (Copilot-Review-Finding auf PR #115).
    if status == "Superseded":
        # Seit ADR 0030, Abschnitt 2: Superseded ist kein Feldwert mehr (STATUS_OPTIONS enthaelt
        # ihn nicht), das Status-Feld wird stattdessen geleert - exakt dasselbe Muster wie das
        # bereits bestehende Leeren des Prioritaets-Felds.
        gh.clear_item_field(project, item_id=item_id, field_id=fields.status_field_id)
    else:
        # Seit Spec 0060 / ADR 0037, Abschnitt 2: der gepushte Board-Wert ist die aus dem
        # Datei-Status berechnete Baseline, optional verfeinert durch runtime_status - aber
        # strukturell NIE mehr als eine Verfeinerung von "Todo": sobald die Baseline "Done" ist,
        # gewinnt sie immer, unabhaengig davon, was runtime_status noch traegt (der Aufrufer
        # muss den State-Eintrag dafuer nicht separat "kennen").
        baseline = _BOARD_STATUS_BASELINE[status]
        if runtime_status is not None and baseline == "Todo":
            board_status = runtime_status
        else:
            board_status = baseline
        _apply_status_only(gh, project, fields, item_id, status=board_status)

    _apply_priority_only(gh, project, fields, item_id, priority)


def _sync_one(
    *,
    number: str,
    title: str,
    status: str,
    content_zone: str,
    full_text: str,
    path: Path,
    priority: str | None,
    stored_entry: SyncStateEntry | None,
    gh: GhAdapter,
    project: Project,
    fields: ProjectFields,
    resolution: Resolution | None,
    now: Callable[[], str],
) -> tuple[SpecSyncResult, SyncStateEntry | None]:
    # Automatische PR-Merge-Erkennung (Spec 0060 / ADR 0037, Abschnitt 5) - ganz am Anfang der
    # Funktion, vor der Status-Validitaetspruefung: nur aktiv fuer eine bereits getrackte
    # ("stored_entry is not None"), noch "Accepted" gefuehrte Spec mit stehendem
    # "Review"-Override und referenziertem PR. Ist der PR gemerged, wird die Spec-Datei hier
    # selbst (einzige Schreibstelle, ADR 0017 Abschnitt 4) auf "Implemented" umgeschrieben -
    # alle nachgelagerte Logik (Hash, _apply_fields, is_open, Labels) behandelt sie danach wie
    # jede regulaer auf "Implemented" gesetzte Spec, kein weiterer Sonderpfad noetig.
    finalized_from_pr: int | None = None
    if (
        stored_entry is not None
        and status == "Accepted"
        and stored_entry.runtime_status == "Review"
        and stored_entry.pr_number is not None
    ):
        try:
            pull_request = gh.get_pull_request(stored_entry.pr_number)
        except GhAdapterError as exc:
            # Wie bei ungueltigem Status/Marker-Integritaet (unten): ein Problem, das nur diese
            # eine Spec betrifft (PR nicht auffindbar, gh-CLI-Fehler, Rate-Limit), darf nicht
            # den gesamten Mehr-Spec-Lauf per Exception toeten. stored_entry bleibt unveraendert -
            # ein erneuter Lauf versucht die Merge-Erkennung erneut, sobald behoben (idempotent).
            result = SpecSyncResult(
                number=number,
                title=title,
                issue_number=stored_entry.issue_number,
                classification=None,
                aborted_reason=(
                    f"PR-Merge-Erkennung fuer Spec {number} fehlgeschlagen (PR "
                    f"#{stored_entry.pr_number}): {exc}. Sync fuer diese Spec abgebrochen, "
                    "andere Specs sind unbeeinflusst."
                ),
            )
            return result, stored_entry
        if pull_request.state == "merged":
            new_status_line = f"Implemented ([PR #{stored_entry.pr_number}]({pull_request.url}))"
            full_text = set_status_line(full_text, new_status_line)
            path.write_text(full_text, encoding="utf-8")
            status = "Implemented"
            finalized_from_pr = stored_entry.pr_number

    if status not in _VALID_STATUSES:
        # Ein Problem, das nur diese eine Spec betrifft, darf nicht den gesamten Mehr-Spec-Lauf
        # mit einer laufabbrechenden SyncError toeten (Akzeptanzkriterium "Marker-Integritaet":
        # andere Specs im selben Lauf laufen unbeeinflusst weiter). stored_entry (falls
        # vorhanden) bleibt unveraendert; fuer eine noch nie synchronisierte Spec (stored_entry
        # is None) gibt es naturgemaess nichts zu bewahren.
        result = SpecSyncResult(
            number=number,
            title=title,
            issue_number=stored_entry.issue_number if stored_entry is not None else None,
            classification=None,
            aborted_reason=(
                f"Ungueltiger/unbekannter Status {status!r} (erwartet einen von "
                f"{sorted(_VALID_STATUSES)}). Sync fuer diese Spec abgebrochen, andere Specs "
                "sind unbeeinflusst."
            ),
        )
        return result, stored_entry

    priority_warning = None
    if priority is None and status in _OPEN_STATUSES:
        priority_warning = (
            f"Spec {number} ({status}) taucht in keiner Prioritaets-Tabelle von "
            "specs/roadmap.md auf."
        )

    push_hash_now = push_state_hash(status=status, priority=priority, content_zone=content_zone)
    issue_title = f"[{number}] {title}"
    is_open = status in _OPEN_STATUSES
    desired_labels: frozenset[str] = (
        frozenset({_LABEL_SUPERSEDED}) if status == "Superseded" else frozenset()
    )

    if stored_entry is None:
        body = build_issue_body(number, content_zone)
        issue_number = gh.create_issue(issue_title, body)
        issue = gh.get_issue(issue_number)
        item_id = gh.add_item_to_project(project, issue_url=issue.url)
        _apply_fields(gh, project, fields, item_id, status=status, priority=priority)
        gh.set_issue_state(issue_number, open=is_open)
        _reconcile_labels(
            gh,
            issue_number,
            current=issue.labels,
            desired=desired_labels,
            managed=_MANAGED_FEATURE_LABELS,
        )

        new_entry = SyncStateEntry(
            issue_number=issue_number,
            item_id=item_id,
            pushed_state_hash=push_hash_now,
            pulled_body_hash=text_hash(content_zone),
            last_synced_at=now(),
        )
        result = SpecSyncResult(
            number=number,
            title=title,
            issue_number=issue_number,
            classification="created",
            priority_warning=priority_warning,
        )
        return result, new_entry

    issue = gh.get_issue(stored_entry.issue_number)
    # ADR decisions/0017-github-projects-v2-spec-sync.md, Bedrohung 1, nennt als zusaetzliche
    # Gegenmassnahme "ein Fallback bei fehlendem State-Eintrag verifiziert zusaetzlich
    # issue.author.login == 'TheRealKoller'". Dieser Fallback wird hier bewusst NICHT
    # implementiert, siehe dortige Begruendung - IssueView.author_login wird deshalb aktuell
    # nicht ausgewertet.
    marker_number = parse_marker(issue.body)
    if marker_number != number:
        result = SpecSyncResult(
            number=number,
            title=title,
            issue_number=stored_entry.issue_number,
            classification=None,
            aborted_reason=(
                f"Marker-Integritaet verletzt: Issue #{stored_entry.issue_number} enthaelt "
                f"keinen zu Spec {number} passenden Marker (gefunden: {marker_number!r}). "
                "Sync fuer diese Spec abgebrochen, andere Specs sind unbeeinflusst."
            ),
            priority_warning=priority_warning,
            finalized_from_pr=finalized_from_pr,
        )
        return result, stored_entry

    remote_content_zone = extract_content_zone_from_issue_body(issue.body)
    pull_hash_now = text_hash(remote_content_zone)
    classification = classify(
        stored_entry, push_hash_now=push_hash_now, pull_hash_now=pull_hash_now
    )

    # Status/Prioritaet + nativer Issue-Zustand sind eine bewusste Einbahnstrasse und werden bei
    # jedem Sync-Lauf neu gesetzt, unabhaengig von der Inhalts-Klassifikation (ADR 0017, Abschnitt
    # 4/6: "immer, pro Sync-Lauf" - setzt auch ein manuell abweichend geoeffnetes/geschlossenes
    # Issue wieder zurueck, siehe Akzeptanzkriterium "Status-Feld + Issue-Zustand"). Labels
    # (superseded) werden aus demselben Grund ebenfalls unabhaengig von der Klassifikation
    # reconciled (ADR 0030, Abschnitt 6: "pro Sync-Lauf voll reconciled").
    _apply_fields(
        gh,
        project,
        fields,
        stored_entry.item_id,
        status=status,
        priority=priority,
        runtime_status=stored_entry.runtime_status,
    )
    gh.set_issue_state(stored_entry.issue_number, open=is_open)
    _reconcile_labels(
        gh,
        stored_entry.issue_number,
        current=issue.labels,
        desired=desired_labels,
        managed=_MANAGED_FEATURE_LABELS,
    )

    if classification == "conflict" and resolution is None:
        result = SpecSyncResult(
            number=number,
            title=title,
            issue_number=stored_entry.issue_number,
            classification="conflict",
            priority_warning=priority_warning,
            conflict=ConflictDiff(
                local_content_zone=content_zone, remote_content_zone=remote_content_zone
            ),
            finalized_from_pr=finalized_from_pr,
        )
        # Baseline-Hashes bleiben unveraendert, bis Daniel den Konflikt explizit aufloest -
        # ein erneuter Lauf ohne Aufloesung meldet denselben Konflikt wieder (idempotent).
        return result, stored_entry

    effective: SyncClassification = classification
    if classification == "conflict" and resolution == "keep_spec":
        effective = "pushed"
    elif classification == "conflict" and resolution == "keep_issue":
        effective = "pulled"

    pulled_content_zone: str | None = None
    effective_local_content_zone = content_zone

    if effective == "pushed":
        gh.edit_issue_body(stored_entry.issue_number, build_issue_body(number, content_zone))
    elif effective == "pulled":
        pulled_content_zone = remote_content_zone
        effective_local_content_zone = remote_content_zone
        updated_text = replace_content_zone(full_text, remote_content_zone)
        path.write_text(updated_text, encoding="utf-8")

    # Ein Laufzeit-Override ist strukturell nie mehr als eine Verfeinerung der Baseline "Todo"
    # (ADR 0037, Abschnitt 2) - sobald die (ggf. gerade per Merge-Erkennung finalisierte)
    # Baseline "Done" wird, wird ein noch gespeicherter Override defensiv geleert, statt
    # unveraendert fuer den naechsten Lauf stehen zu bleiben.
    carries_override = _BOARD_STATUS_BASELINE.get(status) == "Todo"
    new_entry = SyncStateEntry(
        issue_number=stored_entry.issue_number,
        item_id=stored_entry.item_id,
        pushed_state_hash=push_state_hash(
            status=status, priority=priority, content_zone=effective_local_content_zone
        ),
        pulled_body_hash=text_hash(effective_local_content_zone),
        last_synced_at=now(),
        runtime_status=stored_entry.runtime_status if carries_override else None,
        pr_number=stored_entry.pr_number if carries_override else None,
    )
    result = SpecSyncResult(
        number=number,
        title=title,
        issue_number=stored_entry.issue_number,
        classification=effective,
        priority_warning=priority_warning,
        pulled_content_zone=pulled_content_zone,
        finalized_from_pr=finalized_from_pr,
    )
    return result, new_entry


def _adopt_story_and_push_first_content(
    *,
    number: str,
    title: str,
    status: str,
    content_zone: str,
    priority: str | None,
    issue_number: int,
    item_id: str,
    gh: GhAdapter,
    project: Project,
    fields: ProjectFields,
    now: Callable[[], str],
) -> tuple[SpecSyncResult, SyncStateEntry]:
    """Story -> Feature-Spec-Uebergang (`--adopt-issue`, ADR 0036 Abschnitt 6): das bestehende
    Story-Issue/-Item wird uebernommen (kein `create_issue`/`add_item_to_project`), stattdessen
    wird die Spec zum ersten Mal als Marker+Inhalt in den bestehenden Issue-Body geschrieben.
    Bewusst NICHT ueber `_sync_one()` geloest: dessen Marker-Integritaetspruefung wuerde bei
    einem frisch adoptierten Issue (noch kein `photosort-spec`-Marker vorhanden) faelschlich
    abbrechen."""
    if status not in _VALID_STATUSES:
        raise SyncError(
            f"--adopt-issue: Spec {number} hat einen ungueltigen/unbekannten Status {status!r} "
            f"(erwartet einen von {sorted(_VALID_STATUSES)})."
        )

    is_open = status in _OPEN_STATUSES
    desired_labels: frozenset[str] = (
        frozenset({_LABEL_SUPERSEDED}) if status == "Superseded" else frozenset()
    )

    gh.edit_issue_body(issue_number, build_issue_body(number, content_zone))
    issue = gh.get_issue(issue_number)
    _apply_fields(gh, project, fields, item_id, status=status, priority=priority)
    gh.set_issue_state(issue_number, open=is_open)
    _reconcile_labels(
        gh,
        issue_number,
        current=issue.labels,
        desired=desired_labels,
        managed=_MANAGED_FEATURE_LABELS,
    )

    new_entry = SyncStateEntry(
        issue_number=issue_number,
        item_id=item_id,
        pushed_state_hash=push_state_hash(
            status=status, priority=priority, content_zone=content_zone
        ),
        pulled_body_hash=text_hash(content_zone),
        last_synced_at=now(),
    )
    result = SpecSyncResult(
        number=number, title=title, issue_number=issue_number, classification="pushed"
    )
    return result, new_entry


def run_sync(
    *,
    repo_root: Path,
    gh: GhAdapter,
    only: str | None = None,
    adopt_issue: int | None = None,
    resolutions: Mapping[str, Resolution] | None = None,
    now: Callable[[], str] = _utcnow_iso,
) -> SyncRunResult:
    resolutions = resolutions or {}
    features_dir = repo_root / "specs" / "features"
    roadmap_path = repo_root / "specs" / "roadmap.md"
    state_path = repo_root / "specs" / ".github-sync-state.json"

    gh.check_auth_scope()

    nested_state = load_state(state_path)
    roadmap_priorities = (
        parse_roadmap_priorities(roadmap_path.read_text(encoding="utf-8"))
        if roadmap_path.exists()
        else {}
    )

    only_number = _parse_only(only)

    if adopt_issue is not None:
        if only_number is None:
            raise SyncError("--adopt-issue erfordert --only NNNN (Feature-Scope) im selben Aufruf.")
        story_key = str(adopt_issue)
        validate_issue_number_key(story_key)
        if story_key not in nested_state.stories:
            raise SyncError(
                f"--adopt-issue: kein Story-State-Eintrag fuer Issue {adopt_issue} gefunden "
                "(wurde es per --create-issue/--only issue: erfasst?)."
            )
        if only_number in nested_state.features:
            raise SyncError(
                f"--adopt-issue: Spec {only_number} hat bereits einen Feature-State-Eintrag - "
                "Adoption ist nur fuer die erstmalige Spec-Anlage vorgesehen."
            )

    spec_paths = sorted(features_dir.glob("*.md")) if features_dir.exists() else []
    parsed_by_number = {}
    path_by_number: dict[str, Path] = {}
    for spec_path in spec_paths:
        parsed = parse_spec_file(spec_path)
        parsed_by_number[parsed.number] = parsed
        path_by_number[parsed.number] = spec_path

    if only_number is not None:
        if only_number not in parsed_by_number:
            raise SyncError(f"Spec {only_number} nicht unter {features_dir} gefunden.")
        feature_numbers = [only_number]
    else:
        feature_numbers = sorted(parsed_by_number)

    project = gh.ensure_project()
    fields = gh.ensure_fields(project)
    for label_name, meta in _LABEL_PROVISIONING.items():
        gh.ensure_label(label_name, description=meta["description"], color=meta["color"])

    spec_results: list[SpecSyncResult] = []
    orphaned: list[OrphanCleanup] = []
    new_features: StateDict = dict(nested_state.features)
    new_stories: dict[str, StoryStateEntry] = dict(nested_state.stories)
    adopted_result: AdoptedResult | None = None

    # try/finally statt eines einzigen Schreibvorgangs am Ende: bricht der Lauf mitten in einem
    # Mehr-Eintrags-Durchlauf ab (z.B. ein unerwarteter gh-Fehler), behalten bereits verarbeitete
    # Eintraege trotzdem ihren korrekt erreichten State (Edge Case "Abbruchresilienz").
    try:
        for number in feature_numbers:
            spec = parsed_by_number[number]
            result: SpecSyncResult
            updated_entry: SyncStateEntry | None
            if adopt_issue is not None and number == only_number:
                story_key = str(adopt_issue)
                adopted_story_entry = nested_state.stories[story_key]
                result, updated_entry = _adopt_story_and_push_first_content(
                    number=number,
                    title=spec.title,
                    status=spec.status,
                    content_zone=spec.content_zone,
                    priority=roadmap_priorities.get(number),
                    issue_number=adopted_story_entry.issue_number,
                    item_id=adopted_story_entry.item_id,
                    gh=gh,
                    project=project,
                    fields=fields,
                    now=now,
                )
                new_stories.pop(story_key, None)
                adopted_result = AdoptedResult(
                    spec_number=number, issue_number=adopted_story_entry.issue_number
                )
            else:
                result, updated_entry = _sync_one(
                    number=number,
                    title=spec.title,
                    status=spec.status,
                    content_zone=spec.content_zone,
                    full_text=spec.full_text,
                    path=path_by_number[number],
                    priority=roadmap_priorities.get(number),
                    stored_entry=nested_state.features.get(number),
                    gh=gh,
                    project=project,
                    fields=fields,
                    resolution=resolutions.get(number),
                    now=now,
                )
            spec_results.append(result)
            # updated_entry ist None, wenn eine noch nie synchronisierte Spec (kein
            # stored_entry) mit ungueltigem Status abgebrochen wurde - dann gibt es nichts zu
            # speichern, ein Retry beim naechsten Lauf bleibt moeglich.
            if updated_entry is not None:
                new_features[number] = updated_entry

        if only_number is None:
            for number in find_orphaned_numbers(
                nested_state.features, existing_numbers=set(parsed_by_number)
            ):
                orphan_entry = nested_state.features[number]
                gh.close_issue_with_comment(orphan_entry.issue_number, _ORPHAN_CLOSE_COMMENT)
                new_features.pop(number, None)
                orphaned.append(
                    OrphanCleanup(number=number, issue_number=orphan_entry.issue_number)
                )

            # Batch-Prioritaets-Push fuer issue-referenzierte Roadmap-Zeilen (ADR 0036,
            # Abschnitt 5): faengt manuelle Prioritaets-Aenderungen in roadmap.md zwischen
            # gezielten `--only issue:NNN`-Aufrufen ab. Status/Body bleiben unangetastet - nur
            # eine bereits per --create-issue/--only issue: erfasste Story (State-Eintrag
            # vorhanden) wird beruecksichtigt, alles andere wird stillschweigend uebersprungen.
            for key, priority in roadmap_priorities.items():
                if not key.startswith(_ISSUE_ONLY_PREFIX):
                    continue
                story_key = key[len(_ISSUE_ONLY_PREFIX) :]
                batch_story_entry = new_stories.get(story_key)
                if batch_story_entry is None:
                    continue
                _apply_priority_only(gh, project, fields, batch_story_entry.item_id, priority)
                new_stories[story_key] = StoryStateEntry(
                    issue_number=batch_story_entry.issue_number,
                    item_id=batch_story_entry.item_id,
                    last_synced_at=now(),
                )
    finally:
        save_state(state_path, NestedState(features=new_features, stories=new_stories))

    return SyncRunResult(specs=spec_results, orphaned=orphaned, adopted=adopted_result)


def _find_spec_path(features_dir: Path, spec_number: str) -> Path:
    if features_dir.exists():
        for candidate in sorted(features_dir.glob(f"{spec_number}-*.md")):
            return candidate
    raise SyncError(f"Spec {spec_number} nicht unter {features_dir} gefunden.")


def set_feature_runtime_status(
    *,
    repo_root: Path,
    gh: GhAdapter,
    spec_number: str,
    runtime_status: str,
    pr_number: int | None = None,
    now: Callable[[], str] = _utcnow_iso,
) -> dict[str, object]:
    """`--only NNNN --runtime-status {In Progress,Review} [--pr-number NNN]` (ADR 0037, Abschnitt
    3/4): leichtgewichtiger, zielgerichteter Schreibzugriff auf eine bereits getrackte
    Feature-Spec - laedt die Spec-Datei nur zur Bestimmung der Baseline, pusht Status+Prioritaet
    ueber _apply_fields(), kein voller bidirektionaler Content-Abgleich (kein Pull/Konflikt-
    Handling, Hashes im State-Eintrag bleiben unangetastet)."""
    validate_spec_number(spec_number)
    if runtime_status not in _RUNTIME_OVERRIDE_STATUSES:
        raise SyncError(
            f"Ungueltiger Laufzeit-Status {runtime_status!r} (erwartet einen von "
            f"{sorted(_RUNTIME_OVERRIDE_STATUSES)})."
        )

    state_path = repo_root / "specs" / ".github-sync-state.json"
    features_dir = repo_root / "specs" / "features"
    roadmap_path = repo_root / "specs" / "roadmap.md"

    gh.check_auth_scope()
    nested_state = load_state(state_path)
    stored_entry = nested_state.features.get(spec_number)
    if stored_entry is None:
        raise SyncError(
            f"Spec {spec_number} hat noch keinen Feature-State-Eintrag - erst ueber einen "
            "regulaeren Sync-Lauf (--only NNNN oder voller Lauf) anlegen."
        )

    parsed = parse_spec_file(_find_spec_path(features_dir, spec_number))
    baseline = _BOARD_STATUS_BASELINE.get(parsed.status)
    if baseline != "Todo":
        raise SyncError(
            f"Spec {spec_number} hat Datei-Status {parsed.status!r} (Baseline {baseline!r}) - "
            "ein Laufzeit-Override ist nur wirksam, solange die Baseline 'Todo' ist "
            "(Datei-Status Proposed/Accepted)."
        )

    project = gh.ensure_project()
    fields = gh.ensure_fields(project)

    roadmap_priorities = (
        parse_roadmap_priorities(roadmap_path.read_text(encoding="utf-8"))
        if roadmap_path.exists()
        else {}
    )
    priority = roadmap_priorities.get(spec_number)

    _apply_fields(
        gh,
        project,
        fields,
        stored_entry.item_id,
        status=parsed.status,
        priority=priority,
        runtime_status=runtime_status,
    )

    new_entry = SyncStateEntry(
        issue_number=stored_entry.issue_number,
        item_id=stored_entry.item_id,
        pushed_state_hash=stored_entry.pushed_state_hash,
        pulled_body_hash=stored_entry.pulled_body_hash,
        last_synced_at=now(),
        runtime_status=runtime_status,
        pr_number=pr_number,
    )
    new_features = dict(nested_state.features)
    new_features[spec_number] = new_entry
    save_state(state_path, NestedState(features=new_features, stories=nested_state.stories))

    return {"spec_number": spec_number, "runtime_status": runtime_status, "pr_number": pr_number}


# -- Dateiloser Story-Pfad (Spec 0059 / ADR 0036, Abschnitt 5) ---------------------------------


def create_story_issue(
    *,
    repo_root: Path,
    gh: GhAdapter,
    typ: str,
    title: str,
    body: str,
    now: Callable[[], str] = _utcnow_iso,
) -> int:
    """`--create-issue`: legt ein neues, dateiloses Story-Issue an (Status Unrefined). Verwendet
    von `capture` und der einmaligen Alteintrags-Migration."""
    if typ not in _STORY_TYPE_TO_LABEL:
        raise SyncError(
            f"Unbekannter Typ {typ!r} (erwartet einen von {sorted(_STORY_TYPE_TO_LABEL)})."
        )

    state_path = repo_root / "specs" / ".github-sync-state.json"
    gh.check_auth_scope()
    nested_state = load_state(state_path)

    project = gh.ensure_project()
    fields = gh.ensure_fields(project)
    for label_name, meta in _LABEL_PROVISIONING.items():
        gh.ensure_label(label_name, description=meta["description"], color=meta["color"])

    issue_number = gh.create_issue(title, body)
    issue = gh.get_issue(issue_number)
    item_id = gh.add_item_to_project(project, issue_url=issue.url)
    _apply_status_only(gh, project, fields, item_id, status="Unrefined")
    gh.set_issue_state(issue_number, open=True)
    desired_label = _STORY_TYPE_TO_LABEL[typ]
    _reconcile_labels(
        gh,
        issue_number,
        current=issue.labels,
        desired=frozenset({desired_label}),
        managed=_MANAGED_STORY_LABELS,
    )

    new_stories = dict(nested_state.stories)
    new_stories[str(issue_number)] = StoryStateEntry(
        issue_number=issue_number, item_id=item_id, last_synced_at=now()
    )
    save_state(state_path, NestedState(features=nested_state.features, stories=new_stories))
    return issue_number


def _get_story_entry(nested_state: NestedState, issue_number: int) -> StoryStateEntry:
    key = str(issue_number)
    entry = nested_state.stories.get(key)
    if entry is not None:
        return entry

    adopted_spec_number = next(
        (
            number
            for number, feature_entry in nested_state.features.items()
            if feature_entry.issue_number == issue_number
        ),
        None,
    )
    if adopted_spec_number is not None:
        raise SyncError(
            f"Issue {issue_number} ist bereits Spec {adopted_spec_number} (per --adopt-issue "
            "adoptiert) - Story-Scope-Befehle sind dafuer nicht mehr gueltig."
        )
    raise SyncError(
        f"Story-Issue {issue_number} nicht im stories-Namensraum gefunden - wurde es per "
        "--create-issue angelegt?"
    )


def sync_story(
    *,
    repo_root: Path,
    gh: GhAdapter,
    issue_number: int,
    status: str | None = None,
    body: str | None = None,
    now: Callable[[], str] = _utcnow_iso,
) -> dict[str, object]:
    """`--only issue:NNN [--status ...] [--body-file ...]`: aktualisiert optional Body/Status
    eines bestehenden Story-Issues und pusht in jedem Fall die aus roadmap.md neu berechnete
    Prioritaet (Einbahnstrasse, ADR 0017 Abschnitt 4, hier auf die Story-Stufe uebertragen)."""
    if status is not None and status not in _STORY_VALID_STATUSES:
        # Seit Spec 0060 / ADR 0037, Abschnitt 6: verengt auf {"Unrefined", "Ready", "Done"} -
        # die drei neuen Feature-only-Werte (Todo/In Progress/Review) ergeben fuer eine Story
        # keinen Sinn (kein Baseline/Override-Modell auf Story-Ebene).
        raise SyncError(
            f"Unbekannter Story-Status {status!r} (erwartet einen von "
            f"{sorted(_STORY_VALID_STATUSES)})."
        )

    state_path = repo_root / "specs" / ".github-sync-state.json"
    roadmap_path = repo_root / "specs" / "roadmap.md"

    gh.check_auth_scope()
    nested_state = load_state(state_path)
    entry = _get_story_entry(nested_state, issue_number)

    project = gh.ensure_project()
    fields = gh.ensure_fields(project)

    if body is not None:
        gh.edit_issue_body(issue_number, body)
    if status is not None:
        _apply_status_only(gh, project, fields, entry.item_id, status=status)
        if status == "Done":
            # Abschnitt 6: eine ohne technische Umsetzung verworfene/obsolet gewordene Story
            # wird zusaetzlich geschlossen (der Doppelbedeutung "fertig umgesetzt" vs.
            # "verworfen" wird bewusst nicht mit einem eigenen Statuswert begegnet).
            gh.set_issue_state(issue_number, open=False)

    roadmap_priorities = (
        parse_roadmap_priorities(roadmap_path.read_text(encoding="utf-8"))
        if roadmap_path.exists()
        else {}
    )
    priority = roadmap_priorities.get(f"{_ISSUE_ONLY_PREFIX}{issue_number}")
    _apply_priority_only(gh, project, fields, entry.item_id, priority)

    new_stories = dict(nested_state.stories)
    new_stories[str(issue_number)] = StoryStateEntry(
        issue_number=issue_number, item_id=entry.item_id, last_synced_at=now()
    )
    save_state(state_path, NestedState(features=nested_state.features, stories=new_stories))

    return {"issue_number": issue_number, "status": status, "priority": priority}


def show_story_status(*, repo_root: Path, gh: GhAdapter, issue_number: int) -> str | None:
    """`--only issue:NNN --show-status`: rein lesend, veraendert nichts."""
    state_path = repo_root / "specs" / ".github-sync-state.json"
    gh.check_auth_scope()
    nested_state = load_state(state_path)
    entry = _get_story_entry(nested_state, issue_number)

    project = gh.ensure_project()
    gh.ensure_fields(project)  # stellt sicher, dass ProjectFields (Fake und real) initialisiert ist
    return gh.get_item_field_value(project, item_id=entry.item_id, field_name=STATUS_FIELD_NAME)
