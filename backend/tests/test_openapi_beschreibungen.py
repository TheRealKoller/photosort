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
    # specs/features/0430-album-entwurf-je-nutzer.md, PR 3: der Alternativen-Endpunkt tritt an die
    # Stelle von `/projects/{project_id}/curation-candidates`. Seine Beschreibung traegt die
    # beiden Aussagen, die der Antwort sonst nirgends anzusehen sind: WELCHE Menge geliefert wird
    # (das Event abzueglich des eigenen Entwurfs, gestrichene eingeschlossen) und WORAN die
    # Reihenfolge haengt (den Motiven des Bezugsbildes).
    ("get", "/projects/{project_id}/draft-alternatives"),
    # specs/features/0431-endauswahl-gemeinsam.md, PR 1: der Schreibendpunkt der gemeinsamen
    # Entscheidung. Seine Beschreibung traegt die Aussage, die der Signatur gerade nicht anzusehen
    # ist - dass die Entscheidung dem PROJEKT gehoert und nicht dem angemeldeten Nutzer, dass sie
    # die Einigkeit in beide Richtungen ueberschreibt und dass es kein `DELETE` gibt.
    ("put", "/photos/{photo_id}/album-decision"),
    # Und der Leseendpunkt derselben Story. Seine Beschreibung traegt die Zusammensetzung der
    # Antwortmenge (`strittig ∪ Endauswahl ∪ entschieden`), die der Antwort selbst nicht anzusehen
    # ist - namentlich, warum ein ausdruecklich herausgenommenes Bild darin stehen bleibt.
    ("get", "/projects/{project_id}/album-selection"),
    # specs/features/0432-diagnose-und-gewichte-aus-der-nacharbeit.md, PR 1: der Austausch. Seine
    # Beschreibung traegt die drei Aussagen, die der Signatur nicht anzusehen sind - dass es EIN
    # Schreibvorgang in EINER Transaktion ist, dass beide Bilder zum selben Ereignis desselben
    # Laufs gehoeren muessen, und dass er ausdruecklich KEIN zusaetzliches Streich- und
    # Aufnahme-Ereignis erzeugt.
    ("post", "/projects/{project_id}/draft/exchange"),
    # PR 2 derselben Spec: die laufende Diagnose. Ihre Beschreibung traegt die Aussage, die der
    # Antwort selbst nicht anzusehen ist - dass die Zahlen PROJEKTUEBERGREIFEND und ueber beide
    # Nutzer gelten, obwohl der Abschnitt auf der Projekt-Statistikseite steht, und dass die drei
    # Tauschklassen nirgends summiert werden.
    ("get", "/feedback/diagnosis"),
    # PR 3 derselben Spec: die beiden Schreibendpunkte auf die global wirkende Grundlage. Ihre
    # Beschreibung traegt die Aussagen, die der Signatur gerade nicht anzusehen sind - dass der
    # Server den Vorschlag NEU rechnet und keine Gewichte aus dem Body uebernimmt, dass die
    # Aenderung erst beim naechsten Durchlauf wirkt und sonst nichts schreibt, und dass die
    # Ruecknahme eine neue Fassung anlegt statt eine zu loeschen.
    ("post", "/feedback/weights"),
    ("post", "/feedback/weights/revert"),
    # specs/features/0374-duplikate-vergleichen.md: der Lesepfad der Vergleichsansicht. Seine
    # Beschreibung traegt die drei Aussagen, die der Antwort selbst nicht anzusehen sind - dass die
    # Gruppe ABGELEITET ist und deshalb keine eigene Id hat (sie ist ueber jedes Mitglied
    # erreichbar), dass kein Mitglied ausgezeichnet ist, und worauf sich `position`/`total`
    # beziehen.
    ("get", "/projects/{project_id}/duplicate-groups/{photo_id}"),
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
