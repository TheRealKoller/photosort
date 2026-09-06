import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'

import { Button } from './button'
import { Dialog } from './dialog'

/*
 * specs/features/0320-dark-utility-register.md, Teststrategie "jsdom-Fallstrick beim Dialog".
 *
 * jsdom implementiert WEDER `showModal()` (der Projekt-Polyfill in setupTests.ts setzt nur das
 * `open`-Attribut und feuert `close`) NOCH die native Fokusfalle NOCH die Esc-Behandlung des
 * <dialog>-Elements. Ein Test gegen das native Verhalten wuerde also den Polyfill pruefen, also
 * nichts. Deshalb sind Fokusfalle und Esc in eigenem JS implementiert - genau, damit die Zusage
 * ueberhaupt pruefbar ist.
 */
function TestDialog({ onClose = vi.fn(), open = true }: { onClose?: () => void; open?: boolean }) {
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Klassifizierung starten"
      description="Diese Aktion ist kostenpflichtig."
      icon="cog"
      actions={<Button type="button">Kostenpflichtig starten</Button>}
    >
      <p>Es werden 42 Fotos verarbeitet.</p>
    </Dialog>
  )
}

describe('Dialog', () => {
  it('renders nothing visible while closed', () => {
    render(<TestDialog open={false} />)

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('links the title via aria-labelledby and the text via aria-describedby', () => {
    render(<TestDialog />)

    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(dialog).toHaveAccessibleName('Klassifizierung starten')
    expect(dialog).toHaveAccessibleDescription('Diese Aktion ist kostenpflichtig.')
  })

  // Verbindlich (UI/UX-Abschnitt der Spec): der Erstfokus liegt auf der AM WENIGSTEN
  // EINGREIFENDEN Schaltflaeche, nie auf einer bestaetigenden oder loeschenden Aktion. Der erste
  // Konsument ist ein Dialog vor einer kostenpflichtigen Aktion.
  it('puts the initial focus on the least destructive action', () => {
    render(<TestDialog />)

    expect(screen.getByRole('button', { name: 'Abbrechen' })).toHaveFocus()
  })

  it('closes on Escape', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(<TestDialog onClose={onClose} />)

    await user.keyboard('{Escape}')

    expect(onClose).toHaveBeenCalledTimes(1)
  })

  // Entschieden und getestet statt undefiniert (Spec, Abschnitt "Entscheidungen"): der erste
  // Konsument ist ein Dialog vor einer kostenpflichtigen Aktion - ein versehentliches Verwerfen
  // durch einen Klick daneben waere hier teuer.
  it('does not close on a backdrop click', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(<TestDialog onClose={onClose} />)

    await user.click(screen.getByRole('dialog'))

    expect(onClose).not.toHaveBeenCalled()
  })

  it('traps the focus: Tab from the last element wraps to the first', async () => {
    const user = userEvent.setup()
    render(<TestDialog />)

    const cancel = screen.getByRole('button', { name: 'Abbrechen' })
    const confirm = screen.getByRole('button', { name: 'Kostenpflichtig starten' })

    confirm.focus()
    await user.tab()

    expect(cancel).toHaveFocus()
  })

  it('traps the focus: Shift+Tab from the first element wraps to the last', async () => {
    const user = userEvent.setup()
    render(<TestDialog />)

    const cancel = screen.getByRole('button', { name: 'Abbrechen' })
    const confirm = screen.getByRole('button', { name: 'Kostenpflichtig starten' })

    cancel.focus()
    await user.tab({ shift: true })

    expect(confirm).toHaveFocus()
  })

  /*
   * Copilot-Review-Fund (PR #322): Der Ausreisserfall "Fokus liegt ausserhalb des Dialogs" war nur
   * fuer Shift+Tab behandelt - vorwaerts traf kein Zweig zu und der Fokus wanderte aus dem Modal
   * heraus. Die beiden Zweige sind jetzt symmetrisch.
   *
   * Das wiegt hier schwerer als bei einer Bibliothekskomponente: die Falle ist gerade DESHALB von
   * Hand gebaut, weil jsdom keine native Einsperrung mitbringt - es gibt also nichts, was den
   * Fehler auffinge. Die beiden Richtungstests darueber decken den Regelfall ab, dieser den
   * Ausreisser; deshalb wird der Fokus hier bewusst aus dem Dialog GENOMMEN (blur), bevor die
   * Taste am Dialog ankommt.
   */
  it.each([
    [false, 'Abbrechen'],
    [true, 'Kostenpflichtig starten'],
  ])('pulls stray focus back into the dialog (shift=%s)', (shift, expectedLabel) => {
    render(<TestDialog />)

    const dialog = screen.getByRole('dialog')
    ;(document.activeElement as HTMLElement | null)?.blur()
    expect(dialog.contains(document.activeElement)).toBe(false)

    fireEvent.keyDown(dialog, { key: 'Tab', shiftKey: shift })

    expect(screen.getByRole('button', { name: expectedLabel })).toHaveFocus()
  })

  /*
   * Copilot-Review-Fund (PR #322), Haertung: Die Schliessanfrage des Browsers ist NICHT als
   * Standardaktion des `keydown` definiert und laesst sich dort nicht zuverlaessig per
   * `preventDefault()` unterdruecken - der dafuer vorgesehene Haken ist `cancel`. Beide Pfade sind
   * jetzt angeschlossen; dieser Test haelt fest, dass sie zusammen trotzdem GENAU EINMAL
   * schliessen. In jsdom feuert `cancel` nie von selbst, der Doppelaufruf waere also im Browser
   * aufgetreten und hier unsichtbar geblieben - deshalb wird er hier von Hand ausgeloest.
   */
  it('closes exactly once when Escape and the native cancel event both arrive', () => {
    const onClose = vi.fn()
    render(<TestDialog onClose={onClose} />)

    const dialog = screen.getByRole('dialog')
    fireEvent.keyDown(dialog, { key: 'Escape' })
    fireEvent(dialog, new Event('cancel', { bubbles: false, cancelable: true }))

    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('closes on the native cancel event alone', () => {
    const onClose = vi.fn()
    render(<TestDialog onClose={onClose} />)

    fireEvent(screen.getByRole('dialog'), new Event('cancel', { bubbles: false, cancelable: true }))

    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('still closes on a second Escape when the caller ignored the first', () => {
    // Gegenprobe zur Richtung der Esc/cancel-Absprache: Esc traegt immer, auch wenn ein Aufrufer
    // das erste bewusst ignoriert (z.B. um vor dem Verwerfen von Eingaben nachzufragen). Ein
    // dauerhafter Riegel haette das zweite Esc verschluckt.
    const onClose = vi.fn()
    render(<TestDialog onClose={onClose} />)

    const dialog = screen.getByRole('dialog')
    fireEvent.keyDown(dialog, { key: 'Escape' })
    fireEvent.keyDown(dialog, { key: 'Escape' })

    expect(onClose).toHaveBeenCalledTimes(2)
  })

  it('returns the focus to the triggering element after closing', async () => {
    const user = userEvent.setup()

    function Host() {
      const [open, setOpen] = useState(false)
      return (
        <>
          <Button type="button" onClick={() => setOpen(true)}>
            Öffnen
          </Button>
          <Dialog open={open} onClose={() => setOpen(false)} title="Titel">
            <p>Inhalt</p>
          </Dialog>
        </>
      )
    }

    render(<Host />)
    const trigger = screen.getByRole('button', { name: 'Öffnen' })
    await user.click(trigger)
    expect(screen.getByRole('button', { name: 'Abbrechen' })).toHaveFocus()

    await user.click(screen.getByRole('button', { name: 'Abbrechen' }))

    expect(trigger).toHaveFocus()
  })

  it('keeps the background from scrolling while open', () => {
    const { unmount } = render(<TestDialog />)
    expect(document.body.style.overflow).toBe('hidden')

    unmount()
    expect(document.body.style.overflow).toBe('')
  })

  /*
   * specs/features/0321-dark-utility-register-ansichten.md, Etappe 1: Die Scroll-Sperre traegt
   * jetzt auch bei mehreren gleichzeitig offenen Ueberlagerungen. Zuvor merkte sich jeder Dialog
   * den vorgefundenen `overflow`-Wert selbst - der zweite las bereits 'hidden' als "vorherigen"
   * Wert, und wenn der ERSTE zuerst schloss, schrieb er sein leeres '' zurueck.
   *
   * Bewusst ueber tatsaechlich gerendertes React statt ueber die Modul-API von `lib/scrollLock`
   * (die dort eigene Unit-Tests hat): nur so ist belegt, dass `dialog.tsx` den Zaehler wirklich
   * benutzt.
   */
  it.each([
    ['in Anlegereihenfolge', true],
    ['in umgekehrter Reihenfolge', false],
  ])('keeps the background locked while a second dialog is still open (%s)', (_name, closeFirstFirst) => {
    const first = render(<TestDialog />)
    const second = render(<TestDialog />)
    expect(document.body.style.overflow).toBe('hidden')

    const [closedFirst, closedLast] = closeFirstFirst ? [first, second] : [second, first]

    closedFirst.unmount()
    expect(document.body.style.overflow).toBe('hidden')

    closedLast.unmount()
    expect(document.body.style.overflow).toBe('')
  })
})
