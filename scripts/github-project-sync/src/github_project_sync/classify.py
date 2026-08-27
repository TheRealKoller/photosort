"""Vier-Wege-Konflikt-Klassifikation: (stored_state, push_hash_now, pull_hash_now) -> Fall.

Reine Funktion ohne I/O, siehe ADR decisions/0017-github-projects-v2-spec-sync.md, Abschnitt 6.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SyncClassification = Literal["created", "pushed", "pulled", "conflict", "unchanged"]


@dataclass(frozen=True)
class SyncStateEntry:
    """Ein Eintrag aus specs/.github-sync-state.json (ein Eintrag pro Spec-Nummer).

    runtime_status/pr_number seit Spec 0060 / ADR 0037, Abschnitt 2: optionaler
    Laufzeit-Override ("In Progress"/"Review"/None), der den aus dem Datei-Status berechneten
    Baseline-Board-Wert verfeinert, solange die Baseline "Todo" ist (siehe sync.py,
    _BOARD_STATUS_BASELINE/_RUNTIME_OVERRIDE_STATUSES). pr_number ist die Grundlage fuer die
    automatische Merge-/"Done"-Erkennung, nur gesetzt waehrend runtime_status == "Review".
    """

    issue_number: int
    item_id: str
    pushed_state_hash: str
    pulled_body_hash: str
    last_synced_at: str
    runtime_status: str | None = None
    pr_number: int | None = None


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
