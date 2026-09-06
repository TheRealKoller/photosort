import '@testing-library/jest-dom/vitest'

import { afterEach } from 'vitest'

import { resetBodyScrollLock } from './lib/scrollLock'

// `lib/scrollLock.ts` haelt modulweiten Zustand (Zaehler + gesicherter overflow-Wert). Ohne diesen
// Aufruf leckt eine nicht freigegebene Sperre samt `overflow: hidden` in die naechste Testdatei.
// Testhygiene, KEINE Produktions-API (specs/features/0321-dark-utility-register-ansichten.md).
afterEach(() => {
  resetBodyScrollLock()
})

// specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md, UI/UX-Abschnitt:
// erster echter <dialog>-Einsatz im Produkt (Bestaetigungsdialog vor kostenpflichtiger Aktion,
// bewusst nativ statt eines neuen @radix-ui/react-dialog-Pakets). jsdom implementiert
// HTMLDialogElement.showModal()/close() nicht (wirft "not implemented" - verifiziert gegen die
// hier verwendete jsdom-Version) - globaler Test-Polyfill, der `open`/den `close`-Event
// hinreichend fuer JSDOM-Tests nachbildet, ohne echtes natives Rendering zu benoetigen. Analog zum
// bereits etablierten Muster projektweiter Test-Doubles fuer nicht von jsdom unterstuetzte APIs.
if (typeof HTMLDialogElement !== 'undefined') {
  HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
    this.setAttribute('open', '')
  }
  HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
    const wasOpen = this.hasAttribute('open')
    this.removeAttribute('open')
    if (wasOpen) {
      this.dispatchEvent(new Event('close'))
    }
  }
}
