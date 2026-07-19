from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import unquote
from xml.etree import ElementTree

_DAV_NS = "DAV:"


@dataclass(frozen=True)
class DavEntry:
    href: str
    name: str
    is_collection: bool
    etag: str | None
    last_modified: datetime | None
    content_length: int | None


def _tag(local_name: str) -> str:
    return f"{{{_DAV_NS}}}{local_name}"


def _name_from_href(href: str) -> str:
    decoded = unquote(href)
    return decoded.rstrip("/").rsplit("/", maxsplit=1)[-1]


def _parse_last_modified(value: str | None) -> datetime | None:
    if not value:
        return None
    return parsedate_to_datetime(value)


def parse_multistatus(xml_bytes: bytes) -> list[DavEntry]:
    root = ElementTree.fromstring(xml_bytes)
    entries: list[DavEntry] = []

    for response in root.findall(_tag("response")):
        href_el = response.find(_tag("href"))
        if href_el is None or not href_el.text:
            continue
        href = href_el.text

        prop = None
        for propstat in response.findall(_tag("propstat")):
            status_el = propstat.find(_tag("status"))
            if status_el is not None and status_el.text and " 200 " in status_el.text:
                prop = propstat.find(_tag("prop"))
                break

        if prop is None:
            continue

        resourcetype = prop.find(_tag("resourcetype"))
        is_collection = (
            resourcetype is not None and resourcetype.find(_tag("collection")) is not None
        )

        etag_el = prop.find(_tag("getetag"))
        etag = etag_el.text if etag_el is not None else None

        last_modified_el = prop.find(_tag("getlastmodified"))
        last_modified_text = last_modified_el.text if last_modified_el is not None else None
        last_modified = _parse_last_modified(last_modified_text)

        length_el = prop.find(_tag("getcontentlength"))
        content_length = int(length_el.text) if length_el is not None and length_el.text else None

        entries.append(
            DavEntry(
                href=href,
                name=_name_from_href(href),
                is_collection=is_collection,
                etag=etag,
                last_modified=last_modified,
                content_length=content_length,
            )
        )

    return entries
