"""Antwortmodelle und die reine Umwandlung von ORM-Zustand in Antwortobjekte.

Jede Abbildung, die ohne Datenbankzugriff auskommt, steht hier: die Schemas der Fotoliste, der
Entwuerfe und der Auswahl sowie die Funktionen, die aus geladenen Zeilen die Antwortfelder bauen.
Die Themengruppen und die geteilten Lesehilfen greifen darauf zu; dieses Modul importiert
umgekehrt keine Gruppe und keine Lesehilfe.
"""

from __future__ import annotations

import enum
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from photosort.api.persons import PhotoPersonOut
from photosort.cameras import CameraIdentity, camera_label
from photosort.criteria import CRITERIA_REGISTRY, is_landmark_candidate
from photosort.duplicates import has_open_suggestion_for, survives_ausschuss_for
from photosort.events import EffectiveLocation
from photosort.final_selection import selection_state_of
from photosort.models import (
    CategoryMethod,
    CloudVisionPhase,
    CriterionSource,
    Event,
    MotifAssessmentSource,
    Photo,
    PhotoCloudVisionError,
    PhotoRanking,
    PhotoScore,
    Project,
    RatingStatus,
)
from photosort.motif_strengths import EffectiveStrength
from photosort.motifs import MOTIF_REGISTRY
from photosort.selection import motif_is_present


def suggestion_reason(score: PhotoScore) -> Literal["duplicate", "low_quality"]:
    return "duplicate" if score.duplicate_of is not None else "low_quality"


class RatingFilter(enum.StrEnum):
    """Die Eintraege des Rasterfilters. `favorite` bleibt als EINTRAG, ist aber kein
    Bewertungsstatus mehr: er filtert auf die eigene Spalte `Rating.favorite`.

    `unrated` heisst "KEINE ALBUMENTSCHEIDUNG" (`status IS NULL`), nicht "keine
    Zeile" - ein nur als Favorit markiertes Bild bleibt damit in diesem Filter."""

    UNRATED = "unrated"
    SUGGESTED = "suggested"
    FAVORITE = "favorite"
    ALBUM_WORTHY = "album_worthy"
    REJECTED = "rejected"


class RatingOut(BaseModel):
    """Die Bewertungszeile EINES Nutzers. `status` ist die Albumentscheidung und `null`, wenn
    keine getroffen wurde - auch dann, wenn die Zeile wegen `favorite` existiert.

    SICHERHEIT: Die Oberflaeche liest den EIGENEN Zustand - Albumentscheidung UND
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
    # im Info-Popover - lauf-global berechnet (siehe partition_sizes), nicht nutzerspezifisch
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
    Modellantwort zeichensaniert worden (cloud_vision.py::sanitize_label_text) und
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

    `source` ist ein SICHERHEITSMERKMAL, kein Anzeigedetail:
    `scoring.GPS_CLUSTER_SPLIT_DISTANCE_METERS` begrenzt den SCHRITT zwischen
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

    `kind` benennt die STUFE, nicht den einzigen Text des Events: `landmark_name` steht
    NEBEN `EventOut.place_name`, statt ihn zu verdraengen. Verdraengt bleibt allein
    die KOORDINATENSTUFE - `kind` bleibt `"landmark"` auch dann, wenn daneben ein Ortsname steht,
    und traegt weiterhin keine Koordinate.

    `kind="multiple"` traegt STRUKTURELL keine Koordinate: es gibt den einen Ort, den sie
    repraesentieren muesste, gerade nicht.

    `landmark_name` ist freier, extern erzeugter LLM-Text (`Event.landmark_name`, ueber
    `sanitize_landmark_name` entstanden) - dieselbe Auflage wie bei `FineLabelOut.raw_label`:
    ausschliesslich als regulaerer React-Textknoten rendern, nie `dangerouslySetInnerHTML`, nie als
    HTML-String-Prop, nie in `href`/`src`/`style`, nie als React-`key`. Ein Event traegt ihn
    nur, wenn ihn mindestens ein Zehntel seiner Fotos bezeugt
    (`events.LANDMARK_MIN_SHARE`); ein zu schwach gestuetzter Name ist von "nie erkannt" NICHT zu
    unterscheiden und hat keinen eigenen Anzeigezustand. Bricht in
    `frontend/src/pages/AlbumDraftPage.*.test.tsx`, Faelle
    `rendert einen HTML-artigen Sehenswuerdigkeit-Namen als Text, nicht als Markup` und
    `rendert beide feindlichen Teile als Text, nicht als Markup`."""

    kind: Literal["landmark", "coordinate", "multiple"]
    landmark_name: str | None = None
    lat: float | None = None
    lon: float | None = None


class EventOut(BaseModel):
    """Das Event, zu dem dieses Foto im letzten erfolgreichen Lauf gehoert.

    Der Server liefert KEINE fertige Ueberschrift, sondern ihre Teile: Nummer,
    Zeitspanne, den aufgeloesten Ort und den aufgeloesten Ortsnamen. Es haengt nichts davon ab,
    welche Fotos eine Antwort gerade enthaelt - alle Werte stehen in der `events`-Zeile.

    Auch zusammengesetzt wird hier nichts: `place_name` ist der REINE Ortsname ("Ort" bzw.
    "Ort, Viertel"), und die Form "<Name>, <Ort>" entsteht erst in
    `frontend/src/utils/timeOfDay.ts::eventPlaceName`. Eine zweite Quelle
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
    Normalfall. Bricht in `frontend/src/pages/AlbumDraftPage.*.test.tsx`, Fall
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

    `provider` ist `null` bei `source == "local"` UND bei `source == "eye"` - Eye ist kein
    Cloud-Anbieter, ein Anbieterwert behauptete einen Kontakt, der nicht stattfand; die
    Modellrevision steht in `eye_result`. `excluded_document` ist von Hand NICHT korrigierbar -
    der Rueckweg ist allein ein erneuter Klassifizierungslauf, und die Oberflaeche benennt das,
    statt einen Schalter anzubieten."""

    source: Literal["cloud", "eye", "local"]
    provider: str | None
    excluded_document: bool
    computed_at: datetime


class EyeResultOut(BaseModel):
    """Die Eye-Auswertung eines Fotos - gesetzt GENAU dann, wenn die Motiv-Kopfzeile
    `source="eye"` traegt.

    Nicht gesetzt allein deshalb, weil `photo_eye_results` existiert: Die Zeile steht auch neben
    einer gueltigen Cloud-Kopfzeile. Dieses Feld zeigt sie nur, wenn sie auch gilt; die ZAHLENDE
    Albumstufe steht unabhaengig davon in `album_suitability`, sobald der Lauf Eye als Quelle
    eingefroren hat.

    `fine_labels` sind die ROHEn Eye-Tags ab Konfidenz 0.5, beim Schreiben zeichensaniert und
    laengenbegrenzt - deshalb hier als reine Textknoten, ohne weitere Umformung. Die
    Modellrevision steht hier und NICHT in `MotifAssessmentOut.provider`: Eye ist kein
    Cloud-Anbieter. `mapping_version` ist die Fassung der Uebersetzung, mit der die Zeile entstand
    - ein serverseitiger Schluessel von `eye_mapping.MAPPINGS`, als Rohwert."""

    album_level: int
    model_revision: str
    mapping_version: str
    computed_at: datetime
    fine_labels: list[str]


class AlbumSuitabilityOut(BaseModel):
    """Die ZAEHLENDE fuenfstufige Albumstufe eines Fotos samt Herkunft und - nur bei Cloud -
    Begruendung.

    `null` am Foto heisst "noch nicht eingestuft" und ist damit von der niedrigsten Stufe
    unterscheidbar - die Oberflaeche zeigt an dieser Stelle einen Satz statt einer Stufe. Es gilt
    auch fuer ein Foto, das nur eine Stufe des ANDEREN Verfahrens traegt: es gibt keinen Rueckfall.

    SICHERHEIT: `source` ist das am Lauf eingefrorene Verfahren (`album_level_source`) bzw.
    ohne Lauf die Projekteinstellung - festgelegt allein vom Server, nie aus Query, Body,
    Motiv-Kopfzeile oder `eye_result`. Der geschlossene `Literal` bricht die Antwortvalidierung bei
    jedem anderen Wert.

    `reason` ist FREIER MODELLTEXT und nur bei `source="cloud"` gesetzt; bei `eye` ist es
    serverseitig `None` - Eye liefert keinen Text. Der Cloud-Text ist bereits am Parser
    saniert und gekappt (`album_suitability.py`, Sicherheitsauflage) und wird hier unveraendert
    durchgereicht; eine zweite Fassung derselben Regel gibt es nicht. In der Oberflaeche gehoert er
    ausschliesslich als regulaerer Textknoten gerendert - nie ueber `dangerouslySetInnerHTML`, nie
    in ein `href`, `src` oder `style`.

    Die Aussage ist erkennbar die des MODELLS, nicht die von PhotoSort: sie stammt aus einem Bild,
    das Text enthalten kann."""

    level: int
    reason: str | None
    source: Literal["cloud", "eye"]


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
    # Behaelt Namen und Form und liefert die KORRIGIERTE Zeit.
    # Der Bedeutungswechsel ist beabsichtigt; die beiden Felder darunter treten daneben,
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
    # Breite geteilt durch Hoehe des GEZEIGTEN Bildes. `null` heisst "nicht
    # bekannt" und ist ein REGULAERER Zustand, kein Fehler - die Oberflaeche plant ein solches
    # Foto mit 3:2 ein. Einheitlich auf ALLEN Lesepfaden ausgeliefert, nicht nur auf dem der
    # Rasteransicht: ein je Query-Modus divergierendes `PhotoOut` waere genau die "zweite,
    # driftende Abbildung", vor der der `ranking`-Kommentar oben warnt.
    aspect_ratio: float | None = None
    ratings: list[RatingOut]
    suggestion: SuggestionOut | None
    # Die Rangzeile des Fotos im letzten erfolgreichen Lauf, in beiden Query-Modi - `null`,
    # solange kein erfolgreicher Lauf existiert oder das Foto darin keine Zeile hat. EIN Feld und
    # keine Liste: ein Foto steht je Lauf in genau einer Zeile.
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
    # Die Eye-Auswertung, `null` ohne Eye-Kopfzeile - auch dann, wenn ein Schattensatz daneben
    # steht (siehe `EyeResultOut`). Auf ALLEN Lesepfaden befuellt, Muster `motif_assessment`.
    eye_result: EyeResultOut | None = None
    # DIE DREI FELDER DER ENDAUSWAHL, auf ALLEN Lesepfaden befuellt - Muster
    # `RankingOut.proposed`: ein je Query-Modus verschiedenes `PhotoOut` waere die zweite,
    # driftende Abbildung. Alle drei sind PROJEKTAUSSAGEN und tragen kein nutzerbezogenes Datum.
    #
    # Die persistierte gemeinsame Entscheidung, `null` = keine. AUSDRUECKLICH NICHT
    # `album_decision` benannt: so heisst bereits `ratings[].status`, die Entscheidung eines
    # NUTZERS - und die beiden zu verwechseln ist genau der Fehler, den diese Story ausschliesst.
    #
    # ALLE DREI OHNE VORGABEWERT, anders als `location`/`event`/`ranking` darueber:
    # Ein `= False` waere die stille Ausfallrichtung "nicht im Album" - plausibel, ohne Ausnahme
    # und ohne Fehlercode, und der Fehler zeigte sich erst an einem leeren Album statt an der
    # Stelle, an der er entsteht. Zusammen mit den pflichtigen `to_photo_out`-Parametern
    # scheitert ein vergessener Aufrufer damit VOR der Laufzeit.
    final_selection_decision: bool | None
    # Gehoert das Foto zur Endauswahl? `album_selection.py::selection_state(...).included`. Das
    # Frontend leitet die Zugehoerigkeit NIE selbst her; sie kommt vom Server.
    in_final_selection: bool
    # Sind sich die Nutzer uneins und ist noch nicht gemeinsam entschieden?
    # `album_selection.py::selection_state(...).contested`.
    contested: bool
    # Je WIRKSAM zugeordneter Person nur Id und Herkunft (`recognized`/`corrected`), nach Slot -
    # nie ein Name, ein Merkmal oder eine Aehnlichkeit. Ohne Vorgabewert: wie
    # `decisions` ist `persons` ein pflichtiger Schluesselwortparameter von `to_photo_out`, damit
    # ein vergessener Aufrufer vor der Laufzeit scheitert statt still eine leere Liste zu liefern.
    persons: list[PhotoPersonOut]


class PhotoListOut(BaseModel):
    items: list[PhotoOut]
    total: int


class AlbumParticipantOut(BaseModel):
    """EIN Teilnehmer der Endauswahl - genau `user_id` und `username`, nie mehr.

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
    # Sonderfall". Seine LAENGE ist zugleich der Nenner der Einigkeitsregel.
    participants: list[AlbumParticipantOut]
    # "Mindestens eine Rangzeile des letzten erfolgreichen Laufs traegt `selection_position`."
    # Trennt die beiden Leerzustaende, die die Story GETRENNT verlangt ("kein Auswahlvorschlag"
    # gegen "keine Unterschiede offen") - sie verlangen verschiedene Handlungen, einmal einen Lauf
    # starten, einmal nichts tun. Aus den Kandidatenzeilen abgeleitet, ohne eigene Abfrage.
    has_proposal: bool
    items: list[PhotoOut]


class AlbumDraftOut(BaseModel):
    """Der Album-Entwurf des anfragenden Nutzers samt Eventliste des letzten erfolgreichen Laufs.

    `events` sind ALLE Events dieses Laufs nach `position` (lueckenlos 1..m), auch die ohne Foto im
    Entwurf - daraus entstehen "Event p von E", Tage und Events im Kopf und das Hinzufuegen-Feld in
    leeren Events. `items` ist `Vorschlag ∪ eigene album_worthy ∪ (eigene rejected ∩ Rangzeile)`
    in `(events.position, taken_at, id)`; innerhalb der Antwort gilt ausnahmslos: im Album genau
    dann, wenn der eigene Status nicht `rejected` ist. Die Ansicht blendet Gestrichenes aus.

    KEIN `total` und keine Seitenweise, wie `AlbumSelectionOut`."""

    events: list[EventOut]
    items: list[PhotoOut]
    # Die Zahl AUSWAHLFAEHIGER Kandidaten des Laufs - dieselbe Menge, aus der
    # `worker/_criterion/ranking.py::apply_run_selection` waehlt (Rangzeile mit `rank_score`, kein
    # `excluded_document`). Lauf-global, ohne Nutzerbezug. Speist allein den Hinweis
    # "kleinerer Vorschlag": Er erscheint nur, wenn der Vorschlag diese Menge ausschoepft.
    eligible_candidate_count: int


def _to_suggestion_out(score: PhotoScore) -> SuggestionOut:
    return SuggestionOut(
        status=score.suggested_status,  # type: ignore[arg-type]
        reason=suggestion_reason(score),
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
    cloud_vision_errors) eager geladen ist (siehe photos_by_id) - kein Lazy-Load hier."""
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
    # SICHERHEITSAUFLAGE, auch hier: geprueft wird auf `source='cloud'`, nicht auf das bloße
    # Vorhandensein der Kopfzeile. Der Kriterien-Lauf schreibt fuer jedes beurteilte Foto eine
    # LOKALE Kopfzeile; ein reiner Existenztest meldete jedes lokal beurteilte Foto als
    # erfolgreich cloud-klassifiziert, obwohl nie ein Cloud-Aufruf stattfand. Dieselbe Bedingung
    # steht in worker/remote_categories.py::select_remote_category_candidates und
    # candidate_counts.py::count_remote_category_candidates.
    # SICHERHEITSAUFLAGE: das Erfolgssignal ist ZUSAMMENGESETZT, genau wie das Skip-Kriterium
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
            # Spiegelt exakt die WHERE-Klausel von
            # worker/remote_categories.py::select_remote_category_candidates - und zwar ueber
            # DASSELBE Praedikat, nicht ueber eine zweite Formulierung davon. Kein
            # Ort des Praedikats: Anzeige, keine Grenze.
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

    SICHERHEIT: MITGLIEDSCHAFTSPRUEFUNG statt blindem Cast, sonst legt ein einzelner Wert
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


def event_out(event: Event) -> EventOut:
    return EventOut(
        id=event.id,
        position=event.position,
        started_at=event.started_at,
        ended_at=event.ended_at,
        place=_event_place_out(event),
        place_name=event.place_name,
    )


def location_out(location: EffectiveLocation | None) -> PhotoLocationOut | None:
    """`source` ist ein SICHERHEITSMERKMAL, kein Anzeigedetail: es entsteht ausschliesslich aus
    `EffectiveLocation.inferred` und wird nie aus einem anderen Signal nachgebildet."""
    if location is None:
        return None
    return PhotoLocationOut(
        lat=location.lat, lon=location.lon, source="derived" if location.inferred else "exif"
    )


def _album_suitability_out(photo: Photo, source: CategoryMethod) -> AlbumSuitabilityOut | None:
    """Die zaehlende Stufe aus der Tabelle des Verfahrens `source` - unabhaengig von der Herkunft
    der Motiv-Kopfzeile. Fehlt die Zeile dieses Verfahrens, ist das Ergebnis `None`, auch wenn das
    andere Verfahren eine Stufe hat (kein Rueckfall).

    Der Cloud-Text wird UNVERAENDERT aus der Zeile uebernommen - kein erneutes Sanieren, kein
    erneutes Kappen. Beides geschah EINMAL am Parser; eine zweite Fassung hier waere die zweite
    Pflegestelle, die auseinanderlaeuft."""
    if source is CategoryMethod.EYE:
        result = photo.eye_result
        if result is None:
            return None
        # Eye hat keinen Modelltext; eine daneben liegende Cloud-Begruendung gehoert nicht zu
        # dieser Stufe und bleibt hier aussen vor.
        return AlbumSuitabilityOut(level=result.album_level, reason=None, source="eye")
    suitability = photo.album_suitability
    if suitability is None:
        return None
    return AlbumSuitabilityOut(level=suitability.level, reason=suitability.reason, source="cloud")


def _eye_result_out(photo: Photo) -> EyeResultOut | None:
    """Die Eye-Auswertung NUR bei gueltiger Eye-Kopfzeile - der Schatten bleibt unsichtbar.

    Die Reihenfolge der Labels kommt aus der Tabelle selbst (`fine_labels` hat keine eigene
    Sortierspalte): absteigend nach Konfidenz, bei Gleichstand nach Label, damit die Antwort
    zwischen zwei Abfragen nicht wackelt."""
    assessment = photo.motif_assessment
    result = photo.eye_result
    if assessment is None or result is None or assessment.source is not MotifAssessmentSource.EYE:
        return None
    return EyeResultOut(
        album_level=result.album_level,
        model_revision=result.model_revision,
        mapping_version=result.mapping_version,
        computed_at=result.computed_at,
        fine_labels=[
            label.label
            for label in sorted(result.fine_labels, key=lambda row: (-row.confidence, row.label))
        ],
    )


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


def to_photo_out(
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
    persons: list[PhotoPersonOut],
    album_level_source: CategoryMethod,
) -> PhotoOut:
    """Baut die Antwortdarstellung EINES Fotos.

    SICHERHEIT - die Antwort ist eine Funktion des ANFRAGENDEN Nutzers:

    Bekommen `GET /projects/{id}/photos`, `GET /projects/{id}/album-draft`,
    `GET /projects/{id}/draft-alternatives` oder `GET /projects/{id}/album-selection` je eine
    Antwort-Zwischenspeicherung, ein `ETag` oder ein `Cache-Control` ueber `no-store` hinaus, MUSS
    der Schluessel den Nutzer enthalten. Dafuer gibt es ZWEI UNABHAENGIGE URSACHEN;
    der Wegfall der einen hebt die Auflage nicht auf:

    * der ANTWORTKOERPER: `PhotoOut.suggestion` wird unten genau dann gesetzt, wenn der anfragende
      Nutzer noch keine eigene Albumentscheidung fuer dieses Foto hat (`has_own_album_decision`) -
      zwei Nutzer bekommen fuer dasselbe Foto verschiedene Antwortkoerper.
    * die MENGE: Der Entwurfs-Lesepfad liefert `Vorschlag ∪ eigene Aufnahmen ∪ eigene
      Streichungen mit Rangzeile` und ist damit je Nutzer eine ANDERE Liste; `total` des
      Alternativen-Endpunkts ist die Restmenge nach Abzug des EIGENEN Albums. Bei Verletzung saehe
      der eine den Entwurf des anderen als seinen eigenen - samt "Deine Eingriffe" -, ohne dass
      irgendeine Anzeige das als falsch ausweist.

    Nicht theoretisch: das Frontend ist eine PWA mit Workbox
    (`registerType: 'autoUpdate'`), heute ohne `runtimeCaching` fuer API-Antworten; der
    Service-Worker-Cache ist pro Browserprofil geteilt, und das JWT liegt in `localStorage` - zwei
    Personen an einem Geraet ist der realistische Familienfall.

    `PhotoOut.ratings[]` traegt diese Auflage AUSDRUECKLICH NICHT: die Liste enthaelt beide
    Bewertungen und ist fuer beide Anfragenden identisch - sichtbare Fremdbewertung ist gewollt.
    `RankingOut.proposed` ebenso wenig: es ist lauf-global.

    Auf `GET /projects/{id}/album-selection` trifft von den beiden Ursachen nur die erste zu: Die
    MENGE ist dort nutzerunabhaengig, `PhotoOut.suggestion` bleibt es nicht. EINE Ursache genuegt;
    die Abwesenheit der anderen ist keine Erlaubnis.

    `curation_position` traegt keinen Ablehnungsfilter; sie numeriert die gelieferte Reihenfolge
    und haengt damit an der Menge, nicht an einer Bewertung.

    `decisions` und `user_count` sind PFLICHTIGE Schluesselwortparameter ohne Vorgabewert.
    Ein vergessener Aufrufer wirft keine Ausnahme und liefert keinen Fehlercode - er
    antwortete `in_final_selection: false` fuer jedes Foto, plausibel und still. Das ist die
    Menge, die als Album gilt und die der Export nimmt; der Fehler zeigte sich erst an einem
    leeren Album, nicht an der Stelle, an der er entsteht. `mypy --strict` ist die einzige
    Pruefung, die ihn vor der Laufzeit faengt.

    `album_level_source` ist ebenfalls PFLICHTIGES Schluesselwort und kommt aus
    `album_level_source`, EINMAL je Anfrage berechnet. Er kommt nie aus einem Query- oder
    Body-Parameter und nie aus einem anderen Feld derselben Antwort: Ein vergessener Aufrufer
    scheiterte an `mypy --strict`, statt still die Tabelle des anderen Verfahrens zu lesen.

    Die drei Felder sind PROJEKTAUSSAGEN und tragen die Cache-Auflage ausdruecklich NICHT - genau
    wie `ratings[]` und `RankingOut.proposed`."""
    # Anzeigeregel: ein Vorschlag ist nur sichtbar, wenn (a) er OFFEN ist - gestellt und im
    # Duplikat-Vergleich noch nicht beantwortet - UND (b) der anfragende Nutzer noch
    # KEINE eigene ALBUMENTSCHEIDUNG fuer dieses Foto hat, unabhaengig davon, ob eine ANDERE
    # Person das Foto schon bewertet hat; die eigene Bewertung hat immer Vorrang.
    #
    # Das VORHANDENSEIN der Bewertungszeile ist hier keine Aussage: da `favorite` eine eigene
    # Spalte ist, existiert eine Zeile auch ohne jede Albumentscheidung. Ueber das
    # Zeilenvorhandensein gepruefte Abwesenheit liesse den Ausschuss-Vorschlag verschwinden, sobald
    # jemand das Foto als Favorit markiert - ohne Meldung und ohne Weg zurueck.
    has_own_album_decision = any(
        rating.user_id == current_user_id and rating.status is not None for rating in photo.ratings
    )
    has_suggestion = has_open_suggestion_for(photo) and not has_own_album_decision
    suggestion = _to_suggestion_out(photo.score) if has_suggestion and photo.score else None
    decision = decisions.get(photo.id)
    state = selection_state_of(
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
        album_suitability=_album_suitability_out(photo, album_level_source),
        eye_result=_eye_result_out(photo),
        final_selection_decision=decision,
        in_final_selection=state.included,
        contested=state.contested,
        persons=persons,
    )
