from __future__ import annotations

from pathlib import Path

import pytest

from github_project_sync.spec_parser import (
    ParsedSpec,
    SpecParseError,
    parse_spec_file,
    parse_spec_text,
    replace_content_zone,
    validate_spec_number,
)

SAMPLE = """# 0031 - Zwei-Wege-Sync Feature-Specs ↔ GitHub-Projekt

**Status:** Accepted
**Erstellt:** 2026-08-09
**Bezug:** [`inbox/0011-...md`](../inbox/0011-...md)

## Ziel

Status und Priorität aller Feature-Specs sollen sichtbar sein.

## User Story

Als Daniel möchte ich ...
"""


def test_parse_spec_text_extracts_number_title_status() -> None:
    parsed = parse_spec_text(SAMPLE)

    assert parsed.number == "0031"
    assert parsed.title == "Zwei-Wege-Sync Feature-Specs ↔ GitHub-Projekt"
    assert parsed.status == "Accepted"


def test_parse_spec_text_extracts_content_zone_starting_at_first_h2() -> None:
    parsed = parse_spec_text(SAMPLE)

    assert parsed.content_zone.startswith("## Ziel")
    assert "## User Story" in parsed.content_zone
    assert "**Status:**" not in parsed.content_zone


def test_parse_spec_text_header_keeps_metadata_block() -> None:
    parsed = parse_spec_text(SAMPLE)

    assert parsed.header.startswith("# 0031 -")
    assert "**Status:** Accepted" in parsed.header
    assert "## Ziel" not in parsed.header


def test_parse_spec_text_without_content_zone_raises() -> None:
    text = "# 0031 - Titel\n\n**Status:** Accepted\n**Erstellt:** 2026-08-09\n**Bezug:** x\n"

    with pytest.raises(SpecParseError):
        parse_spec_text(text)


def test_parse_spec_text_without_h1_raises() -> None:
    with pytest.raises(SpecParseError):
        parse_spec_text("kein Titel hier\n\n## Ziel\n\nfoo\n")


def test_parse_spec_text_without_status_raises() -> None:
    text = "# 0031 - Titel\n\n**Erstellt:** 2026-08-09\n**Bezug:** x\n\n## Ziel\n\nfoo\n"

    with pytest.raises(SpecParseError):
        parse_spec_text(text)


def test_parse_spec_file_reads_and_validates_filename_number(tmp_path: Path) -> None:
    spec_path = tmp_path / "0031-zweiwege-sync.md"
    spec_path.write_text(SAMPLE, encoding="utf-8")

    parsed = parse_spec_file(spec_path)

    assert parsed.number == "0031"


def test_parse_spec_file_rejects_filename_number_mismatch(tmp_path: Path) -> None:
    spec_path = tmp_path / "0099-mismatch.md"
    spec_path.write_text(SAMPLE, encoding="utf-8")

    with pytest.raises(SpecParseError):
        parse_spec_file(spec_path)


@pytest.mark.parametrize("value", ["0031", "0000", "9999"])
def test_validate_spec_number_accepts_four_digits(value: str) -> None:
    assert validate_spec_number(value) == value


@pytest.mark.parametrize("value", ["31", "00031", "abcd", "003a", "", "../0031", "0031/../etc"])
def test_validate_spec_number_rejects_everything_else(value: str) -> None:
    with pytest.raises(ValueError):
        validate_spec_number(value)


def test_replace_content_zone_keeps_header_untouched() -> None:
    new_zone = "## Ziel\n\nNeuer Text aus dem Issue.\n"

    result = replace_content_zone(SAMPLE, new_zone)

    assert result.startswith("# 0031 -")
    assert "**Status:** Accepted" in result
    assert "Neuer Text aus dem Issue." in result
    assert "Als Daniel" not in result


def test_replace_content_zone_ignores_metadata_edits_in_new_zone() -> None:
    # Ein versehentlich im Issue mitgeaenderter Metadaten-Block darf keine Wirkung haben -
    # replace_content_zone ersetzt ausschliesslich den Teil ab "## ", der Header bleibt die
    # lokale Fassung (ADR 0017, Abschnitt 4).
    new_zone = "## Ziel\n\nGeaendert.\n"

    result = replace_content_zone(SAMPLE, new_zone)

    assert result.count("**Status:**") == 1
    assert "**Status:** Accepted" in result


def test_parsed_spec_is_frozen_dataclass() -> None:
    import dataclasses

    parsed = parse_spec_text(SAMPLE)
    assert isinstance(parsed, ParsedSpec)
    with pytest.raises(dataclasses.FrozenInstanceError):
        parsed.status = "Proposed"  # type: ignore[misc]
