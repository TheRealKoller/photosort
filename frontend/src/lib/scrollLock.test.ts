import { afterEach, describe, expect, it } from 'vitest'

import { lockBodyScroll, resetBodyScrollLock } from './scrollLock'

/*
 * specs/features/0321-dark-utility-register-ansichten.md, Etappe 1a.
 *
 * Der behobene Fehler: `ui/dialog.tsx` merkte sich in seinem Effekt den VORGEFUNDENEN Wert von
 * `document.body.style.overflow`. Bei zwei gleichzeitig offenen Dialogen liest der zweite bereits
 * 'hidden' als "vorherigen" Wert; schliesst danach der ERSTE zuerst, schreibt er sein leeres ''
 * zurueck und der Hintergrund scrollt, obwohl noch ein Dialog offen ist. Der modulweite Zaehler
 * hier ist der einzige Ort, an dem sich das reproduzieren laesst - die Reihenfolge- und
 * Doppelaufruf-Semantik ist echte Logik und wird deshalb vollstaendig abgedeckt.
 */
afterEach(() => {
  resetBodyScrollLock()
})

describe('scrollLock', () => {
  it('sperrt beim Uebergang 0 -> 1 und sichert den Ausgangswert', () => {
    expect(document.body.style.overflow).toBe('')

    const release = lockBodyScroll()

    expect(document.body.style.overflow).toBe('hidden')

    release()

    expect(document.body.style.overflow).toBe('')
  })

  it('haelt die Sperre bis zur letzten Freigabe (Anlegereihenfolge)', () => {
    const releaseA = lockBodyScroll()
    const releaseB = lockBodyScroll()

    releaseA()
    expect(document.body.style.overflow).toBe('hidden')

    releaseB()
    expect(document.body.style.overflow).toBe('')
  })

  // Der ohne Zaehler brechende Fall und der Grund des ganzen Umbaus: umgekehrte Schliessreihenfolge.
  it('haelt die Sperre auch bei umgekehrter Freigabereihenfolge', () => {
    const releaseA = lockBodyScroll()
    const releaseB = lockBodyScroll()

    releaseB()
    expect(document.body.style.overflow).toBe('hidden')

    releaseA()
    expect(document.body.style.overflow).toBe('')
  })

  it('stellt einen vorbelegten Ausgangswert wieder her, nicht den leeren String', () => {
    document.body.style.overflow = 'scroll'

    const releaseA = lockBodyScroll()
    const releaseB = lockBodyScroll()
    expect(document.body.style.overflow).toBe('hidden')

    releaseA()
    releaseB()

    expect(document.body.style.overflow).toBe('scroll')
  })

  /*
   * React ruft Effekt-Aufraeumungen im StrictMode doppelt auf (`main.tsx` rendert unter
   * StrictMode); im Test greift das nicht, der Doppelaufruf wird deshalb hier direkt provoziert.
   * Der Nachweis braucht BEIDE Richtungen: ohne (a) bestuende der Test auch bei einem nackten
   * `count--`.
   */
  it('zaehlt eine doppelt aufgerufene Freigabe nur einmal herunter', () => {
    const releaseA = lockBodyScroll()
    const releaseB = lockBodyScroll()

    releaseA()
    releaseA()
    expect(document.body.style.overflow).toBe('hidden')

    releaseB()
    expect(document.body.style.overflow).toBe('')
  })

  it('setzt mit resetBodyScrollLock Zaehler, gesicherten Wert und DOM-Zustand zurueck', () => {
    document.body.style.overflow = 'scroll'
    lockBodyScroll()
    lockBodyScroll()

    resetBodyScrollLock()

    // Ohne die dritte Zusage (DOM abraeumen) leckt 'hidden' in die naechste Testdatei.
    expect(document.body.style.overflow).toBe('')

    // Eine danach angelegte Sperre sichert wieder frisch - nicht den alten 'scroll'-Wert.
    const release = lockBodyScroll()
    expect(document.body.style.overflow).toBe('hidden')
    release()
    expect(document.body.style.overflow).toBe('')
  })
})
