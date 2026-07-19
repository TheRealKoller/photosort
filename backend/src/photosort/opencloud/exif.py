from __future__ import annotations

import io
from datetime import datetime

from PIL import Image
from PIL.ExifTags import IFD

_DATETIME_ORIGINAL_TAG = 36867
_DATETIME_FORMAT = "%Y:%m:%d %H:%M:%S"


def extract_taken_at(content: bytes) -> datetime | None:
    """Best-effort EXIF DateTimeOriginal extraction.

    Runs on partial (range-fetched) file content from untrusted, possibly
    truncated downloads, so any parsing failure is treated as "no date
    available" rather than propagated — a single unreadable photo must
    never abort a project scan.
    """
    try:
        image = Image.open(io.BytesIO(content))
        exif = image.getexif()
        raw_value = exif.get(_DATETIME_ORIGINAL_TAG) or exif.get_ifd(IFD.Exif).get(
            _DATETIME_ORIGINAL_TAG
        )
    except Exception:
        return None

    if not raw_value:
        return None

    try:
        return datetime.strptime(raw_value, _DATETIME_FORMAT)
    except ValueError:
        return None
