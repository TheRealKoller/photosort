from __future__ import annotations

import json
from pathlib import Path

import pytest

from github_project_sync.gh_adapter import GhAuthScopeError, ProjectFields
from github_project_sync.hashing import push_state_hash, text_hash
from github_project_sync.issue_body import build_issue_body
from github_project_sync.state import load_state
from github_project_sync.sync import (
    OrphanCleanup,
    SyncError,
    create_story_issue,
    run_sync,
    set_feature_runtime_status,
    show_story_status,
    sync_story,
)
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


def _make_repo(
    tmp_path: Path,
    *,
    specs: dict[str, str],
    state: dict | None = None,
    stories_state: dict | None = None,
    legacy_flat_state: dict | None = None,
    raw_state: dict | None = None,
) -> Path:
    repo_root = tmp_path / "repo"
    features_dir = repo_root / "specs" / "features"
    features_dir.mkdir(parents=True)
    for number, text in specs.items():
        (features_dir / f"{number}-x.md").write_text(text, encoding="utf-8")
    if raw_state is not None:
        (repo_root / "specs" / ".github-sync-state.json").write_text(
            json.dumps(raw_state), encoding="utf-8"
        )
    elif legacy_flat_state is not None:
        (repo_root / "specs" / ".github-sync-state.json").write_text(
            json.dumps(legacy_flat_state), encoding="utf-8"
        )
    elif state is not None or stories_state is not None:
        (repo_root / "specs" / ".github-sync-state.json").write_text(
            json.dumps({"features": state or {}, "stories": stories_state or {}}),
            encoding="utf-8",
        )
    return repo_root


def test_check_auth_scope_failure_propagates(tmp_path: Path) -> None:
    repo_root = _make_repo(tmp_path, specs={})
    gh = FakeGhAdapter(auth_ok=False)

    with pytest.raises(GhAuthScopeError):
        run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)


def test_created_case_creates_issue_item_and_state_entry(tmp_path: Path) -> None:
    repo_root = _make_repo(
        tmp_path,
        specs={"0031": _spec_text("0031", "Sync-Feature", "Accepted")},
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
    assert state.features["0031"].issue_number == 1
    assert state.features["0031"].item_id in gh.items


def test_created_case_sets_status_field_and_never_touches_priority(tmp_path: Path) -> None:
    repo_root = _make_repo(
        tmp_path,
        specs={"0031": _spec_text("0031", "Sync-Feature", "Accepted")},
    )
    gh = FakeGhAdapter()

    run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)

    item_id = next(iter(gh.items))
    assert gh.items[item_id]["F_STATUS"] == "S_Todo"  # Baseline Accepted -> Todo (ADR 0037)
    # ADR 0039: das Prioritaets-Feld wird auf keinem Pfad geschrieben.
    assert "F_PRIO" not in gh.items[item_id]
    assert all(field_id != "F_PRIO" for _, field_id in gh.single_select_writes)
    assert all(field_id != "F_PRIO" for _, field_id in gh.cleared_fields)


# -- Baseline+Override (Spec 0060 / ADR 0037, Abschnitte 1-2/5) --------------------------------


def test_created_case_proposed_status_maps_to_todo_baseline(tmp_path: Path) -> None:
    repo_root = _make_repo(
        tmp_path,
        specs={"0031": _spec_text("0031", "Sync-Feature", "Proposed")},
    )
    gh = FakeGhAdapter()

    run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)

    item_id = next(iter(gh.items))
    assert gh.items[item_id]["F_STATUS"] == "S_Todo"


def test_created_case_implemented_status_maps_to_done_baseline(tmp_path: Path) -> None:
    repo_root = _make_repo(
        tmp_path,
        specs={"0031": _spec_text("0031", "Sync-Feature", "Implemented")},
    )
    gh = FakeGhAdapter()

    run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)

    item_id = next(iter(gh.items))
    assert gh.items[item_id]["F_STATUS"] == "S_Done"


def test_stored_runtime_override_wins_over_todo_baseline(tmp_path: Path) -> None:
    content_zone = "## Ziel\n\nText.\n"
    push_hash = push_state_hash(status="Accepted", content_zone=content_zone)
    entry = _existing_state_entry(issue_number=42, push_hash=push_hash)
    entry["runtime_status"] = "In Progress"
    entry["pr_number"] = None

    repo_root = _make_repo(
        tmp_path,
        specs={"0031": _spec_text("0031", "Sync-Feature", "Accepted", ziel="Text.")},
        state={"0031": entry},
    )
    gh = FakeGhAdapter()
    gh.seed_issue(42, body=build_issue_body("0031", content_zone))

    run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)

    assert gh.items["ITEM_1"]["F_STATUS"] == "S_In Progress"

    state = load_state(repo_root / "specs" / ".github-sync-state.json")
    # Override bleibt fuer den naechsten Lauf erhalten, solange die Baseline "Todo" bleibt:
    assert state.features["0031"].runtime_status == "In Progress"


def test_runtime_override_defensively_cleared_once_baseline_becomes_done(tmp_path: Path) -> None:
    content_zone = "## Ziel\n\nText.\n"
    push_hash = push_state_hash(status="Accepted", content_zone=content_zone)
    entry = _existing_state_entry(issue_number=42, push_hash=push_hash)
    entry["runtime_status"] = "Review"
    entry["pr_number"] = 55

    repo_root = _make_repo(
        tmp_path,
        # Datei-Status ist jetzt (unabhaengig von einer Merge-Erkennung) bereits "Implemented" -
        # ein stehengebliebener Override darf die Baseline "Done" nie mehr verfeinern.
        specs={"0031": _spec_text("0031", "Sync-Feature", "Implemented", ziel="Text.")},
        state={"0031": entry},
    )
    gh = FakeGhAdapter()
    gh.seed_issue(42, body=build_issue_body("0031", content_zone))

    run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)

    assert gh.items["ITEM_1"]["F_STATUS"] == "S_Done"
    state = load_state(repo_root / "specs" / ".github-sync-state.json")
    assert state.features["0031"].runtime_status is None
    assert state.features["0031"].pr_number is None


# -- Automatische PR-Merge-Erkennung -> "Done" (Spec 0060 / ADR 0037, Abschnitt 5) --------------


def test_merged_pr_finalizes_spec_to_implemented_and_pushes_done(tmp_path: Path) -> None:
    content_zone = "## Ziel\n\nText.\n"
    push_hash = push_state_hash(status="Accepted", content_zone=content_zone)
    entry = _existing_state_entry(issue_number=42, push_hash=push_hash)
    entry["runtime_status"] = "Review"
    entry["pr_number"] = 101

    repo_root = _make_repo(
        tmp_path,
        specs={"0031": _spec_text("0031", "Sync-Feature", "Accepted", ziel="Text.")},
        state={"0031": entry},
    )
    gh = FakeGhAdapter()
    gh.seed_issue(42, body=build_issue_body("0031", content_zone))
    gh.seed_pull_request(
        101, state="merged", url="https://github.com/TheRealKoller/photosort/pull/101"
    )

    result = run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)

    spec_result = result.specs[0]
    assert spec_result.finalized_from_pr == 101

    spec_text = (repo_root / "specs" / "features" / "0031-x.md").read_text(encoding="utf-8")
    expected_status_line = (
        "**Status:** Implemented ([PR #101](https://github.com/TheRealKoller/photosort/pull/101))"
    )
    assert expected_status_line in spec_text
    assert "## Ziel" in spec_text  # Inhalts-Zone unangetastet

    assert gh.items["ITEM_1"]["F_STATUS"] == "S_Done"
    assert gh.issue(42).state == "closed"  # Implemented -> nativer Issue-Zustand zu

    state = load_state(repo_root / "specs" / ".github-sync-state.json")
    assert state.features["0031"].runtime_status is None
    assert state.features["0031"].pr_number is None


def test_open_pr_does_not_finalize_spec_yet(tmp_path: Path) -> None:
    content_zone = "## Ziel\n\nText.\n"
    push_hash = push_state_hash(status="Accepted", content_zone=content_zone)
    entry = _existing_state_entry(issue_number=42, push_hash=push_hash)
    entry["runtime_status"] = "Review"
    entry["pr_number"] = 101

    repo_root = _make_repo(
        tmp_path,
        specs={"0031": _spec_text("0031", "Sync-Feature", "Accepted", ziel="Text.")},
        state={"0031": entry},
    )
    gh = FakeGhAdapter()
    gh.seed_issue(42, body=build_issue_body("0031", content_zone))
    gh.seed_pull_request(101, state="open")

    result = run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)

    assert result.specs[0].finalized_from_pr is None
    spec_text = (repo_root / "specs" / "features" / "0031-x.md").read_text(encoding="utf-8")
    assert "**Status:** Accepted" in spec_text
    assert gh.items["ITEM_1"]["F_STATUS"] == "S_Review"

    state = load_state(repo_root / "specs" / ".github-sync-state.json")
    assert state.features["0031"].runtime_status == "Review"
    assert state.features["0031"].pr_number == 101


def test_merge_detection_not_triggered_without_review_override(tmp_path: Path) -> None:
    # Guard-Bedingung: stored_entry.runtime_status muss exakt "Review" sein - ein "In Progress"-
    # Override (auch mit zufaellig gesetztem pr_number) darf gh.get_pull_request() nie aufrufen.
    content_zone = "## Ziel\n\nText.\n"
    push_hash = push_state_hash(status="Accepted", content_zone=content_zone)
    entry = _existing_state_entry(issue_number=42, push_hash=push_hash)
    entry["runtime_status"] = "In Progress"
    entry["pr_number"] = None

    repo_root = _make_repo(
        tmp_path,
        specs={"0031": _spec_text("0031", "Sync-Feature", "Accepted", ziel="Text.")},
        state={"0031": entry},
    )
    gh = FakeGhAdapter()
    gh.seed_issue(42, body=build_issue_body("0031", content_zone))
    # Kein seed_pull_request() - ein Aufruf wuerde GhAdapterError werfen und den Test scheitern
    # lassen.

    result = run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)

    assert result.specs[0].finalized_from_pr is None


def test_merge_detection_not_triggered_when_spec_status_is_not_accepted(tmp_path: Path) -> None:
    # Guard-Bedingung: status == "Accepted" - eine bereits "Superseded"-Spec mit stehengebliebenem
    # Review-Override darf gh.get_pull_request() nie aufrufen.
    content_zone = "## Ziel\n\nText.\n"
    push_hash = push_state_hash(status="Superseded", content_zone=content_zone)
    entry = _existing_state_entry(issue_number=42, push_hash=push_hash)
    entry["runtime_status"] = "Review"
    entry["pr_number"] = 101

    repo_root = _make_repo(
        tmp_path,
        specs={"0031": _spec_text("0031", "Sync-Feature", "Superseded", ziel="Text.")},
        state={"0031": entry},
    )
    gh = FakeGhAdapter()
    gh.seed_issue(42, body=build_issue_body("0031", content_zone), state="closed")

    result = run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)

    assert result.specs[0].finalized_from_pr is None


def test_merge_detection_error_aborts_only_that_spec_not_the_whole_run(tmp_path: Path) -> None:
    # Regressionstest fuer ein Review-Finding (test-engineer): gh.get_pull_request() lief bisher
    # ohne Error-Handling - ein GhAdapterError (PR nicht auffindbar, gh-CLI-Fehler) haette den
    # gesamten Mehr-Spec-Lauf per Exception abgebrochen, statt (wie bei ungueltigem Status/
    # Marker-Integritaet bereits etabliert) nur diese eine Spec mit aborted_reason zu markieren.
    content_zone = "## Ziel\n\nText.\n"
    push_hash = push_state_hash(status="Accepted", content_zone=content_zone)
    broken_entry = _existing_state_entry(issue_number=42, push_hash=push_hash)
    broken_entry["runtime_status"] = "Review"
    broken_entry["pr_number"] = 999  # bewusst nicht per seed_pull_request() bekannt gemacht

    repo_root = _make_repo(
        tmp_path,
        specs={
            "0031": _spec_text("0031", "Kaputte Spec", "Accepted", ziel="Text."),
            "0032": _spec_text("0032", "Gesunde Spec", "Accepted"),
        },
        state={"0031": broken_entry},
    )
    gh = FakeGhAdapter()
    gh.seed_issue(42, body=build_issue_body("0031", content_zone))
    # Kein seed_pull_request(999) - gh.get_pull_request(999) wirft GhAdapterError.

    result = run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)

    broken = next(r for r in result.specs if r.number == "0031")
    assert broken.classification is None
    assert broken.aborted_reason is not None
    assert "999" in broken.aborted_reason

    healthy = next(r for r in result.specs if r.number == "0032")
    assert healthy.classification == "created"
    assert healthy.issue_number is not None

    # Der State-Eintrag der kaputten Spec bleibt unveraendert - ein erneuter Lauf versucht die
    # Merge-Erkennung erneut, sobald der zugrundeliegende Fehler behoben ist (idempotent).
    state = load_state(repo_root / "specs" / ".github-sync-state.json")
    assert state.features["0031"].runtime_status == "Review"
    assert state.features["0031"].pr_number == 999


def _drop_status_option(fields: ProjectFields, *, option_name: str) -> ProjectFields:
    """Simuliert Board-Drift: eine erwartete Option fehlt im Status-Feld (z.B. manuell
    umbenannt/geloescht), obwohl das Feld selbst unter dem erwarteten Namen existiert."""
    return ProjectFields(
        status_field_id=fields.status_field_id,
        status_options={k: v for k, v in fields.status_options.items() if k != option_name},
        priority_field_id=fields.priority_field_id,
        priority_options=fields.priority_options,
    )


def test_missing_status_option_aborts_with_sync_error_instead_of_silent_no_op(
    tmp_path: Path,
) -> None:
    repo_root = _make_repo(
        tmp_path,
        specs={"0031": _spec_text("0031", "Sync-Feature", "Accepted")},
    )
    gh = FakeGhAdapter()
    project = gh.ensure_project()
    fields = gh.ensure_fields(project)
    # Seit Spec 0060 / ADR 0037: "Accepted" ist kein Board-Wert mehr, der gepushte Wert ist die
    # Baseline "Todo" - die fehlende Option muss deshalb hier simuliert werden, nicht "Accepted".
    gh.fields = _drop_status_option(fields, option_name="Todo")

    with pytest.raises(SyncError, match="Status"):
        run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)


def _existing_state_entry(*, issue_number: int, push_hash: str) -> dict:
    return {
        "issue_number": issue_number,
        "item_id": "ITEM_1",
        "pushed_state_hash": push_hash,
        "last_synced_at": "2026-08-09T00:00:00Z",
    }


def _story_state_entry_dict(*, issue_number: int, item_id: str = "ITEM_1") -> dict:
    return {
        "issue_number": issue_number,
        "item_id": item_id,
        "last_synced_at": "2026-08-09T00:00:00Z",
    }


def test_pushed_case_updates_issue_body_from_spec(tmp_path: Path) -> None:
    content_zone = "## Ziel\n\nAlter Text.\n"
    old_push_hash = push_state_hash(status="Accepted", content_zone=content_zone)

    repo_root = _make_repo(
        tmp_path,
        specs={"0031": _spec_text("0031", "Sync-Feature", "Accepted", ziel="Neuer Text.")},
        state={"0031": _existing_state_entry(issue_number=42, push_hash=old_push_hash)},
    )
    gh = FakeGhAdapter()
    gh.seed_issue(42, body=build_issue_body("0031", content_zone))

    result = run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)

    assert result.specs[0].classification == "pushed"
    assert "Neuer Text." in gh.issue(42).body
    assert "Alter Text." not in gh.issue(42).body


def test_unchanged_case_does_not_touch_issue_body(tmp_path: Path) -> None:
    content_zone = "## Ziel\n\nText.\n"
    push_hash = push_state_hash(status="Accepted", content_zone=content_zone)

    repo_root = _make_repo(
        tmp_path,
        specs={"0031": _spec_text("0031", "Sync-Feature", "Accepted", ziel="Text.")},
        state={"0031": _existing_state_entry(issue_number=42, push_hash=push_hash)},
    )
    gh = FakeGhAdapter()
    original_body = build_issue_body("0031", content_zone)
    gh.seed_issue(42, body=original_body)

    result = run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)

    assert result.specs[0].classification == "unchanged"
    assert gh.issue(42).body == original_body


def test_manually_closed_issue_is_reopened_on_next_sync_even_when_unchanged(tmp_path: Path) -> None:
    content_zone = "## Ziel\n\nText.\n"
    push_hash = push_state_hash(status="Accepted", content_zone=content_zone)

    repo_root = _make_repo(
        tmp_path,
        specs={"0031": _spec_text("0031", "Sync-Feature", "Accepted", ziel="Text.")},
        state={"0031": _existing_state_entry(issue_number=42, push_hash=push_hash)},
    )
    gh = FakeGhAdapter()
    gh.seed_issue(42, body=build_issue_body("0031", content_zone), state="closed")

    run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)

    assert gh.issue(42).state == "open"


def test_marker_mismatch_aborts_only_that_spec(tmp_path: Path) -> None:
    content_zone = "## Ziel\n\nText.\n"
    push_hash = push_state_hash(status="Accepted", content_zone=content_zone)

    repo_root = _make_repo(
        tmp_path,
        specs={
            "0031": _spec_text("0031", "Sync-Feature", "Accepted", ziel="Text."),
            "0032": _spec_text("0032", "Anderes Feature", "Accepted"),
        },
        state={"0031": _existing_state_entry(issue_number=42, push_hash=push_hash)},
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
    assert state.features["0031"].issue_number == 42


def test_marker_number_mismatch_also_aborts(tmp_path: Path) -> None:
    content_zone = "## Ziel\n\nText.\n"
    push_hash = push_state_hash(status="Accepted", content_zone=content_zone)

    repo_root = _make_repo(
        tmp_path,
        specs={"0031": _spec_text("0031", "Sync-Feature", "Accepted", ziel="Text.")},
        state={"0031": _existing_state_entry(issue_number=42, push_hash=push_hash)},
    )
    gh = FakeGhAdapter()
    # Marker verweist auf eine andere Spec-Nummer als der State-Eintrag erwartet:
    gh.seed_issue(42, body=build_issue_body("9999", content_zone))

    result = run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)

    assert result.specs[0].aborted_reason is not None


def test_deleted_spec_file_closes_issue_and_removes_state_entry(tmp_path: Path) -> None:
    content_zone = "## Ziel\n\nText.\n"
    push_hash = push_state_hash(status="Accepted", content_zone=content_zone)

    repo_root = _make_repo(
        tmp_path,
        specs={},
        state={"0031": _existing_state_entry(issue_number=42, push_hash=push_hash)},
    )
    gh = FakeGhAdapter()
    gh.seed_issue(42, body=build_issue_body("0031", content_zone))

    result = run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)

    assert result.orphaned == [OrphanCleanup(number="0031", issue_number=42)]
    assert gh.issue(42).state == "closed"
    assert gh.issue(42).comments == ["Spec-Datei wurde entfernt."]

    state = load_state(repo_root / "specs" / ".github-sync-state.json")
    assert "0031" not in state.features


def test_only_filter_processes_single_spec_and_skips_orphan_cleanup(tmp_path: Path) -> None:
    content_zone = "## Ziel\n\nText.\n"
    push_hash = push_state_hash(status="Accepted", content_zone=content_zone)

    repo_root = _make_repo(
        tmp_path,
        specs={"0032": _spec_text("0032", "Neues Feature", "Accepted")},
        # 0031 hat einen State-Eintrag, aber keine Datei mehr (waere sonst ein Orphan):
        state={"0031": _existing_state_entry(issue_number=42, push_hash=push_hash)},
    )
    gh = FakeGhAdapter()
    gh.seed_issue(42, body=build_issue_body("0031", content_zone))

    result = run_sync(repo_root=repo_root, gh=gh, only="0032", now=lambda: _FIXED_NOW)

    assert len(result.specs) == 1
    assert result.specs[0].number == "0032"
    assert result.orphaned == []
    assert gh.issue(42).state == "open"  # unberuehrt, da --only genutzt wurde


def test_only_filter_raises_for_unknown_spec_number(tmp_path: Path) -> None:
    repo_root = _make_repo(tmp_path, specs={})
    gh = FakeGhAdapter()

    with pytest.raises(SyncError):
        run_sync(repo_root=repo_root, gh=gh, only="9999", now=lambda: _FIXED_NOW)


def test_self_provisioning_idempotent_across_two_runs(tmp_path: Path) -> None:
    repo_root = _make_repo(
        tmp_path,
        specs={"0031": _spec_text("0031", "Sync-Feature", "Accepted")},
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
    assert "0031" in state.features
    assert "0032" not in state.features


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
    )
    gh = FakeGhAdapter()

    run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)

    state = load_state(repo_root / "specs" / ".github-sync-state.json")
    assert "0031" not in state.features


# -- Superseded: Status-Feld leeren + Label statt Feldwert (Spec 0052 / ADR 0030, Abschnitt 2) --


def test_superseded_status_clears_status_field_and_sets_label(tmp_path: Path) -> None:
    repo_root = _make_repo(
        tmp_path,
        specs={"0003": _spec_text("0003", "Alte Spec", "Superseded")},
    )
    gh = FakeGhAdapter()

    result = run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)

    assert result.specs[0].classification == "created"
    item_id = next(iter(gh.items))
    assert gh.items[item_id]["F_STATUS"] is None  # Feld geleert statt eines Werts
    issue_number = result.specs[0].issue_number
    assert issue_number is not None
    assert "superseded" in gh.issue(issue_number).labels
    assert gh.issue(issue_number).state == "closed"  # nativer Issue-Zustand bleibt geschlossen


def test_superseded_label_removed_when_status_changes_back(tmp_path: Path) -> None:
    content_zone = "## Ziel\n\nText.\n"
    push_hash = push_state_hash(status="Superseded", content_zone=content_zone)

    repo_root = _make_repo(
        tmp_path,
        specs={"0003": _spec_text("0003", "Alte Spec", "Accepted", ziel="Text.")},
        state={"0003": _existing_state_entry(issue_number=42, push_hash=push_hash)},
    )
    gh = FakeGhAdapter()
    gh.seed_issue(
        42,
        body=build_issue_body("0003", content_zone),
        state="closed",
        labels=frozenset({"superseded"}),
    )

    run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)

    assert "superseded" not in gh.issue(42).labels


def test_non_superseded_status_never_gets_superseded_label(tmp_path: Path) -> None:
    repo_root = _make_repo(
        tmp_path,
        specs={"0031": _spec_text("0031", "Sync-Feature", "Accepted")},
    )
    gh = FakeGhAdapter()

    result = run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)

    issue_number = result.specs[0].issue_number
    assert issue_number is not None
    assert "superseded" not in gh.issue(issue_number).labels


# -- State-Datei-Migration End-to-End (altes flaches Format -> voller Lauf -> neues Format) ----


def test_full_run_over_legacy_flat_state_does_not_reclassify_as_created(tmp_path: Path) -> None:
    content_zone = "## Ziel\n\nText.\n"
    push_hash = push_state_hash(status="Accepted", content_zone=content_zone)

    repo_root = _make_repo(
        tmp_path,
        specs={"0031": _spec_text("0031", "Sync-Feature", "Accepted", ziel="Text.")},
        legacy_flat_state={"0031": _existing_state_entry(issue_number=42, push_hash=push_hash)},
    )
    gh = FakeGhAdapter()
    gh.seed_issue(42, body=build_issue_body("0031", content_zone))

    result = run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)

    assert result.specs[0].classification == "unchanged"  # nicht faelschlich "created"

    raw = json.loads((repo_root / "specs" / ".github-sync-state.json").read_text(encoding="utf-8"))
    assert set(raw.keys()) == {"features", "stories"}
    assert raw["features"]["0031"]["issue_number"] == 42


def test_full_run_over_old_inbox_namespace_state_does_not_touch_orphaned_inbox_issues(
    tmp_path: Path,
) -> None:
    # Testkonzept-Ergaenzung "Erweiterung fuer ADR 0036" (specs/architecture/0002-testkonzept.md):
    # eine vor Spec 0059 im "inbox"-Namensraum vorliegende Zustandsdatei (Format aus ADR 0030,
    # z.B. fuer die bewusst unangetastet bleibenden Alteintraege 0027/0031) darf nach diesem
    # Umbau NICHT dazu fuehren, dass die verwaisten alten Inbox-Issues angefasst/geschlossen
    # werden - load_state() ignoriert den "inbox"-Schluessel bereits beim Lesen (siehe
    # test_state.py), hier zusaetzlich End-to-End ueber einen vollen Sync-Lauf nachgewiesen.
    content_zone = "## Ziel\n\nText.\n"
    push_hash = push_state_hash(status="Accepted", content_zone=content_zone)

    repo_root = _make_repo(
        tmp_path,
        specs={"0031": _spec_text("0031", "Sync-Feature", "Accepted", ziel="Text.")},
        raw_state={
            "features": {"0031": _existing_state_entry(issue_number=42, push_hash=push_hash)},
            "inbox": {"0027": _existing_state_entry(issue_number=77, push_hash="alt-push")},
        },
    )
    gh = FakeGhAdapter()
    gh.seed_issue(42, body=build_issue_body("0031", content_zone))
    gh.seed_issue(77, body="<!-- photosort-inbox: 0027 -->\n\n## Rohtext\n\nAlt.\n")

    result = run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)

    assert result.specs[0].classification == "unchanged"
    assert result.orphaned == []  # das verwaiste alte Inbox-Issue zaehlt NICHT als Feature-Orphan
    # Das alte Inbox-Issue #77 bleibt komplett unangetastet - weder geschlossen noch kommentiert:
    assert gh.issue(77).state == "open"
    assert gh.issue(77).comments == []

    raw = json.loads((repo_root / "specs" / ".github-sync-state.json").read_text(encoding="utf-8"))
    assert set(raw.keys()) == {"features", "stories"}
    assert "inbox" not in raw
    assert raw["features"]["0031"]["issue_number"] == 42


# -- Dateiloser Story-Pfad: --create-issue (Spec 0059 / ADR 0036, Abschnitt 5) -----------------


def test_create_story_issue_sets_unrefined_status_and_idee_label(tmp_path: Path) -> None:
    repo_root = _make_repo(tmp_path, specs={})
    gh = FakeGhAdapter()

    issue_number = create_story_issue(
        repo_root=repo_root,
        gh=gh,
        typ="idee",
        title="Story-Titel",
        body="Rohtext der Idee.",
        now=lambda: _FIXED_NOW,
    )

    issue = gh.issue(issue_number)
    assert issue.title == "Story-Titel"
    assert issue.body == "Rohtext der Idee."  # kein Marker-Kommentar (ADR 0036, Abschnitt 1)
    assert issue.state == "open"
    assert "idee" in issue.labels

    item_id = next(iter(gh.items))
    assert gh.items[item_id]["F_STATUS"] == "S_Unrefined"
    assert "F_PRIO" not in gh.items[item_id]  # Prioritaet nie gesetzt, nicht aktiv geleert

    state = load_state(repo_root / "specs" / ".github-sync-state.json")
    assert state.stories[str(issue_number)].issue_number == issue_number
    assert state.stories[str(issue_number)].item_id == item_id


def test_create_story_issue_bug_type_reuses_existing_bug_label(tmp_path: Path) -> None:
    repo_root = _make_repo(tmp_path, specs={})
    gh = FakeGhAdapter()

    issue_number = create_story_issue(
        repo_root=repo_root, gh=gh, typ="bug", title="Titel", body="Text.", now=lambda: _FIXED_NOW
    )

    assert "bug" in gh.ensure_label_calls
    assert "bug" not in gh.ensure_label_created  # existierte bereits im (Fake-)Repo
    assert "bug" in gh.issue(issue_number).labels


def test_create_story_issue_rejects_unknown_type(tmp_path: Path) -> None:
    repo_root = _make_repo(tmp_path, specs={})
    gh = FakeGhAdapter()

    with pytest.raises(SyncError):
        create_story_issue(
            repo_root=repo_root, gh=gh, typ="voellig-unbekannt", title="Titel", body="Text."
        )


# -- Dateiloser Story-Pfad: --only issue:NNN (Body/Status setzen) ------------------------------


def test_sync_story_sets_status_and_body(tmp_path: Path) -> None:
    repo_root = _make_repo(
        tmp_path,
        specs={},
        stories_state={"215": _story_state_entry_dict(issue_number=215, item_id="ITEM_1")},
    )
    gh = FakeGhAdapter()
    gh.seed_issue(215, body="Alter Rohtext.")
    gh.items["ITEM_1"] = {}

    result = sync_story(
        repo_root=repo_root,
        gh=gh,
        issue_number=215,
        status="Ready",
        body="## Ziel\n\nNeuer Inhalt.\n",
        now=lambda: _FIXED_NOW,
    )

    assert result["status"] == "Ready"
    assert "priority" not in result  # ADR 0039: kein Prioritaets-Feld im Ergebnis
    assert gh.issue(215).body == "## Ziel\n\nNeuer Inhalt.\n"
    assert gh.items["ITEM_1"]["F_STATUS"] == "S_Ready"
    # ADR 0039: das Prioritaets-Feld wird nie geschrieben.
    assert "F_PRIO" not in gh.items["ITEM_1"]
    assert all(field_id != "F_PRIO" for _, field_id in gh.single_select_writes)
    assert all(field_id != "F_PRIO" for _, field_id in gh.cleared_fields)

    state = load_state(repo_root / "specs" / ".github-sync-state.json")
    assert state.stories["215"].last_synced_at == _FIXED_NOW


def test_sync_story_without_status_or_body_changes_no_item_fields_or_body(tmp_path: Path) -> None:
    # ADR 0039: ohne --status/--body-file aendert sync_story() keine Item-Felder und keinen
    # Issue-Body mehr (frueher wurde hier die Prioritaet aus roadmap.md gepusht). Der
    # last_synced_at-Touch in der lokalen State-Datei bleibt.
    repo_root = _make_repo(
        tmp_path,
        specs={},
        stories_state={"215": _story_state_entry_dict(issue_number=215, item_id="ITEM_1")},
    )
    gh = FakeGhAdapter()
    gh.seed_issue(215, body="Unveraendert.")
    gh.items["ITEM_1"] = {"F_PRIO": "P_Hoch"}

    sync_story(repo_root=repo_root, gh=gh, issue_number=215, now=lambda: _FIXED_NOW)

    assert gh.issue(215).body == "Unveraendert."
    assert gh.items["ITEM_1"] == {"F_PRIO": "P_Hoch"}  # vorab gesetzter Wert ueberlebt unveraendert
    assert gh.single_select_writes == []
    assert gh.cleared_fields == []

    state = load_state(repo_root / "specs" / ".github-sync-state.json")
    assert state.stories["215"].last_synced_at == _FIXED_NOW  # lokaler Touch bleibt


def test_sync_story_raises_for_unknown_issue(tmp_path: Path) -> None:
    repo_root = _make_repo(tmp_path, specs={})
    gh = FakeGhAdapter()

    with pytest.raises(SyncError):
        sync_story(repo_root=repo_root, gh=gh, issue_number=999)


def test_sync_story_rejects_unknown_status(tmp_path: Path) -> None:
    repo_root = _make_repo(
        tmp_path,
        specs={},
        stories_state={"215": _story_state_entry_dict(issue_number=215, item_id="ITEM_1")},
    )
    gh = FakeGhAdapter()
    gh.seed_issue(215, body="Text.")

    with pytest.raises(SyncError):
        sync_story(repo_root=repo_root, gh=gh, issue_number=215, status="VoelligUnbekannt")


@pytest.mark.parametrize("status", ["Todo", "In Progress", "Review"])
def test_sync_story_rejects_feature_only_board_statuses(tmp_path: Path, status: str) -> None:
    # Seit Spec 0060 / ADR 0037, Abschnitt 6: die Statuswert-Validierung fuer Stories ist auf
    # {"Unrefined", "Ready", "Done"} verengt - die drei neuen Umsetzungsfortschritt-Werte sind
    # nur fuer Feature-Specs sinnvoll (kein Baseline/Override-Modell fuer dateilose Stories).
    repo_root = _make_repo(
        tmp_path,
        specs={},
        stories_state={"215": _story_state_entry_dict(issue_number=215, item_id="ITEM_1")},
    )
    gh = FakeGhAdapter()
    gh.seed_issue(215, body="Text.")

    with pytest.raises(SyncError):
        sync_story(repo_root=repo_root, gh=gh, issue_number=215, status=status)


def test_sync_story_done_closes_the_issue(tmp_path: Path) -> None:
    # Abschnitt 6: eine ohne technische Umsetzung verworfene Story wird bei --status Done
    # zusaetzlich geschlossen (sync_story() ist der einzige Ort, der das nativ tut).
    repo_root = _make_repo(
        tmp_path,
        specs={},
        stories_state={"215": _story_state_entry_dict(issue_number=215, item_id="ITEM_1")},
    )
    gh = FakeGhAdapter()
    gh.seed_issue(215, body="Text.", state="open")
    gh.items["ITEM_1"] = {}

    sync_story(repo_root=repo_root, gh=gh, issue_number=215, status="Done", now=lambda: _FIXED_NOW)

    assert gh.issue(215).state == "closed"
    assert gh.items["ITEM_1"]["F_STATUS"] == "S_Done"


def test_sync_story_ready_status_does_not_close_the_issue(tmp_path: Path) -> None:
    repo_root = _make_repo(
        tmp_path,
        specs={},
        stories_state={"215": _story_state_entry_dict(issue_number=215, item_id="ITEM_1")},
    )
    gh = FakeGhAdapter()
    gh.seed_issue(215, body="Text.", state="open")

    sync_story(repo_root=repo_root, gh=gh, issue_number=215, status="Ready", now=lambda: _FIXED_NOW)

    assert gh.issue(215).state == "open"


# -- Dateiloser Story-Pfad: --only issue:NNN --show-status (rein lesend) -----------------------


def test_show_story_status_returns_current_status_without_changing_anything(tmp_path: Path) -> None:
    repo_root = _make_repo(
        tmp_path,
        specs={},
        stories_state={"215": _story_state_entry_dict(issue_number=215, item_id="ITEM_1")},
    )
    gh = FakeGhAdapter()
    gh.seed_issue(215, body="Text.")
    project = gh.ensure_project()
    fields = gh.ensure_fields(project)
    gh.items["ITEM_1"] = {fields.status_field_id: fields.status_options["Ready"]}

    status = show_story_status(repo_root=repo_root, gh=gh, issue_number=215)

    assert status == "Ready"
    # Rein lesend - Issue/Item unveraendert:
    assert gh.issue(215).body == "Text."
    assert gh.items["ITEM_1"][fields.status_field_id] == fields.status_options["Ready"]


def test_show_story_status_raises_for_unknown_issue(tmp_path: Path) -> None:
    repo_root = _make_repo(tmp_path, specs={})
    gh = FakeGhAdapter()

    with pytest.raises(SyncError):
        show_story_status(repo_root=repo_root, gh=gh, issue_number=999)


def test_show_story_status_raises_helpful_error_when_already_adopted(tmp_path: Path) -> None:
    content_zone = "## Ziel\n\nText.\n"
    push_hash = push_state_hash(status="Accepted", content_zone=content_zone)
    repo_root = _make_repo(
        tmp_path,
        specs={},
        state={"0052": _existing_state_entry(issue_number=215, push_hash=push_hash)},
    )
    gh = FakeGhAdapter()

    with pytest.raises(SyncError, match="0052|adoptiert"):
        show_story_status(repo_root=repo_root, gh=gh, issue_number=215)


# -- Story -> Feature-Spec-Uebergang: --only NNNN --adopt-issue MMM (ADR 0036, Abschnitt 6) ----


def test_adopt_issue_migrates_story_state_into_features_and_writes_marker(tmp_path: Path) -> None:
    repo_root = _make_repo(
        tmp_path,
        specs={"0052": _spec_text("0052", "Neue Spec", "Accepted")},
        stories_state={"215": _story_state_entry_dict(issue_number=215, item_id="ITEM_1")},
    )
    gh = FakeGhAdapter()
    gh.seed_issue(215, body="Story-Rohtext, kein Marker.")
    gh.items["ITEM_1"] = {}

    result = run_sync(
        repo_root=repo_root, gh=gh, only="0052", adopt_issue=215, now=lambda: _FIXED_NOW
    )

    assert result.adopted is not None
    assert result.adopted.spec_number == "0052"
    assert result.adopted.issue_number == 215
    assert result.specs[0].classification == "pushed"
    assert result.specs[0].issue_number == 215

    issue = gh.issue(215)
    assert issue.body.startswith("<!-- photosort-spec: 0052 -->")
    assert gh.items["ITEM_1"]["F_STATUS"] == "S_Todo"  # Baseline Accepted -> Todo (ADR 0037)
    assert "F_PRIO" not in gh.items["ITEM_1"]  # ADR 0039: Prioritaet nie angefasst

    state = load_state(repo_root / "specs" / ".github-sync-state.json")
    assert "215" not in state.stories
    assert state.features["0052"].issue_number == 215
    assert state.features["0052"].item_id == "ITEM_1"

    # Kein zweites Issue/Item angelegt:
    assert len(gh.items) == 1


def test_adopt_issue_subsequent_run_is_a_normal_feature_sync(tmp_path: Path) -> None:
    repo_root = _make_repo(
        tmp_path,
        specs={"0052": _spec_text("0052", "Neue Spec", "Accepted")},
        stories_state={"215": _story_state_entry_dict(issue_number=215, item_id="ITEM_1")},
    )
    gh = FakeGhAdapter()
    gh.seed_issue(215, body="Story-Rohtext, kein Marker.")
    gh.items["ITEM_1"] = {}
    run_sync(repo_root=repo_root, gh=gh, only="0052", adopt_issue=215, now=lambda: _FIXED_NOW)

    result_again = run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)

    assert result_again.specs[0].classification == "unchanged"


def test_adopt_issue_requires_only_feature_scope(tmp_path: Path) -> None:
    repo_root = _make_repo(
        tmp_path,
        specs={},
        stories_state={"215": _story_state_entry_dict(issue_number=215, item_id="ITEM_1")},
    )
    gh = FakeGhAdapter()
    gh.seed_issue(215, body="Text.")

    with pytest.raises(SyncError):
        run_sync(repo_root=repo_root, gh=gh, adopt_issue=215, now=lambda: _FIXED_NOW)


def test_adopt_issue_raises_when_no_story_state_entry_exists(tmp_path: Path) -> None:
    repo_root = _make_repo(
        tmp_path,
        specs={"0052": _spec_text("0052", "Neue Spec", "Accepted")},
    )
    gh = FakeGhAdapter()

    with pytest.raises(SyncError):
        run_sync(repo_root=repo_root, gh=gh, only="0052", adopt_issue=999, now=lambda: _FIXED_NOW)


def test_adopt_issue_raises_when_feature_already_has_state_entry(tmp_path: Path) -> None:
    content_zone = "## Ziel\n\nText.\n"
    push_hash = push_state_hash(status="Accepted", content_zone=content_zone)
    repo_root = _make_repo(
        tmp_path,
        specs={"0052": _spec_text("0052", "Neue Spec", "Accepted", ziel="Text.")},
        state={"0052": _existing_state_entry(issue_number=42, push_hash=push_hash)},
        stories_state={"215": _story_state_entry_dict(issue_number=215, item_id="ITEM_1")},
    )
    gh = FakeGhAdapter()
    gh.seed_issue(42, body=build_issue_body("0052", content_zone))
    gh.seed_issue(215, body="Story-Rohtext.")

    with pytest.raises(SyncError):
        run_sync(repo_root=repo_root, gh=gh, only="0052", adopt_issue=215, now=lambda: _FIXED_NOW)


# -- ADR 0039: das Board-Feld `Prioritaet` wird auf keinem Pfad geschrieben --------------------


def _assert_priority_field_untouched(gh: FakeGhAdapter) -> None:
    assert all(field_id != "F_PRIO" for _, field_id in gh.single_select_writes)
    assert all(field_id != "F_PRIO" for _, field_id in gh.cleared_fields)


def test_full_run_never_writes_priority_and_preexisting_value_survives(tmp_path: Path) -> None:
    content_zone = "## Ziel\n\nText.\n"
    push_hash = push_state_hash(status="Accepted", content_zone=content_zone)
    repo_root = _make_repo(
        tmp_path,
        specs={"0031": _spec_text("0031", "Sync-Feature", "Accepted", ziel="Text.")},
        state={"0031": _existing_state_entry(issue_number=42, push_hash=push_hash)},
    )
    gh = FakeGhAdapter()
    gh.seed_issue(42, body=build_issue_body("0031", content_zone))
    gh.items["ITEM_1"] = {"F_PRIO": "P_Hoch"}

    run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)

    assert gh.items["ITEM_1"]["F_PRIO"] == "P_Hoch"
    _assert_priority_field_untouched(gh)


def test_only_scope_never_writes_priority_and_preexisting_value_survives(tmp_path: Path) -> None:
    repo_root = _make_repo(
        tmp_path,
        specs={"0032": _spec_text("0032", "Neues Feature", "Accepted")},
    )
    gh = FakeGhAdapter()

    run_sync(repo_root=repo_root, gh=gh, only="0032", now=lambda: _FIXED_NOW)

    item_id = next(iter(gh.items))
    assert "F_PRIO" not in gh.items[item_id]
    _assert_priority_field_untouched(gh)


def test_only_issue_scope_never_writes_priority(tmp_path: Path) -> None:
    repo_root = _make_repo(
        tmp_path,
        specs={},
        stories_state={"215": _story_state_entry_dict(issue_number=215, item_id="ITEM_1")},
    )
    gh = FakeGhAdapter()
    gh.seed_issue(215, body="Text.")
    gh.items["ITEM_1"] = {"F_PRIO": "P_Hoch"}

    sync_story(repo_root=repo_root, gh=gh, issue_number=215, status="Ready", now=lambda: _FIXED_NOW)

    assert gh.items["ITEM_1"]["F_PRIO"] == "P_Hoch"
    _assert_priority_field_untouched(gh)


def test_adopt_issue_never_writes_priority(tmp_path: Path) -> None:
    repo_root = _make_repo(
        tmp_path,
        specs={"0052": _spec_text("0052", "Neue Spec", "Accepted")},
        stories_state={"215": _story_state_entry_dict(issue_number=215, item_id="ITEM_1")},
    )
    gh = FakeGhAdapter()
    gh.seed_issue(215, body="Story-Rohtext, kein Marker.")
    gh.items["ITEM_1"] = {"F_PRIO": "P_Mittel"}

    run_sync(repo_root=repo_root, gh=gh, only="0052", adopt_issue=215, now=lambda: _FIXED_NOW)

    assert gh.items["ITEM_1"]["F_PRIO"] == "P_Mittel"
    _assert_priority_field_untouched(gh)


def test_runtime_status_scope_never_writes_priority(tmp_path: Path) -> None:
    content_zone = "## Ziel\n\nText.\n"
    push_hash = push_state_hash(status="Accepted", content_zone=content_zone)
    repo_root = _make_repo(
        tmp_path,
        specs={"0031": _spec_text("0031", "Sync-Feature", "Accepted", ziel="Text.")},
        state={"0031": _existing_state_entry(issue_number=42, push_hash=push_hash)},
    )
    gh = FakeGhAdapter()
    gh.seed_issue(42, body=build_issue_body("0031", content_zone))
    gh.items["ITEM_1"] = {"F_PRIO": "P_Hoch"}

    set_feature_runtime_status(
        repo_root=repo_root,
        gh=gh,
        spec_number="0031",
        runtime_status="In Progress",
        now=lambda: _FIXED_NOW,
    )

    assert gh.items["ITEM_1"]["F_PRIO"] == "P_Hoch"
    _assert_priority_field_untouched(gh)


def test_superseded_path_only_clears_the_status_field_not_priority(tmp_path: Path) -> None:
    repo_root = _make_repo(
        tmp_path,
        specs={"0003": _spec_text("0003", "Alte Spec", "Superseded")},
    )
    gh = FakeGhAdapter()

    run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)

    assert gh.cleared_fields == [(next(iter(gh.items)), "F_STATUS")]
    _assert_priority_field_untouched(gh)


# -- ADR 0039: einmalige, gutartige Selbstheilung der Baseline nach der Hash-Signaturaenderung --


def _legacy_priority_push_hash(*, status: str, content_zone: str, priority: str) -> str:
    """Bildet den `pushed_state_hash` nach der ALTEN, prioritaetshaltigen Formel nach
    (STATUS/PRIORITY/---/content_zone) - so lag er vor ADR 0039 in .github-sync-state.json."""
    composite = f"STATUS:{status}\nPRIORITY:{priority}\n---\n{content_zone}"
    return text_hash(composite)


def test_old_priority_baseline_heals_once_as_pushed_then_stays_unchanged(tmp_path: Path) -> None:
    content_zone = "## Ziel\n\nText.\n"
    legacy_hash = _legacy_priority_push_hash(
        status="Accepted", content_zone=content_zone, priority="Niedrig"
    )
    repo_root = _make_repo(
        tmp_path,
        specs={"0031": _spec_text("0031", "Sync-Feature", "Accepted", ziel="Text.")},
        state={"0031": _existing_state_entry(issue_number=42, push_hash=legacy_hash)},
    )
    gh = FakeGhAdapter()
    gh.seed_issue(42, body=build_issue_body("0031", content_zone))

    first = run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)
    assert first.specs[0].classification == "pushed"
    # identischer Re-Push, Inhalt unveraendert:
    assert content_zone.strip() in gh.issue(42).body

    second = run_sync(repo_root=repo_root, gh=gh, now=lambda: _FIXED_NOW)
    assert second.specs[0].classification == "unchanged"


# -- set_feature_runtime_status() (--only NNNN --runtime-status ...): leichtgewichtiger,
# zielgerichteter Schreibzugriff ohne vollen Content-Abgleich (Spec 0060 / ADR 0037, Abschnitt 3) -


def test_set_feature_runtime_status_sets_in_progress_when_baseline_is_todo(tmp_path: Path) -> None:
    content_zone = "## Ziel\n\nText.\n"
    push_hash = push_state_hash(status="Accepted", content_zone=content_zone)
    repo_root = _make_repo(
        tmp_path,
        specs={"0031": _spec_text("0031", "Sync-Feature", "Accepted", ziel="Text.")},
        state={"0031": _existing_state_entry(issue_number=42, push_hash=push_hash)},
    )
    gh = FakeGhAdapter()
    gh.seed_issue(42, body=build_issue_body("0031", content_zone))
    gh.items["ITEM_1"] = {}

    result = set_feature_runtime_status(
        repo_root=repo_root,
        gh=gh,
        spec_number="0031",
        runtime_status="In Progress",
        now=lambda: _FIXED_NOW,
    )

    assert result == {"spec_number": "0031", "runtime_status": "In Progress", "pr_number": None}
    assert gh.items["ITEM_1"]["F_STATUS"] == "S_In Progress"

    state = load_state(repo_root / "specs" / ".github-sync-state.json")
    assert state.features["0031"].runtime_status == "In Progress"
    assert state.features["0031"].pr_number is None
    assert state.features["0031"].last_synced_at == _FIXED_NOW
    # Hash bleibt unangetastet - kein voller Content-Abgleich:
    assert state.features["0031"].pushed_state_hash == push_hash


def test_set_feature_runtime_status_sets_review_with_pr_number(tmp_path: Path) -> None:
    content_zone = "## Ziel\n\nText.\n"
    push_hash = push_state_hash(status="Accepted", content_zone=content_zone)
    repo_root = _make_repo(
        tmp_path,
        specs={"0031": _spec_text("0031", "Sync-Feature", "Accepted", ziel="Text.")},
        state={"0031": _existing_state_entry(issue_number=42, push_hash=push_hash)},
    )
    gh = FakeGhAdapter()
    gh.seed_issue(42, body=build_issue_body("0031", content_zone))
    gh.items["ITEM_1"] = {}

    result = set_feature_runtime_status(
        repo_root=repo_root,
        gh=gh,
        spec_number="0031",
        runtime_status="Review",
        pr_number=101,
        now=lambda: _FIXED_NOW,
    )

    assert result == {"spec_number": "0031", "runtime_status": "Review", "pr_number": 101}
    assert gh.items["ITEM_1"]["F_STATUS"] == "S_Review"

    state = load_state(repo_root / "specs" / ".github-sync-state.json")
    assert state.features["0031"].runtime_status == "Review"
    assert state.features["0031"].pr_number == 101


def test_set_feature_runtime_status_raises_when_baseline_is_not_todo(tmp_path: Path) -> None:
    content_zone = "## Ziel\n\nText.\n"
    push_hash = push_state_hash(status="Implemented", content_zone=content_zone)
    repo_root = _make_repo(
        tmp_path,
        specs={"0031": _spec_text("0031", "Sync-Feature", "Implemented", ziel="Text.")},
        state={"0031": _existing_state_entry(issue_number=42, push_hash=push_hash)},
    )
    gh = FakeGhAdapter()
    gh.seed_issue(42, body=build_issue_body("0031", content_zone), state="closed")

    with pytest.raises(SyncError, match="Todo"):
        set_feature_runtime_status(
            repo_root=repo_root, gh=gh, spec_number="0031", runtime_status="In Progress"
        )


def test_set_feature_runtime_status_raises_when_no_state_entry_exists(tmp_path: Path) -> None:
    repo_root = _make_repo(
        tmp_path,
        specs={"0031": _spec_text("0031", "Sync-Feature", "Accepted")},
    )
    gh = FakeGhAdapter()

    with pytest.raises(SyncError):
        set_feature_runtime_status(
            repo_root=repo_root, gh=gh, spec_number="0031", runtime_status="In Progress"
        )


def test_set_feature_runtime_status_rejects_unknown_value(tmp_path: Path) -> None:
    content_zone = "## Ziel\n\nText.\n"
    push_hash = push_state_hash(status="Accepted", content_zone=content_zone)
    repo_root = _make_repo(
        tmp_path,
        specs={"0031": _spec_text("0031", "Sync-Feature", "Accepted", ziel="Text.")},
        state={"0031": _existing_state_entry(issue_number=42, push_hash=push_hash)},
    )
    gh = FakeGhAdapter()
    gh.seed_issue(42, body=build_issue_body("0031", content_zone))

    with pytest.raises(SyncError):
        set_feature_runtime_status(
            repo_root=repo_root, gh=gh, spec_number="0031", runtime_status="Done"
        )


def test_set_feature_runtime_status_review_requires_pr_number(tmp_path: Path) -> None:
    # Copilot-Review-Finding auf PR #229: bisher erzwang nur cli.py "Review braucht pr_number" -
    # die Funktion selbst akzeptierte jede Kombination, was einen inkonsistenten State-Eintrag
    # (runtime_status="Review" ohne pr_number) erzeugen und die spaetere Merge-Erkennung in
    # _sync_one() verhindern konnte (deren Guard-Bedingung pr_number is not None voraussetzt).
    content_zone = "## Ziel\n\nText.\n"
    push_hash = push_state_hash(status="Accepted", content_zone=content_zone)
    repo_root = _make_repo(
        tmp_path,
        specs={"0031": _spec_text("0031", "Sync-Feature", "Accepted", ziel="Text.")},
        state={"0031": _existing_state_entry(issue_number=42, push_hash=push_hash)},
    )
    gh = FakeGhAdapter()
    gh.seed_issue(42, body=build_issue_body("0031", content_zone))

    with pytest.raises(SyncError, match="pr_number|PR-Nummer"):
        set_feature_runtime_status(
            repo_root=repo_root, gh=gh, spec_number="0031", runtime_status="Review"
        )

    # Kein State-Eintrag mit inkonsistenter Kombination geschrieben:
    state = load_state(repo_root / "specs" / ".github-sync-state.json")
    assert state.features["0031"].runtime_status is None


def test_set_feature_runtime_status_in_progress_rejects_pr_number(tmp_path: Path) -> None:
    content_zone = "## Ziel\n\nText.\n"
    push_hash = push_state_hash(status="Accepted", content_zone=content_zone)
    repo_root = _make_repo(
        tmp_path,
        specs={"0031": _spec_text("0031", "Sync-Feature", "Accepted", ziel="Text.")},
        state={"0031": _existing_state_entry(issue_number=42, push_hash=push_hash)},
    )
    gh = FakeGhAdapter()
    gh.seed_issue(42, body=build_issue_body("0031", content_zone))

    with pytest.raises(SyncError, match="pr_number|PR-Nummer"):
        set_feature_runtime_status(
            repo_root=repo_root,
            gh=gh,
            spec_number="0031",
            runtime_status="In Progress",
            pr_number=101,
        )

    state = load_state(repo_root / "specs" / ".github-sync-state.json")
    assert state.features["0031"].runtime_status is None
