import { apiFetch } from './client'
import type { DuplicateDecision, DuplicateGroupIndexOut, DuplicateGroupOut } from './types'

/**
 * Wie viele Duplikat-Gruppen das Projekt hat und wo der Durchgang beginnt.
 *
 * Grundlage der beiden Einstiege — aus dem Ausschuss-Schritt und aus der nach Vorschlägen
 * gefilterten Fotoliste. `total === 0` heißt „es gibt nichts zu vergleichen"; der Einstieg wird
 * dann nicht gerendert, damit er nicht auf eine leere Ansicht führt.
 *
 * KEINE Liste aller Gruppen: Sie wäre eine zweite Quelle derselben Reihenfolge neben
 * `position`/`total` der Gruppenantwort. Die Nachbarn reisen dort mit.
 */
export function getDuplicateGroupIndex(projectId: number): Promise<DuplicateGroupIndexOut> {
  return apiFetch<DuplicateGroupIndexOut>(`/projects/${projectId}/duplicate-groups`)
}

/**
 * Eine Duplikat-Gruppe, erreichbar über IRGENDEIN Mitglied.
 *
 * Die Gruppe ist abgeleitet und hat keine eigene Id (ADR 0104 Punkt 1): Der Server bildet sie zur
 * Lesezeit als Stern über `duplicate_of`. Jedes Mitglied — der Gewinner eingeschlossen — führt
 * deshalb zur selben Antwort.
 *
 * `404` heißt „zu dieser Id gibt es keine Gruppe" und deckt vier ununterscheidbare Fälle:
 * unbekanntes Foto, fremdes Projekt, Foto ohne Duplikat und Vorschlag wegen geringer
 * Bildqualität. Die Ansicht zeigt darauf ihren LEEREN Zustand, nicht den Fehler-Alert.
 */
export function getDuplicateGroup(projectId: number, photoId: number): Promise<DuplicateGroupOut> {
  return apiFetch<DuplicateGroupOut>(`/projects/${projectId}/duplicate-groups/${photoId}`)
}

/**
 * Die Entscheidung über EINE Aufnahme des Ausschusses.
 *
 * Der Body trägt ausschließlich `decision` — kein `photo_id`, kein `user_id`. Die Entscheidung
 * gehört dem Projekt, nicht dem angemeldeten Nutzer.
 *
 * ES GIBT KEINE RÜCKNAHME und kein `DELETE`: „noch nicht entschieden" ist kein Zustand, in den
 * man zurückkehrt; ändern heißt den anderen Wert schreiben.
 *
 * Die Antwort ist der vollständige neue Stand der ganzen Gruppe, nicht ein Echo des Bodys.
 */
export function setDuplicateDecision(
  projectId: number,
  photoId: number,
  decision: DuplicateDecision,
): Promise<DuplicateGroupOut> {
  return apiFetch<DuplicateGroupOut>(
    `/projects/${projectId}/photos/${photoId}/duplicate-decision`,
    { method: 'PUT', body: { decision } },
  )
}

/**
 * Dieselbe Entscheidung für ALLE Mitglieder der Gruppe — in EINEM Aufruf.
 *
 * KEINE Id-Liste im Body: Welche Fotos die Gruppe umfasst, bestimmt der Server aus dem Stern.
 * Eine vom Client gelieferte Menge wäre ein Massen-Schreibweg auf beliebige Fotos des Projekts.
 * `photoId` ist deshalb der ANKER der Gruppe, nicht ihr Inhalt.
 */
export function setDuplicateGroupDecision(
  projectId: number,
  photoId: number,
  decision: DuplicateDecision,
): Promise<DuplicateGroupOut> {
  return apiFetch<DuplicateGroupOut>(
    `/projects/${projectId}/duplicate-groups/${photoId}/decision`,
    { method: 'PUT', body: { decision } },
  )
}
