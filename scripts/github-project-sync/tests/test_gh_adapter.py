from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field

import pytest

from github_project_sync.gh_adapter import (
    PRIORITY_FIELD_NAME,
    STATUS_FIELD_NAME,
    GhAdapterError,
    GhAuthScopeError,
    GhCliAdapter,
    IssueView,
    Project,
)


@dataclass
class _FakeRun:
    """Zeichnet jeden Aufruf auf (Argument-Konstruktion in Listenform pruefbar) und liefert
    vordefinierte Antworten in Aufrufreihenfolge zurueck - analog zum Mocking-Ansatz aus der
    Teststrategie in specs/features/0031-zweiwege-sync-specs-github-projekt.md."""

    responses: list[subprocess.CompletedProcess[str]] = field(default_factory=list)
    calls: list[list[str]] = field(default_factory=list)

    def __call__(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        return self.responses.pop(0)


def _ok(stdout: object = "") -> subprocess.CompletedProcess[str]:
    payload = stdout if isinstance(stdout, str) else json.dumps(stdout)
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=payload, stderr="")


def _fail(stderr: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr=stderr)


def test_check_auth_scope_passes_when_project_scope_present() -> None:
    run = _FakeRun([_ok("Token scopes: 'gist', 'project', 'repo'")])
    adapter = GhCliAdapter(owner="TheRealKoller", run=run)

    adapter.check_auth_scope()

    assert run.calls == [["gh", "auth", "status"]]


def test_check_auth_scope_raises_specific_error_when_scope_missing() -> None:
    run = _FakeRun([_ok("Token scopes: 'gist', 'repo'")])
    adapter = GhCliAdapter(owner="TheRealKoller", run=run)

    with pytest.raises(GhAuthScopeError, match="gh auth refresh -s project"):
        adapter.check_auth_scope()


def test_check_auth_scope_raises_on_gh_failure() -> None:
    run = _FakeRun([_fail("not logged in")])
    adapter = GhCliAdapter(owner="TheRealKoller", run=run)

    with pytest.raises(GhAdapterError):
        adapter.check_auth_scope()


def test_ensure_project_returns_existing_project_without_creating() -> None:
    run = _FakeRun(
        [_ok({"projects": [{"number": 3, "id": "PVT_1", "title": "PhotoSort Roadmap"}]})]
    )
    adapter = GhCliAdapter(owner="TheRealKoller", run=run)

    project = adapter.ensure_project()

    assert project == Project(number=3, id="PVT_1", title="PhotoSort Roadmap")
    assert len(run.calls) == 1
    assert run.calls[0][:3] == ["gh", "project", "list"]


def test_ensure_project_creates_when_missing_self_provisioning() -> None:
    run = _FakeRun(
        [
            _ok({"projects": []}),
            _ok({"number": 5, "id": "PVT_2", "title": "PhotoSort Roadmap"}),
        ]
    )
    adapter = GhCliAdapter(owner="TheRealKoller", run=run)

    project = adapter.ensure_project()

    assert project == Project(number=5, id="PVT_2", title="PhotoSort Roadmap")
    assert run.calls[1][:3] == ["gh", "project", "create"]


def test_ensure_fields_returns_existing_fields_without_creating() -> None:
    run = _FakeRun(
        [
            _ok(
                {
                    "fields": [
                        {
                            "id": "F_STATUS",
                            "name": STATUS_FIELD_NAME,
                            "options": [
                                {"id": "O1", "name": "Proposed"},
                                {"id": "O2", "name": "Accepted"},
                            ],
                        },
                        {
                            "id": "F_PRIO",
                            "name": PRIORITY_FIELD_NAME,
                            "options": [{"id": "O3", "name": "Hoch"}],
                        },
                    ]
                }
            )
        ]
    )
    adapter = GhCliAdapter(owner="TheRealKoller", run=run)
    project = Project(number=3, id="PVT_1", title="PhotoSort Roadmap")

    fields = adapter.ensure_fields(project)

    assert fields.status_field_id == "F_STATUS"
    assert fields.status_options == {"Proposed": "O1", "Accepted": "O2"}
    assert fields.priority_field_id == "F_PRIO"
    assert fields.priority_options == {"Hoch": "O3"}
    assert len(run.calls) == 1


def test_ensure_fields_creates_missing_fields_self_provisioning() -> None:
    run = _FakeRun(
        [
            _ok({"fields": []}),
            _ok(
                {
                    "id": "F_STATUS",
                    "options": [{"id": "O1", "name": "Proposed"}],
                }
            ),
            _ok(
                {
                    "id": "F_PRIO",
                    "options": [{"id": "O3", "name": "Hoch"}],
                }
            ),
        ]
    )
    adapter = GhCliAdapter(owner="TheRealKoller", run=run)
    project = Project(number=3, id="PVT_1", title="PhotoSort Roadmap")

    fields = adapter.ensure_fields(project)

    assert fields.status_field_id == "F_STATUS"
    assert fields.priority_field_id == "F_PRIO"
    assert run.calls[1][:3] == ["gh", "project", "field-create"]
    assert STATUS_FIELD_NAME in run.calls[1]
    assert run.calls[2][:3] == ["gh", "project", "field-create"]
    assert PRIORITY_FIELD_NAME in run.calls[2]


def test_ensure_fields_does_not_adopt_githubs_built_in_status_field() -> None:
    # Regressionstest fuer einen zweiten, beim manuellen Smoke-Test nach Merge von PR #115
    # entdeckten Bug: GitHub Projects (V2) legt bei jedem neuen Project automatisch ein
    # eingebautes Single-Select-Feld namens exakt "Status" an (Optionen Todo/In Progress/Done).
    # ensure_fields() darf dieses NICHT faelschlich als unser Lifecycle-Feld uebernehmen, nur
    # weil der Name uebereinstimmt - STATUS_FIELD_NAME ist deshalb bewusst nicht "Status".
    run = _FakeRun(
        [
            _ok(
                {
                    "fields": [
                        {"id": "F_TITLE", "name": "Title"},
                        {
                            "id": "F_BUILTIN_STATUS",
                            "name": "Status",
                            "options": [
                                {"id": "T1", "name": "Todo"},
                                {"id": "T2", "name": "In Progress"},
                                {"id": "T3", "name": "Done"},
                            ],
                        },
                    ]
                }
            ),
            _ok({"id": "F_SPEC_STATUS", "options": [{"id": "O1", "name": "Proposed"}]}),
            _ok({"id": "F_PRIO", "options": [{"id": "O3", "name": "Hoch"}]}),
        ]
    )
    adapter = GhCliAdapter(owner="TheRealKoller", run=run)
    project = Project(number=3, id="PVT_1", title="PhotoSort Roadmap")

    fields = adapter.ensure_fields(project)

    assert fields.status_field_id == "F_SPEC_STATUS"  # nicht das eingebaute F_BUILTIN_STATUS
    assert run.calls[1][:3] == ["gh", "project", "field-create"]
    assert STATUS_FIELD_NAME in run.calls[1]


def test_get_issue_parses_json_output() -> None:
    run = _FakeRun(
        [
            _ok(
                {
                    "number": 42,
                    "body": "<!-- photosort-spec: 0031 -->\n\n## Ziel\n\nfoo\n",
                    "state": "OPEN",
                    "author": {"login": "TheRealKoller"},
                    "url": "https://github.com/TheRealKoller/photosort/issues/42",
                }
            )
        ]
    )
    adapter = GhCliAdapter(owner="TheRealKoller", run=run)

    issue = adapter.get_issue(42)

    assert issue == IssueView(
        number=42,
        body="<!-- photosort-spec: 0031 -->\n\n## Ziel\n\nfoo\n",
        state="open",
        author_login="TheRealKoller",
        url="https://github.com/TheRealKoller/photosort/issues/42",
    )
    assert run.calls == [["gh", "issue", "view", "42", "--json", "number,body,state,author,url"]]


def test_get_issue_raises_on_failure() -> None:
    run = _FakeRun([_fail("issue not found")])
    adapter = GhCliAdapter(owner="TheRealKoller", run=run)

    with pytest.raises(GhAdapterError):
        adapter.get_issue(999)


def test_create_issue_writes_body_via_body_file_not_inline_argument() -> None:
    # Regressionstest fuer einen echten Bug (manueller Smoke-Test nach Merge von PR #115):
    # "gh issue create" kennt kein --json/--format-Flag (anders als z.B. "gh issue view") und
    # gibt bei Erfolg nur die Issue-URL als Klartext auf stdout aus, kein JSON.
    run = _FakeRun([_ok("https://github.com/TheRealKoller/photosort/issues/7\n")])
    adapter = GhCliAdapter(owner="TheRealKoller", run=run)

    number = adapter.create_issue("[0031] Titel", "<!-- photosort-spec: 0031 -->\n\n## Ziel\n")

    assert number == 7
    call = run.calls[0]
    assert call[:3] == ["gh", "issue", "create"]
    assert "--body-file" in call
    assert "--json" not in call  # "gh issue create" kennt dieses Flag nicht (unlike "issue view")
    assert "--format" not in call
    assert "<!-- photosort-spec: 0031 -->" not in call  # kein Inline-Body-Argument


def test_create_issue_parses_number_from_url_without_trailing_newline() -> None:
    run = _FakeRun([_ok("https://github.com/TheRealKoller/photosort/issues/123")])
    adapter = GhCliAdapter(owner="TheRealKoller", run=run)

    number = adapter.create_issue("Titel", "Body")

    assert number == 123


def test_create_issue_raises_clear_error_on_unparseable_output() -> None:
    run = _FakeRun([_ok("Irgendwas Unerwartetes, keine URL\n")])
    adapter = GhCliAdapter(owner="TheRealKoller", run=run)

    with pytest.raises(GhAdapterError, match="Issue-Nummer"):
        adapter.create_issue("Titel", "Body")


def test_create_issue_raises_clear_error_on_empty_output() -> None:
    run = _FakeRun([_ok("")])
    adapter = GhCliAdapter(owner="TheRealKoller", run=run)

    with pytest.raises(GhAdapterError, match="keine Ausgabe"):
        adapter.create_issue("Titel", "Body")


def test_edit_issue_body_uses_body_file() -> None:
    run = _FakeRun([_ok("")])
    adapter = GhCliAdapter(owner="TheRealKoller", run=run)

    adapter.edit_issue_body(42, "<!-- photosort-spec: 0031 -->\n\n## Ziel\n\nneu\n")

    call = run.calls[0]
    assert call[:3] == ["gh", "issue", "edit"]
    assert "42" in call
    assert "--body-file" in call


def test_set_issue_state_open_calls_reopen() -> None:
    run = _FakeRun([_ok("")])
    adapter = GhCliAdapter(owner="TheRealKoller", run=run)

    adapter.set_issue_state(42, open=True)

    assert run.calls == [["gh", "issue", "reopen", "42"]]


def test_set_issue_state_closed_calls_close() -> None:
    run = _FakeRun([_ok("")])
    adapter = GhCliAdapter(owner="TheRealKoller", run=run)

    adapter.set_issue_state(42, open=False)

    assert run.calls == [["gh", "issue", "close", "42"]]


def test_close_issue_with_comment() -> None:
    run = _FakeRun([_ok("")])
    adapter = GhCliAdapter(owner="TheRealKoller", run=run)

    adapter.close_issue_with_comment(42, "Spec-Datei wurde entfernt.")

    assert run.calls == [
        ["gh", "issue", "close", "42", "--comment", "Spec-Datei wurde entfernt."]
    ]


def test_add_item_to_project() -> None:
    run = _FakeRun([_ok({"id": "ITEM_1"})])
    adapter = GhCliAdapter(owner="TheRealKoller", run=run)
    project = Project(number=3, id="PVT_1", title="PhotoSort Roadmap")

    item_id = adapter.add_item_to_project(
        project, issue_url="https://github.com/TheRealKoller/photosort/issues/42"
    )

    assert item_id == "ITEM_1"
    call = run.calls[0]
    assert call[:3] == ["gh", "project", "item-add"]
    assert "https://github.com/TheRealKoller/photosort/issues/42" in call


def test_set_item_status() -> None:
    run = _FakeRun([_ok("")])
    adapter = GhCliAdapter(owner="TheRealKoller", run=run)
    project = Project(number=3, id="PVT_1", title="PhotoSort Roadmap")

    adapter.set_item_single_select(project, item_id="ITEM_1", field_id="F_STATUS", option_id="O2")

    call = run.calls[0]
    assert call[:3] == ["gh", "project", "item-edit"]
    assert "--single-select-option-id" in call
    assert "O2" in call


def test_clear_item_field_when_no_option() -> None:
    run = _FakeRun([_ok("")])
    adapter = GhCliAdapter(owner="TheRealKoller", run=run)
    project = Project(number=3, id="PVT_1", title="PhotoSort Roadmap")

    adapter.clear_item_field(project, item_id="ITEM_1", field_id="F_PRIO")

    call = run.calls[0]
    assert call[:3] == ["gh", "project", "item-edit"]
    assert "--clear" in call
