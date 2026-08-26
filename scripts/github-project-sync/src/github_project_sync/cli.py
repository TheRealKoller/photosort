"""Kommandozeilen-Einstiegspunkt fuer den Skill .claude/skills/github-project-sync/SKILL.md.

Gibt strukturiertes JSON auf stdout aus, damit der aufrufende Skill (Claude) das Ergebnis
zuverlaessig auswerten kann (Konflikte an Daniel bzw. requirements-engineer weiterreichen).
Siehe specs/features/0031-zweiwege-sync-specs-github-projekt.md und
specs/features/0059-story-lebenszyklus-github-issues.md.
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
from github_project_sync.sync import (
    Resolution,
    SyncError,
    SyncRunResult,
    create_story_issue,
    run_sync,
    show_story_status,
    sync_story,
)

GhFactory = Callable[[str], GhAdapter]

_RESOLUTION_VALUES = {"keep_spec", "keep_issue"}
_ISSUE_ONLY_PREFIX = "issue:"


def _parse_resolutions(raw: list[str]) -> dict[str, Resolution]:
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


def _parse_issue_only(value: str) -> int:
    raw_number = value[len(_ISSUE_ONLY_PREFIX) :]
    if not raw_number.isdigit() or raw_number.startswith("0"):
        raise SyncError(
            f"Ungueltiger Issue-Scope {value!r} (erwartet 'issue:NNN' mit einer positiven "
            "Ganzzahl ohne fuehrende Null)."
        )
    return int(raw_number)


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
        "orphaned": [{"number": o.number, "issue_number": o.issue_number} for o in result.orphaned],
        "adopted": (
            {
                "spec_number": result.adopted.spec_number,
                "issue_number": result.adopted.issue_number,
            }
            if result.adopted is not None
            else None
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="github-project-sync",
        description=(
            "Zwei-Wege-Sync zwischen specs/features/*.md und einem GitHub Project (V2), plus "
            "dateiloser Story-Stufe (issue:NNN). Siehe "
            "specs/features/0031-zweiwege-sync-specs-github-projekt.md und "
            "specs/features/0059-story-lebenszyklus-github-issues.md."
        ),
    )
    parser.add_argument(
        "--only",
        metavar="NNNN|issue:NNN",
        default=None,
        help=(
            "Nur diese eine Spec-Nummer syncen (bare NNNN, Feature-Scope) oder nur dieses eine "
            "Story-Issue (issue:NNN, dateiloser Scope ohne Pull/Konflikt-Handling)."
        ),
    )
    parser.add_argument(
        "--adopt-issue",
        type=int,
        default=None,
        metavar="MMM",
        help=(
            "Story -> Feature-Spec-Uebergang: das bestehende Story-Issue MMM wird adoptiert "
            "(kein neues Issue). Erfordert --only NNNN (Feature-Scope)."
        ),
    )
    parser.add_argument(
        "--create-issue",
        action="store_true",
        help=(
            "Legt ein neues, dateiloses Story-Issue an (Status Unrefined). "
            "Braucht --type/--title/--body-file."
        ),
    )
    parser.add_argument(
        "--type",
        choices=["idee", "bug"],
        default=None,
        help="Typ des neuen Story-Issues (nur mit --create-issue).",
    )
    parser.add_argument(
        "--title",
        default=None,
        help="Titel des neuen Story-Issues (nur mit --create-issue).",
    )
    parser.add_argument(
        "--body-file",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Body aus Datei lesen - mit --create-issue fuer den neuen Issue-Body, mit "
            "--only issue:NNN fuer eine Aktualisierung des bestehenden Issue-Bodys."
        ),
    )
    parser.add_argument(
        "--status",
        default=None,
        help="Status-Feld setzen (nur mit --only issue:NNN, z.B. 'Story').",
    )
    parser.add_argument(
        "--show-status",
        action="store_true",
        help="Nur den aktuellen Status lesen, nichts veraendern (erfordert --only issue:NNN).",
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
        help="Konflikt fuer eine Spec-Nummer explizit aufloesen. Mehrfach angebbar.",
    )
    return parser


def _default_gh_factory(owner: str) -> GhAdapter:
    return GhCliAdapter(owner=owner, project_title=DEFAULT_PROJECT_TITLE)


def _read_body_file(path: Path | None) -> str | None:
    if path is None:
        return None
    return path.read_text(encoding="utf-8")


def main(argv: Sequence[str] | None = None, *, gh_factory: GhFactory = _default_gh_factory) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        repo_root = args.repo_root or _discover_repo_root(Path.cwd())
        gh = gh_factory(args.owner)

        if args.create_issue:
            if not args.type or not args.title or not args.body_file:
                raise SyncError("--create-issue erfordert --type, --title und --body-file.")
            body = _read_body_file(args.body_file)
            assert body is not None
            issue_number = create_story_issue(
                repo_root=repo_root, gh=gh, typ=args.type, title=args.title, body=body
            )
            print(json.dumps({"issue_number": issue_number}, ensure_ascii=False))
            return 0

        if args.only is not None and args.only.startswith(_ISSUE_ONLY_PREFIX):
            issue_number = _parse_issue_only(args.only)

            if args.show_status:
                status = show_story_status(repo_root=repo_root, gh=gh, issue_number=issue_number)
                print(json.dumps({"status": status}, ensure_ascii=False))
                return 0

            body = _read_body_file(args.body_file)
            story_result = sync_story(
                repo_root=repo_root,
                gh=gh,
                issue_number=issue_number,
                status=args.status,
                body=body,
            )
            print(json.dumps(story_result, ensure_ascii=False))
            return 0

        if args.show_status:
            raise SyncError("--show-status erfordert --only issue:NNN.")

        resolutions = _parse_resolutions(args.resolve)
        result = run_sync(
            repo_root=repo_root,
            gh=gh,
            only=args.only,
            adopt_issue=args.adopt_issue,
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
