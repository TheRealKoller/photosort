"""Kommandozeilen-Einstiegspunkt fuer den Skill .claude/skills/github-project-sync/SKILL.md.

Gibt strukturiertes JSON auf stdout aus, damit der aufrufende Skill (Claude) das Ergebnis
zuverlaessig auswerten kann (Konflikte/pulled-Faelle an Daniel bzw. requirements-engineer
weiterreichen). Siehe specs/features/0031-zweiwege-sync-specs-github-projekt.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from github_project_sync.gh_adapter import (
    DEFAULT_PROJECT_TITLE,
    GhAdapter,
    GhAdapterError,
    GhCliAdapter,
)
from github_project_sync.spec_parser import validate_spec_number
from github_project_sync.sync import Resolution, SyncError, SyncRunResult, run_sync

GhFactory = Callable[[str], GhAdapter]

_RESOLUTION_VALUES = {"keep_spec", "keep_issue"}


def _parse_resolutions(raw: list[str]) -> dict[str, Resolution]:
    # Bekannte, bewusst nicht behobene Einschraenkung (Review-Finding auf Spec 0052/PR): der
    # Resolution-Key ist eine nackte Nummer, nicht nach Namespace praefixiert (kein
    # "inbox:NNNN=..." analog zu --only). Bei einer echten Nummernkollision (z.B. inbox/0004 +
    # features/0004, real vorkommend) mit gleichzeitigem Konflikt in BEIDEN Namespaces wuerde
    # "--resolve 0004=keep_spec" unbeabsichtigt auf beide Eintraege wirken - keine isolierte
    # Aufloesung moeglich. In der Praxis unkritisch, weil Konfliktaufloesung laut
    # .claude/skills/github-project-sync/SKILL.md (Schritt 4) immer in Kombination mit einem auf
    # eine einzelne Entitaet gescopten "--only NNNN"/"--only inbox:NNNN"-Aufruf erfolgt - dort
    # ist "resolutions" ohnehin nur fuer die eine verarbeitete Nummer relevant. Der Randfall
    # (Voll-Lauf ohne --only, Kollision, Konflikt auf beiden Seiten gleichzeitig) ist nicht durch
    # ein Akzeptanzkriterium gefordert und wird hier nicht extra abgefangen.
    resolutions: dict[str, Resolution] = {}
    for item in raw:
        if "=" not in item:
            raise SyncError(
                f"Ungueltiges --resolve-Argument (erwartet NNNN=keep_spec|keep_issue): {item!r}"
            )
        number, _, value = item.partition("=")
        validate_spec_number(number)
        if value not in _RESOLUTION_VALUES:
            raise SyncError(
                f"Ungueltiger Aufloesungswert fuer Spec {number}: {value!r} "
                f"(erwartet einen von {sorted(_RESOLUTION_VALUES)})."
            )
        resolutions[number] = value  # type: ignore[assignment]
    return resolutions


def _discover_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "specs").is_dir() and (candidate / ".git").exists():
            return candidate
    raise SyncError(
        f"Kein Repo-Root (specs/ + .git) ausgehend von {start} gefunden. "
        "Mit --repo-root explizit angeben."
    )


def _result_to_dict(result: SyncRunResult) -> dict[str, object]:
    return {
        "specs": [
            {
                "number": r.number,
                "title": r.title,
                "issue_number": r.issue_number,
                "classification": r.classification,
                "aborted_reason": r.aborted_reason,
                "priority_warning": r.priority_warning,
                "conflict": (
                    {
                        "local_content_zone": r.conflict.local_content_zone,
                        "remote_content_zone": r.conflict.remote_content_zone,
                    }
                    if r.conflict is not None
                    else None
                ),
                "pulled_content_zone": r.pulled_content_zone,
            }
            for r in result.specs
        ],
        "orphaned": [
            {"number": o.number, "issue_number": o.issue_number} for o in result.orphaned
        ],
        "inbox": [
            {
                "number": r.number,
                "title": r.title,
                "issue_number": r.issue_number,
                "classification": r.classification,
                "aborted_reason": r.aborted_reason,
                "conflict": (
                    {
                        "local_content_zone": r.conflict.local_content_zone,
                        "remote_content_zone": r.conflict.remote_content_zone,
                    }
                    if r.conflict is not None
                    else None
                ),
                "pulled_content_zone": r.pulled_content_zone,
            }
            for r in result.inbox
        ],
        "orphaned_inbox": [
            {"number": o.number, "issue_number": o.issue_number} for o in result.orphaned_inbox
        ],
        "supersede": (
            {
                "inbox_number": result.supersede.inbox_number,
                "inbox_issue_number": result.supersede.inbox_issue_number,
                "new_issue_number": result.supersede.new_issue_number,
            }
            if result.supersede is not None
            else None
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="github-project-sync",
        description=(
            "Zwei-Wege-Sync zwischen specs/features/*.md und einem GitHub Project (V2). "
            "Siehe specs/features/0031-zweiwege-sync-specs-github-projekt.md."
        ),
    )
    parser.add_argument(
        "--only",
        metavar="NNNN|inbox:NNNN",
        default=None,
        help=(
            "Nur diese eine Spec-Nummer syncen (bare NNNN, rueckwaertskompatibel Feature-Scope) "
            "oder nur diesen einen Inbox-Eintrag (inbox:NNNN)."
        ),
    )
    parser.add_argument(
        "--supersede-inbox",
        metavar="MMMM",
        default=None,
        help=(
            "Schliesst gezielt das Inbox-Issue MMMM mit einem auf die per --only NNNN "
            "gesyncte Spec verlinkenden Kommentar. Erfordert --only NNNN (Feature-Scope)."
        ),
    )
    parser.add_argument(
        "--owner",
        default="TheRealKoller",
        help="GitHub-Owner des Projects (Default: TheRealKoller).",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repo-Root explizit angeben statt automatisch ausgehend vom cwd zu suchen.",
    )
    parser.add_argument(
        "--resolve",
        action="append",
        default=[],
        metavar="NNNN=keep_spec|keep_issue",
        help=(
            "Konflikt fuer eine Spec-/Inbox-Nummer explizit aufloesen. Mehrfach angebbar. "
            "Nummer ist NICHT nach Namespace praefixiert - bei einer Nummernkollision "
            "zwischen specs/features/ und specs/inbox/ mit Konflikt auf beiden Seiten im "
            "selben Voll-Lauf wirkt dieselbe Nummer auf beide (siehe _parse_resolutions())."
        ),
    )
    return parser


def _default_gh_factory(owner: str) -> GhAdapter:
    return GhCliAdapter(owner=owner, project_title=DEFAULT_PROJECT_TITLE)


def main(argv: Sequence[str] | None = None, *, gh_factory: GhFactory = _default_gh_factory) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        resolutions = _parse_resolutions(args.resolve)
        repo_root = args.repo_root or _discover_repo_root(Path.cwd())
        gh = gh_factory(args.owner)
        result = run_sync(
            repo_root=repo_root,
            gh=gh,
            only=args.only,
            supersede_inbox=args.supersede_inbox,
            resolutions=resolutions,
        )
    except SyncError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1
    except GhAdapterError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1

    print(json.dumps(_result_to_dict(result), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
