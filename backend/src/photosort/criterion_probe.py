"""REIN LESENDES Messkommando: misst an einem echten Projekt, was die Kriterien-Werte hergeben.

Aufruf::

    docker compose exec -T backend python -m photosort.criterion_probe --project-id 3

Gemessen wird der Vorher/Nachher-Beleg der Spec 0283 auf Material-Ebene: die Verteilung der
gespeicherten Werte der Kriterien ``gebaeude`` und ``landschaft`` und die Zahl der
Landmark-Kandidaten, die daraus folgt. Ein Vorher-Stand liegt NICHT in der Datenbank -
``PhotoCriterionScore`` traegt keinen Laufbezug und wird bei jedem Lauf ueberschrieben
(``UniqueConstraint(photo_id, criterion_key)``). Er wird deshalb GEZOGEN, bevor er ueberschrieben
wird, und nach der Aenderung ein zweites Mal.

Gemessen wird mit den Mitteln des Laufs: ``criteria.py::is_landmark_candidate`` ist dieselbe reine
Schwellenwert-Pruefung, die auch ``worker.py::_select_landmark_candidates`` nimmt, und
``api/projects.py::_count_landmark_candidates`` ist woertlich die Funktion hinter dem angezeigten
``landmark_candidate_count``. Eine zweite, nachbildende Fassung maesse etwas anderes, als der Lauf
tatsaechlich tut, waehrend beide fuer sich gruen blieben.

REIN LESEND, und das ist eine gepruefte Zusage, keine Absicht: kein ``INSERT``/``UPDATE``/
``DELETE``, kein Aufrufpfad aus ``main.py``/``worker.py``, kein Endpunkt, kein
Compose-``command``. Kein Lauf hinterlaesst eine geaenderte, geloeschte oder neue Zeile.
``tests/test_criterion_probe.py`` haelt das dreifach fest - Import-Graph, Syntaxbaum-Waechter
gegen jede Schreibform und ein echter ``main()``-Lauf mit Schnappschuss jeder Tabelle davor und
danach. Kein Teil traegt allein. Der Preis des Formwaechters ist, dass diese Datei auf
``set.add``/``dict.update`` als Sammlungs-Methoden verzichtet.

SICHERHEIT (S2 der Spec 0283):

* DIE AUSGABE TRAEGT KEINEN ``relative_path`` UND KEINEN DATEINAMEN, KEINEN OPENCLOUD-PFAD,
  KEINEN PROJEKTNAMEN, KEINEN ZEITSTEMPEL, KEINE KOORDINATE UND KEINEN ORTS- ODER
  SEHENSWUERDIGKEIT-NAMEN; ausgewiesen wird die Projekt-**Id**. Das ist die Bedingung dafuer, dass
  die Zahlen als Ganzes in einen oeffentlichen Pull Request duerfen.
* AUSGEGEBEN WERDEN AUSSCHLIESSLICH ANZAHLEN UEBER DEN LAUF, NIE EINE ZEILE JE FOTO. Verboten ist
  ausserdem die Verbindung Klassenname <-> einzelnes Foto in jeder Form - kein Beispielabschnitt,
  kein Auszug, auch nicht gekuerzt und auch nicht mit Foto-Id statt Pfad. Eine solche Zeile ist
  eine Aussage darueber, was auf einem bestimmten Familienfoto zu sehen ist; eine Auszaehlung ist
  es nicht. Deshalb KEIN ``--namen``-Schalter (anders als ``place_probe.py``).
* AUSFALLRICHTUNG - "NICHT GEMESSEN" IST NICHT "0": Liegt kein erfolgreicher Kriterien-Lauf vor,
  meldet der Bericht ``NICHT GEMESSEN``, nie eine Null. Eine Null truege hier die Aussage "der
  Zuwachs ist klein" und damit die Abnahme der Spec - dieselbe Regel, die ``api/projects.py`` mit
  ``landmark_candidate_count: int | None`` bereits durchsetzt.
* AUSGABEKANAL: ausschliesslich stdout. Keine Datei-Ausgabe, nichts ueber den strukturierten
  Anwendungs-Logger und damit nichts in persistente Container-Logs. Dieses Modul schreibt kein
  Log.
* EINGABE: ``--project-id`` ist ``argparse type=int``; jeder Datenbankzugriff laeuft ueber
  SQLAlchemy-Konstrukte mit Parameterbindung, nie ueber ``text()`` mit f-String. Ein unbekanntes
  Projekt oder ein Verbindungsfehler ergibt eine kurze eigene Meldung und einen Exit-Code != 0 -
  NIE ein durchgereichter SQLAlchemy-Traceback, der die ``DATABASE_URL`` samt Zugangsdaten in eine
  Ausgabe schriebe, die anschliessend in einen Pull Request kopiert wird (Muster
  ``demo_state.py``).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

# WOERTLICH DIE FUNKTION HINTER DER ANGEZEIGTEN ZAHL, nicht eine zweite Fassung davon: Der Bericht
# weist `landmark_candidate_count` genau so aus, wie die Projekt-Antwort es tut. Eine Nachbildung
# hier liefe beim naechsten Grenzfall auseinander, und der Beleg behauptete dann eine Zahl, die
# niemand zu sehen bekommt. Denselben Weg nimmt `tests/test_worker_criterion_scoring.py` bereits.
from photosort.api.projects import _count_landmark_candidates
from photosort.config import settings
from photosort.criteria import LANDMARK_CANDIDATE_CRITERION_KEYS, is_landmark_candidate
from photosort.db import make_engine, make_session_factory
from photosort.models import (
    CriterionScoringRun,
    Photo,
    PhotoCriterionScore,
    Project,
    ScanStatus,
)

# Eine gelesene Kriterien-Zeile: Foto, Kriterium, Wert. Der Schluessel bleibt im Modul und
# erreicht den Bericht nie - gezaehlt wird ueber ihn, ausgegeben werden Anzahlen (S2).
ScoreRow = tuple[int, str, float]


class CriterionProbeError(Exception):
    """Der Messlauf kann nicht stattfinden (unbekanntes Projekt).

    Meldungen nennen Bedingung und Id, nie einen Konfigurationswert, nie einen Projektnamen und
    nie einen Pfad."""


@dataclass(frozen=True)
class CriterionCounts:
    """Die Verteilung EINES Kriteriums ueber die gespeicherten Werte - in Anzahlen, nie je Foto.

    `at_zero` und `above_zero` sind die beiden Klassen, nach denen die Spec fragt: Ein Wert `> 0`
    heisst "das Kriterium hat auf diesem Foto gegriffen". Bei `gebaeude` faellt beides zusammen
    mit "Landmark-Kandidat" - `compute_gebaeude_score` gibt entweder exakt `0.0` oder einen Wert
    `>= 0.5` zurueck, und die Praesenzgrenze liegt bei 0.01.

    `photos_with_a_value` steht DANEBEN und ist nicht die Fotozahl des Projekts: Ein Foto ohne
    Zeile zu diesem Kriterium ist nicht dasselbe wie ein Foto mit dem Wert null. Ein Lauf, der ein
    Kriterium gar nicht geschrieben hat, faellt sonst mit einem Lauf zusammen, der es ueberall auf
    null gesetzt hat."""

    criterion_key: str
    photos_with_a_value: int
    at_zero: int
    above_zero: int


@dataclass(frozen=True)
class CriterionProbeInput:
    """Der gemessene Bestand, bereits vollstaendig gelesen - ab hier rechnet alles rein.

    `run_id` ist die Kennung des letzten erfolgreichen Kriterien-Laufs; `None` heisst "dieses
    Projekt hat keinen erfolgreichen Lauf" und ist etwas anderes als "ein Lauf ohne Treffer". Der
    Bericht meldet dann `NICHT GEMESSEN`, nie eine Null (S2).

    EIN FELD, NICHT ZWEI: `run_found` ist abgeleitet, nicht daneben gespeichert - ein `True` ohne
    Kennung ergaebe einen Kopf ohne Lauf, ein `False` mit Kennung eine Ausfallmeldung trotz
    messbarer Werte. Abgeleitet ist der Widerspruch nicht darstellbar (Muster `event_probe.py`).

    `landmark_candidates` und `landmark_candidate_count` stehen NEBENEINANDER, weil sie
    verschiedene Mengen sind: die erste ist die reine Schwellenwert-Zaehlung ueber alle
    gespeicherten Werte des Projekts (`criteria.py::is_landmark_candidate`), die zweite die Zahl
    der Projekt-Antwort (`api/projects.py::_count_landmark_candidates`) - dort zusaetzlich auf
    Ausschuss-Ueberlebende eingeschraenkt und um Fotos mit bereits vorhandener `landmark`-Zeile
    verringert. Sie duerfen abweichen; verrechnet wuerde genau diese Aussage verschwinden. `None`
    heisst bei beiden "nicht gemessen"."""

    project_id: int
    photos_total: int
    run_id: int | None
    counts: tuple[CriterionCounts, ...] = ()
    landmark_candidates: int | None = None
    landmark_candidate_count: int | None = None

    @property
    def run_found(self) -> bool:
        return self.run_id is not None


# --- Die Zaehlbloecke, rein ----------------------------------------------------------------------


def criterion_counts(rows: Sequence[ScoreRow]) -> tuple[CriterionCounts, ...]:
    """Je Kriterium aus `LANDMARK_CANDIDATE_CRITERION_KEYS` eine Verteilung - JEDES davon, auch
    das ohne eine einzige Zeile.

    Ein Kriterium, das aus dem Bericht faellt, waere eine still unvollstaendige Messung, ohne dass
    eine Summe kleiner wuerde. Die Grenze ist `> 0.0` und ausdruecklich keine Praesenzgrenze: Die
    Frage der Spec ist "hat das Kriterium ueberhaupt gegriffen", und eine zweite Schwelle hier
    liefe gegen `is_landmark_candidate` auseinander.

    Eine Zeile zu einem anderen Kriterium wird UEBERGANGEN, nicht gezaehlt: Der Lesepfad fragt
    ohnehin nur diese beiden, und eine Zeile mehr duerfte keine Klasse verschieben."""
    above: dict[str, int] = {key: 0 for key in LANDMARK_CANDIDATE_CRITERION_KEYS}
    zero: dict[str, int] = {key: 0 for key in LANDMARK_CANDIDATE_CRITERION_KEYS}
    for _photo_id, criterion_key, value in rows:
        if criterion_key not in above:
            continue
        if value > 0.0:
            above[criterion_key] += 1
        else:
            zero[criterion_key] += 1
    return tuple(
        CriterionCounts(
            criterion_key=key,
            photos_with_a_value=above[key] + zero[key],
            at_zero=zero[key],
            above_zero=above[key],
        )
        for key in LANDMARK_CANDIDATE_CRITERION_KEYS
    )


def landmark_candidates(rows: Sequence[ScoreRow]) -> int:
    """Die Zahl der Fotos, die `criteria.py::is_landmark_candidate` erfuellen - DIESELBE reine
    Funktion, die auch der Live-Lauf fragt.

    Gezaehlt werden FOTOS, nie Zeilen: Ein Foto mit Werten zu beiden Kriterien ist ein Kandidat,
    nicht zwei. Die Werte eines Fotos gehen gemeinsam hinein, weil die Pruefung ein ODER ueber
    beide ist und ein fehlender Wert dort als `0.0` gilt.

    Bewusst OHNE Ausschuss-Einschraenkung und ohne Ausschluss bereits gescorter Fotos: Das ist die
    obere, listenabhaengige Zahl, an der die Aenderung der Allow-Liste unmittelbar abzulesen ist.
    Was davon ein Lauf tatsaechlich hinausgibt, steht als zweite Zahl daneben."""
    values_by_photo: dict[int, dict[str, float]] = {}
    for photo_id, criterion_key, value in rows:
        values_by_photo.setdefault(photo_id, {})[criterion_key] = value
    return sum(1 for values in values_by_photo.values() if is_landmark_candidate(values))


# --- Der Lesepfad --------------------------------------------------------------------------------


async def read_criterion_probe_input(session: AsyncSession, project_id: int) -> CriterionProbeInput:
    """Der EINZIGE Datenbankzugriff dieses Moduls, und er liest ausschliesslich.

    SICHERHEIT: Die Bindung an `project_id` steht in jeder Abfrage ausgeschrieben - gemessen wird
    genau ein Projekt, nie ein Bestand ueber Projektgrenzen hinweg. Gelesen werden ausschliesslich
    die beiden Kriterien aus `LANDMARK_CANDIDATE_CRITERION_KEYS`; kein `relative_path`, kein
    Projektname, kein Zeitstempel verlaesst diese Funktion.

    OHNE ERFOLGREICHEN LAUF WIRD GAR NICHT ERST GEZAEHLT: Es gaebe dann zwar Zeilen aus einem
    frueheren, gescheiterten Zustand, aber keine Messung - und eine Zahl daraus saehe aus wie
    eine."""
    project_id_found = (
        await session.execute(select(Project.id).where(Project.id == project_id))
    ).scalar_one_or_none()
    if project_id_found is None:
        raise CriterionProbeError(f"Es gibt kein Projekt mit der Id {project_id}.")

    photos_total = (
        await session.execute(
            select(Photo.id).where(Photo.project_id == project_id).order_by(Photo.id)
        )
    ).all()

    run_id = (
        await session.execute(
            select(CriterionScoringRun.id)
            .where(
                CriterionScoringRun.project_id == project_id,
                CriterionScoringRun.status == ScanStatus.SUCCESS,
            )
            .order_by(CriterionScoringRun.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if run_id is None:
        return CriterionProbeInput(
            project_id=project_id, photos_total=len(photos_total), run_id=None
        )

    rows: list[ScoreRow] = [
        (photo_id, criterion_key, float(value))
        for photo_id, criterion_key, value in (
            await session.execute(
                select(
                    PhotoCriterionScore.photo_id,
                    PhotoCriterionScore.criterion_key,
                    PhotoCriterionScore.value,
                )
                .join(Photo, Photo.id == PhotoCriterionScore.photo_id)
                .where(
                    Photo.project_id == project_id,
                    PhotoCriterionScore.criterion_key.in_(LANDMARK_CANDIDATE_CRITERION_KEYS),
                )
            )
        ).all()
    ]

    return CriterionProbeInput(
        project_id=project_id,
        photos_total=len(photos_total),
        run_id=run_id,
        counts=criterion_counts(rows),
        landmark_candidates=landmark_candidates(rows),
        # DIE ZAHL DER PROJEKT-ANTWORT, aus ihrer eigenen Funktion: Sie zaehlt gegen
        # `survives_ausschuss()` und laesst Fotos mit vorhandener `landmark`-Zeile weg - beides
        # steht dort und gehoert nicht hierher kopiert.
        landmark_candidate_count=await _count_landmark_candidates(session, project_id),
    )


# --- Die Ausgabe ---------------------------------------------------------------------------------

# Was anstelle einer Zahl steht, wenn nichts gemessen wurde. EINE Zeichenfolge, nicht je
# Fundstelle eine eigene: Sie ist die Ausfallrichtung aus S2 und wird im Bericht gesucht.
NOT_MEASURED = "NICHT GEMESSEN"


def _percent(part: int, whole: int) -> str:
    if whole == 0:
        return "-"
    return f"{100.0 * part / whole:.1f} %"


def _report_head(probe: CriterionProbeInput) -> str:
    """DIE EINE KOPFZEILE des Berichts: Titel, Projekt-Id, Laufkennung.

    BEIDE ZAHLEN SIND INTERNE KENNUNGEN und fallen unter keine der verbotenen Klassen aus S2: kein
    Pfad, kein Dateiname, kein Projektname, kein Zeitstempel, keine Koordinate. Der Projekt-NAME
    waere eine Angabe ueber den Bestand, die Id ist keine.

    OHNE LAUF STEHT KEINE ERFUNDENE KENNUNG DA: Anders als `event_probe.py` bricht dieses Kommando
    nicht ab - "es gibt keinen erfolgreichen Lauf" ist hier selbst das Messergebnis und wird als
    `NICHT GEMESSEN` berichtet. Ein "Lauf 0" oder "Lauf None" waere dagegen eine Kennung, die es
    nicht gibt."""
    if probe.run_id is None:
        return f"# Kriterien-Messung, Projekt {probe.project_id}, ohne erfolgreichen Lauf"
    return f"# Kriterien-Messung, Projekt {probe.project_id}, Lauf {probe.run_id}"


def render_report(probe: CriterionProbeInput) -> str:
    """Markdown nach stdout - AUSSCHLIESSLICH ANZAHLEN (S2).

    Der Bericht traegt keinen `relative_path` und keinen Dateinamen, keinen OpenCloud-Pfad, keinen
    Projektnamen, keinen Zeitstempel, keine Koordinate und keinen Orts- oder
    Sehenswuerdigkeit-Namen; ausgewiesen wird die Projekt-Id. Es gibt keine Zeile je Foto und
    keine Verbindung Klassenname <-> Foto - damit sind die Zahlen als Ganzes weitergebbar, ohne
    Einzelfallpruefung.

    OHNE ERFOLGREICHEN LAUF STEHT UEBERALL `NICHT GEMESSEN`, nie eine Null: Eine Null waere hier
    das guenstigste aller Messergebnisse ("der Zuwachs ist klein") und truege die Abnahme der
    Spec."""
    lines = [
        _report_head(probe),
        "",
        f"- Fotos im Projekt: {probe.photos_total}",
    ]

    if not probe.run_found:
        return (
            "\n".join(
                [
                    *lines,
                    "",
                    f"{NOT_MEASURED} - dieses Projekt hat keinen erfolgreichen Kriterien-Lauf.",
                    "Die Zahlen dieses Berichts fehlen, sie sind NICHT null: Eine Null hiesse",
                    '"kein Foto traegt einen Wert" und waere als Messergebnis genau die',
                    "guenstigste Aussage. Erst einen Kriterien-Lauf durchfuehren, dann messen.",
                ]
            )
            + "\n"
        )

    for counts in probe.counts:
        lines += [
            "",
            f"## Kriterium {counts.criterion_key}",
            "",
            f"- Fotos mit einem gespeicherten Wert: {counts.photos_with_a_value}",
            f"- davon mit Wert 0: {counts.at_zero} "
            f"({_percent(counts.at_zero, counts.photos_with_a_value)})",
            f"- davon mit Wert > 0: {counts.above_zero} "
            f"({_percent(counts.above_zero, counts.photos_with_a_value)})",
        ]

    lines += [
        "",
        "## Landmark-Kandidaten",
        "",
        f"- nach is_landmark_candidate ueber die gespeicherten Werte: "
        f"{_number(probe.landmark_candidates)}",
        f"- landmark_candidate_count der Projekt-Antwort: "
        f"{_number(probe.landmark_candidate_count)}",
        "",
        "Die beiden Zahlen sind VERSCHIEDENE Mengen und werden nicht verrechnet: Die erste zaehlt",
        "jedes Foto des Projekts, dessen gespeicherte Werte die Schwellen erfuellen. Die zweite",
        "ist die Zahl, die die Projekt-Antwort ausweist - sie zaehlt nur Ausschuss-Ueberlebende",
        "und laesst Fotos mit bereits vorhandener landmark-Zeile weg. Zwischen einem Treffer der",
        "Gebaeude-Allow-Liste und der Cloud-Kandidatur liegt keine daempfende Schwelle; die erste",
        "Zahl ist deshalb die, an der eine Aenderung dieser Liste unmittelbar abzulesen ist.",
    ]
    return "\n".join(lines) + "\n"


def _number(value: int | None) -> str:
    """Eine Anzahl - oder `NICHT GEMESSEN`, wenn keine gemessen wurde. Nie eine ersatzweise
    Null: Sie laese sich als Messergebnis lesen, und genau diese Verwechslung schliesst S2 aus."""
    if value is None:
        return NOT_MEASURED
    return str(value)


# --- Verdrahtung ---------------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Genau EIN Schalter, und ausdruecklich kein `--namen` (S2): Dieses Kommando gibt Anzahlen
    aus; die Verbindung Klassenname <-> einzelnes Foto ist in jeder Form verboten, auch hinter
    einem standardmaessig ausgeschalteten Schalter."""
    parser = argparse.ArgumentParser(
        prog="python -m photosort.criterion_probe",
        description=(
            "Misst an einem echten Projekt die Verteilung der Kriterien-Werte und die Zahl der "
            "Landmark-Kandidaten. REIN LESEND - kein Lauf veraendert eine Zeile."
        ),
    )
    parser.add_argument("--project-id", type=int, required=True)
    return parser


async def _probe_with_own_session(database_url: str, *, project_id: int) -> str:
    engine = make_engine(database_url)
    try:
        session_factory = make_session_factory(engine)
        async with session_factory() as session:
            probe = await read_criterion_probe_input(session, project_id)
    finally:
        await engine.dispose()
    return render_report(probe)


def main(argv: Sequence[str] | None = None, *, database_url: str | None = None) -> int:
    """Verdrahtung + Exit-Code. `argv` und `database_url` sind injizierbar - kein
    `sys.argv`-Zugriff im Testpfad und kein unbeabsichtigter Zugriff auf die konfigurierte
    Anwendungs-Datenbank.

    `asyncio.run` laeuft INNERHALB von main(): eine Async-Engine ueberlebt keinen Loop-Wechsel.

    EIN PROJEKT OHNE ERFOLGREICHEN LAUF IST KEIN FEHLER, sondern ein Messergebnis - es wird als
    `NICHT GEMESSEN` berichtet, und der Aufrufer bekommt 0. Ein unbekanntes Projekt ist dagegen
    eine falsche Frage und bekommt 1."""
    args = _build_parser().parse_args(argv)
    try:
        report = asyncio.run(
            _probe_with_own_session(
                database_url or settings.database_url, project_id=args.project_id
            )
        )
    except CriterionProbeError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1
    except SQLAlchemyError as exc:
        # Nur der Fehlertyp, NIE str(exc)/Traceback - die SQLAlchemy-Meldung kann die
        # DATABASE_URL inklusive Zugangsdaten enthalten (Muster demo_state.py).
        print(f"Fehler: Datenbankzugriff fehlgeschlagen ({type(exc).__name__}).", file=sys.stderr)
        return 1
    print(report)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
