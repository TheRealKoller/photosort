"""Die Route-Docstrings SIND die OpenAPI-Beschreibung - es gibt an keiner Route ein
`summary=`- oder `description=`-Argument. Ihr Wegfall wäre still: kein Lint und kein anderer
Test fällt darüber."""

from typing import Any

import pytest

from photosort.main import create_app

# Eingefrorene Liste der heute beschriebenen Routen. Sie ist Gegenstand der Zusage, nicht ihr
# Nebenprodukt: Wächst sie aus `app.openapi()` heraus, prüft der Test nur noch sich selbst.
DOCUMENTED_ROUTES: tuple[tuple[str, str], ...] = (
    ("delete", "/projects/{project_id}"),
    ("post", "/projects/{project_id}/confirm-ausschuss-gate"),
    ("post", "/projects/{project_id}/classify"),
    ("put", "/projects/{project_id}/cloud-vision-consent"),
    ("get", "/projects/{project_id}/classify/estimate"),
    ("get", "/projects/{project_id}/fine-labels"),
    ("get", "/projects/{project_id}/curation-candidates"),
    ("get", "/projects/{project_id}/stats"),
    # specs/features/0426-zeitversatz-je-kamera.md: die zweite der zwei Registerstellen, die
    # einen neuen Router still uebergehen - ein nicht eingetragener Endpunkt faellt ohne roten
    # Test aus der Beschreibungspflicht.
    ("get", "/projects/{project_id}/cameras"),
    ("put", "/projects/{project_id}/cameras/{camera_id}/time-offset"),
    ("get", "/projects/{project_id}/camera-time-offset-suggestion"),
    # specs/features/0427-motive-mit-staerke.md, PR 1: ein nicht eingetragener Endpunkt faellt
    # ohne roten Test aus der Beschreibungspflicht.
    ("get", "/motifs"),
    ("put", "/photos/{photo_id}/motif-corrections/{motif_key}"),
    ("delete", "/photos/{photo_id}/motif-corrections/{motif_key}"),
    # specs/features/0429-auswahl-richtwert-und-mischung.md: ein nicht eingetragener Endpunkt
    # faellt ohne roten Test aus der Beschreibungspflicht.
    ("put", "/projects/{project_id}/selection-target"),
    # specs/features/0430-album-entwurf-je-nutzer.md, PR 1: alle drei Schreibendpunkte der
    # Bewertungszeile. Ihre Beschreibung traegt die Aussage, die diese Story erst erzeugt -
    # WELCHES Feld der jeweilige Endpunkt anfasst und welches er unberuehrt laesst.
    ("put", "/photos/{photo_id}/rating"),
    ("delete", "/photos/{photo_id}/rating"),
    ("put", "/photos/{photo_id}/favorite"),
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


class TestTheSchemaNamesStayUnqualified:
    """Zwei gleichnamige Pydantic-Modelle in verschiedenen Modulen benennt FastAPI in der
    OpenAPI-Beschreibung auf BEIDEN Seiten um - aus `RatingOut` wird
    `photosort__api__photos__RatingOut` UND `photosort__api__ratings__RatingOut`.

    Der Schaden trifft damit auch den Endpunkt, den niemand angefasst hat: Ein neues Modell in
    Modul B aendert still den Schemanamen eines Bestands-Endpunkts in Modul A. Nichts im Bestand
    faellt darueber - kein Lint, kein Typprüfer, kein anderer Test.

    Geprueft wird die FORM, nicht eine eingefrorene Namensliste: Der Doppelunterstrich entsteht
    ausschliesslich aus dieser Qualifizierung."""

    def test_no_schema_name_is_module_qualified(self, openapi_schema: dict[str, Any]) -> None:
        qualified = [name for name in openapi_schema["components"]["schemas"] if "__" in name]

        assert qualified == [], (
            "Gleichnamige Modelle in verschiedenen Modulen - FastAPI qualifiziert dadurch auch "
            f"den Schemanamen des unveraenderten Endpunkts: {qualified}"
        )
