from slowapi import Limiter

from photosort.rate_limit import limiter


def test_limiter_uses_configured_storage_uri() -> None:
    assert isinstance(limiter, Limiter)
