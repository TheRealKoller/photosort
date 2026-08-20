from __future__ import annotations

import json
from pathlib import Path

import pytest

from github_project_sync.classify import SyncStateEntry
from github_project_sync.state import find_orphaned_numbers, load_state, save_state


def test_load_state_returns_empty_dict_when_file_missing(tmp_path: Path) -> None:
    state = load_state(tmp_path / ".github-sync-state.json")

    assert state == {}


def test_load_state_parses_existing_entries(tmp_path: Path) -> None:
    state_path = tmp_path / ".github-sync-state.json"
    state_path.write_text(
        json.dumps(
            {
                "0031": {
                    "issue_number": 42,
                    "item_id": "ITEM_1",
                    "pushed_state_hash": "abc",
                    "pulled_body_hash": "def",
                    "last_synced_at": "2026-08-09T00:00:00Z",
                }
            }
        ),
        encoding="utf-8",
    )

    state = load_state(state_path)

    assert state["0031"] == SyncStateEntry(
        issue_number=42,
        item_id="ITEM_1",
        pushed_state_hash="abc",
        pulled_body_hash="def",
        last_synced_at="2026-08-09T00:00:00Z",
    )


def test_load_state_rejects_invalid_spec_number_keys(tmp_path: Path) -> None:
    state_path = tmp_path / ".github-sync-state.json"
    state_path.write_text(
        json.dumps(
            {
                "../etc/passwd": {
                    "issue_number": 1,
                    "item_id": "x",
                    "pushed_state_hash": "a",
                    "pulled_body_hash": "b",
                    "last_synced_at": "2026-08-09T00:00:00Z",
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_state(state_path)


def test_save_state_round_trips(tmp_path: Path) -> None:
    state_path = tmp_path / ".github-sync-state.json"
    entry = SyncStateEntry(
        issue_number=42,
        item_id="ITEM_1",
        pushed_state_hash="abc",
        pulled_body_hash="def",
        last_synced_at="2026-08-09T00:00:00Z",
    )

    save_state(state_path, {"0031": entry})
    reloaded = load_state(state_path)

    assert reloaded == {"0031": entry}


def test_save_state_writes_deterministic_sorted_json_with_trailing_newline(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / ".github-sync-state.json"
    entry = SyncStateEntry(
        issue_number=1, item_id="a", pushed_state_hash="x", pulled_body_hash="y",
        last_synced_at="2026-08-09T00:00:00Z",
    )

    save_state(state_path, {"0099": entry, "0001": entry})

    text = state_path.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert text.index('"0001"') < text.index('"0099"')


def test_find_orphaned_numbers_returns_entries_without_spec_file() -> None:
    state = {
        "0031": SyncStateEntry(1, "a", "x", "y", "2026-08-09T00:00:00Z"),
        "0099": SyncStateEntry(2, "b", "x", "y", "2026-08-09T00:00:00Z"),
    }

    orphaned = find_orphaned_numbers(state, existing_numbers={"0031"})

    assert orphaned == ["0099"]


def test_find_orphaned_numbers_empty_when_all_present() -> None:
    state = {"0031": SyncStateEntry(1, "a", "x", "y", "2026-08-09T00:00:00Z")}

    assert find_orphaned_numbers(state, existing_numbers={"0031"}) == []
