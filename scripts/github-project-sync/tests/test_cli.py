from __future__ import annotations

import json
from pathlib import Path

import pytest

from github_project_sync.cli import _discover_repo_root, _parse_resolutions, main
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


def _make_repo(tmp_path: Path, *, with_inbox: bool = False) -> Path:
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
    if with_inbox:
        inbox_dir = repo_root / "specs" / "inbox"
        inbox_dir.mkdir(parents=True)
        (inbox_dir / "0029-x.md").write_text(
            "# 0029 - Inbox-Titel\n\n**Typ:** Idee\n**Erfasst:** 2026-08-09\n"
            "**Status:** Unrefined\n\n## Rohtext\n\nFoo.\n",
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


def test_main_json_output_includes_inbox_branch(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = _make_repo(tmp_path, with_inbox=True)
    fake = FakeGhAdapter()

    exit_code = main(["--repo-root", str(repo_root)], gh_factory=lambda owner: fake)

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["inbox"][0]["number"] == "0029"
    assert output["inbox"][0]["classification"] == "created"
    assert output["orphaned_inbox"] == []
    assert output["supersede"] is None


def test_main_only_inbox_prefix_scopes_to_inbox_entry(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = _make_repo(tmp_path, with_inbox=True)
    fake = FakeGhAdapter()

    exit_code = main(
        ["--repo-root", str(repo_root), "--only", "inbox:0029"], gh_factory=lambda owner: fake
    )

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["specs"] == []
    assert len(output["inbox"]) == 1
    assert output["inbox"][0]["number"] == "0029"


def test_main_only_bare_number_still_scopes_to_feature(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = _make_repo(tmp_path, with_inbox=True)
    fake = FakeGhAdapter()

    exit_code = main(
        ["--repo-root", str(repo_root), "--only", "0031"], gh_factory=lambda owner: fake
    )

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert len(output["specs"]) == 1
    assert output["inbox"] == []


def test_main_supersede_inbox_reports_link_in_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = _make_repo(tmp_path, with_inbox=True)
    fake = FakeGhAdapter()
    # Ersten Lauf ohne --only, damit der Inbox-Eintrag einen State-Eintrag bekommt:
    main(["--repo-root", str(repo_root)], gh_factory=lambda owner: fake)
    capsys.readouterr()

    exit_code = main(
        [
            "--repo-root",
            str(repo_root),
            "--only",
            "0031",
            "--supersede-inbox",
            "0029",
        ],
        gh_factory=lambda owner: fake,
    )

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["supersede"]["inbox_number"] == "0029"


def test_main_returns_nonzero_on_supersede_inbox_without_state_entry(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = _make_repo(tmp_path)
    fake = FakeGhAdapter()

    exit_code = main(
        [
            "--repo-root",
            str(repo_root),
            "--only",
            "0031",
            "--supersede-inbox",
            "9999",
        ],
        gh_factory=lambda owner: fake,
    )

    assert exit_code != 0
    output = json.loads(capsys.readouterr().out)
    assert "error" in output
