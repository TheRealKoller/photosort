"""Der Aufbau der `EventCandidate`-Menge eines Kriterien-Laufs - REIN LESEND.

ZWEI AUFRUFER, EIN WEG: der Lauf (`worker.py::_build_grouping_and_rankings`) und das rein lesende
Messkommando (`event_probe.py`). Eine zweite, nachbildende Fassung maesse etwas anderes, als der
Lauf tatsaechlich tut, waehrend beide fuer sich gruen blieben (ADR 0117 Punkt 5).

REIN LESEND, und das ist eine gepruefte Zusage, keine Absicht: kein ``INSERT``/``UPDATE``/
``DELETE``, kein ``commit``, kein ``flush``. ``tests/test_event_probe.py`` haelt das mit einem
eigenen Syntaxbaum-Waechter fest - JE MODUL, nicht ueber den Import-Graphen: ueber die Import-Huelle
angewandt schluege er auf ``events.py``/``selection.py``/``geonames.py`` an (gleichnamige
Sammlungs-Methoden) und wuerde dann entschaerft. Der Preis ist, dass diese Datei auf ``set.add``,
``dict.update``, ``merge`` und ``delete`` auch als Sammlungs-Methoden verzichtet - eine kleine
Auflage gegen eine lueckenlose Zusage.

Die Import-Graph-Zusage von ``place_probe.py`` gilt hier AUSDRUECKLICH NICHT: dieses Modul liegt
per Konstruktion im Graphen von ``worker.py``, und genau diese Richtung pinnt eine Gegenprobe.

LOGGING-AUFLAGE (S8) fuer jede kuenftige Logzeile dieses Moduls: weder eine Koordinate noch ein
Orts- oder Sehenswuerdigkeit-Name gehoert hinein, nur ein festes Grund-Token und eine Id.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.events import EventCandidate, LocationEntry, infer_locations
from photosort.landmark import usable_landmark_name
from photosort.models import (
    Photo,
    PhotoLandmarkDetection,
    PhotoMotifAssessment,
)
from photosort.motif_strengths import EffectiveStrength, load_effective_strengths


@dataclass(frozen=True)
class EventInputs:
    """Was die Event-Bildung eines Laufs braucht, vollstaendig gelesen - ab hier rechnet alles rein.

    `candidates` ist GENAU die uebergebene Id-Menge, in ihrer Reihenfolge; `entries` ist die
    Inferenzbasis der Ortsherleitung und damit JEDES Foto des Projekts, auch ein aussortiertes.
    Beide stehen nebeneinander, weil sie verschiedene Mengen sind: Die Herleitung aus der
    Kandidatenmenge waere zirkulaer, und ein aussortiertes Foto traegt eine ebenso gueltige
    Koordinate."""

    candidates: tuple[EventCandidate, ...]
    entries: tuple[LocationEntry, ...]


def _plain_strengths(
    effective: Mapping[str, EffectiveStrength] | None,
) -> dict[str, float] | None:
    """Die wirksamen Staerken eines Fotos als blanke Zahlen - `None` BLEIBT `None`.

    Die Abwesenheit der Kopfzeile ist ein eigener Zustand ("noch nicht klassifiziert") und
    ausdruecklich nicht dasselbe wie eine Kopfzeile ohne getragenes Motiv. Ein `.get(photo_id, {})`
    an der Aufrufstelle - wie es der Auswahlvorschlag richtigerweise tut - liesse beide
    zusammenfallen, und ein unklassifiziertes Foto zerrisse dann ein Event, statt uebergangen zu
    werden."""
    if effective is None:
        return None
    return {motif_key: value.strength for motif_key, value in effective.items()}


async def _landmark_names(
    session: AsyncSession, photo_ids: Collection[int]
) -> dict[int, str | None]:
    """Die bereits PERSISTIERTEN Sehenswuerdigkeit-Namen der Kandidaten eines Laufs - ein
    einzelner Lesezugriff, KEIN Cloud-Aufruf.

    Gelesen wird die TABELLE, NIE eine laufinterne Abbildung der Cloud-Antworten: Die Namen
    erreichen ihre Events damit auch in einem Lauf, in dem die Cloud-Phase gar nicht lief
    (Einwilligung aus, Cloud-Haekchen abgewaehlt, oder alle Fotos bereits in einem frueheren Lauf
    erkannt), und ein erneuter Kriterien-Lauf benennt dieselben Events wieder. Eine
    In-Memory-Variante koppelte die Benennung still an die Frage, ob im SELBEN Lauf Geld ausgegeben
    wurde.

    Dies ist zugleich die EINZIGE Quelle von `events.landmark_name` (Sicherheitsauflage M9).

    DIE GRENZE WIRKT HIER, an der LESESTELLE, nicht an der Schreibstelle (ADR 0107 Punkt 2): Die
    Erkennungszeile wird unveraendert vollstaendig geschrieben - die Antwort ist bezahlt -, und ob
    aus ihr ein verwendbarer Name wird, entscheidet `usable_landmark_name`. Eine spaetere Aenderung
    der Grenze wirkt dadurch beim naechsten Neuaufbau der Gruppierung, ohne einen einzigen erneuten
    Cloud-Aufruf; laege die Entscheidung an der Schreibstelle, waere jede Korrektur kostenpflichtig
    und fuer den Altbestand gar nicht mehr moeglich.

    Ein so verworfener Treffer ist von "nie erkannt" NICHT zu unterscheiden: beide ergeben `None`,
    das Foto faellt auf Ortsname bzw. Koordinate zurueck, und es entsteht kein Anzeigezustand und
    kein Hinweis auf die Vermutung.

    SANITISIERUNG BEIM LESEN DER PERSISTIERTEN ZEILEN (Muss-Kriterium des Sicherheitskonzepts,
    Abschnitt "Standortdaten"): `usable_landmark_name` wendet `sanitize_landmark_name` hier ein
    ZWEITES Mal an, obwohl `landmark.py::_landmark_detection_from_json` sie bereits an der Quelle
    anwendet, und zwar auf den kanonischen Namen EBENSO wie auf den Rohnamen (S9). Sie ist die
    einzige Deckung des Altbestands: es gibt reale Zeilen mit unsaniertem Rohtext und fuer sie
    keinen Migrationsweg. Bitte nicht als vermeintliche Dopplung entfernen. Fachlich wirkt sie
    hier zusaetzlich als Zusammenfuehrung: ein unsanierter Altname und sein sauberer Zwilling
    meinen dieselbe Sehenswuerdigkeit und duerfen ihr Event nicht unter zwei Schreibweisen
    fuehren."""
    if not photo_ids:
        return {}

    rows = (
        await session.execute(
            select(
                PhotoLandmarkDetection.photo_id,
                PhotoLandmarkDetection.name,
                PhotoLandmarkDetection.confidence,
                PhotoLandmarkDetection.canonical_name,
            ).where(PhotoLandmarkDetection.photo_id.in_(photo_ids))
        )
    ).all()
    return {
        photo_id: usable_landmark_name(name, confidence, canonical_name)
        for photo_id, name, confidence, canonical_name in rows
    }


async def read_event_inputs(
    session: AsyncSession, project_id: int, photo_ids: Collection[int]
) -> EventInputs:
    """Die Kandidaten eines Laufs samt ihrer Inferenzbasis - der EINZIGE Datenbankzugriff dieses
    Moduls, und er liest ausschliesslich.

    SICHERHEIT (M5): Die Inferenzbasis ist JEDES Foto DIESES Projekts - die Bindung an
    `Photo.project_id` steht ausgeschrieben. Ohne sie erbte ein Foto Koordinaten aus einem fremden
    Projekt, und die Event-Grenzen in Projekt A haengten an Fotos aus Projekt B. Ausdruecklich
    NICHT auf die Kandidatenmenge eingeschraenkt: ein aussortiertes Foto traegt eine ebenso
    gueltige Koordinate.

    SICHERHEIT (S4): Namens-, Staerke- und Ausschlussabfrage bleiben auf `photo_ids` eingeschraenkt
    und duerfen die Menge, die `build_events` sieht, NIE erweitern - anders als die Inferenzbasis
    oben, deren Bezugsmenge bewusst das ganze Projekt ist.

    Die Reihenfolge der Kandidaten ist die der uebergebenen Ids; `build_events` sortiert ohnehin
    selbst."""
    # EINE Abfrage fuer BEIDES: die Inferenzbasis der Ortsherleitung (jedes Foto des Projekts) UND
    # `taken_at`/`gps` der Kandidaten (eine Teilmenge davon).
    photo_rows = (
        await session.execute(
            select(Photo.id, Photo.taken_at, Photo.gps_lat, Photo.gps_lon).where(
                Photo.project_id == project_id
            )
        )
    ).all()
    entries = tuple(
        LocationEntry(photo_id=photo_id, taken_at=taken_at, gps_lat=gps_lat, gps_lon=gps_lon)
        for photo_id, taken_at, gps_lat, gps_lon in photo_rows
    )
    effective_locations = infer_locations(entries)
    time_and_place_by_photo_id = {
        photo_id: (taken_at, gps_lat, gps_lon)
        for photo_id, taken_at, gps_lat, gps_lon in photo_rows
    }

    landmark_name_by_photo = await _landmark_names(session, photo_ids)

    # DAS MOTIVBILD je Kandidat - die Grundlage des Motivwechsels als Trennsignal. Die WIRKSAMEN
    # Staerken, nie die rohe Staerkezeile: eine Nutzerkorrektur wirkt damit genau wie die
    # Modellaussage, ohne eine zweite Fassung des `CASE`.
    effective_strengths = await load_effective_strengths(session, photo_ids)
    excluded_documents = frozenset(
        (
            await session.execute(
                select(PhotoMotifAssessment.photo_id).where(
                    PhotoMotifAssessment.photo_id.in_(photo_ids),
                    PhotoMotifAssessment.excluded_document.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )

    candidates = tuple(
        EventCandidate(
            photo_id=photo_id,
            taken_at=time_and_place_by_photo_id[photo_id][0],
            location=effective_locations.get(photo_id),
            gps_lat=time_and_place_by_photo_id[photo_id][1],
            gps_lon=time_and_place_by_photo_id[photo_id][2],
            landmark_name=landmark_name_by_photo.get(photo_id),
            motif_strengths=_plain_strengths(effective_strengths.get(photo_id)),
            excluded_document=photo_id in excluded_documents,
        )
        for photo_id in photo_ids
    )
    return EventInputs(candidates=candidates, entries=entries)
