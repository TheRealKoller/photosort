"""specs/features/0427-motive-mit-staerke.md, PR 1 Schritt 5 - `GET /motifs`.

Der Endpunkt ist die EINZIGE Quelle für Anzeigenamen, Reihenfolge und Erklärtexte der Motive; im
Frontend wird keine Motivliste gespiegelt. Zwei Aussagen tragen mehr als die Feldform:

* `locally_assessable` ist aus `LOCAL_MOTIF_SIGNALS` ABGELEITET, nicht literal gepflegt. Ohne
  dieses Feld könnte die Oberfläche „0 weil nicht zu sehen" nicht von „0 weil nicht angesehen"
  unterscheiden, ohne die Signalliste zu spiegeln.
* `strength_bands` kommt vom Server, damit das Frontend die Grenzen nicht hinterlegt - sie sind
  eine Anzeigekonvention der Statistik und keine Zugehörigkeitsschwelle.
"""

from __future__ import annotations

from typing import Any

import httpx

from photosort.motifs import (
    EXCLUSION_KEY,
    LOCAL_MOTIF_SIGNALS,
    MOTIF_REGISTRY,
    MOTIF_STRENGTH_BAND_MEDIUM,
    MOTIF_STRENGTH_BAND_STRONG,
)


async def _motifs(client: httpx.AsyncClient) -> dict[str, Any]:
    response = await client.get("/motifs")
    assert response.status_code == 200
    payload: dict[str, Any] = response.json()
    return payload


async def test_it_requires_a_token(api_client: httpx.AsyncClient) -> None:
    """SICHERHEIT (S1): der Torwaechter sitzt als Router-Dependency. Inhaltlich exponiert der
    Endpunkt ausschliesslich statische Registry-Daten, er bleibt aber bewusst hinter Auth, damit
    die Linie "jeder Endpunkt ist auth-pflichtig, einzige Ausnahme POST /auth/login" ohne
    Sonderfall besteht."""
    response = await api_client.get("/motifs")

    assert response.status_code == 401


async def test_it_returns_exactly_the_eight_motifs_in_registry_order(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    """Die Reihenfolge ist Gegenstand der Zusage: die Staerkeliste eines Fotos und die
    Statistiktabelle uebernehmen genau sie, und sie ist auf jedem Foto dieselbe."""
    payload = await _motifs(authenticated_api_client)

    assert [item["key"] for item in payload["items"]] == list(MOTIF_REGISTRY)


async def test_every_entry_carries_name_definition_and_delimitation(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    payload = await _motifs(authenticated_api_client)

    for item in payload["items"]:
        definition = MOTIF_REGISTRY[item["key"]]
        assert item["display_name"] == definition.display_name
        assert item["definition"] == definition.definition
        assert item["delimitation"] == definition.delimitation


async def test_no_entry_carries_an_ordering_number(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    """Die Antwort darf keine Zahl tragen, aus der das Frontend eine Rangfolge bauen koennte -
    die Reihenfolge ist die Listenreihenfolge, nichts weiter."""
    payload = await _motifs(authenticated_api_client)

    for item in payload["items"]:
        assert set(item) == {
            "key",
            "display_name",
            "definition",
            "delimitation",
            "locally_assessable",
        }


async def test_the_locally_assessable_flag_is_derived_from_the_signal_registry(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    payload = await _motifs(authenticated_api_client)

    for item in payload["items"]:
        assert item["locally_assessable"] == (item["key"] in LOCAL_MOTIF_SIGNALS)


async def test_exactly_the_two_cloud_only_motifs_are_not_locally_assessable(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    """Die Gegenprobe zur Ableitung oben: eine Antwort, in der ALLE acht `true` tragen, bestuende
    die Ableitungspruefung genauso - solange auch die Registry alle acht kennte."""
    payload = await _motifs(authenticated_api_client)

    not_assessable = {item["key"] for item in payload["items"] if not item["locally_assessable"]}

    assert not_assessable == {"aktivitaet", "detail_stimmung"}


async def test_the_exclusion_key_is_not_part_of_the_list(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    """„Dokument und Screenshot" ist kein Motiv - die Oberflaeche darf es nicht als korrigierbare
    Zeile anbieten."""
    payload = await _motifs(authenticated_api_client)

    assert EXCLUSION_KEY not in {item["key"] for item in payload["items"]}


async def test_the_strength_bands_come_from_the_server(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    """Das Frontend hinterlegt die Grenzen nicht: `0.67` dort und `2/3` hier verschoeben die
    Grenze um einen Betrag, den kein Test trifft."""
    payload = await _motifs(authenticated_api_client)

    assert payload["strength_bands"] == {
        "strong": MOTIF_STRENGTH_BAND_STRONG,
        "medium": MOTIF_STRENGTH_BAND_MEDIUM,
    }


async def test_the_route_keeps_its_openapi_description(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    """Die Beschreibungspflicht selbst haengt an der eingefrorenen Liste in
    test_openapi_beschreibungen.py - dieser Fall ist der Hinweis darauf, dass sie dort steht."""
    response = await authenticated_api_client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["paths"]["/motifs"]["get"].get("description", "").strip()


async def test_the_category_endpoint_is_gone(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    """Die NEGATIVE Haelfte der Abloesung (Spec 0427, PR 3): `GET /categories` existiert nicht
    mehr.

    Ein stehengebliebener Router waere von jedem Positivtest des Motiv-Endpunkts unsichtbar - er
    lieferte weiter ein vollstaendiges Kategorien-Set und laedt jeden kuenftigen Leser dazu ein,
    es wieder zu benutzen. Als `404` gepruaft und nicht ueber die Router-Liste der App: die
    Aussage ist "von aussen nicht erreichbar"."""
    response = await authenticated_api_client.get("/categories")

    assert response.status_code == 404
