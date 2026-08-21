"""Orchestrierung des vollen Zwei-Wege-Sync-Laufs (Feature-Specs UND Inbox-Eintraege).

Verdrahtet die reinen Bausteine (spec_parser, inbox_parser, roadmap_parser, hashing, classify,
issue_body, state) mit dem GhAdapter-Protokoll. Siehe
specs/features/0031-zweiwege-sync-specs-github-projekt.md,
specs/features/0052-github-sync-natives-status-feld-inbox-einbindung.md und
ADR decisions/0017-github-projects-v2-spec-sync.md /
ADR decisions/0030-github-sync-natives-status-feld-inbox-einbindung.md.

Seit Spec 0052 gibt es zwei eigene Sync-Pfade (_sync_one fuer Feature-Specs, _sync_one_inbox fuer
Inbox-Eintraege) statt eines gemeinsamen, generischen Pfads - beide Entitaeten unterscheiden sich
strukturell genug (Prioritaet/Superseded-Feldleerung nur bei Features, Typ/Label nur bei Inbox,
Unrefined = immer offener Issue-Zustand), dass eine erzwungene Vereinheitlichung mehr Komplexitaet
als Nutzen gebracht haette (siehe Spec 0052, Architektur/Umsetzung: "eigener Inbox-Sync-Pfad").
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from github_project_sync.classify import SyncClassification, SyncStateEntry, classify
from github_project_sync.gh_adapter import GhAdapter, Project, ProjectFields
from github_project_sync.hashing import push_state_hash, push_state_hash_inbox, text_hash
from github_project_sync.inbox_parser import (
    VALID_INBOX_STATUSES,
    VALID_INBOX_TYPES,
    parse_inbox_file,
)
from github_project_sync.issue_body import (
    build_inbox_issue_body,
    build_issue_body,
    extract_content_zone_from_issue_body,
    parse_inbox_marker,
    parse_marker,
)
from github_project_sync.roadmap_parser import parse_roadmap_priorities
from github_project_sync.spec_parser import (
    parse_spec_file,
    replace_content_zone,
    validate_spec_number,
)
from github_project_sync.state import (
    NestedState,
    StateDict,
    find_orphaned_numbers,
    load_state,
    save_state,
)

Resolution = Literal["keep_spec", "keep_issue"]
_OnlyKind = Literal["feature", "inbox"]

_OPEN_STATUSES = {"Proposed", "Accepted"}
_CLOSED_STATUSES = {"Implemented", "Superseded"}
_VALID_STATUSES = _OPEN_STATUSES | _CLOSED_STATUSES

_ORPHAN_CLOSE_COMMENT = "Spec-Datei wurde entfernt."
_ORPHAN_CLOSE_COMMENT_INBOX = "Inbox-Eintrag wurde entfernt."

_INBOX_ONLY_PREFIX = "inbox:"

# Labels: Superseded verschwindet als Feldwert und wird stattdessen ein Label (ADR 0030,
# Abschnitt 2); Idee/Bug bilden den Inbox-**Typ:** ab (ADR 0030, Abschnitt 6). "bug" existiert im
# Repo bereits (wiederverwendet statt eines eigenen, spezifischeren Labels) - ensure_label() ist
# trotzdem idempotent-sicher fuer alle drei, daher einheitlich fuer alle drei aufgerufen.
_LABEL_SUPERSEDED = "superseded"
_LABEL_IDEE = "idee"
_LABEL_BUG = "bug"
_MANAGED_FEATURE_LABELS: frozenset[str] = frozenset({_LABEL_SUPERSEDED})
_MANAGED_INBOX_LABELS: frozenset[str] = frozenset({_LABEL_IDEE, _LABEL_BUG})
_TYPE_TO_LABEL = {"Idee": _LABEL_IDEE, "Bug (vermeintlich)": _LABEL_BUG}
_LABEL_PROVISIONING = {
    _LABEL_SUPERSEDED: {
        "description": "Spec wurde durch eine neuere abgeloest.",
        "color": "cfd3d7",
    },
    _LABEL_IDEE: {
        "description": "Inbox-Eintrag: neue Idee, noch ungeschaerft.",
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


@dataclass(frozen=True)
class InboxSyncResult:
    number: str
    title: str
    issue_number: int | None
    classification: SyncClassification | None
    aborted_reason: str | None = None
    conflict: ConflictDiff | None = None
    pulled_content_zone: str | None = None


@dataclass(frozen=True)
class OrphanCleanup:
    number: str
    issue_number: int


@dataclass(frozen=True)
class SupersedeResult:
    inbox_number: str
    inbox_issue_number: int
    new_issue_number: int


@dataclass(frozen=True)
class SyncRunResult:
    specs: list[SpecSyncResult]
    orphaned: list[OrphanCleanup]
    inbox: list[InboxSyncResult]
    orphaned_inbox: list[OrphanCleanup]
    supersede: SupersedeResult | None = None


def _parse_only(value: str | None) -> tuple[_OnlyKind, str] | None:
    """Liefert (kind, number) mit kind in {"feature", "inbox"}, oder None fuer einen vollen Lauf.

    Bare "NNNN" bleibt rueckwaertskompatibel Feature-Scope (ADR 0030, Abschnitt 7); "inbox:NNNN"
    adressiert einen einzelnen Inbox-Eintrag. Beide Faelle nutzen dieselbe, parametrisierte
    Nummernvalidierung wie die Pfadkonstruktion selbst (kein zweiter, unabhaengig driftender
    Regex).
    """
    if value is None:
        return None
    if value.startswith(_INBOX_ONLY_PREFIX):
        number = value[len(_INBOX_ONLY_PREFIX) :]
        validate_spec_number(number)
        return ("inbox", number)
    validate_spec_number(value)
    return ("feature", value)


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


def _apply_fields(
    gh: GhAdapter,
    project: Project,
    fields: ProjectFields,
    item_id: str,
    *,
    status: str,
    priority: str | None,
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
        # bereits bestehende Leeren des Prioritaets-Felds unten.
        gh.clear_item_field(project, item_id=item_id, field_id=fields.status_field_id)
    else:
        status_option_id = fields.status_options.get(status)
        if status_option_id is None:
            raise SyncError(
                f"Project-Feld 'Status' hat keine Option fuer {status!r} (vorhanden: "
                f"{sorted(fields.status_options)}). Vermutlich wurden die Feld-Optionen manuell "
                "im GitHub Project veraendert - bitte das Status-Feld reparieren, bevor der "
                "Sync erneut laeuft."
            )
        gh.set_item_single_select(
            project, item_id=item_id, field_id=fields.status_field_id, option_id=status_option_id
        )

    if priority is None:
        # Implemented/Superseded-Specs haben laut Design keine Prioritaet - Feld bewusst leeren.
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
    """Wie _apply_fields, aber ohne jede Beruehrung des Prioritaets-Felds (Inbox-Eintraege haben
    laut Design keine Prioritaet - nie gesetzt, nicht aktiv geleert, siehe Spec 0052 AK
    "Inbox 1:1-Sync")."""
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
    if status not in _VALID_STATUSES:
        # Wie bei einem Marker-Integritaetsbruch (siehe unten): ein Problem, das nur diese eine
        # Spec betrifft, darf nicht den gesamten Mehr-Spec-Lauf mit einer laufabbrechenden
        # SyncError toeten (Akzeptanzkriterium "Marker-Integritaet": andere Specs im selben Lauf
        # laufen unbeeinflusst weiter). Bug gefunden im zweiten manuellen Sync-Lauf gegen echtes
        # GitHub nach Merge von PR #117 - ein einzelner unerwarteter Statuswert (z.B. weil
        # spec_parser trotz seines Fixes doch mal mehr als das Enum-Schluesselwort erfasst) brach
        # bisher via "raise SyncError" den kompletten Lauf ab, bevor irgendeine andere Spec
        # verarbeitet wurde. stored_entry (falls vorhanden) bleibt unveraendert; fuer eine noch
        # nie synchronisierte Spec (stored_entry is None) gibt es naturgemaess nichts zu bewahren.
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
    # implementiert: er greift nur, wenn ein Spec<->Issue-Match ueber einen Such-/Lookup-Pfad
    # (Titel/Marker ueber die gesamte Repo-Issue-Liste) zustande kommt - genau diesen Pfad gibt
    # es im GhAdapter-Protokoll strukturell nicht (siehe AC "Fremd-Issues": Zuordnung
    # ausschliesslich ueber den hier bereits vorliegenden stored_entry.issue_number). Fehlt ein
    # State-Eintrag komplett (stored_entry is None, siehe Zweig oben), wird immer ein neues
    # Issue angelegt (create_issue), nie ein bestehendes fremdes adoptiert - der Angriffspfad,
    # den der Fallback abdecken soll, existiert also gar nicht erst. `IssueView.author_login`
    # wird deshalb aktuell nicht ausgewertet; er ist fuer eine etwaige kuenftige Erweiterung des
    # Lookups vorgehalten (siehe gh_adapter.py), keine unbeabsichtigte Luecke.
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
    # Issue wieder zurueck, siehe Akzeptanzkriterium "Status-Feld + Issue-Zustand"). Labels
    # (superseded) werden aus demselben Grund ebenfalls unabhaengig von der Klassifikation
    # reconciled (ADR 0030, Abschnitt 6: "pro Sync-Lauf voll reconciled").
    _apply_fields(gh, project, fields, stored_entry.item_id, status=status, priority=priority)
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


def _sync_one_inbox(
    *,
    number: str,
    title: str,
    status: str,
    typ: str,
    content_zone: str,
    full_text: str,
    path: Path,
    stored_entry: SyncStateEntry | None,
    gh: GhAdapter,
    project: Project,
    fields: ProjectFields,
    resolution: Resolution | None,
    now: Callable[[], str],
) -> tuple[InboxSyncResult, SyncStateEntry | None]:
    if status not in VALID_INBOX_STATUSES or typ not in VALID_INBOX_TYPES:
        reasons = []
        if status not in VALID_INBOX_STATUSES:
            reasons.append(
                f"unbekannter/ungueltiger Status {status!r} (erwartet 'Unrefined')"
            )
        if typ not in VALID_INBOX_TYPES:
            reasons.append(
                f"unbekannter Typ {typ!r} (erwartet einen von {sorted(VALID_INBOX_TYPES)})"
            )
        result = InboxSyncResult(
            number=number,
            title=title,
            issue_number=stored_entry.issue_number if stored_entry is not None else None,
            classification=None,
            aborted_reason=(
                "; ".join(reasons) + ". Sync fuer diesen Inbox-Eintrag abgebrochen, andere "
                "Eintraege sind unbeeinflusst."
            ),
        )
        return result, stored_entry

    push_hash_now = push_state_hash_inbox(status=status, typ=typ, content_zone=content_zone)
    issue_title = f"[inbox/{number}] {title}"
    desired_label = _TYPE_TO_LABEL[typ]

    if stored_entry is None:
        body = build_inbox_issue_body(number, content_zone)
        issue_number = gh.create_issue(issue_title, body)
        issue = gh.get_issue(issue_number)
        item_id = gh.add_item_to_project(project, issue_url=issue.url)
        _apply_status_only(gh, project, fields, item_id, status=status)
        gh.set_issue_state(issue_number, open=True)  # Unrefined = immer offener Issue-Zustand
        _reconcile_labels(
            gh,
            issue_number,
            current=issue.labels,
            desired=frozenset({desired_label}),
            managed=_MANAGED_INBOX_LABELS,
        )

        new_entry = SyncStateEntry(
            issue_number=issue_number,
            item_id=item_id,
            pushed_state_hash=push_hash_now,
            pulled_body_hash=text_hash(content_zone),
            last_synced_at=now(),
        )
        result = InboxSyncResult(
            number=number, title=title, issue_number=issue_number, classification="created"
        )
        return result, new_entry

    issue = gh.get_issue(stored_entry.issue_number)
    marker_number = parse_inbox_marker(issue.body)
    if marker_number != number:
        result = InboxSyncResult(
            number=number,
            title=title,
            issue_number=stored_entry.issue_number,
            classification=None,
            aborted_reason=(
                f"Marker-Integritaet verletzt: Issue #{stored_entry.issue_number} enthaelt "
                f"keinen zu Inbox-Eintrag {number} passenden photosort-inbox-Marker (gefunden: "
                f"{marker_number!r}). Sync fuer diesen Eintrag abgebrochen, andere Eintraege "
                "sind unbeeinflusst."
            ),
        )
        return result, stored_entry

    remote_content_zone = extract_content_zone_from_issue_body(issue.body)
    pull_hash_now = text_hash(remote_content_zone)
    classification = classify(
        stored_entry, push_hash_now=push_hash_now, pull_hash_now=pull_hash_now
    )

    _apply_status_only(gh, project, fields, stored_entry.item_id, status=status)
    gh.set_issue_state(stored_entry.issue_number, open=True)
    _reconcile_labels(
        gh,
        stored_entry.issue_number,
        current=issue.labels,
        desired=frozenset({desired_label}),
        managed=_MANAGED_INBOX_LABELS,
    )

    if classification == "conflict" and resolution is None:
        result = InboxSyncResult(
            number=number,
            title=title,
            issue_number=stored_entry.issue_number,
            classification="conflict",
            conflict=ConflictDiff(
                local_content_zone=content_zone, remote_content_zone=remote_content_zone
            ),
        )
        return result, stored_entry

    effective: SyncClassification = classification
    if classification == "conflict" and resolution == "keep_spec":
        effective = "pushed"
    elif classification == "conflict" and resolution == "keep_issue":
        effective = "pulled"

    pulled_content_zone: str | None = None
    effective_local_content_zone = content_zone

    if effective == "pushed":
        gh.edit_issue_body(
            stored_entry.issue_number, build_inbox_issue_body(number, content_zone)
        )
    elif effective == "pulled":
        pulled_content_zone = remote_content_zone
        effective_local_content_zone = remote_content_zone
        updated_text = replace_content_zone(full_text, remote_content_zone)
        path.write_text(updated_text, encoding="utf-8")

    new_entry = SyncStateEntry(
        issue_number=stored_entry.issue_number,
        item_id=stored_entry.item_id,
        pushed_state_hash=push_state_hash_inbox(
            status=status, typ=typ, content_zone=effective_local_content_zone
        ),
        pulled_body_hash=text_hash(effective_local_content_zone),
        last_synced_at=now(),
    )
    result = InboxSyncResult(
        number=number,
        title=title,
        issue_number=stored_entry.issue_number,
        classification=effective,
        pulled_content_zone=pulled_content_zone,
    )
    return result, new_entry


def run_sync(
    *,
    repo_root: Path,
    gh: GhAdapter,
    only: str | None = None,
    supersede_inbox: str | None = None,
    resolutions: Mapping[str, Resolution] | None = None,
    now: Callable[[], str] = _utcnow_iso,
) -> SyncRunResult:
    """resolutions ist bewusst NICHT nach Namespace praefixiert (nackte Nummer als Key, geteilt
    zwischen _sync_one() und _sync_one_inbox() via resolutions.get(number)). Bei einer echten
    Nummernkollision (inbox/NNNN + features/NNNN, siehe issue_body.py) mit Konflikt auf BEIDEN
    Seiten im selben Voll-Lauf wuerde dieselbe Aufloesung unbeabsichtigt auf beide wirken - siehe
    cli.py::_parse_resolutions() fuer die ausfuehrliche Begruendung, warum das in der Praxis
    unkritisch ist (Konfliktaufloesung laeuft immer ueber einen auf --only gescopten Aufruf)."""
    resolutions = resolutions or {}
    features_dir = repo_root / "specs" / "features"
    inbox_dir = repo_root / "specs" / "inbox"
    roadmap_path = repo_root / "specs" / "roadmap.md"
    state_path = repo_root / "specs" / ".github-sync-state.json"

    gh.check_auth_scope()

    nested_state = load_state(state_path)
    roadmap_priorities = (
        parse_roadmap_priorities(roadmap_path.read_text(encoding="utf-8"))
        if roadmap_path.exists()
        else {}
    )

    only_scope = _parse_only(only)

    if supersede_inbox is not None:
        validate_spec_number(supersede_inbox)
        if only_scope is None or only_scope[0] != "feature":
            raise SyncError(
                "--supersede-inbox erfordert --only NNNN (Feature-Scope, kein inbox:-Praefix) "
                "im selben Aufruf."
            )
        if supersede_inbox not in nested_state.inbox:
            raise SyncError(
                f"--supersede-inbox: kein State-Eintrag fuer Inbox-Eintrag {supersede_inbox} "
                "gefunden."
            )

    process_features = only_scope is None or only_scope[0] == "feature"
    process_inbox = only_scope is None or only_scope[0] == "inbox"

    # Copilot-Review-Finding (PR #173): beide Parsing-Schleifen NUR ausfuehren, wenn der
    # jeweilige Entitaetstyp im aktuellen Lauf tatsaechlich gebraucht wird (process_features/
    # process_inbox) - vorher wurden bei einem auf einen Typ gescopten --only-Lauf trotzdem
    # BEIDE Verzeichnisse eager geparst, sodass ein einzelner strukturell kaputter Eintrag des
    # gerade IRRELEVANTEN Typs (parse_spec_file()/parse_inbox_file() werfen ungefangen
    # SpecParseError) auch diesen Lauf zum Absturz gebracht haette, obwohl dieser Typ gar nicht
    # verarbeitet wird. Symmetrisch fuer beide Richtungen behoben, nicht nur fuer Inbox.
    spec_paths = (
        sorted(features_dir.glob("*.md")) if process_features and features_dir.exists() else []
    )
    parsed_by_number = {}
    path_by_number: dict[str, Path] = {}
    for spec_path in spec_paths:
        parsed = parse_spec_file(spec_path)
        parsed_by_number[parsed.number] = parsed
        path_by_number[parsed.number] = spec_path

    inbox_paths = (
        sorted(inbox_dir.glob("*.md")) if process_inbox and inbox_dir.exists() else []
    )
    inbox_by_number = {}
    inbox_path_by_number: dict[str, Path] = {}
    for inbox_path in inbox_paths:
        parsed_inbox = parse_inbox_file(inbox_path)
        inbox_by_number[parsed_inbox.number] = parsed_inbox
        inbox_path_by_number[parsed_inbox.number] = inbox_path

    if only_scope is not None and only_scope[0] == "feature":
        if only_scope[1] not in parsed_by_number:
            raise SyncError(f"Spec {only_scope[1]} nicht unter {features_dir} gefunden.")
        feature_numbers = [only_scope[1]]
    else:
        feature_numbers = sorted(parsed_by_number) if process_features else []

    if only_scope is not None and only_scope[0] == "inbox":
        if only_scope[1] not in inbox_by_number:
            raise SyncError(f"Inbox-Eintrag {only_scope[1]} nicht unter {inbox_dir} gefunden.")
        inbox_numbers = [only_scope[1]]
    else:
        inbox_numbers = sorted(inbox_by_number) if process_inbox else []

    project = gh.ensure_project()
    fields = gh.ensure_fields(project)
    for label_name, meta in _LABEL_PROVISIONING.items():
        gh.ensure_label(label_name, description=meta["description"], color=meta["color"])

    spec_results: list[SpecSyncResult] = []
    inbox_results: list[InboxSyncResult] = []
    orphaned: list[OrphanCleanup] = []
    orphaned_inbox: list[OrphanCleanup] = []
    new_features: StateDict = dict(nested_state.features)
    new_inbox: StateDict = dict(nested_state.inbox)
    supersede_result: SupersedeResult | None = None

    # try/finally statt eines einzigen Schreibvorgangs am Ende: bricht der Lauf mitten in einem
    # Mehr-Eintrags-Durchlauf ab (z.B. ein unerwarteter gh-Fehler), behalten bereits verarbeitete
    # Eintraege trotzdem ihren korrekt erreichten State (Edge Case "Abbruchresilienz").
    try:
        for number in feature_numbers:
            spec = parsed_by_number[number]
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

        for number in inbox_numbers:
            entry = inbox_by_number[number]
            result_inbox, updated_inbox_entry = _sync_one_inbox(
                number=number,
                title=entry.title,
                status=entry.status,
                typ=entry.typ,
                content_zone=entry.content_zone,
                full_text=entry.full_text,
                path=inbox_path_by_number[number],
                stored_entry=nested_state.inbox.get(number),
                gh=gh,
                project=project,
                fields=fields,
                resolution=resolutions.get(number),
                now=now,
            )
            inbox_results.append(result_inbox)
            if updated_inbox_entry is not None:
                new_inbox[number] = updated_inbox_entry

        if only_scope is None:
            for number in find_orphaned_numbers(
                nested_state.features, existing_numbers=set(parsed_by_number)
            ):
                orphan_entry = nested_state.features[number]
                gh.close_issue_with_comment(orphan_entry.issue_number, _ORPHAN_CLOSE_COMMENT)
                new_features.pop(number, None)
                orphaned.append(
                    OrphanCleanup(number=number, issue_number=orphan_entry.issue_number)
                )

            for number in find_orphaned_numbers(
                nested_state.inbox, existing_numbers=set(inbox_by_number)
            ):
                orphan_entry = nested_state.inbox[number]
                gh.close_issue_with_comment(
                    orphan_entry.issue_number, _ORPHAN_CLOSE_COMMENT_INBOX
                )
                new_inbox.pop(number, None)
                orphaned_inbox.append(
                    OrphanCleanup(number=number, issue_number=orphan_entry.issue_number)
                )

        if supersede_inbox is not None:
            assert only_scope is not None  # bereits oben validiert
            feature_entry = new_features.get(only_scope[1])
            if feature_entry is None:
                raise SyncError(
                    f"--supersede-inbox: Spec {only_scope[1]} wurde nicht erfolgreich gesynct "
                    "(siehe aborted_reason), kein Ziel-Issue zum Verlinken vorhanden."
                )
            inbox_entry = nested_state.inbox[supersede_inbox]  # Existenz bereits geprueft
            gh.close_issue_with_comment(
                inbox_entry.issue_number,
                f"In Spec-Issue #{feature_entry.issue_number} überführt.",
            )
            new_inbox.pop(supersede_inbox, None)
            supersede_result = SupersedeResult(
                inbox_number=supersede_inbox,
                inbox_issue_number=inbox_entry.issue_number,
                new_issue_number=feature_entry.issue_number,
            )
    finally:
        save_state(state_path, NestedState(features=new_features, inbox=new_inbox))

    return SyncRunResult(
        specs=spec_results,
        orphaned=orphaned,
        inbox=inbox_results,
        orphaned_inbox=orphaned_inbox,
        supersede=supersede_result,
    )
