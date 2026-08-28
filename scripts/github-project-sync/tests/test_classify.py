from __future__ import annotations

from github_project_sync.classify import SyncStateEntry, classify


def _state(push_hash: str = "p1") -> SyncStateEntry:
    return SyncStateEntry(
        issue_number=42,
        item_id="item-1",
        pushed_state_hash=push_hash,
        last_synced_at="2026-08-09T00:00:00Z",
    )


def test_no_stored_state_is_created() -> None:
    assert classify(None, push_hash_now="p1") == "created"


def test_unchanged_when_hash_matches_baseline() -> None:
    assert classify(_state(), push_hash_now="p1") == "unchanged"


def test_pushed_when_hash_differs() -> None:
    assert classify(_state(), push_hash_now="p2") == "pushed"


def test_sync_state_entry_runtime_override_fields_default_to_none() -> None:
    # Seit Spec 0060 / ADR 0037, Abschnitt 2: neue, optionale Laufzeit-Override-Felder - eine
    # Spec, die noch nie ueber --runtime-status gesetzt wurde, hat beide auf None.
    entry = _state()

    assert entry.runtime_status is None
    assert entry.pr_number is None


def test_sync_state_entry_accepts_runtime_override_fields() -> None:
    entry = SyncStateEntry(
        issue_number=42,
        item_id="item-1",
        pushed_state_hash="p1",
        last_synced_at="2026-08-09T00:00:00Z",
        runtime_status="Review",
        pr_number=101,
    )

    assert entry.runtime_status == "Review"
    assert entry.pr_number == 101
