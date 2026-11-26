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
 * Der Client der Klassifizierungspruefung. Basis ist der ENGLISCHE Kebab-Pfad wie bei
 * `album-draft` und `duplicate-groups`; der deutsche Pfad gilt ausschliesslich der Oberflaeche.
 *
 * KEIN Betrag, kein Anbieter und keine Id-Liste im Koerper: Kosten entstehen serverseitig, der
 * Anbieter folgt aus dem Modell, und welche Faelle es gibt, entscheidet die Pruefung.
 */

/** Alle Pruefungen des Projekts, neueste zuerst. */
export function listClassificationReviews(
  projectId: number,
): Promise<ClassificationReviewListItemOut[]> {
  return apiFetch('/projects/{project_id}/classification-reviews', {
    pathParams: { project_id: projectId },
  })
}

/**
 * Waehlbare Verfahren samt Sperrgruenden. `unavailable_reasons` ist die geschlossene Menge der
 * Gruende - die Oberflaeche formuliert sie, sie leitet sie nicht ab.
 */
export function getClassificationReviewOptions(
  projectId: number,
): Promise<ClassificationReviewOptionsOut> {
  return apiFetch('/projects/{project_id}/classification-reviews/options', {
    pathParams: { project_id: projectId },
  })
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
  return apiFetch('/projects/{project_id}/classification-reviews/estimate', {
    pathParams: { project_id: projectId },
    query: {
      a_kind: sides.a.kind,
      b_kind: sides.b.kind,
      // Ein Modell gilt nur fuer eine Cloud-Seite; an einer Eye- oder lokalen Seite ist es
      // wirkungslos und wird deshalb nicht gesendet.
      ...(sides.a.kind === 'cloud' && sides.a.model ? { a_model: sides.a.model } : {}),
      ...(sides.b.kind === 'cloud' && sides.b.model ? { b_model: sides.b.model } : {}),
    },
  })
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
  return apiFetch('/projects/{project_id}/classification-reviews', {
    method: 'POST',
    pathParams: { project_id: projectId },
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
  return apiFetch('/projects/{project_id}/classification-reviews/{review_id}', {
    pathParams: { project_id: projectId, review_id: reviewId },
  })
}

/**
 * Die vorgelegten Faelle, sortiert nach Foto-Position, Zweck und Merkmal. Bei einer laufenden
 * Pruefung antwortet der Server mit `200` und leerer Liste - kein Fehlerzustand.
 */
export function listClassificationReviewCases(
  projectId: number,
  reviewId: number,
): Promise<ClassificationReviewCasesOut> {
  return apiFetch('/projects/{project_id}/classification-reviews/{review_id}/cases', {
    pathParams: { project_id: projectId, review_id: reviewId },
  })
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
  return apiFetch(
    '/projects/{project_id}/classification-reviews/{review_id}/cases/{case_id}/verdict',
    {
      method: 'PUT',
      pathParams: { project_id: projectId, review_id: reviewId, case_id: caseId },
      body: { verdict },
    },
  )
}

/**
 * Die Exportdatei fuer die KI - ein authentifizierter Blob-Weg, weil ein gewoehnlicher Link keinen
 * Authorization-Header traegt. `409`, solange die Pruefung nicht `SUCCESS` ist.
 */
export function exportClassificationReview(projectId: number, reviewId: number): Promise<Blob> {
  return apiFetchBlob('/projects/{project_id}/classification-reviews/{review_id}/export', {
    pathParams: { project_id: projectId, review_id: reviewId },
  })
}
