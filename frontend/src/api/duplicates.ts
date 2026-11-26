import { apiFetch } from './client'
import type { DuplicateDecision, DuplicateGroupIndexOut, DuplicateGroupOut } from './types'

/**
 * Wie viele Duplikat-Gruppen das Projekt hat und wo der Durchgang beginnt.
 *
 * Grundlage der beiden Einstiege — aus dem Ausschuss-Schritt und aus der nach Vorschlägen
 * gefilterten Fotoliste. `total === 0` heißt „es gibt nichts zu vergleichen"; der Einstieg wird
 * dann nicht gerendert, damit er nicht auf eine leere Ansicht führt.
 */
export function getDuplicateGroupIndex(projectId: number): Promise<DuplicateGroupIndexOut> {
  return apiFetch('/projects/{project_id}/duplicate-groups', {
    pathParams: { project_id: projectId },
  })
}

/**
 * Eine Duplikat-Gruppe, erreichbar über IRGENDEIN Mitglied.
 *
 * Die Gruppe ist abgeleitet und hat keine eigene Id: Der Server bildet sie zur
 * Lesezeit als Stern über `duplicate_of`. Jedes Mitglied — der Gewinner eingeschlossen — führt
 * deshalb zur selben Antwort.
 *
 * `404` heißt „zu dieser Id gibt es keine Gruppe" und deckt vier ununterscheidbare Fälle:
 * unbekanntes Foto, fremdes Projekt, Foto ohne Duplikat und Vorschlag wegen geringer
 * Bildqualität. Die Ansicht zeigt darauf ihren LEEREN Zustand, nicht den Fehler-Alert.
 */
export function getDuplicateGroup(projectId: number, photoId: number): Promise<DuplicateGroupOut> {
  return apiFetch('/projects/{project_id}/duplicate-groups/{photo_id}', {
    pathParams: { project_id: projectId, photo_id: photoId },
  })
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
  return apiFetch('/projects/{project_id}/photos/{photo_id}/duplicate-decision', {
    method: 'PUT',
    pathParams: { project_id: projectId, photo_id: photoId },
    body: { decision },
  })
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
  return apiFetch('/projects/{project_id}/duplicate-groups/{photo_id}/decision', {
    method: 'PUT',
    pathParams: { project_id: projectId, photo_id: photoId },
    body: { decision },
  })
}

/**
 * Schließt EINE Gruppe ab: Jedes Mitglied mit offenem Vorschlag bekommt „Ausschuss"
 * festgeschrieben. Kein angezeigter Zustand ändert sich — ein offener Vorschlag zeigt ihn schon.
 *
 * OHNE KÖRPER: Weder die Menge noch der Wert kommen von hier. Eine Id-Liste wäre ein
 * Massen-Schreibweg auf beliebige Fotos, ein Wert ein Massen-„behalten".
 */
export function confirmDuplicateGroup(
  projectId: number,
  photoId: number,
): Promise<DuplicateGroupOut> {
  return apiFetch('/projects/{project_id}/duplicate-groups/{photo_id}/confirm', {
    method: 'POST',
    pathParams: { project_id: projectId, photo_id: photoId },
  })
}
