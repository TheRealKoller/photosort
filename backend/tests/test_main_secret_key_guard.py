import pytest

from photosort.config import settings
from photosort.main import create_app


def test_create_app_rejects_placeholder_secret_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "secret_key", "change-me")

    with pytest.raises(RuntimeError):
        create_app()


def test_create_app_rejects_too_short_secret_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "secret_key", "short-secret")

    with pytest.raises(RuntimeError):
        create_app()


def test_create_app_accepts_sufficiently_long_non_placeholder_secret_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "secret_key", "a" * 32)

    create_app()
