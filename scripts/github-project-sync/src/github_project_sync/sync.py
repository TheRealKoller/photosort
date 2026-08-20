"""Orchestrierung des vollen Zwei-Wege-Sync-Laufs (ein oder alle specs/features/*.md).

Verdrahtet die reinen Bausteine (spec_parser, roadmap_parser, hashing, classify, issue_body,
state) mit dem GhAdapter-Protokoll. Siehe specs/features/0031-zweiwege-sync-specs-github-projekt.md
und ADR decisions/0017-github-projects-v2-spec-sync.md.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from github_project_sync.classify import SyncClassification, SyncStateEntry, classify
from github_project_sync.gh_adapter import GhAdapter, ProjectFields
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
    validate_spec_number,
)
from github_project_sync.state import find_orphaned_numbers, load_state, save_state

Resolution = Literal["keep_spec", "keep_issue"]

_OPEN_STATUSES = {"Proposed", "Accepted"}
_CLOSED_STATUSES = {"Implemented", "Superseded"}
_VALID_STATUSES = _OPEN_STATUSES | _CLOSED_STATUSES

_ORPHAN_CLOSE_COMMENT = "Spec-Datei wurde entfernt."


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


@dataclass(frozen=True)
class OrphanCleanup:
    number: str
    issue_number: int


@dataclass(frozen=True)
class SyncRunResult:
    specs: list[SpecSyncResult]
    orphaned: list[OrphanCleanup]

    @property
    def pulled(self) -> list[SpecSyncResult]:
        return [r for r in self.specs if r.classification == "pulled"]

    @property
    def conflicts(self) -> list[SpecSyncResult]:
        return [r for r in self.specs if r.classification == "conflict"]


def _apply_fields(
    gh: GhAdapter,
    project: object,
    fields: ProjectFields,
    item_id: str,
    *,
    status: str,
    priority: str | None,
) -> None:
    status_option_id = fields.status_options.get(status)
    if status_option_id is not None:
        gh.set_item_single_select(
            project, item_id=item_id, field_id=fields.status_field_id, option_id=status_option_id
        )

    priority_option_id = fields.priority_options.get(priority) if priority is not None else None
    if priority_option_id is not None:
        gh.set_item_single_select(
            project,
            item_id=item_id,
            field_id=fields.priority_field_id,
            option_id=priority_option_id,
        )
    else:
        gh.clear_item_field(project, item_id=item_id, field_id=fields.priority_field_id)


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
    project: object,
    fields: ProjectFields,
    resolution: Resolution | None,
    now: Callable[[], str],
) -> tuple[SpecSyncResult, SyncStateEntry | None]:
    if status not in _VALID_STATUSES:
        raise SyncError(f"Spec {number}: unbekannter Status {status!r}.")

    priority_warning = None
    if priority is None and status in _OPEN_STATUSES:
        priority_warning = (
            f"Spec {number} ({status}) taucht in keiner Prioritaets-Tabelle von "
            "specs/roadmap.md auf."
        )

    push_hash_now = push_state_hash(status=status, priority=priority, content_zone=content_zone)
    issue_title = f"[{number}] {title}"
    is_open = status in _OPEN_STATUSES

    if stored_entry is None:
        body = build_issue_body(number, content_zone)
        issue_number = gh.create_issue(issue_title, body)
        issue = gh.get_issue(issue_number)
        item_id = gh.add_item_to_project(project, issue_url=issue.url)
        _apply_fields(gh, project, fields, item_id, status=status, priority=priority)
        gh.set_issue_state(issue_number, open=is_open)

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
    # Issue wieder zurueck, siehe Akzeptanzkriterium "Status-Feld + Issue-Zustand").
    _apply_fields(gh, project, fields, stored_entry.item_id, status=status, priority=priority)
    gh.set_issue_state(stored_entry.issue_number, open=is_open)

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

    new_entry = SyncStateEntry(
        issue_number=stored_entry.issue_number,
        item_id=stored_entry.item_id,
        pushed_state_hash=push_state_hash(
            status=status, priority=priority, content_zone=effective_local_content_zone
        ),
        pulled_body_hash=text_hash(effective_local_content_zone),
        last_synced_at=now(),
    )
    result = SpecSyncResult(
        number=number,
        title=title,
        issue_number=stored_entry.issue_number,
        classification=effective,
        priority_warning=priority_warning,
        pulled_content_zone=pulled_content_zone,
    )
    return result, new_entry


def run_sync(
    *,
    repo_root: Path,
    gh: GhAdapter,
    only: str | None = None,
    resolutions: Mapping[str, Resolution] | None = None,
    now: Callable[[], str] = _utcnow_iso,
) -> SyncRunResult:
    resolutions = resolutions or {}
    features_dir = repo_root / "specs" / "features"
    roadmap_path = repo_root / "specs" / "roadmap.md"
    state_path = repo_root / "specs" / ".github-sync-state.json"

    gh.check_auth_scope()

    state = load_state(state_path)
    roadmap_priorities = (
        parse_roadmap_priorities(roadmap_path.read_text(encoding="utf-8"))
        if roadmap_path.exists()
        else {}
    )

    spec_paths = sorted(features_dir.glob("*.md")) if features_dir.exists() else []
    parsed_by_number = {}
    path_by_number: dict[str, Path] = {}
    for spec_path in spec_paths:
        parsed = parse_spec_file(spec_path)
        parsed_by_number[parsed.number] = parsed
        path_by_number[parsed.number] = spec_path

    if only is not None:
        validate_spec_number(only)
        if only not in parsed_by_number:
            raise SyncError(f"Spec {only} nicht unter {features_dir} gefunden.")
        target_numbers = [only]
    else:
        target_numbers = sorted(parsed_by_number)

    project = gh.ensure_project()
    fields = gh.ensure_fields(project)

    results: list[SpecSyncResult] = []
    orphaned: list[OrphanCleanup] = []
    new_state = dict(state)

    # try/finally statt eines einzigen Schreibvorgangs am Ende: bricht der Lauf mitten in einem
    # Mehr-Spec-Durchlauf ab (z.B. ein unerwarteter gh-Fehler), behalten bereits verarbeitete
    # Specs trotzdem ihren korrekten, bereits erreichten State (Edge Case "Abbruchresilienz" aus
    # der Teststrategie in Spec 0031) statt verloren zu gehen.
    try:
        for number in target_numbers:
            spec = parsed_by_number[number]
            result, updated_entry = _sync_one(
                number=number,
                title=spec.title,
                status=spec.status,
                content_zone=spec.content_zone,
                full_text=spec.full_text,
                path=path_by_number[number],
                priority=roadmap_priorities.get(number),
                stored_entry=state.get(number),
                gh=gh,
                project=project,
                fields=fields,
                resolution=resolutions.get(number),
                now=now,
            )
            results.append(result)
            if updated_entry is not None:
                new_state[number] = updated_entry
            else:
                new_state.pop(number, None)

        if only is None:
            for number in find_orphaned_numbers(state, existing_numbers=set(parsed_by_number)):
                entry = state[number]
                gh.close_issue_with_comment(entry.issue_number, _ORPHAN_CLOSE_COMMENT)
                new_state.pop(number, None)
                orphaned.append(OrphanCleanup(number=number, issue_number=entry.issue_number))
    finally:
        save_state(state_path, new_state)

    return SyncRunResult(specs=results, orphaned=orphaned)
