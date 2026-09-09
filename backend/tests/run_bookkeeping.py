"""Die Bindungs-Invariante zwischen Live-Zaehler und Kosten-Buchfuehrung eines Cloud-Laufs.

specs/features/0348-klassifizierungs-transparenz.md, decisions/0068-klassifizierungslauf-vier-
teilschritte-und-laufeigene-cloud-bilanz.md Punkt 2.

Mit ADR 0068 steht erstmals ein LAUFEND fortgeschriebener Zaehler unmittelbar neben einer
EINGEFRORENEN Kosten-Buchfuehrung: `photos_processed`/`failed_calls` wachsen je
`asyncio.gather`-Block, `api_calls` wird einmal am Phasenende geschrieben. Die Fehlerzahl ist
damit doppelt vorhanden (`photos_processed - api_calls` liefert sie nach dem Lauf ebenfalls) -
bewusst, weil die Story sie WAEHREND des Laufs verlangt. Genau deshalb braucht es eine
gemeinsame, an einer Stelle formulierte Zusage, dass die beiden Wege nicht auseinanderlaufen:

    photos_processed == api_calls + failed_calls

Hier statt in einer der beiden Testdateien, weil beide Phasen (Landmark in
test_worker_criterion_scoring.py, Remote-Kategorie in
test_worker_remote_category_classification.py) dieselbe Zusage tragen und zwei Kopien driften
wuerden.
"""

from __future__ import annotations

from photosort.models import CriterionScoringRun, RemoteCategoryClassificationRun


def assert_call_bookkeeping_invariant(
    run: CriterionScoringRun | RemoteCategoryClassificationRun,
) -> None:
    """Prueft die Invariante fuer den Cloud-Anteil des uebergebenen Laufs.

    UEBERSPRUNGEN, solange die Phase nicht betreten wurde (`failed_calls is None`): dort steht der
    Live-Zaehler auf `NULL` = "nicht erfasst", waehrend die Buchfuehrungsspalte ihren Python-Default
    `0` traegt - ein Vergleich liefe in `0 == 0 + None`. Das ist keine Nachlaessigkeit, sondern die
    Vierfeldertafel selbst: "Phase nicht betreten" ist kein Zustand, ueber den die Invariante
    etwas aussagt.
    """
    if isinstance(run, CriterionScoringRun):
        processed = run.landmark_photos_processed
        api_calls = run.landmark_api_calls
        failed_calls = run.landmark_failed_calls
        label = "landmark"
    else:
        processed = run.photos_processed
        api_calls = run.api_calls
        failed_calls = run.failed_calls
        label = "remote_category"

    if failed_calls is None:
        assert processed is None or isinstance(run, RemoteCategoryClassificationRun), (
            f"{label}: failed_calls ist NULL (Phase nicht betreten), der Live-Fortschritt steht "
            f"aber auf {processed} - beide Zaehler werden gemeinsam gesetzt."
        )
        return

    assert processed is not None, f"{label}: failed_calls erfasst, photos_processed aber NULL"
    assert api_calls is not None, f"{label}: failed_calls erfasst, api_calls aber NULL"
    assert processed == api_calls + failed_calls, (
        f"{label}: photos_processed={processed} != api_calls={api_calls} + "
        f"failed_calls={failed_calls}"
    )
