"""Die laufende Diagnose und die Gewichte, die aus ihr abgeleitet werden.

OHNE PROJEKTPARAMETER und als EIGENER Router statt einer Einbettung in `ProjectStatsOut`: Dieser
Block rechnet projektuebergreifend, ist spuerbar teurer als die uebrigen Projektzahlen und wird
nach einer Gewichtsanpassung fuer sich neu geladen. Eingebettet zwaenge er die ganze
Statistikseite in seinen Ladezustand.

DIE GEWICHTE KOMMEN NIE AUS EINEM BODY. Beide Schreibendpunkte tragen genau ein Feld, und das ist
ein WAECHTER: der Anker auf den zuletzt gesehenen Ereignisstand bzw. die Fassung, die
zurueckgenommen werden soll. Der Server rechnet den Vorschlag neu. `weight` waere der einzige
Wert, mit dem ein Aufrufer die eigene Korrektur in der global wirkenden Ableitung
ueberproportional zaehlen liesse.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, computed_field
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.api.deps import get_current_user, get_session
from photosort.criteria import CRITERIA_REGISTRY
from photosort.feedback import ExchangeKind, MotifErrorCase, derive_weights
from photosort.feedback_log import latest_event_id, load_diagnosis
from photosort.models import QualityWeightSetOrigin, User
from photosort.quality import QUALITY_CRITERION_WEIGHTS
from photosort.quality_weights import (
    effective_weights,
    latest_weight_set,
    previous_weights,
    store_weights,
)

# SICHERHEIT (S1): Der Torwaechter haengt am ROUTER und gilt damit fuer jeden Endpunkt hier, auch
# fuer einen spaeter ergaenzten. Er traegt zusaetzlich seinen Eintrag in
# `tests/test_auth_guard.py::_protected_router_operations()` und je Pfad einen eigenen,
# pfadbenannten 401-Fall. Ohne ihn waere die Diagnose ein unauthentifizierter Lesepfad auf
# Aussagen ueber ALLE Projekte und die Anpassung ein unauthentifizierter Schreibzugriff auf eine
# global wirkende Grundlage.
#
# Die beiden Schreibendpunkte nehmen `current_user` ZUSAETZLICH als Parameter entgegen - nicht
# fuer die Authentifizierung, sondern weil eine Fassung ihren Urheber traegt. Das ist
# Urheberschaft, nie Geltungsbereich: Die Fassung wirkt auf jeden Lauf jedes Projekts.
router = APIRouter(prefix="/feedback", tags=["feedback"], dependencies=[Depends(get_current_user)])

# Deklarative Obergrenze wie in S4: Ein unbeschraenkter Pydantic-`int` erzeugt unter SQLite
# jenseits von 2^63 einen `OverflowError` und damit `500` statt `422`.
_MAX_ID = 1_000_000_000

# EIN Text fuer beide Konfliktfaelle der Uebernahme waere falsch - die beiden Waechter sagen
# Verschiedenes, und die Oberflaeche muss dem Nutzer sagen koennen, was zu tun ist.
_STALE_ANCHOR = (
    "Seit der Anzeige sind neue Korrekturen hinzugekommen. Bitte lade die Rueckmeldung neu und "
    "sieh dir den aktualisierten Vorschlag an."
)
_STALE_SET = "Die genannte Fassung ist nicht mehr die geltende. Bitte lade die Rueckmeldung neu."


class MotifErrorOut(BaseModel):
    """Ein Motiv-Fehlerfall mit seiner Fallzahl.

    Die drei Faelle sind NICHT erschoepfend: Eine Korrektur ohne Modellfehler (ein hinzugefuegtes
    Motiv, das das Modell ohnehin traegt; jede Ruecknahme) zaehlt in keinem von ihnen. Ihre
    Bezugsgroesse ist `correction_count`, nie ihre eigene Summe."""

    case: MotifErrorCase
    count: int


class ExchangeStatsOut(BaseModel):
    """Eine Tauschklasse mit ihren drei Zahlen.

    `quality_incomparable_count` haelt die Paare mit gleichem UND die mit fehlendem eingefrorenem
    Qualitaetswert; sie gehen in `preferred_lower_rated_count` nicht ein und werden auch seinem
    Gegenstueck nicht zugeschlagen (D4)."""

    kind: ExchangeKind
    count: int
    preferred_lower_rated_count: int
    quality_incomparable_count: int


class CriterionAgreementOut(BaseModel):
    """Die Bilanz eines Kriteriums (D5).

    `case_count` ist die Zahl der TATSAECHLICH AUSWERTBAREN Paare - beide Fotos tragen den
    Messwert. Sie kann kleiner sein als die Zahl der gleichstufigen Austausche; beide stehen
    nebeneinander. `agreement` liegt in `[-1, 1]` und ist bei null Stimmen `0.0`.

    `display_name` kommt aus `criteria.py::CRITERIA_REGISTRY`, wie bei `CriterionScoreOut`: Im
    Frontend wird dazu bewusst keine zweite Merkmalsliste gepflegt - sie liefe mit jedem neuen
    Kriterium auseinander, und die Tabelle zeigte dann rohe Schluessel."""

    criterion_key: str
    display_name: str
    case_count: int
    agreement: float


class CriterionWeightOut(BaseModel):
    """Das GELTENDE Gewicht eines Kriteriums."""

    criterion_key: str
    weight: float


class ProposedWeightOut(BaseModel):
    """Das ABGELEITETE Gewicht eines Kriteriums samt seiner Abweichung vom geltenden.

    `delta` ist `weight - <geltendes Gewicht>` und damit genau der Unterschied zwischen den
    beiden nebeneinander dargestellten Spalten. Eine Abweichung gegenueber dem STARTWERT waere
    eine dritte Zahl, die niemand sieht.

    HIER STEHEN WEDER `case_count` NOCH `agreement`: Beide tragen die Kriterienliste `criteria`
    dieser Antwort, aus denselben Paaren gerechnet. Eine zweite Kopie in derselben Antwort waere
    eine zweite Wahrheit, und welche gilt, entschiede der Lesepfad."""

    criterion_key: str
    weight: float
    delta: float


class WeightPreviewOut(BaseModel):
    """Die Gewichts-Vorschau: was gilt, was vorgeschlagen wird, woran das haengt.

    `based_on_event_id` ist das ZUSTIMMUNGS-TOKEN auf den zuletzt beruecksichtigten
    Ereignisstand (S6), nie ein Objektverweis: Es wird nie zu einer Zeile aufgeloest, traegt
    keine Autorisierung und ist bei leerem Log `0`. Es ist das Einzige, was "der Nutzer hat
    uebernommen, was ihm angezeigt wurde" wahr macht - die Uebernahme prueft es auf STRIKTE
    GLEICHHEIT gegen die hoechste `id` des GESAMTEN Logs.

    `current_set_id` ist die geltende Fassung, `None` heisst "es gilt der Startwertsatz". Die
    Ruecknahme MUSS sie nennen koennen (S7), und `can_revert` ist genau
    `current_set_id is not None` - deshalb ein BERECHNETES Feld und kein zweites, unabhaengig
    gefuelltes: Zwei Quellen fuer dieselbe Aussage liefen auseinander, und die Oberflaeche boete
    eine Schaltflaeche ohne Ziel an. Die erste Fassung ist sehr wohl zuruecknehmbar - ihre
    Vorgaengerin ist der Startwertsatz.

    DER VORSCHLAG WIRD AUS DEN STARTWERTEN ABGELEITET, nie aus den geltenden Gewichten: Sonst
    verschoebe jede Uebernahme die Grundlage der naechsten, und die Bandbreite aus G3 waere nach
    wenigen Runden verlassen, ohne dass eine einzelne Uebernahme sie je verletzte."""

    current: list[CriterionWeightOut]
    proposed: list[ProposedWeightOut]
    based_on_event_id: int
    current_set_id: int | None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def can_revert(self) -> bool:
        """Ohne gespeicherte Fassung gibt es nichts zurueckzunehmen (G10)."""
        return self.current_set_id is not None


class FeedbackDiagnosisOut(BaseModel):
    """Die Diagnose - AUSSCHLIESSLICH AGGREGATE (S8).

    `correction_count` ist die UNGEWICHTETE Zahl aller festgehaltenen Korrekturen, ueber alle
    Projekte und beide Nutzer. Ein Ereignis der gemeinsamen Endauswahl wiegt in der RECHNUNG
    mehr, zaehlt hier aber wie jedes andere genau einmal: Eine gewichtete Zahl als Fallzahl
    behauptete Korrekturen, die niemand vorgenommen hat.

    Eine zurueckgenommene Korrektur ERHOEHT diese Zahl und verringert sie nie - das Log ist
    append-only, und die Fallzahl, in die das urspruengliche Ereignis eingeht, bleibt bestehen."""

    correction_count: int
    motif_errors: list[MotifErrorOut]
    exchanges: list[ExchangeStatsOut]
    criteria: list[CriterionAgreementOut]
    weights: WeightPreviewOut


class WeightAdoptionIn(BaseModel):
    """Der Body der Uebernahme: GENAU EIN FELD, und das ist ein Waechter (G7/S4).

    Kein Gewicht, kein Kriterium, kein Nutzer - Massenzuweisung ist strukturell ausgeschlossen
    statt im Handler herausgefiltert, und `extra="forbid"` weist ein zusaetzliches Feld
    ausdruecklich ab, statt es still zu verwerfen.

    `based_on_event_id` ist das Zustimmungs-Token (S6): `0` bei leerem Log, sonst die hoechste
    `id` des gesamten Logs, wie sie die Diagnose ausgewiesen hat."""

    model_config = ConfigDict(extra="forbid")

    based_on_event_id: int = Field(ge=0, le=_MAX_ID)


class WeightRevertIn(BaseModel):
    """Der Body der Ruecknahme: die Fassung, die zurueckgenommen werden soll (S7).

    Ohne diese Angabe legen zwei Aufrufe kurz hintereinander erst die Ruecknahme und dann deren
    Ruecknahme an - das Ergebnis ist der Ausgangszustand, die Kette sieht lueckenlos aus, und
    keine Anzeige weist das als falsch aus."""

    model_config = ConfigDict(extra="forbid")

    reverts_set_id: int = Field(ge=1, le=_MAX_ID)


async def _weight_preview(session: AsyncSession) -> WeightPreviewOut:
    """Die Vorschau, aus EINER Rechnung fuer alle drei Endpunkte.

    Ein zweiter Rechenweg fuer dasselbe liefe auseinander - und die Zusage "die gespeicherten
    Werte sind exakt die zuvor angezeigten" (G6) haengt daran, dass Anzeige und Uebernahme
    denselben Weg gehen."""
    diagnosis = await load_diagnosis(session, criterion_keys=tuple(QUALITY_CRITERION_WEIGHTS))
    current = await effective_weights(session)
    current_set = await latest_weight_set(session)
    # ABGELEITET AUS DEN STARTWERTEN, nie aus `current`: siehe `WeightPreviewOut`.
    proposed = derive_weights(diagnosis.criteria, QUALITY_CRITERION_WEIGHTS)
    return WeightPreviewOut(
        current=[
            CriterionWeightOut(criterion_key=key, weight=current[key])
            for key in QUALITY_CRITERION_WEIGHTS
        ],
        proposed=[
            ProposedWeightOut(
                criterion_key=key, weight=proposed[key], delta=proposed[key] - current[key]
            )
            for key in QUALITY_CRITERION_WEIGHTS
        ],
        based_on_event_id=diagnosis.latest_event_id,
        current_set_id=None if current_set is None else current_set.id,
    )


@router.post("/weights", response_model=WeightPreviewOut)
async def adopt_feedback_weights(
    payload: WeightAdoptionIn,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> WeightPreviewOut:
    """Uebernimmt die abgeleiteten Gewichte als neue, global geltende Fassung.

    DER SERVER RECHNET DEN VORSCHLAG NEU; der Body traegt keine Gewichte. Uebernommen wird genau
    das, was die Diagnose unter demselben Anker angezeigt hat.

    `based_on_event_id` wird auf STRIKTE GLEICHHEIT gegen die hoechste `id` des GESAMTEN Logs
    geprueft - nie gegen ein nach Projekt oder Art gefiltertes Maximum. Sind seither Ereignisse
    hinzugekommen, gleich in welchem Projekt, antwortet der Endpunkt `409` und schreibt NICHTS.

    ER SCHREIBT DIE NEUE FASSUNG UND SONST NICHTS (G9): Keine Rangzeile bewegt sich, es entsteht
    kein neuer Lauf, es wird kein Hintergrundjob eingereiht, und es ergeht kein Modell- oder
    Cloud-Aufruf. Erst der naechste Durchlauf rechnet mit den neuen Gewichten. Das ist der
    bewusste Gegensatz zu `PUT /projects/{id}/selection-target`, das synchron neu rechnet - eine
    Gewichtsanpassung wirkt global und riesse sonst jeden offenen Entwurf jedes Projekts um.

    Geloest wird der Anker NIE zu einer Zeile auf: Er traegt keine Autorisierung, er ist das
    Einzige, was "der Nutzer hat uebernommen, was ihm angezeigt wurde" wahr macht."""
    if payload.based_on_event_id != await latest_event_id(session):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_STALE_ANCHOR)

    diagnosis = await load_diagnosis(session, criterion_keys=tuple(QUALITY_CRITERION_WEIGHTS))
    await store_weights(
        session,
        weights=derive_weights(diagnosis.criteria, QUALITY_CRITERION_WEIGHTS),
        user_id=current_user.id,
        based_on_event_id=payload.based_on_event_id,
    )
    await session.commit()
    return await _weight_preview(session)


@router.post("/weights/revert", response_model=WeightPreviewOut)
async def revert_feedback_weights(
    payload: WeightRevertIn,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> WeightPreviewOut:
    """Nimmt die geltende Fassung zurueck - als NEUE Fassung mit den Werten ihrer Vorgaengerin.

    ES WIRD NIE EINE FASSUNG GELOESCHT; die Kette bleibt lueckenlos. Und es ist ein UMSCHALTER:
    Der zweite Druck fuehrt zurueck auf die Werte, von denen der erste zurueckgesetzt hat, und
    geht nicht eine weitere Fassung rueckwaerts (G10).

    Der Aufruf NENNT die Fassung, die zurueckgenommen werden soll, und wird mit `409` abgewiesen,
    wenn sie nicht mehr die geltende ist - auch dann, wenn es ueberhaupt keine gibt. Ohne diesen
    Waechter legen zwei Aufrufe kurz hintereinander erst die Ruecknahme und dann deren Ruecknahme
    an (S7).

    Die Vorgaengerin der ersten Fassung ist der STARTWERTSATZ: Die erste Anpassung bleibt damit
    zuruecknehmbar, ohne dass je eine Fassung mit den Startwerten gespeichert worden waere.

    Wie die Uebernahme rechnet er nichts neu - die Aenderung wirkt erst beim naechsten
    Durchlauf."""
    current = await latest_weight_set(session)
    if current is None or current.id != payload.reverts_set_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_STALE_SET)

    await store_weights(
        session,
        weights=await previous_weights(session),
        user_id=current_user.id,
        origin=QualityWeightSetOrigin.REVERT,
        reverts_set_id=current.id,
    )
    await session.commit()
    return await _weight_preview(session)


@router.get("/diagnosis", response_model=FeedbackDiagnosisOut)
async def get_feedback_diagnosis(
    session: AsyncSession = Depends(get_session),
) -> FeedbackDiagnosisOut:
    """Was die Nacharbeit am Album-Entwurf ueber die Modellfehler sagt.

    DIE ZAHLEN GELTEN PROJEKTUEBERGREIFEND UND UEBER BEIDE NUTZER, obwohl der Abschnitt auf der
    Projekt-Statistikseite steht: Der Gewichtssatz gilt global; zaehlten sie nur ein Projekt,
    stuenden sie neben einem Vorschlag, den sie nicht belegen. Der Endpunkt nimmt deshalb keinen
    Projektparameter entgegen. Die Beschriftung des Abschnitts spricht das aus.

    ES GIBT KEINE EINZELEREIGNISSE HIER und keine Aufschluesselung je Nutzer (S8). Das Log haelt
    auch ZURUECKGENOMMENE Korrekturen fest, die der Bestand nicht mehr zeigt; alles andere, was
    die Diagnose zaehlt, ist ueber `PhotoOut.ratings[]` ohnehin je Foto lesbar.

    Die drei Tauschklassen stehen GETRENNT und werden nirgends summiert. Ein Paar mit fehlender
    Modellstufe ist `undetermined` und wird keiner der beiden anderen zugeschlagen.

    Ein Eintrag je Fehlerfall, je Tauschklasse und je Kriterium steht auch dann in der Antwort,
    wenn seine Zahl null ist - den Leerzustand erkennt die Oberflaeche an `correction_count`.

    `weights` traegt die VORSCHAU auf die Anpassung: das geltende Gewicht, das abgeleitete und
    die Abweichung, dazu den Anker, gegen den eine Uebernahme geprueft wird, und ob eine
    Ruecknahme angeboten wird. Es wird hier NICHTS geschrieben - der Vorschlag entsteht bei jedem
    Aufruf neu und wird erst durch `POST /feedback/weights` uebernommen."""
    diagnosis = await load_diagnosis(session, criterion_keys=tuple(QUALITY_CRITERION_WEIGHTS))
    return FeedbackDiagnosisOut(
        correction_count=diagnosis.correction_count,
        motif_errors=[
            MotifErrorOut(case=case, count=diagnosis.motif_errors[case]) for case in MotifErrorCase
        ],
        exchanges=[
            ExchangeStatsOut(
                kind=kind,
                count=diagnosis.exchanges[kind].count,
                preferred_lower_rated_count=diagnosis.exchanges[kind].preferred_lower_rated_count,
                quality_incomparable_count=diagnosis.exchanges[kind].quality_incomparable_count,
            )
            for kind in ExchangeKind
        ],
        criteria=[
            CriterionAgreementOut(
                criterion_key=key,
                display_name=CRITERIA_REGISTRY[key].display_name,
                case_count=diagnosis.criteria[key].case_count,
                agreement=diagnosis.criteria[key].agreement,
            )
            for key in QUALITY_CRITERION_WEIGHTS
        ],
        weights=await _weight_preview(session),
    )
