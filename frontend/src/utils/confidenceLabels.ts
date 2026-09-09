/**
 * Wortlaut und Kennzeichnung der Modell-Konfidenz (specs/features/0299-kategorie-konfidenz-
 * anzeigen.md, Akzeptanzkriterium 7).
 *
 * Eigene Datei statt eines Literals an den Anzeigestellen, weil der Hinweis an ZWEI Orten steht
 * (Bewertungsdetails und Statistikblock) und dort wortgleich sein muss - zwei Kopien liefen bei
 * der ersten Umformulierung auseinander, und dann staende an einer Stelle eine Zusage, die an der
 * anderen zurueckgenommen ist.
 */

/**
 * Die Kennzeichnung als Selbsteinschaetzung. Bewusst zwei Saetze: der erste sagt, woher die Zahl
 * kommt, der zweite nimmt die naheliegende Fehldeutung ausdruecklich zurueck.
 *
 * Die Woerter "Trefferquote", "Genauigkeit" und "korrekt" kommen hier - und an keiner anderen
 * Stelle der Konfidenz-Anzeige - vor: sie behaupteten eine GEMESSENE Groesse. Der Text steht
 * unmittelbar bei der Zahl, weil eine Prozentangabe ohne diese Einordnung als Trefferquote
 * gelesen wird.
 */
export const CONFIDENCE_EXPLANATION =
  'Modell-Selbsteinschätzung — die Angabe stammt vom Erkennungsmodell selbst und ist keine ' +
  'gemessene Trefferquote. Ein hoher Wert heißt, dass das Modell sich sicher war; er schließt ' +
  'einen Irrtum nicht aus.'

/**
 * Beschriftung des Info-Ausloesers an beiden Anzeigestellen - in den Bewertungsdetails als
 * SICHTBARER Text des `<summary>`, auf der Statistikseite als Ueberschrift des Info-Popovers und
 * Bestandteil seines zugaenglichen Namens.
 *
 * Bewusst ein sprechender Text und kein blosses "i" mit `aria-label`: eine Beschriftung, die
 * sichtbar und zugaenglich derselbe String ist, kann nicht auseinanderlaufen (WCAG 2.5.3) - und
 * "Modell-Selbsteinschaetzung" sagt bereits im geschlossenen Zustand das Wesentliche.
 */
export const CONFIDENCE_EXPLANATION_LABEL = 'Modell-Selbsteinschätzung'
