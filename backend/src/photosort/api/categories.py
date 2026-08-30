from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from photosort.api.deps import get_current_user
from photosort.categories import CATEGORY_REGISTRY, LOCAL_CATEGORY_SIGNALS

# specs/features/0289-feste-kategorien.md, Umsetzungsschritt 6: das feste Kategorien-Set kommt vom
# Server (ADR 0049, Entwurfsentscheidung 5) - es gibt bewusst KEINE TypeScript-Spiegelung im
# Frontend. Eine zweite Liste waere eine dauerhaft driftende Kopie, und die Override-Auswahl
# braucht das volle Set unabhaengig davon, was fuer ein einzelnes Foto erkannt wurde.
#
# Auth am ROUTER (nicht pro Endpunkt, Muster wie api/projects.py/api/opencloud.py) - die Abweichung
# in api/photos.py existiert nur, weil dort jeder Endpunkt das `User`-Objekt selbst braucht, hier
# nicht. Inhaltlich exponiert dieser Endpunkt ausschliesslich statische Registry-Daten (keine
# Foto-, Projekt- oder Nutzerdaten) und ist damit kein Informationsleck; er bleibt trotzdem
# bewusst hinter Auth, damit die Linie "jeder Endpunkt ist auth-pflichtig, einzige Ausnahme
# POST /auth/login" ohne Sonderfall bestehen bleibt (Security-Abschnitt der Spec, Punkt 1).
router = APIRouter(
    prefix="/categories", tags=["categories"], dependencies=[Depends(get_current_user)]
)


class CategoryOut(BaseModel):
    """Ein Eintrag des festen Sets. `definition` ist die fachliche Beschreibung aus der Registry -
    dieselbe, die auch in den Klassifizierungs-Prompt geht (eine Quelle, keine zweite Pflege).
    `locally_available` wird aus `LOCAL_CATEGORY_SIGNALS` ABGELEITET, nicht literal gepflegt: nur
    sechs der zwoelf Kategorien sind ohne Remote-Lauf ueberhaupt erreichbar, und genau das soll die
    Oberflaeche erklaeren koennen, ohne die Verdrahtung nachzubilden."""

    key: str
    display_name: str
    definition: str
    locally_available: bool


@router.get("", response_model=list[CategoryOut])
def list_categories() -> list[CategoryOut]:
    """Liefert alle 13 Eintraege in ANZEIGEREIHENFOLGE der Registry (nicht alphabetisch, nicht in
    Vorrangreihenfolge) - das Frontend uebernimmt genau diese Reihenfolge, damit sie ueberall im
    Produkt identisch ist."""
    return [
        CategoryOut(
            key=definition.key,
            display_name=definition.display_name,
            definition=definition.definition,
            locally_available=definition.key in LOCAL_CATEGORY_SIGNALS,
        )
        for definition in CATEGORY_REGISTRY.values()
    ]
