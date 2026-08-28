from __future__ import annotations

from github_project_sync.hashing import normalize_text, push_state_hash, text_hash


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
    h1 = push_state_hash(status="Accepted", content_zone="## Ziel\n\nfoo\n")
    h2 = push_state_hash(status="Proposed", content_zone="## Ziel\n\nfoo\n")

    assert h1 != h2


def test_push_state_hash_changes_with_content() -> None:
    h1 = push_state_hash(status="Accepted", content_zone="## Ziel\n\nfoo\n")
    h2 = push_state_hash(status="Accepted", content_zone="## Ziel\n\nbar\n")

    assert h1 != h2


def test_push_state_hash_stable_under_crlf_and_trailing_whitespace_normalization() -> None:
    h1 = push_state_hash(status="Accepted", content_zone="## Ziel\n\nfoo\n")
    h2 = push_state_hash(status="Accepted", content_zone="## Ziel\r\n\r\nfoo   \r\n")

    assert h1 == h2
