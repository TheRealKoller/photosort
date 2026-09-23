from __future__ import annotations

import enum
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi import Path as PathParam
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import CursorResult, and_, delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from photosort.album_selection import SelectionState, selection_state
from photosort.api.deps import get_current_user, get_session
from photosort.api.ratings import RatingWriteOut, write_own_rating
from photosort.cameras import CameraIdentity, camera_label
from photosort.config import settings
from photosort.criteria import CRITERIA_REGISTRY, is_landmark_candidate
from photosort.duplicates import (
    all_group_representative_ids,
    effective_decision_for,
    group_standing,
    has_ausschuss_entry,
    has_open_suggestion,
    has_open_suggestion_for,
    keep_possible_for,
    load_duplicate_links,
    member_ids_of,
    representative_of,
    survives_ausschuss_for,
)
from photosort.events import (
    EffectiveLocation,
    EventSpan,
    LocationEntry,
    event_for_time,
    infer_locations,
)
from photosort.feedback_log import load_frozen_context, record_exchange, record_motif_correction
from photosort.models import (
    CloudVisionPhase,
    CriterionScoringRun,
    CriterionSource,
    DuplicateDecision,
    Event,
    FeedbackEventKind,
    FinalSelectionDecision,
    MotifAssessmentSource,
    Photo,
    PhotoAlbumSuitability,
    PhotoCloudVisionError,
    PhotoFineLabel,
    PhotoMotifCorrection,
    PhotoMotifStrength,
    PhotoRanking,
    PhotoScore,
    Project,
    Rating,
    RatingStatus,
    ScanStatus,
    User,
)
from photosort.motif_strengths import EffectiveStrength, load_effective_strengths
from photosort.motifs import MOTIF_REGISTRY, is_motif_key

# AUSSCHLIESSLICH das Praedikat, nie die Konstante: Die Praesenzgrenze steht an genau einer Stelle,
# und der inklusive Vergleich gehoert dort ebenso hin (Zusicherung 26). Dasselbe gilt fuer die
# Reihenfolge der Alternativen: sie ist eine REINE Funktion in `selection.py`, hier steht nur die
# Beschaffung ihrer Eingabe.
from photosort.selection import AlternativeCandidate, motif_is_present, order_alternatives
from photosort.thumbnails import variant_path

# Bewusste Abweichung vom Router-Level-dependencies=[Depends(get_current_user)]-Muster aus
# projects.py/opencloud.py: jeder Endpunkt hier braucht das tatsächliche
# User-Objekt (fuer die eigene Bewertung/den Datenzugriff), nicht nur die Auth-Pruefung als reinen
# Torwaechter - deshalb current_user als normaler Depends()-Parameter statt Router-weiter
# dependencies-Liste. Sicherheitswirkung ist identisch (jeder Endpunkt bleibt auth-pflichtig).
router = APIRouter(tags=["photos"])


class RatingFilter(enum.StrEnum):
    """Die Eintraege des Rasterfilters. `favorite` bleibt als EINTRAG, ist aber kein
    Bewertungsstatus mehr: er filtert auf die eigene Spalte `Rating.favorite`.

    `unrated` heisst ab jetzt "KEINE ALBUMENTSCHEIDUNG" (`status IS NULL`), nicht mehr "keine
    Zeile" - ein nur als Favorit markiertes Bild bleibt damit in diesem Filter."""

    UNRATED = "unrated"
    SUGGESTED = "suggested"
    FAVORITE = "favorite"
    ALBUM_WORTHY = "album_worthy"
    REJECTED = "rejected"


class RatingOut(BaseModel):
    """Die Bewertungszeile EINES Nutzers. `status` ist die Albumentscheidung und `null`, wenn
    keine getroffen wurde - auch dann, wenn die Zeile wegen `favorite` existiert.

    SICHERHEIT (S6): Die Oberflaeche liest den EIGENEN Zustand - Albumentscheidung UND
    Kennzeichen - ausschliesslich ueber `utils/ownRating.ts` (Abgleich ueber den
    `username`-Claim), nie ueber eine Zweitableitung wie `ratings.some(r => r.favorite)`. Eine
    solche stellte die Auszeichnung des anderen als die eigene dar."""

    user_id: int
    username: str
    status: RatingStatus | None
    favorite: bool


class SuggestionOut(BaseModel):
    """Automatischer Vorschlag aus PhotoScore, bewusst getrennt von RatingOut/ratings[] -
    ein Vorschlag ist strukturell nie eine Rating-Zeile. `reason` ist regelbasiert aus
    duplicate_of abgeleitet, nicht separat in PhotoScore gespeichert.

    PhotoScore.suggested_status wird "praktisch nur noch REJECTED" gesetzt; die Rangfolge trägt
    die Kriterien-Pipeline (PhotoRanking, siehe RankingOut unten). `reason` traegt ausschliesslich
    `duplicate`/`low_quality` - die Rangfolgen-Information steht in `PhotoOut.rankings`, nie
    hier."""

    status: RatingStatus
    reason: Literal["duplicate", "low_quality"]
    duplicate_of: int | None
    sharpness: float
    exposure: float
    cluster_key: str | None
    computed_at: datetime


class RankingOut(BaseModel):
    """EINE Zugehörigkeit eines Fotos zu einer Kategorie aus der Kriterien-/Rangfolgen-Pipeline.

    Auch im Standard-Listing-Zweig befüllt, nicht nur, wenn das Foto Teil des abgefragten
    Top-N-Ergebnisses ist. Getrennt von SuggestionOut, siehe dessen Docstring.

    Ein Foto hat pro Lauf GENAU EINE solche Zeile - die Partition ist allein das Event."""

    event_id: int
    # BEIDE nullable, und `null` heisst hier GENAU EINES: "kein Qualitätswert, weil keine
    # Modellbewertung" - projektweit ohne Cloud-Freigabe, je Foto bei einem fehlgeschlagenen
    # Aufruf. `0.0` ist dagegen ein GÜLTIGER Qualitätswert (die schlechteste Modellstufe ohne
    # lokale Korrektur); ein Leser, der auf Falsyness statt auf `null` prüft, verliert ihn
    # lautlos. `event_id` bleibt daneben gesetzt - die Gliederung ist keine Cloud-Leistung.
    rank_score: float | None
    rank_position: int | None
    # Größe der GESAMTEN Event-Partition (nicht nur der angeforderten top_n), für "Rang M von N"
    # im Info-Popover - lauf-global berechnet (siehe _partition_sizes), nicht nutzerspezifisch
    # gefiltert.
    partition_size: int
    # Traegt der LAUF dieses Foto vor? `selection_position IS NOT NULL`, LAUF-GLOBAL und ohne
    # jeden Nutzerbezug - beide Nutzer sehen denselben Wert.
    #
    # Auf ALLEN Lesepfaden befuellt, nicht nur im Entwurfsmodus: Der Entwurf eines Nutzers ist
    # Vorschlag ∪ eigene Aufnahmen, und erst dieses Feld unterscheidet darin die beiden Herkuenfte.
    # Ein Eintrag mit `proposed=false` und eigener Entscheidung `album_worthy` ist der Zustand
    # "aufgenommen, vom aktuellen Vorschlag nicht getragen".
    #
    # NICHT aus `curation_position` ableitbar: jene traegt den Platz in der ANGEZEIGTEN Auswahl
    # und steht ausserhalb des Entwurfszweigs ueberall auf `null`.
    proposed: bool
    # Der Platz dieses Fotos in der ANGEZEIGTEN Auswahl seines Events. `null`, wenn das Foto nicht
    # zur angeforderten Auswahl gehoert oder gar keine angefordert wurde.
    #
    # Die Kuratierungs-Query hat KEINEN Ablehnungsfilter, der Wert ist damit ENTWEDER `null` ODER
    # gleich `rank_position`, und nicht nutzerabhaengig.
    #
    # Trotz des Zusammenfallens NICHT mit `rank_position` zusammenlegen: jene ist die lauf-globale
    # Rangaussage des Info-Popovers (unabhaengig vom Query-Parameter), diese hier die
    # Zugehoerigkeit zur angeforderten Auswahl ("ist dieses Foto zu zeigen") - die einzige
    # Auskunft darueber, die das Frontend sonst nachbilden muesste.
    curation_position: int | None = None


class CriterionScoreOut(BaseModel):
    """Ein einzelner, bereits normierter Kriterien-Wert eines Fotos
    - exponiert die `PhotoCriterionScore`-Tabelle.
    `display_name` kommt aus criteria.py::CRITERIA_REGISTRY (Fallback auf `criterion_key`, falls
    ein DB-Wert nicht im Register steht - defensiv gegen Registry-/Daten-Drift).

    `has_presence_threshold` ist `presence_threshold is not None` der Registry (Fallback False)
    und die alleinige Grundlage der Frontend-Gliederung in die Bloecke "Qualitaet"/"Bildinhalt" -
    bewusst kein zweites, redundantes Anzeige-Attribut. Die SCHWELLE selbst geht ausdruecklich
    NICHT in die Antwort: sie ist die Vorfilter-Grenze des Cloud-Aufrufs, keine Anzeigehilfe, und
    hat in der Oberflaeche nichts zu entscheiden."""

    criterion_key: str
    display_name: str
    value: float
    source: CriterionSource
    has_presence_threshold: bool


class FineLabelOut(BaseModel):
    """Ein frei formuliertes, auf einen kanonischen Eintrag aufgeloestes Feinlabel
    Immer eine Liste (0-2 Einträge), nie None, analog
    `ratings`/`criterion_scores`. Reine ZUSATZINFORMATION am Foto, keine Kategoriequelle.

    `display_name` und
    `raw_label` sind freier, extern erzeugter LLM-Text - sie sind beim Uebernehmen der
    Modellantwort zeichensaniert worden (cloud_vision.py::_sanitize_label_text) und
    duerfen im Frontend ausschliesslich als regulaerer Textknoten gerendert werden."""

    canonical_key: str
    display_name: str
    raw_label: str
    provider: str


class CloudVisionStatus(enum.StrEnum):
    """Einer von sechs Zuständen je Foto x
    CloudVisionPhase, zur Anfragezeit aus bereits vorhandenen Signalen abgeleitet (siehe
    _cloud_vision_status_out)."""

    NOT_RUN = "not_run"
    NOT_CANDIDATE = "not_candidate"
    CONSENT_DISABLED = "consent_disabled"
    ERROR = "error"
    NO_RESULT = "no_result"
    RESULT = "result"


class CloudVisionStatusOut(BaseModel):
    """Ein Eintrag von `PhotoOut.cloud_vision_status` (immer genau zwei, einer je
    CloudVisionPhase, feste Reihenfolge [landmark, remote_category])."""

    phase: CloudVisionPhase
    status: CloudVisionStatus
    # Nur bei status == ERROR gesetzt.
    error_message: str | None = None
    # Nur bei status in {ERROR, NO_RESULT, RESULT} gesetzt.
    attempted_at: datetime | None = None


class PhotoLocationOut(BaseModel):
    """Der Ort DIESES Fotos - in VOLLER EXIF-Präzision, ohne serverseitige Rundung (die Rundung
    auf zwei Nachkommastellen liegt allein in `ClusterPlaceOut`).

    `source` ist ein SICHERHEITSMERKMAL, kein Anzeigedetail (Muss-Kriterium des
    Sicherheitskonzepts): `scoring.GPS_CLUSTER_SPLIT_DISTANCE_METERS` begrenzt den SCHRITT zwischen
    zwei aufeinanderfolgenden Fotos, nicht den DURCHMESSER eines Clusters - ein Spaziergang in
    400-m-Schritten teilt nie und kann Kilometer ueberspannen. Eine `"derived"`-Koordinate kann
    deshalb beliebig weit von der tatsaechlichen Aufnahmestelle entfernt liegen; sie ist eine
    SCHAETZUNG, nie eine Messung. Kein kuenftiger Verbraucher (Kartenansicht, Export,
    Reverse-Geocoding) darf `derived` wie `exif` behandeln - genau dafuer existiert das Feld.

    Wird NIRGENDS persistiert."""

    lat: float
    lon: float
    source: Literal["exif", "derived"]


class EventPlaceOut(BaseModel):
    """Der bereits AUFGELÖSTE Ort des EVENTS - auf jedem Foto desselben Events identisch, `null`
    ohne jede Ortsinformation.

    Der Server liefert den fertigen ZUSTAND, nicht die Rohdaten fuer eine Rangfolge: `kind` benennt,
    welche Stufe (erkannte Sehenswuerdigkeit -> ungefaehre Koordinate -> mehrere Orte) tatsaechlich
    gilt. Das Frontend bildet die Rangfolge NICHT nach, es formatiert nur.

    `kind` benennt die STUFE, nicht den einzigen Text des Events: seit Spec 0514 (ADR 0120) steht
    `landmark_name` NEBEN `EventOut.place_name`, statt ihn zu verdraengen. Verdraengt bleibt allein
    die KOORDINATENSTUFE - `kind` bleibt `"landmark"` auch dann, wenn daneben ein Ortsname steht,
    und traegt weiterhin keine Koordinate.

    `kind="multiple"` traegt STRUKTURELL keine Koordinate: es gibt den einen Ort, den sie
    repraesentieren muesste, gerade nicht.

    `landmark_name` ist freier, extern erzeugter LLM-Text (`Event.landmark_name`, ueber
    `sanitize_landmark_name` entstanden) - dieselbe Auflage wie bei `FineLabelOut.raw_label`:
    ausschliesslich als regulaerer React-Textknoten rendern, nie `dangerouslySetInnerHTML`, nie als
    HTML-String-Prop, nie in `href`/`src`/`style`, nie als React-`key`. Seit Spec 0514 traegt ein
    Event ihn nur, wenn ihn mindestens ein Zehntel seiner Fotos bezeugt
    (`events.LANDMARK_MIN_SHARE`); ein zu schwach gestuetzter Name ist von "nie erkannt" NICHT zu
    unterscheiden und hat keinen eigenen Anzeigezustand. Bricht in
    `frontend/src/pages/AlbumDraftPage.test.tsx`, Faelle
    `rendert einen HTML-artigen Sehenswuerdigkeit-Namen als Text, nicht als Markup` und
    `rendert beide feindlichen Teile als Text, nicht als Markup`."""

    kind: Literal["landmark", "coordinate", "multiple"]
    landmark_name: str | None = None
    lat: float | None = None
    lon: float | None = None


class EventOut(BaseModel):
    """Das Event, zu dem dieses Foto im letzten erfolgreichen Lauf gehoert.

    Der Server liefert weiterhin KEINE fertige Ueberschrift, sondern ihre Teile: Nummer,
    Zeitspanne, den aufgeloesten Ort und den aufgeloesten Ortsnamen. Anders als die frueheren
    Cluster-Angaben haengt hier nichts mehr davon ab, welche Fotos eine Antwort gerade enthaelt -
    alle Werte stehen in der `events`-Zeile.

    Auch zusammengesetzt wird hier nichts: `place_name` ist der REINE Ortsname ("Ort" bzw.
    "Ort, Viertel"), und die Form "<Name>, <Ort>" entsteht erst in
    `frontend/src/utils/timeOfDay.ts::eventPlaceName` (Spec 0514, ADR 0120). Eine zweite Quelle
    derselben Form erzeugte genau die Divergenz, gegen die `photoDetail.structure.test.ts` steht.

    `place_name` steht BEWUSST HIER und nicht in `EventPlaceOut`: `_event_place_out` liefert bei
    unbekanntem `place_kind` `None`, und ein persistierter Name darf damit nicht mitfallen. `null`
    heisst "kein aufgeloester Ortsname" - das Event heisst dann nach Nummer und Zeitspanne, sofern
    kein Sehenswuerdigkeitsname daneben steht.

    Es ist freier, extern erzeugter Text (aus dem Ortsdatensatz, ueber
    `places.sanitize_place_name` entstanden) und traegt die Auflage von `landmark_name`
    wortgleich: ausschliesslich als regulaerer React-Textknoten rendern, nie
    `dangerouslySetInnerHTML`, nie als HTML-String-Prop, nie in `href`/`src`/`style`, nie als
    React-`key`. Die Schluessel-Auflage ist hier nicht nur XSS-Hygiene: Gleichnamigkeit ist der
    Normalfall, den diese Story eigens behandelt. Bricht in
    `frontend/src/pages/AlbumDraftPage.test.tsx`, Fall
    `rendert einen HTML-artigen Ortsnamen als Text, nicht als Markup`."""

    id: int
    position: int
    started_at: datetime
    ended_at: datetime
    place: EventPlaceOut | None = None
    place_name: str | None = None


class CameraOut(BaseModel):
    """Die Kamera eines Fotos. `label` kommt vom SERVER (`cameras.py::camera_label`) - eine
    Stelle entscheidet, wie eine Kamera heisst, und der Wert ist dort bereits von Zeichen der
    Unicode-Kategorien Cc/Cf befreit."""

    id: int
    label: str


class MotifAssessmentOut(BaseModel):
    """Die Kopfzeile des Motiv-Staerkevektors eines Fotos - `null` heisst "noch nicht
    klassifiziert" und ist damit unterscheidbar von "nichts erkannt" (Kopfzeile vorhanden, alle
    acht Staerken niedrig). Genau dafuer gibt es dieses Feld getrennt von `motifs`: acht Nullzeilen
    sind von "nichts erkannt" nicht zu unterscheiden.

    `provider` ist `null` bei `source == "local"`. `excluded_document` ist von Hand NICHT
    korrigierbar - der Rueckweg ist allein ein erneuter Klassifizierungslauf, und die Oberflaeche
    benennt das, statt einen Schalter anzubieten."""

    source: Literal["cloud", "local"]
    provider: str | None
    excluded_document: bool
    computed_at: datetime


class AlbumSuitabilityOut(BaseModel):
    """Die fuenfstufige Modellaussage ueber die ALBUMTAUGLICHKEIT eines Fotos samt Begruendung.

    `null` am Foto heisst "noch nicht bewertet" und ist damit von der niedrigsten Stufe
    unterscheidbar - die Oberflaeche zeigt an dieser Stelle einen Satz statt einer Stufe.

    `reason` ist FREIER MODELLTEXT. Er ist bereits am Parser saniert und gekappt
    (`album_suitability.py`, Sicherheitsauflage S2) und wird hier unveraendert durchgereicht; eine
    zweite Fassung derselben Regel gibt es nicht. In der Oberflaeche gehoert er ausschliesslich
    als regulaerer Textknoten gerendert - nie ueber `dangerouslySetInnerHTML`, nie in ein `href`,
    `src` oder `style` (S12).

    Die Aussage ist erkennbar die des MODELLS, nicht die von PhotoSort: sie stammt aus einem Bild,
    das Text enthalten kann."""

    level: int
    reason: str | None


class MotifStrengthOut(BaseModel):
    """Die WIRKSAME Staerke eines Motivs an einem Foto samt ihrem Korrekturzustand.

    `strength` traegt die Korrektur bereits eingerechnet (motif_strengths.py::
    effective_strength_expression) - das Frontend rechnet nichts nach und kennt die Regel nicht.
    `correction` ist `null` ohne Korrekturzeile, sonst die Aussage des Nutzers; ohne dieses Feld
    waere eine Modellaussage von genau `1.0` von einer Korrektur nicht zu unterscheiden, und die
    Oberflaeche koennte das Korrekturwort nicht statt der Prozentzahl setzen."""

    # `key` wie in `MotifOut` von `GET /motifs` - dieselbe Sache heisst an beiden Stellen gleich,
    # und das Frontend schlaegt je Schluessel nach.
    key: str
    strength: float
    correction: bool | None
    # DIE AUSSAGE DES SERVERS, ob das Foto dieses Motiv TRAEGT. Die Grenze wohnt in
    # `selection.py::motif_is_present` und verlaesst das Backend nie als Zahl - das Frontend liest
    # fuer diese Frage ausschliesslich dieses Feld, nie `strength`.
    #
    # Additiv und auf ALLEN Lesepfaden befuellt (Muster `RankingOut.proposed`). Es speist die
    # Motivmischung am Event des Album-Entwurfs; eine im Frontend hinterlegte Grenze waere die
    # zweite Stelle, an der ueber Zugehoerigkeit entschieden wird.
    present: bool


class PhotoOut(BaseModel):
    id: int
    relative_path: str
    # Behaelt Namen und Form und liefert seit Spec 0426 die KORRIGIERTE Zeit (ADR 0090, Punkt 1).
    # Der brechende Bedeutungswechsel ist beabsichtigt; die beiden Felder darunter treten daneben,
    # damit eine korrigierte Anzeige als korrigiert erkennbar bleibt.
    taken_at: datetime
    # Die aufgezeichnete Zeit (EXIF `DateTimeOriginal`, sonst `last_modified`).
    taken_at_original: datetime
    # Die Differenz der beiden Zeitstempel in ganzen Minuten - `0` heisst "nicht korrigiert".
    # Aus der Differenz gerechnet statt aus `ProjectCamera.offset_minutes` gelesen: so kann die
    # Anzeige nicht behaupten, eine Zeit sei um X verschoben, wenn sie es nicht ist (etwa bei
    # einem Foto, dessen Versatz beim Scan an einem Ueberlauf gescheitert ist).
    time_offset_minutes: int
    camera: CameraOut | None = None
    # Breite geteilt durch Hoehe des GEZEIGTEN Bildes (ADR 0110 Punkt 1). `null` heisst "nicht
    # bekannt" und ist ein REGULAERER Zustand, kein Fehler - die Oberflaeche plant ein solches
    # Foto mit 3:2 ein. Einheitlich auf ALLEN Lesepfaden ausgeliefert, nicht nur auf dem der
    # Rasteransicht: ein je Query-Modus divergierendes `PhotoOut` waere genau die "zweite,
    # driftende Abbildung", vor der der `ranking`-Kommentar oben warnt.
    aspect_ratio: float | None = None
    ratings: list[RatingOut]
    suggestion: SuggestionOut | None
    # Die Rangzeile des Fotos im letzten erfolgreichen Lauf, in beiden Query-Modi - `null`,
    # solange kein erfolgreicher Lauf existiert oder das Foto darin keine Zeile hat. EIN Feld und
    # keine Liste: ein Foto steht je Lauf in genau einer Zeile, seit die Partition allein das
    # Event ist.
    ranking: RankingOut | None = None
    # Immer eine Liste, nie None (analog `ratings`) - best-effort: enthaelt nur Kriterien, fuer
    # die tatsaechlich eine PhotoCriterionScore-Zeile existiert, sortiert nach
    # CRITERIA_REGISTRY-Reihenfolge.
    criterion_scores: list[CriterionScoreOut]
    # Immer eine Liste (0-2 Einträge), nie None.
    fine_labels: list[FineLabelOut]
    # Immer genau 2 Einträge (einer je
    # CloudVisionPhase), feste Reihenfolge [landmark, remote_category] - siehe
    # _cloud_vision_status_out.
    cloud_vision_status: list[CloudVisionStatusOut]
    # Zwei additive, OPTIONALE Felder mit Vorgabewert `null`. Beide werden einheitlich auf ALLEN
    # Lesepfaden ausgeliefert, nicht nur im Kuratierungsmodus: ein je Query-Modus divergierendes
    # `PhotoOut` waere genau die "zweite, driftende Abbildung", vor der der `rankings`-Kommentar
    # oben warnt.
    location: PhotoLocationOut | None = None
    event: EventOut | None = None
    # `motif_assessment` ist `null`, solange das Foto keinen Klassifizierungslauf gesehen hat -
    # dann ist `motifs` LEER und traegt ausdruecklich NICHT acht Eintraege mit Wert 0. Die
    # Oberflaeche zeigt an ihrer Stelle einen Satz; ein `?? 0` oder eine leere Standardliste im
    # Lesepfad machte "noch nicht klassifiziert" von "nichts erkannt" ununterscheidbar.
    motif_assessment: MotifAssessmentOut | None = None
    # Immer eine Liste, nie `null` (analog `ratings`): leer ohne Kopfzeile, sonst GENAU acht
    # Eintraege in Registry-Reihenfolge - auch bei unvollstaendigen Staerkezeilen. Die Reihenfolge
    # ist auf jedem Foto dieselbe; das Frontend schlaegt je Schluessel nach und nie ueber den Index.
    motifs: list[MotifStrengthOut]
    # `null` heisst "noch nicht bewertet" - kein Meter-Glyph, keine Stufe, kein Platzhalter.
    album_suitability: AlbumSuitabilityOut | None = None
    # DIE DREI FELDER DER ENDAUSWAHL (ADR 0099 Punkt 4), auf ALLEN Lesepfaden befuellt - Muster
    # `RankingOut.proposed`: ein je Query-Modus verschiedenes `PhotoOut` waere die zweite,
    # driftende Abbildung. Alle drei sind PROJEKTAUSSAGEN und tragen kein nutzerbezogenes Datum.
    #
    # Die persistierte gemeinsame Entscheidung, `null` = keine. AUSDRUECKLICH NICHT
    # `album_decision` benannt: so heisst bereits `ratings[].status`, die Entscheidung eines
    # NUTZERS - und die beiden zu verwechseln ist genau der Fehler, den diese Story ausschliesst.
    #
    # ALLE DREI OHNE VORGABEWERT, anders als `location`/`event`/`ranking` darueber (Auflage S9):
    # Ein `= False` waere die stille Ausfallrichtung "nicht im Album" - plausibel, ohne Ausnahme
    # und ohne Fehlercode, und der Fehler zeigte sich erst an einem leeren Album statt an der
    # Stelle, an der er entsteht. Zusammen mit den pflichtigen `_to_photo_out`-Parametern
    # scheitert ein vergessener Aufrufer damit VOR der Laufzeit.
    final_selection_decision: bool | None
    # Gehoert das Foto zur Endauswahl? `album_selection.py::selection_state(...).included`. Das
    # Frontend leitet die Zugehoerigkeit NIE selbst her; sie kommt vom Server.
    in_final_selection: bool
    # Sind sich die Nutzer uneins und ist noch nicht gemeinsam entschieden?
    # `album_selection.py::selection_state(...).contested`.
    contested: bool


class PhotoListOut(BaseModel):
    items: list[PhotoOut]
    total: int


class AlbumParticipantOut(BaseModel):
    """EIN Teilnehmer der Endauswahl - genau `user_id` und `username`, nie mehr (Auflage S8).

    Die Liste entsteht aus einer AUSDRUECKLICHEN Projektion auf diese zwei Spalten, nie aus einer
    Serialisierung des `User`-Objekts: Dies ist der erste Endpunkt, der den vollstaendigen
    Kontenbestand ausliefert, und ein `model_validate(User)` mit `from_attributes` schoebe
    `password_hash` und `created_at` in eine Antwort, die im Browser beider Nutzer und in jedem
    Cache landet.

    Es entsteht dadurch keine neue Datenklasse zwischen den beiden Nutzern: Der `username` ist
    ueber `PhotoOut.ratings[]` bereits heute sichtbar."""

    user_id: int
    username: str


class AlbumSelectionOut(BaseModel):
    """Die gemeinsame Endauswahl eines Projekts.

    KEIN `total` und keine Seitenweise: Die Menge wird als GANZES geliefert, wie der
    Entwurfszweig. Ein `total == len(items)` lueede dazu ein, etwas zu blaettern, das nicht
    geblaettert wird."""

    # ALLE Nutzer, nach `user_id` sortiert - auch der, der noch nie etwas angefasst hat. Aus
    # `ratings[]` abgeleitet fehlte genau er, und die Story benennt ihn ausdruecklich als "kein
    # Sonderfall". Seine LAENGE ist zugleich der Nenner der Einigkeitsregel (Auflage S8).
    participants: list[AlbumParticipantOut]
    # "Mindestens eine Rangzeile des letzten erfolgreichen Laufs traegt `selection_position`."
    # Trennt die beiden Leerzustaende, die die Story GETRENNT verlangt ("kein Auswahlvorschlag"
    # gegen "keine Unterschiede offen") - sie verlangen verschiedene Handlungen, einmal einen Lauf
    # starten, einmal nichts tun. Aus den Kandidatenzeilen abgeleitet, ohne eigene Abfrage.
    has_proposal: bool
    items: list[PhotoOut]


async def _get_project_or_404(project_id: int, session: AsyncSession) -> Project:
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projekt nicht gefunden.")
    return project


async def _filtered_photo_ids(
    session: AsyncSession,
    project_id: int,
    current_user_id: int,
    rating_status: RatingFilter | None,
    limit: int,
    offset: int,
    camera_id: int | None = None,
) -> tuple[list[int], int]:
    own_rating = aliased(Rating)
    base = (
        select(Photo.id)
        .where(Photo.project_id == project_id)
        .outerjoin(
            own_rating,
            and_(own_rating.photo_id == Photo.id, own_rating.user_id == current_user_id),
        )
    )
    if camera_id is not None:
        # SICHERHEIT (Projektgrenze): ein weiteres PRAEDIKAT neben dem vorhandenen
        # `Photo.project_id == project_id` - nie eine vorgeschaltete Aufloesung der Kamerazeile,
        # aus deren Fotos dann gelistet wird. Eine `camera_id` aus einem fremden Projekt trifft
        # damit kein Foto und ergibt eine LEERE Liste, ohne den Wert zu spiegeln.
        base = base.where(Photo.camera_id == camera_id)
    if rating_status is RatingFilter.UNRATED:
        # "Unbewertet" ist KEINE ALBUMENTSCHEIDUNG, nicht mehr "keine Zeile": seit `favorite`
        # eine eigene Spalte ist, kann eine Zeile ohne jede Albumentscheidung existieren. Ueber
        # das Zeilenvorhandensein gepruefte Abwesenheit liesse ein nur als Favorit markiertes
        # Foto still aus dem Filter fallen.
        base = base.where(or_(own_rating.id.is_(None), own_rating.status.is_(None)))
    elif rating_status is RatingFilter.SUGGESTED:
        # Bildet dieselbe Regel wie has_suggestion in _to_photo_out als SQL-Praedikat nach: keine
        # eigene ALBUMENTSCHEIDUNG des anfragenden Nutzers UND ein OFFENER Vorschlag.
        #
        # "Offen" ist seit ADR 0104 mehr als "suggested_status gesetzt": Eine im Duplikat-Vergleich
        # entschiedene Aufnahme ist beantwortet und verschwindet aus diesem Filter - und damit auch
        # aus der Zaehlung des Ausschuss-Gates, die denselben Filter benutzt. Die Bedingung steht
        # deshalb an EINER Stelle (`duplicates.py::has_open_suggestion`); die Objektfassung
        # daneben bleibt ueber
        # `tests/test_api_photos.py::test_list_photos_suggested_filter_matches_has_suggestion_parity`
        # an sie gebunden.
        base = base.join(PhotoScore, PhotoScore.photo_id == Photo.id).where(
            or_(own_rating.id.is_(None), own_rating.status.is_(None)),
            has_open_suggestion(),
        )
    elif rating_status is RatingFilter.FAVORITE:
        # Eigene SPALTE, nicht mehr ein Wert von `status`. Ohne diesen Zweig wuerfe
        # `RatingStatus("favorite")` unten einen `ValueError` - eine 500 auf einem
        # nutzererreichbaren Query-Parameter (Auflage S11).
        base = base.where(own_rating.favorite.is_(True))
    elif rating_status is not None:
        base = base.where(own_rating.status == RatingStatus(rating_status.value))

    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()

    paged = base.order_by(Photo.taken_at, Photo.id).offset(offset).limit(limit)
    ids = [row[0] for row in (await session.execute(paged)).all()]
    return ids, total


async def _photos_by_id(session: AsyncSession, ids: list[int]) -> dict[int, Photo]:
    if not ids:
        return {}
    result = await session.execute(
        select(Photo)
        .where(Photo.id.in_(ids))
        .options(
            selectinload(Photo.ratings).selectinload(Rating.user),
            selectinload(Photo.score),
            # Photo.criterion_scores ist bereits eine ORM-Relationship (models.py) - eager laden
            # statt eines Query pro Foto.
            selectinload(Photo.criterion_scores),
            # Analog
            # eager geladen, inkl. der verknuepften fine_labels-Zeile (fuer canonical_key/
            # display_name, ohne N+1-Query pro Feinlabel).
            selectinload(Photo.fine_labels).selectinload(PhotoFineLabel.fine_label),
            # Eager geladen (analog criterion_scores/fine_labels oben), kein zusaetzliches Query
            # je Foto fuer _cloud_vision_status_out. Ohne dieses selectinload loest
            # photo.landmark_detection einen Lazy-Load aus und schlaegt im Async-Kontext mit
            # MissingGreenlet fehl.
            selectinload(Photo.landmark_detection),
            selectinload(Photo.cloud_vision_errors),
            # Grundlage von `PhotoOut.camera`. EINE Abfrage mehr, unabhaengig von der
            # Fotoanzahl - ohne sie loeste `photo.camera` einen Lazy-Load aus und schluege im
            # Async-Kontext mit MissingGreenlet fehl.
            selectinload(Photo.camera),
            # Grundlage von `PhotoOut.motif_assessment`. Ohne dieses selectinload loeste
            # `photo.motif_assessment` einen Lazy-Load aus und schluege im Async-Kontext mit
            # MissingGreenlet fehl. Die STAERKEN kommen bewusst nicht ueber die Relationship,
            # sondern ueber `load_effective_strengths` - sonst muesste die Korrektur zweimal
            # ausgewertet werden.
            selectinload(Photo.motif_assessment),
            # Grundlage von `PhotoOut.album_suitability` UND der zweiten Haelfte des
            # Erfolgssignals in `_cloud_vision_status_out`. Ohne dieses selectinload loeste
            # `photo.album_suitability` einen Lazy-Load aus und schluege im Async-Kontext mit
            # MissingGreenlet fehl.
            selectinload(Photo.album_suitability),
            # Grundlage der Objektfassung des Ueberlebenden-Praedikats (`is_candidate`) und der
            # Anzeigeregel des offenen Vorschlags. Ohne dieses selectinload loeste
            # `photo.duplicate_decision` einen Lazy-Load aus und schluege im Async-Kontext mit
            # MissingGreenlet fehl.
            selectinload(Photo.duplicate_decision),
        )
    )
    return {photo.id: photo for photo in result.scalars()}


def _suggestion_reason(score: PhotoScore) -> Literal["duplicate", "low_quality"]:
    return "duplicate" if score.duplicate_of is not None else "low_quality"


def _to_suggestion_out(score: PhotoScore) -> SuggestionOut:
    return SuggestionOut(
        status=score.suggested_status,  # type: ignore[arg-type]  # caller already checked not None
        reason=_suggestion_reason(score),
        duplicate_of=score.duplicate_of,
        sharpness=score.sharpness,
        exposure=score.exposure,
        cluster_key=score.cluster_key,
        computed_at=score.computed_at,
    )


def _criterion_scores_out(photo: Photo) -> list[CriterionScoreOut]:
    """Sortiert die vorhandenen PhotoCriterionScore-Zeilen des Fotos nach CRITERIA_REGISTRY-
    Reihenfolge; Zeilen, deren criterion_key nicht in der
    Registry steht (Registry-/Daten-Drift), landen ans Ende, sortiert nach ihrem eigenen Key fuer
    ein deterministisches Ergebnis, und bekommen den rohen Key als display_name-Fallback sowie
    `has_presence_threshold=False` (identisch zum Registry-Default). Fehlt umgekehrt ein
    Registry-Kriterium in der DB, taucht es einfach nicht auf - kein Platzhalter."""
    registry_order = {key: index for index, key in enumerate(CRITERIA_REGISTRY)}
    sorted_scores = sorted(
        photo.criterion_scores,
        key=lambda s: (registry_order.get(s.criterion_key, len(registry_order)), s.criterion_key),
    )
    return [
        CriterionScoreOut(
            criterion_key=s.criterion_key,
            display_name=(
                CRITERIA_REGISTRY[s.criterion_key].display_name
                if s.criterion_key in CRITERIA_REGISTRY
                else s.criterion_key
            ),
            value=s.value,
            source=s.source,
            has_presence_threshold=(
                s.criterion_key in CRITERIA_REGISTRY
                and CRITERIA_REGISTRY[s.criterion_key].presence_threshold is not None
            ),
        )
        for s in sorted_scores
    ]


def _fine_labels_out(photo: Photo) -> list[FineLabelOut]:
    return [
        FineLabelOut(
            canonical_key=row.fine_label.canonical_key,
            display_name=row.fine_label.display_name,
            raw_label=row.raw_label,
            provider=row.provider,
        )
        for row in photo.fine_labels
    ]


def _cloud_vision_status_for_phase(
    phase: CloudVisionPhase,
    *,
    success: tuple[CloudVisionStatus, datetime] | None,
    error: PhotoCloudVisionError | None,
    consent_enabled: bool,
    is_candidate: bool,
) -> CloudVisionStatusOut:
    """Wendet die 5-Ränge-Prioritäts-Kaskade für EINE Phase an - erster zutreffender Rang
    gewinnt, kein Merge mehrerer gleichzeitig zutreffender
    Signale. `success` ist bereits das fertige (Status, attempted_at)-Paar der jeweils
    aufrufenden Phase (RESULT/NO_RESULT unterscheiden sich nur bei landmark, siehe
    _cloud_vision_status_out)."""
    if success is not None:
        status, attempted_at = success
        return CloudVisionStatusOut(phase=phase, status=status, attempted_at=attempted_at)
    if error is not None:
        return CloudVisionStatusOut(
            phase=phase,
            status=CloudVisionStatus.ERROR,
            error_message=error.error_message,
            attempted_at=error.attempted_at,
        )
    if not consent_enabled:
        return CloudVisionStatusOut(phase=phase, status=CloudVisionStatus.CONSENT_DISABLED)
    if not is_candidate:
        return CloudVisionStatusOut(phase=phase, status=CloudVisionStatus.NOT_CANDIDATE)
    return CloudVisionStatusOut(phase=phase, status=CloudVisionStatus.NOT_RUN)


def _cloud_vision_status_out(photo: Photo, project: Project) -> list[CloudVisionStatusOut]:
    """Read-time abgeleiteter Cloud-Vision-Status für beide Phasen,
    IMMER genau 2 Eintraege in fester Reihenfolge [landmark, remote_category] (unabhaengig von
    DB-/Insert-Reihenfolge von photo.cloud_vision_errors). Erwartet, dass `photo` bereits ueber
    selectinload(Photo.criterion_scores/landmark_detection/motif_assessment/album_suitability/
    cloud_vision_errors) eager geladen ist (siehe _photos_by_id) - kein Lazy-Load hier."""
    errors_by_phase = {row.phase: row for row in photo.cloud_vision_errors}

    # Landmark: Erfolgssignal ist entweder eine tatsaechliche Detection ("gefunden", RESULT) oder
    # eine PhotoCriterionScore(criterion_key="landmark")-Zeile ohne Detection ("nichts gefunden",
    # NO_RESULT eigener Sonderfall) - die PRAESENZ der Score-Zeile entscheidet, nicht ihr
    # konkreter Wert.
    landmark_score = next(
        (score for score in photo.criterion_scores if score.criterion_key == "landmark"), None
    )
    landmark_success: tuple[CloudVisionStatus, datetime] | None = None
    if photo.landmark_detection is not None:
        landmark_success = (CloudVisionStatus.RESULT, photo.landmark_detection.computed_at)
    elif landmark_score is not None:
        landmark_success = (CloudVisionStatus.NO_RESULT, landmark_score.computed_at)

    # Remote-Kategorie: kein "nichts gefunden"-Fall - ein Erfolg schreibt GENAU EINE Kopfzeile
    # samt Staerkevektor, auch wenn alle acht Staerken 0 sind und keine Feinlabels entstanden
    # sind. Die PRAESENZ dieser Kopfzeile ist damit das Erfolgssignal, nicht die Existenz einer
    # Feinlabel-Zeile.
    #
    # SICHERHEITSAUFLAGE S14, auch hier: gepruaft wird auf `source='cloud'`, nicht auf das bloße
    # Vorhandensein der Kopfzeile. Der Kriterien-Lauf schreibt fuer jedes beurteilte Foto eine
    # LOKALE Kopfzeile; ein reiner Existenztest meldete jedes lokal beurteilte Foto als
    # erfolgreich cloud-klassifiziert, obwohl nie ein Cloud-Aufruf stattfand. Dieselbe Bedingung
    # steht in worker.py::select_remote_category_candidates und
    # api/projects.py::_count_remote_category_candidates.
    # SICHERHEITSAUFLAGE S6: das Erfolgssignal ist ZUSAMMENGESETZT, genau wie das Skip-Kriterium
    # der Auswahl - Cloud-Kopfzeile UND Albumtauglichkeitszeile. Ohne die zweite Haelfte meldete
    # diese Stelle fuer jedes Bestandsfoto `RESULT`, waehrend dasselbe Foto in Auswahl und
    # Schaetzung wieder Kandidat ist; und ein Foto, das seine Stufe wiederholt unbrauchbar liefert,
    # bliebe als erledigt ausgewiesen, obwohl es bei jedem Lauf erneut gesendet wird.
    remote_category_success: tuple[CloudVisionStatus, datetime] | None = None
    assessment = photo.motif_assessment
    if (
        assessment is not None
        and assessment.source == MotifAssessmentSource.CLOUD
        and photo.album_suitability is not None
    ):
        remote_category_success = (CloudVisionStatus.RESULT, assessment.computed_at)

    return [
        _cloud_vision_status_for_phase(
            CloudVisionPhase.LANDMARK,
            success=landmark_success,
            error=errors_by_phase.get(CloudVisionPhase.LANDMARK),
            consent_enabled=project.cloud_vision_detection_enabled,
            is_candidate=is_landmark_candidate(
                {score.criterion_key: score.value for score in photo.criterion_scores}
            ),
        ),
        _cloud_vision_status_for_phase(
            CloudVisionPhase.REMOTE_CATEGORY,
            success=remote_category_success,
            error=errors_by_phase.get(CloudVisionPhase.REMOTE_CATEGORY),
            consent_enabled=project.cloud_vision_detection_enabled,
            # Spiegelt exakt die WHERE-Klausel von worker.py::select_remote_category_candidates -
            # und zwar ueber DASSELBE Praedikat, nicht ueber eine zweite Formulierung davon. Kein
            # PhotoScore vorhanden ODER nicht ueberlebend -> kein Kandidat. Dies ist der fuenfte
            # Ort des Praedikats: Anzeige, keine Grenze (S1).
            is_candidate=survives_ausschuss_for(photo),
        ),
    ]


@dataclass(frozen=True)
class PhotoPlace:
    """Die beiden Ortsfelder EINES Fotos. `NO_PLACE` ist der Zustand "nichts bekannt" und zugleich
    die AUSFALLRICHTUNG, wenn kein Bezugslauf existiert oder ein Foto keine Rangzeile hat."""

    location: PhotoLocationOut | None = None
    event: EventOut | None = None


NO_PLACE = PhotoPlace()


def _event_place_out(event: Event) -> EventPlaceOut | None:
    """Der Ortsteil einer `events`-Zeile - `None` bei unbekanntem oder fehlendem `place_kind`.

    SICHERHEIT (M8): MITGLIEDSCHAFTSPRUEFUNG statt blindem Cast, sonst legt ein einzelner Wert
    ausserhalb des Vorrats die gesamte Listenantwort auf 500. Die drei Zweige sind einzeln
    ausgeschrieben und setzen dabei die Feldkombination ein zweites Mal durch: eine driftende
    Zeile kann so keine Koordinate unter `"multiple"` ausliefern."""
    if event.place_kind == "landmark":
        return EventPlaceOut(kind="landmark", landmark_name=event.landmark_name)
    if event.place_kind == "coordinate":
        return EventPlaceOut(kind="coordinate", lat=event.place_lat, lon=event.place_lon)
    if event.place_kind == "multiple":
        return EventPlaceOut(kind="multiple")
    return None


def _event_out(event: Event) -> EventOut:
    return EventOut(
        id=event.id,
        position=event.position,
        started_at=event.started_at,
        ended_at=event.ended_at,
        place=_event_place_out(event),
        place_name=event.place_name,
    )


def _location_out(location: EffectiveLocation | None) -> PhotoLocationOut | None:
    """`source` ist ein SICHERHEITSMERKMAL, kein Anzeigedetail: es entsteht ausschliesslich aus
    `EffectiveLocation.inferred` und wird nie aus einem anderen Signal nachgebildet."""
    if location is None:
        return None
    return PhotoLocationOut(
        lat=location.lat, lon=location.lon, source="derived" if location.inferred else "exif"
    )


def _event_ids_from_rankings(rankings_by_photo_id: Mapping[int, PhotoRanking]) -> dict[int, int]:
    """Die Event-Abbildung der Lesepfade, die ausschliesslich Fotos MIT Rangzeile liefern.

    Der Entwurfszweig baut seine eigene: dort haben aufgenommene Fotos ohne Rangzeile ihr Event
    ueber `events.py::event_for_time`."""
    return {photo_id: ranking.event_id for photo_id, ranking in rankings_by_photo_id.items()}


async def _event_and_location_by_photo_id(
    session: AsyncSession,
    project_id: int,
    criterion_scoring_run_id: int | None,
    photos_by_id: Mapping[int, Photo],
    event_id_by_photo_id: Mapping[int, int],
) -> dict[int, PhotoPlace]:
    """Beide Ortsfelder aller Fotos einer Antwort aus ZWEI Abfragen - ihre Zahl ist fest und
    unabhaengig von der Zahl der Fotos.

    (a) Alle Fotos DIESES Projekts als Inferenzbasis von `events.py::infer_locations`. Die
    Bezugsmenge ist ausdruecklich nicht die Antwort und auch nicht die Kandidatenmenge: ein
    aussortiertes Foto traegt eine ebenso gueltige Koordinate. Dieselbe Funktion speist den
    Worker - zwei Herleitungen derselben Sache liefen an dem Tag auseinander, an dem eine ihre
    Bezugsmenge aendert.

    (b) Die Events der uebergebenen Abbildung `photo_id -> event_id`. Sie kommt FERTIG herein
    statt hier aus Rangzeilen gebildet zu werden: der Entwurfszweig ordnet aufgenommene Fotos ohne
    Rangzeile ueber ihre Aufnahmezeit ein, und diese Zuordnung gehoert an die eine Stelle, die
    beide Herkuenfte kennt.

    SICHERHEIT - zwei GETRENNTE Bindungen, beide ausgeschrieben:

    * (M5) Die Inferenzbasis haengt an `Photo.project_id`. Ohne sie erbte ein Foto Koordinaten aus
      einem fremden Projekt.
    * (M1) Die Event-Abfrage haengt an `Event.criterion_scoring_run_id` - `event_id` ist ein
      GLOBALER Surrogatschluessel, und eine Id aus Projekt B identifiziert unter `/projects/A/...`
      eindeutig ein fremdes Event. Die Lauf-Id wird EINMAL PRO REQUEST aufgeloest und hierher
      durchgereicht, nie in dieser Funktion neu bestimmt; fehlt sie, bleibt `event` `None`. Die
      Ausfallrichtung ist "nichts anzeigen", nie "aus irgendeinem Lauf herleiten".

    `_photos_by_id` filtert nur nach Id und ist ausdruecklich KEINE zweite Verteidigungslinie."""
    if not photos_by_id:
        return {}

    location_rows = (
        await session.execute(
            select(Photo.id, Photo.taken_at, Photo.gps_lat, Photo.gps_lon).where(
                Photo.project_id == project_id
            )
        )
    ).all()
    effective_locations = infer_locations(
        LocationEntry(photo_id=photo_id, taken_at=taken_at, gps_lat=gps_lat, gps_lon=gps_lon)
        for photo_id, taken_at, gps_lat, gps_lon in location_rows
    )

    events_by_id: dict[int, EventOut] = {}
    if criterion_scoring_run_id is not None and event_id_by_photo_id:
        events_by_id = {
            event.id: _event_out(event)
            for event in (
                await session.execute(
                    select(Event).where(
                        # SICHERHEIT: das Pflichtpraedikat, siehe Docstring. Nie die Id allein.
                        Event.criterion_scoring_run_id == criterion_scoring_run_id,
                        Event.id.in_(set(event_id_by_photo_id.values())),
                    )
                )
            )
            .scalars()
            .all()
        }

    return {
        photo_id: PhotoPlace(
            location=_location_out(effective_locations.get(photo_id)),
            event=events_by_id.get(event_id_by_photo_id.get(photo_id, 0)),
        )
        for photo_id in photos_by_id
    }


def _album_suitability_out(photo: Photo) -> AlbumSuitabilityOut | None:
    """Die Modellaussage UNVERAENDERT aus der Zeile - kein erneutes Sanieren, kein erneutes
    Kappen, keine Umformulierung. Beides geschah EINMAL am Parser; eine zweite Fassung hier waere
    die zweite Pflegestelle, die auseinanderlaeuft."""
    suitability = photo.album_suitability
    if suitability is None:
        return None
    return AlbumSuitabilityOut(level=suitability.level, reason=suitability.reason)


def _motif_assessment_out(photo: Photo) -> MotifAssessmentOut | None:
    assessment = photo.motif_assessment
    if assessment is None:
        return None
    return MotifAssessmentOut(
        # `.value` und nicht das Enum selbst: das Antwortfeld ist ein `Literal["cloud", "local"]`,
        # damit der erzeugte OpenAPI-Typ zwei Zeichenketten nennt und nicht einen Enum-Namen, den
        # das Frontend nachbilden muesste.
        source=assessment.source.value,
        provider=assessment.provider,
        excluded_document=assessment.excluded_document,
        computed_at=assessment.computed_at,
    )


def _motifs_out(
    photo: Photo, effective: Mapping[str, EffectiveStrength] | None
) -> list[MotifStrengthOut]:
    """Die acht Motive eines Fotos in Registry-Reihenfolge - oder eine LEERE Liste, wenn das Foto
    keine Kopfzeile hat.

    Die Iteration laeuft ueber `MOTIF_REGISTRY` und nicht ueber die geladenen Zeilen: das liefert
    die Anzeigereihenfolge ohne Nachsortieren, ergaenzt eine fehlende Staerkezeile mit `0.0` (der
    Vektor ist dann trotzdem vollstaendig) und ist zugleich die Verteidigung gegen einen
    Altschluessel ausserhalb des Sets - er kann hier nicht durchfallen.

    Die leere Liste OHNE Kopfzeile ist die eigentliche Zusage: acht Eintraege mit Wert 0 waeren von
    "nichts erkannt" nicht zu unterscheiden - und acht Eintraege mit `present=False` ebenso.

    `strength` und `present` entstehen aus EINER lokalen Groesse. Zweimal hergeleitet liefen sie an
    dem Tag auseinander, an dem eine der beiden Stellen sich aendert; `present` kommt dabei
    ausschliesslich ueber `selection.py::motif_is_present`, nie ueber einen eigenen Vergleich."""
    if photo.motif_assessment is None:
        return []
    strengths = effective or {}
    entries: list[MotifStrengthOut] = []
    for motif_key in MOTIF_REGISTRY:
        effective_entry = strengths.get(motif_key)
        strength = 0.0 if effective_entry is None else effective_entry.strength
        entries.append(
            MotifStrengthOut(
                key=motif_key,
                strength=strength,
                correction=None if effective_entry is None else effective_entry.correction,
                present=motif_is_present(strength),
            )
        )
    return entries


async def _final_selection_decisions(
    session: AsyncSession, photo_ids: list[int]
) -> dict[int, bool]:
    """Die gemeinsame Entscheidung je Foto - EINE Abfrage je Anfrage, nie eine je Foto (Muster
    `_ranking_by_photo_id`).

    Ein fehlender Eintrag heisst "unentschieden"; es gibt keinen dritten Zustand."""
    if not photo_ids:
        return {}
    result = await session.execute(
        select(FinalSelectionDecision.photo_id, FinalSelectionDecision.included).where(
            FinalSelectionDecision.photo_id.in_(photo_ids)
        )
    )
    return {photo_id: included for photo_id, included in result.all()}


def _selection_state_of(
    photo: Photo, *, proposed: bool, decision: bool | None, user_count: int
) -> SelectionState:
    """Die Eingaenge der Endauswahl-Regel aus EINEM Foto - die Regel selbst lebt in
    `album_selection.py` und nur dort.

    Die beiden Zaehlungen laufen ueber `Rating.status`, NIE ueber das Vorhandensein der Zeile:
    Seit ADR 0098 kann eine Zeile allein den Favoriten tragen, und ein Existenztest machte aus
    einer Auszeichnung eine Streichung.

    EINE Stelle fuer beide Leser (`_to_photo_out` und der Zustandsfilter von
    `album_selection`): Zweimal geschrieben liefe die Antwortmenge an dem Tag von den gelieferten
    Feldern auseinander, an dem eine der beiden Stellen sich aendert - die Ansicht zeigte dann ein
    Bild, dessen eigene Felder sagen, dass es nicht dazugehoert."""
    return selection_state(
        taken=sum(1 for r in photo.ratings if r.status is RatingStatus.ALBUM_WORTHY),
        rejected=sum(1 for r in photo.ratings if r.status is RatingStatus.REJECTED),
        user_count=user_count,
        proposed=proposed,
        decision=decision,
    )


async def _participants(session: AsyncSession) -> list[AlbumParticipantOut]:
    """Alle Konten als AUSDRUECKLICHE Projektion auf zwei Spalten, nach `user_id` sortiert.

    Nie `model_validate(User)`: `password_hash` und `created_at` duerfen diesen Endpunkt nicht
    erreichen (Auflage S8). Die LAENGE dieser Liste ist der Nenner der Regel - sie stammt damit
    aus derselben Leseoperation wie die Anzeige, und die beiden koennen nicht auseinandergehen."""
    rows = (await session.execute(select(User.id, User.username).order_by(User.id))).all()
    return [AlbumParticipantOut(user_id=user_id, username=username) for user_id, username in rows]


async def _user_count(session: AsyncSession) -> int:
    """Der NENNER der Einigkeitsregel: die Zahl der Konten im Bestand.

    Eine einzelne Zahl statt der Nutzerliste, weil die drei Bestands-Lesepfade (Listing, Entwurf,
    Alternativen) von der Nutzermenge nichts anderes brauchen. Der neue Endpunkt zaehlt bewusst
    NICHT hierueber: Er liefert `participants` mit aus, und sein Nenner stammt aus DERSELBEN
    Leseoperation (Auflage S8) - gingen beide auseinander, behauptete die Ansicht Einigkeit ueber
    zwei Teilnehmer, waehrend die Regel ueber drei rechnet, und kein Feld der Antwort saehe dabei
    widerspruechlich aus.

    RESTRISIKO, bewusst getragen und in der Spec benannt: Der Nenner ist die GLOBALE Nutzerzahl.
    Ein drittes, administrativ angelegtes Konto aendert die Endauswahl jedes Projekts, ohne dass
    ein Schreibzugriff stattfindet."""
    return (await session.execute(select(func.count()).select_from(User))).scalar_one()


def _to_photo_out(
    photo: Photo,
    current_user_id: int,
    project: Project,
    ranking: PhotoRanking | None = None,
    partition_sizes: Mapping[int, int] | None = None,
    curation_positions: Mapping[int, int] | None = None,
    place: PhotoPlace = NO_PLACE,
    motifs: Mapping[str, EffectiveStrength] | None = None,
    *,
    decisions: Mapping[int, bool],
    user_count: int,
) -> PhotoOut:
    """Baut die Antwortdarstellung EINES Fotos.

    SICHERHEIT - die Antwort ist eine Funktion des ANFRAGENDEN Nutzers:

    Bekommen `GET /projects/{id}/photos` (in BEIDEN Modi), `GET /projects/{id}/draft-alternatives`
    oder `GET /projects/{id}/album-selection` je eine Antwort-Zwischenspeicherung, ein `ETag` oder
    ein `Cache-Control` ueber `no-store` hinaus, MUSS der Schluessel den Nutzer enthalten. Dafuer
    gibt es seit ADR 0098 ZWEI UNABHAENGIGE URSACHEN; der Wegfall der einen hebt die Auflage nicht
    auf:

    * der ANTWORTKOERPER: `PhotoOut.suggestion` wird unten genau dann gesetzt, wenn der anfragende
      Nutzer noch keine eigene Albumentscheidung fuer dieses Foto hat (`has_own_album_decision`) -
      zwei Nutzer bekommen fuer dasselbe Foto verschiedene Antwortkoerper.
    * die MENGE: Der Entwurfszweig liefert `Vorschlag ∪ eigene Aufnahmen` und ist damit je Nutzer
      eine ANDERE Liste; `total` des Alternativen-Endpunkts ist die Restmenge nach Abzug des
      EIGENEN Entwurfs. Bei Verletzung saehe der eine den Entwurf des anderen als seinen eigenen,
      ohne dass irgendeine Anzeige das als falsch ausweist.

    Nicht theoretisch: das Frontend ist eine PWA mit Workbox
    (`registerType: 'autoUpdate'`), heute ohne `runtimeCaching` fuer API-Antworten; der
    Service-Worker-Cache ist pro Browserprofil geteilt, und das JWT liegt in `localStorage` - zwei
    Personen an einem Geraet ist der realistische Familienfall.

    `PhotoOut.ratings[]` traegt diese Auflage AUSDRUECKLICH NICHT: die Liste enthaelt beide
    Bewertungen und ist fuer beide Anfragenden identisch - sichtbare Fremdbewertung ist gewollt.
    `RankingOut.proposed` ebenso wenig: es ist lauf-global.

    Auf `GET /projects/{id}/album-selection` trifft von den beiden Ursachen nur die erste zu: Die
    MENGE ist dort nutzerunabhaengig, `PhotoOut.suggestion` bleibt es nicht. EINE Ursache genuegt;
    die Abwesenheit der anderen ist keine Erlaubnis (Auflage S7).

    `curation_position` traegt keinen Ablehnungsfilter; sie numeriert die gelieferte Reihenfolge
    und haengt damit an der Menge, nicht an einer Bewertung.

    `decisions` und `user_count` sind PFLICHTIGE Schluesselwortparameter ohne Vorgabewert (Auflage
    S9). Ein vergessener Aufrufer wirft keine Ausnahme und liefert keinen Fehlercode - er
    antwortete `in_final_selection: false` fuer jedes Foto, plausibel und still. Das ist die
    Menge, die als Album gilt und die der Export nimmt; der Fehler zeigte sich erst an einem
    leeren Album, nicht an der Stelle, an der er entsteht. `mypy --strict` ist die einzige
    Pruefung, die ihn vor der Laufzeit faengt.

    Die drei Felder sind PROJEKTAUSSAGEN und tragen die Cache-Auflage ausdruecklich NICHT - genau
    wie `ratings[]` und `RankingOut.proposed`."""
    # Anzeigeregel: ein Vorschlag ist nur sichtbar, wenn (a) er OFFEN ist - gestellt und im
    # Duplikat-Vergleich noch nicht beantwortet (ADR 0104) - UND (b) der anfragende Nutzer noch
    # KEINE eigene ALBUMENTSCHEIDUNG fuer dieses Foto hat, unabhaengig davon, ob eine ANDERE
    # Person das Foto schon bewertet hat; die eigene Bewertung hat immer Vorrang.
    #
    # Das VORHANDENSEIN der Bewertungszeile ist hier keine Aussage: seit `favorite` eine eigene
    # Spalte ist, existiert eine Zeile auch ohne jede Albumentscheidung. Ueber das
    # Zeilenvorhandensein gepruefte Abwesenheit liesse den Ausschuss-Vorschlag verschwinden, sobald
    # jemand das Foto als Favorit markiert - ohne Meldung und ohne Weg zurueck.
    has_own_album_decision = any(
        rating.user_id == current_user_id and rating.status is not None for rating in photo.ratings
    )
    has_suggestion = has_open_suggestion_for(photo) and not has_own_album_decision
    suggestion = _to_suggestion_out(photo.score) if has_suggestion and photo.score else None
    decision = decisions.get(photo.id)
    state = _selection_state_of(
        photo,
        proposed=ranking is not None and ranking.selection_position is not None,
        decision=decision,
        user_count=user_count,
    )
    return PhotoOut(
        id=photo.id,
        relative_path=photo.relative_path,
        taken_at=photo.taken_at,
        taken_at_original=photo.taken_at_original,
        # Ganze Minuten VON KONSTRUKTION WEGEN: der Versatz ist eine Ganzzahl Minuten, beide
        # Zeitstempel entstehen aus derselben Rechnung, und die Division bleibt damit ohne Rest.
        time_offset_minutes=round((photo.taken_at - photo.taken_at_original).total_seconds() / 60),
        camera=(
            None
            if photo.camera is None
            else CameraOut(
                id=photo.camera.id,
                label=camera_label(
                    CameraIdentity(make=photo.camera.make, model=photo.camera.model)
                ),
            )
        ),
        aspect_ratio=photo.aspect_ratio,
        ratings=[
            RatingOut(
                user_id=r.user_id,
                username=r.user.username,
                status=r.status,
                favorite=r.favorite,
            )
            for r in photo.ratings
        ],
        suggestion=suggestion,
        ranking=(
            None
            if ranking is None
            else RankingOut(
                event_id=ranking.event_id,
                rank_score=ranking.rank_score,
                rank_position=ranking.rank_position,
                # Aus der Rangzeile selbst, nicht aus der uebergebenen Auswahlabbildung: `proposed`
                # ist lauf-global und muss auch dort stehen, wo gar keine Auswahl angefordert
                # wurde.
                proposed=ranking.selection_position is not None,
                partition_size=(partition_sizes or {}).get(ranking.event_id, 0),
                curation_position=(curation_positions or {}).get(ranking.photo_id),
            )
        ),
        criterion_scores=_criterion_scores_out(photo),
        fine_labels=_fine_labels_out(photo),
        cloud_vision_status=_cloud_vision_status_out(photo, project),
        # Beide Felder kommen fertig aus `_event_and_location_by_photo_id`. Der Vorgabewert
        # `NO_PLACE` haelt die Ausfallrichtung fest: eine vergessene Durchreichung ergibt `null`,
        # nie einen falschen Ort.
        location=place.location,
        event=place.event,
        motif_assessment=_motif_assessment_out(photo),
        motifs=_motifs_out(photo, motifs),
        album_suitability=_album_suitability_out(photo),
        final_selection_decision=decision,
        in_final_selection=state.included,
        contested=state.contested,
    )


async def _latest_successful_criterion_scoring_run_id(
    session: AsyncSession, project_id: int
) -> int | None:
    return (
        await session.execute(
            select(CriterionScoringRun.id)
            .where(
                CriterionScoringRun.project_id == project_id,
                CriterionScoringRun.status == ScanStatus.SUCCESS,
            )
            .order_by(CriterionScoringRun.started_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


@dataclass(frozen=True)
class PlacedPhotos:
    """Eine Fotomenge, in die Events eines Laufs EINGEORDNET und darin numeriert - drei
    zusammengehoerige Teile EINER Herleitung.

    Nicht mehr `DraftContent`: Die Einordnung traegt seit Spec 0431 ZWEI Zweige, den Album-Entwurf
    eines Nutzers und die gemeinsame Endauswahl des Projekts. Ein Name, der nur den einen nennt,
    laedt dazu ein, sie fuer den anderen ein zweites Mal zu schreiben.

    `event_id_by_photo_id` steht hier und nicht beim Aufrufer: Fuer ein Foto ohne Rangzeile ist die
    Zuordnung ueber die Aufnahmezeit entstanden, und sie ist zugleich der Sortierschluessel
    gewesen. Zweimal hergeleitet liefe sie an dem Tag auseinander, an dem eine der beiden Stellen
    sich aendert.

    Die Lauf-Id gehoert AUSDRUECKLICH NICHT hierher: Jeder der beiden Zweige loest sie selbst auf,
    und sie ist keine Eigenschaft der Einordnung."""

    ordered_ids: list[int]
    curation_positions: dict[int, int]
    event_id_by_photo_id: dict[int, int]


EMPTY_PLACEMENT = PlacedPhotos(ordered_ids=[], curation_positions={}, event_id_by_photo_id={})


def _place_in_events(
    rows: Sequence[tuple[int, datetime, int | None]],
    spans: Sequence[EventSpan],
    position_by_event_id: Mapping[int, int],
) -> PlacedPhotos:
    """Die EINE Einordnung einer Fotomenge in die Events eines Laufs - von BEIDEN Zweigen
    aufgerufen (Entwurf und Endauswahl), nie zweimal geschrieben.

    Zweimal geschrieben ordneten Entwurf und Endauswahl dieselben Fotos verschieden - sichtbar,
    ohne dass eine Pruefung rot wuerde.

    DIE RANGZEILE HAT VORRANG. Ordnet der Lauf ein aufgenommenes Foto einem anderen Event zu, steht
    es dort - nicht dort, wohin seine Zeit zeigte. Ein Foto, dessen Zeit in keine Eventspanne
    faellt und das keine Rangzeile hat, faellt HERAUS: die Ausfallrichtung ist "nicht zeigen", nie
    eine erfundene Gruppe.

    REIHENFOLGE `(events.position, photos.taken_at, photos.id)` - innerhalb eines Events also
    CHRONOLOGISCH nach der korrigierten Aufnahmezeit, ausdruecklich nicht nach
    `selection_position`. Der Schluessel ist damit TOTAL und fuer vorgeschlagene wie aufgenommene
    Fotos derselbe.

    `curation_positions` ist der Platz in der ANGEZEIGTEN Auswahl des Events - lueckenlos ab 1
    ueber die gelieferte Reihenfolge vergeben, nicht die `selection_position`: ein aufgenommenes
    Foto hat keine, und eine Luecke waere eine Aussage ueber einen Platz, den es nicht gibt.

    Die Komplexitaetsklasse ist verbindlich (Auflage S14): ein Durchgang ueber die Zeilen, nie eine
    Abfrage je Foto. Die Eventliste kommt FERTIG herein."""
    placed: list[tuple[int, int, datetime, int]] = []
    event_id_by_photo_id: dict[int, int] = {}
    for photo_id, taken_at, ranked_event_id in rows:
        event_id = (
            ranked_event_id if ranked_event_id is not None else event_for_time(spans, taken_at)
        )
        if event_id is None or event_id not in position_by_event_id:
            continue
        event_id_by_photo_id[photo_id] = event_id
        placed.append((position_by_event_id[event_id], photo_id, taken_at, event_id))

    placed.sort(key=lambda entry: (entry[0], entry[2], entry[1]))

    ordered_ids: list[int] = []
    curation_positions: dict[int, int] = {}
    seen_per_event: dict[int, int] = {}
    for _, photo_id, _, event_id in placed:
        seen_per_event[event_id] = seen_per_event.get(event_id, 0) + 1
        curation_positions[photo_id] = seen_per_event[event_id]
        ordered_ids.append(photo_id)
    return PlacedPhotos(
        ordered_ids=ordered_ids,
        curation_positions=curation_positions,
        event_id_by_photo_id=event_id_by_photo_id,
    )


async def _event_spans_and_positions(
    session: AsyncSession, criterion_scoring_run_id: int
) -> tuple[list[EventSpan], dict[int, int]]:
    """Die Events eines Laufs - EINMAL geladen, als Spannenliste und als Positionsabbildung. Die
    Eingabe von `_place_in_events`, ebenfalls von beiden Zweigen geteilt."""
    event_rows = (
        await session.execute(
            select(Event.id, Event.position, Event.started_at, Event.ended_at).where(
                Event.criterion_scoring_run_id == criterion_scoring_run_id
            )
        )
    ).all()
    spans = [
        EventSpan(event_id=event_id, started_at=started_at, ended_at=ended_at)
        for event_id, _, started_at, ended_at in event_rows
    ]
    return spans, {event_id: position for event_id, position, _, _ in event_rows}


async def _draft_photo_ids(
    session: AsyncSession, project_id: int, user_id: int
) -> tuple[PlacedPhotos, int | None]:
    """Der Album-Entwurf DIESES Nutzers (ADR 0098):
    `Vorschlag(letzter erfolgreicher Lauf) ∪ Aufgenommen(u)`.

    Er ist ABGELEITET und nirgends gespeichert. "Nie angefasst" ist die Abwesenheit einer eigenen
    Albumentscheidung; daraus folgen "genau ein Entwurf je Nutzer", "ueberdauert die Sitzung" und
    "nur unangefasste Plaetze werden neu befuellt" strukturell statt durchgesetzt.

    EINE ABFRAGE FUER DIE VEREINIGUNG, kein Aneinanderhaengen zweier Mengen: `PhotoRanking` ist je
    (Lauf, Foto) eindeutig und `Rating` je (Foto, Nutzer) - ein vorgeschlagenes UND aufgenommenes
    Foto steht deshalb in genau einer Zeile und genau einmal in der Antwort.

    KEIN ABLEHNUNGSFILTER: ein gestrichenes Foto des Vorschlags bleibt in der Antwort und traegt
    seinen Zustand in `PhotoOut.ratings[]` - Streichen ist ein Anzeigezustand, kein Filter. Ein
    gestrichenes Foto, das weder vorgeschlagen noch je aufgenommen war, geraet dadurch NICHT in
    den Entwurf: es erfuellt keine der beiden Bedingungen.

    OHNE ERFOLGREICHEN LAUF IST DER ENTWURF LEER, auch wenn der Nutzer bereits Fotos aufgenommen
    hat - es gibt dann weder einen Vorschlag noch Events, in die einzuordnen waere. Dasselbe gilt
    fuer ein Foto, dessen Zeit in keiner Eventspanne des Laufs einzuordnen ist (ein Lauf ohne
    Events): die Ausfallrichtung ist "nicht zeigen", nie eine erfundene Gruppe.

    REIHENFOLGE `(events.position, photos.taken_at, photos.id)` - innerhalb eines Events also
    CHRONOLOGISCH nach der korrigierten Aufnahmezeit, ausdruecklich nicht nach
    `selection_position`. Der Schluessel ist damit TOTAL und fuer vorgeschlagene wie aufgenommene
    Fotos derselbe. Nach `selection_position NULLS LAST` zu sortieren ist ausgeschlossen: ein
    aufgenommenes Foto hat keinen Platz im Vorschlag und stuende dann stets am Ende seiner Gruppe
    - ein Austausch ersetzte das Bild nicht an seiner Stelle, sondern verschoebe es ans
    Gruppenende.

    AUFLAGE S14 - die Komplexitaetsklasse ist verbindlich, nicht die Eingabegrenze: Die Menge
    waechst mit den eigenen Aufnahmen, bis hin zu jedem Foto des Projekts. Die Eventliste wird
    deshalb EINMAL geladen und die Zuordnung laeuft in einem Durchgang darueber, nie als Abfrage
    je Foto.

    Rueckgabe: die Einordnung UND die Lauf-Id - jene gehoert nicht in `PlacedPhotos`, weil sie
    keine Eigenschaft der Einordnung ist und der zweite Zweig sie selbst aufloest."""
    latest_run_id = await _latest_successful_criterion_scoring_run_id(session, project_id)
    if latest_run_id is None:
        return EMPTY_PLACEMENT, None

    # (1) Die Events des Laufs - EINMAL, als Spannenliste und als Positionsabbildung.
    spans, position_by_event_id = await _event_spans_and_positions(session, latest_run_id)

    # (2) Die Vereinigung selbst. Der `outerjoin` auf die Rangzeile traegt beides: das Praedikat
    # des Vorschlags UND die Event-Zuordnung der vorgeschlagenen Fotos.
    own_rating = aliased(Rating)
    ranking = aliased(PhotoRanking)
    rows = (
        await session.execute(
            select(Photo.id, Photo.taken_at, ranking.event_id)
            .where(Photo.project_id == project_id)
            .outerjoin(
                ranking,
                and_(
                    ranking.photo_id == Photo.id,
                    ranking.criterion_scoring_run_id == latest_run_id,
                ),
            )
            .outerjoin(
                own_rating,
                and_(own_rating.photo_id == Photo.id, own_rating.user_id == user_id),
            )
            .where(
                or_(
                    ranking.selection_position.is_not(None),
                    own_rating.status == RatingStatus.ALBUM_WORTHY,
                )
            )
        )
    ).all()

    # (3) Einordnung und Numerierung - dieselbe Funktion, die auch die Endauswahl benutzt. Die
    # Zeilen werden dabei ausgepackt: ein `Row` ist fuer den Typpruefer kein `tuple`, und die reine
    # Funktion soll ausdruecklich keine SQLAlchemy-Form in ihrer Signatur tragen.
    placement_rows = [(photo_id, taken_at, event_id) for photo_id, taken_at, event_id in rows]
    return _place_in_events(placement_rows, spans, position_by_event_id), latest_run_id


async def _partition_sizes(session: AsyncSession, criterion_scoring_run_id: int) -> dict[int, int]:
    """Größe jeder Event-Partition eines Laufs, für "Rang M von N" im Info-Popover - ein einzelner
    GROUP BY-Query pro Aufruf (nicht pro Foto). Bewusst lauf-global, nicht nutzerspezifisch
    gefiltert - siehe RankingOut.partition_size-Docstring.

    Gezählt wird die BEWERTETE Teilmenge: ein Foto ohne Modellbewertung erscheint nicht im
    Entwurf, und eine Größe, die es mitzählte, machte aus "Rang 1 von 1" ein "Rang 1 von 2" über
    einer Partition mit genau einem einsehbaren Foto. Die Zahl an der Event-Überschrift und der
    tatsächlich einsehbare Vorrat müssen dieselbe Menge beschreiben.

    SICHERHEIT (S2): das Lauf-Prädikat steht auch HIER - diese Zählabfrage speist `partition_size`
    auf jedem Lesepfad, den Alternativen-Endpunkt eingeschlossen, und ist damit eine Abfrage
    dieser Endpunkte wie jede andere."""
    result = await session.execute(
        select(PhotoRanking.event_id, func.count())
        .where(
            PhotoRanking.criterion_scoring_run_id == criterion_scoring_run_id,
            PhotoRanking.rank_position.is_not(None),
        )
        .group_by(PhotoRanking.event_id)
    )
    return {event_id: count for event_id, count in result.all()}


async def _ranking_by_photo_id(
    session: AsyncSession, criterion_scoring_run_id: int, photo_ids: list[int]
) -> dict[int, PhotoRanking]:
    """Die Rangzeile je Foto - GENAU EINE, durch den Unique-Constraint `(Lauf, Foto)` garantiert.

    `scalar_one_or_none()` je Foto waere ein Query pro Foto; die Abbildung entsteht deshalb aus
    einer Abfrage."""
    if not photo_ids:
        return {}
    result = await session.execute(
        select(PhotoRanking).where(
            PhotoRanking.criterion_scoring_run_id == criterion_scoring_run_id,
            PhotoRanking.photo_id.in_(photo_ids),
        )
    )
    return {row.photo_id: row for row in result.scalars()}


# SICHERHEIT - Obergrenze von `offset`/`camera_id`/`event_id`/`photo_id`: ein Pydantic-`int` ist
# unbeschraenkt und landet direkt im SQL-Vergleich; unter SQLite (Testlauf und lokale Entwicklung)
# wirft ein Wert jenseits von 2^63 einen `OverflowError` und damit eine 500 statt einer leeren
# Liste. Der Wert liegt weit ueber jeder realistischen Partitionsgroesse - er begrenzt einen
# Missbrauchsfall, nicht die Benutzung.
#
# Steht VOR `list_photos`, nicht erst vor dem Alternativen-Endpunkt: `Query(...)`-Vorgabewerte
# werden zur DEFINITIONSZEIT ausgewertet, eine spaeter definierte Konstante bricht den Import.
#
# OEFFENTLICH (kein fuehrender Unterstrich), weil die Grenze GETEILT ist: `api/duplicate_decisions.py`
# zieht sie von hier. Ein geteilter Grenzwert soll nicht zweimal dastehen - zwei Zahlen liefen
# auseinander, und die kleinere entschiede still, welche Anfrage `422` statt `404` bekommt. Die
# aeltere Nachbildung in `api/cameras.py` bleibt vorerst stehen (eigener Wert, eigene Begruendung);
# sie darf spaeter hierher zusammengezogen werden.
MAX_QUERY_POSITION = 1_000_000_000


@router.get("/projects/{project_id}/photos", response_model=PhotoListOut)
async def list_photos(
    project_id: int,
    rating_status: RatingFilter | None = None,
    # ENTWURFSMODUS. Gesetzt, ersetzt er `rating_status` vollstaendig (eigenstaendige
    # Entwurfsansicht) und liefert den Album-Entwurf DES ANFRAGENDEN NUTZERS als GANZES.
    #
    # SICHERHEIT (S4/S14): `limit`/`offset` werden in diesem Zweig VOLLSTAENDIG ignoriert - nie
    # halb. Die Obergrenze der Antwort ist der auswahlfaehige Bestand des Laufs zuzueglich der
    # eigenen Aufnahmen. Das wird bewusst getragen (die Menge waechst nur durch Handlungen des
    # Anfragenden selbst, beide Nutzer sind die Vertrauensbasis). Wirkten `limit`/`offset` hier
    # HALB, zeigte die Ansicht einen abgeschnittenen Entwurf als vollstaendigen an, und der
    # Kopfbereich naennte eine Ist-Anzahl, die es nicht gibt - ein Zustand, den keine Anzeige als
    # fehlerhaft ausweist.
    draft: bool = False,
    # Der alte Auswahlparameter, mit ADR 0098 ersetzt. Er steht hier noch als `None`-typisierter
    # Parameter, damit ein Aufruf mit ihm LAUT scheitert (`422`) statt still ignoriert zu werden -
    # in BEIDEN Belegungen. `selection=false` ist der gefaehrlichere Fall: heute ein gueltiger
    # Aufruf, der sonst still in den Listing-Zweig fiele. Die Antwortmenge des Nachfolgers ist
    # zudem NUTZERABHAENGIG; ein stehengebliebener Aufrufer bekaeme also nicht bloss eine andere
    # Menge, sondern eine mit anderer Bedeutung.
    selection: None = Query(None, include_in_schema=False),
    # Der alte Kuratierungsparameter, mit ADR 0097 ERSATZLOS entfallen. Er steht hier noch als
    # `None`-typisierter Parameter, damit ein Aufruf mit ihm LAUT scheitert (`422`) statt still
    # ignoriert zu werden: FastAPI uebergeht einen unbekannten Query-Parameter kommentarlos, und
    # ein stehengebliebener Aufrufer bekaeme dann den vollen Listing-Zweig statt einer Auswahl -
    # ohne dass irgendwo ein Fehler sichtbar wuerde. Ein Uebergangsweg, der beide Parameter
    # kennt, entsteht bewusst nicht; er waere eine zweite Auswahlregel.
    top_n_per_event: None = Query(None, include_in_schema=False),
    # Ohne diesen Filter kann die Oberflaeche die beiden Fotos fuer den Versatz-Vorschlag nicht
    # anbieten. `ge=1` schliesst `0` und negative Werte aus, `le` verhindert, dass ein Wert
    # jenseits von 2^63 unter SQLite einen OverflowError und damit eine 500 statt einer leeren
    # Liste erzeugt (Muster `MAX_QUERY_POSITION`).
    camera_id: int | None = Query(None, ge=1, le=MAX_QUERY_POSITION),
    limit: int = Query(60, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PhotoListOut:
    project = await _get_project_or_404(project_id, session)

    if draft:
        content, criterion_scoring_run_id = await _draft_photo_ids(
            session, project_id, current_user.id
        )
        ids = content.ordered_ids
        photos_by_id = await _photos_by_id(session, ids)
        rankings_by_id = (
            await _ranking_by_photo_id(session, criterion_scoring_run_id, ids)
            if criterion_scoring_run_id is not None
            else {}
        )
        partition_sizes = (
            await _partition_sizes(session, criterion_scoring_run_id)
            if criterion_scoring_run_id is not None
            else {}
        )
        place_by_id = await _event_and_location_by_photo_id(
            session,
            project_id,
            criterion_scoring_run_id,
            photos_by_id,
            # Die Abbildung kommt aus der Entwurfsherleitung, NICHT aus den Rangzeilen: ein
            # aufgenommenes Foto ohne Rangzeile haette dort keinen Eintrag und verloere seine
            # Eventueberschrift, obwohl es in der Liste steht.
            content.event_id_by_photo_id,
        )
        motifs_by_id = await load_effective_strengths(session, ids)
        decisions = await _final_selection_decisions(session, ids)
        user_count = await _user_count(session)
        items = [
            _to_photo_out(
                photos_by_id[photo_id],
                current_user.id,
                project,
                rankings_by_id.get(photo_id),
                partition_sizes,
                content.curation_positions,
                place_by_id.get(photo_id, NO_PLACE),
                motifs_by_id.get(photo_id),
                decisions=decisions,
                user_count=user_count,
            )
            for photo_id in ids
        ]
        return PhotoListOut(items=items, total=len(items))

    ids, total = await _filtered_photo_ids(
        session, project_id, current_user.id, rating_status, limit, offset, camera_id
    )
    photos_by_id = await _photos_by_id(session, ids)
    # RankingOut wird AUCH hier im Standard-Listing-Zweig befüllt, nicht nur bei
    # top_n_per_event - Grid-/Detailansicht sollen ebenfalls Rang-Score/-Position zeigen
    # koennen, unabhaengig vom top_n_per_event-Kuratierungsmodus.
    latest_run_id = await _latest_successful_criterion_scoring_run_id(session, project_id)
    rankings_by_id = (
        await _ranking_by_photo_id(session, latest_run_id, ids) if latest_run_id is not None else {}
    )
    partition_sizes = (
        await _partition_sizes(session, latest_run_id) if latest_run_id is not None else {}
    )
    place_by_id = await _event_and_location_by_photo_id(
        session, project_id, latest_run_id, photos_by_id, _event_ids_from_rankings(rankings_by_id)
    )
    motifs_by_id = await load_effective_strengths(session, ids)
    decisions = await _final_selection_decisions(session, ids)
    user_count = await _user_count(session)
    items = [
        _to_photo_out(
            photos_by_id[photo_id],
            current_user.id,
            project,
            rankings_by_id.get(photo_id),
            partition_sizes,
            # Ohne angeforderte Auswahl traegt JEDE Zugehoerigkeit `curation_position = null` - es
            # gibt in diesem Modus keine Auswahl, zu der sie eine Position haben koennte.
            None,
            place_by_id.get(photo_id, NO_PLACE),
            motifs_by_id.get(photo_id),
            decisions=decisions,
            user_count=user_count,
        )
        for photo_id in ids
    ]
    return PhotoListOut(items=items, total=total)


@router.get("/projects/{project_id}/album-selection", response_model=AlbumSelectionOut)
async def album_selection(
    project_id: int,
    session: AsyncSession = Depends(get_session),
    # SICHERHEIT (S1): ausgeschriebene Auth-Dependency. Dieser Router traegt bewusst KEINE
    # router-weite `dependencies`-Liste (siehe Kopfkommentar der Datei) - ein Endpunkt, der diesen
    # Parameter vergisst, waere STILL OEFFENTLICH. `current_user.id` geht unveraendert an
    # `_to_photo_out`: die MENGE dieser Antwort ist zwar nutzerunabhaengig, `PhotoOut.suggestion`
    # bleibt es nicht.
    current_user: User = Depends(get_current_user),
) -> AlbumSelectionOut:
    """Die gemeinsame Endauswahl des Projekts - die Menge, die als Album gilt (ADR 0099).

    Sie ist ABGELEITET und nirgends gespeichert: Gespeichert wird allein die ausdrueckliche
    gemeinsame Entscheidung. Einigkeit beider Entwuerfe ist eine VORBELEGUNG, die nur wirkt,
    solange keine Entscheidung vorliegt; eine getroffene Entscheidung ueberlebt umgekehrt jede
    spaetere Entwurfsaenderung und jeden neuen Vorschlagslauf.

    Die Antwort traegt DREI Teile: `participants` (alle Konten, auch das ohne jede Bewertung),
    `has_proposal` (trennt die beiden Leerzustaende) und `items`.

    DIE ANTWORTMENGE IST ADDITIV: `strittig ∪ Endauswahl ∪ entschieden`. Der dritte Teil ist keine
    Redundanz (ADR 0099 Punkt 5) - ein ausdruecklich HERAUSGENOMMENES Bild gehoert nicht zur
    Endauswahl und verschwaende sonst aus beiden Sichten; die Entscheidung liesse sich dann nicht
    mehr aendern, obwohl die Story das ausdruecklich zusagt. Es bleibt stattdessen mit einem
    Anzeigezustand stehen, genau wie ein gestrichenes Foto im Entwurf (ADR 0071 Entscheidung 3).
    Kein Ausschluss bildet die Menge. Ein Bild, das BEIDE gestrichen haben und ueber das niemand
    entschieden hat, erscheint hier nicht; der Weg zurueck fuehrt ueber den Einzelentwurf.

    KEINE SEITENWEISE, wie der Entwurfszweig (ADR 0098, Auflage S14). Die Obergrenze der Antwort
    ist `Vorschlag ∪ jemals bewertet ∪ entschieden`; die Zahl der Abfragen ist fest und
    unabhaengig von der Fotoanzahl.

    SICHERHEIT - Projektbindung (S2): `Photo.project_id == project_id` ist eine UND-Bedingung
    ueber die GESAMTE Kandidatenmenge und steht AUSSERHALB der ODER-Verknuepfung ihrer drei
    Quellen; der Rangzweig haengt zusaetzlich am `criterion_scoring_run_id` des letzten
    erfolgreichen Laufs DIESES Projekts. Zwei der drei Quellen sind projektblind:
    `final_selection_decisions` hat nur `photo_id`, `Rating` nur `(photo_id, user_id)`, und
    `PhotoRanking` traegt keine `project_id`. Ein in die ODER-Verknuepfung gerutschtes
    Projektpraedikat ist syntaktisch unauffaellig und liesse jedes jemals bewertete oder
    entschiedene Foto ALLER Projekte in die Antwort - die Endauswahl eines Projekts enthielte dann
    kohaerent aussehende Fotos eines anderen, und das ist die Menge, die der Export nimmt.
    `_photos_by_id` filtert nur nach Id und ist ausdruecklich KEINE zweite Verteidigungslinie.

    SICHERHEIT (S8): `user_count` stammt aus DERSELBEN Leseoperation wie `participants`. Gingen
    beide auseinander, behauptete die Ansicht Einigkeit ueber zwei Teilnehmer, waehrend die Regel
    ueber drei rechnet - kein Feld der Antwort saehe dabei widerspruechlich aus."""
    project = await _get_project_or_404(project_id, session)

    # (1) Teilnehmer UND Nenner aus EINER Leseoperation (S8).
    participants = await _participants(session)
    user_count = len(participants)

    latest_run_id = await _latest_successful_criterion_scoring_run_id(session, project_id)
    if latest_run_id is None:
        # Ohne erfolgreichen Lauf gibt es weder Vorschlag noch Events, in die einzuordnen waere -
        # die Teilnehmerliste steht trotzdem, sonst waere der Leerzustand nicht von einer Instanz
        # ohne Konten zu unterscheiden.
        return AlbumSelectionOut(participants=participants, has_proposal=False, items=[])

    # (2) Die Events des Laufs - einmal, ueber dieselbe Beschaffung wie der Entwurfszweig.
    spans, position_by_event_id = await _event_spans_and_positions(session, latest_run_id)

    # (3) DIE KANDIDATENMENGE, eine Obermenge, in EINER Abfrage: vorgeschlagen ODER entschieden
    # ODER jemals mit einer Albumentscheidung versehen. Sie ist vollstaendig - ohne jede
    # Bewertungszeile sind alle Nutzer einig, und Zugehoerigkeit ohne Entscheidung setzt den
    # Vorschlag voraus.
    #
    # `Rating.status.is_not(None)` und nicht das Vorhandensein der Zeile: eine reine
    # Favoritenzeile ist keine Aussage ueber die Albumzugehoerigkeit und holt ein sonst
    # unbeteiligtes Foto nicht herein.
    ranking = aliased(PhotoRanking)
    decision_row = aliased(FinalSelectionDecision)
    candidate_rows = (
        await session.execute(
            select(Photo.id, Photo.taken_at, ranking.event_id, ranking.selection_position)
            # SICHERHEIT (S2): das Pflichtpraedikat, UND-verknuepft ueber die gesamte Menge.
            .where(Photo.project_id == project_id)
            .outerjoin(
                ranking,
                and_(
                    ranking.photo_id == Photo.id,
                    ranking.criterion_scoring_run_id == latest_run_id,
                ),
            )
            .outerjoin(decision_row, decision_row.photo_id == Photo.id)
            .where(
                or_(
                    ranking.selection_position.is_not(None),
                    decision_row.photo_id.is_not(None),
                    Photo.id.in_(select(Rating.photo_id).where(Rating.status.is_not(None))),
                )
            )
        )
    ).all()

    # `has_proposal` aus den Kandidatenzeilen, ohne eigene Abfrage: ein Foto mit
    # `selection_position` ist ueber das erste Praedikat immer Kandidat.
    has_proposal = any(row.selection_position is not None for row in candidate_rows)

    # (4) Hydratation der Kandidaten - `photo.ratings` samt `Rating.user` ist dort bereits eager
    # geladen, die Zaehlung darunter loest deshalb keinen Lazy-Load aus.
    candidate_ids = [row.id for row in candidate_rows]
    photos_by_id = await _photos_by_id(session, candidate_ids)
    decisions = await _final_selection_decisions(session, candidate_ids)

    # (5) DER ZUSTANDSFILTER: behalten wird, was strittig ist ODER zur Endauswahl gehoert ODER
    # eine Entscheidung traegt - derselbe `selection_state`-Aufruf, den `_to_photo_out` danach
    # fuer die Felder benutzt. Ohne ihn stuende jedes von beiden gestrichene Foto in der Antwort.
    kept_rows: list[tuple[int, datetime, int | None]] = []
    for row in candidate_rows:
        # Direkter Zugriff, KEIN `.get(...)` mit stillem Ueberspringen: Jede Kandidaten-Id stammt
        # aus `select(Photo.id)` derselben Transaktion, `_photos_by_id` liefert sie also alle.
        # Ein fehlender Eintrag waere ein Fehler und soll laut scheitern - stillschweigend
        # uebersprungen verschwaende ein Foto aus dem Album, ohne dass etwas es meldet.
        photo = photos_by_id[row.id]
        decision = decisions.get(row.id)
        state = _selection_state_of(
            photo,
            proposed=row.selection_position is not None,
            decision=decision,
            user_count=user_count,
        )
        if state.contested or state.included or decision is not None:
            kept_rows.append((row.id, row.taken_at, row.event_id))

    placed = _place_in_events(kept_rows, spans, position_by_event_id)
    ids = placed.ordered_ids
    rankings_by_id = await _ranking_by_photo_id(session, latest_run_id, ids)
    partition_sizes = await _partition_sizes(session, latest_run_id)
    place_by_id = await _event_and_location_by_photo_id(
        session,
        project_id,
        latest_run_id,
        {photo_id: photos_by_id[photo_id] for photo_id in ids},
        placed.event_id_by_photo_id,
    )
    motifs_by_id = await load_effective_strengths(session, ids)
    items = [
        _to_photo_out(
            photos_by_id[photo_id],
            current_user.id,
            project,
            rankings_by_id.get(photo_id),
            partition_sizes,
            # KEINE `curation_position`: Die Endauswahl ist keine numerierte Auswahl, und eine
            # Zahl hier waere eine Rangaussage ueber eine Menge, die keinen Rang kennt.
            None,
            place_by_id.get(photo_id, NO_PLACE),
            motifs_by_id.get(photo_id),
            decisions=decisions,
            user_count=user_count,
        )
        for photo_id in ids
    ]
    return AlbumSelectionOut(participants=participants, has_proposal=has_proposal, items=items)


class DuplicateGroupPhotoOut(BaseModel):
    """Ein Mitglied der Duplikat-Gruppe: das Foto, sein wirksamer Zustand und ob sich dieser
    ueberhaupt aendern laesst.

    DIE ANTWORT NENNT DIE AUSWERTUNG DES UEBERLEBENS-PRAEDIKATS, NICHT DIE ENTSCHEIDUNGSZEILE
    (ADR 0111). Die beiden fielen genau dort auseinander, wo keine Zeile steht: Ein unentschiedener
    Duplikat-Verlierer traegt `suggested_status = REJECTED` und scheidet aus, sah aber aus wie der
    Repraesentant, der bleibt. Es gibt deshalb keinen dritten Wert und kein `null`, und aus der
    Antwort geht nicht hervor, ob ein Zustand vom Automaten oder vom Nutzer stammt.

    `keep_possible = false` heisst: Kein Wert der Entscheidungszeile aendert diesen Zustand - die
    Ablehnung folgt nicht aus dem Duplikat. Der GRUND reist nicht als Feld, weil er aus der
    Bedingung selbst folgt; die Oberflaeche rendert dort einen festen Text. Entstuende ein dritter
    Ablehnungsgrund, gehoert er ab dann als eigenes Feld hierher (ADR 0111, Konsequenzen) -
    `tests/test_duplikat_anzeigezustand.py` laesst das laut auffallen."""

    photo: PhotoOut
    effective_decision: DuplicateDecision
    keep_possible: bool


class DuplicateGroupOut(BaseModel):
    """Die Antwortform ALLER DREI Endpunkte der Vergleichsansicht - Lesepfad wie beide
    Schreibwege. Ein Schreibvorgang liefert damit denselben vollstaendigen Stand zurueck, den ein
    erneutes Laden liefern wuerde; die Oberflaeche braucht danach keine zweite Anfrage, um zu
    wissen, was gilt.

    `position`/`total` sind 1-basiert und beziehen sich auf ALLE Duplikat-Gruppen des Projekts.
    `previous_photo_id`/`next_photo_id` tragen die Repraesentanten-Id der jeweils benachbarten
    Gruppe, `null` am Rand - dort ist die Schaltflaeche `disabled`, nicht abwesend.

    SICHERHEIT (S6): Beide Nachbar-Ids stammen aus derselben projektbegrenzten Kantenliste wie die
    Gruppe selbst, nie aus einer eigenen Abfrage auf `photo_scores` - dessen `duplicate_of` zeigt
    auf `photos.id` ohne Projektbedingung. Zugriffsmarken sind sie nicht: Die Folgeanfrage laeuft
    erneut ueber `project_id` und loest eine fremde Id nicht auf."""

    items: list[DuplicateGroupPhotoOut]
    position: int
    total: int
    previous_photo_id: int | None
    next_photo_id: int | None


async def build_duplicate_group_out(
    session: AsyncSession, project: Project, photo_id: int, current_user_id: int
) -> DuplicateGroupOut:
    """Bildet den Stern um `photo_id` und hydratisiert seine Mitglieder zur vollen Antwort.

    VON ALLEN DREI ENDPUNKTEN GENUTZT, auch von den beiden Schreibwegen im eigenen Router - genau
    deshalb steht der Aufbau hier und nicht im Endpunkt: Die Hydratation (`_photos_by_id`,
    `_to_photo_out` samt Event-, Orts- und Rang-Kontext) haengt an dieser Datei, und eine zweite
    Fassung davon liefe auseinander.

    `404` (als `HTTPException`), wenn es keine Gruppe gibt. Der Fall deckt unbekannte Id, fremdes
    Projekt (die Kantenliste ist bereits projektbegrenzt, S7) und "Foto in keinem Stern" - und
    unterscheidet sie ausdruecklich nicht.

    SICHERHEIT (S10): Die Antwort traegt `PhotoOut` und damit `suggestion`/`ratings`; sie ist
    damit eine Funktion des ANFRAGENDEN Nutzers. Bekaeme sie je eine Zwischenspeicherung, ein
    `ETag` oder ein `Cache-Control` ueber `no-store` hinaus, muss der Schluessel den Nutzer
    enthalten."""
    links = await load_duplicate_links(session, project.id)
    representative_id = representative_of(photo_id, links)
    if representative_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Keine Duplikat-Gruppe zu diesem Foto."
        )
    stellung = group_standing(representative_id, links)
    # `representative_of` hat die Gruppe soeben aufgeloest - `group_standing` kann sie nicht mehr
    # verfehlen. Der Zweig steht trotzdem, weil `mypy --strict` sonst das `None` durchliesse.
    assert stellung is not None

    ids = member_ids_of(representative_id, links)
    photos_by_id = await _photos_by_id(session, ids)
    latest_run_id = await _latest_successful_criterion_scoring_run_id(session, project.id)
    rankings_by_id = (
        await _ranking_by_photo_id(session, latest_run_id, ids) if latest_run_id is not None else {}
    )
    partition_sizes = (
        await _partition_sizes(session, latest_run_id) if latest_run_id is not None else {}
    )
    place_by_id = await _event_and_location_by_photo_id(
        session, project.id, latest_run_id, photos_by_id, _event_ids_from_rankings(rankings_by_id)
    )
    motifs_by_id = await load_effective_strengths(session, ids)
    final_decisions = await _final_selection_decisions(session, ids)
    user_count = await _user_count(session)
    return DuplicateGroupOut(
        items=[
            DuplicateGroupPhotoOut(
                photo=_to_photo_out(
                    photos_by_id[member_id],
                    current_user_id,
                    project,
                    rankings_by_id.get(member_id),
                    partition_sizes,
                    # Keine `curation_position`: Die Gruppe ist keine numerierte Auswahl.
                    None,
                    place_by_id.get(member_id, NO_PLACE),
                    motifs_by_id.get(member_id),
                    decisions=final_decisions,
                    user_count=user_count,
                ),
                # BEIDE WERTE KOMMEN AUS `duplicates.py`, nie als ausgeschriebene Bedingung hier
                # (Auflage S2): Sie ziehen dasselbe Praedikat, das bestimmt, welche Bilder den
                # Homeserver Richtung Cloud-Anbieter verlassen. Eine zweite Fassung liefe von der
                # ersten weg, ohne Fehler und ohne Meldung -
                # `tests/test_ausschuss_ueberlebende.py` schlaegt fuer jede hier ausgeschriebene
                # Fassung an.
                effective_decision=effective_decision_for(photos_by_id[member_id]),
                keep_possible=keep_possible_for(photos_by_id[member_id]),
            )
            for member_id in ids
        ],
        position=stellung.position,
        total=stellung.total,
        previous_photo_id=stellung.previous_id,
        next_photo_id=stellung.next_id,
    )


def empty_duplicate_group_out() -> DuplicateGroupOut:
    """Der leere Gruppenstand fuer eine Aufnahme OHNE Gruppe (Spec 0525, AK6).

    Der Einzel-Schreibweg nimmt seit Spec 0525 auch die Unschaerfe-Ablehnung an, die in keinem
    Stern liegt: Dort ist die Entscheidung selbst das Ergebnis und es gibt keine Gruppe, die man
    zurueckgeben koennte. Die Antwortform bleibt trotzdem dieselbe `DuplicateGroupOut` - die
    Oberflaeche schreibt den Rueckgabewert der Entscheidung unmittelbar fort und braucht eine
    zweite Anfrage sonst nur, um zu erfahren, dass es nichts zu zeigen gibt.

    `position = 0` ist der eine Wert, der NICHT der 1-basierten Zaehlung der gefuellten Antwort
    folgt, und er ist genau dafuer da: Ein Platz in einer Reihenfolge, die es nicht gibt, waere
    eine erfundene Auskunft. `total = 0` sagt dasselbe ueber die Gesamtzahl."""
    return DuplicateGroupOut(
        items=[], position=0, total=0, previous_photo_id=None, next_photo_id=None
    )


class DuplicateGroupIndexOut(BaseModel):
    """Die Auskunft fuer den EINSTIEG: wie viele Duplikat-Gruppen es gibt und wo der Durchgang
    beginnt.

    `first_photo_id` ist `null`, wenn es keine Gruppe gibt - die Oberflaeche rendert den Einstieg
    dann gar nicht, statt auf eine leere Ansicht zu fuehren (AK8).

    KEINE LISTE ALLER GRUPPEN (ADR 0111 Punkt 3): Sie waere eine zweite Quelle derselben
    Reihenfolge neben `position`/`total`, deren Momentaufnahmen auseinanderlaufen koennen. Die
    Nachbarn reisen in der Gruppenantwort selbst."""

    total: int
    first_photo_id: int | None


@router.get("/projects/{project_id}/duplicate-groups", response_model=DuplicateGroupIndexOut)
async def duplicate_group_index(
    project_id: Annotated[int, PathParam(ge=1, le=MAX_QUERY_POSITION)],
    session: AsyncSession = Depends(get_session),
    # SICHERHEIT (S1): ausgeschriebene Auth-Dependency. Dieser Router traegt bewusst KEINE
    # router-weite `dependencies`-Liste und keinen Vollstaendigkeitstest - ein Endpunkt, der
    # diesen Parameter vergisst, waere STILL OEFFENTLICH (keine 401, nur Daten). Der eigene
    # 401-Fall steht in `tests/test_api_duplicate_group_index.py`.
    current_user: User = Depends(get_current_user),
) -> DuplicateGroupIndexOut:
    """Wie viele Duplikat-Gruppen dieses Projekt hat und ueber welche Aufnahme die erste beginnt.

    Grundlage der beiden Einstiege in die Vergleichsansicht - aus dem Ausschuss-Schritt und aus der
    nach Vorschlaegen gefilterten Fotoliste. Ohne Foto-Hydratation: Die Antwort traegt kein
    `PhotoOut` und ist damit keine Funktion des anfragenden Nutzers.

    `total` ist DIESELBE Zahl wie in `DuplicateGroupOut` und zaehlt alle Gruppen des Projekts,
    entschiedene eingeschlossen.

    SICHERHEIT (S6): `first_photo_id` stammt aus derselben projektbegrenzten Kantenliste wie die
    Gruppe selbst, nie aus einer eigenen Abfrage auf `photo_scores` - dessen `duplicate_of` zeigt
    auf `photos.id` ohne Projektbedingung. Eine Zugriffsmarke ist die Id nicht: Die Folgeanfrage
    laeuft erneut ueber `project_id`.

    `404` fuer ein unbekanntes Projekt, ohne den uebergebenen Wert zu spiegeln. `422` fuer eine
    Pfad-Id ausserhalb der Grenzen - ein unbeschraenkter Pydantic-`int` erreicht die Datenbank und
    wird jenseits von 2^63 zu `500` statt `404`."""
    project = await _get_project_or_404(project_id, session)
    representatives = all_group_representative_ids(await load_duplicate_links(session, project.id))
    return DuplicateGroupIndexOut(
        total=len(representatives),
        first_photo_id=representatives[0] if representatives else None,
    )


@router.get("/projects/{project_id}/duplicate-groups/{photo_id}", response_model=DuplicateGroupOut)
async def duplicate_group(
    project_id: Annotated[int, PathParam(ge=1, le=MAX_QUERY_POSITION)],
    photo_id: Annotated[int, PathParam(ge=1, le=MAX_QUERY_POSITION)],
    session: AsyncSession = Depends(get_session),
    # SICHERHEIT: ausgeschriebene Auth-Dependency. Dieser Router traegt bewusst KEINE router-weite
    # `dependencies`-Liste (siehe Kopfkommentar der Datei) - ein Endpunkt, der diesen Parameter
    # vergisst, waere STILL OEFFENTLICH.
    current_user: User = Depends(get_current_user),
) -> DuplicateGroupOut:
    """Alle Aufnahmen EINER Duplikat-Gruppe samt ihrem wirksamen Zustand und ihren Nachbargruppen.

    Die Gruppe ist ABGELEITET und nirgends gespeichert (ADR 0104 Punkt 1): Sie ist der Stern ueber
    `PhotoScore.duplicate_of` - der Gewinner und alle, die auf ihn zeigen -, zur Lesezeit gebildet.
    Sie hat deshalb keine eigene Id und ist ueber JEDES ihrer Mitglieder unter derselben Antwort
    erreichbar, den Gewinner eingeschlossen.

    KEIN MITGLIED IST AUSGEZEICHNET. Die Antwort nennt weder Gewinner noch Original noch
    Vorgeschlagenen - die Reihenfolge ist `taken_at`, bei Gleichstand `id`, und sonst nichts.
    Jedes Mitglied traegt aber seinen wirksamen Zustand (`effective_decision`), also das, was ohne
    weiteres Zutun eintritt.

    `position`/`total` beziehen sich auf ALLE Duplikat-Gruppen des Projekts. Eine vollstaendig
    entschiedene Gruppe zaehlt weiter mit und bleibt erreichbar; die Gesamtzahl aendert sich
    waehrend eines Durchgangs nicht, und die Position einer Gruppe verschiebt sich nicht dadurch,
    dass eine andere entschieden wird.

    `404`, wenn es zu dieser Id keine Gruppe gibt - unbekanntes Foto, fremdes Projekt, Foto ohne
    Duplikat, oder ein Vorschlag wegen geringer Bildqualitaet (der traegt kein `duplicate_of`).
    Die vier Faelle sind voneinander nicht unterscheidbar, und die Antwort spiegelt den
    uebergebenen Wert nicht.

    `422` fuer eine Pfad-Id ausserhalb der Grenzen: Ein unbeschraenkter Pydantic-`int` erreicht die
    Datenbank und wird jenseits von 2^63 zu `500` statt `404`."""
    project = await _get_project_or_404(project_id, session)
    return await build_duplicate_group_out(session, project, photo_id, current_user.id)


class AusschussEntryOut(BaseModel):
    """EIN Eintrag der Ausschuss-Uebersicht (Spec 0525).

    `reason` ist der GRUND der Markierung und kommt vom Server, nicht aus einer TypeScript-Ableitung
    (Auflage S7): `duplicate` genau dann, wenn `PhotoScore.duplicate_of IS NOT NULL`, sonst
    `low_quality` - dieselbe Ableitung wie `_suggestion_reason`, keine zweite. Der Grund ist damit
    unterscheidbar, statt ein Sammelzustand zu sein (AK4).

    `decision` ist der GESPEICHERTE Zeilenwert aus `photo_duplicate_decisions`, ausdruecklich NICHT
    `duplicates.py::effective_decision_for` (ADR 0111 Punkt 1): Die Uebersicht zeigt den
    Sichtungsfortschritt, und ein unwirksames `keep` (Unschaerfe-Ablehnung ohne Gruppe) bleibt als
    gespeicherte Handlung sichtbar. Die Detailansicht zieht dieselbe Groesse, damit Uebersicht und
    Detail ueber denselben Bildzustand sprechen. Ein `null` heisst "noch nicht entschieden"; es gibt
    keinen Weg zurueck in diesen Zustand.

    `group_anchor_photo_id` ist der Repraesentant der Duplikatgruppe des Fotos oder `null`. Er
    entsteht ueber `duplicates.py::representative_of` aus der PROJEKTBEGRENZTEN Kantenliste (Auflage
    S6): `PhotoScore.duplicate_of` zeigt auf `photos.id` ohne Projektbedingung, eine eigene Abfrage
    darauf koennte den Gewinner eines fremden Projekts nennen. Eine Zugriffsmarke ist die Id nicht -
    die Folgeanfrage laeuft erneut ueber `project_id`."""

    photo: PhotoOut
    reason: Literal["duplicate", "low_quality"]
    decision: DuplicateDecision | None
    group_anchor_photo_id: int | None


class AusschussOut(BaseModel):
    """Die Antwort des Ausschuss-Lesepfads: der Bestand, seine Groesse und die Zahl der offenen
    Vorschlaege.

    `total` ist die Groesse des GESAMTBESTANDS (paginierbar), `open_count` die projektweite Zahl der
    OFFENEN Vorschlaege - unabhaengig von `limit`/`offset`. Der Bestaetigungsbutton nennt genau
    `open_count` (AK9); aus `len(items)` gebildet nennte er auf der zweiten Seite eine andere Zahl,
    und ein bereits entschiedenes Bild zaehlte mit.

    Die Antwort traegt `PhotoOut` samt `suggestion`/`ratings` und ist damit eine Funktion des
    ANFRAGENDEN Nutzers (Auflage S8): Bekaeme sie je eine Zwischenspeicherung, ein `ETag` oder ein
    `Cache-Control` ueber `no-store` hinaus, muss der Schluessel den Nutzer enthalten."""

    items: list[AusschussEntryOut]
    total: int
    open_count: int


async def _ausschuss_entries_out(
    session: AsyncSession,
    project: Project,
    ids: list[int],
    current_user_id: int,
) -> list[AusschussEntryOut]:
    """Hydratisiert die Ausschuss-Eintraege einer Seite - dieselbe Kontextbeschaffung wie die
    Fotoliste (Rang, Partition, Ort/Event, Motive, Endauswahl), damit ein Eintrag dieselben
    `PhotoOut`-Felder traegt wie jedes andere Foto.

    `links` wird EINMAL fuer die ganze Seite geladen und nicht je Foto: Die Gruppenaufloesung ist
    ohnehin eine Abfrage ueber das ganze Projekt, und je Eintrag gestellt waere sie ein Query pro
    Kachel."""
    if not ids:
        return []
    photos_by_id = await _photos_by_id(session, ids)
    latest_run_id = await _latest_successful_criterion_scoring_run_id(session, project.id)
    rankings_by_id = (
        await _ranking_by_photo_id(session, latest_run_id, ids) if latest_run_id is not None else {}
    )
    partition_sizes = (
        await _partition_sizes(session, latest_run_id) if latest_run_id is not None else {}
    )
    place_by_id = await _event_and_location_by_photo_id(
        session, project.id, latest_run_id, photos_by_id, _event_ids_from_rankings(rankings_by_id)
    )
    motifs_by_id = await load_effective_strengths(session, ids)
    decisions = await _final_selection_decisions(session, ids)
    user_count = await _user_count(session)
    links = await load_duplicate_links(session, project.id)

    entries: list[AusschussEntryOut] = []
    for photo_id in ids:
        photo = photos_by_id[photo_id]
        score = photo.score
        # Der Bestand ist ueber den inneren Join auf `PhotoScore` gebildet - hier kann die Zeile
        # nicht fehlen. Der Zweig steht trotzdem, weil `mypy --strict` sonst das `None` durchliesse.
        assert score is not None
        entscheidung = photo.duplicate_decision
        entries.append(
            AusschussEntryOut(
                photo=_to_photo_out(
                    photo,
                    current_user_id,
                    project,
                    rankings_by_id.get(photo_id),
                    partition_sizes,
                    # Keine `curation_position`: Der Ausschuss ist keine numerierte Auswahl.
                    None,
                    place_by_id.get(photo_id, NO_PLACE),
                    motifs_by_id.get(photo_id),
                    decisions=decisions,
                    user_count=user_count,
                ),
                # SICHERHEIT (S7): die vorhandene Ableitung, nicht eine zweite Fassung davon.
                reason=_suggestion_reason(score),
                decision=None if entscheidung is None else entscheidung.decision,
                group_anchor_photo_id=representative_of(photo_id, links),
            )
        )
    return entries


@router.get("/projects/{project_id}/ausschuss", response_model=AusschussOut)
async def list_ausschuss(
    # SICHERHEIT (S5): deklarativ begrenzt wie der Gruppen-Index daneben - ein unbeschraenkter
    # Pydantic-`int` erreicht die Datenbank und wird jenseits von 2^63 zu `500` statt `404`.
    project_id: Annotated[int, PathParam(ge=1, le=MAX_QUERY_POSITION)],
    # Die Detailansicht der Schritt-Route ist derselbe Endpunkt mit gesetztem Filter (AK5, AK8):
    # `items` traegt dann GENAU den passenden Eintrag oder eine leere Liste, `total`/`open_count`
    # bleiben projektweit, und `limit`/`offset` sind in diesem Zweig ohne Wirkung - das Muster des
    # Alternativ-Zweigs der Fotoliste. Damit ist der Deep-Link `?photo=<id>` auch fuer eine Aufnahme
    # ausserhalb der geladenen Seite definiert.
    #
    # SICHERHEIT (S5): deklarativ begrenzt, BEVOR der Wert die Datenbank erreicht - ein
    # unbeschraenkter Pydantic-`int` wird jenseits von 2^63 zu `500` statt einer leeren Liste.
    photo_id: int | None = Query(None, ge=1, le=MAX_QUERY_POSITION),
    limit: int = Query(60, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    # SICHERHEIT (S5): ausgeschriebene Auth-Dependency. Dieser Router traegt bewusst KEINE
    # router-weite `dependencies`-Liste (siehe Kopfkommentar der Datei), und
    # `_protected_router_operations()` in `test_auth_guard.py` fuehrt ihn nicht - fuer ihn gibt es
    # KEIN Vollstaendigkeitsnetz. Ein Endpunkt, der diesen Parameter vergisst, waere STILL
    # OEFFENTLICH: kein Fehler, keine 401, nur Daten. Der eigene, pfadbenannte 401-Fall steht in
    # `tests/test_api_ausschuss.py`.
    current_user: User = Depends(get_current_user),
) -> AusschussOut:
    """Der Ausschuss-BESTAND dieses Projekts: offene Vorschlaege und getroffene Entscheidungen,
    mit Grund, gespeicherter Entscheidung und Gruppenanker.

    Der Bestand ist die VEREINIGUNG beider Ursachen - "offener Vorschlag" UND
    "Entscheidungszeile", also offen, angenommen und aufgehoben zusammen (AK1, AK3). Er ist
    ausdruecklich NICHT `NOT ueberlebt`: Eine mit `Ausschuss` entschiedene Aufnahme ist weder
    Ueberlebende noch offener Vorschlag.

    SICHERHEIT (S1/S6): Projektbindung und Bestandsbedingung stehen als UND-Glieder in DERSELBEN
    Anweisung, nie als nachgelagerter Filter ueber einer bereits gebildeten Menge.
    `duplicates.py::has_open_suggestion` traegt selbst keine Projektbedingung - ohne
    `Photo.project_id == project_id` daneben lieferte der Endpunkt jeden offenen Vorschlag der
    ganzen Instanz aus. `PhotoScore.duplicate_of` zeigt auf `photos.id` ohne Projektbedingung; der
    Gruppenanker stammt deshalb aus der bereits projektbegrenzten Kantenliste. Eine unbekannte oder
    fremde `photo_id` liefert eine leere Liste, ununterscheidbar von einer unbekannten.

    KEIN `404`/`409` fuer "nichts gefunden": Der leere Ausschuss ist ein regulaerer Zustand (AK14) -
    auch ohne erfolgreichen `ScoringRun` und bei einem Projekt ganz ohne Fotos. `404` gibt es allein
    fuer ein unbekanntes Projekt, ohne den uebergebenen Wert zu spiegeln; `422` fuer eine Id
    ausserhalb der Grenzen.

    Reihenfolge und Paginierung wie die Fotoliste: `Photo.taken_at, Photo.id`, `total` ueber den
    ganzen Bestand. `open_count` ist davon unabhaengig und nennt die Zahl, die der
    Bestaetigungsbutton traegt (AK9)."""
    project = await _get_project_or_404(project_id, session)

    # Eine Anweisung, zwei UND-Glieder: die Projektbindung und der Bestand. `has_ausschuss_entry`
    # zieht dieselbe Praesenzgrenze wie das Ueberlebenden-Praedikat und steht NICHT ausgeschrieben
    # hier (Auflage S9 - eine zweite Fassung daneben liefe ohne Fehler und ohne Meldung weg).
    bestand = (
        select(Photo.id)
        .join(PhotoScore, PhotoScore.photo_id == Photo.id)
        .where(Photo.project_id == project_id, has_ausschuss_entry())
    )
    total = (
        await session.execute(select(func.count()).select_from(bestand.subquery()))
    ).scalar_one()

    # SICHERHEIT (S1): dieselbe ausgeschriebene Projektbindung wie der Bestand - eine Zaehlung ohne
    # sie gaebe dem Button eine Zahl, die auf dieser Seite niemand einloesen kann.
    open_count = (
        await session.execute(
            select(func.count())
            .select_from(Photo)
            .join(PhotoScore, PhotoScore.photo_id == Photo.id)
            .where(Photo.project_id == project_id, has_open_suggestion())
        )
    ).scalar_one()

    if photo_id is not None:
        # Der Detail-Zweig: GENAU der passende Eintrag oder gar keiner. `limit`/`offset` sind hier
        # bewusst ohne Wirkung - die Antwort ist der eine Eintrag, nicht eine Seite.
        ids = [
            row for row in (await session.execute(bestand.where(Photo.id == photo_id))).scalars()
        ]
    else:
        ids = list(
            (
                await session.execute(
                    bestand.order_by(Photo.taken_at, Photo.id).offset(offset).limit(limit)
                )
            ).scalars()
        )

    items = await _ausschuss_entries_out(session, project, ids, current_user.id)
    return AusschussOut(items=items, total=total, open_count=open_count)


def _strength_values(effective: Mapping[str, EffectiveStrength] | None) -> dict[str, float]:
    """Die wirksamen Staerken als nackte Zahlen fuer `selection.py`.

    Die Auswahlseite kennt weder `EffectiveStrength` noch die Herkunft eines Werts: ob eine
    Korrektur im Spiel war, aendert die Staerke bereits IN `effective_strength_expression()` und
    ist danach keine zweite Eingabe mehr."""
    return {} if effective is None else {key: entry.strength for key, entry in effective.items()}


@router.get("/projects/{project_id}/draft-alternatives", response_model=PhotoListOut)
async def draft_alternatives(
    project_id: int,
    # SICHERHEIT (S4): zwei fremdgesteuerte Objekt-Ids, deklarativ begrenzt VOR jeder Verwendung.
    # `ge=1` schliesst `0` und negative Werte aus, `le` verhindert, dass ein Wert jenseits von
    # 2^63 unter SQLite einen `OverflowError` und damit eine 500 statt einer leeren Liste erzeugt.
    # FastAPI spiegelt bei `422` den Rohwert im `input`-Feld zurueck - er wird ausschliesslich als
    # React-Textknoten gerendert, nie geloggt.
    event_id: int = Query(..., ge=1, le=MAX_QUERY_POSITION),
    photo_id: int = Query(..., ge=1, le=MAX_QUERY_POSITION),
    # `limit <= 200` deckelt zugleich die schwere Hydratation ueber `_photos_by_id` mit ihren
    # `selectinload`s - sie laeuft ausschliesslich ueber die angeforderte Seite, nie ueber die
    # ganze Restmenge.
    limit: int = Query(60, ge=1, le=200),
    offset: int = Query(0, ge=0, le=MAX_QUERY_POSITION),
    session: AsyncSession = Depends(get_session),
    # SICHERHEIT (S1): ausgeschriebene Auth-Dependency. Dieser Router traegt bewusst KEINE
    # router-weite `dependencies`-Liste (siehe Kopfkommentar der Datei), und
    # `_protected_router_operations()` in `test_auth_guard.py` fuehrt ihn nicht - fuer ihn gibt es
    # KEIN Vollstaendigkeitsnetz. Ein Endpunkt, der diesen Parameter vergisst, waere STILL
    # OEFFENTLICH: kein Fehler, keine 401, nur Daten. `current_user.id` geht unveraendert an
    # `_to_photo_out` (nie ein Platzhalter wie `0` - der liesse `PhotoOut.suggestion` auch fuer
    # laengst bewertete Fotos wieder aufblitzen).
    current_user: User = Depends(get_current_user),
) -> PhotoListOut:
    """Die Alternativen zu EINEM Bild des Entwurfs (ADR 0098 Punkt 5).

    Inhalt: die Fotos DIESES Events im letzten erfolgreichen Lauf ABZUEGLICH des Entwurfs des
    anfragenden Nutzers (`Vorschlag ∪ eigene Aufnahmen`). Ein von ihm GESTRICHENES Foto ist damit
    enthalten - genau daraus folgt, dass ein Austausch umkehrbar ist. Ein im Ausschuss-Schritt
    aussortiertes Foto hat keine Rangzeile und erscheint hier nicht.

    Reihenfolge und Seitenweise: `selection.py::order_alternatives` ordnet die volle Restmenge,
    danach schneidet `limit`/`offset` die Seite heraus. `total` ist die RESTMENGE und damit
    unabhaengig von beiden - ein aus `len(items)` gebildetes `total` waere auf der ersten Seite
    nicht davon zu unterscheiden. Die Ordnung entsteht in Python und nicht im `ORDER BY`, weil sie
    an den Motiven des BEZUGSBILDES haengt; die Menge ist die eines Events.

    SICHERHEIT - Projektbindung (S2): `PhotoRanking` traegt KEINE `project_id`, und `event_id` ist
    ein GLOBALER Surrogatschluessel - eine Id aus Projekt B identifiziert unter `/projects/A/…`
    eindeutig FREMDE Rangzeilen. Ohne das Lauf-Praedikat liefe der Endpunkt nicht in eine
    erkennbar falsche Kollisionsmenge, sondern lieferte KOHAERENTE Fotos eines fremden Projekts:
    die Ausfallrichtung wird unauffaelliger, nicht harmloser. Die einzige Bindung an das Projekt
    des Pfadparameters ist `criterion_scoring_run_id` aus
    `_latest_successful_criterion_scoring_run_id(session, project_id)`; sie steht AUSGESCHRIEBEN
    in der Aufloesung des Bezugsfotos, in der Kandidatenabfrage und in `_partition_sizes`. `total`
    entsteht aus der Kandidatenabfrage selbst und damit aus derselben Bindung - eine eigene
    Zaehlabfrage ohne das Praedikat lieferte eine plausible Zahl zu einer leeren Liste, und nichts
    wuerde rot. Die Motivabfrage (`load_effective_strengths`) bekommt ausschliesslich Ids aus
    diesen beiden Abfragen; sie fuegt der Menge keine Zeile hinzu. `_photos_by_id` filtert nur
    nach Id und ist ausdruecklich KEINE zweite Verteidigungslinie.

    SICHERHEIT - das Bezugsbild (S3): `photo_id` wird AUSSCHLIESSLICH ueber eine Rangzeile
    desselben Laufs UND desselben Events aufgeloest, nie ueber `session.get(Photo, …)`. Scheitert
    das, endet die Anfrage vor jeder weiteren Abfrage mit `200`, `items: []` und `total: 0` - auf
    demselben Antwortpfad wie eine leere Trefferliste, ohne Fehlertext und ohne Rueckspiegelung
    der uebergebenen Werte. `photo_id` steuert allein die SORTIERUNG: die Motive des Bezugsbildes
    bestimmen, welche Fotos vorn stehen. Ohne das Praedikat ordnete ein fremdes Foto die eigene
    Antwort, und aus der beobachteten Reihenfolge liesse sich das Motivprofil eines Bildes
    ablesen, das der Anfragende nie sehen darf - ein Leck ueber die Sortierung, das keine
    Antwortzeile benennt. Ein abweichender Statuscode waere daneben ein Existenz-Orakel ueber
    fremde Ids."""
    project = await _get_project_or_404(project_id, session)

    latest_run_id = await _latest_successful_criterion_scoring_run_id(session, project_id)
    if latest_run_id is None:
        return PhotoListOut(items=[], total=0)

    # (1) Das Bezugsbild - beide Praedikate ausgeschrieben, siehe Docstring (S3).
    reference_row = (
        await session.execute(
            select(PhotoRanking.photo_id, PhotoRanking.rank_score).where(
                PhotoRanking.criterion_scoring_run_id == latest_run_id,
                PhotoRanking.event_id == event_id,
                PhotoRanking.photo_id == photo_id,
            )
        )
    ).first()
    if reference_row is None:
        return PhotoListOut(items=[], total=0)

    # (2) Die Kandidaten: die Rangzeilen dieses Events ABZUEGLICH des eigenen Entwurfs.
    #
    # Der Entwurf ist `(Vorschlag ∪ Aufgenommen) \ Gestrichen` (ADR 0098 Punkt 1); hier steht
    # dessen Verneinung, ausgeschrieben als zwei Bedingungen:
    #
    #   (a) nicht selbst aufgenommen, und
    #   (b) nicht vorgeschlagen ODER selbst gestrichen.
    #
    # Der zweite Halbsatz von (b) ist die Umkehrbarkeit des Austauschs: ein GESTRICHENES Foto des
    # Vorschlags gehoert nicht mehr zum Entwurf und steht deshalb wieder unter den Alternativen -
    # ohne ihn liesse sich ein Austausch nicht zuruecknehmen. Er ist zugleich der Unterschied zum
    # Entwurfs-LESEPFAD, der gestrichene Fotos bewusst stehen laesst: dort sind sie ein
    # Anzeigezustand, hier gehoeren sie zur Restmenge (Zusicherung 2).
    #
    # `or_(… is_(None), … != …)` und nicht `!=` allein: ohne eigene Bewertungszeile ist `status`
    # `NULL`, und ein blosser Ungleichheitsvergleich ergaebe in SQL `NULL` - jedes unbewertete
    # Foto fiele still aus der Antwort.
    own_rating = aliased(Rating)
    candidate_rows = (
        await session.execute(
            select(PhotoRanking.photo_id, PhotoRanking.rank_score)
            .outerjoin(
                own_rating,
                and_(
                    own_rating.photo_id == PhotoRanking.photo_id,
                    own_rating.user_id == current_user.id,
                ),
            )
            .where(
                # SICHERHEIT: das Pflichtpraedikat, siehe Docstring. Nie die Event-Id allein.
                PhotoRanking.criterion_scoring_run_id == latest_run_id,
                PhotoRanking.event_id == event_id,
                or_(
                    own_rating.status.is_(None),
                    own_rating.status != RatingStatus.ALBUM_WORTHY,
                ),
                or_(
                    PhotoRanking.selection_position.is_(None),
                    own_rating.status == RatingStatus.REJECTED,
                ),
            )
        )
    ).all()

    # (3) Die Motive beider Seiten in EINER Abfrage - nie eine je Kandidat.
    strengths_by_id = await load_effective_strengths(
        session, [photo_id, *(row.photo_id for row in candidate_rows)]
    )
    reference = AlternativeCandidate(
        photo_id=photo_id,
        quality=reference_row.rank_score,
        motif_strengths=_strength_values(strengths_by_id.get(photo_id)),
    )
    ordered_ids = order_alternatives(
        reference,
        [
            AlternativeCandidate(
                photo_id=row.photo_id,
                quality=row.rank_score,
                motif_strengths=_strength_values(strengths_by_id.get(row.photo_id)),
            )
            for row in candidate_rows
        ],
    )

    # (4) `total` ist die volle Restmenge, die Hydratation laeuft ueber die Seite.
    total = len(ordered_ids)
    ids = ordered_ids[offset : offset + limit]
    photos_by_id = await _photos_by_id(session, ids)
    rankings_by_id = await _ranking_by_photo_id(session, latest_run_id, ids)
    partition_sizes = await _partition_sizes(session, latest_run_id)
    place_by_id = await _event_and_location_by_photo_id(
        session, project_id, latest_run_id, photos_by_id, _event_ids_from_rankings(rankings_by_id)
    )
    decisions = await _final_selection_decisions(session, ids)
    user_count = await _user_count(session)
    items = [
        _to_photo_out(
            photos_by_id[alternative_id],
            current_user.id,
            project,
            rankings_by_id.get(alternative_id),
            partition_sizes,
            # KEINE `curation_position`: die Alternativen sind keine Auswahl, zu der ein Bild
            # einen Platz haette. Eine Zahl hier waere eine Rangaussage ueber eine Reihenfolge,
            # die allein am gerade betrachteten Bezugsbild haengt.
            None,
            place_by_id.get(alternative_id, NO_PLACE),
            strengths_by_id.get(alternative_id),
            decisions=decisions,
            user_count=user_count,
        )
        # Eigener Name, nicht `photo_id`: der Query-Parameter gleichen Namens ist das BEZUGSBILD
        # und wird oben gebraucht; eine Ueberdeckung hier waere an keiner Stelle sichtbar.
        for alternative_id in ids
    ]
    return PhotoListOut(items=items, total=total)


# --- Der Austausch: ein Aufruf, eine Transaktion, ein Ereignis ---------------------------------


class DraftExchangeIn(BaseModel):
    """SICHERHEIT (S4): der Body traegt GENAU ZWEI Felder, beide mit deklarativen Grenzen.

    Kein `user_id`, kein `event_id`, kein `weight`, kein `kind`, kein `criterion_scoring_run_id`,
    kein `motif_strength` - Massenzuweisung ist strukturell ausgeschlossen statt im Handler
    herausgefiltert; `model_config` weist ein zusaetzliches Feld ausdruecklich ab statt es still
    zu verwerfen.

    `weight` WIEGT AM SCHWERSTEN: Es ist der einzige Wert, mit dem ein Aufrufer die eigene
    Korrektur in der global wirkenden Gewichtsableitung ueberproportional zaehlen liesse.

    Die Obergrenze ist nicht Kosmetik: Ein unbeschraenkter Pydantic-`int` erzeugt unter SQLite
    jenseits von 2^63 einen `OverflowError` und damit `500` statt `422`."""

    model_config = ConfigDict(extra="forbid")

    photo_id: int = Field(ge=1, le=MAX_QUERY_POSITION)
    replaced_photo_id: int = Field(ge=1, le=MAX_QUERY_POSITION)


class DraftExchangeOut(BaseModel):
    """Der geschriebene Zustand BEIDER Bewertungszeilen (L2).

    Beide, damit die Oberflaeche wie bisher in ihre bereits geladene Liste fortschreibt statt neu
    zu laden - ein Neuladen risse die gerade getauschte Kachel aus der Entwurfsliste."""

    taken: RatingWriteOut
    struck: RatingWriteOut


@dataclass(frozen=True)
class _ExchangeSide:
    """Eine Seite des Austauschs, AUFGELOEST UEBER IHRE RANGZEILE (S2)."""

    photo_id: int
    event_id: int
    level: int | None
    quality: float | None


# S14: EIN Text fuer die unbekannte und fuer die projektfremde Id. Verschiedene Antworten machten
# den Endpunkt zum Existenz-Orakel ueber fremde Foto-Ids.
_EXCHANGE_REFUSAL = (
    "Beide Bilder muessen zum selben Ereignis des juengsten Vorschlagslaufs dieses Projekts "
    "gehoeren."
)


async def _exchange_sides(
    session: AsyncSession, criterion_scoring_run_id: int, photo_ids: tuple[int, int]
) -> dict[int, _ExchangeSide]:
    """Loest beide Foto-Ids UEBER EINE RANGZEILE des uebergebenen Laufs auf.

    SICHERHEIT (S2), und das ist die tragende Entscheidung dieses Endpunkts: Die Aufloesung laeuft
    ausschliesslich ueber `PhotoRanking` mit dem Praedikat "juengster erfolgreicher Lauf DIESES
    Projekts", NIE ueber `session.get(Photo, …)` mit nachgelagerter Projektpruefung.

    Grund: `PhotoRanking` traegt keine `project_id`, `event_id` ist ein globaler
    Surrogatschluessel, und ohne das Laufpraedikat identifiziert eine Id aus Projekt B unter
    `/projects/A/…` eindeutig FREMDE Zeilen - der Endpunkt liefe dann nicht in eine erkennbar
    falsche Menge, sondern tauschte kohaerent zwei Bilder eines fremden Projekts. Die untersagte
    Alternative ist die nachgelagerte Pruefung auf `Photo.project_id`; sie ist keine zweite
    Verteidigungslinie, sondern der Ersatz der richtigen Bedingung durch eine schwaechere.

    Die Modellstufe kommt ueber einen OUTER JOIN mit: Ein Foto ohne Modellbewertung haelt den
    Austausch nicht auf (L4), sein Paar ist in der Diagnose spaeter nur `unbestimmt`."""
    rows = (
        await session.execute(
            select(
                PhotoRanking.photo_id,
                PhotoRanking.event_id,
                PhotoAlbumSuitability.level,
                PhotoRanking.rank_score,
            )
            .outerjoin(
                PhotoAlbumSuitability,
                PhotoAlbumSuitability.photo_id == PhotoRanking.photo_id,
            )
            .where(
                PhotoRanking.criterion_scoring_run_id == criterion_scoring_run_id,
                PhotoRanking.photo_id.in_(photo_ids),
            )
        )
    ).all()
    return {
        photo_id: _ExchangeSide(
            photo_id=photo_id, event_id=event_id, level=level, quality=rank_score
        )
        for photo_id, event_id, level, rank_score in rows
    }


@router.post("/projects/{project_id}/draft/exchange", response_model=DraftExchangeOut)
async def exchange_draft_photo(
    project_id: int,
    payload: DraftExchangeIn,
    session: AsyncSession = Depends(get_session),
    # SICHERHEIT (S1): ausgeschriebene Auth-Dependency. Fuer diesen Router gibt es KEIN
    # Vollstaendigkeitsnetz - ein hier vergessener Parameter waere still oeffentlich: kein Fehler,
    # keine 401, sondern ein unauthentifizierter Schreibzugriff, der ZWEI Bewertungszeilen aendert.
    current_user: User = Depends(get_current_user),
) -> DraftExchangeOut:
    """Tauscht im eigenen Album-Entwurf ein Bild gegen ein anderes desselben Ereignisses: Das
    gewaehlte wird aufgenommen, das ersetzte gestrichen.

    EIN AUFRUF STATT ZWEIER, und das ist der Gegenstand dieses Endpunkts: "B statt A" ist die
    Aussage, die beiden Bilder fuer sich tragen sie nicht. Zwei getrennte Aufrufe liessen sich
    nachtraeglich nur ueber eine Heuristik zu einem Paar zusammenfuegen, und der zweite kann
    fehlschlagen - dann bliebe ein halb ausgefuehrter Austausch stehen.

    BEIDE Bewertungszeilen und das eine Ereignis gehen in EINER Transaktion oder gar nicht
    (Auflage S5). Das Favoriten-Kennzeichen bleibt auf beiden Seiten unberuehrt, weil der Austausch
    durch dieselbe Schreibstelle laeuft wie `PUT /photos/{id}/rating`.

    Er erzeugt AUSDRUECKLICH KEIN zusaetzliches Streich- und Aufnahme-Ereignis: Sonst zaehlte jeder
    Austausch dreifach. Die Umkehr eines Austauschs ist ein weiterer Austausch mit eigenem
    Ereignis; sie loescht nichts.

    `404` ohne Projekt. `422`, wenn beide Verweise dasselbe Foto benennen, wenn eines der Bilder
    nicht ueber eine Rangzeile des juengsten erfolgreichen Laufs dieses Projekts erreichbar ist,
    oder wenn die beiden nicht zum selben Ereignis gehoeren - in allen drei Faellen mit
    demselben Text (Auflage S14). `409` bei einem gleichzeitigen Schreibversuch auf eine der
    beiden Zeilen.

    Die Antwort traegt BEIDE geschriebenen Zeilenzustaende, damit die Oberflaeche fortschreibt
    statt neu zu laden."""
    await _get_project_or_404(project_id, session)

    if payload.photo_id == payload.replaced_photo_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=_EXCHANGE_REFUSAL
        )

    run_id = await _latest_successful_criterion_scoring_run_id(session, project_id)
    if run_id is None:
        # Ohne erfolgreichen Lauf gibt es keine Rangzeile, ueber die die Projektbindung liefe -
        # und damit keinen Entwurf, in dem etwas auszutauschen waere. Derselbe Text (S14).
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=_EXCHANGE_REFUSAL
        )

    sides = await _exchange_sides(session, run_id, (payload.photo_id, payload.replaced_photo_id))
    taken = sides.get(payload.photo_id)
    struck = sides.get(payload.replaced_photo_id)
    # EINE Bedingung fuer alle drei Ablehnungsgruende: unbekannt, projektfremd, verschiedene
    # Ereignisse. `event_id` stammt damit aus der Rangzeile und nie aus dem Body (S3).
    if taken is None or struck is None or taken.event_id != struck.event_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=_EXCHANGE_REFUSAL
        )

    # `record=False` auf BEIDEN Aufrufen: Ohne diese Unterdrueckung entstuenden neben dem
    # Austausch-Ereignis noch ein Streich- und ein Aufnahme-Ereignis, und jeder Austausch zaehlte
    # dreifach. Keiner der beiden Aufrufe committet - die Transaktionsgrenze liegt unten.
    written_taken = await write_own_rating(
        session,
        project_id=project_id,
        photo_id=taken.photo_id,
        user_id=current_user.id,
        next_state=lambda _status, favorite: (RatingStatus.ALBUM_WORTHY, favorite),
        record=False,
    )
    written_struck = await write_own_rating(
        session,
        project_id=project_id,
        photo_id=struck.photo_id,
        user_id=current_user.id,
        next_state=lambda _status, favorite: (RatingStatus.REJECTED, favorite),
        record=False,
    )
    await record_exchange(
        session,
        project_id=project_id,
        user_id=current_user.id,
        photo_id=taken.photo_id,
        replaced_photo_id=struck.photo_id,
        criterion_scoring_run_id=run_id,
        event_id=taken.event_id,
        level=taken.level,
        replaced_level=struck.level,
        quality=taken.quality,
        replaced_quality=struck.quality,
    )
    # DER EINE COMMIT ueber beide Zeilen und das Ereignis (S5).
    await session.commit()
    return DraftExchangeOut(taken=written_taken, struck=written_struck)


@router.get("/photos/{photo_id}/image")
async def get_photo_image(
    photo_id: int,
    # Literal["thumbnail", "display"] statt ein freier str-Parameter: FastAPI/Pydantic validiert
    # gegen genau diese Allowlist und liefert 422 fuer alles andere, BEVOR der Wert unten in eine
    # Datei-Pfadoperation einfließt - Muss-Kriterium gegen Path-Traversal über den
    # variant-Parameter.
    variant: Literal["thumbnail", "display"],
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    photo = await session.get(Photo, photo_id)
    if photo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foto nicht gefunden.")

    path = variant_path(Path(settings.photo_cache_dir), photo.id, photo.etag, variant)
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Bild wird noch verarbeitet."
        )

    # SICHERHEIT: Content-Type explizit gesetzt (immer JPEG, siehe thumbnails.py), nicht vom
    # Dateisystem erraten; X-Content-Type-Options verhindert MIME-Sniffing-XSS bei falsch
    # benannten Dateien.
    return FileResponse(
        path, media_type="image/jpeg", headers={"X-Content-Type-Options": "nosniff"}
    )


async def _get_photo_or_404(photo_id: int, session: AsyncSession) -> Photo:
    photo = await session.get(Photo, photo_id)
    if photo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foto nicht gefunden.")
    return photo


class MotifCorrectionIn(BaseModel):
    """SICHERHEIT (S5): der Body traegt AUSSCHLIESSLICH `applies`.

    Kein `user_id`, `photo_id`, `motif_key`, `strength` oder `updated_at` im Eingabeschema -
    Massenzuweisung ist strukturell ausgeschlossen statt im Handler herausgefiltert. Ein Feld,
    ueber das ein Client eine Staerke setzen koennte, hebt die Unterscheidung zwischen
    Modellaussage und Korrektur auf, und ein `user_id` im Body liesse Nutzer A unter dem Namen von
    B schreiben. Ein spaeter ergaenztes Feld bricht in
    tests/test_api_motif_corrections.py::TestTheRequestBody."""

    applies: bool


class MotifCorrectionOut(BaseModel):
    photo_id: int
    motif_key: str
    applies: bool


async def _stored_motif_strength(
    session: AsyncSession, photo_id: int, motif_key: str
) -> float | None:
    """Die GESPEICHERTE Modellstaerke dieses Paares, `None` ohne Staerkezeile.

    AUSDRUECKLICH NICHT `motif_strengths.py::effective_strength_expression` (ADR 0100 Punkt 2):
    Die wirksame Staerke traegt bereits eine fruehere Korrektur desselben Paares. Eingefroren
    zeigte die ZWEITE Korrektur eines Motivs nie einen Modellfehler an - sie beantwortete die
    Frage nach der Modellaussage mit der Korrektur.

    `None` ist ein gewoehnlicher, haeufiger Fall und kein Fehler: Die Korrektur eines nie
    erkannten Motivs ist ausdruecklich erlaubt und fuer die Diagnose der interessanteste Fall."""
    return (
        await session.execute(
            select(PhotoMotifStrength.strength).where(
                PhotoMotifStrength.photo_id == photo_id,
                PhotoMotifStrength.motif_key == motif_key,
            )
        )
    ).scalar_one_or_none()


def _validated_motif_key(motif_key: str) -> str:
    """SICHERHEIT (S4): reine Mitgliedschaftspruefung im geschlossenen Achter-Schluesselraum, VOR
    jeder Schreib- und Loeschaktion, fuer `PUT` UND `DELETE`.

    Kein `startswith`, kein Regex, keine Normalisierung des Eingabewerts - der Client schickt den
    Schluessel exakt so zurueck, wie `GET /motifs` ihn geliefert hat. `EXCLUSION_KEY` ist kein
    gueltiger Wert und kann ueber diese Pruefung nicht hereinkommen: `is_motif_key` sieht
    ausschliesslich in `MOTIF_REGISTRY`, und dort steht er nicht.

    Angriffsmodell: ein erratener oder aus der Laufhistorie bekannter Schluessel. Untersagte
    Alternative ist eine auf die vorhandenen Staerkezeilen DIESES Fotos skopierte Existenzpruefung
    - sie haengt an Daten statt am Vokabular und wiese das Korrigieren eines nie erkannten Motivs
    zu Unrecht ab."""
    if not is_motif_key(motif_key):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="motif_key gehoert nicht zum festen Motivset.",
        )
    return motif_key


@router.put("/photos/{photo_id}/motif-corrections/{motif_key}", response_model=MotifCorrectionOut)
async def set_motif_correction(
    photo_id: int,
    motif_key: str,
    payload: MotifCorrectionIn,
    session: AsyncSession = Depends(get_session),
    # SICHERHEIT (S2): ausgeschriebene Auth-Dependency. Dieser Router traegt bewusst KEINE
    # Router-weite `dependencies`-Liste und hat deshalb auch keinen Vollstaendigkeitstest - ein
    # hier vergessener Parameter waere STILL OEFFENTLICH: kein Fehler, keine 401, nur Daten.
    current_user: User = Depends(get_current_user),
) -> MotifCorrectionOut:
    """Markiert ein Motiv fuer dieses Foto als zutreffend oder als nicht zutreffend: `404` bei
    fehlendem Foto, `422` bei einem `motif_key` ausserhalb des festen Achter-Sets (auch fuer
    `dokument_screenshot` und fuer einen entfallenen Kategorieschluessel), `409` bei einem
    gleichzeitigen Schreibversuch auf dasselbe Paar.

    Die Korrektur traegt nie eine Zahl - der Nutzer schaetzt nichts ein, er waehlt ein Motiv ab
    oder zu. Die WIRKSAME Staerke entsteht erst im Lesepfad und wird nicht in die Staerkezeile
    materialisiert; sie ueberlebt damit jeden weiteren Klassifizierungslauf ohne Sonderfallcode.

    AUSDRUECKLICH ERLAUBT ist ein Motiv, das fuer dieses Foto nie erkannt wurde, und ein Foto ohne
    Kopfzeile: die Tabelle ist lauf-unabhaengig, und die Korrektur greift dann beim ersten Lauf.

    Eine Korrektur je Foto und Motiv, letzter Zugriff gewinnt: korrigiert der zweite Nutzer
    dasselbe Paar, UEBERSCHREIBT er die Aussage des ersten. `user_id` haelt fest, wer zuletzt
    geschrieben hat - es gibt keine Historie und keinen Hinweis an die erste Person. Eine
    wirkungslose Korrektur (`applies=false` auf einem Motiv, dessen Staerke schon 0 ist) wird
    trotzdem gespeichert; sie ist eine Nutzeraussage, keine Zwischenspeicherung."""
    # Die `project_id` VOR dem `flush` festhalten: Dessen `rollback`-Zweig laesst jedes geladene
    # Objekt expired zurueck, und ein danach angefasstes Attribut braeche unter `asyncio` mit
    # `MissingGreenlet`.
    project_id = (await _get_photo_or_404(photo_id, session)).project_id
    _validated_motif_key(motif_key)

    # SICHERHEIT (S6): die Aufsuch-Bedingung lautet `(photo_id, motif_key)` und filtert BEWUSST
    # NICHT zusaetzlich auf `user_id`. Mit dem Nutzer im Filter entstuenden zwei widersprueckliche
    # Zeilen fuer dasselbe Paar, und welche gilt, entschiede die Sortierung.
    existing = (
        await session.execute(
            select(PhotoMotifCorrection).where(
                PhotoMotifCorrection.photo_id == photo_id,
                PhotoMotifCorrection.motif_key == motif_key,
            )
        )
    ).scalar_one_or_none()

    # NUR BEI TATSAECHLICHER AENDERUNG (Spec 0432, L1): Dieselbe Korrektur erneut geschrieben ist
    # keine Korrektur - auch dann nicht, wenn die Zeile dabei den Nutzer wechselt. Der
    # Bestandszustand des FOTOS bewegt sich nicht, und die Story misst Korrekturen.
    changed = existing is None or existing.applies != payload.applies

    if existing is None:
        # SICHERHEIT (S6): `user_id` stammt AUSSCHLIESSLICH aus `current_user.id` - nie aus Body
        # oder Query. Es ist ein Auditfeld und kein Zugriffsschluessel.
        session.add(
            PhotoMotifCorrection(
                photo_id=photo_id,
                user_id=current_user.id,
                motif_key=motif_key,
                applies=payload.applies,
            )
        )
    else:
        existing.applies = payload.applies
        existing.user_id = current_user.id
        # `updated_at` traegt `onupdate=func.now()` und wird nie von Hand gesetzt.

    # SICHERHEIT (S7): der `flush` VOR dem `commit` bringt den Unique-Constraint hier zum Tragen,
    # damit ein gleichzeitiger Schreibversuch beider Nutzer als `409` herauskommt und nie als
    # `500`. Eine Sperre (`with_for_update()`) ist nicht noetig und ausdruecklich nicht
    # vorzusehen: die Korrektur schreibt eine Zeile und leitet nichts ab, sie hat keinen
    # Schreibzugriff auf die Rangfolge.
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Die Korrektur dieses Motivs wurde gerade veraendert. Bitte erneut versuchen.",
        ) from exc

    if changed:
        await record_motif_correction(
            session,
            project_id=project_id,
            photo_id=photo_id,
            user_id=current_user.id,
            kind=(
                FeedbackEventKind.MOTIF_ADDED
                if payload.applies
                else FeedbackEventKind.MOTIF_DROPPED
            ),
            motif_key=motif_key,
            motif_strength=await _stored_motif_strength(session, photo_id, motif_key),
            context=await load_frozen_context(session, project_id=project_id, photo_id=photo_id),
        )
    # Der EINE Commit: Korrekturzeile und etwaiges Ereignis gehen gemeinsam oder gar nicht.
    await session.commit()

    return MotifCorrectionOut(photo_id=photo_id, motif_key=motif_key, applies=payload.applies)


@router.delete(
    "/photos/{photo_id}/motif-corrections/{motif_key}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_motif_correction(
    photo_id: int,
    motif_key: str,
    session: AsyncSession = Depends(get_session),
    # SICHERHEIT (S2): siehe set_motif_correction - der 401-Nachweis ist fuer BEIDE Endpunkte
    # Pflicht, weil dieser Router keinen Vollstaendigkeitstest hat.
    current_user: User = Depends(get_current_user),
) -> None:
    """Nimmt die Korrektur eines Motivs zurueck - die wirksame Staerke ist danach wieder die der
    Grundlage. `404` bei fehlendem Foto, `422` bei einem `motif_key` ausserhalb des festen Sets.

    IDEMPOTENT (`204` auch ohne bestehende Zeile) und ohne Body. Auch die jeweils andere Person
    darf eine Korrektur zuruecknehmen: die Aussage gehoert zum Foto, nicht zu einem Geschmack.

    Ein Aufruf auf ein NIE korrigiertes Motiv erzeugt kein Ereignis der Nacharbeit (Spec 0432,
    L1): Er nimmt nichts zurueck. Die Ruecknahme einer bestehenden Korrektur dagegen erzeugt ein
    ZUSAETZLICHES Ereignis - das urspruengliche bleibt unveraendert stehen (L6)."""
    project_id = (await _get_photo_or_404(photo_id, session)).project_id
    _validated_motif_key(motif_key)

    # Die Staerke VOR der Loeschung lesen - danach ist die Korrekturzeile fort, und die
    # eingefrorene Modellaussage steht in einer anderen Tabelle, die den Zeitpunkt nicht kennt.
    motif_strength = await _stored_motif_strength(session, photo_id, motif_key)
    deleted = await session.execute(
        delete(PhotoMotifCorrection).where(
            PhotoMotifCorrection.photo_id == photo_id,
            PhotoMotifCorrection.motif_key == motif_key,
        )
    )
    if cast("CursorResult[Any]", deleted).rowcount:
        await record_motif_correction(
            session,
            project_id=project_id,
            photo_id=photo_id,
            user_id=current_user.id,
            kind=FeedbackEventKind.MOTIF_CORRECTION_WITHDRAWN,
            motif_key=motif_key,
            motif_strength=motif_strength,
            context=await load_frozen_context(session, project_id=project_id, photo_id=photo_id),
        )
    await session.commit()
