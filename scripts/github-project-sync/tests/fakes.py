"""In-Memory-Testdouble fuer GhAdapter, analog zu FakeOpenCloudClient (backend/tests/*.py).

Lebt bewusst unter tests/ (nicht im Package selbst) - ein Testdouble ist kein Produktionscode,
siehe Teststrategie in specs/features/0031-zweiwege-sync-specs-github-projekt.md ("FakeGhAdapter
analog zu FakeOpenCloudClient"). Wird von mehreren Testmodulen (Sync-Integrationstests) geteilt,
daher als eigenes Modul statt dupliziert in jeder Testdatei.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from github_project_sync.gh_adapter import (
    DEFAULT_PROJECT_TITLE,
    PRIORITY_OPTIONS,
    STATUS_OPTIONS,
    GhAuthScopeError,
    IssueView,
    Project,
    ProjectFields,
)


@dataclass
class _FakeIssue:
    title: str
    body: str
    state: str
    author_login: str
    url: str
    comments: list[str] = field(default_factory=list)


class FakeGhAdapter:
    def __init__(self, *, owner: str = "TheRealKoller", auth_ok: bool = True) -> None:
        self.owner = owner
        self.auth_ok = auth_ok
        self.project: Project | None = None
        self.fields: ProjectFields | None = None
        self._issues: dict[int, _FakeIssue] = {}
        self._next_issue_number = 1
        self.items: dict[str, dict[str, str | None]] = {}
        self._next_item_id = 1
        self.ensure_project_calls = 0
        self.ensure_fields_calls = 0

    # -- Setup-Helfer fuer Tests -------------------------------------------------
    def seed_issue(
        self, number: int, *, body: str, state: str = "open", author_login: str | None = None
    ) -> None:
        self._issues[number] = _FakeIssue(
            title=f"issue-{number}",
            body=body,
            state=state,
            author_login=author_login or self.owner,
            url=f"https://github.com/{self.owner}/photosort/issues/{number}",
        )
        self._next_issue_number = max(self._next_issue_number, number + 1)

    def issue(self, number: int) -> _FakeIssue:
        return self._issues[number]

    # -- GhAdapter-Protokoll -------------------------------------------------
    def check_auth_scope(self) -> None:
        if not self.auth_ok:
            raise GhAuthScopeError("fake: gh-Session hat keinen 'project'-Scope.")

    def ensure_project(self) -> Project:
        self.ensure_project_calls += 1
        if self.project is None:
            self.project = Project(number=1, id="PVT_FAKE", title=DEFAULT_PROJECT_TITLE)
        return self.project

    def ensure_fields(self, project: Project) -> ProjectFields:
        self.ensure_fields_calls += 1
        if self.fields is None:
            self.fields = ProjectFields(
                status_field_id="F_STATUS",
                status_options={name: f"S_{name}" for name in STATUS_OPTIONS},
                priority_field_id="F_PRIO",
                priority_options={name: f"P_{name}" for name in PRIORITY_OPTIONS},
            )
        return self.fields

    def get_issue(self, issue_number: int) -> IssueView:
        issue = self._issues[issue_number]
        return IssueView(
            number=issue_number,
            body=issue.body,
            state=issue.state,
            author_login=issue.author_login,
            url=issue.url,
        )

    def create_issue(self, title: str, body: str) -> int:
        number = self._next_issue_number
        self._next_issue_number += 1
        self._issues[number] = _FakeIssue(
            title=title,
            body=body,
            state="open",
            author_login=self.owner,
            url=f"https://github.com/{self.owner}/photosort/issues/{number}",
        )
        return number

    def edit_issue_body(self, issue_number: int, body: str) -> None:
        self._issues[issue_number].body = body

    def set_issue_state(self, issue_number: int, *, open: bool) -> None:
        self._issues[issue_number].state = "open" if open else "closed"

    def close_issue_with_comment(self, issue_number: int, comment: str) -> None:
        self._issues[issue_number].state = "closed"
        self._issues[issue_number].comments.append(comment)

    def add_item_to_project(self, project: Project, *, issue_url: str) -> str:
        item_id = f"ITEM_{self._next_item_id}"
        self._next_item_id += 1
        self.items[item_id] = {"issue_url": issue_url}
        return item_id

    def set_item_single_select(
        self, project: Project, *, item_id: str, field_id: str, option_id: str
    ) -> None:
        # setdefault statt einer harten KeyError, falls der Test einen State-Eintrag mit
        # item_id vorgibt, ohne den Fake ueber ein vorheriges add_item_to_project() zu fuehren
        # (analog: auf echtem GitHub existiert das Item bereits, unser In-Memory-Fake muss das
        # nur nachbilden koennen).
        self.items.setdefault(item_id, {})[field_id] = option_id

    def clear_item_field(self, project: Project, *, item_id: str, field_id: str) -> None:
        self.items.setdefault(item_id, {})[field_id] = None
