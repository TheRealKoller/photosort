"""Duenner Adapter-Layer um `gh issue`/`gh project`-Subcommands (subprocess, Listenform).

Siehe ADR decisions/0017-github-projects-v2-spec-sync.md, Abschnitt 3/5: native gh-Subcommands
statt roher GraphQL-Aufrufe, kein `shell=True`, keine String-Interpolation. Argument-Konstruktion
wird gegen einen injizierten `run`-Callable getestet (gemocktes subprocess.run, siehe
tests/test_gh_adapter.py) - echtes `gh` wird laut Teststrategie der Spec nur manuell vor dem
Merge verifiziert, nicht in CI.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

RunFunc = Callable[[list[str]], "subprocess.CompletedProcess[str]"]


class GhAdapterError(RuntimeError):
    """Ein `gh`-Aufruf ist fehlgeschlagen oder lieferte eine unerwartete Antwort."""


class GhAuthScopeError(GhAdapterError):
    """Der lokalen `gh`-Session fehlt der fuer GitHub Projects (V2) noetige `project`-Scope."""


@dataclass(frozen=True)
class Project:
    number: int
    id: str
    title: str


@dataclass(frozen=True)
class ProjectFields:
    status_field_id: str
    status_options: dict[str, str]
    priority_field_id: str
    priority_options: dict[str, str]


@dataclass(frozen=True)
class IssueView:
    number: int
    body: str
    state: str  # "open" | "closed"
    # Aktuell von sync.py bewusst nicht ausgewertet - vorgehalten fuer eine etwaige kuenftige
    # Erweiterung um einen Marker-/Titel-Lookup-Pfad (dann waere der in ADR
    # decisions/0017-github-projects-v2-spec-sync.md, Bedrohung 1, beschriebene
    # issue.author.login-Fallback noetig). Solange die Zuordnung ausschliesslich ueber den
    # gespeicherten issue_number laeuft (siehe Kommentar in sync.py::_sync_one), gibt es dafuer
    # keinen Verwendungszweck. Siehe auch Review-Finding zu dieser Abweichung.
    author_login: str
    url: str


class GhAdapter(Protocol):
    """Alles, was die Sync-Logik (sync.py) an `gh`-Operationen braucht - implementiert von
    GhCliAdapter (echtes `gh`) bzw. FakeGhAdapter (In-Memory, siehe tests/fakes.py)."""

    def check_auth_scope(self) -> None: ...

    def ensure_project(self) -> Project: ...

    def ensure_fields(self, project: Project) -> ProjectFields: ...

    def get_issue(self, issue_number: int) -> IssueView: ...

    def create_issue(self, title: str, body: str) -> int: ...

    def edit_issue_body(self, issue_number: int, body: str) -> None: ...

    def set_issue_state(self, issue_number: int, *, open: bool) -> None: ...

    def close_issue_with_comment(self, issue_number: int, comment: str) -> None: ...

    def add_item_to_project(self, project: Project, *, issue_url: str) -> str: ...

    def set_item_single_select(
        self, project: Project, *, item_id: str, field_id: str, option_id: str
    ) -> None: ...

    def clear_item_field(self, project: Project, *, item_id: str, field_id: str) -> None: ...


def _default_run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, check=False)  # noqa: S603


# Bewusst NICHT "Status": GitHub Projects (V2) legt bei JEDEM neuen Project automatisch ein
# eingebautes Single-Select-Feld exakt mit diesem Namen an (Optionen "Todo"/"In Progress"/"Done",
# fuer die klassische Kanban-Ansicht) - verifiziert per "gh project field-list" gegen das echte,
# bereits per Smoke-Test selbstprovisionierte Project (Owner TheRealKoller, "PhotoSort Roadmap").
# ensure_fields() matcht rein ueber den Feldnamen (siehe unten); mit "Status" als Name haette es
# faelschlich dieses eingebaute Feld als "unseres" uebernommen - dessen Optionen enthalten aber
# keinen unserer vier Lifecycle-Werte, wodurch _apply_fields() in sync.py bei jedem Lauf mit einer
# SyncError abgebrochen waere. Zusaetzlicher, beim manuellen Smoke-Test nach Merge von PR #115
# entdeckter Bug (ueber den urspruenglich gemeldeten "gh issue create --json"-Fehler hinaus).
STATUS_FIELD_NAME = "Spec Status"
STATUS_OPTIONS = ["Proposed", "Accepted", "Implemented", "Superseded"]
PRIORITY_FIELD_NAME = "Priorität"
PRIORITY_OPTIONS = ["Hoch", "Mittel", "Niedrig"]
DEFAULT_PROJECT_TITLE = "PhotoSort Roadmap"

# "gh issue create" hat - anders als z.B. "gh issue view" - kein --json/--format-Flag (verifiziert
# gegen "gh issue create --help", gh 2.97.0) und gibt bei Erfolg nur die Issue-URL als Klartext auf
# stdout aus (z.B. "https://github.com/TheRealKoller/photosort/issues/123"). Bug gefunden im
# manuellen Smoke-Test nach Merge von PR #115 ("unknown flag: --json").
_ISSUE_URL_NUMBER_RE = re.compile(r"/issues/(\d+)/?\s*$")


def _parse_issue_number_from_create_output(stdout: str) -> int:
    lines = [line.strip() for line in stdout.strip().splitlines() if line.strip()]
    if not lines:
        raise GhAdapterError(
            "'gh issue create' lieferte keine Ausgabe - erwartet wurde die Issue-URL auf stdout."
        )
    last_line = lines[-1]
    match = _ISSUE_URL_NUMBER_RE.search(last_line)
    if match is None:
        raise GhAdapterError(
            "Konnte keine Issue-Nummer aus der Ausgabe von 'gh issue create' extrahieren "
            f"(erwartet eine Issue-URL, z.B. '.../issues/123'): {last_line!r}"
        )
    return int(match.group(1))


class GhCliAdapter:
    """Echte `gh`-CLI-Implementierung von GhAdapter (kein `shell=True`, Listenform-Argumente)."""

    def __init__(
        self,
        *,
        owner: str,
        project_title: str = DEFAULT_PROJECT_TITLE,
        run: RunFunc = _default_run,
    ) -> None:
        self._owner = owner
        self._project_title = project_title
        self._run = run

    def _run_text(self, args: list[str]) -> str:
        result = self._run(args)
        if result.returncode != 0:
            raise GhAdapterError(
                f"gh-Aufruf fehlgeschlagen ({' '.join(args)}): {result.stderr.strip()}"
            )
        return result.stdout

    def _run_json(self, args: list[str]) -> Any:
        stdout = self._run_text(args)
        try:
            return json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise GhAdapterError(
                f"gh-Ausgabe fuer '{' '.join(args)}' war kein gueltiges JSON: {exc}"
            ) from exc

    def check_auth_scope(self) -> None:
        result = self._run(["gh", "auth", "status"])
        output = (result.stdout or "") + (result.stderr or "")
        if result.returncode != 0:
            raise GhAdapterError(f"'gh auth status' fehlgeschlagen: {output.strip()}")
        if "project" not in output:
            raise GhAuthScopeError(
                "Der lokalen gh-Session fehlt der Scope 'project' fuer GitHub Projects (V2). "
                "Bitte einmalig 'gh auth refresh -s project' ausfuehren (siehe ADR 0017, "
                "Abschnitt 2)."
            )

    def ensure_project(self) -> Project:
        data = self._run_json(
            ["gh", "project", "list", "--owner", self._owner, "--format", "json"]
        )
        for project in data.get("projects", []):
            if project.get("title") == self._project_title:
                return Project(
                    number=project["number"], id=project["id"], title=project["title"]
                )

        created = self._run_json(
            [
                "gh",
                "project",
                "create",
                "--owner",
                self._owner,
                "--title",
                self._project_title,
                "--format",
                "json",
            ]
        )
        return Project(number=created["number"], id=created["id"], title=created["title"])

    def ensure_fields(self, project: Project) -> ProjectFields:
        data = self._run_json(
            [
                "gh",
                "project",
                "field-list",
                str(project.number),
                "--owner",
                self._owner,
                "--format",
                "json",
            ]
        )
        existing = {f["name"]: f for f in data.get("fields", [])}

        status_field = existing.get(STATUS_FIELD_NAME) or self._create_single_select_field(
            project, STATUS_FIELD_NAME, STATUS_OPTIONS
        )
        priority_field = existing.get(PRIORITY_FIELD_NAME) or self._create_single_select_field(
            project, PRIORITY_FIELD_NAME, PRIORITY_OPTIONS
        )

        return ProjectFields(
            status_field_id=status_field["id"],
            status_options={o["name"]: o["id"] for o in status_field.get("options", [])},
            priority_field_id=priority_field["id"],
            priority_options={o["name"]: o["id"] for o in priority_field.get("options", [])},
        )

    def _create_single_select_field(
        self, project: Project, name: str, options: list[str]
    ) -> dict[str, Any]:
        result: dict[str, Any] = self._run_json(
            [
                "gh",
                "project",
                "field-create",
                str(project.number),
                "--owner",
                self._owner,
                "--name",
                name,
                "--data-type",
                "SINGLE_SELECT",
                "--single-select-options",
                ",".join(options),
                "--format",
                "json",
            ]
        )
        return result

    def get_issue(self, issue_number: int) -> IssueView:
        data = self._run_json(
            ["gh", "issue", "view", str(issue_number), "--json", "number,body,state,author,url"]
        )
        return IssueView(
            number=data["number"],
            body=data.get("body") or "",
            state=str(data["state"]).lower(),
            author_login=data.get("author", {}).get("login", ""),
            url=data.get("url", ""),
        )

    def _with_body_file(self, body: str, build_args: Callable[[str], list[str]]) -> str:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".md", delete=False, encoding="utf-8"
        ) as handle:
            handle.write(body)
            body_path = handle.name
        try:
            return self._run_text(build_args(body_path))
        finally:
            Path(body_path).unlink(missing_ok=True)

    def create_issue(self, title: str, body: str) -> int:
        stdout = self._with_body_file(
            body,
            lambda body_path: [
                "gh",
                "issue",
                "create",
                "--title",
                title,
                "--body-file",
                body_path,
            ],
        )
        return _parse_issue_number_from_create_output(stdout)

    def edit_issue_body(self, issue_number: int, body: str) -> None:
        self._with_body_file(
            body,
            lambda body_path: [
                "gh",
                "issue",
                "edit",
                str(issue_number),
                "--body-file",
                body_path,
            ],
        )

    def set_issue_state(self, issue_number: int, *, open: bool) -> None:
        subcommand = "reopen" if open else "close"
        self._run_text(["gh", "issue", subcommand, str(issue_number)])

    def close_issue_with_comment(self, issue_number: int, comment: str) -> None:
        self._run_text(["gh", "issue", "close", str(issue_number), "--comment", comment])

    def add_item_to_project(self, project: Project, *, issue_url: str) -> str:
        data = self._run_json(
            [
                "gh",
                "project",
                "item-add",
                str(project.number),
                "--owner",
                self._owner,
                "--url",
                issue_url,
                "--format",
                "json",
            ]
        )
        return str(data["id"])

    def set_item_single_select(
        self, project: Project, *, item_id: str, field_id: str, option_id: str
    ) -> None:
        self._run_text(
            [
                "gh",
                "project",
                "item-edit",
                "--id",
                item_id,
                "--project-id",
                project.id,
                "--field-id",
                field_id,
                "--single-select-option-id",
                option_id,
            ]
        )

    def clear_item_field(self, project: Project, *, item_id: str, field_id: str) -> None:
        self._run_text(
            [
                "gh",
                "project",
                "item-edit",
                "--id",
                item_id,
                "--project-id",
                project.id,
                "--field-id",
                field_id,
                "--clear",
            ]
        )
