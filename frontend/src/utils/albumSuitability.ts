// Die Beschriftungen der Albumtauglichkeit an EINER Stelle - die genaue Stufe und der Satz für
// „kein Modellurteil". Kachel und Bewertungsdetails lesen beide von hier; zwei Literale liefen
// auseinander.

/** Die Skala ist fünfstufig (backend `album_suitability.py`). */
export const ALBUM_SUITABILITY_MAX_LEVEL = 5

/**
 * Der Satz für ein Foto ohne Modellurteil - auf der Kachel an der Stelle der Stufenzeile und in
 * den Bewertungsdetails an der Stelle der Stufe.
 *
 * Ein SATZ und kein Platzhalterzeichen: „—" oder ein Meter-Glyph (`○○○`) hieße „schlechteste
 * Stufe" statt „nicht beurteilt". „Noch nie klassifiziert" und „Modellaufruf fehlgeschlagen"
 * tragen bewusst denselben Satz - beide Male hilft derselbe nächste Klassifizierungslauf.
 */
export const ALBUM_SUITABILITY_NOT_RATED_TEXT = 'Noch nicht bewertet'

/**
 * Die genaue Modellstufe, ausgeschrieben („Stufe 4 von 5"). Sie erscheint NUR in den
 * Bewertungsdetails, nicht neben der Dreistufigkeit auf der Kachel: zwei Skalen nebeneinander
 * wären zwei Zahlen für eine Aussage.
 */
export function formatAlbumSuitabilityLevel(level: number): string {
  return `Stufe ${level} von ${ALBUM_SUITABILITY_MAX_LEVEL}`
}
