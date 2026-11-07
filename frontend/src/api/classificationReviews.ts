import { apiFetch, apiFetchBlob } from './client'
import type {
  ClassificationReviewCasesOut,
  ClassificationReviewCreateBody,
  ClassificationReviewCreatedOut,
  ClassificationReviewDetailOut,
  ClassificationReviewEstimateOut,
  ClassificationReviewListItemOut,
  ClassificationReviewOptionsOut,
  ClassificationReviewSideIn,
  ClassificationReviewVerdictOut,
  ClassificationVerdict,
} from './types'

/*
 * Der Client der Klassifizierungspruefung (Spec 0616). Basis ist der ENGLISCHE Kebab-Pfad wie bei
 * `album-draft` und `duplicate-groups`; der deutsche Pfad gilt ausschliesslich der Oberflaeche.
 *
 * KEIN Betrag, kein Anbieter und keine Id-Liste im Koerper: Kosten entstehen serverseitig, der
 * Anbieter folgt aus dem Modell, und welche Faelle es gibt, entscheidet die Pruefung.
 */

function reviewBase(projectId: number): string {
  return `/projects/${projectId}/classification-reviews`
}

/** Alle Pruefungen des Projekts, neueste zuerst. */
export function listClassificationReviews(
  projectId: number,
): Promise<ClassificationReviewListItemOut[]> {
  return apiFetch<ClassificationReviewListItemOut[]>(reviewBase(projectId))
}

/**
 * Waehlbare Verfahren samt Sperrgruenden. `unavailable_reasons` ist die geschlossene Menge der
 * Gruende - die Oberflaeche formuliert sie, sie leitet sie nicht ab.
 */
export function getClassificationReviewOptions(
  projectId: number,
): Promise<ClassificationReviewOptionsOut> {
  return apiFetch<ClassificationReviewOptionsOut>(`${reviewBase(projectId)}/options`)
}

/**
 * Die Kostenvorschau vor dem Start, je Seite: Groesse der Pruefmenge x Preis je Bild.
 *
 * Es gibt KEINEN Betrag im Aufruf; `estimated_cost_usd` der Antwort ist `0.0` fuer kostenfreie
 * Verfahren und `null` fuer "nicht schaetzbar" - nie "kostenlos".
 */
export function getClassificationReviewEstimate(
  projectId: number,
  sides: { a: ClassificationReviewSideIn; b: ClassificationReviewSideIn },
): Promise<ClassificationReviewEstimateOut> {
  const query = new URLSearchParams({
    a_kind: sides.a.kind,
    b_kind: sides.b.kind,
  })
  // Ein Modell gilt nur fuer eine Cloud-Seite; an einer Eye- oder lokalen Seite ist es wirkungslos
  // und wird deshalb nicht gesendet.
  if (sides.a.kind === 'cloud' && sides.a.model) {
    query.set('a_model', sides.a.model)
  }
  if (sides.b.kind === 'cloud' && sides.b.model) {
    query.set('b_model', sides.b.model)
  }
  return apiFetch<ClassificationReviewEstimateOut>(
    `${reviewBase(projectId)}/estimate?${query.toString()}`,
  )
}

/**
 * Die Verfahrenswahl einer Seite, reduziert auf die Felder, die zu ihrer Art gehoeren.
 *
 * Ein Modell an einer Eye-Seite oder eine Fassung an einer Cloud-Seite waere am falschen Ort und
 * damit wirkungslos; sie wird hier gar nicht erst gesendet statt still verworfen.
 */
function sideBody(side: ClassificationReviewSideIn): ClassificationReviewSideIn {
  if (side.kind === 'cloud' && side.model) {
    return { kind: side.kind, model: side.model }
  }
  if (side.kind === 'eye' && side.eye_mapping_version) {
    return { kind: side.kind, eye_mapping_version: side.eye_mapping_version }
  }
  return { kind: side.kind }
}

/**
 * Legt eine Pruefung an und reiht den Job ein. Antwortet `201` mit Id und `running`.
 *
 * Die Ablehnungen sind Teil der Zusage und kommen als `ApiError` mit `status`: `403` (Funktion
 * aus, Eye abgeschaltet, Cloud ohne Einwilligung), `404` (Projekt unbekannt), `409` (kein
 * erfolgreicher Ausschusslauf, Gate fehlt, eine Pruefung laeuft), `503` (Eye-Dienst nicht
 * erreichbar, nichts eingereiht), `422` (zwei gleiche Seiten, unbekanntes Modell oder Fassung,
 * Pruefgraesse ausserhalb der Grenzen).
 */
export function createClassificationReview(
  projectId: number,
  body: ClassificationReviewCreateBody,
): Promise<ClassificationReviewCreatedOut> {
  return apiFetch<ClassificationReviewCreatedOut>(reviewBase(projectId), {
    method: 'POST',
    body: {
      a: sideBody(body.a),
      b: sideBody(body.b),
      sample_size: body.sample_size,
    },
  })
}

/** Status, Fortschritt, Herkunft beider Seiten, Zaehlungen je Zweck und Urteilszahlen. */
export function getClassificationReview(
  projectId: number,
  reviewId: number,
): Promise<ClassificationReviewDetailOut> {
  return apiFetch<ClassificationReviewDetailOut>(`${reviewBase(projectId)}/${reviewId}`)
}

/**
 * Die vorgelegten Faelle, sortiert nach Foto-Position, Zweck und Merkmal. Bei einer laufenden
 * Pruefung antwortet der Server mit `200` und leerer Liste - kein Fehlerzustand.
 */
export function listClassificationReviewCases(
  projectId: number,
  reviewId: number,
): Promise<ClassificationReviewCasesOut> {
  return apiFetch<ClassificationReviewCasesOut>(`${reviewBase(projectId)}/${reviewId}/cases`)
}

/**
 * Setzt oder aendert das EINE Urteil eines Falls (Upsert, letzter Schreiber gewinnt).
 *
 * `404` heisst "Fall oder Pruefung unbekannt", `409` "die Pruefung ist nicht abgeschlossen"; ein
 * unbekannter Urteilswert kann hier strukturell nicht entstehen (`ClassificationVerdict`).
 */
export function setClassificationReviewVerdict(
  projectId: number,
  reviewId: number,
  caseId: number,
  verdict: ClassificationVerdict,
): Promise<ClassificationReviewVerdictOut> {
  return apiFetch<ClassificationReviewVerdictOut>(
    `${reviewBase(projectId)}/${reviewId}/cases/${caseId}/verdict`,
    { method: 'PUT', body: { verdict } },
  )
}

/**
 * Die Exportdatei fuer die KI - ein authentifizierter Blob-Weg, weil ein gewoehnlicher Link keinen
 * Authorization-Header traegt. `409`, solange die Pruefung nicht `SUCCESS` ist.
 */
export function exportClassificationReview(projectId: number, reviewId: number): Promise<Blob> {
  return apiFetchBlob(`${reviewBase(projectId)}/${reviewId}/export`)
}
