from __future__ import annotations

from github_project_sync.classify import SyncStateEntry, classify


def _state(push_hash: str = "p1", pull_hash: str = "b1") -> SyncStateEntry:
    return SyncStateEntry(
        issue_number=42,
        item_id="item-1",
        pushed_state_hash=push_hash,
        pulled_body_hash=pull_hash,
        last_synced_at="2026-08-09T00:00:00Z",
    )


def test_no_stored_state_is_created() -> None:
    assert classify(None, push_hash_now="p1", pull_hash_now="b1") == "created"


def test_unchanged_when_both_hashes_match_baseline() -> None:
    assert classify(_state(), push_hash_now="p1", pull_hash_now="b1") == "unchanged"


def test_pushed_when_only_push_hash_differs() -> None:
    assert classify(_state(), push_hash_now="p2", pull_hash_now="b1") == "pushed"


def test_pulled_when_only_pull_hash_differs() -> None:
    assert classify(_state(), push_hash_now="p1", pull_hash_now="b2") == "pulled"


def test_conflict_when_both_hashes_differ() -> None:
    assert classify(_state(), push_hash_now="p2", pull_hash_now="b2") == "conflict"
