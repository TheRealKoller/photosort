"""Die benannten Antworten der Ausloeser und des Ausschuss-Abschlusses.

Jeder 2xx-Koerper dieser Anwendung ist ein benanntes Schema: ein Ausloeser ohne `response_model`
erzeugte ein anonymes Objekt in der Schnittstellenbeschreibung, und die Oberflaeche muesste den
Statuswert dort als `string` fuehren statt als geschlossene Menge. Der JSON-Koerper bleibt
unveraendert (`{"status": "queued"}` bzw. `{"status": "confirmed"}`).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TriggerQueuedOut(BaseModel):
    """Die Antwort eines Ausloesers: der Lauf ist angenommen, aber noch nicht begonnen.

    `queued` beschreibt den ZUSTAND DES LAUFS, nicht den Erfolg einer Arbeit - die Arbeit selbst
    laeuft im Hintergrund und wird ueber `ProjectOut.last_*` verfolgt."""

    status: Literal["queued"] = Field(
        description=(
            "Immer `queued`: der Lauf ist angenommen, aber noch nicht begonnen. Ein anderer Wert "
            "kommt an diesem Endpunkt nicht vor."
        )
    )


class AusschussGateConfirmedOut(BaseModel):
    """Die Antwort des Ausschuss-Abschlusses: das Gate ist bestaetigt, der naechste Schritt frei.

    Der Aufruf ist idempotent - ein wiederholter Aufruf antwortet gleich, ohne einen zweiten
    Effekt."""

    status: Literal["confirmed"] = Field(
        description=(
            "Immer `confirmed`: alle offenen Vorschlaege sind uebernommen und das Gate traegt "
            "einen Zeitstempel."
        )
    )
