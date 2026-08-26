from __future__ import annotations

import json
from pathlib import Path

import pytest

from github_project_sync.classify import SyncStateEntry
from github_project_sync.state import (
    NestedState,
    StoryStateEntry,
    find_orphaned_numbers,
    load_state,
    save_state,
)

_ENTRY = SyncStateEntry(
    issue_number=42,
    item_id="ITEM_1",
    pushed_state_hash="abc",
    pulled_body_hash="def",
    last_synced_at="2026-08-09T00:00:00Z",
)

_STORY_ENTRY = StoryStateEntry(
    issue_number=215,
    item_id="ITEM_9",
    last_synced_at="2026-08-20T00:00:00Z",
)


def test_load_state_returns_empty_namespaces_when_file_missing(tmp_path: Path) -> None:
    state = load_state(tmp_path / ".github-sync-state.json")

    assert state == NestedState(features={}, stories={})


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
                "stories": {
                    "215": {
                        "issue_number": 215,
                        "item_id": "ITEM_9",
                        "last_synced_at": "2026-08-20T00:00:00Z",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    state = load_state(state_path)

    assert state.features["0031"] == _ENTRY
    assert state.stories["215"] == _STORY_ENTRY


def test_load_state_migrates_flat_legacy_format_transparently(tmp_path: Path) -> None:
    # Altformat (vor Spec 0052): flaches {"NNNN": {...}} ohne Top-Level-Schluessel
    # "features"/"stories" - wird transparent als {"features": <alt>, "stories": {}} gelesen.
    # Bereits bekannte Feature-Eintraege duerfen dabei nicht faelschlich als "created" neu
    # klassifiziert werden - das pruefen wir hier ueber die unveraendert erhaltenen
    # Hash-/Issue-Werte.
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
    assert state.stories == {}


def test_load_state_ignores_old_inbox_namespace_instead_of_crashing(tmp_path: Path) -> None:
    # Seit Spec 0059 / ADR 0036: ein altes "inbox"-Vorkommen (Format vor dieser Umsetzung) wird
    # beim Laden ignoriert statt zum Absturz zu fuehren - bewusster, einmaliger Datenverlust nur
    # fuer diesen bereits obsoleten Namensraum.
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
                    "0027": {
                        "issue_number": 77,
                        "item_id": "ITEM_OLD",
                        "pushed_state_hash": "x",
                        "pulled_body_hash": "y",
                        "last_synced_at": "2026-08-01T00:00:00Z",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    state = load_state(state_path)

    assert state.features["0031"] == _ENTRY
    assert state.stories == {}


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
                "stories": {},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_state(state_path)


def test_load_state_rejects_invalid_issue_number_keys_in_stories(tmp_path: Path) -> None:
    state_path = tmp_path / ".github-sync-state.json"
    state_path.write_text(
        json.dumps(
            {
                "features": {},
                "stories": {
                    "../etc/passwd": {
                        "issue_number": 1,
                        "item_id": "x",
                        "last_synced_at": "2026-08-09T00:00:00Z",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_state(state_path)


def test_load_state_rejects_leading_zero_issue_number_keys_in_stories(tmp_path: Path) -> None:
    state_path = tmp_path / ".github-sync-state.json"
    state_path.write_text(
        json.dumps(
            {
                "features": {},
                "stories": {
                    "0215": {
                        "issue_number": 215,
                        "item_id": "x",
                        "last_synced_at": "2026-08-09T00:00:00Z",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_state(state_path)


def test_load_state_rejects_story_key_issue_number_drift(tmp_path: Path) -> None:
    # Copilot-Review-Finding auf PR #220: der JSON-Schluessel (String-Issue-Nummer) wurde bisher
    # nur auf Format geprueft, nie gegen entry["issue_number"] abgeglichen - eine manuell
    # inkonsistent editierte Zustandsdatei (Schluessel "215" mit issue_number=999) haette sonst
    # zu einem falschen item_id-Lookup fuer Operationen auf Issue 215 fuehren koennen.
    state_path = tmp_path / ".github-sync-state.json"
    state_path.write_text(
        json.dumps(
            {
                "features": {},
                "stories": {
                    "215": {
                        "issue_number": 999,
                        "item_id": "ITEM_1",
                        "last_synced_at": "2026-08-09T00:00:00Z",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="215.*999|999.*215"):
        load_state(state_path)


def test_save_state_round_trips(tmp_path: Path) -> None:
    state_path = tmp_path / ".github-sync-state.json"

    save_state(state_path, NestedState(features={"0031": _ENTRY}, stories={"215": _STORY_ENTRY}))
    reloaded = load_state(state_path)

    assert reloaded == NestedState(features={"0031": _ENTRY}, stories={"215": _STORY_ENTRY})


def test_save_state_writes_nested_format_with_both_namespaces(tmp_path: Path) -> None:
    state_path = tmp_path / ".github-sync-state.json"

    save_state(state_path, NestedState(features={"0031": _ENTRY}, stories={}))

    raw = json.loads(state_path.read_text(encoding="utf-8"))
    assert set(raw.keys()) == {"features", "stories"}
    assert "0031" in raw["features"]
    assert raw["stories"] == {}


def test_save_state_writes_deterministic_sorted_json_with_trailing_newline(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / ".github-sync-state.json"

    save_state(
        state_path,
        NestedState(features={"0099": _ENTRY, "0001": _ENTRY}, stories={}),
    )

    text = state_path.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert text.index('"0001"') < text.index('"0099"')


def test_save_state_sorts_stories_numerically_not_lexically(tmp_path: Path) -> None:
    # "9" < "10" numerisch, aber "10" < "9" lexikalisch - Issue-Nummern haben anders als
    # Spec-Nummern keine feste Breite, deshalb muss hier numerisch sortiert werden.
    state_path = tmp_path / ".github-sync-state.json"
    entry_9 = StoryStateEntry(issue_number=9, item_id="ITEM_9", last_synced_at="t")
    entry_10 = StoryStateEntry(issue_number=10, item_id="ITEM_10", last_synced_at="t")

    save_state(state_path, NestedState(features={}, stories={"10": entry_10, "9": entry_9}))

    text = state_path.read_text(encoding="utf-8")
    assert text.index('"9"') < text.index('"10"')


def test_save_state_after_migration_writes_new_nested_format(tmp_path: Path) -> None:
    # End-to-End der Migration: Alt-Format lesen, unveraendert zurueckschreiben - Ergebnis muss
    # bereits im neuen genesteten Format vorliegen.
    state_path = tmp_path / ".github-sync-state.json"
    state_path.write_text(json.dumps({"0031": _entry_dict()}), encoding="utf-8")

    state = load_state(state_path)
    save_state(state_path, state)

    raw = json.loads(state_path.read_text(encoding="utf-8"))
    assert set(raw.keys()) == {"features", "stories"}
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
