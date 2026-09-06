/**
 * Zaehlende Sperre des Hintergrund-Scrollens hinter einer Ueberlagerung
 * (specs/features/0321-dark-utility-register-ansichten.md, Etappe 1).
 *
 * WARUM MODULWEIT UND NICHT PRO KOMPONENTE: Die vorherige Loesung merkte sich den vorgefundenen
 * Wert von `document.body.style.overflow` im Effekt der jeweiligen Ueberlagerung. Bei zwei
 * gleichzeitig offenen Ueberlagerungen liest die zweite bereits 'hidden' als "vorherigen" Wert;
 * schliesst danach die ERSTE zuerst, schreibt sie ihr leeres '' zurueck und der Hintergrund
 * scrollt, obwohl noch eine Ueberlagerung offen ist. Ein gemeinsamer Zaehler ist der einzige Ort,
 * an dem sich diese Reihenfolge korrekt aufloesen laesst.
 *
 * IDEMPOTENZ DER FREIGABE: React ruft Effekt-Aufraeumungen im StrictMode doppelt auf
 * (`main.tsx` rendert unter StrictMode). Ohne eigenes Flag je Freigabe wuerde der zweite Aufruf
 * den Zaehler ein zweites Mal senken und die Sperre einer noch offenen Ueberlagerung aufheben.
 */

let lockCount = 0
let savedOverflow = ''

/**
 * Sperrt das Scrollen des `body` und liefert die zugehoerige Freigabe. Der Ausgangswert wird nur
 * beim Uebergang 0 -> 1 gesichert und nur beim Uebergang 1 -> 0 wiederhergestellt. Die
 * zurueckgegebene Freigabe ist idempotent.
 */
export function lockBodyScroll(): () => void {
  if (lockCount === 0) {
    savedOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
  }
  lockCount += 1

  let released = false
  return function release(): void {
    if (released) {
      return
    }
    released = true
    lockCount -= 1
    if (lockCount === 0) {
      document.body.style.overflow = savedOverflow
      savedOverflow = ''
    }
  }
}

/**
 * Testhygiene fuer den modulweiten Zustand - KEINE Produktions-API. Wird in `setupTests.ts` per
 * `afterEach` aufgerufen, damit weder der Zaehler noch ein gesetztes `overflow: hidden` in die
 * naechste Testdatei leckt.
 *
 * Die DOM-Pruefung ist noetig, weil `setupTests.ts` auch fuer die Testdatei mit der Umgebung
 * `node` (designSystem.contract.test.ts) laeuft - dort gibt es kein `document`.
 */
export function resetBodyScrollLock(): void {
  lockCount = 0
  savedOverflow = ''
  if (typeof document !== 'undefined') {
    document.body.style.overflow = ''
  }
}
