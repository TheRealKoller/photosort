"""Tests fuer scripts/gh-board.py (Spec 0262 / ADR 0043).

Kein Netzwerk, kein echtes `gh`: das Script bekommt sein `run`-Callable injiziert, ein FakeGh
beantwortet die Aufrufe aus einem In-Memory-Zustand und protokolliert dabei die tatsaechlich
konstruierten Argumentlisten (dieselbe Technik wie im abgeloesten test_gh_adapter.py).
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

# Bindestrich im Dateinamen (analog zu seed-opencloud-demo.py, siehe conftest.py) - kein
# gueltiger Python-Modulname, daher per Pfad statt per "import" geladen.
_SCRIPT_PATH = Path(__file__).parent.parent / "gh-board.py"

OWNER = "TheRealKoller"
REPO = "photosort"
PROJECT_TITLE = "PhotoSort Roadmap"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("gh_board", _SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def gh_board() -> ModuleType:
    return _load_module()


def _completed(
    stdout: str = "", *, returncode: int = 0, stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["gh"], returncode=returncode, stdout=stdout, stderr=stderr
    )


class FakeGh:
    """Minimaler, zustandsbehafteter Ersatz fuer echte `gh`-Aufrufe."""

    def __init__(
        self,
        *,
        auth_scopes: str = "- Token scopes: 'gist', 'project', 'read:org', 'repo'",
        auth_returncode: int = 0,
        projects: list[dict] | None = None,
        fields: list[dict] | None = None,
        items: list[dict] | None = None,
        labels: list[str] | None = None,
        issue_create_stdout: str | None = None,
        pull_requests: dict[int, dict] | None = None,
        closing_prs: dict[int, list[dict]] | None = None,
        issue_states: dict[int, str] | None = None,
        done_schliesst_das_issue: bool = False,
        failing: set[tuple[str, ...]] | None = None,
        failure_stderr: dict[tuple[str, ...], str] | None = None,
    ) -> None:
        self.auth_scopes = auth_scopes
        self.auth_returncode = auth_returncode
        self.projects = (
            projects
            if projects is not None
            else [{"number": 7, "id": "PVT_project", "title": PROJECT_TITLE}]
        )
        self.fields = (
            fields
            if fields is not None
            else [
                {
                    "id": "FIELD_status",
                    "name": "Status",
                    "options": [
                        {"id": f"OPT_{name}", "name": name}
                        for name in [
                            "Unrefined",
                            "Ready",
                            "Todo",
                            "In Progress",
                            "Review",
                            "Done",
                        ]
                    ],
                },
                {"id": "FIELD_prio", "name": "Priorität", "options": []},
            ]
        )
        self.items = (
            items
            if items is not None
            else [
                {
                    "id": "PVTI_262",
                    "content": {"type": "Issue", "number": 262, "url": _issue_url(262)},
                    "status": "Ready",
                }
            ]
        )
        self.labels = labels if labels is not None else ["idee", "bug"]
        self.issue_create_stdout = (
            issue_create_stdout if issue_create_stdout is not None else _issue_url(311) + "\n"
        )
        self.pull_requests = pull_requests or {}
        self.closing_prs = closing_prs or {}
        # Zustandsbehaftet statt Antwort-Tabelle: `gh issue close` und `gh issue view --json
        # state` schauen auf denselben Zustand - genau darin besteht der Fall aus ADR 0048
        # (Testkonzept, Sektion "Erweiterung fuer ADR 0048"). Default: alle Issues offen.
        self.issue_states = dict(issue_states or {})
        # Opt-in-Modell des Board-Workflows `Auto-close issue` (ADR 0046, Abschnitt 5): ein
        # `item-edit` auf die `Done`-Options-Id schliesst das Issue. Bewusst KEIN Default -
        # sonst bekaemen alle unbeteiligten Tests ein Verhalten aufgepraegt, das ihr
        # Pruefgegenstand nicht ist.
        self.done_schliesst_das_issue = done_schliesst_das_issue
        self.failing = failing or set()
        # Je Aufruf-Praefix die stderr-Ausgabe, mit der er scheitern soll - die reale
        # Fehlermeldung entscheidet, wie `gh-board.py` sie einordnet.
        self.failure_stderr = failure_stderr or {}
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(args))
        for prefix in self.failing:
            if tuple(args[: len(prefix)]) == prefix:
                return _completed(
                    returncode=1, stderr=self.failure_stderr.get(prefix, "fake gh failure")
                )
        return self._dispatch(args)

    def _dispatch(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        head = tuple(args[:3])
        if head == ("gh", "auth", "status"):
            return _completed(self.auth_scopes, returncode=self.auth_returncode)
        if head == ("gh", "project", "list"):
            return _completed(json.dumps({"projects": self.projects}))
        if head == ("gh", "project", "field-list"):
            return _completed(json.dumps({"fields": self.fields}))
        if head == ("gh", "project", "item-list"):
            return _completed(json.dumps({"items": self.items, "totalCount": len(self.items)}))
        if head == ("gh", "project", "item-edit"):
            if self.done_schliesst_das_issue and "OPT_Done" in args:
                self.issue_states[self._issue_of_item(args[args.index("--id") + 1])] = "closed"
            return _completed("")
        if head == ("gh", "project", "item-add"):
            url = args[args.index("--url") + 1]
            number = int(url.rsplit("/", 1)[-1])
            item = {
                "id": f"PVTI_{number}",
                "content": {"type": "Issue", "number": number, "url": url},
            }
            self.items.append(item)
            return _completed(json.dumps({"id": item["id"]}))
        if head == ("gh", "issue", "create"):
            return _completed(self.issue_create_stdout)
        if head == ("gh", "issue", "close"):
            number = int(args[3])
            if self.issue_state(number) == "closed":
                # Real beobachtete Meldung (Spec 0278). Sie ist Kulisse, nie Pruefgegenstand:
                # keine Assertion darf auf ihr aufsetzen, sonst waere die in ADR 0048
                # verworfene Fehlertext-Heuristik durch die Hintertuer zurueck.
                return _completed(returncode=1, stderr=BEREITS_GESCHLOSSEN_STDERR)
            self.issue_states[number] = "closed"
            return _completed("")
        if head[:2] == ("gh", "issue") and head[2] in {"edit", "reopen"}:
            return _completed("")
        if head == ("gh", "issue", "view"):
            number = int(args[3])
            fields = args[args.index("--json") + 1]
            if fields == "state":
                return _completed(json.dumps({"state": self.issue_state(number).upper()}))
            if fields == "closedByPullRequestsReferences":
                return _completed(
                    json.dumps(
                        {"closedByPullRequestsReferences": self.closing_prs.get(number, [])}
                    )
                )
            raise AssertionError(f"unerwartete --json-Felder fuer 'gh issue view': {fields!r}")
        if head == ("gh", "pr", "view"):
            number = int(args[3])
            if number not in self.pull_requests:
                return _completed(returncode=1, stderr=f"no pull request #{number}")
            return _completed(json.dumps(self.pull_requests[number]))
        if head == ("gh", "label", "list"):
            return _completed(json.dumps([{"name": name} for name in self.labels]))
        if head == ("gh", "label", "create"):
            self.labels.append(args[3])
            return _completed("")
        raise AssertionError(f"unerwarteter gh-Aufruf im Test: {args}")

    # -- Zustand -----------------------------------------------------------------------------

    def issue_state(self, number: int) -> str:
        return self.issue_states.get(number, "open")

    def _issue_of_item(self, item_id: str) -> int:
        for item in self.items:
            if item["id"] == item_id:
                return int((item.get("content") or {})["number"])
        raise AssertionError(f"unbekanntes Board-Item im Test: {item_id!r}")

    # -- Auswertungshilfen -------------------------------------------------------------------

    def calls_starting_with(self, *prefix: str) -> list[list[str]]:
        return [call for call in self.calls if tuple(call[: len(prefix)]) == prefix]

    def single_call(self, *prefix: str) -> list[str]:
        matches = self.calls_starting_with(*prefix)
        assert len(matches) == 1, f"erwartet genau ein {prefix!r}, gefunden: {matches}"
        return matches[0]


def _issue_url(number: int) -> str:
    return f"https://github.com/{OWNER}/{REPO}/issues/{number}"


def _pr_url(number: int) -> str:
    return f"https://github.com/{OWNER}/{REPO}/pull/{number}"


# So meldet `gh` ein `--json`-Feld, das die installierte Version nicht kennt - der Fall
# `closingIssuesReferences` mit gh < 2.72.0. Wortgetreue Form, Feldliste gekuerzt.
UNKNOWN_JSON_FIELD_STDERR = (
    'unknown JSON field: "closingIssuesReferences"\n'
    "Available fields:\n"
    "  additions\n"
    "  assignees\n"
    "  author\n"
    "  baseRefName\n"
    "  body\n"
    "  state\n"
    "  url"
)

# So scheitert `gh issue close` real auf einem bereits geschlossenen Issue (beobachtet bei der
# Finalisierung von Spec 0209, PR #277). Der Text ist Kulisse fuer den FakeGh - das
# Produktivverhalten haengt bewusst nicht an ihm (ADR 0048, Abschnitt 2).
BEREITS_GESCHLOSSEN_STDERR = "GraphQL: Could not close the issue. (closeIssue)"

# Ein Fehlschlag, der mit der `gh`-Version nichts zu tun hat.
ABGELAUFENES_TOKEN_STDERR = "gh: Bad credentials (HTTP 401)\nTry authenticating with: gh auth login"


def _closing_ref(number: int, *, owner: str = OWNER, repo: str = REPO) -> dict:
    """Ein Eintrag aus `closingIssuesReferences`, in der Feldform der echten `gh`-Antwort.

    Die Eintraege sind repo-qualifiziert - genau deshalb vergleicht `gh-board.py` das Tripel
    Owner/Repo/Nummer und nicht bloss die Nummer (ADR 0046, Abschnitt 3).
    """
    return {
        "number": number,
        "url": f"https://github.com/{owner}/{repo}/issues/{number}",
        "repository": {"name": repo, "owner": {"login": owner}},
    }


def _pull_request(
    number: int,
    *,
    state: str = "OPEN",
    base_ref_name: str = "main",
    closing_issues: list[dict] | None = None,
) -> dict:
    """PR-Antwort fuer den FakeGh - mit standardmaessig erfuellter Verknuepfungs-Vorbedingung.

    Die Default-Werte (`baseRefName` = Default-Branch, Referenz auf Issue 262) halten die
    Tests gruen, deren Pruefgegenstand ein ganz anderer ist; sonst faerbte eine vergessene
    Vorbedingung ein Dutzend Tests mit einer irrefuehrenden Meldung rot (Testkonzept,
    Abschnitt zu Spec 0251).
    """
    return {
        "state": state,
        "url": _pr_url(number),
        "baseRefName": base_ref_name,
        "closingIssuesReferences": (
            [_closing_ref(262)] if closing_issues is None else closing_issues
        ),
    }


def _board(gh_board: ModuleType, fake: FakeGh):
    return gh_board.GhBoard(owner=OWNER, project_title=PROJECT_TITLE, run=fake)


def _write_spec(
    repo_root: Path, number: str, *, status: str = "Accepted", title: str = "Beispiel-Spec"
) -> Path:
    features = repo_root / "specs" / "features"
    features.mkdir(parents=True, exist_ok=True)
    path = features / f"{number}-beispiel.md"
    path.write_text(
        f"# {number} - {title}\n"
        f"\n"
        f"**Status:** {status}\n"
        f"**Erstellt:** 2026-08-29\n"
        f"**Bezug:** [GitHub-Issue #262]({_issue_url(262)})\n"
        f"\n"
        f"## Ziel\n"
        f"\n"
        f"Irgendetwas. Auch hier steht ein **Status:** Beispieltext, der nicht getroffen "
        f"werden darf.\n",
        encoding="utf-8",
    )
    return path


# -- Auth-Scope -------------------------------------------------------------------------------


def test_fehlender_project_scope_wird_als_eigener_fehler_gemeldet(gh_board: ModuleType) -> None:
    fake = FakeGh(auth_scopes="- Token scopes: 'gist', 'read:org', 'repo'")
    board = _board(gh_board, fake)

    with pytest.raises(gh_board.BoardError) as excinfo:
        board.check_auth_scope()

    assert "gh auth refresh -s project" in str(excinfo.value)


def test_auth_status_fehlschlag_wird_gemeldet(gh_board: ModuleType) -> None:
    fake = FakeGh(auth_returncode=1)
    board = _board(gh_board, fake)

    with pytest.raises(gh_board.BoardError):
        board.check_auth_scope()


def test_vorhandener_project_scope_ist_still(gh_board: ModuleType) -> None:
    fake = FakeGh()
    _board(gh_board, fake).check_auth_scope()

    assert fake.single_call("gh", "auth", "status") == ["gh", "auth", "status"]


# -- Projekt-/Feld-Aufloesung -----------------------------------------------------------------


def test_unbekanntes_projekt_wird_nicht_angelegt_sondern_gemeldet(gh_board: ModuleType) -> None:
    fake = FakeGh(projects=[{"number": 1, "id": "PVT_other", "title": "Anderes Board"}])
    board = _board(gh_board, fake)

    with pytest.raises(gh_board.BoardError) as excinfo:
        board.project()

    assert PROJECT_TITLE in str(excinfo.value)
    assert fake.calls_starting_with("gh", "project", "create") == []


def test_fehlendes_statusfeld_wird_nicht_angelegt_sondern_gemeldet(gh_board: ModuleType) -> None:
    fake = FakeGh(fields=[{"id": "FIELD_prio", "name": "Priorität", "options": []}])
    board = _board(gh_board, fake)

    with pytest.raises(gh_board.BoardError) as excinfo:
        board.status_field()

    assert "Status" in str(excinfo.value)
    assert fake.calls_starting_with("gh", "project", "field-create") == []


def test_projekt_und_feld_werden_nur_einmal_aufgeloest(gh_board: ModuleType) -> None:
    fake = FakeGh()
    board = _board(gh_board, fake)

    board.status_field()
    board.status_field()

    assert len(fake.calls_starting_with("gh", "project", "list")) == 1
    assert len(fake.calls_starting_with("gh", "project", "field-list")) == 1


# -- Prioritaetsfeld-Aufloesung ----------------------------------------------------------------


def test_prioritaetsfeld_wird_aufgeloest(gh_board: ModuleType) -> None:
    fake = FakeGh()
    board = _board(gh_board, fake)

    field = board.priority_field()

    assert field["id"] == "FIELD_prio"
    assert field["name"] == "Priorität"


def test_fehlendes_prioritaetsfeld_wird_nicht_angelegt_sondern_gemeldet(
    gh_board: ModuleType,
) -> None:
    fake = FakeGh(
        fields=[
            {
                "id": "FIELD_status",
                "name": "Status",
                "options": [{"id": "OPT_Ready", "name": "Ready"}],
            }
        ]
    )
    board = _board(gh_board, fake)

    with pytest.raises(gh_board.BoardError) as excinfo:
        board.priority_field()

    assert "Priorität" in str(excinfo.value)
    assert fake.calls_starting_with("gh", "project", "field-create") == []


# -- Item-Aufloesung ueber die Issue-Nummer ---------------------------------------------------


def test_item_wird_ueber_die_issue_nummer_aufgeloest(gh_board: ModuleType) -> None:
    fake = FakeGh()
    board = _board(gh_board, fake)

    assert board.find_item(262)["id"] == "PVTI_262"


def test_unbekanntes_issue_im_board_ist_ein_klarer_fehler(gh_board: ModuleType) -> None:
    fake = FakeGh()
    board = _board(gh_board, fake)

    with pytest.raises(gh_board.BoardError) as excinfo:
        board.find_item(999)

    assert "999" in str(excinfo.value)


def test_gleichnamige_pr_nummer_wird_nicht_mit_einem_issue_verwechselt(
    gh_board: ModuleType,
) -> None:
    fake = FakeGh(
        items=[
            {
                "id": "PVTI_pr",
                "content": {"type": "PullRequest", "number": 262, "url": _pr_url(262)},
            }
        ]
    )
    board = _board(gh_board, fake)

    with pytest.raises(gh_board.BoardError):
        board.find_item(262)


# -- set-status -------------------------------------------------------------------------------


def test_set_status_setzt_die_passende_options_id(gh_board: ModuleType) -> None:
    fake = FakeGh()

    result = gh_board.cmd_set_status(_board(gh_board, fake), issue_number=262, status="In Progress")

    assert result == {"issue_number": 262, "status": "In Progress"}
    assert fake.single_call("gh", "project", "item-edit") == [
        "gh",
        "project",
        "item-edit",
        "--id",
        "PVTI_262",
        "--project-id",
        "PVT_project",
        "--field-id",
        "FIELD_status",
        "--single-select-option-id",
        "OPT_In Progress",
    ]


def test_set_status_done_schliesst_das_issue_zusaetzlich(gh_board: ModuleType) -> None:
    fake = FakeGh()

    gh_board.cmd_set_status(_board(gh_board, fake), issue_number=262, status="Done")

    assert fake.single_call("gh", "issue", "close") == ["gh", "issue", "close", "262"]


def test_set_status_ohne_done_laesst_den_issue_zustand_unangetastet(gh_board: ModuleType) -> None:
    fake = FakeGh()

    gh_board.cmd_set_status(_board(gh_board, fake), issue_number=262, status="Review")

    assert fake.calls_starting_with("gh", "issue", "close") == []
    assert fake.calls_starting_with("gh", "issue", "reopen") == []


def test_unbekannter_statuswert_wird_abgelehnt(gh_board: ModuleType) -> None:
    fake = FakeGh()

    with pytest.raises(gh_board.BoardError) as excinfo:
        gh_board.cmd_set_status(_board(gh_board, fake), issue_number=262, status="Erledigt")

    assert "Erledigt" in str(excinfo.value)
    assert fake.calls_starting_with("gh", "project", "item-edit") == []


def test_fehlende_options_id_im_board_bricht_ab(gh_board: ModuleType) -> None:
    fake = FakeGh(
        fields=[
            {
                "id": "FIELD_status",
                "name": "Status",
                "options": [{"id": "OPT_Todo", "name": "Todo"}],
            }
        ]
    )

    with pytest.raises(gh_board.BoardError) as excinfo:
        gh_board.cmd_set_status(_board(gh_board, fake), issue_number=262, status="Review")

    assert "Review" in str(excinfo.value)


# -- Prioritaet (get_priority/set_priority/set_priority_if_unset) -----------------------------


_PRIORITY_FIELD_WITH_OPTIONS = {
    "id": "FIELD_prio",
    "name": "Priorität",
    "options": [{"id": f"OPT_prio_{name}", "name": name} for name in ("Hoch", "Mittel", "Niedrig")],
}


def _fields_mit_prioritaets_optionen() -> list[dict]:
    return [
        {
            "id": "FIELD_status",
            "name": "Status",
            "options": [
                {"id": f"OPT_{name}", "name": name}
                for name in ["Unrefined", "Ready", "Todo", "In Progress", "Review", "Done"]
            ],
        },
        _PRIORITY_FIELD_WITH_OPTIONS,
    ]


def test_get_priority_liest_den_klartextwert(gh_board: ModuleType) -> None:
    fake = FakeGh(
        items=[
            {
                "id": "PVTI_262",
                "content": {"type": "Issue", "number": 262, "url": _issue_url(262)},
                "priorität": "Hoch",
            }
        ]
    )

    assert _board(gh_board, fake).get_priority(262) == "Hoch"


def test_get_priority_liefert_none_bei_leerem_feld(gh_board: ModuleType) -> None:
    fake = FakeGh(
        items=[
            {
                "id": "PVTI_262",
                "content": {"type": "Issue", "number": 262, "url": _issue_url(262)},
                "priorität": "",
            }
        ]
    )

    assert _board(gh_board, fake).get_priority(262) is None


def test_get_priority_liefert_none_wenn_feld_ganz_fehlt(gh_board: ModuleType) -> None:
    fake = FakeGh()  # Standard-Item hat gar kein "priorität"-Feld.

    assert _board(gh_board, fake).get_priority(262) is None


def test_set_priority_setzt_die_passende_options_id(gh_board: ModuleType) -> None:
    fake = FakeGh(fields=_fields_mit_prioritaets_optionen())

    _board(gh_board, fake).set_priority(262, "Mittel")

    assert fake.single_call("gh", "project", "item-edit") == [
        "gh",
        "project",
        "item-edit",
        "--id",
        "PVTI_262",
        "--project-id",
        "PVT_project",
        "--field-id",
        "FIELD_prio",
        "--single-select-option-id",
        "OPT_prio_Mittel",
    ]


def test_set_priority_fehlende_options_id_bricht_ab(gh_board: ModuleType) -> None:
    fake = FakeGh()  # Standard-Prioritaetsfeld hat keine Optionen.

    with pytest.raises(gh_board.BoardError) as excinfo:
        _board(gh_board, fake).set_priority(262, "Hoch")

    assert "Hoch" in str(excinfo.value)
    assert fake.calls_starting_with("gh", "project", "item-edit") == []


def test_set_priority_if_unset_schreibt_bei_leerem_feld(gh_board: ModuleType) -> None:
    fake = FakeGh(fields=_fields_mit_prioritaets_optionen())

    changed, priority = _board(gh_board, fake).set_priority_if_unset(262, "Hoch")

    assert (changed, priority) == (True, "Hoch")
    assert fake.single_call("gh", "project", "item-edit")


def test_set_priority_if_unset_ist_ein_no_op_bei_bereits_gesetztem_feld(
    gh_board: ModuleType,
) -> None:
    fake = FakeGh(
        fields=_fields_mit_prioritaets_optionen(),
        items=[
            {
                "id": "PVTI_262",
                "content": {"type": "Issue", "number": 262, "url": _issue_url(262)},
                "priorität": "Niedrig",
            }
        ],
    )

    changed, priority = _board(gh_board, fake).set_priority_if_unset(262, "Hoch")

    # Rueckgabe ist der VORHANDENE Wert (Niedrig), nicht der angefragte (Hoch).
    assert (changed, priority) == (False, "Niedrig")
    assert fake.calls_starting_with("gh", "project", "item-edit") == []


# -- set-priority -----------------------------------------------------------------------------


def test_cmd_set_priority_schreibt_bei_leerem_feld(gh_board: ModuleType) -> None:
    fake = FakeGh(fields=_fields_mit_prioritaets_optionen())

    result = gh_board.cmd_set_priority(_board(gh_board, fake), issue_number=262, priority="Hoch")

    assert result == {"issue_number": 262, "priority": "Hoch", "changed": True}
    assert fake.single_call("gh", "project", "item-edit")


def test_cmd_set_priority_ist_no_op_bei_bereits_gesetztem_feld(gh_board: ModuleType) -> None:
    fake = FakeGh(
        fields=_fields_mit_prioritaets_optionen(),
        items=[
            {
                "id": "PVTI_262",
                "content": {"type": "Issue", "number": 262, "url": _issue_url(262)},
                "priorität": "Niedrig",
            }
        ],
    )

    result = gh_board.cmd_set_priority(_board(gh_board, fake), issue_number=262, priority="Hoch")

    # Rueckgabe ist der vorhandene Wert (Niedrig), nicht der angefragte (Hoch).
    assert result == {"issue_number": 262, "priority": "Niedrig", "changed": False}
    assert fake.calls_starting_with("gh", "project", "item-edit") == []


def test_cmd_set_priority_unbekannter_wert_wird_vor_jedem_gh_aufruf_abgelehnt(
    gh_board: ModuleType,
) -> None:
    fake = FakeGh()

    with pytest.raises(gh_board.BoardError) as excinfo:
        gh_board.cmd_set_priority(_board(gh_board, fake), issue_number=262, priority="Kritisch")

    assert "Kritisch" in str(excinfo.value)
    assert fake.calls == []


def test_cmd_set_priority_fehlende_options_id_fuer_gueltigen_wert_bricht_ab(
    gh_board: ModuleType,
) -> None:
    fake = FakeGh()  # Standard-Prioritaetsfeld ist vorhanden, hat aber keine Optionen.

    with pytest.raises(gh_board.BoardError) as excinfo:
        gh_board.cmd_set_priority(_board(gh_board, fake), issue_number=262, priority="Hoch")

    assert "Hoch" in str(excinfo.value)


# -- show-status ------------------------------------------------------------------------------


def test_show_status_liest_den_aktuellen_wert_ohne_schreibzugriff(gh_board: ModuleType) -> None:
    fake = FakeGh()

    result = gh_board.cmd_show_status(_board(gh_board, fake), issue_number=262)

    assert result == {"issue_number": 262, "status": "Ready"}
    assert fake.calls_starting_with("gh", "project", "item-edit") == []
    assert fake.calls_starting_with("gh", "issue", "edit") == []


def test_show_status_liefert_none_bei_leerem_feld(gh_board: ModuleType) -> None:
    fake = FakeGh(
        items=[
            {
                "id": "PVTI_262",
                "content": {"type": "Issue", "number": 262, "url": _issue_url(262)},
                "status": "",
            }
        ]
    )

    assert gh_board.cmd_show_status(_board(gh_board, fake), issue_number=262)["status"] is None


# -- set-body ---------------------------------------------------------------------------------


def test_set_body_uebergibt_den_body_ueber_eine_datei(gh_board: ModuleType) -> None:
    fake = FakeGh()

    result = gh_board.cmd_set_body(_board(gh_board, fake), issue_number=262, body="Neuer Text")

    assert result == {"issue_number": 262}
    call = fake.single_call("gh", "issue", "edit")
    assert call[:4] == ["gh", "issue", "edit", "262"]
    assert call[4] == "--body-file"
    assert "Neuer Text" not in " ".join(call)


def test_temporaere_body_datei_wird_wieder_entfernt(gh_board: ModuleType) -> None:
    fake = FakeGh()
    gh_board.cmd_set_body(_board(gh_board, fake), issue_number=262, body="Neuer Text")

    body_path = Path(fake.single_call("gh", "issue", "edit")[5])
    assert not body_path.exists()


# -- create-issue -----------------------------------------------------------------------------


def test_create_issue_legt_label_projektitem_und_status_an(gh_board: ModuleType) -> None:
    fake = FakeGh()

    result = gh_board.cmd_create_issue(
        _board(gh_board, fake), typ="idee", title="Neue Idee", body="Rohtext"
    )

    assert result == {"issue_number": 311}
    create_call = fake.single_call("gh", "issue", "create")
    assert "--label" in create_call
    assert create_call[create_call.index("--label") + 1] == "idee"
    assert "Rohtext" not in " ".join(create_call)
    assert fake.single_call("gh", "project", "item-add") == [
        "gh",
        "project",
        "item-add",
        "7",
        "--owner",
        OWNER,
        "--url",
        _issue_url(311),
        "--format",
        "json",
    ]
    item_edit = fake.single_call("gh", "project", "item-edit")
    assert item_edit[item_edit.index("--single-select-option-id") + 1] == "OPT_Unrefined"


def test_create_issue_legt_ein_fehlendes_label_vorher_an(gh_board: ModuleType) -> None:
    fake = FakeGh(labels=["bug"])

    gh_board.cmd_create_issue(_board(gh_board, fake), typ="idee", title="T", body="B")

    assert fake.single_call("gh", "label", "create")[3] == "idee"


def test_create_issue_legt_ein_vorhandenes_label_nicht_erneut_an(gh_board: ModuleType) -> None:
    fake = FakeGh(labels=["idee", "bug"])

    gh_board.cmd_create_issue(_board(gh_board, fake), typ="idee", title="T", body="B")

    assert fake.calls_starting_with("gh", "label", "create") == []


def test_unbekannter_typ_wird_abgelehnt(gh_board: ModuleType) -> None:
    fake = FakeGh()

    with pytest.raises(gh_board.BoardError):
        gh_board.cmd_create_issue(_board(gh_board, fake), typ="epic", title="T", body="B")

    assert fake.calls_starting_with("gh", "issue", "create") == []


def test_unparsbare_ausgabe_von_issue_create_bricht_ab(gh_board: ModuleType) -> None:
    fake = FakeGh(issue_create_stdout="irgendwas ohne URL\n")

    with pytest.raises(gh_board.BoardError):
        gh_board.cmd_create_issue(_board(gh_board, fake), typ="idee", title="T", body="B")


# -- get_pull_request ------------------------------------------------------------------------


def test_get_pull_request_holt_die_verknuepfungsfelder_und_niemals_den_body(
    gh_board: ModuleType,
) -> None:
    """Die Verknuepfungspruefung faehrt im ohnehin abgesetzten `gh pr view` mit (ADR 0046,
    Abschnitt 3). Dass **kein** `body` angefragt wird, ist keine Nebenwirkung, sondern eine
    zugesicherte Eigenschaft: von aussen befuellbarer Fremdtext wird gar nicht erst eingelesen.
    """
    fake = FakeGh(pull_requests={281: _pull_request(281)})

    data = _board(gh_board, fake).get_pull_request(281)

    call = fake.single_call("gh", "pr", "view")
    assert call == [
        "gh",
        "pr",
        "view",
        "281",
        "--json",
        "state,url,baseRefName,closingIssuesReferences",
    ]
    assert not any("body" in arg for arg in call)
    assert data["state"] == "open"
    assert data["url"] == _pr_url(281)
    assert data["baseRefName"] == "main"
    assert data["closingIssuesReferences"] == [_closing_ref(262)]


# -- Zielzustands-Idempotenz beim Schliessen (Spec 0278 / ADR 0048) ---------------------------


def _zustandsabfragen(fake: FakeGh) -> list[list[str]]:
    """Nur die Zustands-Nachpruefungen aus dem Aufruflog - `gh issue view` gibt es auch mit
    anderen `--json`-Feldern (`closedByPullRequestsReferences`)."""
    return [
        call
        for call in fake.calls_starting_with("gh", "issue", "view")
        if call[call.index("--json") + 1] == "state"
    ]


def test_issue_state_fragt_genau_das_state_feld_ab_und_normalisiert(gh_board: ModuleType) -> None:
    """`gh` liefert den GraphQL-Enum gross (CLOSED); ohne Normalisierung griffe die Ausnahme nie.
    Abgefragt wird ausschliesslich `state` - nie Titel, Body, Labels oder Kommentare."""
    fake = FakeGh(issue_states={262: "closed"})

    assert _board(gh_board, fake).issue_state(262) == "closed"
    assert fake.single_call("gh", "issue", "view") == [
        "gh",
        "issue",
        "view",
        "262",
        "--json",
        "state",
    ]


@pytest.mark.parametrize("payload", ['{"state": null}', "{}", '{"state": ""}', "[]"])
def test_issue_state_meldet_ein_unbrauchbares_state_feld_als_boarderror(
    gh_board: ModuleType, payload: str
) -> None:
    """Ein KeyError/AttributeError wuerde die Ausgabekonvention des Werkzeugs
    ({"error": ...} plus Exit-Code 1) mit einem Traceback brechen."""

    def run(args: list[str]) -> subprocess.CompletedProcess[str]:
        if tuple(args[:3]) == ("gh", "issue", "view"):
            return _completed(payload)
        return FakeGh()(args)

    with pytest.raises(gh_board.BoardError):
        gh_board.GhBoard(owner=OWNER, project_title=PROJECT_TITLE, run=run).issue_state(262)


def test_close_issue_ist_still_wenn_das_issue_bereits_geschlossen_ist(
    gh_board: ModuleType,
) -> None:
    """Kern von AK 1/2: Zielzustand ist 'Issue geschlossen', nicht 'dieser Aufruf hat es
    geschlossen'."""
    fake = FakeGh(issue_states={262: "closed"})

    _board(gh_board, fake).close_issue(262)

    assert fake.single_call("gh", "issue", "close") == ["gh", "issue", "close", "262"]


def test_close_issue_meldet_den_urspruenglichen_fehler_wenn_das_issue_offen_ist(
    gh_board: ModuleType,
) -> None:
    """AK 5: ein echter Fehlschlag (z.B. abgelaufenes Token) bleibt ein Fehler - und zwar mit dem
    Originaltext von `gh issue close`, nicht mit dem der Nachpruefung."""
    fake = FakeGh(
        failing={("gh", "issue", "close")},
        failure_stderr={("gh", "issue", "close"): ABGELAUFENES_TOKEN_STDERR},
    )

    with pytest.raises(gh_board.BoardError) as excinfo:
        _board(gh_board, fake).close_issue(262)

    assert "Bad credentials" in str(excinfo.value)


def test_close_issue_meldet_den_close_fehler_wenn_die_nachpruefung_selbst_scheitert(
    gh_board: ModuleType,
) -> None:
    """AK 5: nicht existierendes Issue / fehlende Berechtigung / Dienst nicht erreichbar - der
    aussagekraeftigere `close`-Fehler wird gemeldet, der Lesefehler haengt als Ursache daran."""
    fake = FakeGh(
        failing={("gh", "issue", "close"), ("gh", "issue", "view")},
        failure_stderr={
            ("gh", "issue", "close"): ABGELAUFENES_TOKEN_STDERR,
            ("gh", "issue", "view"): "gh: Not Found (HTTP 404)",
        },
    )

    with pytest.raises(gh_board.BoardError) as excinfo:
        _board(gh_board, fake).close_issue(262)

    assert "Bad credentials" in str(excinfo.value)
    assert "Not Found" in str(excinfo.value.__cause__)


def test_close_issue_prueft_den_zustand_im_erfolgsfall_nicht_nach(gh_board: ModuleType) -> None:
    """AK 8 / Regressionsschutz: die Pruefung ist eine Nachpruefung, keine Vorabpruefung - sonst
    kostet sie in jedem `Done`-Pfad einen zusaetzlichen `gh`-Aufruf, ohne das Rennen mit der
    asynchronen Board-Automation zu beseitigen."""
    fake = FakeGh()

    _board(gh_board, fake).close_issue(262)

    assert _zustandsabfragen(fake) == []


def test_set_status_done_auf_bereits_geschlossenem_issue_meldet_erfolg(
    gh_board: ModuleType,
) -> None:
    """AK 2/4: regulaerer Payload, und der Zielzustand wird trotzdem vollstaendig hergestellt -
    die Board-Spalte wird gesetzt, das Schliessen versucht."""
    fake = FakeGh(issue_states={262: "closed"})

    result = gh_board.cmd_set_status(_board(gh_board, fake), issue_number=262, status="Done")

    assert result == {"issue_number": 262, "status": "Done"}
    item_edit = fake.single_call("gh", "project", "item-edit")
    assert item_edit[item_edit.index("--single-select-option-id") + 1] == "OPT_Done"
    assert fake.single_call("gh", "issue", "close") == ["gh", "issue", "close", "262"]


def test_set_status_done_ueberlebt_die_auto_close_automation_des_boards(
    gh_board: ModuleType,
) -> None:
    """Reproduktion des gemeldeten Falls im Zusammenhang: das `Done` schliesst das Issue ueber
    den Board-Workflow, das eigene `close` trifft es danach bereits geschlossen an."""
    fake = FakeGh(done_schliesst_das_issue=True)

    result = gh_board.cmd_set_status(_board(gh_board, fake), issue_number=262, status="Done")

    assert result == {"issue_number": 262, "status": "Done"}
    assert fake.issue_state(262) == "closed"


def test_set_status_done_ist_ununterscheidbar_vom_selbst_geschlossenen_fall(
    gh_board: ModuleType,
) -> None:
    """AK 3 als Gleichheit zweier real erzeugter Ergebnisse - nicht als Feldliste: nur diese Form
    faengt ein spaeter nachgeruestetes Feld ('war schon geschlossen') ab."""
    ergebnis_bereits_geschlossen = gh_board.cmd_set_status(
        _board(gh_board, FakeGh(issue_states={262: "closed"})), issue_number=262, status="Done"
    )
    ergebnis_frisch_geschlossen = gh_board.cmd_set_status(
        _board(gh_board, FakeGh()), issue_number=262, status="Done"
    )

    assert ergebnis_bereits_geschlossen == ergebnis_frisch_geschlossen


# -- finalize ---------------------------------------------------------------------------------


def test_finalize_schreibt_statuszeile_setzt_done_und_schliesst_das_issue(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    path = _write_spec(tmp_path, "0262")
    fake = FakeGh(pull_requests={281: _pull_request(281)})

    result = gh_board.cmd_finalize(
        _board(gh_board, fake),
        repo_root=tmp_path,
        spec_number="0262",
        issue_number=262,
        pr_number=281,
    )

    assert result == {
        "spec_number": "0262",
        "issue_number": 262,
        "pr_number": 281,
        "status_line": f"Implemented ([PR #281]({_pr_url(281)}))",
        "status": "Done",
    }
    text = path.read_text(encoding="utf-8")
    assert f"**Status:** Implemented ([PR #281]({_pr_url(281)}))\n" in text
    # Der '**Status:**'-Vorkommen in der Inhaltszone darf nicht getroffen werden.
    assert "Auch hier steht ein **Status:** Beispieltext" in text
    item_edit = fake.single_call("gh", "project", "item-edit")
    assert item_edit[item_edit.index("--single-select-option-id") + 1] == "OPT_Done"
    assert fake.single_call("gh", "issue", "close") == ["gh", "issue", "close", "262"]


def test_finalize_ueberlebt_die_auto_close_automation_des_boards(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    """AK 1/4 als Reproduktion des gemeldeten Falls (Finalisierung von Spec 0209, PR #277): das
    `Done` schliesst das Issue ueber den Board-Workflow, das eigene `close` trifft es danach
    bereits geschlossen an - der Zielzustand entsteht trotzdem vollstaendig."""
    path = _write_spec(tmp_path, "0262")
    fake = FakeGh(pull_requests={281: _pull_request(281)}, done_schliesst_das_issue=True)

    result = gh_board.cmd_finalize(
        _board(gh_board, fake),
        repo_root=tmp_path,
        spec_number="0262",
        issue_number=262,
        pr_number=281,
    )

    assert result["status"] == "Done"
    assert f"**Status:** Implemented ([PR #281]({_pr_url(281)}))\n" in path.read_text(
        encoding="utf-8"
    )
    item_edit = fake.single_call("gh", "project", "item-edit")
    assert item_edit[item_edit.index("--single-select-option-id") + 1] == "OPT_Done"
    assert fake.single_call("gh", "issue", "close") == ["gh", "issue", "close", "262"]


def test_finalize_ist_ununterscheidbar_vom_selbst_geschlossenen_fall(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    """AK 3 als Gleichheit zweier real erzeugter Ergebnisse: der aufrufende Ablauf soll den
    Unterschied 'war schon geschlossen' gar nicht sehen koennen."""
    _write_spec(tmp_path / "bereits", "0262")
    _write_spec(tmp_path / "frisch", "0262")

    ergebnis_bereits_geschlossen = gh_board.cmd_finalize(
        _board(
            gh_board,
            FakeGh(pull_requests={281: _pull_request(281)}, issue_states={262: "closed"}),
        ),
        repo_root=tmp_path / "bereits",
        spec_number="0262",
        issue_number=262,
        pr_number=281,
    )
    ergebnis_frisch_geschlossen = gh_board.cmd_finalize(
        _board(gh_board, FakeGh(pull_requests={281: _pull_request(281)})),
        repo_root=tmp_path / "frisch",
        spec_number="0262",
        issue_number=262,
        pr_number=281,
    )

    assert ergebnis_bereits_geschlossen == ergebnis_frisch_geschlossen


def test_finalize_prueft_den_zustand_im_erfolgsfall_nicht_nach(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    """AK 8: der ungestoerte Regelfall setzt weiterhin genau die bisherigen `gh`-Aufrufe ab."""
    _write_spec(tmp_path, "0262")
    fake = FakeGh(pull_requests={281: _pull_request(281)})

    gh_board.cmd_finalize(
        _board(gh_board, fake),
        repo_root=tmp_path,
        spec_number="0262",
        issue_number=262,
        pr_number=281,
    )

    assert _zustandsabfragen(fake) == []


def test_finalize_akzeptiert_einen_bereits_gemergten_pr(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    _write_spec(tmp_path, "0262")
    fake = FakeGh(pull_requests={281: _pull_request(281, state="MERGED")})

    result = gh_board.cmd_finalize(
        _board(gh_board, fake),
        repo_root=tmp_path,
        spec_number="0262",
        issue_number=262,
        pr_number=281,
    )

    assert result["pr_number"] == 281


def test_finalize_lehnt_einen_ohne_merge_geschlossenen_pr_ab(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    path = _write_spec(tmp_path, "0262")
    fake = FakeGh(pull_requests={281: _pull_request(281, state="CLOSED")})

    with pytest.raises(gh_board.BoardError) as excinfo:
        gh_board.cmd_finalize(
            _board(gh_board, fake),
            repo_root=tmp_path,
            spec_number="0262",
            issue_number=262,
            pr_number=281,
        )

    assert "closed" in str(excinfo.value).lower()
    assert "**Status:** Accepted" in path.read_text(encoding="utf-8")


def test_finalize_lehnt_eine_nicht_akzeptierte_spec_ab(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    """Statusgate (c): jeder Status ausser `Accepted`/`Implemented` bricht unveraendert ab, und
    zwar vor jedem GitHub-Zugriff."""
    path = _write_spec(tmp_path, "0262", status="Proposed")
    fake = FakeGh(pull_requests={281: _pull_request(281)})

    with pytest.raises(gh_board.BoardError) as excinfo:
        gh_board.cmd_finalize(
            _board(gh_board, fake),
            repo_root=tmp_path,
            spec_number="0262",
            issue_number=262,
            pr_number=281,
        )

    assert "Accepted" in str(excinfo.value)
    assert "**Status:** Proposed" in path.read_text(encoding="utf-8")
    assert fake.calls == []


def test_finalize_laeuft_bei_bereits_geschriebener_identischer_zielzeile_durch(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    """Statusgate (a) / AK 9 positiv: `Implemented` mit genau der Zeile, die dieser Lauf schreiben
    wuerde, ist ein bereits erreichter Zielzustand - kein Fehler. Geschrieben wird dabei exakt
    der Inhalt, der ohnehin schon in der Datei steht."""
    path = _write_spec(tmp_path, "0262", status=f"Implemented ([PR #281]({_pr_url(281)}))")
    vorher = path.read_text(encoding="utf-8")
    fake = FakeGh(pull_requests={281: _pull_request(281)})

    result = gh_board.cmd_finalize(
        _board(gh_board, fake),
        repo_root=tmp_path,
        spec_number="0262",
        issue_number=262,
        pr_number=281,
    )

    assert result == {
        "spec_number": "0262",
        "issue_number": 262,
        "pr_number": 281,
        "status_line": f"Implemented ([PR #281]({_pr_url(281)}))",
        "status": "Done",
    }
    assert path.read_text(encoding="utf-8") == vorher
    item_edit = fake.single_call("gh", "project", "item-edit")
    assert item_edit[item_edit.index("--single-select-option-id") + 1] == "OPT_Done"


def test_finalize_lehnt_ein_implemented_mit_anderem_pr_ab(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    """Statusgate (b) / AK 9 negativ: das ist kein erreichter Zielzustand, sondern ein Hinweis auf
    die falsche Spec- oder PR-Nummer - Abbruch ohne Board-Schreibzugriff und ohne Dateiaenderung.
    """
    path = _write_spec(tmp_path, "0262", status=f"Implemented ([PR #1]({_pr_url(1)}))")
    fake = FakeGh(pull_requests={281: _pull_request(281)})

    with pytest.raises(gh_board.BoardError):
        gh_board.cmd_finalize(
            _board(gh_board, fake),
            repo_root=tmp_path,
            spec_number="0262",
            issue_number=262,
            pr_number=281,
        )

    assert f"**Status:** Implemented ([PR #1]({_pr_url(1)}))" in path.read_text(encoding="utf-8")
    assert fake.calls_starting_with("gh", "project", "item-edit") == []
    assert fake.calls_starting_with("gh", "issue", "close") == []


def test_finalize_lehnt_eine_zielzeile_mit_abweichendem_freitext_ab(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    """Statusgate (d): verglichen wird die vollstaendige Zeile, nicht das fuehrende Schluesselwort
    aus `read_spec_status()` - gleiche PR-Nummer bei abweichender URL gilt nicht als gleich."""
    path = _write_spec(
        tmp_path, "0262", status="Implemented ([PR #281](https://example.invalid/pull/281))"
    )
    fake = FakeGh(pull_requests={281: _pull_request(281)})

    with pytest.raises(gh_board.BoardError):
        gh_board.cmd_finalize(
            _board(gh_board, fake),
            repo_root=tmp_path,
            spec_number="0262",
            issue_number=262,
            pr_number=281,
        )

    assert "https://example.invalid/pull/281" in path.read_text(encoding="utf-8")
    assert fake.calls_starting_with("gh", "project", "item-edit") == []


def test_finalize_vergleicht_die_zielzeile_nur_in_der_header_zone(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    """Ein in der Inhalts-Zone zitiertes `**Status:**` darf die Gleichheit nicht erfuellen, waehrend
    der Header auf etwas anderem steht - dieselbe `_split_header`-Trennung wie beim Schreiben."""
    path = _write_spec(tmp_path, "0262", status=f"Implemented ([PR #999]({_pr_url(999)}))")
    path.write_text(
        path.read_text(encoding="utf-8")
        + f"\n**Status:** Implemented ([PR #281]({_pr_url(281)}))\n",
        encoding="utf-8",
    )
    vorher = path.read_text(encoding="utf-8")
    fake = FakeGh(pull_requests={281: _pull_request(281)})

    with pytest.raises(gh_board.BoardError):
        gh_board.cmd_finalize(
            _board(gh_board, fake),
            repo_root=tmp_path,
            spec_number="0262",
            issue_number=262,
            pr_number=281,
        )

    assert path.read_text(encoding="utf-8") == vorher
    assert fake.calls_starting_with("gh", "project", "item-edit") == []


def test_finalize_ist_ohne_ruecknahme_wiederholbar(gh_board: ModuleType, tmp_path: Path) -> None:
    """AK 6, als ganzer Aufruf statt als Summe der Einzelschritte: zweimal derselbe Aufruf auf
    demselben zustandsbehafteten FakeGh, ohne dazwischen irgendetwas zurueckzunehmen."""
    path = _write_spec(tmp_path, "0262")
    fake = FakeGh(pull_requests={281: _pull_request(281)}, done_schliesst_das_issue=True)
    board = _board(gh_board, fake)

    def lauf() -> dict:
        return gh_board.cmd_finalize(
            board,
            repo_root=tmp_path,
            spec_number="0262",
            issue_number=262,
            pr_number=281,
        )

    erster_lauf = lauf()
    datei_nach_lauf_1 = path.read_text(encoding="utf-8")
    zweiter_lauf = lauf()

    assert zweiter_lauf == erster_lauf
    assert path.read_text(encoding="utf-8") == datei_nach_lauf_1


def test_finalize_meldet_eine_fehlende_spec_datei(gh_board: ModuleType, tmp_path: Path) -> None:
    (tmp_path / "specs" / "features").mkdir(parents=True)
    fake = FakeGh(pull_requests={281: _pull_request(281)})

    with pytest.raises(gh_board.BoardError) as excinfo:
        gh_board.cmd_finalize(
            _board(gh_board, fake),
            repo_root=tmp_path,
            spec_number="0262",
            issue_number=262,
            pr_number=281,
        )

    assert "0262" in str(excinfo.value)


@pytest.mark.parametrize("number", ["../06", "26", "02620", "abcd", "02 2"])
def test_ungueltige_spec_nummer_wird_vor_jeder_pfadkonstruktion_abgelehnt(
    gh_board: ModuleType, tmp_path: Path, number: str
) -> None:
    fake = FakeGh()

    with pytest.raises(gh_board.BoardError):
        gh_board.cmd_finalize(
            _board(gh_board, fake),
            repo_root=tmp_path,
            spec_number=number,
            issue_number=262,
            pr_number=281,
        )


def test_finalize_ohne_pr_nummer_loest_den_schliessenden_gemergten_pr_auf(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    _write_spec(tmp_path, "0262")
    fake = FakeGh(
        closing_prs={262: [{"number": 281, "url": _pr_url(281)}]},
        pull_requests={281: _pull_request(281, state="MERGED")},
    )

    result = gh_board.cmd_finalize(
        _board(gh_board, fake),
        repo_root=tmp_path,
        spec_number="0262",
        issue_number=262,
        pr_number=None,
    )

    assert result["pr_number"] == 281
    assert result["status_line"] == f"Implemented ([PR #281]({_pr_url(281)}))"


def test_finalize_ohne_gemergten_pr_ist_ein_fehler_statt_einer_stillen_aenderung(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    path = _write_spec(tmp_path, "0262")
    fake = FakeGh(
        closing_prs={262: [{"number": 281, "url": _pr_url(281)}]},
        pull_requests={281: _pull_request(281)},
    )

    with pytest.raises(gh_board.BoardError):
        gh_board.cmd_finalize(
            _board(gh_board, fake),
            repo_root=tmp_path,
            spec_number="0262",
            issue_number=262,
            pr_number=None,
        )

    assert "**Status:** Accepted" in path.read_text(encoding="utf-8")


def test_finalize_ohne_verknuepften_pr_ist_ein_klarer_fehler(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    _write_spec(tmp_path, "0262")
    fake = FakeGh(closing_prs={262: []})

    with pytest.raises(gh_board.BoardError) as excinfo:
        gh_board.cmd_finalize(
            _board(gh_board, fake),
            repo_root=tmp_path,
            spec_number="0262",
            issue_number=262,
            pr_number=None,
        )

    assert "262" in str(excinfo.value)


# -- finalize: PR<->Issue-Verknuepfung (Spec 0251 / ADR 0046) ---------------------------------


def test_finalize_akzeptiert_einen_pr_mit_passender_closing_referenz(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    path = _write_spec(tmp_path, "0262")
    fake = FakeGh(pull_requests={281: _pull_request(281, closing_issues=[_closing_ref(262)])})

    result = gh_board.cmd_finalize(
        _board(gh_board, fake),
        repo_root=tmp_path,
        spec_number="0262",
        issue_number=262,
        pr_number=281,
    )

    assert result["pr_number"] == 281
    assert "**Status:** Implemented" in path.read_text(encoding="utf-8")


def test_finalize_akzeptiert_ein_manuell_verknuepftes_issue_ohne_keyword(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    """Regressionsschutz fuer eine bewusste Entscheidung, kein zweiter Positivfall (ADR 0046,
    Abschnitt 3a): Vorgeschrieben ist die Zeile `Closes #NNN` im PR-Body, geprueft wird aber
    nur ihre **Wirkung** - die von GitHub gepflegte Verknuepfung. Weil `gh pr view --json` die
    Argumente `excludeUserLinked`/`userLinkedOnly` nicht uebergeben kann (beide Schema-Default
    `false`), enthaelt `closingIssuesReferences` auch per Development-Seitenleiste manuell
    verknuepfte Issues; die werden beim Merge genauso geschlossen.

    Aus Sicht des Test-Doubles ist dieser Fall vom Keyword-Fall **nicht unterscheidbar** - die
    Herkunft der Referenz taucht im Feld gar nicht auf. Genau das ist die Aussage: Der Test
    haelt fest, dass eine spaetere Verengung (Umstieg auf `gh api graphql` mit
    `excludeUserLinked: true`, Zusatzpruefung auf die Textzeile) auffallen soll, statt
    stillschweigend durchzugehen. Ohne diese Begruendung saehe er wie ein Duplikat des
    vorherigen Falls aus und waere der erste Kandidat beim Aufraeumen.
    """
    _write_spec(tmp_path, "0262")
    fake = FakeGh(pull_requests={281: _pull_request(281, closing_issues=[_closing_ref(262)])})

    result = gh_board.cmd_finalize(
        _board(gh_board, fake),
        repo_root=tmp_path,
        spec_number="0262",
        issue_number=262,
        pr_number=281,
    )

    assert result["pr_number"] == 281


@pytest.mark.parametrize(
    ("pull_request", "erwartete_textbausteine"),
    [
        pytest.param(_pull_request(281, closing_issues=[]), ["2.72.0"], id="leere-liste"),
        pytest.param(
            _pull_request(281, closing_issues=[_closing_ref(999)]),
            ["2.72.0"],
            id="nur-fremdes-issue",
        ),
        pytest.param(
            _pull_request(281, closing_issues=[_closing_ref(262, owner="fremd", repo="anderes")]),
            ["2.72.0", "fremd/anderes"],
            id="gleiche-nummer-fremdes-repository",
        ),
        pytest.param(
            _pull_request(281, base_ref_name="release/0.24"),
            ["release/0.24", "main"],
            id="nicht-der-default-branch",
        ),
    ],
)
def test_finalize_lehnt_einen_pr_ohne_wirksame_verknuepfung_ab(
    gh_board: ModuleType,
    tmp_path: Path,
    pull_request: dict,
    erwartete_textbausteine: list[str],
) -> None:
    """Abbruch vor dem Umschreiben der Spec-Datei und vor **jedem** Board-Zugriff, auch dem
    lesenden - deshalb wird zusaetzlich das vollstaendige Aufruflog geprueft. Das beweist mehr
    als eine Aufzaehlung verbotener Aufrufe und altert nicht mit neuen Schreibbefehlen.
    """
    path = _write_spec(tmp_path, "0262")
    fake = FakeGh(pull_requests={281: pull_request})

    with pytest.raises(gh_board.BoardError) as excinfo:
        gh_board.cmd_finalize(
            _board(gh_board, fake),
            repo_root=tmp_path,
            spec_number="0262",
            issue_number=262,
            pr_number=281,
        )

    message = str(excinfo.value)
    assert "262" in message
    for baustein in erwartete_textbausteine:
        assert baustein in message
    assert "**Status:** Accepted" in path.read_text(encoding="utf-8")
    assert {tuple(call[:3]) for call in fake.calls} == {("gh", "pr", "view")}


def test_ein_gh_ohne_das_verknuepfungsfeld_wird_als_versionsproblem_gemeldet(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    """Ein `gh` < 2.72.0 kennt `closingIssuesReferences` nicht und laesst den Aufruf mit
    'unknown JSON field' scheitern. Die Meldung muss die Mindestversion nennen, sonst wird ein
    Werkzeugproblem als fehlende Verknuepfung fehlgedeutet - und jemand traegt eine Zeile nach,
    die laengst da ist."""
    path = _write_spec(tmp_path, "0262")
    fake = FakeGh(
        failing={("gh", "pr", "view")},
        failure_stderr={("gh", "pr", "view"): UNKNOWN_JSON_FIELD_STDERR},
    )

    with pytest.raises(gh_board.BoardError) as excinfo:
        gh_board.cmd_finalize(
            _board(gh_board, fake),
            repo_root=tmp_path,
            spec_number="0262",
            issue_number=262,
            pr_number=281,
        )

    message = str(excinfo.value)
    assert "2.72.0" in message
    assert "unknown JSON field" in message
    assert "**Status:** Accepted" in path.read_text(encoding="utf-8")


def test_ein_unverwandter_gh_fehler_wird_nicht_zum_versionsproblem_umgedeutet(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    """Gegenstueck zum Versionsfall: Ein abgelaufenes Token, ein Netzwerkfehler oder ein nicht
    gefundener PR haben mit der `gh`-Version nichts zu tun. Wuerde der Hinweis unbedingt
    angehaengt, verschlechterte ausgerechnet diese Aenderung die Diagnostik - jemand
    aktualisiert `gh`, waehrend in Wahrheit die Anmeldung abgelaufen ist."""
    path = _write_spec(tmp_path, "0262")
    fake = FakeGh(
        failing={("gh", "pr", "view")},
        failure_stderr={("gh", "pr", "view"): ABGELAUFENES_TOKEN_STDERR},
    )

    with pytest.raises(gh_board.BoardError) as excinfo:
        gh_board.cmd_finalize(
            _board(gh_board, fake),
            repo_root=tmp_path,
            spec_number="0262",
            issue_number=262,
            pr_number=281,
        )

    message = str(excinfo.value)
    assert "2.72.0" not in message
    assert "Bad credentials (HTTP 401)" in message
    assert "**Status:** Accepted" in path.read_text(encoding="utf-8")


def test_finalize_ist_nach_dem_nachtragen_der_verknuepfung_wiederholbar(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    """Der Abbruch ist folgenlos: Nach dem Nachtragen der Verknuepfung am offenen PR laeuft
    derselbe Aufruf durch, ohne dass vorher etwas zurueckgenommen werden muesste."""
    path = _write_spec(tmp_path, "0262")
    fake = FakeGh(pull_requests={281: _pull_request(281, closing_issues=[])})
    board = _board(gh_board, fake)

    with pytest.raises(gh_board.BoardError):
        gh_board.cmd_finalize(
            board, repo_root=tmp_path, spec_number="0262", issue_number=262, pr_number=281
        )

    fake.pull_requests[281] = _pull_request(281, closing_issues=[_closing_ref(262)])

    result = gh_board.cmd_finalize(
        board, repo_root=tmp_path, spec_number="0262", issue_number=262, pr_number=281
    )

    assert result["pr_number"] == 281
    assert "**Status:** Implemented" in path.read_text(encoding="utf-8")


def test_cli_meldet_die_fehlende_verknuepfung_als_json_fehler(
    gh_board: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_spec(tmp_path, "0262")
    fake = FakeGh(pull_requests={281: _pull_request(281, closing_issues=[])})

    exit_code = gh_board.main(
        ["finalize", "--spec", "0262", "--pr-number", "281"],
        run=fake,
        repo_root=tmp_path,
        owner=OWNER,
    )

    assert exit_code == 1
    assert "2.72.0" in json.loads(capsys.readouterr().out)["error"]


def test_finalize_ohne_pr_nummer_prueft_die_verknuepfung_bewusst_nicht_selbst(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    """Charakterisierungstest (ADR 0046, Abschnitt 3b): Der Ausnahmepfad findet den PR ueber
    `closedByPullRequestsReferences` am Issue - dieselbe von GitHub gepflegte Verknuepfung aus
    der Gegenrichtung, die ohne sie leer bliebe. Eine eigene Pruefung waere dort sinnlos.

    Festgehalten, damit niemand die Pruefung "sauberkeitshalber" nach `get_pull_request()`
    verschiebt und damit den Ausnahmepfad bricht: Dieser gemergte PR traegt weder eine
    passende Closing-Referenz noch den Default-Branch - und wird trotzdem akzeptiert.
    """
    _write_spec(tmp_path, "0262")
    fake = FakeGh(
        closing_prs={262: [{"number": 281, "url": _pr_url(281)}]},
        pull_requests={
            281: _pull_request(281, state="MERGED", base_ref_name="release/0.24", closing_issues=[])
        },
    )

    result = gh_board.cmd_finalize(
        _board(gh_board, fake),
        repo_root=tmp_path,
        spec_number="0262",
        issue_number=262,
        pr_number=None,
    )

    assert result["pr_number"] == 281


def test_mehrdeutige_spec_nummer_bricht_ab_statt_still_die_erste_datei_zu_waehlen(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    """Zwei Dateien mit derselben Nummer duerfen nie stillschweigend aufgeloest werden -
    `finalize` wuerde sonst die falsche Spec-Datei umschreiben (Copilot-Review-Finding auf
    PR #267)."""
    first = _write_spec(tmp_path, "0262")
    second = tmp_path / "specs" / "features" / "0262-zweite-datei.md"
    second.write_text(first.read_text(encoding="utf-8"), encoding="utf-8")
    fake = FakeGh(pull_requests={281: _pull_request(281)})

    with pytest.raises(gh_board.BoardError) as excinfo:
        gh_board.cmd_finalize(
            _board(gh_board, fake),
            repo_root=tmp_path,
            spec_number="0262",
            issue_number=262,
            pr_number=281,
        )

    message = str(excinfo.value)
    assert "0262-beispiel.md" in message
    assert "0262-zweite-datei.md" in message
    assert "**Status:** Accepted" in first.read_text(encoding="utf-8")
    assert "**Status:** Accepted" in second.read_text(encoding="utf-8")


def test_finalize_findet_die_spec_ueber_die_nummer_nicht_ueber_den_titel(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    _write_spec(tmp_path, "0262")
    _write_spec(tmp_path, "0065")
    fake = FakeGh(pull_requests={281: _pull_request(281)})

    result = gh_board.cmd_finalize(
        _board(gh_board, fake),
        repo_root=tmp_path,
        spec_number="0065",
        issue_number=262,
        pr_number=281,
    )

    assert result["spec_number"] == "0065"
    assert "Implemented" in (tmp_path / "specs" / "features" / "0065-beispiel.md").read_text(
        encoding="utf-8"
    )
    assert "**Status:** Accepted" in (
        tmp_path / "specs" / "features" / "0262-beispiel.md"
    ).read_text(encoding="utf-8")


# -- CLI --------------------------------------------------------------------------------------


def test_cli_gibt_ein_einzelnes_json_objekt_aus(
    gh_board: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeGh()

    exit_code = gh_board.main(
        ["show-status", "--issue", "262"], run=fake, repo_root=tmp_path, owner=OWNER
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == {"issue_number": 262, "status": "Ready"}


def test_cli_meldet_fehler_als_json_mit_exit_code_1(
    gh_board: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeGh()

    exit_code = gh_board.main(
        ["set-status", "--issue", "262", "--status", "Erledigt"],
        run=fake,
        repo_root=tmp_path,
        owner=OWNER,
    )

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert "Erledigt" in payload["error"]
    assert set(payload) == {"error"}


def test_cli_set_priority_gibt_das_erwartete_json_zurueck(
    gh_board: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeGh(fields=_fields_mit_prioritaets_optionen())

    exit_code = gh_board.main(
        ["set-priority", "--issue", "262", "--priority", "Hoch"],
        run=fake,
        repo_root=tmp_path,
        owner=OWNER,
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == {
        "issue_number": 262,
        "priority": "Hoch",
        "changed": True,
    }


def test_cli_set_priority_lehnt_unbekannten_wert_mit_exit_code_1_ab(
    gh_board: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeGh()

    exit_code = gh_board.main(
        ["set-priority", "--issue", "262", "--priority", "Kritisch"],
        run=fake,
        repo_root=tmp_path,
        owner=OWNER,
    )

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert "Kritisch" in payload["error"]
    assert set(payload) == {"error"}


def test_cli_meldet_einen_fehlgeschlagenen_gh_aufruf_als_json(
    gh_board: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeGh(failing={("gh", "project", "item-list")})

    exit_code = gh_board.main(
        ["show-status", "--issue", "262"], run=fake, repo_root=tmp_path, owner=OWNER
    )

    assert exit_code == 1
    assert "error" in json.loads(capsys.readouterr().out)


def test_cli_finalize_nimmt_die_spec_nummer_als_issue_nummer(
    gh_board: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_spec(tmp_path, "0262")
    fake = FakeGh(pull_requests={281: _pull_request(281)})

    exit_code = gh_board.main(
        ["finalize", "--spec", "0262", "--pr-number", "281"],
        run=fake,
        repo_root=tmp_path,
        owner=OWNER,
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["issue_number"] == 262


def test_cli_finalize_ist_wiederholbar_und_meldet_zweimal_dasselbe(
    gh_board: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AK 6/7 auf der Ebene, die `ship-feature` tatsaechlich auswertet: zweimal Exit-Code 0 und
    identisches JSON auf stdout - kein `{"error": ...}`, keine Handbeurteilung."""
    _write_spec(tmp_path, "0262")
    fake = FakeGh(pull_requests={281: _pull_request(281)}, done_schliesst_das_issue=True)
    argv = ["finalize", "--spec", "0262", "--pr-number", "281"]

    erster_code = gh_board.main(argv, run=fake, repo_root=tmp_path, owner=OWNER)
    erste_ausgabe = capsys.readouterr().out
    zweiter_code = gh_board.main(argv, run=fake, repo_root=tmp_path, owner=OWNER)
    zweite_ausgabe = capsys.readouterr().out

    assert (erster_code, zweiter_code) == (0, 0)
    assert json.loads(zweite_ausgabe) == json.loads(erste_ausgabe)


def test_cli_finalize_erlaubt_eine_abweichende_issue_nummer_fuer_altspecs(
    gh_board: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_spec(tmp_path, "0065")
    fake = FakeGh(
        items=[
            {
                "id": "PVTI_240",
                "content": {"type": "Issue", "number": 240, "url": _issue_url(240)},
                "status": "Todo",
            }
        ],
        # Altspec: Issue-Nummer weicht von der Spec-Nummer ab, die Verknuepfung muss auf
        # genau dieses Issue zeigen (der Default der Hilfsfunktion referenziert 262).
        pull_requests={261: _pull_request(261, state="MERGED", closing_issues=[_closing_ref(240)])},
    )

    exit_code = gh_board.main(
        ["finalize", "--spec", "0065", "--issue", "240", "--pr-number", "261"],
        run=fake,
        repo_root=tmp_path,
        owner=OWNER,
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["issue_number"] == 240


@pytest.mark.parametrize(
    ("argv"),
    [
        ["create-issue", "--type", "idee", "--title", "T", "--body-file", "B"],
        ["set-body", "--issue", "262", "--body-file", "B"],
        ["set-status", "--issue", "262", "--status", "Todo"],
        ["set-priority", "--issue", "262", "--priority", "Hoch"],
        ["show-status", "--issue", "262"],
        ["finalize", "--spec", "0262"],
    ],
)
def test_cli_kennt_alle_in_den_skills_dokumentierten_befehle(
    gh_board: ModuleType, argv: list[str]
) -> None:
    """Die Aufrufformen aus .claude/skills/github-board/SKILL.md muessen parsebar bleiben."""
    assert gh_board.build_parser().parse_args(argv).command == argv[0]


def test_kein_gh_aufruf_verwendet_eine_shell(gh_board: ModuleType, tmp_path: Path) -> None:
    """Alle Aufrufe gehen als Argumentliste raus (ADR 0017, Abschnitt 5 - unveraendert gueltig)."""
    _write_spec(tmp_path, "0262")
    fake = FakeGh(pull_requests={281: _pull_request(281)})

    gh_board.main(
        ["finalize", "--spec", "0262", "--pr-number", "281"],
        run=fake,
        repo_root=tmp_path,
        owner=OWNER,
    )

    assert fake.calls
    for call in fake.calls:
        assert isinstance(call, list)
        assert call[0] == "gh"
        assert all(isinstance(arg, str) for arg in call)
