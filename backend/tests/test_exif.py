import io

from PIL import Image
from PIL.ExifTags import IFD

from photosort.opencloud.exif import extract_taken_at

_DATETIME_ORIGINAL_TAG = 36867


def _make_jpeg(with_exif_datetime: str | None) -> bytes:
    image = Image.new("RGB", (4, 4), color="red")
    buffer = io.BytesIO()

    if with_exif_datetime is not None:
        exif = image.getexif()
        exif_ifd = exif.get_ifd(IFD.Exif)
        exif_ifd[_DATETIME_ORIGINAL_TAG] = with_exif_datetime
        image.save(buffer, format="JPEG", exif=exif)
    else:
        image.save(buffer, format="JPEG")

    return buffer.getvalue()


def _make_png() -> bytes:
    image = Image.new("RGB", (4, 4), color="blue")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_extracts_datetime_original_from_jpeg_exif() -> None:
    jpeg_bytes = _make_jpeg("2023:08:15 12:30:00")

    taken_at = extract_taken_at(jpeg_bytes)

    assert taken_at is not None
    assert (taken_at.year, taken_at.month, taken_at.day) == (2023, 8, 15)
    assert (taken_at.hour, taken_at.minute, taken_at.second) == (12, 30, 0)


def test_returns_none_for_jpeg_without_exif() -> None:
    jpeg_bytes = _make_jpeg(with_exif_datetime=None)

    assert extract_taken_at(jpeg_bytes) is None


def test_returns_none_for_png_without_exif() -> None:
    assert extract_taken_at(_make_png()) is None


def test_returns_none_for_garbage_bytes() -> None:
    assert extract_taken_at(b"not-an-image") is None
