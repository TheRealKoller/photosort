"""Vier-Wege-Konflikt-Klassifikation: (stored_state, push_hash_now, pull_hash_now) -> Fall.

Reine Funktion ohne I/O, siehe ADR decisions/0017-github-projects-v2-spec-sync.md, Abschnitt 6.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SyncClassification = Literal["created", "pushed", "pulled", "conflict", "unchanged"]


@dataclass(frozen=True)
class SyncStateEntry:
    """Ein Eintrag aus specs/.github-sync-state.json (ein Eintrag pro Spec-Nummer)."""

    issue_number: int
    item_id: str
    pushed_state_hash: str
    pulled_body_hash: str
    last_synced_at: str


def classify(
    stored: SyncStateEntry | None, *, push_hash_now: str, pull_hash_now: str
) -> SyncClassification:
    if stored is None:
        return "created"

    push_changed = push_hash_now != stored.pushed_state_hash
    pull_changed = pull_hash_now != stored.pulled_body_hash

    if push_changed and pull_changed:
        return "conflict"
    if push_changed:
        return "pushed"
    if pull_changed:
        return "pulled"
    return "unchanged"
