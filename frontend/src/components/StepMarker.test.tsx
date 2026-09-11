import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { STEP_MARKER_AUSPRAEGUNGEN, StepMarker, type StepMarkerAuspraegung } from './StepMarker'

/*
 * specs/features/0387-schrittleiste-fortschritt.md, Teststrategie "Komponente (jsdom):
 * StepMarker". Der Baustein ist rein praesentational - er kennt weder Routing noch Zustand und
 * traegt keinen eigenen zugaenglichen Namen; der kommt vom umschliessenden Bedienelement in
 * Stepper.tsx.
 *
 * KEINE CSS-ASSERTIONS (Projektkonvention): dass die vier Auspraegungen unterschiedlich AUSSEHEN,
 * bindet der Design-Vertrag. Hier steht die Zusage, dass sie ohne Rueckgriff auf Farbe
 * unterscheidbar sind - ueber `data-step-state` und die Glyphe.
 */

function marker(auspraegung: StepMarkerAuspraegung, options: { istErledigt?: boolean } = {}) {
  const { container } = render(
    <StepMarker auspraegung={auspraegung} nummer={3} istErledigt={options.istErledigt} />,
  )
  const root = container.querySelector('[data-step-state]')
  expect(root, 'Marker ohne data-step-state').not.toBeNull()
  return { root: root as HTMLElement, container }
}

describe('StepMarker', () => {
  /* Ueber die exportierte Laufzeitliste statt ueber eine hier abgetippte - eine fuenfte
   * Auspraegung kann dadurch nicht ungeprueft hinzukommen (Muster wie ICON_NAMES). */
  it('fuehrt genau die vier Auspraegungen des Entwurfs', () => {
    expect([...STEP_MARKER_AUSPRAEGUNGEN]).toEqual([
      'erledigt',
      'aktuell',
      'ausstehend',
      'blockiert',
    ])
  })

  it.each([
    { auspraegung: 'erledigt' as const, glyphe: 'haken' },
    { auspraegung: 'aktuell' as const, glyphe: 'nummer' },
    { auspraegung: 'ausstehend' as const, glyphe: 'nummer' },
    { auspraegung: 'blockiert' as const, glyphe: 'schloss' },
  ])('zeigt fuer $auspraegung genau eine Glyphe: $glyphe', ({ auspraegung, glyphe }) => {
    const { root, container } = marker(auspraegung)

    expect(root).toHaveAttribute('data-step-state', auspraegung)
    // GENAU EINE Glyphe - "Haken UND Nummer" waere sonst gruen.
    const glyphen = container.querySelectorAll('[data-glyph]')
    expect(glyphen).toHaveLength(1)
    expect(glyphen[0]).toHaveAttribute('data-glyph', glyphe)
  })

  /*
   * HAKEN VOR SCHLOSS (Edge Case 2 der Spec): Zustandsbenennung und Glyphenwahl folgen ZWEI
   * verschiedenen, je unveraenderten Rangfolgen. Ein erledigter Schritt, der inzwischen wieder
   * gesperrt ist, heisst "blockiert" und zeigt trotzdem den Haken.
   */
  it.each(['aktuell' as const, 'blockiert' as const])(
    'zeigt bei %s trotzdem den Haken, sobald der Schritt erledigt ist',
    (auspraegung) => {
      const { root, container } = marker(auspraegung, { istErledigt: true })

      expect(root).toHaveAttribute('data-step-state', auspraegung)
      expect(container.querySelectorAll('[data-glyph]')).toHaveLength(1)
      expect(container.querySelector('[data-glyph]')).toHaveAttribute('data-glyph', 'haken')
    },
  )

  it('zeigt die Schrittnummer, wo die Nummer die Glyphe ist', () => {
    const { container } = render(<StepMarker auspraegung="ausstehend" nummer={4} />)

    expect(container.querySelector('[data-glyph="nummer"]')).toHaveTextContent('4')
  })

  /* Die vier Auspraegungen liefern VIER verschiedene Werte - das ist "ohne Rueckgriff auf Farbe
   * allein unterscheidbar" in seiner pruefbaren Form, und zwar ueber alle vier statt wie bisher
   * ueber drei. */
  it('unterscheidet alle vier Auspraegungen ohne Farbe', () => {
    const werte = STEP_MARKER_AUSPRAEGUNGEN.map((auspraegung) =>
      marker(auspraegung).root.getAttribute('data-step-state'),
    )

    expect(new Set(werte).size).toBe(STEP_MARKER_AUSPRAEGUNGEN.length)
  })

  /* Der Marker traegt KEINEN eigenen zugaenglichen Namen: der kommt vollstaendig vom
   * umschliessenden Bedienelement. Ein zweiter Name dort waere eine Dopplung im Screenreader. */
  it.each([...STEP_MARKER_AUSPRAEGUNGEN])(
    'bleibt bei %s ohne eigenen zugaenglichen Namen',
    (auspraegung) => {
      const { root, container } = marker(auspraegung)

      expect(root).toHaveAccessibleName('')
      expect(container.querySelector('[data-glyph]')).toHaveAttribute('aria-hidden', 'true')
    },
  )
})
