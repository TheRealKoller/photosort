from __future__ import annotations

from pathlib import Path

import pytest

from github_project_sync.spec_parser import (
    ParsedSpec,
    SpecParseError,
    parse_spec_file,
    parse_spec_text,
    replace_content_zone,
    set_status_line,
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


def _spec_with_status_line(status_line: str) -> str:
    return (
        "# 0099 - Titel\n\n"
        f"**Status:** {status_line}\n"
        "**Erstellt:** 2026-08-09\n"
        "**Bezug:** x\n\n"
        "## Ziel\n\nfoo\n"
    )


# Regressionstest fuer einen echten Bug (zweiter manueller Sync-Lauf gegen echtes GitHub nach
# Merge von PR #117): _STATUS_RE uebernahm bisher die komplette Zeile hinter "**Status:**" statt
# nur das fuehrende Enum-Schluesselwort - dadurch scheiterte sync.py's Status-Validierung fuer
# praktisch den gesamten Bestand bereits abgeschlossener Specs. Alle Varianten unten sind reale,
# per "grep -h '^\*\*Status:\*\*' specs/features/*.md" im Repo gefundene Zeilen (nicht nur
# synthetische Faelle), siehe Sync-Lauf-Fehlermeldung fuer Spec 0003.
_PR = "https://github.com/TheRealKoller/photosort/pull"  # kuerzt die Fixtures unten ab


@pytest.mark.parametrize(
    ("status_line", "expected"),
    [
        ("Accepted", "Accepted"),
        ("Proposed", "Proposed"),
        ("Implemented", "Implemented"),
        (f"Implemented ([PR #100]({_PR}/100))", "Implemented"),
        (f"Implemented ([PR #101]({_PR}/101), 2026-08-17)", "Implemented"),
        (f"Implemented — AK1–AK9 umgesetzt in [PR #40]({_PR}/40)", "Implemented"),
        (
            f"Implemented — AK1–AK12 umgesetzt in [PR #34]({_PR}/34) "
            f"(AK13/Copilot-Review-Bedingung bereits zuvor mit [PR #32]({_PR}/32), "
            "gemerged 2026-08-07, umgesetzt).",
            "Implemented",
        ),
        (
            "Superseded, abgelöst durch "
            f"[`0037`](./0037-gateführte-bewertungs-pipeline-mit-backfill.md) ([PR #6]({_PR}/6))",
            "Superseded",
        ),
        (
            "Superseded, abgelöst durch "
            f"[`0037`](./0037-gateführte-bewertungs-pipeline-mit-backfill.md) ([PR #51]({_PR}/51))",
            "Superseded",
        ),
    ],
)
def test_parse_spec_text_status_extracts_only_leading_keyword(
    status_line: str, expected: str
) -> None:
    parsed = parse_spec_text(_spec_with_status_line(status_line))

    assert parsed.status == expected


# -- set_status_line() (Spec 0060 / ADR 0037, Abschnitt 5): Merge-Erkennung schreibt den finalen
# "Implemented ([PR #NNN](url))"-Freitext in den Header, analog zu replace_content_zone() aber
# fuer den Header statt die Inhalts-Zone. ------------------------------------------------------


def test_set_status_line_replaces_status_keyword_only() -> None:
    result = set_status_line(SAMPLE, "Implemented")

    assert "**Status:** Implemented\n" in result
    assert "**Status:** Accepted" not in result


def test_set_status_line_accepts_full_freetext_value_with_pr_link() -> None:
    new_status = "Implemented ([PR #101](https://github.com/TheRealKoller/photosort/pull/101))"

    result = set_status_line(SAMPLE, new_status)

    assert f"**Status:** {new_status}\n" in result


def test_set_status_line_keeps_everything_else_untouched() -> None:
    result = set_status_line(SAMPLE, "Implemented")

    assert result.startswith("# 0031 -")
    assert "**Erstellt:** 2026-08-09" in result
    assert "## Ziel" in result
    assert "Als Daniel möchte ich ..." in result


def test_set_status_line_raises_when_no_status_field_found() -> None:
    text = "# 0031 - Titel\n\n**Erstellt:** 2026-08-09\n\n## Ziel\n\nfoo\n"

    with pytest.raises(SpecParseError):
        set_status_line(text, "Implemented")


def test_set_status_line_ignores_status_occurrence_in_content_zone() -> None:
    # Regressionstest (test-engineer, Testkonzept "Erweiterung fuer ADR 0037"): diese Spec
    # handelt selbst ueber das "**Status:**"-Feld, ihre eigene Inhalts-Zone enthaelt deshalb
    # naheliegenderweise weitere Vorkommen einer Zeile, die (wie der echte Header) mit
    # "**Status:**" beginnt (z.B. als zitiertes Beispiel eines Metadaten-Blocks) -
    # set_status_line() darf ausschliesslich die erste, tatsaechliche Header-Zeile ersetzen.
    text = (
        "# 0060 - Status-Lebenszyklus\n\n"
        "**Status:** Accepted\n"
        "**Erstellt:** 2026-08-27\n\n"
        "## Beispiel\n\n"
        "Ein Metadaten-Block sieht z.B. so aus:\n\n"
        "**Status:** Implemented ([PR #101](https://example.com/pull/101))\n"
    )

    result = set_status_line(text, "Implemented ([PR #200](https://example.com/pull/200))")

    header, _, content_zone = result.partition("## Beispiel")
    assert header.count("**Status:**") == 1
    assert "**Status:** Implemented ([PR #200](https://example.com/pull/200))" in header
    # Die Inhalts-Zone bleibt unangetastet - inkl. ihres eigenen "**Status:**"-Vorkommens, das
    # NICHT auf den neuen Wert umgeschrieben werden darf:
    assert content_zone.count("**Status:**") == 1
    assert "**Status:** Implemented ([PR #101](https://example.com/pull/101))" in content_zone


def test_parsed_spec_is_frozen_dataclass() -> None:
    import dataclasses

    parsed = parse_spec_text(SAMPLE)
    assert isinstance(parsed, ParsedSpec)
    with pytest.raises(dataclasses.FrozenInstanceError):
        parsed.status = "Proposed"  # type: ignore[misc]
