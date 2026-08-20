from __future__ import annotations

import json
from pathlib import Path

import pytest

from github_project_sync.gh_adapter import GhAuthScopeError, ProjectFields
from github_project_sync.hashing import push_state_hash, text_hash
from github_project_sync.issue_body import build_issue_body
from github_project_sync.spec_parser import parse_spec_file
from github_project_sync.state import load_state
from github_project_sync.sync import OrphanCleanup, SyncError, run_sync
from tests.fakes import FakeGhAdapter

_FIXED_NOW = "2026-08-20T00:00:00+00:00"


def _spec_text(number: str, title: str, status: str, ziel: str = "Foo.") -> str:
    return (
        f"# {number} - {title}\n\n"
        f"**Status:** {status}\n"
        f"**Erstellt:** 2026-08-09\n"
        f"**Bezug:** (keiner)\n\n"
        f"## Ziel\n\n{ziel}\n"
    )


def _roadmap_text(*, niedrig: list[tuple[str, str]] | None = None) -> str:
    rows = "\n".join(f"| [{n}](./features/{n}-x.md) | {t} | Accepted |" for n, t in (niedrig or []))
    table = rows or ""
    return (
        "# Roadmap\n\n## Status auf einen Blick\n\n"
        "### Offen — Hoch\n\nKeine offenen Einträge.\n\n"
        "### Offen — Mittel\n\nKeine offenen Einträge.\n\n"
        f"### Offen — Niedrig\n\n| Spec | Titel | Status |\n|---|---|---|\n{table}\n"
    )


def _make_repo(
    tmp_path: Path,
    *,
    specs: dict[str, str],
    roadmap: str,
    state: dict | None = None,
) -> Path:
    repo_root = tmp_path / "repo"
    features_dir = repo_root / "specs" / "features"
    features_dir.mkdir(parents=True)
    for number, text in specs.items():
        (features_dir / f"{number}-x.md").write_text(text, encoding="utf-8")
    (repo_root / "specs" / "roadmap.md").write_text(roadmap, encoding="utf-8")
    if state is not None:
        (repo_root / "specs" / ".github-sync-state.json").write_text(
            json.dumps(state), encoding="utf-8"
        )
    return repo_root


def test_check_auth_scope_failure_propagates(tmp_path: Path) -> None:
    repo_root = _make_repo(tmp_path, specs={}, roadmap=_roadmap_text())
    gh = FakeGhAdapter(auth_ok=False)

    with pytest.raises(GhAuthScopeError):
        run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)


def test_created_case_creates_issue_item_and_state_entry(tmp_path: Path) -> None:
    repo_root = _make_repo(
        tmp_path,
        specs={"0031": _spec_text("0031", "Sync-Feature", "Accepted")},
        roadmap=_roadmap_text(niedrig=[("0031", "Sync-Feature")]),
    )
    gh = FakeGhAdapter()

    result = run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)

    assert len(result.specs) == 1
    spec_result = result.specs[0]
    assert spec_result.classification == "created"
    assert spec_result.issue_number == 1

    issue = gh.issue(1)
    assert issue.title == "[0031] Sync-Feature"
    assert issue.body.startswith("<!-- photosort-spec: 0031 -->")
    assert issue.state == "open"

    state = load_state(repo_root / "specs" / ".github-sync-state.json")
    assert state["0031"].issue_number == 1
    assert state["0031"].item_id in gh.items


def test_created_case_sets_status_and_priority_fields(tmp_path: Path) -> None:
    repo_root = _make_repo(
        tmp_path,
        specs={"0031": _spec_text("0031", "Sync-Feature", "Accepted")},
        roadmap=_roadmap_text(niedrig=[("0031", "Sync-Feature")]),
    )
    gh = FakeGhAdapter()

    result = run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)

    item_id = gh.items and next(iter(gh.items))
    assert gh.items[item_id]["F_STATUS"] == "S_Accepted"
    assert gh.items[item_id]["F_PRIO"] == "P_Niedrig"
    assert result.specs[0].priority_warning is None


def test_missing_priority_for_open_spec_yields_warning_but_still_syncs(tmp_path: Path) -> None:
    repo_root = _make_repo(
        tmp_path,
        specs={"0031": _spec_text("0031", "Sync-Feature", "Accepted")},
        roadmap=_roadmap_text(niedrig=[]),
    )
    gh = FakeGhAdapter()

    result = run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)

    assert result.specs[0].classification == "created"
    assert result.specs[0].priority_warning is not None
    assert "0031" in result.specs[0].priority_warning


def _drop_field_option(
    fields: ProjectFields, *, field_name: str, option_name: str
) -> ProjectFields:
    """Simuliert Board-Drift: eine erwartete Option fehlt im Project-Feld (z.B. manuell
    umbenannt/geloescht), obwohl das Feld selbst unter dem erwarteten Namen existiert."""
    if field_name == "status":
        return ProjectFields(
            status_field_id=fields.status_field_id,
            status_options={k: v for k, v in fields.status_options.items() if k != option_name},
            priority_field_id=fields.priority_field_id,
            priority_options=fields.priority_options,
        )
    return ProjectFields(
        status_field_id=fields.status_field_id,
        status_options=fields.status_options,
        priority_field_id=fields.priority_field_id,
        priority_options={k: v for k, v in fields.priority_options.items() if k != option_name},
    )


def test_missing_status_option_aborts_with_sync_error_instead_of_silent_no_op(
    tmp_path: Path,
) -> None:
    repo_root = _make_repo(
        tmp_path,
        specs={"0031": _spec_text("0031", "Sync-Feature", "Accepted")},
        roadmap=_roadmap_text(niedrig=[("0031", "Sync-Feature")]),
    )
    gh = FakeGhAdapter()
    project = gh.ensure_project()
    fields = gh.ensure_fields(project)
    gh.fields = _drop_field_option(fields, field_name="status", option_name="Accepted")

    with pytest.raises(SyncError, match="Status"):
        run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)


def test_missing_priority_option_aborts_with_sync_error_instead_of_clearing_field(
    tmp_path: Path,
) -> None:
    # Regressionstest fuer den Copilot-Review-Fund auf PR #115: eine fehlende Options-ID durfte
    # nicht faelschlich als "priority is None" behandelt werden (das haette das Feld
    # stillschweigend geleert, obwohl die Spec eine echte, nicht-leere Prioritaet hat).
    repo_root = _make_repo(
        tmp_path,
        specs={"0031": _spec_text("0031", "Sync-Feature", "Accepted")},
        roadmap=_roadmap_text(niedrig=[("0031", "Sync-Feature")]),
    )
    gh = FakeGhAdapter()
    project = gh.ensure_project()
    fields = gh.ensure_fields(project)
    gh.fields = _drop_field_option(fields, field_name="priority", option_name="Niedrig")

    with pytest.raises(SyncError, match="Priorität"):
        run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)


def _existing_state_entry(*, issue_number: int, push_hash: str, pull_hash: str) -> dict:
    return {
        "issue_number": issue_number,
        "item_id": "ITEM_1",
        "pushed_state_hash": push_hash,
        "pulled_body_hash": pull_hash,
        "last_synced_at": "2026-08-09T00:00:00Z",
    }


def test_pushed_case_updates_issue_body_from_spec(tmp_path: Path) -> None:
    content_zone = "## Ziel\n\nAlter Text.\n"
    old_push_hash = push_state_hash(
        status="Accepted", priority="Niedrig", content_zone=content_zone
    )
    old_pull_hash = text_hash(content_zone)

    repo_root = _make_repo(
        tmp_path,
        specs={"0031": _spec_text("0031", "Sync-Feature", "Accepted", ziel="Neuer Text.")},
        roadmap=_roadmap_text(niedrig=[("0031", "Sync-Feature")]),
        state={
            "0031": _existing_state_entry(
                issue_number=42, push_hash=old_push_hash, pull_hash=old_pull_hash
            )
        },
    )
    gh = FakeGhAdapter()
    gh.seed_issue(42, body=build_issue_body("0031", content_zone))

    result = run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)

    assert result.specs[0].classification == "pushed"
    assert "Neuer Text." in gh.issue(42).body
    assert "Alter Text." not in gh.issue(42).body


def test_pulled_case_writes_issue_content_into_spec_file(tmp_path: Path) -> None:
    content_zone = "## Ziel\n\nAlter Text.\n"
    push_hash = push_state_hash(status="Accepted", priority="Niedrig", content_zone=content_zone)
    old_pull_hash = text_hash(content_zone)

    repo_root = _make_repo(
        tmp_path,
        specs={"0031": _spec_text("0031", "Sync-Feature", "Accepted", ziel="Alter Text.")},
        roadmap=_roadmap_text(niedrig=[("0031", "Sync-Feature")]),
        state={
            "0031": _existing_state_entry(
                issue_number=42, push_hash=push_hash, pull_hash=old_pull_hash
            )
        },
    )
    gh = FakeGhAdapter()
    new_remote_zone = "## Ziel\n\nVon Daniel im Issue geändert.\n"
    gh.seed_issue(42, body=build_issue_body("0031", new_remote_zone))

    result = run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)

    assert result.specs[0].classification == "pulled"
    assert result.specs[0].pulled_content_zone == new_remote_zone

    updated = parse_spec_file(repo_root / "specs" / "features" / "0031-x.md")
    assert "Von Daniel im Issue geändert." in updated.content_zone
    assert updated.status == "Accepted"  # Metadaten-Block unangetastet
    assert updated.title == "Sync-Feature"


def test_pulled_case_ignores_metadata_edits_in_issue_body(tmp_path: Path) -> None:
    content_zone = "## Ziel\n\nAlter Text.\n"
    push_hash = push_state_hash(status="Accepted", priority="Niedrig", content_zone=content_zone)
    old_pull_hash = text_hash(content_zone)

    repo_root = _make_repo(
        tmp_path,
        specs={"0031": _spec_text("0031", "Sync-Feature", "Accepted", ziel="Alter Text.")},
        roadmap=_roadmap_text(niedrig=[("0031", "Sync-Feature")]),
        state={
            "0031": _existing_state_entry(
                issue_number=42, push_hash=push_hash, pull_hash=old_pull_hash
            )
        },
    )
    gh = FakeGhAdapter()
    # Daniel hat versehentlich versucht, den Status im Issue-Body mitzuaendern - hat nur
    # Wirkung, wenn es Teil der Inhalts-Zone waere; hier simuliert als Freitext in "## Ziel".
    new_remote_zone = "## Ziel\n\n**Status:** Proposed (das darf keine Wirkung haben)\n"
    gh.seed_issue(42, body=build_issue_body("0031", new_remote_zone))

    run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)

    updated = parse_spec_file(repo_root / "specs" / "features" / "0031-x.md")
    assert updated.status == "Accepted"


def test_conflict_case_touches_neither_side_and_is_idempotent(tmp_path: Path) -> None:
    content_zone = "## Ziel\n\nAlter Text.\n"
    push_hash = push_state_hash(status="Accepted", priority="Niedrig", content_zone=content_zone)
    old_pull_hash = text_hash(content_zone)

    repo_root = _make_repo(
        tmp_path,
        specs={"0031": _spec_text("0031", "Sync-Feature", "Accepted", ziel="Lokal geändert.")},
        roadmap=_roadmap_text(niedrig=[("0031", "Sync-Feature")]),
        state={
            "0031": _existing_state_entry(
                issue_number=42, push_hash=push_hash, pull_hash=old_pull_hash
            )
        },
    )
    gh = FakeGhAdapter()
    remote_zone = "## Ziel\n\nAuf GitHub geändert.\n"
    gh.seed_issue(42, body=build_issue_body("0031", remote_zone))

    result = run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)

    spec_result = result.specs[0]
    assert spec_result.classification == "conflict"
    assert spec_result.conflict is not None
    assert "Lokal geändert." in spec_result.conflict.local_content_zone
    assert "Auf GitHub geändert." in spec_result.conflict.remote_content_zone

    # Keine Seite automatisch ueberschrieben:
    assert "Auf GitHub geändert." in gh.issue(42).body
    updated = parse_spec_file(repo_root / "specs" / "features" / "0031-x.md")
    assert "Lokal geändert." in updated.content_zone

    # Erneuter Lauf ohne Aufloesung meldet denselben Konflikt wieder (idempotent):
    result_again = run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)
    assert result_again.specs[0].classification == "conflict"


def test_conflict_resolution_keep_spec_pushes_local_content(tmp_path: Path) -> None:
    content_zone = "## Ziel\n\nAlter Text.\n"
    push_hash = push_state_hash(status="Accepted", priority="Niedrig", content_zone=content_zone)
    old_pull_hash = text_hash(content_zone)

    repo_root = _make_repo(
        tmp_path,
        specs={"0031": _spec_text("0031", "Sync-Feature", "Accepted", ziel="Lokal geändert.")},
        roadmap=_roadmap_text(niedrig=[("0031", "Sync-Feature")]),
        state={
            "0031": _existing_state_entry(
                issue_number=42, push_hash=push_hash, pull_hash=old_pull_hash
            )
        },
    )
    gh = FakeGhAdapter()
    gh.seed_issue(42, body=build_issue_body("0031", "## Ziel\n\nAuf GitHub geändert.\n"))

    result = run_sync(
        repo_root=repo_root, gh=gh, resolutions={"0031": "keep_spec"}, now=lambda: _FIXED_NOW
    )

    assert result.specs[0].classification == "pushed"
    assert "Lokal geändert." in gh.issue(42).body

    # Aufloesung wird als neue Baseline gespeichert - naechster Lauf ist wieder unchanged:
    result_again = run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)
    assert result_again.specs[0].classification == "unchanged"


def test_conflict_resolution_keep_issue_pulls_remote_content(tmp_path: Path) -> None:
    content_zone = "## Ziel\n\nAlter Text.\n"
    push_hash = push_state_hash(status="Accepted", priority="Niedrig", content_zone=content_zone)
    old_pull_hash = text_hash(content_zone)

    repo_root = _make_repo(
        tmp_path,
        specs={"0031": _spec_text("0031", "Sync-Feature", "Accepted", ziel="Lokal geändert.")},
        roadmap=_roadmap_text(niedrig=[("0031", "Sync-Feature")]),
        state={
            "0031": _existing_state_entry(
                issue_number=42, push_hash=push_hash, pull_hash=old_pull_hash
            )
        },
    )
    gh = FakeGhAdapter()
    gh.seed_issue(42, body=build_issue_body("0031", "## Ziel\n\nAuf GitHub geändert.\n"))

    result = run_sync(
        repo_root=repo_root, gh=gh, resolutions={"0031": "keep_issue"}, now=lambda: _FIXED_NOW
    )

    assert result.specs[0].classification == "pulled"
    updated = parse_spec_file(repo_root / "specs" / "features" / "0031-x.md")
    assert "Auf GitHub geändert." in updated.content_zone


def test_unchanged_case_does_not_touch_issue_body(tmp_path: Path) -> None:
    content_zone = "## Ziel\n\nText.\n"
    push_hash = push_state_hash(status="Accepted", priority="Niedrig", content_zone=content_zone)
    pull_hash = text_hash(content_zone)

    repo_root = _make_repo(
        tmp_path,
        specs={"0031": _spec_text("0031", "Sync-Feature", "Accepted", ziel="Text.")},
        roadmap=_roadmap_text(niedrig=[("0031", "Sync-Feature")]),
        state={
            "0031": _existing_state_entry(
                issue_number=42, push_hash=push_hash, pull_hash=pull_hash
            )
        },
    )
    gh = FakeGhAdapter()
    original_body = build_issue_body("0031", content_zone)
    gh.seed_issue(42, body=original_body)

    result = run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)

    assert result.specs[0].classification == "unchanged"
    assert gh.issue(42).body == original_body


def test_manually_closed_issue_is_reopened_on_next_sync_even_when_unchanged(tmp_path: Path) -> None:
    content_zone = "## Ziel\n\nText.\n"
    push_hash = push_state_hash(status="Accepted", priority="Niedrig", content_zone=content_zone)
    pull_hash = text_hash(content_zone)

    repo_root = _make_repo(
        tmp_path,
        specs={"0031": _spec_text("0031", "Sync-Feature", "Accepted", ziel="Text.")},
        roadmap=_roadmap_text(niedrig=[("0031", "Sync-Feature")]),
        state={
            "0031": _existing_state_entry(
                issue_number=42, push_hash=push_hash, pull_hash=pull_hash
            )
        },
    )
    gh = FakeGhAdapter()
    gh.seed_issue(42, body=build_issue_body("0031", content_zone), state="closed")

    run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)

    assert gh.issue(42).state == "open"


def test_marker_mismatch_aborts_only_that_spec(tmp_path: Path) -> None:
    content_zone = "## Ziel\n\nText.\n"
    push_hash = push_state_hash(status="Accepted", priority="Niedrig", content_zone=content_zone)
    pull_hash = text_hash(content_zone)

    repo_root = _make_repo(
        tmp_path,
        specs={
            "0031": _spec_text("0031", "Sync-Feature", "Accepted", ziel="Text."),
            "0032": _spec_text("0032", "Anderes Feature", "Accepted"),
        },
        roadmap=_roadmap_text(niedrig=[("0031", "Sync-Feature"), ("0032", "Anderes Feature")]),
        state={
            "0031": _existing_state_entry(
                issue_number=42, push_hash=push_hash, pull_hash=pull_hash
            )
        },
    )
    gh = FakeGhAdapter()
    # Marker fehlt komplett im referenzierten Issue:
    gh.seed_issue(42, body="Kein Marker hier.\n\n## Ziel\n\nText.\n")

    result = run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)

    aborted = next(r for r in result.specs if r.number == "0031")
    assert aborted.classification is None
    assert aborted.aborted_reason is not None

    created = next(r for r in result.specs if r.number == "0032")
    assert created.classification == "created"

    # State fuer die abgebrochene Spec bleibt unveraendert (kein Zweit-Issue angelegt):
    state = load_state(repo_root / "specs" / ".github-sync-state.json")
    assert state["0031"].issue_number == 42


def test_marker_number_mismatch_also_aborts(tmp_path: Path) -> None:
    content_zone = "## Ziel\n\nText.\n"
    push_hash = push_state_hash(status="Accepted", priority="Niedrig", content_zone=content_zone)
    pull_hash = text_hash(content_zone)

    repo_root = _make_repo(
        tmp_path,
        specs={"0031": _spec_text("0031", "Sync-Feature", "Accepted", ziel="Text.")},
        roadmap=_roadmap_text(niedrig=[("0031", "Sync-Feature")]),
        state={
            "0031": _existing_state_entry(
                issue_number=42, push_hash=push_hash, pull_hash=pull_hash
            )
        },
    )
    gh = FakeGhAdapter()
    # Marker verweist auf eine andere Spec-Nummer als der State-Eintrag erwartet:
    gh.seed_issue(42, body=build_issue_body("9999", content_zone))

    result = run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)

    assert result.specs[0].aborted_reason is not None


def test_deleted_spec_file_closes_issue_and_removes_state_entry(tmp_path: Path) -> None:
    content_zone = "## Ziel\n\nText.\n"
    push_hash = push_state_hash(status="Accepted", priority="Niedrig", content_zone=content_zone)
    pull_hash = text_hash(content_zone)

    repo_root = _make_repo(
        tmp_path,
        specs={},
        roadmap=_roadmap_text(),
        state={
            "0031": _existing_state_entry(
                issue_number=42, push_hash=push_hash, pull_hash=pull_hash
            )
        },
    )
    gh = FakeGhAdapter()
    gh.seed_issue(42, body=build_issue_body("0031", content_zone))

    result = run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)

    assert result.orphaned == [OrphanCleanup(number="0031", issue_number=42)]
    assert gh.issue(42).state == "closed"
    assert gh.issue(42).comments == ["Spec-Datei wurde entfernt."]

    state = load_state(repo_root / "specs" / ".github-sync-state.json")
    assert "0031" not in state


def test_only_filter_processes_single_spec_and_skips_orphan_cleanup(tmp_path: Path) -> None:
    content_zone = "## Ziel\n\nText.\n"
    push_hash = push_state_hash(status="Accepted", priority="Niedrig", content_zone=content_zone)
    pull_hash = text_hash(content_zone)

    repo_root = _make_repo(
        tmp_path,
        specs={"0032": _spec_text("0032", "Neues Feature", "Accepted")},
        roadmap=_roadmap_text(niedrig=[("0032", "Neues Feature")]),
        # 0031 hat einen State-Eintrag, aber keine Datei mehr (waere sonst ein Orphan):
        state={
            "0031": _existing_state_entry(
                issue_number=42, push_hash=push_hash, pull_hash=pull_hash
            )
        },
    )
    gh = FakeGhAdapter()
    gh.seed_issue(42, body=build_issue_body("0031", content_zone))

    result = run_sync(repo_root=repo_root, gh=gh, only="0032", now=lambda: _FIXED_NOW)

    assert len(result.specs) == 1
    assert result.specs[0].number == "0032"
    assert result.orphaned == []
    assert gh.issue(42).state == "open"  # unberuehrt, da --only genutzt wurde


def test_only_filter_raises_for_unknown_spec_number(tmp_path: Path) -> None:
    repo_root = _make_repo(tmp_path, specs={}, roadmap=_roadmap_text())
    gh = FakeGhAdapter()

    with pytest.raises(SyncError):
        run_sync(repo_root=repo_root, gh=gh, only="9999", now=lambda: _FIXED_NOW)


def test_self_provisioning_idempotent_across_two_runs(tmp_path: Path) -> None:
    repo_root = _make_repo(
        tmp_path,
        specs={"0031": _spec_text("0031", "Sync-Feature", "Accepted")},
        roadmap=_roadmap_text(niedrig=[("0031", "Sync-Feature")]),
    )
    gh = FakeGhAdapter()

    run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)
    result_two = run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)

    assert len(gh.items) == 1  # kein zweites Project-Item fuer dieselbe Spec
    assert result_two.specs[0].classification == "unchanged"


def test_abort_mid_run_keeps_state_of_already_processed_specs(tmp_path: Path) -> None:
    repo_root = _make_repo(
        tmp_path,
        specs={
            "0031": _spec_text("0031", "Erstes Feature", "Accepted"),
            "0032": _spec_text("0032", "Zweites Feature", "Accepted"),
        },
        roadmap=_roadmap_text(niedrig=[("0031", "Erstes Feature"), ("0032", "Zweites Feature")]),
    )

    class _CrashingAfterFirst(FakeGhAdapter):
        def __init__(self) -> None:
            super().__init__()
            self._create_calls = 0

        def create_issue(self, title: str, body: str) -> int:
            self._create_calls += 1
            if self._create_calls == 2:
                raise RuntimeError("simulierter Netzwerkfehler beim zweiten Issue")
            return super().create_issue(title, body)

    gh = _CrashingAfterFirst()

    with pytest.raises(RuntimeError):
        run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)

    state = load_state(repo_root / "specs" / ".github-sync-state.json")
    assert "0031" in state
    assert "0032" not in state


def test_state_file_missing_roadmap_still_syncs_with_empty_priorities(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / "specs" / "features").mkdir(parents=True)
    (repo_root / "specs" / "features" / "0031-x.md").write_text(
        _spec_text("0031", "Sync-Feature", "Implemented"), encoding="utf-8"
    )
    gh = FakeGhAdapter()

    result = run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)

    assert result.specs[0].classification == "created"
    assert result.specs[0].priority_warning is None  # Implemented braucht keine Prioritaet

    issue_number = result.specs[0].issue_number
    assert issue_number is not None
    assert gh.issue(issue_number).state == "closed"  # Implemented -> nativer Issue-Zustand zu

    item_id = next(iter(gh.items))
    assert gh.items[item_id]["F_PRIO"] is None  # keine Prioritaets-Tabelle -> Feld geleert


def test_invalid_status_aborts_only_that_spec_not_the_whole_run(tmp_path: Path) -> None:
    # Regressionstest fuer einen echten Bug (zweiter manueller Sync-Lauf gegen echtes GitHub nach
    # Merge von PR #117): ein ungueltiger/unbekannter Status brach bisher den GESAMTEN
    # Mehr-Spec-Lauf per SyncError ab, noch bevor irgendeine andere Spec verarbeitet wurde -
    # analog zum bereits bestehenden Marker-Integritaets-Mechanismus soll stattdessen nur die
    # betroffene Spec ueber aborted_reason abbrechen, andere Specs laufen unbeeinflusst weiter.
    repo_root = _make_repo(
        tmp_path,
        specs={
            "0031": _spec_text("0031", "Kaputte Spec", "Draft"),  # kein bekannter Lifecycle-Wert
            "0032": _spec_text("0032", "Gesunde Spec", "Accepted"),
        },
        roadmap=_roadmap_text(niedrig=[("0032", "Gesunde Spec")]),
    )
    gh = FakeGhAdapter()

    result = run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)

    broken = next(r for r in result.specs if r.number == "0031")
    assert broken.classification is None
    assert broken.aborted_reason is not None
    assert "Draft" in broken.aborted_reason

    healthy = next(r for r in result.specs if r.number == "0032")
    assert healthy.classification == "created"
    assert healthy.issue_number is not None


def test_invalid_status_without_prior_state_writes_no_state_entry(tmp_path: Path) -> None:
    # Fuer eine noch nie synchronisierte Spec (kein State-Eintrag) gibt es beim Abbruch nichts zu
    # bewahren - ein erneuter Lauf versucht es (nach einer Korrektur der Spec-Datei) erneut.
    repo_root = _make_repo(
        tmp_path,
        specs={"0031": _spec_text("0031", "Kaputte Spec", "Draft")},
        roadmap=_roadmap_text(),
    )
    gh = FakeGhAdapter()

    run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)

    state = load_state(repo_root / "specs" / ".github-sync-state.json")
    assert "0031" not in state
