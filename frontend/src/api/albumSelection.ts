import { apiFetch } from './client'
import type { AlbumDecisionOut, AlbumSelectionOut } from './types'

/**
 * Die gemeinsame Endauswahl eines Projekts - EINE Abfrage für BEIDE Sichten.
 *
 * Es gibt weder `limit`/`offset` noch einen Sichtparameter: Arbeitssicht („nur die
 * Unterschiede") und Ergebnissicht („die ganze Endauswahl") sind zwei Filter über derselben
 * geladenen Antwort. Ein zweiter Abruf beim Umschalten ordnete die Ergebnissicht jedes Mal neu.
 */
export function getAlbumSelection(projectId: number): Promise<AlbumSelectionOut> {
  return apiFetch<AlbumSelectionOut>(`/projects/${projectId}/album-selection`)
}

/**
 * Setzt die GEMEINSAME Entscheidung des Projekts über ein Foto: gehört es in die Endauswahl oder
 * nicht.
 *
 * Sie ist keine Aussage eines Nutzers - anders als `setRating`. Der Body trägt ausschließlich
 * `included`; weder `photo_id` noch `user_id` gehen mit, und es gibt kein `DELETE`: „wieder
 * strittig werden" ist kein Zustand, den die Story kennt, ändern heißt den anderen Wert
 * schreiben.
 *
 * Die Antwort ist der PERSISTIERTE Zustand, nie ein Echo des Bodys (Auflage S5) - sie und nur sie
 * wird über `utils/albumSelection.ts::applyAlbumDecision` in den geladenen Stand fortgeschrieben.
 */
export function setAlbumDecision(photoId: number, included: boolean): Promise<AlbumDecisionOut> {
  return apiFetch<AlbumDecisionOut>(`/photos/${photoId}/album-decision`, {
    method: 'PUT',
    body: { included },
  })
}
