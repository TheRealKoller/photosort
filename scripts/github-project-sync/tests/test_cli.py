from __future__ import annotations

import json
from pathlib import Path

import pytest

from github_project_sync.cli import _discover_repo_root, _parse_issue_only, _parse_resolutions, main
from github_project_sync.sync import SyncError
from tests.fakes import FakeGhAdapter


def test_parse_resolutions_valid() -> None:
    resolutions = _parse_resolutions(["0031=keep_spec", "0032=keep_issue"])

    assert resolutions == {"0031": "keep_spec", "0032": "keep_issue"}


def test_parse_resolutions_rejects_missing_equals_sign() -> None:
    with pytest.raises(SyncError):
        _parse_resolutions(["0031-keep_spec"])


def test_parse_resolutions_rejects_unknown_value() -> None:
    with pytest.raises(SyncError):
        _parse_resolutions(["0031=delete_everything"])


def test_parse_resolutions_rejects_invalid_spec_number() -> None:
    with pytest.raises(ValueError):
        _parse_resolutions(["31=keep_spec"])


def test_parse_issue_only_extracts_number() -> None:
    assert _parse_issue_only("issue:215") == 215


def test_parse_issue_only_rejects_leading_zero() -> None:
    with pytest.raises(SyncError):
        _parse_issue_only("issue:0215")


def test_parse_issue_only_rejects_non_digit() -> None:
    with pytest.raises(SyncError):
        _parse_issue_only("issue:abc")


def test_discover_repo_root_finds_ancestor_with_specs_and_git(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / "specs").mkdir(parents=True)
    (repo_root / ".git").mkdir()
    nested = repo_root / "scripts" / "github-project-sync"
    nested.mkdir(parents=True)

    found = _discover_repo_root(nested)

    assert found == repo_root


def test_discover_repo_root_raises_when_not_found(tmp_path: Path) -> None:
    with pytest.raises(SyncError):
        _discover_repo_root(tmp_path)


def _make_repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    (repo_root / ".git").mkdir(parents=True)
    features_dir = repo_root / "specs" / "features"
    features_dir.mkdir(parents=True)
    (features_dir / "0031-x.md").write_text(
        "# 0031 - Titel\n\n**Status:** Accepted\n**Erstellt:** 2026-08-09\n"
        "**Bezug:** x\n\n## Ziel\n\nFoo.\n",
        encoding="utf-8",
    )
    (repo_root / "specs" / "roadmap.md").write_text(
        "# Roadmap\n\n## Status auf einen Blick\n\n### Offen — Hoch\n\nKeine offenen Einträge.\n\n"
        "### Offen — Mittel\n\nKeine offenen Einträge.\n\n"
        "### Offen — Niedrig\n\n| Spec | Titel | Status |\n|---|---|---|\n"
        "| [0031](./features/0031-x.md) | Titel | Accepted |\n",
        encoding="utf-8",
    )
    return repo_root


def test_main_runs_sync_and_prints_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo_root = _make_repo(tmp_path)
    fake = FakeGhAdapter()

    exit_code = main(["--repo-root", str(repo_root)], gh_factory=lambda owner: fake)

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["specs"][0]["number"] == "0031"
    assert output["specs"][0]["classification"] == "created"
    assert output["adopted"] is None


def test_main_returns_nonzero_on_auth_scope_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = _make_repo(tmp_path)
    fake = FakeGhAdapter(auth_ok=False)

    exit_code = main(["--repo-root", str(repo_root)], gh_factory=lambda owner: fake)

    assert exit_code != 0
    output = json.loads(capsys.readouterr().out)
    assert "error" in output


def test_main_returns_nonzero_on_unknown_only_spec(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = _make_repo(tmp_path)
    fake = FakeGhAdapter()

    exit_code = main(
        ["--repo-root", str(repo_root), "--only", "9999"], gh_factory=lambda owner: fake
    )

    assert exit_code != 0
    output = json.loads(capsys.readouterr().out)
    assert "error" in output


def test_main_returns_nonzero_on_old_inbox_only_prefix(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # --only inbox:NNNN wurde mit Spec 0059 vollstaendig entfernt - muss mit einer praezisen
    # Fehlermeldung (nicht der generischen "Ungueltige Spec-Nummer") abgelehnt werden.
    repo_root = _make_repo(tmp_path)
    fake = FakeGhAdapter()

    exit_code = main(
        ["--repo-root", str(repo_root), "--only", "inbox:0004"], gh_factory=lambda owner: fake
    )

    assert exit_code != 0
    output = json.loads(capsys.readouterr().out)
    assert "error" in output
    assert "entfernt" in output["error"]
    assert "issue:NNN" in output["error"]


def test_main_returns_json_error_on_removed_supersede_inbox_flag(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # --supersede-inbox wurde mit Spec 0059 entfernt - anders als ein schlicht aus dem Parser
    # entferntes Flag (das auf argparses generisches stderr/Exit-Code-2-Verhalten faellt) bleibt
    # es hier bewusst registriert, damit ein alter Aufruf dieselbe {"error": ...}-JSON-Konvention
    # auf stdout bekommt wie jeder andere abgelehnte Fall.
    repo_root = _make_repo(tmp_path)
    fake = FakeGhAdapter()

    exit_code = main(
        ["--repo-root", str(repo_root), "--only", "0031", "--supersede-inbox", "0004"],
        gh_factory=lambda owner: fake,
    )

    assert exit_code != 0
    output = json.loads(capsys.readouterr().out)
    assert "error" in output
    assert "entfernt" in output["error"]
    assert "adopt-issue" in output["error"]


def test_main_passes_resolve_argument_through(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = _make_repo(tmp_path)
    fake = FakeGhAdapter()

    exit_code = main(
        ["--repo-root", str(repo_root), "--resolve", "0031=keep_spec"],
        gh_factory=lambda owner: fake,
    )

    assert exit_code == 0


# -- --create-issue (Spec 0059) -----------------------------------------------------------


def test_main_create_issue_prints_issue_number(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = _make_repo(tmp_path)
    fake = FakeGhAdapter()
    body_file = tmp_path / "body.md"
    body_file.write_text("Rohtext der Idee.", encoding="utf-8")

    exit_code = main(
        [
            "--repo-root",
            str(repo_root),
            "--create-issue",
            "--type",
            "idee",
            "--title",
            "Neue Idee",
            "--body-file",
            str(body_file),
        ],
        gh_factory=lambda owner: fake,
    )

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["issue_number"] == 1
    assert fake.issue(1).title == "Neue Idee"
    assert fake.issue(1).body == "Rohtext der Idee."


def test_main_create_issue_requires_type_title_and_body_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = _make_repo(tmp_path)
    fake = FakeGhAdapter()

    exit_code = main(
        ["--repo-root", str(repo_root), "--create-issue", "--title", "Nur Titel"],
        gh_factory=lambda owner: fake,
    )

    assert exit_code != 0
    output = json.loads(capsys.readouterr().out)
    assert "error" in output


# -- --only issue:NNN (Story-Update + --show-status) --------------------------------------


def _make_repo_with_story(tmp_path: Path) -> tuple[Path, FakeGhAdapter]:
    repo_root = _make_repo(tmp_path)
    fake = FakeGhAdapter()
    exit_code = main(
        [
            "--repo-root",
            str(repo_root),
            "--create-issue",
            "--type",
            "idee",
            "--title",
            "Story-Titel",
            "--body-file",
            str(_write_body(tmp_path, "Rohtext.")),
        ],
        gh_factory=lambda owner: fake,
    )
    assert exit_code == 0
    return repo_root, fake


def _write_body(tmp_path: Path, text: str) -> Path:
    path = tmp_path / f"body-{text[:4]}.md"
    path.write_text(text, encoding="utf-8")
    return path


def test_main_only_issue_updates_status_and_body(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root, fake = _make_repo_with_story(tmp_path)
    capsys.readouterr()

    exit_code = main(
        [
            "--repo-root",
            str(repo_root),
            "--only",
            "issue:1",
            "--status",
            "Ready",
            "--body-file",
            str(_write_body(tmp_path, "## Ziel\n\nNeu.\n")),
        ],
        gh_factory=lambda owner: fake,
    )

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["issue_number"] == 1
    assert output["status"] == "Ready"
    assert fake.issue(1).body == "## Ziel\n\nNeu.\n"


def test_main_only_issue_show_status_is_read_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root, fake = _make_repo_with_story(tmp_path)
    capsys.readouterr()

    exit_code = main(
        ["--repo-root", str(repo_root), "--only", "issue:1", "--show-status"],
        gh_factory=lambda owner: fake,
    )

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "Unrefined"


def test_main_show_status_without_only_issue_scope_is_an_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = _make_repo(tmp_path)
    fake = FakeGhAdapter()

    exit_code = main(
        ["--repo-root", str(repo_root), "--show-status"], gh_factory=lambda owner: fake
    )

    assert exit_code != 0
    output = json.loads(capsys.readouterr().out)
    assert "error" in output


def test_main_only_issue_unknown_number_is_an_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = _make_repo(tmp_path)
    fake = FakeGhAdapter()

    exit_code = main(
        ["--repo-root", str(repo_root), "--only", "issue:999", "--show-status"],
        gh_factory=lambda owner: fake,
    )

    assert exit_code != 0
    output = json.loads(capsys.readouterr().out)
    assert "error" in output


# -- --adopt-issue (Story -> Feature-Spec-Uebergang) ---------------------------------------


def test_main_adopt_issue_reports_adopted_result(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root, fake = _make_repo_with_story(tmp_path)
    capsys.readouterr()

    exit_code = main(
        ["--repo-root", str(repo_root), "--only", "0031", "--adopt-issue", "1"],
        gh_factory=lambda owner: fake,
    )

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["adopted"]["spec_number"] == "0031"
    assert output["adopted"]["issue_number"] == 1
    assert output["specs"][0]["issue_number"] == 1


def test_main_adopt_issue_without_only_is_an_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root, fake = _make_repo_with_story(tmp_path)
    capsys.readouterr()

    exit_code = main(
        ["--repo-root", str(repo_root), "--adopt-issue", "1"], gh_factory=lambda owner: fake
    )

    assert exit_code != 0
    output = json.loads(capsys.readouterr().out)
    assert "error" in output


# -- --runtime-status/--pr-number (Spec 0060 / ADR 0037, Abschnitt 3/4) -------------------------


def _sync_once(repo_root: Path, fake: FakeGhAdapter) -> None:
    exit_code = main(["--repo-root", str(repo_root)], gh_factory=lambda owner: fake)
    assert exit_code == 0


def test_main_runtime_status_sets_in_progress_override(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = _make_repo(tmp_path)
    fake = FakeGhAdapter()
    _sync_once(repo_root, fake)
    capsys.readouterr()

    exit_code = main(
        ["--repo-root", str(repo_root), "--only", "0031", "--runtime-status", "In Progress"],
        gh_factory=lambda owner: fake,
    )

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output == {"spec_number": "0031", "runtime_status": "In Progress", "pr_number": None}


def test_main_runtime_status_review_requires_pr_number(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = _make_repo(tmp_path)
    fake = FakeGhAdapter()
    _sync_once(repo_root, fake)
    capsys.readouterr()

    exit_code = main(
        ["--repo-root", str(repo_root), "--only", "0031", "--runtime-status", "Review"],
        gh_factory=lambda owner: fake,
    )

    assert exit_code != 0
    output = json.loads(capsys.readouterr().out)
    assert "error" in output


def test_main_runtime_status_review_with_pr_number_succeeds(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = _make_repo(tmp_path)
    fake = FakeGhAdapter()
    _sync_once(repo_root, fake)
    capsys.readouterr()

    exit_code = main(
        [
            "--repo-root",
            str(repo_root),
            "--only",
            "0031",
            "--runtime-status",
            "Review",
            "--pr-number",
            "101",
        ],
        gh_factory=lambda owner: fake,
    )

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output == {"spec_number": "0031", "runtime_status": "Review", "pr_number": 101}


def test_main_runtime_status_requires_bare_feature_scope_not_issue_scope(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root, fake = _make_repo_with_story(tmp_path)
    capsys.readouterr()

    exit_code = main(
        ["--repo-root", str(repo_root), "--only", "issue:1", "--runtime-status", "In Progress"],
        gh_factory=lambda owner: fake,
    )

    assert exit_code != 0
    output = json.loads(capsys.readouterr().out)
    assert "error" in output


def test_main_runtime_status_requires_only_flag(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = _make_repo(tmp_path)
    fake = FakeGhAdapter()

    exit_code = main(
        ["--repo-root", str(repo_root), "--runtime-status", "In Progress"],
        gh_factory=lambda owner: fake,
    )

    assert exit_code != 0
    output = json.loads(capsys.readouterr().out)
    assert "error" in output


def test_main_runtime_status_rejects_unknown_value(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = _make_repo(tmp_path)
    fake = FakeGhAdapter()

    with pytest.raises(SystemExit):
        main(
            ["--repo-root", str(repo_root), "--only", "0031", "--runtime-status", "Done"],
            gh_factory=lambda owner: fake,
        )


def test_main_pr_number_without_runtime_status_is_an_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = _make_repo(tmp_path)
    fake = FakeGhAdapter()

    exit_code = main(
        ["--repo-root", str(repo_root), "--only", "0031", "--pr-number", "101"],
        gh_factory=lambda owner: fake,
    )

    assert exit_code != 0
    output = json.loads(capsys.readouterr().out)
    assert "error" in output


def test_main_run_sync_output_includes_finalized_from_pr_key(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = _make_repo(tmp_path)
    fake = FakeGhAdapter()

    exit_code = main(["--repo-root", str(repo_root)], gh_factory=lambda owner: fake)

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["specs"][0]["finalized_from_pr"] is None
