from __future__ import annotations

from github_project_sync.issue_body import (
    build_inbox_issue_body,
    build_issue_body,
    extract_content_zone_from_issue_body,
    parse_inbox_marker,
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


# -- Inbox-Marker (photosort-inbox) -----------------------------------------------------
# Getrennte, jeweils hart auf den Entitaets-String geankerte Regexe (photosort-spec vs.
# photosort-inbox) statt einer gemeinsamen, nur die Zahl extrahierenden Funktion - siehe
# Security-Abschnitt der Spec 0052 (Bedrohung 1: Nummernkreis-Kollision zwischen Inbox und
# Features ist real, z.B. inbox/0004 und features/0004 existieren gleichzeitig).


def test_build_inbox_issue_body_starts_with_inbox_marker_line() -> None:
    body = build_inbox_issue_body("0029", "## Rohtext\n\nfoo\n")

    assert body.startswith("<!-- photosort-inbox: 0029 -->\n")
    assert "## Rohtext" in body


def test_parse_inbox_marker_extracts_number() -> None:
    body = "<!-- photosort-inbox: 0029 -->\n\n## Rohtext\n\nfoo\n"

    assert parse_inbox_marker(body) == "0029"


def test_parse_inbox_marker_returns_none_when_missing() -> None:
    assert parse_inbox_marker("## Rohtext\n\nfoo\n") is None


def test_parse_inbox_marker_returns_none_when_malformed() -> None:
    assert parse_inbox_marker("<!-- photosort-inbox: abcd -->\n\n## Rohtext\n") is None


def test_round_trip_build_and_extract_inbox() -> None:
    content_zone = "## Rohtext\n\nfoo\n"

    body = build_inbox_issue_body("0029", content_zone)

    assert extract_content_zone_from_issue_body(body) == content_zone


def test_parse_marker_rejects_inbox_marked_body_cross_namespace() -> None:
    # Ein Issue mit photosort-inbox-Marker darf vom Feature-Sync-Pfad (parse_marker) nicht als
    # Spec-Marker interpretiert werden, auch wenn die Nummer korrekt ist.
    body = "<!-- photosort-inbox: 0004 -->\n\n## Rohtext\n\nfoo\n"

    assert parse_marker(body) is None


def test_parse_inbox_marker_rejects_spec_marked_body_cross_namespace() -> None:
    # Umgekehrt: ein Issue mit photosort-spec-Marker darf vom Inbox-Sync-Pfad (parse_inbox_marker)
    # nicht als Inbox-Marker interpretiert werden, auch wenn die Nummer korrekt ist (reale
    # Kollision: inbox/0004 und features/0004 existieren gleichzeitig im Repo).
    body = "<!-- photosort-spec: 0004 -->\n\n## Ziel\n\nfoo\n"

    assert parse_inbox_marker(body) is None
