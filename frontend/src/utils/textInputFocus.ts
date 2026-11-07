/**
 * Steht der Fokus in einem Textfeld? Seitenweite Tastenkuerzel (Einzelbild, Fallansicht der
 * Pruefung) schweigen dann - wer in ein Feld tippt, setzt kein Urteil und keine Bewertung.
 */
export function isTextInputFocused(): boolean {
  const active = document.activeElement
  if (active === null) {
    return false
  }
  if (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA') {
    return true
  }
  return (active as HTMLElement).isContentEditable
}
