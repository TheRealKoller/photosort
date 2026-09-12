import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { MotifAssessmentMarker } from './MotifAssessmentMarker'

/**
 * specs/features/0427-motive-mit-staerke.md, UI/UX-Abschnitt „Kachel und Raster": der EINZIGE
 * Motiv-Marker der Kachel. Er sagt „noch nicht klassifiziert" - lokale Grundlage und Ausschluss
 * stehen im Info-Popover und in der Einzelansicht, nicht als weitere Ecken-Glyphen.
 */
describe('MotifAssessmentMarker', () => {
  it('is an image role with a spoken label and a hidden glyph', () => {
    render(<MotifAssessmentMarker />)

    const marker = screen.getByRole('img', { name: 'Motive noch nicht bestimmt' })
    expect(marker).toBeInTheDocument()
    // Das Zeichen selbst ist `aria-hidden` - es ersetzt kein Label, es begleitet es.
    expect(marker.querySelector('[aria-hidden="true"]')?.textContent).toBe('○')
  })

  it('is not interactive and spans no tap target', () => {
    /* Ein Marker ohne Handler darf keine 44px-Fläche aufspannen: sie läge über der Bildfläche der
     * Kachel und schluckte den Klick, der zur Einzelbildansicht führt. */
    render(<MotifAssessmentMarker />)

    const marker = screen.getByRole('img', { name: 'Motive noch nicht bestimmt' })
    expect(marker.tagName).toBe('SPAN')
    expect(marker.className).not.toContain('tap-target')
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('accepts an additional class without losing its own', () => {
    render(<MotifAssessmentMarker className="ml-1" />)

    const marker = screen.getByRole('img', { name: 'Motive noch nicht bestimmt' })
    expect(marker.className).toContain('ml-1')
    // Die eigene Groesse bleibt: `cn` ergaenzt, es ersetzt nicht. Bewusst nicht die Rundform
    // geprueft - der Design-Vertrag zaehlt deren Fundstellen im ganzen Baum, Testdateien
    // eingeschlossen, und eine zweite hier waere dort ein Befund.
    expect(marker.className).toContain('size-6')
  })
})
