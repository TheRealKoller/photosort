from __future__ import annotations

from github_project_sync.issue_body import (
    build_issue_body,
    extract_content_zone_from_issue_body,
    parse_marker,
)


def test_build_issue_body_starts_with_marker_line() -> None:
    body = build_issue_body("0031", "## Ziel\n\nfoo\n")

    assert body.startswith("<!-- photosort-spec: 0031 -->\n")
    assert "## Ziel" in body


def test_parse_marker_extracts_spec_number() -> None:
    body = "<!-- photosort-spec: 0031 -->\n\n## Ziel\n\nfoo\n"

    assert parse_marker(body) == "0031"


def test_parse_marker_returns_none_when_missing() -> None:
    assert parse_marker("## Ziel\n\nfoo\n") is None


def test_parse_marker_returns_none_when_malformed() -> None:
    assert parse_marker("<!-- photosort-spec: abcd -->\n\n## Ziel\n") is None


def test_extract_content_zone_strips_marker_line_and_leading_blank_lines() -> None:
    body = "<!-- photosort-spec: 0031 -->\n\n\n## Ziel\n\nfoo\n"

    assert extract_content_zone_from_issue_body(body) == "## Ziel\n\nfoo\n"


def test_round_trip_build_and_extract() -> None:
    content_zone = "## Ziel\n\nfoo\n\n## User Story\n\nbar\n"

    body = build_issue_body("0031", content_zone)

    assert extract_content_zone_from_issue_body(body) == content_zone
