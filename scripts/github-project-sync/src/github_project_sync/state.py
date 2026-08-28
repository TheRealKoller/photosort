"""Lese-/Schreib-Logik fuer die eingecheckte Zustandsdatei specs/.github-sync-state.json.

Seit Spec 0059 / ADR decisions/0036-github-issue-natives-story-refinement-inbox-entfaellt.md,
Abschnitt 5: genestetes Format {"features": {NNNN: entry}, "stories": {issue_number: entry}}
statt des vorherigen {"features", "inbox"}-Formats (ADR decisions/0030, Abschnitt 5) - der
"inbox"-Namensraum entfaellt ersatzlos (lokale specs/inbox/*.md-Dateien werden nicht mehr
gesynct), der neue "stories"-Namensraum bildet stattdessen dateilose GitHub-Issue-Stories ab.
Ein Story-Eintrag hat bewusst KEIN Hash-Feld (`pushed_state_hash`) - es gibt nichts zu
vergleichen, da eine Story ausschliesslich im Issue lebt (keine zweite, lokal divergierende
Kopie).

load_state() erkennt weiterhin das ganz alte, flache Format (keine Top-Level-Schluessel
"features"/"stories") und behandelt es transparent als {"features": <bisheriger Inhalt>,
"stories": {}}. Ein ebenfalls noch vorkommendes altes "inbox"-Vorkommen (Format vor dieser
Umsetzung) wird beim Lesen schlicht ignoriert statt zum Absturz zu fuehren - bewusster,
einmaliger Datenverlust nur fuer diesen bereits obsoleten Namensraum (siehe Spec 0059,
Akzeptanzkriterien). Seit Spec 0065 / ADR 0041 gilt dasselbe Prinzip fuer ein noch vorhandenes
`pulled_body_hash`-Feld in einem Feature-Eintrag (Altformat vor dem Wegfall des Content-Pulls):
es wird beim Lesen schlicht nicht mehr referenziert, kein eigener Migrationsschritt noetig -
beim naechsten save_state()-Aufruf verschwindet es selbstheilend aus der Datei.

Inklusive Aufraeumlogik fuer Feature-Eintraege ohne zugehoerige Spec-Datei (Akzeptanzkriterium
"Gelöschte Spec-Datei" in specs/features/0031-zweiwege-sync-specs-github-projekt.md). Story-
Eintraege haben keine vergleichbare Orphan-Cleanup-Logik mehr noetig (keine lokale Datei, die
geloescht werden koennte).
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from github_project_sync.classify import SyncStateEntry
from github_project_sync.spec_parser import validate_spec_number

StateDict = dict[str, SyncStateEntry]

_NAMESPACE_KEYS = ("features", "stories")

_ISSUE_NUMBER_KEY_RE = re.compile(r"^[1-9]\d*$")


@dataclass(frozen=True)
class StoryStateEntry:
    """Ein Eintrag im "stories"-Namensraum - Schluessel ist die GitHub-Issue-Nummer selbst
    (als String), kein eigener Nummernkreis (siehe ADR 0036, Abschnitt 1). Bewusst ohne
    Hash-Felder, siehe Modul-Docstring."""

    issue_number: int
    item_id: str
    last_synced_at: str


StoryStateDict = dict[str, StoryStateEntry]


@dataclass(frozen=True)
class NestedState:
    features: StateDict
    stories: StoryStateDict


def validate_issue_number_key(value: str) -> str:
    """Verteidigung in der Tiefe gegen Pfad-Traversal/ungueltige Schluessel im "stories"-
    Namensraum - analog zu spec_parser.validate_spec_number(), aber ohne die feste
    Vier-Ziffern-Breite (Issue-Nummern wachsen unbegrenzt und haben keine fuehrende Null)."""
    if not _ISSUE_NUMBER_KEY_RE.match(value):
        raise ValueError(
            f"Ungueltiger Issue-Nummer-Schluessel: {value!r} (erwartet eine positive Ganzzahl "
            "ohne fuehrende Null)."
        )
    return value


def _parse_namespace(raw: Mapping[str, dict]) -> StateDict:
    state: StateDict = {}
    for number, entry in raw.items():
        validate_spec_number(number)
        state[number] = SyncStateEntry(
            issue_number=entry["issue_number"],
            item_id=entry["item_id"],
            pushed_state_hash=entry["pushed_state_hash"],
            last_synced_at=entry["last_synced_at"],
            runtime_status=entry.get("runtime_status"),
            pr_number=entry.get("pr_number"),
        )
    return state


def _parse_stories_namespace(raw: Mapping[str, dict[str, Any]]) -> StoryStateDict:
    state: StoryStateDict = {}
    for number, entry in raw.items():
        validate_issue_number_key(number)
        issue_number = entry["issue_number"]
        if int(number) != issue_number:
            # Verteidigung in der Tiefe (Copilot-Review-Finding auf PR #220): eine manuell
            # inkonsistent editierte Zustandsdatei (Schluessel "215" mit issue_number=999)
            # wuerde sonst dazu fuehren, dass _get_story_entry() (sync.py) das falsche
            # item_id fuer eine Operation auf Issue 215 zurueckliefert - --adopt-issue/
            # --only issue:NNN koennten so das falsche GitHub-Project-Item aktualisieren.
            raise ValueError(
                f"Inkonsistenter stories-Eintrag: Schluessel {number!r} weicht von "
                f"issue_number {issue_number!r} im Wert ab."
            )
        state[number] = StoryStateEntry(
            issue_number=issue_number,
            item_id=entry["item_id"],
            last_synced_at=entry["last_synced_at"],
        )
    return state


def load_state(path: Path) -> NestedState:
    if not path.exists():
        return NestedState(features={}, stories={})

    raw = json.loads(path.read_text(encoding="utf-8"))

    if not any(key in raw for key in _NAMESPACE_KEYS):
        # Ganz altes Format (vor ADR 0030): flaches {"NNNN": {...}}, kein Top-Level-Schluessel
        # "features"/"stories" vorhanden - transparent als reine Feature-Eintraege lesen.
        return NestedState(features=_parse_namespace(raw), stories={})

    # Ein evtl. noch vorhandenes altes "inbox"-Vorkommen (Format vor dieser Umsetzung) wird
    # hier bewusst NICHT gelesen - .get("stories", {}) ignoriert es stillschweigend statt
    # abzustuerzen (siehe Modul-Docstring).
    return NestedState(
        features=_parse_namespace(raw.get("features", {})),
        stories=_parse_stories_namespace(raw.get("stories", {})),
    )


def _serialize_namespace(state: Mapping[str, SyncStateEntry]) -> dict:
    for number in state:
        validate_spec_number(number)
    return {
        number: {
            "issue_number": entry.issue_number,
            "item_id": entry.item_id,
            "pushed_state_hash": entry.pushed_state_hash,
            "last_synced_at": entry.last_synced_at,
            "runtime_status": entry.runtime_status,
            "pr_number": entry.pr_number,
        }
        for number, entry in sorted(state.items())
    }


def _serialize_stories_namespace(state: Mapping[str, StoryStateEntry]) -> dict[str, Any]:
    for number in state:
        validate_issue_number_key(number)
    # Numerisch statt lexikalisch sortiert (Issue-Nummern haben, anders als die vierstelligen
    # Spec-Nummern, keine feste Breite - "10" wuerde lexikalisch vor "9" einsortiert werden).
    return {
        number: {
            "issue_number": entry.issue_number,
            "item_id": entry.item_id,
            "last_synced_at": entry.last_synced_at,
        }
        for number, entry in sorted(state.items(), key=lambda item: int(item[0]))
    }


def save_state(path: Path, state: NestedState) -> None:
    serializable = {
        "features": _serialize_namespace(state.features),
        "stories": _serialize_stories_namespace(state.stories),
    }
    # Kein sort_keys=True hier: die beiden _serialize_*_namespace()-Funktionen liefern bereits
    # bewusst sortierte dicts (Python-dicts erhalten Insertion-Order) - "stories" ist numerisch
    # sortiert (variable Ziffernbreite bei Issue-Nummern), json.dumps(sort_keys=True) wuerde das
    # mit einer erneuten lexikalischen Sortierung wieder zerstoeren ("10" vor "9").
    path.write_text(
        json.dumps(serializable, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def find_orphaned_numbers(
    state: Mapping[str, SyncStateEntry], *, existing_numbers: Iterable[str]
) -> list[str]:
    """Nummern mit State-Eintrag, aber ohne (mehr) zugehoerige Spec-Datei."""
    existing = set(existing_numbers)
    return sorted(number for number in state if number not in existing)
