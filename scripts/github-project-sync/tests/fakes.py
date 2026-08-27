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
    PRIORITY_FIELD_NAME,
    PRIORITY_OPTIONS,
    STATUS_FIELD_NAME,
    STATUS_OPTIONS,
    GhAdapterError,
    GhAuthScopeError,
    IssueView,
    Project,
    ProjectFields,
    PullRequestView,
)


@dataclass
class _FakeIssue:
    title: str
    body: str
    state: str
    author_login: str
    url: str
    comments: list[str] = field(default_factory=list)
    labels: frozenset[str] = field(default_factory=frozenset)


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
        # Repo-weit existierende Labels - "bug" ist im echten Repo bereits vorhanden (siehe ADR
        # 0030, Abschnitt 6: Wiederverwendung statt Neuanlage eines spezifischeren Labels).
        self.repo_labels: set[str] = {"bug"}
        self.ensure_label_calls: list[str] = []
        # Nur Namen, fuer die tatsaechlich NEU angelegt wurde (Label war vorher nicht in
        # repo_labels) - im Unterschied zu ensure_label_calls (jeder Aufruf, unabhaengig vom
        # Ergebnis). Damit koennen Tests "kein Duplikat angelegt" praezise pruefen (Review-
        # Finding: die vorherige Fake-Implementierung war unbedingt, verzweigte nie).
        self.ensure_label_created: list[str] = []
        # Seit Spec 0060 / ADR 0037, Abschnitt 5: Grundlage der automatischen
        # PR-Merge-Erkennung. Tests seeden gezielt per seed_pull_request().
        self._pull_requests: dict[int, PullRequestView] = {}

    # -- Setup-Helfer fuer Tests -------------------------------------------------
    def seed_pull_request(self, number: int, *, state: str, url: str | None = None) -> None:
        self._pull_requests[number] = PullRequestView(
            state=state,
            url=url or f"https://github.com/{self.owner}/photosort/pull/{number}",
        )
    def seed_issue(
        self,
        number: int,
        *,
        body: str,
        state: str = "open",
        author_login: str | None = None,
        labels: frozenset[str] = frozenset(),
    ) -> None:
        self._issues[number] = _FakeIssue(
            title=f"issue-{number}",
            body=body,
            state=state,
            author_login=author_login or self.owner,
            url=f"https://github.com/{self.owner}/photosort/issues/{number}",
            labels=labels,
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
            labels=issue.labels,
        )

    def get_pull_request(self, pr_number: int) -> PullRequestView:
        if pr_number not in self._pull_requests:
            raise GhAdapterError(f"Fake: PR {pr_number!r} nicht bekannt (seed_pull_request()?).")
        return self._pull_requests[pr_number]

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

    def ensure_label(self, name: str, *, description: str, color: str) -> None:
        self.ensure_label_calls.append(name)
        if name in self.repo_labels:
            return
        self.repo_labels.add(name)
        self.ensure_label_created.append(name)

    def set_issue_labels(
        self, issue_number: int, *, add: frozenset[str], remove: frozenset[str]
    ) -> None:
        issue = self._issues[issue_number]
        issue.labels = (issue.labels | add) - remove

    def get_item_field_value(
        self, project: Project, *, item_id: str, field_name: str
    ) -> str | None:
        assert self.fields is not None, "ensure_fields() muss vor get_item_field_value() laufen."
        if field_name == STATUS_FIELD_NAME:
            field_id, options = self.fields.status_field_id, self.fields.status_options
        elif field_name == PRIORITY_FIELD_NAME:
            field_id, options = self.fields.priority_field_id, self.fields.priority_options
        else:
            raise GhAdapterError(f"Fake kennt kein Feld {field_name!r}.")
        if item_id not in self.items:
            raise GhAdapterError(f"Fake: Item {item_id!r} nicht bekannt.")
        option_id = self.items[item_id].get(field_id)
        if option_id is None:
            return None
        reverse = {v: k for k, v in options.items()}
        return reverse.get(option_id, option_id)
