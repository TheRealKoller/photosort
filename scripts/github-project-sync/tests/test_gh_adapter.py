from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field

import pytest

from github_project_sync.gh_adapter import (
    PRIORITY_FIELD_NAME,
    STATUS_FIELD_NAME,
    STATUS_OPTIONS,
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


def test_ensure_fields_adopts_native_status_field_after_rollout_migration() -> None:
    # Seit Spec 0052 / ADR 0030 (Abschnitt 3) ist STATUS_FIELD_NAME wieder bewusst "Status" -
    # der frueher vermiedene Namenskonflikt mit GitHubs eingebautem Feld ist kein Problem mehr,
    # weil der einmalige, manuelle Rollout-Schritt das eingebaute Feld vorher loescht (kein
    # automatischer Dauerbetrieb-Codepfad, siehe ADR 0030, Abschnitt 3). ensure_fields() matcht
    # weiterhin rein ueber den Feldnamen und uebernimmt ein bereits existierendes Feld
    # "Status" unveraendert - das ist nach dem Rollout genau das gewuenschte Verhalten.
    # Fixture bildet den erwarteten Zustand NACH dem manuellen Rollout ab (ADR 0030, Abschnitt 3:
    # frisch angelegtes Feld mit allen vier Optionen aus STATUS_OPTIONS) - nicht nur zwei
    # Optionen, sonst bleibt ungetestet, ob ensure_fields() tatsaechlich alle vier durchreicht
    # (Copilot-Review-Finding auf PR #173, Nice-to-have).
    run = _FakeRun(
        [
            _ok(
                {
                    "fields": [
                        {"id": "F_TITLE", "name": "Title"},
                        {
                            "id": "F_STATUS",
                            "name": "Status",
                            "options": [
                                {"id": f"O_{name}", "name": name} for name in STATUS_OPTIONS
                            ],
                        },
                    ]
                }
            ),
            _ok({"id": "F_PRIO", "options": [{"id": "O3", "name": "Hoch"}]}),
        ]
    )
    adapter = GhCliAdapter(owner="TheRealKoller", run=run)
    project = Project(number=3, id="PVT_1", title="PhotoSort Roadmap")

    fields = adapter.ensure_fields(project)

    assert fields.status_field_id == "F_STATUS"
    assert set(fields.status_options) == set(STATUS_OPTIONS)
    assert fields.status_options == {name: f"O_{name}" for name in STATUS_OPTIONS}
    # Kein zweiter field-create-Aufruf fuer Status noetig, das Feld existierte bereits:
    assert run.calls[1][:3] == ["gh", "project", "field-create"]
    assert PRIORITY_FIELD_NAME in run.calls[1]


def test_status_options_include_story_between_unrefined_and_proposed() -> None:
    # Seit Spec 0059 / ADR 0036, Abschnitt 2: neuer Zwischenwert "Story".
    assert STATUS_OPTIONS == ["Unrefined", "Story", "Proposed", "Accepted", "Implemented"]
    assert "Superseded" not in STATUS_OPTIONS


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
                    "labels": [{"name": "idee"}, {"name": "bug"}],
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
        labels=frozenset({"idee", "bug"}),
    )
    assert run.calls == [
        ["gh", "issue", "view", "42", "--json", "number,body,state,author,url,labels"]
    ]


def test_get_issue_defaults_to_empty_labels_when_field_missing() -> None:
    run = _FakeRun(
        [
            _ok(
                {
                    "number": 42,
                    "body": "foo",
                    "state": "OPEN",
                    "author": {"login": "TheRealKoller"},
                    "url": "https://github.com/TheRealKoller/photosort/issues/42",
                }
            )
        ]
    )
    adapter = GhCliAdapter(owner="TheRealKoller", run=run)

    issue = adapter.get_issue(42)

    assert issue.labels == frozenset()


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


# -- ensure_label() / set_issue_labels() (neu in Spec 0052 / ADR 0030, Abschnitt 6) ---------


def test_ensure_label_does_nothing_when_label_already_exists() -> None:
    run = _FakeRun([_ok([{"name": "bug"}, {"name": "idee"}])])
    adapter = GhCliAdapter(owner="TheRealKoller", run=run)

    adapter.ensure_label("bug", description="Something isn't working", color="d73a4a")

    assert len(run.calls) == 1
    assert run.calls[0][:3] == ["gh", "label", "list"]


def test_ensure_label_creates_missing_label_self_provisioning() -> None:
    run = _FakeRun([_ok([{"name": "bug"}]), _ok("")])
    adapter = GhCliAdapter(owner="TheRealKoller", run=run)

    adapter.ensure_label("superseded", description="Spec wurde abgeloest.", color="cfd3d7")

    assert run.calls[1][:3] == ["gh", "label", "create"]
    assert "superseded" in run.calls[1]
    assert "--description" in run.calls[1]
    assert "Spec wurde abgeloest." in run.calls[1]
    assert "--color" in run.calls[1]
    assert "cfd3d7" in run.calls[1]


def test_ensure_label_raises_on_list_failure() -> None:
    run = _FakeRun([_fail("not logged in")])
    adapter = GhCliAdapter(owner="TheRealKoller", run=run)

    with pytest.raises(GhAdapterError):
        adapter.ensure_label("idee", description="Idee", color="0e8a16")


def test_set_issue_labels_adds_and_removes() -> None:
    run = _FakeRun([_ok("")])
    adapter = GhCliAdapter(owner="TheRealKoller", run=run)

    adapter.set_issue_labels(42, add=frozenset({"idee"}), remove=frozenset({"bug"}))

    call = run.calls[0]
    assert call[:3] == ["gh", "issue", "edit"]
    assert "42" in call
    assert "--add-label" in call
    assert "idee" in call
    assert "--remove-label" in call
    assert "bug" in call


def test_set_issue_labels_no_op_when_nothing_to_change() -> None:
    run = _FakeRun([])
    adapter = GhCliAdapter(owner="TheRealKoller", run=run)

    adapter.set_issue_labels(42, add=frozenset(), remove=frozenset())

    assert run.calls == []


# -- get_item_field_value() (neu in Spec 0059 / ADR 0036, Abschnitt 5: Grundlage --show-status) --


def test_get_item_field_value_returns_current_option_display_name() -> None:
    run = _FakeRun(
        [
            _ok(
                {
                    "items": [
                        {"id": "ITEM_1", "Status": "Story", "title": "issue-215"},
                        {"id": "ITEM_2", "Status": "Proposed", "title": "issue-42"},
                    ]
                }
            )
        ]
    )
    adapter = GhCliAdapter(owner="TheRealKoller", run=run)
    project = Project(number=3, id="PVT_1", title="PhotoSort Roadmap")

    value = adapter.get_item_field_value(project, item_id="ITEM_1", field_name=STATUS_FIELD_NAME)

    assert value == "Story"
    assert run.calls[0][:3] == ["gh", "project", "item-list"]


def test_get_item_field_value_returns_none_when_field_unset() -> None:
    run = _FakeRun([_ok({"items": [{"id": "ITEM_1", "title": "issue-215"}]})])
    adapter = GhCliAdapter(owner="TheRealKoller", run=run)
    project = Project(number=3, id="PVT_1", title="PhotoSort Roadmap")

    value = adapter.get_item_field_value(project, item_id="ITEM_1", field_name=STATUS_FIELD_NAME)

    assert value is None


def test_get_item_field_value_raises_when_item_not_found() -> None:
    run = _FakeRun([_ok({"items": []})])
    adapter = GhCliAdapter(owner="TheRealKoller", run=run)
    project = Project(number=3, id="PVT_1", title="PhotoSort Roadmap")

    with pytest.raises(GhAdapterError, match="ITEM_1"):
        adapter.get_item_field_value(project, item_id="ITEM_1", field_name=STATUS_FIELD_NAME)
