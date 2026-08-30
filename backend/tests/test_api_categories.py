from __future__ import annotations

import httpx

from photosort.categories import CATEGORY_REGISTRY, LOCAL_CATEGORY_SIGNALS

# specs/features/0289-feste-kategorien.md, Teststrategie Abschnitt 8: das feste Set kommt vom
# Server (ADR 0049, Entwurfsentscheidung 5) - es gibt bewusst keine TypeScript-Spiegelung, und die
# Override-Auswahl braucht das volle Set unabhaengig von der Erkennung.


async def test_requires_auth(api_client: httpx.AsyncClient) -> None:
    # Router-Level-Auth, testseitig belegt statt nur behauptet (Security-Abschnitt der Spec,
    # Punkt 1) - die Linie "jeder Endpunkt ist auth-pflichtig, einzige Ausnahme POST /auth/login"
    # bleibt ohne Sonderfall bestehen.
    response = await api_client.get("/categories")
    assert response.status_code == 401


async def test_returns_all_thirteen_entries_in_registry_order(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    response = await authenticated_api_client.get("/categories")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 13
    assert [entry["key"] for entry in body] == list(CATEGORY_REGISTRY)


async def test_every_entry_carries_key_display_name_definition_and_availability(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    body = (await authenticated_api_client.get("/categories")).json()

    for entry in body:
        assert set(entry) == {"key", "display_name", "definition", "locally_available"}
        definition = CATEGORY_REGISTRY[entry["key"]]
        assert entry["display_name"] == definition.display_name
        assert entry["definition"] == definition.definition
        assert entry["definition"].strip() != ""


async def test_locally_available_is_derived_from_the_signal_wiring(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    """`locally_available` wird ABGELEITET, nicht literal gepflegt - dieser Test prueft beides
    gegeneinander (Teststrategie 8)."""
    body = (await authenticated_api_client.get("/categories")).json()

    available = {entry["key"] for entry in body if entry["locally_available"]}
    assert available == set(LOCAL_CATEGORY_SIGNALS)


async def test_exactly_the_six_locally_determinable_categories_are_marked(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    # Zusaetzliche literale Stichprobe: ein versehentlich zusaetzlich verdrahtetes Signal wuerde
    # die abgeleitete Pruefung oben nicht auffallen lassen.
    body = (await authenticated_api_client.get("/categories")).json()

    assert {entry["key"] for entry in body if entry["locally_available"]} == {
        "menschen",
        "tier",
        "essen_trinken",
        "fahrzeug",
        "gebaeude_bauwerk",
        "landschaft",
    }


async def test_the_catch_all_is_part_of_the_response_and_not_locally_available(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    body = (await authenticated_api_client.get("/categories")).json()

    catch_all = next(entry for entry in body if entry["key"] == "nicht_erkannt")
    assert catch_all["display_name"] == "Nicht erkannt"
    assert catch_all["locally_available"] is False
