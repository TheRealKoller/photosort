import { render, screen } from '@testing-library/react'
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
})
