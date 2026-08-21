from __future__ import annotations

from pathlib import Path

import pytest

from github_project_sync.inbox_parser import (
    VALID_INBOX_STATUSES,
    VALID_INBOX_TYPES,
    ParsedInboxEntry,
    parse_inbox_file,
    parse_inbox_text,
)
from github_project_sync.spec_parser import SpecParseError

SAMPLE = """# 0029 - release-please Action schlägt manchmal fehl

**Typ:** Bug (vermeintlich)
**Erfasst:** 2026-08-20
**Status:** Unrefined

## Rohtext

Manchmal schlägt die release-please Action fehl. Herausfinden was das Problem ist und fixen.
"""


def test_parse_inbox_text_extracts_number_title_status() -> None:
    parsed = parse_inbox_text(SAMPLE)

    assert parsed.number == "0029"
    assert parsed.title == "release-please Action schlägt manchmal fehl"
    assert parsed.status == "Unrefined"


def test_parse_inbox_text_extracts_typ() -> None:
    parsed = parse_inbox_text(SAMPLE)

    assert parsed.typ == "Bug (vermeintlich)"


def test_parse_inbox_text_extracts_content_zone_starting_at_rohtext() -> None:
    parsed = parse_inbox_text(SAMPLE)

    assert parsed.content_zone.startswith("## Rohtext")
    assert "release-please Action fehl" in parsed.content_zone
    assert "**Status:**" not in parsed.content_zone
    assert "**Typ:**" not in parsed.content_zone


def test_parse_inbox_text_header_keeps_metadata_block() -> None:
    parsed = parse_inbox_text(SAMPLE)

    assert parsed.header.startswith("# 0029 -")
    assert "**Typ:** Bug (vermeintlich)" in parsed.header
    assert "**Status:** Unrefined" in parsed.header
    assert "## Rohtext" not in parsed.header


def test_parse_inbox_text_no_bezug_field_required() -> None:
    # Inbox-Eintraege haben bewusst kein **Bezug:**-Feld (anders als Feature-Specs) - das
    # Parsing darf das nicht vermissen/verlangen (ADR 0030, Abschnitt 8).
    parsed = parse_inbox_text(SAMPLE)

    assert "Bezug" not in parsed.header


def test_parse_inbox_text_without_typ_raises() -> None:
    text = (
        "# 0029 - Titel\n\n**Erfasst:** 2026-08-20\n**Status:** Unrefined\n\n"
        "## Rohtext\n\nfoo\n"
    )

    with pytest.raises(SpecParseError):
        parse_inbox_text(text)


def test_parse_inbox_text_without_status_raises() -> None:
    text = "# 0029 - Titel\n\n**Typ:** Idee\n**Erfasst:** 2026-08-20\n\n## Rohtext\n\nfoo\n"

    with pytest.raises(SpecParseError):
        parse_inbox_text(text)


def test_parse_inbox_text_without_content_zone_raises() -> None:
    text = "# 0029 - Titel\n\n**Typ:** Idee\n**Erfasst:** 2026-08-20\n**Status:** Unrefined\n"

    with pytest.raises(SpecParseError):
        parse_inbox_text(text)


def test_parse_inbox_text_without_h1_raises() -> None:
    with pytest.raises(SpecParseError):
        parse_inbox_text("kein Titel hier\n\n## Rohtext\n\nfoo\n")


def test_parse_inbox_text_does_not_validate_typ_value_itself() -> None:
    # Semantische Validierung (unbekannter Typ -> nicht-fataler Warnfall) passiert in sync.py,
    # analog zum bestehenden Muster fuer unbekannten Feature-Spec-Status (spec_parser.py
    # validiert das Status-Enum ebenfalls nicht selbst) - inbox_parser.py extrahiert nur.
    text = (
        "# 0029 - Titel\n\n**Typ:** Voellig unbekannt\n**Erfasst:** 2026-08-20\n"
        "**Status:** Unrefined\n\n## Rohtext\n\nfoo\n"
    )

    parsed = parse_inbox_text(text)

    assert parsed.typ == "Voellig unbekannt"


def test_parse_inbox_text_does_not_validate_status_value_itself() -> None:
    text = (
        "# 0029 - Titel\n\n**Typ:** Idee\n**Erfasst:** 2026-08-20\n"
        "**Status:** VoelligUnbekannt\n\n## Rohtext\n\nfoo\n"
    )

    parsed = parse_inbox_text(text)

    assert parsed.status == "VoelligUnbekannt"


def test_valid_inbox_statuses_and_types_constants() -> None:
    assert VALID_INBOX_STATUSES == frozenset({"Unrefined"})
    assert VALID_INBOX_TYPES == frozenset({"Idee", "Bug (vermeintlich)"})


def test_parse_inbox_file_reads_and_validates_filename_number(tmp_path: Path) -> None:
    entry_path = tmp_path / "0029-release-please.md"
    entry_path.write_text(SAMPLE, encoding="utf-8")

    parsed = parse_inbox_file(entry_path)

    assert parsed.number == "0029"


def test_parse_inbox_file_rejects_filename_number_mismatch(tmp_path: Path) -> None:
    entry_path = tmp_path / "0099-mismatch.md"
    entry_path.write_text(SAMPLE, encoding="utf-8")

    with pytest.raises(SpecParseError):
        parse_inbox_file(entry_path)


def test_parsed_inbox_entry_is_frozen_dataclass() -> None:
    import dataclasses

    parsed = parse_inbox_text(SAMPLE)
    assert isinstance(parsed, ParsedInboxEntry)
    with pytest.raises(dataclasses.FrozenInstanceError):
        parsed.status = "Proposed"  # type: ignore[misc]


def test_parse_inbox_text_reuses_spec_parser_core_via_full_text_roundtrip() -> None:
    # Wiederverwendungs-Nachweis: full_text/replace_content_zone (aus spec_parser.py) funktioniert
    # unveraendert auch fuer Inbox-Texte, da inbox_parser.py dieselbe Kernstruktur nutzt.
    from github_project_sync.spec_parser import replace_content_zone

    parsed = parse_inbox_text(SAMPLE)
    updated = replace_content_zone(parsed.full_text, "## Rohtext\n\nNeuer Text.\n")

    assert "Neuer Text." in updated
    assert "**Status:** Unrefined" in updated
