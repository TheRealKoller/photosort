/**
 * DIE EINE Begriffsquelle für die Haltung zu einem Foto in Album-Entwurf UND Endauswahl.
 *
 * Jedes der drei Wörter steht im Quellbaum genau einmal als String-Literal, nämlich hier
 * (`albumStateLabels.test.ts`). Der Bildbestand (Raster, Einzelbild, Bewertungsleiste) benennt
 * dieselben Bewertungszeilen weiter mit `ratingLabels.ts::RATING_STATUS_LABELS`.
 *
 * - `proposal`: Teil des Vorschlags und nicht angefasst.
 * - `taken`: von mir aufgenommen.
 * - `struck`: von mir gestrichen.
 */
export type AlbumState = 'proposal' | 'taken' | 'struck'

export const ALBUM_STATE_LABELS: Record<AlbumState, string> = {
  proposal: 'Vorschlag',
  taken: 'Aufgenommen',
  struck: 'Gestrichen',
}

/** Die Haltung „unberührt und nicht vorgeschlagen" in der Endauswahl: sichtbar „–", das hier ist
 * ihr zugänglicher Name. */
export const NOT_IN_DRAFT_LABEL = 'Nicht im Entwurf'
