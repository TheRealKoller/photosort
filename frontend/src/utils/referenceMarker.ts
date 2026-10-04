/**
 * Die Stelle der Bezugsmarke („Wird ersetzt") in einer geladenen Reihe von Alternativen
 * (Spec 0569, Auflage 11): allein `reference_index − offset`, und nur, wenn das eine Ganzzahl in
 * `[0, length]` ist. Sonst `null` - ohne Fehler und ohne geratene Ersatzposition. Der Wert
 * `length` ist inklusiv: die Marke steht dann hinter dem letzten Bild.
 *
 * Die Zeit rechnet das Frontend nie nach - die Stelle liefert der Server.
 */
export function referenceMarkerIndex(
  referenceIndex: number | null,
  offset: number,
  length: number,
): number | null {
  if (referenceIndex === null) {
    return null
  }
  const position = referenceIndex - offset
  return Number.isInteger(position) && position >= 0 && position <= length ? position : null
}
