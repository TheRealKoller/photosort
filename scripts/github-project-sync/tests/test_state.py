from __future__ import annotations

import json
from pathlib import Path

import pytest

from github_project_sync.classify import SyncStateEntry
from github_project_sync.state import NestedState, find_orphaned_numbers, load_state, save_state

_ENTRY = SyncStateEntry(
    issue_number=42,
    item_id="ITEM_1",
    pushed_state_hash="abc",
    pulled_body_hash="def",
    last_synced_at="2026-08-09T00:00:00Z",
)


def test_load_state_returns_empty_namespaces_when_file_missing(tmp_path: Path) -> None:
    state = load_state(tmp_path / ".github-sync-state.json")

    assert state == NestedState(features={}, inbox={})


def test_load_state_parses_existing_nested_entries(tmp_path: Path) -> None:
    state_path = tmp_path / ".github-sync-state.json"
    state_path.write_text(
        json.dumps(
            {
                "features": {
                    "0031": {
                        "issue_number": 42,
                        "item_id": "ITEM_1",
                        "pushed_state_hash": "abc",
                        "pulled_body_hash": "def",
                        "last_synced_at": "2026-08-09T00:00:00Z",
                    }
                },
                "inbox": {
                    "0029": {
                        "issue_number": 99,
                        "item_id": "ITEM_9",
                        "pushed_state_hash": "ghi",
                        "pulled_body_hash": "jkl",
                        "last_synced_at": "2026-08-20T00:00:00Z",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    state = load_state(state_path)

    assert state.features["0031"] == _ENTRY
    assert state.inbox["0029"].issue_number == 99


def test_load_state_migrates_flat_legacy_format_transparently(tmp_path: Path) -> None:
    # Altformat (vor Spec 0052): flaches {"NNNN": {...}} ohne Top-Level-Schluessel
    # "features"/"inbox" - wird transparent als {"features": <alt>, "inbox": {}} gelesen
    # (ADR 0030, Abschnitt 5). Bereits bekannte Feature-Eintraege duerfen dabei nicht
    # faelschlich als "created" neu klassifiziert werden - das pruefen wir hier ueber die
    # unveraendert erhaltenen Hash-/Issue-Werte.
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

    assert state.features["0031"] == _ENTRY
    assert state.inbox == {}


def test_load_state_rejects_invalid_spec_number_keys_in_features(tmp_path: Path) -> None:
    state_path = tmp_path / ".github-sync-state.json"
    state_path.write_text(
        json.dumps(
            {
                "features": {
                    "../etc/passwd": {
                        "issue_number": 1,
                        "item_id": "x",
                        "pushed_state_hash": "a",
                        "pulled_body_hash": "b",
                        "last_synced_at": "2026-08-09T00:00:00Z",
                    }
                },
                "inbox": {},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_state(state_path)


def test_load_state_rejects_invalid_spec_number_keys_in_inbox(tmp_path: Path) -> None:
    state_path = tmp_path / ".github-sync-state.json"
    state_path.write_text(
        json.dumps(
            {
                "features": {},
                "inbox": {
                    "31": {
                        "issue_number": 1,
                        "item_id": "x",
                        "pushed_state_hash": "a",
                        "pulled_body_hash": "b",
                        "last_synced_at": "2026-08-09T00:00:00Z",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_state(state_path)


def test_save_state_round_trips(tmp_path: Path) -> None:
    state_path = tmp_path / ".github-sync-state.json"

    save_state(state_path, NestedState(features={"0031": _ENTRY}, inbox={"0029": _ENTRY}))
    reloaded = load_state(state_path)

    assert reloaded == NestedState(features={"0031": _ENTRY}, inbox={"0029": _ENTRY})


def test_save_state_writes_nested_format_with_both_namespaces(tmp_path: Path) -> None:
    state_path = tmp_path / ".github-sync-state.json"

    save_state(state_path, NestedState(features={"0031": _ENTRY}, inbox={}))

    raw = json.loads(state_path.read_text(encoding="utf-8"))
    assert set(raw.keys()) == {"features", "inbox"}
    assert "0031" in raw["features"]
    assert raw["inbox"] == {}


def test_save_state_writes_deterministic_sorted_json_with_trailing_newline(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / ".github-sync-state.json"

    save_state(
        state_path,
        NestedState(features={"0099": _ENTRY, "0001": _ENTRY}, inbox={}),
    )

    text = state_path.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert text.index('"0001"') < text.index('"0099"')


def test_save_state_after_migration_writes_new_nested_format(tmp_path: Path) -> None:
    # End-to-End der Migration: Alt-Format lesen, unveraendert zurueckschreiben - Ergebnis muss
    # bereits im neuen genesteten Format vorliegen (ADR 0030, Abschnitt 5: "jeder folgende
    # save_state()-Aufruf schreibt bereits im neuen, genesteten Format").
    state_path = tmp_path / ".github-sync-state.json"
    state_path.write_text(json.dumps({"0031": _entry_dict()}), encoding="utf-8")

    state = load_state(state_path)
    save_state(state_path, state)

    raw = json.loads(state_path.read_text(encoding="utf-8"))
    assert set(raw.keys()) == {"features", "inbox"}
    assert raw["features"]["0031"]["issue_number"] == 42


def _entry_dict() -> dict:
    return {
        "issue_number": 42,
        "item_id": "ITEM_1",
        "pushed_state_hash": "abc",
        "pulled_body_hash": "def",
        "last_synced_at": "2026-08-09T00:00:00Z",
    }


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
