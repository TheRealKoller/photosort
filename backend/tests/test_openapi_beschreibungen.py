"""Die Route-Docstrings SIND die OpenAPI-Beschreibung - es gibt an keiner Route ein
`summary=`- oder `description=`-Argument. Ihr Wegfall wäre still: kein Lint und kein anderer
Test fällt darüber."""

from typing import Any

import pytest

from photosort.main import create_app

# Eingefrorene Liste der heute beschriebenen Routen. Sie ist Gegenstand der Zusage, nicht ihr
# Nebenprodukt: Wächst sie aus `app.openapi()` heraus, prüft der Test nur noch sich selbst.
DOCUMENTED_ROUTES: tuple[tuple[str, str], ...] = (
    ("get", "/categories"),
    ("delete", "/projects/{project_id}"),
    ("post", "/projects/{project_id}/confirm-ausschuss-gate"),
    ("post", "/projects/{project_id}/classify"),
    ("put", "/projects/{project_id}/cloud-vision-consent"),
    ("get", "/projects/{project_id}/classify/estimate"),
    ("get", "/projects/{project_id}/fine-labels"),
    ("get", "/projects/{project_id}/curation-candidates"),
    ("put", "/photos/{photo_id}/category-override"),
    ("delete", "/photos/{photo_id}/category-override"),
    ("get", "/projects/{project_id}/stats"),
)


@pytest.fixture(scope="module")
def openapi_schema() -> dict[str, Any]:
    schema: dict[str, Any] = create_app().openapi()
    return schema


class TestTheDocumentedRoutesKeepTheirOpenApiDescription:
    def test_the_frozen_list_is_not_empty(self) -> None:
        """Selbstschutz (a): eine leergelaufene Liste machte die Parametrisierung unten zur
        leeren Menge - der Test bliebe grün und prüfte nichts."""
        assert DOCUMENTED_ROUTES

    @pytest.mark.parametrize(("method", "path"), DOCUMENTED_ROUTES)
    def test_the_listed_route_exists_in_the_app(
        self, method: str, path: str, openapi_schema: dict[str, Any]
    ) -> None:
        """Selbstschutz (b): eine umbenannte oder entfernte Route darf nicht stillschweigend aus
        der Prüfung fallen. Wer eine Route umbenennt, zieht die Liste bewusst nach."""
        assert path in openapi_schema["paths"], path
        assert method in openapi_schema["paths"][path], (method, path)

    @pytest.mark.parametrize(("method", "path"), DOCUMENTED_ROUTES)
    def test_the_description_is_present_and_not_empty(
        self, method: str, path: str, openapi_schema: dict[str, Any]
    ) -> None:
        """Die eigentliche Zusage: ANWESENHEIT, kein Textvergleich. Ein Schnappschuss des Textes
        wiese jede Kürzung zurück, statt den Verlust der Beschreibung zu melden."""
        operation = openapi_schema["paths"][path][method]

        assert operation.get("description", "").strip(), (method, path)
