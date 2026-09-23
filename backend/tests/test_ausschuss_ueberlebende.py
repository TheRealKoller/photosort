"""Das Ueberlebenden-Praedikat: wer den Ausschuss-Schritt ueberlebt (ADR 0104 Punkt 3).

    DISCARD ueberlebt nie · KEEP ueberlebt, solange duplicate_of IS NOT NULL ·
    sonst entscheidet suggested_status

DIE WAHRHEITSTABELLE STEHT IN EINEM FALL FUER BEIDE FASSUNGEN. SQL-Fassung (korrelierte
Skalar-Unterabfrage) und Objektfassung werden ueber DEMSELBEN Datenbestand gemessen und
miteinander verglichen; zwei getrennt hingeschriebene Erwartungswerte liessen sie auseinander
laufen, und genau daran haengt, welche Bilddaten den Homeserver verlassen.

"UEBERLEBENDER" UND "OFFENER VORSCHLAG" SIND NICHT KOMPLEMENTAER (AK5): Eine mit `Ausschuss`
entschiedene Aufnahme ist weder das eine noch das andere. Eine Umsetzung, die "offener Vorschlag"
als `NOT ueberlebt` schreibt, liefert plausible, falsche Listen - deshalb tragen beide Mengen hier
ihre eigene Tabelle ueber demselben Bestand.
"""

from __future__ import annotations

import ast
import re
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from photosort.duplicates import (
    has_open_suggestion,
    has_open_suggestion_for,
    survives_ausschuss,
    survives_ausschuss_for,
)
from photosort.models import (
    DuplicateDecision,
    Photo,
    PhotoDuplicateDecision,
    PhotoScore,
    Project,
    RatingStatus,
)

_BASE = datetime(2023, 5, 1, 12, 0, 0)

# Die drei Achsen der Wahrheitstabelle. Die dritte (`duplicate_of`) traegt Auflage S3: Sie ist der
# Unterschied zwischen "der Nutzer hat die DUPLIKATFRAGE beantwortet" und "der Nutzer hat eine
# Ablehnung aufgehoben, zu der er nie befragt wurde".
_ENTSCHEIDUNGEN: tuple[DuplicateDecision | None, ...] = (
    None,
    DuplicateDecision.KEEP,
    DuplicateDecision.DISCARD,
)
_VORSCHLAEGE: tuple[RatingStatus | None, ...] = (None, RatingStatus.REJECTED)
_IST_VERLIERER: tuple[bool, ...] = (False, True)


def _ueberlebt(
    decision: DuplicateDecision | None, suggested: RatingStatus | None, verlierer: bool
) -> bool:
    """Die Zusage in Prosa, unabhaengig von jeder Umsetzung ausgeschrieben - damit die Erwartung
    nicht dieselbe Verzweigung ist wie der Code, gegen den sie prueft."""
    if decision is DuplicateDecision.DISCARD:
        return False
    if decision is DuplicateDecision.KEEP and verlierer:
        return True
    return suggested is None


def _ist_offener_vorschlag(
    decision: DuplicateDecision | None, suggested: RatingStatus | None, verlierer: bool
) -> bool:
    """Ein Vorschlag ist offen, solange er GESTELLT und nicht beantwortet ist. `verlierer` spielt
    keine Rolle - der Grund des Vorschlags ist fuer seine Offenheit ohne Belang."""
    return suggested is not None and decision is None


async def _project(session: AsyncSession, name: str = "Costa Rica") -> Project:
    project = Project(name=name, opencloud_drive_id="d", opencloud_path="/a")
    session.add(project)
    await session.flush()
    return project


async def _photo(
    session: AsyncSession,
    project: Project,
    path: str,
    *,
    minutes: int = 0,
    with_score: bool = True,
    suggested_status: RatingStatus | None = None,
    duplicate_of: int | None = None,
    decision: DuplicateDecision | None = None,
) -> Photo:
    taken_at = _BASE + timedelta(minutes=minutes)
    photo = Photo(
        project_id=project.id,
        relative_path=path,
        etag="etag",
        content_length=1,
        taken_at=taken_at,
        taken_at_original=taken_at,
        last_modified=taken_at,
    )
    session.add(photo)
    await session.flush()
    if with_score:
        session.add(
            PhotoScore(
                photo_id=photo.id,
                sharpness=0.5,
                exposure=0.5,
                suggested_status=suggested_status,
                duplicate_of=duplicate_of,
                computed_at=taken_at,
            )
        )
    if decision is not None:
        session.add(PhotoDuplicateDecision(photo_id=photo.id, decision=decision))
    await session.flush()
    return photo


async def _loaded_photos(session: AsyncSession, project_id: int) -> list[Photo]:
    return list(
        (
            await session.execute(
                select(Photo)
                .where(Photo.project_id == project_id)
                .options(selectinload(Photo.score), selectinload(Photo.duplicate_decision))
            )
        ).scalars()
    )


async def _build_truth_table(session: AsyncSession) -> tuple[Project, dict[int, tuple[bool, bool]]]:
    """Alle zwoelf Kombinationen als eigene Fotos, plus ein Foto ganz ohne `PhotoScore`.

    Rueckgabe: Projekt und je Foto-Id das erwartete Paar (ueberlebt, offener Vorschlag)."""
    project = await _project(session)
    # Der Repraesentant, auf den die Verlierer zeigen duerfen. Er selbst traegt kein
    # `duplicate_of` und steht ausserhalb der Tabelle.
    representative = await _photo(session, project, "repraesentant.jpg", minutes=0)

    erwartet: dict[int, tuple[bool, bool]] = {}
    minute = 1
    for decision in _ENTSCHEIDUNGEN:
        for suggested in _VORSCHLAEGE:
            for verlierer in _IST_VERLIERER:
                photo = await _photo(
                    session,
                    project,
                    f"fall-{minute}.jpg",
                    minutes=minute,
                    suggested_status=suggested,
                    duplicate_of=representative.id if verlierer else None,
                    decision=decision,
                )
                erwartet[photo.id] = (
                    _ueberlebt(decision, suggested, verlierer),
                    _ist_offener_vorschlag(decision, suggested, verlierer),
                )
                minute += 1

    # SICHERHEIT (S2): Der innere Join auf `PhotoScore` bleibt ein innerer Join. Ein Foto ohne
    # Bewertungsgrundlage ist weder Ueberlebender noch offener Vorschlag - ein Umbau auf einen
    # Outer Join zoege es in beide Mengen.
    ohne_score = await _photo(session, project, "ohne-score.jpg", minutes=minute, with_score=False)
    erwartet[ohne_score.id] = (False, False)
    # Der Repraesentant selbst traegt keinen Vorschlag und keine Entscheidung.
    erwartet[representative.id] = (True, False)

    await session.commit()
    return project, erwartet


async def test_the_survivor_predicate_matches_the_truth_table_in_both_fassungen(
    db_session: AsyncSession,
) -> None:
    """DIE Zusage dieses Moduls. Beide Fassungen werden gegen dieselbe Tabelle UND gegeneinander
    gemessen: Ein Auseinanderlaufen bedeutet, dass die Oberflaeche eine andere Menge anzeigt als
    der Lauf sendet."""
    project, erwartet = await _build_truth_table(db_session)

    sql_ids = set(
        (
            await db_session.execute(
                select(Photo.id)
                .join(PhotoScore, PhotoScore.photo_id == Photo.id)
                .where(Photo.project_id == project.id, survives_ausschuss())
            )
        )
        .scalars()
        .all()
    )
    objekt_ids = {
        photo.id
        for photo in await _loaded_photos(db_session, project.id)
        if survives_ausschuss_for(photo)
    }
    erwartete_ids = {photo_id for photo_id, (ueberlebt, _) in erwartet.items() if ueberlebt}

    assert sql_ids == erwartete_ids
    assert objekt_ids == erwartete_ids
    assert sql_ids == objekt_ids


async def test_the_open_suggestion_predicate_matches_the_truth_table_in_both_fassungen(
    db_session: AsyncSession,
) -> None:
    project, erwartet = await _build_truth_table(db_session)

    sql_ids = set(
        (
            await db_session.execute(
                select(Photo.id)
                .join(PhotoScore, PhotoScore.photo_id == Photo.id)
                .where(Photo.project_id == project.id, has_open_suggestion())
            )
        )
        .scalars()
        .all()
    )
    objekt_ids = {
        photo.id
        for photo in await _loaded_photos(db_session, project.id)
        if has_open_suggestion_for(photo)
    }
    erwartete_ids = {photo_id for photo_id, (_, offen) in erwartet.items() if offen}

    assert sql_ids == erwartete_ids
    assert objekt_ids == erwartete_ids
    assert sql_ids == objekt_ids


async def test_survivor_and_open_suggestion_are_not_complements(db_session: AsyncSession) -> None:
    """AK5 ausdruecklich: Eine mit `Ausschuss` entschiedene Aufnahme ist WEDER Ueberlebende NOCH
    offener Vorschlag. Ohne diesen Fall bestuende eine Umsetzung, die die eine Menge als Negation
    der anderen bildet."""
    project, erwartet = await _build_truth_table(db_session)
    photos = await _loaded_photos(db_session, project.id)

    weder_noch = {
        photo.id
        for photo in photos
        if not survives_ausschuss_for(photo) and not has_open_suggestion_for(photo)
    }

    assert weder_noch, (
        "Die beiden Mengen decken zusammen den ganzen Bestand ab - dann ist die eine als "
        "Negation der anderen gebaut."
    )
    assert not any(
        survives_ausschuss_for(photo) and has_open_suggestion_for(photo) for photo in photos
    )
    assert len(weder_noch) == sum(
        1 for ueberlebt, offen in erwartet.values() if not ueberlebt and not offen
    )


@pytest.mark.parametrize(
    ("decision", "suggested", "verlierer", "ueberlebt"),
    [
        # S3, Richtung eins: `keep` auf einen Duplikat-Verlierer WIRKT - das ist der Zweck der
        # Story.
        (DuplicateDecision.KEEP, RatingStatus.REJECTED, True, True),
        # S3, Richtung zwei: `keep` auf eine wegen Unschaerfe abgelehnte Aufnahme OHNE
        # `duplicate_of` wirkt NICHT. Sonst hoebe eine Antwort auf die Duplikatfrage eine
        # Ablehnung auf, zu der der Nutzer nie befragt wurde.
        (DuplicateDecision.KEEP, RatingStatus.REJECTED, False, False),
        # S3, Richtung drei: `discard` wirkt UNBEDINGT - auch auf eine Aufnahme, die gar keinen
        # Vorschlag trug. Das ist die Richtung, die den abfliessenden Bestand verkleinert.
        (DuplicateDecision.DISCARD, None, False, False),
        # AK12: Ein `keep` wird von selbst wirkungslos, sobald die Aufnahme kein Verlierer mehr
        # ist - und faellt dann auf `suggested_status` zurueck statt die Aufnahme zu entfernen.
        (DuplicateDecision.KEEP, None, False, True),
    ],
)
async def test_the_three_directions_of_s3_stand_in_one_parametrisation(
    db_session: AsyncSession,
    decision: DuplicateDecision,
    suggested: RatingStatus | None,
    verlierer: bool,
    ueberlebt: bool,
) -> None:
    """Getrennt geschrieben bestuende jede Haelfte auch gegen eine Umsetzung, die IMMER oder NIE
    uebersteuert."""
    project = await _project(db_session)
    representative = await _photo(db_session, project, "w.jpg")
    photo = await _photo(
        db_session,
        project,
        "p.jpg",
        minutes=1,
        suggested_status=suggested,
        duplicate_of=representative.id if verlierer else None,
        decision=decision,
    )
    await db_session.commit()

    sql_ids = set(
        (
            await db_session.execute(
                select(Photo.id)
                .join(PhotoScore, PhotoScore.photo_id == Photo.id)
                .where(Photo.id == photo.id, survives_ausschuss())
            )
        )
        .scalars()
        .all()
    )

    assert (photo.id in sql_ids) is ueberlebt


async def test_an_unknown_stored_value_falls_to_the_withholding_side(
    db_session: AsyncSession,
) -> None:
    """SICHERHEIT (S2), fail-closed: Die Spalte ist eine Zeichenkette, der Wertevorrat wird von der
    Datenbank NICHT erzwungen. Ein unerwarteter Wert darf nie zum Abfluss fallen - deshalb wird
    POSITIV auf `keep` geprueft statt negativ auf `discard`."""
    project = await _project(db_session)
    photo = await _photo(db_session, project, "p.jpg")
    await db_session.execute(
        PhotoDuplicateDecision.__table__.insert().values(photo_id=photo.id, decision="VIELLEICHT")
    )
    await db_session.commit()

    sql_ids = set(
        (
            await db_session.execute(
                select(Photo.id)
                .join(PhotoScore, PhotoScore.photo_id == Photo.id)
                .where(Photo.id == photo.id, survives_ausschuss())
            )
        )
        .scalars()
        .all()
    )

    assert sql_ids == set()


# ------------------------------------------------------------------------------------------
# Die Zahl der Aufrufstellen als Sollgroesse
# ------------------------------------------------------------------------------------------

_SRC = Path(__file__).resolve().parent.parent / "src" / "photosort"

# Die Vergleichsformen, die die Bedingung VON HAND wiederholen. Prosa in Kommentaren
# ("PhotoScore.suggested_status IS NULL") faellt nicht darunter - sie beschreibt, sie entscheidet
# nicht.
_HANDGESCHRIEBEN = re.compile(
    r"suggested_status\s*\.\s*is_(?:not_)?\(\s*None\s*\)|suggested_status\s+is\s+(?:not\s+)?None"
)

# ZWEI ZAEHLWEISEN, DIE NICHT DIESELBE ZAHL ERGEBEN - hier auseinandergehalten, weil ihre
# Vermischung genau die Sorte Fund erzeugt, die keiner ist:
#
# * ERSETZTE VORKOMMEN: SECHS. So zaehlen Spec 0374, ADR 0104 Punkt 3 und das Sicherheitskonzept,
#   und so stand `PhotoScore.suggested_status IS NULL` vorher ausgeschrieben da. Diese Zahl wird
#   in den Dokumenten NICHT nachgezogen - sie beschreibt den abgeloesten Zustand.
# * NEUE AUFRUFSTELLEN: die Sollgroesse dieses Waechters (die Tabelle direkt darunter). Die eine
#   Bedingung zerfaellt in ZWEI Funktionen ("ueberlebt" und "offener Vorschlag", seit ADR 0104 nicht
#   mehr komplementaer), und "der Vorschlags-Zweig" war schon vorher zwei Codeformen - eine SQL- und
#   eine Objektfassung, die der Paritaetstest aneinander band. Seit Spec 0525 treten der Massenweg,
#   die projektweite `open_count` und der neue Bestand `has_ausschuss_entry` hinzu.
#
# Wer beide verwechselt, "korrigiert" die Tabelle unten auf sechs und haelt den dann roten Test
# fuer einen Fund.
_ERSETZTE_VORKOMMEN = 6

# Je Aufrufstelle steht DA, WELCHE der vier Funktionen dort gezogen wird - nicht bloss eine Zahl je
# Datei. Nur so faellt ein Vertauschen auf: `has_open_suggestion` an einer cloud-bestimmenden
# Stelle liefert eine plausible Menge und dieselbe Gesamtzahl.
_ERWARTETE_VERWENDUNGEN = {
    # run_criterion_scoring (speist zugleich den Sehenswuerdigkeits-Teilschritt) und
    # select_remote_category_candidates - beide cloud-bestimmend (S1).
    ("worker.py", "survives_ausschuss"): 2,
    # Die beiden Kostenschaetzungen, auf denen die Freigabe eines kostenpflichtigen Laufs beruht.
    # Sie folgen der Auswahl NICHT von selbst (S1).
    ("api/projects.py", "survives_ausschuss"): 2,
    # Spec 0525: die Auswahlmenge des Massenwegs im Abschluss des Ausschuss-Schritts. Die Menge
    # bestimmt der SERVER aus dem offenen Vorschlag - eine mitgeschickte Id-Liste wird nie gelesen.
    ("api/projects.py", "has_open_suggestion"): 1,
    # `is_candidate` - Anzeige, keine Grenze.
    ("api/photos.py", "survives_ausschuss_for"): 1,
    # Der Vorschlags-Zweig von `_filtered_photo_ids` und der Objekt-Zwilling `has_suggestion`; dazu
    # seit Spec 0525 die projektweite `open_count` des Ausschuss-Lesepfads.
    ("api/photos.py", "has_open_suggestion"): 2,
    ("api/photos.py", "has_open_suggestion_for"): 1,
    # Spec 0525: der Ausschuss-BESTAND der Uebersicht - die VEREINIGUNG beider Ursachen, eine eigene
    # Praesenzgrenze neben den vier obigen und deshalb hier als eigener Name gefuehrt (Auflage S9:
    # keine zweite, von Hand geschriebene Fassung von `PhotoScore.suggested_status` im Lesepfad).
    ("api/photos.py", "has_ausschuss_entry"): 1,
}

# Die beiden Fassungen, getrennt gezaehlt: Nur die SQL-Fassungen treten als weiterer
# Konjunktionsteil in eine bestehende Anweisung ein (Auflage S2) - die Objektfassungen lesen ein
# bereits geladenes Foto.
_SQL_FASSUNGEN = frozenset({"survives_ausschuss", "has_open_suggestion", "has_ausschuss_entry"})


def _quelldateien() -> list[Path]:
    return sorted(path for path in _SRC.rglob("*.py") if path.name != "duplicates.py")


def test_no_source_file_writes_the_survivor_condition_by_hand() -> None:
    """DER benannte Fehlgriff aus ADR 0104 Punkt 3: das Praedikat in die Lesepfade der Oberflaeche
    zu legen und eine der vier cloud-bestimmenden Stellen beim alten `suggested_status IS NULL` zu
    belassen. Dann verlassen ausdruecklich verworfene Aufnahmen den Homeserver, behaltene fehlen in
    der Bewertung, und die Schaetzung nennt eine andere Zahl als der Lauf sendet - alles drei ohne
    Fehler und ohne Meldung."""
    treffer = {
        str(path.relative_to(_SRC)): _HANDGESCHRIEBEN.findall(path.read_text(encoding="utf-8"))
        for path in _quelldateien()
    }

    assert {datei: funde for datei, funde in treffer.items() if funde} == {}


_PRAEDIKATSNAMEN = frozenset(
    {
        "survives_ausschuss",
        "survives_ausschuss_for",
        "has_open_suggestion",
        "has_open_suggestion_for",
        # Spec 0525: der Ausschuss-Bestand (die VEREINIGUNG beider Ursachen) - eine eigene
        # Praesenzgrenze neben den vier obigen, hier gefuehrt, damit ihre Aufrufstelle nicht
        # unbemerkt wegfaellt.
        "has_ausschuss_entry",
    }
)


def _aufrufe(quelle: str) -> dict[str, int]:
    """Gezaehlt werden AUFRUFE im Syntaxbaum, nie Vorkommen im Text. Ein Verweis in einem
    Doc-Block traegt denselben Namen und ist keine Verwendungsstelle - eine textuelle Zaehlung
    haenge daran, wie die Doku formuliert ist."""
    gezaehlt: dict[str, int] = {}
    for knoten in ast.walk(ast.parse(quelle)):
        if (
            isinstance(knoten, ast.Call)
            and isinstance(knoten.func, ast.Name)
            and knoten.func.id in _PRAEDIKATSNAMEN
        ):
            gezaehlt[knoten.func.id] = gezaehlt.get(knoten.func.id, 0) + 1
    return gezaehlt


def _gemessene_verwendungen() -> dict[tuple[str, str], int]:
    dateien = {relativ for relativ, _name in _ERWARTETE_VERWENDUNGEN}
    return {
        (relativ, name): anzahl
        for relativ in sorted(dateien)
        for name, anzahl in _aufrufe((_SRC / relativ).read_text(encoding="utf-8")).items()
    }


def test_the_predicates_are_drawn_at_exactly_the_expected_call_sites() -> None:
    """Die Zahl der Verwendungsstellen ist selbst eine Sollgroesse. Ein Wegfall faellt sonst nicht
    auf: Eine Stelle, die das Praedikat schlicht nicht mehr zieht, liefert weiterhin eine
    plausible Menge.

    Geprueft wird je (Datei, Funktion), nicht je Datei: Ein Vertauschen der beiden Praedikate -
    `has_open_suggestion` an einer cloud-bestimmenden Stelle - liefert eine plausible Menge und
    dieselbe Gesamtzahl."""
    assert _gemessene_verwendungen() == _ERWARTETE_VERWENDUNGEN


def test_the_six_replaced_occurrences_and_the_written_call_sites_are_held_side_by_side() -> None:
    """Die beiden Zaehlweisen stehen hier NEBENEINANDER, damit ihre Differenz eine erklaerte
    Groesse ist statt eines Verdachts.

    Die sechs ersetzten Vorkommen der Dokumente werden zu mehr Aufrufstellen, weil die eine
    Bedingung in ZWEI Funktionen zerfaellt und "der Vorschlags-Zweig" schon vorher zwei Codeformen
    war; seit Spec 0525 treten Massenweg, projektweite `open_count` und der Bestand
    `has_ausschuss_entry` hinzu. Ein Teil davon sind SQL-Fassungen und treten als weiterer
    Konjunktionsteil in eine bestehende Anweisung ein (Auflage S2); die zwei Objektfassungen lesen
    ein bereits geladenes Foto."""
    gemessen = _gemessene_verwendungen()
    sql = sum(anzahl for (_datei, name), anzahl in gemessen.items() if name in _SQL_FASSUNGEN)

    assert _ERSETZTE_VORKOMMEN == 6
    assert sum(gemessen.values()) == 10
    assert sql == 8
    assert sum(gemessen.values()) - sql == 2
