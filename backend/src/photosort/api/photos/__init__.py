"""Die HTTP-Schicht der Fotos: ein Router, mehrere Ablagen.

Der Router traegt `tags=["photos"]` und wird in `main.py` genau einmal eingebunden. Dieses Modul
ist der einzige Einstiegspunkt des Pakets: es bindet die Gruppen-Router in der Reihenfolge ein, in
der ihre Operationen in der OpenAPI-Datei stehen, und bietet die Namen an, die ausserhalb des
Pakets adressiert werden.
"""

from __future__ import annotations

from fastapi import APIRouter

from photosort.api.photos import (
    album_draft,
    album_selection,
    ausschuss,
    draft_exchange,
    duplicate_groups,
    image,
)
from photosort.api.photos._conversion import _suggestion_reason
from photosort.api.photos._reads import MAX_QUERY_POSITION
from photosort.api.photos.duplicate_groups import (
    DuplicateGroupOut,
    build_duplicate_group_out,
    empty_duplicate_group_out,
)
from photosort.api.photos.image import MotifCorrectionIn
from photosort.final_selection import selection_state_of as _selection_state_of

# Bewusste Abweichung vom Router-Level-dependencies=[Depends(get_current_user)]-Muster aus
# projects.py/opencloud.py: jeder Endpunkt hier braucht das tatsächliche
# User-Objekt (fuer die eigene Bewertung/den Datenzugriff), nicht nur die Auth-Pruefung als reinen
# Torwaechter - deshalb current_user als normaler Depends()-Parameter statt Router-weiter
# dependencies-Liste. Sicherheitswirkung ist identisch (jeder Endpunkt bleibt auth-pflichtig);
# `tests/test_route_table_photos.py` prueft die Anwesenheit der ausgeschriebenen Dependency an
# jeder Operation des in `main.py` eingebundenen Routers.
router = APIRouter(tags=["photos"])
router.include_router(album_draft.router)
router.include_router(album_selection.router)
router.include_router(duplicate_groups.router)
router.include_router(ausschuss.router)
router.include_router(draft_exchange.router)
router.include_router(image.router)

__all__ = [
    "DuplicateGroupOut",
    "MAX_QUERY_POSITION",
    "MotifCorrectionIn",
    "_selection_state_of",
    "_suggestion_reason",
    "build_duplicate_group_out",
    "empty_duplicate_group_out",
    "router",
]
