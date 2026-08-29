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
        failing: set[tuple[str, ...]] | None = None,
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
        self.failing = failing or set()
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(args))
        for prefix in self.failing:
            if tuple(args[: len(prefix)]) == prefix:
                return _completed(returncode=1, stderr="fake gh failure")
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
        if head[:2] == ("gh", "issue") and head[2] in {"edit", "close", "reopen"}:
            return _completed("")
        if head == ("gh", "issue", "view"):
            number = int(args[3])
            return _completed(
                json.dumps({"closedByPullRequestsReferences": self.closing_prs.get(number, [])})
            )
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

    # -- Auswertungshilfen -------------------------------------------------------------------

    def calls_starting_with(self, *prefix: str) -> list[list[str]]:
        return [call for call in self.calls if tuple(call[: len(prefix)]) == prefix]

    def single_call(self, *prefix: str) -> list[str]:
        matches = self.calls_starting_with(*prefix)
        assert len(matches) == 1, f"erwartet genau ein {prefix!r}, gefunden: {matches}"
        return matches[0]


def _issue_url(number: int) -> str:
    return f"https://github.com/{OWNER}/photosort/issues/{number}"


def _pr_url(number: int) -> str:
    return f"https://github.com/{OWNER}/photosort/pull/{number}"


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


# -- finalize ---------------------------------------------------------------------------------


def test_finalize_schreibt_statuszeile_setzt_done_und_schliesst_das_issue(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    path = _write_spec(tmp_path, "0262")
    fake = FakeGh(pull_requests={281: {"state": "OPEN", "url": _pr_url(281)}})

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


def test_finalize_akzeptiert_einen_bereits_gemergten_pr(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    _write_spec(tmp_path, "0262")
    fake = FakeGh(pull_requests={281: {"state": "MERGED", "url": _pr_url(281)}})

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
    fake = FakeGh(pull_requests={281: {"state": "CLOSED", "url": _pr_url(281)}})

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
    path = _write_spec(tmp_path, "0262", status="Implemented ([PR #1](x))")
    fake = FakeGh(pull_requests={281: {"state": "OPEN", "url": _pr_url(281)}})

    with pytest.raises(gh_board.BoardError) as excinfo:
        gh_board.cmd_finalize(
            _board(gh_board, fake),
            repo_root=tmp_path,
            spec_number="0262",
            issue_number=262,
            pr_number=281,
        )

    assert "Accepted" in str(excinfo.value)
    assert "**Status:** Implemented ([PR #1](x))" in path.read_text(encoding="utf-8")


def test_finalize_meldet_eine_fehlende_spec_datei(gh_board: ModuleType, tmp_path: Path) -> None:
    (tmp_path / "specs" / "features").mkdir(parents=True)
    fake = FakeGh(pull_requests={281: {"state": "OPEN", "url": _pr_url(281)}})

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
        pull_requests={281: {"state": "MERGED", "url": _pr_url(281)}},
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
        pull_requests={281: {"state": "OPEN", "url": _pr_url(281)}},
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


def test_mehrdeutige_spec_nummer_bricht_ab_statt_still_die_erste_datei_zu_waehlen(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    """Zwei Dateien mit derselben Nummer duerfen nie stillschweigend aufgeloest werden -
    `finalize` wuerde sonst die falsche Spec-Datei umschreiben (Copilot-Review-Finding auf
    PR #267)."""
    first = _write_spec(tmp_path, "0262")
    second = tmp_path / "specs" / "features" / "0262-zweite-datei.md"
    second.write_text(first.read_text(encoding="utf-8"), encoding="utf-8")
    fake = FakeGh(pull_requests={281: {"state": "OPEN", "url": _pr_url(281)}})

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
    fake = FakeGh(pull_requests={281: {"state": "OPEN", "url": _pr_url(281)}})

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
    fake = FakeGh(pull_requests={281: {"state": "OPEN", "url": _pr_url(281)}})

    exit_code = gh_board.main(
        ["finalize", "--spec", "0262", "--pr-number", "281"],
        run=fake,
        repo_root=tmp_path,
        owner=OWNER,
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["issue_number"] == 262


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
        pull_requests={261: {"state": "MERGED", "url": _pr_url(261)}},
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
    fake = FakeGh(pull_requests={281: {"state": "OPEN", "url": _pr_url(281)}})

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
