"""specs/features/0036-scan-performance-zweiphasig-parallel.md, ADR 0020 (Phase 2a): reine,
Session-lose Klassifikationsfunktion, die die in Phase 1 materialisierte Eintragsliste gegen die
vorab geladene existing_photos-Map abgleicht - isoliert unit-testbar ohne DB/Async-Session, siehe
Teststrategie-Abschnitt der Spec ("Phase-2a-Klassifikation als reine Funktion")."""

from datetime import UTC, datetime

from photosort.models import Photo
from photosort.opencloud.webdav_xml import DavEntry
from photosort.worker import SkipReason, _classify_scan_entries

MODIFIED = datetime(2023, 8, 15, 10, 0, tzinfo=UTC)


def _entry(name: str, etag: str, content_length: int = 100) -> DavEntry:
    return DavEntry(
        href=f"/dav/spaces/drive-1/CostaRica/{name}",
        name=name,
        is_collection=False,
        etag=etag,
        last_modified=MODIFIED,
        content_length=content_length,
    )


def _existing_photo(relative_path: str, etag: str) -> Photo:
    return Photo(
        id=1,
        project_id=1,
        relative_path=relative_path,
        etag=etag,
        content_length=10,
        taken_at=MODIFIED,
        last_modified=MODIFIED,
    )


def test_unsupported_extension_is_skipped_and_excluded_from_seen_paths() -> None:
    entries = [("CostaRica/notes.txt", _entry("notes.txt", "etag-1"))]

    classification = _classify_scan_entries(entries, existing_photos={})

    assert len(classification.decisions) == 1
    decision = classification.decisions[0]
    assert decision.skip_reason == SkipReason.UNSUPPORTED_EXTENSION
    assert decision.work_item is None
    assert classification.work_items == []
    assert classification.seen_paths == set()


def test_unchanged_etag_is_skipped_but_counted_as_seen() -> None:
    entries = [("CostaRica/img.jpg", _entry("img.jpg", "same-etag"))]
    existing = {"CostaRica/img.jpg": _existing_photo("CostaRica/img.jpg", "same-etag")}

    classification = _classify_scan_entries(entries, existing_photos=existing)

    decision = classification.decisions[0]
    assert decision.skip_reason == SkipReason.UNCHANGED_ETAG
    assert decision.work_item is None
    assert classification.work_items == []
    assert classification.seen_paths == {"CostaRica/img.jpg"}


def test_new_file_becomes_a_work_item_without_existing_photo() -> None:
    entries = [("CostaRica/img.jpg", _entry("img.jpg", "etag-1"))]

    classification = _classify_scan_entries(entries, existing_photos={})

    decision = classification.decisions[0]
    assert decision.skip_reason is None
    assert decision.work_item is not None
    assert decision.work_item.existing_photo is None
    assert decision.work_item.relative_path == "CostaRica/img.jpg"
    assert classification.work_items == [decision.work_item]
    assert classification.seen_paths == {"CostaRica/img.jpg"}


def test_changed_etag_becomes_a_work_item_referencing_the_existing_photo() -> None:
    entries = [("CostaRica/img.jpg", _entry("img.jpg", "new-etag"))]
    existing_photo = _existing_photo("CostaRica/img.jpg", "old-etag")
    existing = {"CostaRica/img.jpg": existing_photo}

    classification = _classify_scan_entries(entries, existing_photos=existing)

    decision = classification.decisions[0]
    assert decision.skip_reason is None
    assert decision.work_item is not None
    assert decision.work_item.existing_photo is existing_photo
    assert classification.seen_paths == {"CostaRica/img.jpg"}


def test_decisions_preserve_input_order_for_a_mixed_batch() -> None:
    """Wichtig fuer die Checkpoint-Kadenz in run_project_scan (Phase 2a): der Aufrufer iteriert
    classification.decisions in genau dieser Reihenfolge, um files_found/files_skipped konsistent
    hochzuzaehlen - eine falsche Reihenfolge wuerde den Live-Fortschritt verfaelschen."""
    entries = [
        ("CostaRica/notes.txt", _entry("notes.txt", "etag-notes")),
        ("CostaRica/unchanged.jpg", _entry("unchanged.jpg", "same-etag")),
        ("CostaRica/new.jpg", _entry("new.jpg", "etag-new")),
    ]
    existing = {
        "CostaRica/unchanged.jpg": _existing_photo("CostaRica/unchanged.jpg", "same-etag"),
    }

    classification = _classify_scan_entries(entries, existing_photos=existing)

    assert [decision.relative_path for decision in classification.decisions] == [
        "CostaRica/notes.txt",
        "CostaRica/unchanged.jpg",
        "CostaRica/new.jpg",
    ]
    assert [decision.skip_reason for decision in classification.decisions] == [
        SkipReason.UNSUPPORTED_EXTENSION,
        SkipReason.UNCHANGED_ETAG,
        None,
    ]
    assert [item.relative_path for item in classification.work_items] == ["CostaRica/new.jpg"]
    assert classification.seen_paths == {"CostaRica/unchanged.jpg", "CostaRica/new.jpg"}


def test_empty_entries_produce_empty_classification() -> None:
    classification = _classify_scan_entries([], existing_photos={})

    assert classification.decisions == []
    assert classification.work_items == []
    assert classification.seen_paths == set()
