from __future__ import annotations

from github_project_sync.hashing import (
    normalize_text,
    push_state_hash,
    push_state_hash_inbox,
    text_hash,
)


def test_normalize_text_converts_crlf_to_lf() -> None:
    assert normalize_text("a\r\nb\r\n") == normalize_text("a\nb\n")


def test_normalize_text_strips_trailing_whitespace_per_line() -> None:
    assert normalize_text("a   \nb\t\n") == normalize_text("a\nb\n")


def test_normalize_text_strips_trailing_newlines() -> None:
    assert normalize_text("a\nb\n\n\n") == normalize_text("a\nb")


def test_text_hash_stable_for_equivalent_input() -> None:
    assert text_hash("a\r\nb   \n\n") == text_hash("a\nb")


def test_text_hash_differs_for_different_content() -> None:
    assert text_hash("a") != text_hash("b")


def test_push_state_hash_changes_with_status() -> None:
    h1 = push_state_hash(status="Accepted", priority="Niedrig", content_zone="## Ziel\n\nfoo\n")
    h2 = push_state_hash(status="Proposed", priority="Niedrig", content_zone="## Ziel\n\nfoo\n")

    assert h1 != h2


def test_push_state_hash_changes_with_priority() -> None:
    h1 = push_state_hash(status="Accepted", priority="Niedrig", content_zone="## Ziel\n\nfoo\n")
    h2 = push_state_hash(status="Accepted", priority="Hoch", content_zone="## Ziel\n\nfoo\n")

    assert h1 != h2


def test_push_state_hash_changes_with_content() -> None:
    h1 = push_state_hash(status="Accepted", priority="Niedrig", content_zone="## Ziel\n\nfoo\n")
    h2 = push_state_hash(status="Accepted", priority="Niedrig", content_zone="## Ziel\n\nbar\n")

    assert h1 != h2


def test_push_state_hash_none_priority_differs_from_empty_string() -> None:
    # Implemented/Superseded-Specs haben keine Prioritaet (leer statt eines Werts) - das muss
    # sich vom Fall "Prioritaet ist der leere String" unterscheiden koennen, falls das je
    # vorkommt, sonst waeren beide Faelle im Hash nicht unterscheidbar.
    h1 = push_state_hash(status="Implemented", priority=None, content_zone="## Ziel\n\nfoo\n")
    h2 = push_state_hash(status="Implemented", priority="", content_zone="## Ziel\n\nfoo\n")

    assert h1 != h2


def test_push_state_hash_stable_under_crlf_and_trailing_whitespace_normalization() -> None:
    h1 = push_state_hash(status="Accepted", priority="Niedrig", content_zone="## Ziel\n\nfoo\n")
    h2 = push_state_hash(
        status="Accepted", priority="Niedrig", content_zone="## Ziel\r\n\r\nfoo   \r\n"
    )

    assert h1 == h2


# -- push_state_hash_inbox() (neu in Spec 0052 - Inbox-Eintraege haben keine Prioritaet, dafuer
# einen Typ; ein eigener, benannter Parameter ("typ" statt der irrefuehrenden Wiederverwendung
# von "priority") ist klarer als eine Umdeutung des bestehenden push_state_hash()-Parameters. ---


def test_push_state_hash_inbox_changes_with_status() -> None:
    h1 = push_state_hash_inbox(status="Unrefined", typ="Idee", content_zone="## Rohtext\n\nfoo\n")
    h2 = push_state_hash_inbox(status="Proposed", typ="Idee", content_zone="## Rohtext\n\nfoo\n")

    assert h1 != h2


def test_push_state_hash_inbox_changes_with_typ() -> None:
    h1 = push_state_hash_inbox(status="Unrefined", typ="Idee", content_zone="## Rohtext\n\nfoo\n")
    h2 = push_state_hash_inbox(
        status="Unrefined", typ="Bug (vermeintlich)", content_zone="## Rohtext\n\nfoo\n"
    )

    assert h1 != h2


def test_push_state_hash_inbox_changes_with_content() -> None:
    h1 = push_state_hash_inbox(status="Unrefined", typ="Idee", content_zone="## Rohtext\n\nfoo\n")
    h2 = push_state_hash_inbox(status="Unrefined", typ="Idee", content_zone="## Rohtext\n\nbar\n")

    assert h1 != h2


def test_push_state_hash_inbox_stable_under_normalization() -> None:
    h1 = push_state_hash_inbox(status="Unrefined", typ="Idee", content_zone="## Rohtext\n\nfoo\n")
    h2 = push_state_hash_inbox(
        status="Unrefined", typ="Idee", content_zone="## Rohtext\r\n\r\nfoo   \r\n"
    )

    assert h1 == h2
