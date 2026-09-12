from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from photosort.api.deps import get_current_user
from photosort.motifs import (
    LOCAL_MOTIF_SIGNALS,
    MOTIF_REGISTRY,
    MOTIF_STRENGTH_BAND_MEDIUM,
    MOTIF_STRENGTH_BAND_STRONG,
)

# Das feste Motivset kommt vom Server - es gibt bewusst KEINE TypeScript-Spiegelung im Frontend.
# Eine zweite Liste waere eine dauerhaft driftende Kopie, und die Staerkeliste braucht das volle
# Set unabhaengig davon, was fuer ein einzelnes Foto beurteilt wurde.
#
# SICHERHEIT (S1): Auth am ROUTER (Muster wie api/categories.py/api/projects.py). Der Eintrag in
# der handgepflegten Router-Liste von tests/test_auth_guard.py::_protected_router_operations
# gehoert dazu - ohne ihn waere ein spaeter ergaenzter zweiter Endpunkt DIESES Routers von keinem
# Vollstaendigkeitstest erfasst. Inhaltlich exponiert der Endpunkt ausschliesslich statische
# Registry-Daten (keine Foto-, Projekt- oder Nutzerdaten) und ist damit kein Informationsleck; er
# bleibt trotzdem bewusst hinter Auth, damit die Linie "jeder Endpunkt ist auth-pflichtig, einzige
# Ausnahme POST /auth/login" ohne Sonderfall bestehen bleibt.
router = APIRouter(prefix="/motifs", tags=["motifs"], dependencies=[Depends(get_current_user)])


class MotifOut(BaseModel):
    """Ein Eintrag des festen Motivsets. `definition`/`delimitation` sind die fachlichen Texte aus
    der Registry - dieselben, die auch in den Klassifizierungs-Prompt gehen (eine Quelle, keine
    zweite Pflege).

    `locally_assessable` wird aus `LOCAL_MOTIF_SIGNALS` ABGELEITET, nicht literal gepflegt: nur
    sechs der acht Motive sind ohne Cloud-Aussage ueberhaupt erreichbar. Ohne dieses Feld koennte
    die Oberflaeche "0 weil nicht zu sehen" nicht von "0 weil nicht angesehen" unterscheiden, ohne
    die Signalliste zu spiegeln - und ein `0 %` an einem lokal nicht beurteilbaren Motiv waere die
    Aussage "nicht zu sehen" statt "nicht angesehen".

    KEIN Ordnungsfeld: die Reihenfolge ist die Listenreihenfolge, und eine Zahl daneben waere die
    Vorrangreihenfolge zurueck."""

    key: str
    display_name: str
    definition: str
    delimitation: str
    locally_assessable: bool


class StrengthBandsOut(BaseModel):
    """Die beiden Anzeigebaender der STATISTIK, inklusiv verglichen (`>=`).

    Sie gehen in die Antwort ein, damit das Frontend sie nicht hinterlegt: `0.67` dort und `2/3`
    im Backend verschoeben die Grenze um einen Betrag, den kein Test trifft. Sie sind
    ausdruecklich KEINE Zugehoerigkeitsschwelle - kein Pfad der Auswahl oder Rangfolge liest sie,
    und ausserhalb der Statistiktabelle erscheint kein Bandwort."""

    strong: float
    medium: float


class MotifSetOut(BaseModel):
    items: list[MotifOut]
    strength_bands: StrengthBandsOut


@router.get("", response_model=MotifSetOut)
def list_motifs() -> MotifSetOut:
    """Liefert alle acht Motive in ANZEIGEREIHENFOLGE der Registry (nicht alphabetisch, nicht nach
    Staerke) samt den beiden Anzeigebaendern der Statistik.

    Das Frontend uebernimmt genau diese Reihenfolge - auf jedem Foto dieselbe. Der
    Ausschluss-Schluessel `dokument_screenshot` steht bewusst NICHT in der Liste: er ist kein
    Motiv, sondern ein Ausschluss-Signal, und er ist von Hand nicht korrigierbar."""
    return MotifSetOut(
        items=[
            MotifOut(
                key=definition.key,
                display_name=definition.display_name,
                definition=definition.definition,
                delimitation=definition.delimitation,
                locally_assessable=definition.key in LOCAL_MOTIF_SIGNALS,
            )
            for definition in MOTIF_REGISTRY.values()
        ],
        strength_bands=StrengthBandsOut(
            strong=MOTIF_STRENGTH_BAND_STRONG, medium=MOTIF_STRENGTH_BAND_MEDIUM
        ),
    )
