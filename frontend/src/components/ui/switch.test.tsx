import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { Switch } from './switch'

// specs/features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md: erstes eigenes (nicht-
// Radix) Toggle-Widget im Projekt - kein bestehendes @radix-ui/react-switch in package.json,
// natives <button role="switch" aria-checked> statt einer neuen Abhaengigkeit (Minimalismus-
// Prinzip, ADR 0006). Selektor-Stabilitaetsregel: ueber role/aria-checked geprueft, nicht
// CSS-Klassen (specs/architecture/0002-testkonzept.md).
describe('Switch', () => {
  it('exposes the native switch role with aria-checked reflecting the checked prop', () => {
    render(<Switch checked={false} onCheckedChange={vi.fn()} aria-label="Testschalter" />)

    const toggle = screen.getByRole('switch', { name: 'Testschalter' })
    expect(toggle).toHaveAttribute('aria-checked', 'false')
  })

  it('reflects checked=true via aria-checked', () => {
    render(<Switch checked={true} onCheckedChange={vi.fn()} aria-label="Testschalter" />)

    expect(screen.getByRole('switch', { name: 'Testschalter' })).toHaveAttribute(
      'aria-checked',
      'true'
    )
  })

  it('calls onCheckedChange with the inverted value on click', async () => {
    const user = userEvent.setup()
    const onCheckedChange = vi.fn()
    render(<Switch checked={false} onCheckedChange={onCheckedChange} aria-label="Testschalter" />)

    await user.click(screen.getByRole('switch', { name: 'Testschalter' }))

    expect(onCheckedChange).toHaveBeenCalledWith(true)
  })

  it('does not call onCheckedChange when disabled', async () => {
    const user = userEvent.setup()
    const onCheckedChange = vi.fn()
    render(
      <Switch
        checked={false}
        onCheckedChange={onCheckedChange}
        disabled
        aria-label="Testschalter"
      />
    )

    await user.click(screen.getByRole('switch', { name: 'Testschalter' }))

    expect(onCheckedChange).not.toHaveBeenCalled()
  })

  it('never lets a stray aria-checked/type prop override the controlled switch semantics (Copilot-Review-Fund PR #181)', () => {
    // SwitchProps omits nur onClick/role aus ComponentProps<'button'>, nicht type/aria-checked -
    // {...props} muss deshalb VOR den invarianten Attributen gespreadet werden, sonst koennte ein
    // Aufrufer versehentlich die kontrollierte Semantik ueberschreiben (aktuell kein Live-Bug in
    // ProjectSettingsPage.tsx, aber ein Robustheits-/Typsicherheitsproblem).
    render(
      <Switch
        checked={true}
        onCheckedChange={vi.fn()}
        aria-label="Testschalter"
        type="submit"
        aria-checked="false"
      />
    )

    const toggle = screen.getByRole('switch', { name: 'Testschalter' })
    expect(toggle).toHaveAttribute('type', 'button')
    expect(toggle).toHaveAttribute('aria-checked', 'true')
  })

  it('is at least 44px tall to satisfy the touch-target minimum', () => {
    render(<Switch checked={false} onCheckedChange={vi.fn()} aria-label="Testschalter" />)

    // Whitebox-Nachweis ueber die Tailwind-Hoehenklasse (h-11 = 44px) statt eines jsdom-
    // Layout-Messwerts (jsdom rendert kein echtes Boxmodell) - konsistent mit der bereits
    // etablierten Vorgehensweise fuer aehnliche Touch-Ziel-Nachweise im Projekt.
    expect(screen.getByRole('switch', { name: 'Testschalter' }).className).toContain('h-11')
  })
})
