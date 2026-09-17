"""Die Bindung von `phase` und `phase_started_at` als Nachsatz jedes Worker-Falls, der einen
Klassifizierungslauf bewegt.

Bewusst kein `test_*`-Modul (wird nicht eingesammelt) - Muster `time_offset_invariant.py`.

Zugesichert wird ADR 0116, Punkt 1: Beide Spalten werden ausschliesslich gemeinsam gesetzt.
`phase IS NULL` heisst "kein laufender Teilschritt", und `phase_started_at` ist es dann mit.
Faellt die Bindung, rechnet die Restdauer den Beginn des VORIGEN Teilschritts gegen den
Fortschritt des aktuellen: Die Anzeige ist dann zu gross - ohne Fehler, ohne Ausnahme und ohne
dass ein Verhaltenstest rot wird.

Der strukturelle Waechter in `test_models.py` deckt die statisch sichtbaren Schreibformen ab;
`setattr` und ein gerechneter Spaltenname sind ihm unsichtbar. Dagegen steht diese Datei.
"""

from __future__ import annotations

from datetime import datetime
from itertools import pairwise

from photosort.models import ClassificationPhase, CriterionScoringRun


def assert_phase_binding(run: CriterionScoringRun) -> None:
    """Die Bindung an EINER Lauf-Zeile: entweder beide Felder gesetzt oder beide leer."""
    assert (run.phase is None) == (run.phase_started_at is None), (
        f"Lauf {run.id} verletzt die Bindung aus ADR 0116 Punkt 1: phase={run.phase!r}, "
        f"phase_started_at={run.phase_started_at!r}. Beide Spalten werden ausschliesslich "
        "gemeinsam gesetzt (worker.py::_set_phase)."
    )


def assert_phase_starts_strictly_increase(
    observed: list[tuple[ClassificationPhase | None, datetime | None]],
) -> None:
    """Der zweite Teil der Zusage: Bei JEDEM Phasenwechsel waechst der Zeitstempel streng.

    Ohne diese Haelfte bestuende die Bindung oben auch gegen ein `_set_phase`, das `phase`
    fortschreibt und den ALTEN Zeitstempel stehen laesst - genau der Fehler, den ADR 0116
    beschreibt, und er faellt sonst nirgends auf.

    Erwartet wird die bereits auf Wechsel zusammengefaltete Abfolge (ein Eintrag je Teilschritt).
    """
    assert observed, "Keine Phasenbeobachtung aufgezeichnet - der Nachsatz prueft dann nichts."

    for (phase, started_at), (next_phase, next_started_at) in pairwise(observed):
        assert (phase is None) == (started_at is None), (
            f"Teilschritt {phase!r} verletzt die Bindung: phase_started_at={started_at!r}."
        )
        if next_phase is None:
            # Der Abschluss: `phase = NULL` nimmt den Beginn mit. Kein Wachstumsvergleich.
            assert next_started_at is None, (
                "Der beendete Lauf traegt keinen Teilschritt mehr, aber noch einen Phasenbeginn: "
                f"{next_started_at!r}."
            )
            continue
        assert started_at is not None and next_started_at is not None
        assert next_started_at > started_at, (
            f"Der Wechsel {phase!r} -> {next_phase!r} hat den Phasenbeginn nicht fortgeschrieben: "
            f"{started_at!r} -> {next_started_at!r}. Der neue Teilschritt rechnete dann mit dem "
            "Beginn des vorigen, und die Restdauer waere zu gross."
        )
