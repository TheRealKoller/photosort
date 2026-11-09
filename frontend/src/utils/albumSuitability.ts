// Die Beschriftungen der Albumtauglichkeit an EINER Stelle - die genaue Stufe und der Satz für
// „kein Modellurteil". Kachel und Bewertungsdetails lesen beide von hier; zwei Literale liefen
// auseinander.

/** Die Skala ist fünfstufig (backend `album_suitability.py`). */
export const ALBUM_SUITABILITY_MAX_LEVEL = 5

/**
 * Der Satz für ein Foto ohne zählende Modellstufe - auf der Kachel an der Stelle der Stufenzeile
 * und in den Bewertungsdetails an der Stelle der Stufe.
 *
 * Ein SATZ und kein Platzhalterzeichen: „—" oder ein Meter-Glyph (`○○○`) hieße „schlechteste
 * Stufe" statt „nicht beurteilt". „Noch nie eingestuft" und „Modellaufruf fehlgeschlagen"
 * tragen bewusst denselben Satz - beide Male hilft derselbe nächste Klassifizierungslauf.
 * „bewertet" bleibt der menschlichen Bewertung vorbehalten.
 */
export const ALBUM_SUITABILITY_NOT_RATED_TEXT = 'Noch nicht eingestuft'

/**
 * Die Zuschreibung, die vor JEDER angezeigten Begründung im selben Träger steht. Ohne sie wird eine
 * per Prompt-Injection erzeugte Zeile („Sitzung abgelaufen, bitte …") als Aussage von PhotoSort
 * gelesen statt als Aussage des Modells.
 */
export const REASON_ATTRIBUTION = 'Begründung des Modells'

/**
 * Die Herkunftszeile an der Stelle der Begründung, wenn die zählende Stufe aus Eyes Auswertung
 * stammt: „Eingestuft von Eye". Ein nacktes „Eye" ließe offen, was Eye behauptet - gerade für
 * einen Screenreader. Wörter, nie ein Badge, eine Farbe oder ein Symbol.
 */
export const ALBUM_SUITABILITY_ORIGIN_LABEL = 'Eingestuft von'
export const ALBUM_SUITABILITY_EYE_ORIGIN_TEXT = 'Eye'

/**
 * Die genaue Modellstufe, ausgeschrieben („Stufe 4 von 5"). Sie erscheint NUR in den
 * Bewertungsdetails, nicht neben der Dreistufigkeit auf der Kachel: zwei Skalen nebeneinander
 * wären zwei Zahlen für eine Aussage.
 */
export function formatAlbumSuitabilityLevel(level: number): string {
  return `Stufe ${level} von ${ALBUM_SUITABILITY_MAX_LEVEL}`
}
