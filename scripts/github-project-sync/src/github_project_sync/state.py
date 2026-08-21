"""Lese-/Schreib-Logik fuer die eingecheckte Zustandsdatei specs/.github-sync-state.json.

Seit Spec 0052 / ADR decisions/0030-github-sync-natives-status-feld-inbox-einbindung.md,
Abschnitt 5: genestetes Format {"features": {NNNN: entry}, "inbox": {NNNN: entry}} statt eines
flachen {NNNN: entry}-Objekts - zwei unabhaengige Entitaeten (Feature-Specs, Inbox-Eintraege) mit
eigenen, potenziell kollidierenden Nummernkreisen (siehe issue_body.py). load_state() erkennt das
alte, flache Format (keine Top-Level-Schluessel "features"/"inbox") und behandelt es transparent
als {"features": <bisheriger Inhalt>, "inbox": {}} - keine manuelle Migration noetig, jeder
folgende save_state()-Aufruf schreibt bereits im neuen Format.

Inklusive Aufraeumlogik fuer Eintraege ohne zugehoerige Spec-/Inbox-Datei (Akzeptanzkriterium
"Gelöschte Spec-Datei" in specs/features/0031-zweiwege-sync-specs-github-projekt.md, erweitert auf
den Inbox-Namensraum in Spec 0052).
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from github_project_sync.classify import SyncStateEntry
from github_project_sync.spec_parser import validate_spec_number

StateDict = dict[str, SyncStateEntry]

_NAMESPACE_KEYS = ("features", "inbox")


@dataclass(frozen=True)
class NestedState:
    features: StateDict
    inbox: StateDict


def _parse_namespace(raw: Mapping[str, dict]) -> StateDict:
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


def load_state(path: Path) -> NestedState:
    if not path.exists():
        return NestedState(features={}, inbox={})

    raw = json.loads(path.read_text(encoding="utf-8"))

    if not any(key in raw for key in _NAMESPACE_KEYS):
        # Altformat (vor Spec 0052): flaches {"NNNN": {...}}, kein Top-Level-Schluessel
        # "features"/"inbox" vorhanden - transparent als reine Feature-Eintraege lesen.
        return NestedState(features=_parse_namespace(raw), inbox={})

    return NestedState(
        features=_parse_namespace(raw.get("features", {})),
        inbox=_parse_namespace(raw.get("inbox", {})),
    )


def _serialize_namespace(state: Mapping[str, SyncStateEntry]) -> dict:
    for number in state:
        validate_spec_number(number)
    return {
        number: {
            "issue_number": entry.issue_number,
            "item_id": entry.item_id,
            "pushed_state_hash": entry.pushed_state_hash,
            "pulled_body_hash": entry.pulled_body_hash,
            "last_synced_at": entry.last_synced_at,
        }
        for number, entry in sorted(state.items())
    }


def save_state(path: Path, state: NestedState) -> None:
    serializable = {
        "features": _serialize_namespace(state.features),
        "inbox": _serialize_namespace(state.inbox),
    }
    path.write_text(
        json.dumps(serializable, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def find_orphaned_numbers(
    state: Mapping[str, SyncStateEntry], *, existing_numbers: Iterable[str]
) -> list[str]:
    """Nummern mit State-Eintrag, aber ohne (mehr) zugehoerige Datei.

    Arbeitet pro Namensraum (state.features bzw. state.inbox einzeln uebergeben) - kein
    eigenes Wissen ueber Features vs. Inbox noetig, reine Mengendifferenz.
    """
    existing = set(existing_numbers)
    return sorted(number for number in state if number not in existing)
