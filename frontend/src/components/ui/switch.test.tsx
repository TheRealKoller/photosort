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

  it('carries the board geometry and spans its tap target to at least 44px', () => {
    render(<Switch checked={false} onCheckedChange={vi.fn()} aria-label="Testschalter" />)

    // Auf das neue Board-Mass umgezogen (specs/features/0320-dark-utility-register.md): sichtbar
    // 48 x 24px, die 44px-Trefferflaeche kommt ueber die Aufspannung (`tap-target`) statt ueber
    // die sichtbare Hoehe. Nur die kurze Achse wird aufgespannt - 48px Breite liegen bereits
    // ueber dem Minimum. Whitebox-Nachweis ueber die Klassen statt eines jsdom-Layout-Messwerts:
    // jsdom hat keine Layout-Engine, getBoundingClientRect() liefert 0.
    const className = screen.getByRole('switch', { name: 'Testschalter' }).className
    expect(className).toMatch(/(^|\s)h-6(\s|$)/)
    expect(className).toMatch(/(^|\s)w-12(\s|$)/)
    expect(className).toMatch(/(^|\s)tap-target(\s|$)/)
  })

  // Der Zustand wird zusaetzlich ueber die KNAUFPOSITION getragen, nicht nur ueber die Farbe -
  // sonst waere "ein"/"aus" ohne Farbwahrnehmung nicht unterscheidbar.
  it('carries the state through the knob position, not through colour alone', () => {
    const { rerender } = render(
      <Switch checked={false} onCheckedChange={vi.fn()} aria-label="Testschalter" />
    )
    const knob = () => screen.getByRole('switch', { name: 'Testschalter' }).querySelector('span')!
    const off = knob().className

    rerender(<Switch checked onCheckedChange={vi.fn()} aria-label="Testschalter" />)

    expect(knob().className).not.toBe(off)
    expect(knob().className).toMatch(/translate-x-6/)
  })
})
