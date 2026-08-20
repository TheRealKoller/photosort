"""Lese-/Schreib-Logik fuer die eingecheckte Zustandsdatei specs/.github-sync-state.json.

Ein Eintrag pro Spec-Nummer (ADR decisions/0017-github-projects-v2-spec-sync.md, Abschnitt 6).
Inklusive Aufraeumlogik fuer Eintraege ohne zugehoerige Spec-Datei (Akzeptanzkriterium
"Gelöschte Spec-Datei" in specs/features/0031-zweiwege-sync-specs-github-projekt.md).
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path

from github_project_sync.classify import SyncStateEntry
from github_project_sync.spec_parser import validate_spec_number

StateDict = dict[str, SyncStateEntry]


def load_state(path: Path) -> StateDict:
    if not path.exists():
        return {}

    raw = json.loads(path.read_text(encoding="utf-8"))
    state: StateDict = {}
    for number, entry in raw.items():
        validate_spec_number(number)
        state[number] = SyncStateEntry(
            issue_number=entry["issue_number"],
            item_id=entry["item_id"],
            pushed_state_hash=entry["pushed_state_hash"],
            pulled_body_hash=entry["pulled_body_hash"],
            last_synced_at=entry["last_synced_at"],
        )
    return state


def save_state(path: Path, state: Mapping[str, SyncStateEntry]) -> None:
    for number in state:
        validate_spec_number(number)

    serializable = {
        number: {
            "issue_number": entry.issue_number,
            "item_id": entry.item_id,
            "pushed_state_hash": entry.pushed_state_hash,
            "pulled_body_hash": entry.pulled_body_hash,
            "last_synced_at": entry.last_synced_at,
        }
        for number, entry in sorted(state.items())
    }
    path.write_text(
        json.dumps(serializable, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def find_orphaned_numbers(
    state: Mapping[str, SyncStateEntry], *, existing_numbers: Iterable[str]
) -> list[str]:
    """Spec-Nummern mit State-Eintrag, aber ohne (mehr) zugehoerige Datei unter specs/features/."""
    existing = set(existing_numbers)
    return sorted(number for number in state if number not in existing)
