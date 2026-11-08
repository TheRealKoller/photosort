"""Registriert den HEIF-Opener bei Pillow - die eine Stelle fuer alle dekodierenden Prozesse.

`thumbnails.py` (API) und `opencloud/exif.py` (Worker) importieren dieses Modul, bevor sie
`PIL.Image.open` aufrufen; Pillow behandelt HEIC/HEIF danach wie JPEG/PNG. Ein kuenftiger
Einstiegspunkt, der Pillow ohne diesen Import oeffnet, verliert HEIC still - der Best-effort-Block
liefert dann "kein Bild", ohne dass irgendwo ein Fehler auftaucht.
"""

from __future__ import annotations

import pillow_heif

pillow_heif.register_heif_opener()
