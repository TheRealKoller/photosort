import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Icon, ICON_NAMES } from './icon'

/*
 * specs/features/0320-dark-utility-register.md, Teststrategie "Komponentenebene, semantisch".
 * Der Zwoelfer-Satz des Boards ist die einzige Symbolquelle des Produkts; diese Datei ist die
 * einzige Stelle, an der `lucide-react` ueberhaupt importiert werden darf (statisch erzwungen in
 * src/designSystem.contract.test.ts).
 */
describe('Icon', () => {
  it('kennt genau die zwoelf Symbole des Boards', () => {
    expect([...ICON_NAMES].sort()).toEqual(
      [
        'book',
        'camera',
        'check',
        'chevron-down',
        'cog',
        'folder',
        'image',
        'info',
        'search',
        'star',
        'tag',
        'x-circle',
      ].sort()
    )
  })

  it.each(ICON_NAMES)('rendert fuer %s ein <svg> mit data-icon', (name) => {
    const { container } = render(<Icon name={name} />)

    const svg = container.querySelector('svg')
    expect(svg).not.toBeNull()
    expect(svg).toHaveAttribute('data-icon', name)
  })

  it('ist im Regelfall dekorativ - ein Symbol ersetzt nie ein Label, es begleitet es', () => {
    const { container } = render(<Icon name="star" />)

    const svg = container.querySelector('svg')!
    expect(svg).toHaveAttribute('aria-hidden', 'true')
    expect(svg).toHaveAttribute('focusable', 'false')
  })

  it('wird mit title zum eigenstaendigen Bild (role="img") fuer den seltenen Alleinstand', () => {
    render(<Icon name="folder" title="Ordner" />)

    const image = screen.getByRole('img', { name: 'Ordner' })
    expect(image).toHaveAttribute('data-icon', 'folder')
    expect(image).not.toHaveAttribute('aria-hidden')
  })

  it('nutzt die Board-Standardgroesse 16 und laesst sie ueberschreiben', () => {
    const { container: standard } = render(<Icon name="check" />)
    expect(standard.querySelector('svg')).toHaveAttribute('width', '16')

    const { container: large } = render(<Icon name="check" size={24} />)
    expect(large.querySelector('svg')).toHaveAttribute('width', '24')
  })

  it('setzt die Board-Strichstaerke 2 zentral', () => {
    const { container } = render(<Icon name="info" />)
    expect(container.querySelector('svg')).toHaveAttribute('stroke-width', '2')
  })

  // Zwei Sonderfaelle aus ADR 0055 Punkt 7b, beide als eigener Test statt als Kommentar:
  it('rendert name="image" aus lucide-react, nicht das DOM-Global Image', () => {
    // `Image` kollidiert mit dem globalen Konstruktor - der Import muss umbenannt werden. Ein
    // versehentlich verwendetes DOM-Global waere zur Laufzeit kein <svg>.
    const { container } = render(<Icon name="image" />)

    const svg = container.querySelector('svg')
    expect(svg).not.toBeNull()
    expect(svg!.querySelectorAll('rect, path, circle, line').length).toBeGreaterThan(0)
  })

  it('rendert name="x-circle" gegen den tatsaechlich installierten Lucide-Exportnamen', () => {
    // Lucide hat das Symbol zu `circle-x` umbenannt; `XCircle` besteht nur noch als Alt-Alias.
    // Dieser Test ist der von ADR 0055 Punkt 7b geforderte Nachweis gegen die INSTALLIERTE
    // Version, statt zu raten.
    const { container } = render(<Icon name="x-circle" />)

    const svg = container.querySelector('svg')
    expect(svg).not.toBeNull()
    expect(svg!.querySelector('circle')).not.toBeNull()
  })
})
