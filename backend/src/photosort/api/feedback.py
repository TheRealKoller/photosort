"""Der Lesepfad der laufenden Diagnose - was die Nacharbeit ueber die Modellfehler sagt.

OHNE PROJEKTPARAMETER und als EIGENER Endpunkt statt einer Einbettung in `ProjectStatsOut`:
Dieser Block rechnet projektuebergreifend, ist spuerbar teurer als die uebrigen Projektzahlen und
wird nach einer Gewichtsanpassung fuer sich neu geladen. Eingebettet zwaenge er die ganze
Statistikseite in seinen Ladezustand.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.api.deps import get_current_user, get_session
from photosort.feedback import ExchangeKind, MotifErrorCase, derive_weights
from photosort.feedback_log import load_diagnosis
from photosort.quality import QUALITY_CRITERION_WEIGHTS
from photosort.quality_weights import effective_weights, latest_weight_set

# SICHERHEIT (S1): Der Torwaechter haengt am ROUTER, und das ist hier moeglich, weil kein Endpunkt
# dieses Routers das `User`-Objekt selbst braucht - die Diagnose ist in jedem Feld
# nutzerunabhaengig. Er traegt zusaetzlich seinen Eintrag in
# `tests/test_auth_guard.py::_protected_router_operations()` und einen eigenen, pfadbenannten
# 401-Fall in `tests/test_api_feedback.py`. Ohne den Torwaechter waere dies ein
# unauthentifizierter Lesepfad auf Aussagen ueber ALLE Projekte.
router = APIRouter(prefix="/feedback", tags=["feedback"], dependencies=[Depends(get_current_user)])


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
    nebeneinander. `agreement` liegt in `[-1, 1]` und ist bei null Stimmen `0.0`."""

    criterion_key: str
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

    `can_revert` ist wahr, sobald ueberhaupt eine Fassung gespeichert ist: Ohne sie gibt es
    nichts zurueckzunehmen, und die Schaltflaeche wird nicht angeboten (G10). Die erste Fassung
    ist sehr wohl zuruecknehmbar - ihre Vorgaengerin ist der Startwertsatz.

    DER VORSCHLAG WIRD AUS DEN STARTWERTEN ABGELEITET, nie aus den geltenden Gewichten: Sonst
    verschoebe jede Uebernahme die Grundlage der naechsten, und die Bandbreite aus G3 waere nach
    wenigen Runden verlassen, ohne dass eine einzelne Uebernahme sie je verletzte."""

    current: list[CriterionWeightOut]
    proposed: list[ProposedWeightOut]
    based_on_event_id: int
    can_revert: bool


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
    current = await effective_weights(session)
    # ABGELEITET AUS DEN STARTWERTEN, nie aus `current`: siehe `WeightPreviewOut`.
    proposed = derive_weights(diagnosis.criteria, QUALITY_CRITERION_WEIGHTS)
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
                case_count=diagnosis.criteria[key].case_count,
                agreement=diagnosis.criteria[key].agreement,
            )
            for key in QUALITY_CRITERION_WEIGHTS
        ],
        weights=WeightPreviewOut(
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
            can_revert=await latest_weight_set(session) is not None,
        ),
    )
