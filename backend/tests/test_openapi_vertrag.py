"""Das eingecheckte Artefakt `backend/openapi.json` gegen `create_app().openapi()`.

Der Kern ist eine reine Funktion `vergleiche(soll, ist) -> list[str]`: sie vergleicht GEPARSTE
Strukturen, nicht Bytes - die Schluesselreihenfolge der Datei ist Form, nicht Vertrag. Bei
Abweichung nennt der Befund den Ort in Punktnotation und BEIDE Nachfuehrbefehle. Dieselbe Meldung
ist hier selbst getestet: eine Meldung ohne Nachfuehrschritt degradiert still zu einer roten Zeile
ohne Handlung.

Dieselbe Datei haelt die Vertragsaussagen fest, die nicht aus dem Vergleich folgen:
- jede 2xx-Antwort mit JSON-Koerper ist ein benanntes Schema (`$ref`, auch als Array davon) -
  ohne Ausnahmeliste;
- die benannten Antworten der vier Ausloeser, des Ausschuss-Abschlusses und von `/health`;
- `CancelOutcome` ist ein geschlossenes Enum, die beiden Zaehlkarten sind feste Modelle;
- die drei Binaerendpunkte behaupten keinen JSON-Koerper;
- `ScanStatus` und `ExportRunStatus` bleiben zwei benannte Schemata mit den richtigen Referenzen;
- die Verhaltensregeln stehen als Beschreibung an ihrem Feld bzw. Enum.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from photosort.main import create_app

ARTEFAKT = Path(__file__).resolve().parents[1] / "openapi.json"
EXPORT_BEFEHL = "backend/scripts/export_openapi.py"
GENERIEREN_BEFEHL = "npm --prefix frontend run api:generate"
NACHFUEHREN = f"Nachfuehren: `{EXPORT_BEFEHL}`, danach `{GENERIEREN_BEFEHL}`."


def _ort(*teile: object) -> str:
    return ".".join(str(teil) for teil in teile if str(teil))


def _befund(ort: str, text: str) -> str:
    return f"{ort}: {text} {NACHFUEHREN}"


def _vergleiche(soll: Any, ist: Any, ort: str, befunde: list[str]) -> None:
    if isinstance(soll, dict) and isinstance(ist, dict):
        for schluessel in sorted(set(soll) - set(ist)):
            befunde.append(_befund(_ort(ort, schluessel), "fehlt in der Anwendung."))
        for schluessel in sorted(set(ist) - set(soll)):
            befunde.append(_befund(_ort(ort, schluessel), "steht nur in der Anwendung."))
        for schluessel in sorted(set(soll) & set(ist)):
            _vergleiche(soll[schluessel], ist[schluessel], _ort(ort, schluessel), befunde)
        return
    if isinstance(soll, list) and isinstance(ist, list):
        for index in range(min(len(soll), len(ist))):
            _vergleiche(soll[index], ist[index], _ort(ort, f"[{index}]"), befunde)
        for index in range(len(ist), len(soll)):
            befunde.append(_befund(_ort(ort, f"[{index}]"), "fehlt in der Anwendung."))
        for index in range(len(soll), len(ist)):
            befunde.append(_befund(_ort(ort, f"[{index}]"), "steht nur in der Anwendung."))
        return
    if type(soll) is not type(ist) or soll != ist:
        befunde.append(_befund(ort, f"weicht ab: Artefakt {soll!r}, Anwendung {ist!r}."))


def vergleiche(soll: dict[str, Any], ist: dict[str, Any]) -> list[str]:
    """Reine Funktion: Soll (Artefakt) und Ist (Anwendung) als geparste Strukturen -> Befunde."""
    befunde: list[str] = []
    _vergleiche(soll, ist, "", befunde)
    return befunde


def _artefakt() -> dict[str, Any]:
    inhalt: dict[str, Any] = json.loads(ARTEFAKT.read_text(encoding="utf-8"))
    return inhalt


def _schema(spec: dict[str, Any], name: str) -> dict[str, Any]:
    schemas: dict[str, Any] = spec["components"]["schemas"]
    return schemas[name]


def _ref_name(schema: dict[str, Any]) -> str | None:
    ref = schema.get("$ref")
    if not isinstance(ref, str):
        return None
    return ref.rsplit("/", 1)[-1]


def _json_antworten(spec: dict[str, Any]) -> list[tuple[str, str, str, dict[str, Any]]]:
    """(Pfad, Methode, Status, Schema) fuer jede 2xx-Antwort MIT JSON-Koerper."""
    treffer: list[tuple[str, str, str, dict[str, Any]]] = []
    for pfad, operationen in spec["paths"].items():
        for methode, operation in operationen.items():
            if methode == "parameters" or not isinstance(operation, dict):
                continue
            for status_code, antwort in operation.get("responses", {}).items():
                if not str(status_code).startswith("2"):
                    continue
                schema = antwort.get("content", {}).get("application/json", {}).get("schema")
                if schema is not None:
                    treffer.append((pfad, methode, str(status_code), schema))
    return treffer


def _ist_benannt(schema: dict[str, Any]) -> bool:
    if _ref_name(schema) is not None:
        return True
    if schema.get("type") == "array":
        items = schema.get("items", {})
        return isinstance(items, dict) and _ist_benannt(items)
    return False


def _status_werte(properties: dict[str, Any]) -> list[Any]:
    """Die erlaubten Werte von `status` - als `const` (ein Wert) oder `enum`."""
    status = properties["status"]
    if "const" in status:
        return [status["const"]]
    werte = status.get("enum", [])
    return list(werte)


# --- Der Vergleich ---------------------------------------------------------------------------


def test_das_artefakt_ist_nachgefuehrt() -> None:
    """Der eine Schritt, der eine Vertragsaenderung ohne Nachfuehrung rot macht."""
    assert ARTEFAKT.is_file(), f"{ARTEFAKT.name} fehlt. Anlegen mit `python {EXPORT_BEFEHL}`."

    befunde = vergleiche(_artefakt(), create_app().openapi())

    assert not befunde, "Artefakt weicht ab:\n" + "\n".join(befunde[:20])


class TestTheMessageItself:
    """Die Meldung ist selbst getestet - sonst degradiert sie still."""

    def test_a_renamed_field_names_the_place_and_both_follow_up_steps(self) -> None:
        soll = {
            "components": {
                "schemas": {"ScanSummary": {"properties": {"photos_added": {"type": "integer"}}}}
            }
        }
        ist = {
            "components": {
                "schemas": {"ScanSummary": {"properties": {"photos_created": {"type": "integer"}}}}
            }
        }

        befunde = vergleiche(soll, ist)
        text = "\n".join(befunde)

        assert "components.schemas.ScanSummary.properties.photos_added" in text
        assert EXPORT_BEFEHL in text
        assert GENERIEREN_BEFEHL in text

    def test_a_removed_field_names_the_field(self) -> None:
        soll = {"components": {"schemas": {"PhotoOut": {"required": ["id", "relative_path"]}}}}
        ist = {"components": {"schemas": {"PhotoOut": {"required": ["id"]}}}}

        text = "\n".join(vergleiche(soll, ist))

        assert "components.schemas.PhotoOut.required.[1]" in text
        assert EXPORT_BEFEHL in text

    def test_an_added_enum_value_names_the_enum(self) -> None:
        soll = {"components": {"schemas": {"ScanStatus": {"enum": ["queued", "running"]}}}}
        ist = {"components": {"schemas": {"ScanStatus": {"enum": ["queued", "running", "paused"]}}}}

        text = "\n".join(vergleiche(soll, ist))

        assert "components.schemas.ScanStatus.enum" in text
        assert GENERIEREN_BEFEHL in text

    def test_a_new_path_and_status_names_the_operation(self) -> None:
        soll = {"paths": {"/projects/{project_id}/scan": {"post": {"responses": {"202": {}}}}}}
        ist = {
            "paths": {
                "/projects/{project_id}/scan": {"post": {"responses": {"202": {}, "429": {}}}}
            }
        }

        text = "\n".join(vergleiche(soll, ist))

        assert "paths./projects/{project_id}/scan.post.responses.429" in text
        assert EXPORT_BEFEHL in text


# --- Benannte Antworten -----------------------------------------------------------------------


def test_every_2xx_json_body_is_a_named_schema() -> None:
    """Ohne Ausnahmeliste: ein unbenanntes Objekt ist ein kuenftiger Ausloeser ohne
    `response_model` und damit eine stille Typluecke in der Oberflaeche."""
    spec = _artefakt()

    unbenannt = [
        f"{pfad} {methode} {status_code}"
        for pfad, methode, status_code, schema in _json_antworten(spec)
        if not _ist_benannt(schema)
    ]

    assert not unbenannt, f"unbenannte 2xx-JSON-Antworten: {unbenannt}"


def test_the_four_triggers_and_the_ausschuss_gate_answer_with_named_models() -> None:
    spec = _artefakt()
    erwartet = {
        ("/projects/{project_id}/scan", "post", "202"): ("TriggerQueuedOut", "queued"),
        ("/projects/{project_id}/score", "post", "202"): ("TriggerQueuedOut", "queued"),
        ("/projects/{project_id}/classify", "post", "202"): ("TriggerQueuedOut", "queued"),
        ("/projects/{project_id}/export", "post", "202"): ("TriggerQueuedOut", "queued"),
        (
            "/projects/{project_id}/confirm-ausschuss-gate",
            "post",
            "200",
        ): ("AusschussGateConfirmedOut", "confirmed"),
        ("/health", "get", "200"): ("HealthOut", "ok"),
    }

    for (pfad, methode, status_code), (schema_name, wert) in erwartet.items():
        schema = spec["paths"][pfad][methode]["responses"][status_code]["content"][
            "application/json"
        ]["schema"]
        assert _ref_name(schema) == schema_name, (pfad, methode, status_code)
        name = schema_name
        assert _status_werte(_schema(spec, name)["properties"]) == [wert], name


def test_cancel_outcome_is_a_closed_enum_with_two_values() -> None:
    spec = _artefakt()

    outcome = _schema(spec, "CancelOutcome")
    assert sorted(outcome.get("enum", [])) == ["already_finished", "cancel_requested"]
    ref = _schema(spec, "CancelOut")["properties"]["outcome"]
    assert _ref_name(ref) == "CancelOutcome"


def test_the_two_review_count_maps_are_fixed_models_with_the_four_purposes() -> None:
    """Der JSON-Koerper bleibt gleich; die Schluessel-Erschoeffnung bleibt typisiert."""
    spec = _artefakt()
    zwecke = {"album_level", "excluded_document", "motif_feature", "motifs"}
    detail = _schema(spec, "ReviewDetailOut")["properties"]

    for field in ("counts_by_purpose", "verdicts_by_purpose"):
        name = _ref_name(detail[field])
        assert name is not None, field
        modell = _schema(spec, name)
        assert set(modell["properties"]) == zwecke, field
        assert "additionalProperties" not in modell, field


def test_the_three_binary_endpoints_declare_no_json_body() -> None:
    spec = _artefakt()
    for pfad, methode in (
        ("/photos/{photo_id}/image", "get"),
        ("/photos/{photo_id}/faces/{index}/image", "get"),
        (
            "/projects/{project_id}/classification-reviews/{review_id}/export",
            "get",
        ),
    ):
        for status_code, antwort in spec["paths"][pfad][methode]["responses"].items():
            if str(status_code).startswith("2"):
                assert "content" not in antwort or antwort["content"] == {}, (pfad, status_code)


def test_the_two_status_vocabularies_stay_separate() -> None:
    spec = _artefakt()

    for name in (
        "ScanSummary",
        "ScoringRunSummary",
        "CriterionScoringRunSummary",
        "ReviewCreatedOut",
        "ReviewListItemOut",
        "ReviewDetailOut",
    ):
        ref = _schema(spec, name)["properties"]["status"]
        assert _ref_name(ref) == "ScanStatus", name

    for name in ("ExportRunSummary", "ExportRunDetailOut"):
        ref = _schema(spec, name)["properties"]["status"]
        assert _ref_name(ref) == "ExportRunStatus", name

    # Die Vorgangsuebersicht fuehrt beide Laeufe in EINER Liste - dort ist die Union richtig.
    betrieb = _schema(spec, "OperationOut")["properties"]["status"]
    varianten = {_ref_name(variante) for variante in betrieb.get("anyOf", [])}
    assert varianten == {"ScanStatus", "ExportRunStatus"}


# --- Verhaltensregeln an ihrem Ort --------------------------------------------------------------

REGELSTELLEN: tuple[tuple[str, str], ...] = (
    ("ScanSummary", "total_files"),
    ("CloudPhaseSummaryOut", "photos_total"),
    ("CloudPhaseSummaryOut", "photos_processed"),
    ("CloudPhaseSummaryOut", "failed_calls"),
    ("CloudPhaseSummaryOut", "responses_used"),
    ("CloudPhaseSummaryOut", "input_tokens"),
    ("CloudPhaseSummaryOut", "output_tokens"),
    ("CloudPhaseSummaryOut", "cost_usd"),
    ("ClassificationEstimatePartOut", "price_per_image_usd"),
    ("ClassificationEstimatePartOut", "candidate_count"),
    ("CriterionScoringRunSummary", "phase_remaining_seconds"),
)


class TestTheBehaviourRulesStandAtTheirField:
    def test_each_null_rule_carries_a_description_with_its_keyword(self) -> None:
        spec = _artefakt()

        for schema_name, field in REGELSTELLEN:
            beschreibung = _schema(spec, schema_name)["properties"][field].get("description", "")
            assert beschreibung.strip(), f"{schema_name}.{field}: keine Beschreibung"
            assert "null" in beschreibung.lower(), f"{schema_name}.{field}: Stichwort 'null' fehlt"

    def test_the_scan_status_explains_queued(self) -> None:
        beschreibung = _schema(_artefakt(), "ScanStatus").get("description", "")

        assert "queued" in beschreibung
        assert "angenommen" in beschreibung

    def test_the_export_status_and_detail_explain_partial_failure(self) -> None:
        spec = _artefakt()

        for name in ("ExportRunStatus", "ExportRunDetailOut"):
            beschreibung = _schema(spec, name).get("description", "")
            assert "success" in beschreibung, name

    def test_the_export_detail_carries_no_cancel_marker(self) -> None:
        """Der Abbruchmerker gehoert zum Polling-Zustand (`ExportRunSummary`), nicht zum Detail."""
        properties = _schema(_artefakt(), "ExportRunDetailOut")["properties"]

        assert "cancel_requested_at" not in properties
        assert "cancel_requested_at" in _schema(_artefakt(), "ExportRunSummary")["properties"]
