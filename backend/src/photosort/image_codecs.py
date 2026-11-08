"""Registriert den HEIF-Opener bei Pillow - die eine Stelle fuer alle dekodierenden Prozesse.

`thumbnails.py` (API) und `opencloud/exif.py` (Worker) importieren dieses Modul, bevor sie
`PIL.Image.open` aufrufen; Pillow behandelt HEIC/HEIF danach wie JPEG/PNG. Ein kuenftiger
Einstiegspunkt, der Pillow ohne diesen Import oeffnet, verliert HEIC still - der Best-effort-Block
liefert dann "kein Bild", ohne dass irgendwo ein Fehler auftaucht.
"""

from __future__ import annotations

import pillow_heif

# `decode_threads=0` schaltet die parallele Grid-Tile-Dekodierung ab; genau dieser Pfad ist in der
# gebuendelten libheif-Version angreifbar. Erst ein libheif mit der Korrektur darf hier wieder
# einen anderen Wert bekommen.
pillow_heif.register_heif_opener(decode_threads=0)
