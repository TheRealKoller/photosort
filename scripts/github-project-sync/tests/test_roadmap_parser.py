from __future__ import annotations

from github_project_sync.roadmap_parser import parse_roadmap_priorities

ROADMAP = """# Roadmap

Lebendes Dokument.

## Status auf einen Blick

Sortiert nach Dringlichkeit.

### Offen — Hoch

Keine offenen Einträge.

### Offen — Mittel

| Spec | Titel | Status |
|---|---|---|
| [0047](./features/0047-x.md) | Sehenswürdigkeit-Erkennung | Accepted |

### Offen — Niedrig

| Spec | Titel | Status |
|---|---|---|
| [0004](./features/0004-opencloud-export.md) | Export nach OpenCloud | Proposed |
| [0031](./features/0031-zweiwege-sync.md) | Zwei-Wege-Sync | Accepted |

### Inbox — ungeschärfte Ideen

| Datei | Kurzbeschreibung |
|---|---|
| [0004](./inbox/0004-x.md) | sollte NICHT als Prioritaet 0004 gezaehlt werden |

### Bereits umgesetzt

| Spec | Titel | Status |
|---|---|---|
| [0001](./features/0001-x.md) | Sollte auch nicht gezaehlt werden | Implemented |

## Priorisierung

Freitext-Begruendung, hier koennte auch "[0099](./features/0099-x.md)" auftauchen und
darf nicht als Tabellen-Eintrag gezaehlt werden.
"""


def test_parses_priority_per_spec_number() -> None:
    priorities = parse_roadmap_priorities(ROADMAP)

    assert priorities["0047"] == "Mittel"
    assert priorities["0004"] == "Niedrig"
    assert priorities["0031"] == "Niedrig"


def test_ignores_inbox_and_implemented_sections() -> None:
    priorities = parse_roadmap_priorities(ROADMAP)

    assert "0001" not in priorities


def test_ignores_freitext_section_after_status_auf_einen_blick() -> None:
    priorities = parse_roadmap_priorities(ROADMAP)

    assert "0099" not in priorities


def test_empty_hoch_section_yields_no_entries() -> None:
    priorities = parse_roadmap_priorities(ROADMAP)

    assert not any(p == "Hoch" for p in priorities.values())


def test_missing_status_section_returns_empty_mapping() -> None:
    priorities = parse_roadmap_priorities("# Roadmap\n\nkein passender Abschnitt hier.\n")

    assert priorities == {}
