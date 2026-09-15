"""Der ANGEZEIGTE Zustand der Vergleichsansicht: `effective_decision_for`/`keep_possible_for`.

Die Ansicht zeigt nicht die Entscheidungszeile, sondern die Auswertung des Ueberlebens-Praedikats
(ADR 0111). Beide Funktionen ziehen dasselbe `_survives` wie `survives_ausschuss_for` -
`keep_possible_for` mit einem HYPOTHETISCHEN `KEEP` statt der tatsaechlichen Zeile. Es ist
ausdruecklich KEINE zweite Regel neben ADR 0104 Punkt 3.

DIE ERWARTUNG STEHT IN PROSA, nicht als zweite Verzweigungsfassung: Eine Erwartung, die dieselbe
Verzweigung wie der Code ist, bestuende auch gegen denselben Denkfehler in beiden.

DER FALL "OHNE `PhotoScore`-ZEILE" IST DER TRENNENDE (Auflage S3). Ein Repraesentant braucht
strukturell keine eigene Zeile, um referenziert zu werden - `load_duplicate_links` joint deshalb
aeusser. Eine Umsetzung, die an `survives_ausschuss_for` delegiert, bildet den INNEREN Join nach,
antwortet dort `False` und zeigte den Gruppengewinner als unumkehrbaren Ausschuss.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from photosort.api.photos import _suggestion_reason
from photosort.duplicates import effective_decision_for, keep_possible_for
from photosort.models import (
    DuplicateDecision,
    Photo,
    PhotoDuplicateDecision,
    PhotoScore,
    RatingStatus,
)

_ENTSCHEIDUNGEN: tuple[DuplicateDecision | None, ...] = (
    None,
    DuplicateDecision.KEEP,
    DuplicateDecision.DISCARD,
)
_VORSCHLAEGE: tuple[RatingStatus | None, ...] = (
    None,
    RatingStatus.ALBUM_WORTHY,
    RatingStatus.REJECTED,
)
_VERLIERER: tuple[bool, ...] = (False, True)


def _photo(
    *,
    with_score: bool = True,
    suggested_status: RatingStatus | None = None,
    duplicate_of: int | None = None,
    decision: DuplicateDecision | None = None,
) -> Photo:
    """Ein Foto rein im Speicher - beide Funktionen sind REIN und brauchen keine Datenbank."""
    photo = Photo(
        id=1,
        project_id=1,
        relative_path="p.jpg",
        etag="etag",
        content_length=1,
    )
    photo.score = (
        PhotoScore(
            photo_id=1,
            sharpness=0.5,
            exposure=0.5,
            suggested_status=suggested_status,
            duplicate_of=duplicate_of,
        )
        if with_score
        else None
    )
    photo.duplicate_decision = (
        PhotoDuplicateDecision(photo_id=1, decision=decision) if decision is not None else None
    )
    return photo


def _ueberlebt(
    decision: DuplicateDecision | None, suggested: RatingStatus | None, verlierer: bool
) -> bool:
    """Die Zusage aus ADR 0104 Punkt 3, in Prosa ausgeschrieben."""
    if decision is DuplicateDecision.DISCARD:
        return False
    if decision is DuplicateDecision.KEEP and verlierer:
        return True
    return suggested is None


# ------------------------------------------------------------------------------------------
# Die Wahrheitstabelle: 3 x 3 x 2
# ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("decision", _ENTSCHEIDUNGEN)
@pytest.mark.parametrize("suggested", _VORSCHLAEGE)
@pytest.mark.parametrize("verlierer", _VERLIERER)
def test_the_effective_decision_is_the_survivor_predicate_in_every_row(
    decision: DuplicateDecision | None, suggested: RatingStatus | None, verlierer: bool
) -> None:
    photo = _photo(
        suggested_status=suggested, duplicate_of=42 if verlierer else None, decision=decision
    )

    erwartet = (
        DuplicateDecision.KEEP
        if _ueberlebt(decision, suggested, verlierer)
        else (DuplicateDecision.DISCARD)
    )
    assert effective_decision_for(photo) is erwartet


@pytest.mark.parametrize("decision", _ENTSCHEIDUNGEN)
@pytest.mark.parametrize("suggested", _VORSCHLAEGE)
@pytest.mark.parametrize("verlierer", _VERLIERER)
def test_keep_is_possible_exactly_where_a_hypothetical_keep_would_survive(
    decision: DuplicateDecision | None, suggested: RatingStatus | None, verlierer: bool
) -> None:
    """`keep_possible` haengt NICHT an der gespeicherten Entscheidung - es fragt, was ein `keep`
    bewirken WUERDE. Die Parametrisierung ueber `decision` ist genau deshalb da: Eine Umsetzung,
    die die tatsaechliche Zeile mitliest, faellt in den Zeilen mit `discard` auf."""
    photo = _photo(
        suggested_status=suggested, duplicate_of=42 if verlierer else None, decision=decision
    )

    assert keep_possible_for(photo) is _ueberlebt(DuplicateDecision.KEEP, suggested, verlierer)


def test_keep_is_impossible_exactly_in_the_six_rows_without_duplicate_of_and_with_a_suggestion() -> (
    None
):
    """ADR 0111 Punkt 2 als MENGE, nicht Zeile fuer Zeile: `keep_possible` ist `false` genau dann,
    wenn `duplicate_of IS NULL AND suggested_status IS NOT NULL` - unabhaengig von der
    gespeicherten Entscheidung. Das sind sechs der achtzehn Zeilen."""
    unmoeglich = {
        (decision, suggested, verlierer)
        for decision in _ENTSCHEIDUNGEN
        for suggested in _VORSCHLAEGE
        for verlierer in _VERLIERER
        if not keep_possible_for(
            _photo(
                suggested_status=suggested,
                duplicate_of=42 if verlierer else None,
                decision=decision,
            )
        )
    }

    assert unmoeglich == {
        (decision, suggested, False)
        for decision in _ENTSCHEIDUNGEN
        for suggested in _VORSCHLAEGE
        if suggested is not None
    }
    assert len(unmoeglich) == 6


# ------------------------------------------------------------------------------------------
# Die drei tragenden Zeilen und der Fall ohne `PhotoScore`
# ------------------------------------------------------------------------------------------


def test_an_undecided_duplicate_loser_already_reads_as_discard() -> None:
    """DER KERN VON AK1: Genau hier fielen Entscheidungszeile und tatsaechliche Wirkung bisher
    auseinander - die Ansicht zeigte "noch nicht entschieden", der Ausschuss-Schritt sortierte
    aus."""
    verlierer = _photo(suggested_status=RatingStatus.REJECTED, duplicate_of=42)

    assert effective_decision_for(verlierer) is DuplicateDecision.DISCARD
    assert keep_possible_for(verlierer) is True


def test_a_stored_keep_on_a_low_quality_rejection_still_reads_as_discard() -> None:
    """AK3 / ADR 0104 Punkt 3: Ein `keep` OHNE `duplicate_of` wirkt nicht - der Nutzer hat die
    Duplikatfrage beantwortet, nicht die Schaerfefrage. Die Ansicht zeigt deshalb weiter
    `discard` und bietet "behalten" gar nicht erst an."""
    unscharf = _photo(suggested_status=RatingStatus.REJECTED, decision=DuplicateDecision.KEEP)

    assert effective_decision_for(unscharf) is DuplicateDecision.DISCARD
    assert keep_possible_for(unscharf) is False


def test_a_member_without_a_photo_score_row_reads_as_keep_and_stays_changeable() -> None:
    """SICHERHEIT (S3), der trennende Fall. Eine Delegation an `survives_ausschuss_for` bildet den
    INNEREN Join nach und antwortete hier `False` - der Gruppengewinner staende dann als
    unumkehrbarer Ausschuss da, genau verkehrt. Eine Aufrufstelle, die
    `photo.score.suggested_status` liest, wirft hier `AttributeError` und reisst nicht eine Kachel,
    sondern die gesamte Gruppenantwort auf `500`."""
    ohne_score = _photo(with_score=False)

    assert effective_decision_for(ohne_score) is DuplicateDecision.KEEP
    assert keep_possible_for(ohne_score) is True


# ------------------------------------------------------------------------------------------
# Die Aequivalenz zum Begruendungstext der Oberflaeche
# ------------------------------------------------------------------------------------------


def test_keep_impossible_means_exactly_low_quality_among_photos_carrying_a_suggestion() -> None:
    """Der Grund hinter `keep_possible === false` reist NICHT als Feld; die Oberflaeche rendert
    dort den festen Text "wegen geringer Bildqualitaet". Diese Aequivalenz haelt das fest, damit
    ein kuenftiger dritter Ablehnungsgrund LAUT auffaellt statt still den falschen Text zu zeigen.

    Eingeschraenkt auf Aufnahmen MIT Vorschlag: Ohne Vorschlag ist die Grundfrage nicht gestellt,
    und ueber dem vollen Bestand waere die Aussage falsch - das zeigt die zweite Gegenprobe."""
    mit_vorschlag = [
        _photo(suggested_status=suggested, duplicate_of=42 if verlierer else None)
        for suggested in (RatingStatus.ALBUM_WORTHY, RatingStatus.REJECTED)
        for verlierer in _VERLIERER
    ]

    unmoeglich = {id(photo) for photo in mit_vorschlag if not keep_possible_for(photo)}
    low_quality = {
        id(photo)
        for photo in mit_vorschlag
        if photo.score is not None and _suggestion_reason(photo.score) == "low_quality"
    }

    # Gegenprobe gegen die selbsterfuellende Variante: beide Seiten leer waere ebenfalls gleich.
    assert unmoeglich
    assert unmoeglich == low_quality

    # Und die Einschraenkung selbst: OHNE Vorschlag nennt `_suggestion_reason` weiterhin
    # `low_quality`, `keep_possible` ist dort aber `true` - ueber dem vollen Bestand liefe die
    # Aequivalenz also auseinander.
    ohne_vorschlag = _photo()
    assert ohne_vorschlag.score is not None
    assert _suggestion_reason(ohne_vorschlag.score) == "low_quality"
    assert keep_possible_for(ohne_vorschlag) is True


_SRC = Path(__file__).resolve().parent.parent / "src" / "photosort"

# Was der Ausschuss-Lauf in `suggested_status` schreiben darf. `RatingStatus` kennt daneben
# `ALBUM_WORTHY`; truege ein Repraesentant den, waere `keep_possible === false` bei falschem
# Begruendungstext - die Oberflaeche nennt dort fest "wegen geringer Bildqualitaet".
_ERLAUBTE_ZUWEISUNGEN = {"None", "RatingStatus.REJECTED"}


def _zugewiesene_werte() -> set[str]:
    """Jeder Wert, der irgendwo in `backend/src` an ein Attribut `suggested_status` zugewiesen
    wird - ueber den Syntaxbaum, nicht ueber den Text. Schluesselwortargumente eines Konstruktors
    (`PhotoScore(suggested_status=...)`) zaehlen mit: Der Demo-Bestand schreibt so."""
    werte: set[str] = set()
    for pfad in sorted(_SRC.rglob("*.py")):
        baum = ast.parse(pfad.read_text(encoding="utf-8"))
        for knoten in ast.walk(baum):
            if isinstance(knoten, ast.Assign):
                for ziel in knoten.targets:
                    if isinstance(ziel, ast.Attribute) and ziel.attr == "suggested_status":
                        werte.add(ast.unparse(knoten.value))
            elif isinstance(knoten, ast.Call):
                for argument in knoten.keywords:
                    if argument.arg == "suggested_status":
                        werte.add(ast.unparse(argument.value))
    return werte


def test_the_ausschuss_run_writes_only_none_or_rejected_into_suggested_status() -> None:
    """GRUND-WAECHTER hinter dem festen Text der Oberflaeche. `keep_possible === false` traegt
    seine Begruendung nur, solange `suggested_status IS NOT NULL` gleichbedeutend mit "wegen
    geringer Bildqualitaet abgelehnt" ist. Ein geschriebenes `ALBUM_WORTHY` braeche das still: Die
    Kachel zeigte dann "Abgelehnt wegen geringer Bildqualitaet" fuer eine album-wuerdige Aufnahme.

    Ein bedingter Ausdruck wird dabei in seine Zweige zerlegt - `None if x else REJECTED` ist
    zulaessig, `ALBUM_WORTHY if x else None` faellt auf."""
    zweige: set[str] = set()
    for wert in _zugewiesene_werte():
        knoten = ast.parse(wert, mode="eval").body
        if isinstance(knoten, ast.IfExp):
            zweige.update(ast.unparse(teil) for teil in (knoten.body, knoten.orelse))
        else:
            zweige.add(wert)

    assert zweige <= _ERLAUBTE_ZUWEISUNGEN, (
        "Der Ausschuss-Lauf schreibt einen dritten Wert in `suggested_status`. `keep_possible === "
        "false` traegt seine Begruendung dann nicht mehr eindeutig - der Grund gehoert ab da als "
        "eigenes Feld in die Antwort (ADR 0111, Konsequenzen)."
    )
    # Ohne diese Zeile bestuende der Waechter auch dann, wenn er gar nichts mehr faende.
    assert zweige == _ERLAUBTE_ZUWEISUNGEN
