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
from photosort.feedback import ExchangeKind, MotifErrorCase
from photosort.feedback_log import load_diagnosis
from photosort.quality import QUALITY_CRITERION_WEIGHTS

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
    wenn seine Zahl null ist - den Leerzustand erkennt die Oberflaeche an `correction_count`."""
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
                case_count=diagnosis.criteria[key].case_count,
                agreement=diagnosis.criteria[key].agreement,
            )
            for key in QUALITY_CRITERION_WEIGHTS
        ],
    )
