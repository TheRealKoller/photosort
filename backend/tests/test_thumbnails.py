from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

from photosort.thumbnails import (
    DISPLAY_MAX_SIZE,
    THUMBNAIL_MAX_SIZE,
    cache_key,
    display_path,
    generate_variants,
    thumbnail_path,
    variant_path,
)


def _jpeg_bytes(width: int, height: int) -> bytes:
    image = Image.new("RGB", (width, height), color="red")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def test_cache_key_is_deterministic_and_differs_by_etag() -> None:
    assert cache_key(1, "etag-a") == cache_key(1, "etag-a")
    assert cache_key(1, "etag-a") != cache_key(1, "etag-b")
    assert cache_key(1, "etag-a") != cache_key(2, "etag-a")


def test_variant_path_thumbnail_and_display_differ(tmp_path: Path) -> None:
    thumb = thumbnail_path(tmp_path, 1, "etag-a")
    display = display_path(tmp_path, 1, "etag-a")
    assert thumb != display
    assert variant_path(tmp_path, 1, "etag-a", "thumbnail") == thumb
    assert variant_path(tmp_path, 1, "etag-a", "display") == display


def test_generate_variants_writes_both_files_downsized(tmp_path: Path) -> None:
    content = _jpeg_bytes(4000, 3000)

    ok = generate_variants(tmp_path, photo_id=1, etag="etag-a", image_bytes=content)

    assert ok is True
    thumb = thumbnail_path(tmp_path, 1, "etag-a")
    display = display_path(tmp_path, 1, "etag-a")
    assert thumb.is_file()
    assert display.is_file()

    with Image.open(thumb) as image:
        assert max(image.size) <= THUMBNAIL_MAX_SIZE
    with Image.open(display) as image:
        assert max(image.size) <= DISPLAY_MAX_SIZE


def test_generate_variants_does_not_upscale_small_images(tmp_path: Path) -> None:
    content = _jpeg_bytes(50, 40)

    generate_variants(tmp_path, photo_id=1, etag="etag-a", image_bytes=content)

    with Image.open(thumbnail_path(tmp_path, 1, "etag-a")) as image:
        assert image.size == (50, 40)


def test_generate_variants_returns_false_for_undecodable_bytes(tmp_path: Path) -> None:
    ok = generate_variants(tmp_path, photo_id=1, etag="etag-a", image_bytes=b"not an image")

    assert ok is False
    assert not thumbnail_path(tmp_path, 1, "etag-a").exists()
    assert not display_path(tmp_path, 1, "etag-a").exists()
