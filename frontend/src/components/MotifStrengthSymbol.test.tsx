import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { MotifStrengthSymbol } from './MotifStrengthSymbol'

/**
 * specs/features/0490-motivstaerke-kompakt.md, AK2 und AK4.
 *
 * BEWUSST NICHT GEPRUEFT: der tatsaechlich sichtbare Fuellstand. `clip-path` ist CSS, und jsdom
 * hat keine Layout-Engine - zugesichert wird der UEBERGEBENE Wert, nie ein gemessener Anteil.
 */
function layers(container: HTMLElement): { outline: SVGElement; fill: SVGElement } {
  const svgs = container.querySelectorAll('svg')
  expect(svgs).toHaveLength(2)
  return { outline: svgs[0] as SVGElement, fill: svgs[1] as SVGElement }
}

describe('MotifStrengthSymbol', () => {
  it('zeichnet dasselbe Symbol zweimal uebereinander', () => {
    const { container } = render(
      <MotifStrengthSymbol iconName="paw-print" step="strong" fillPercent={42} />,
    )

    const { outline, fill } = layers(container)
    expect(outline.getAttribute('data-icon')).toBe('paw-print')
    expect(fill.getAttribute('data-icon')).toBe('paw-print')
  })

  it('haelt die Umrissebene bei JEDER Staerke vollstaendig vor', () => {
    // AK2: Die Symbolform bleibt erkennbar, ein schwach vertretenes Motiv wirkt nicht
    // abgeschnitten - einschliesslich Staerke 0 und Staerke 1.
    for (const [step, percent] of [
      ['none', 0],
      ['weak', 1],
      ['strong', 100],
    ] as const) {
      const { container, unmount } = render(
        <MotifStrengthSymbol iconName="landmark" step={step} fillPercent={percent} />,
      )
      expect(container.querySelectorAll('[data-motif-layer="outline"]'), step).toHaveLength(1)
      unmount()
    }
  })

  it('haelt beide Ebenen aus dem Zugaenglichkeitsbaum heraus', () => {
    // Die Aussage traegt der zugaengliche Name der umgebenden Schaltflaeche, nie das Symbol.
    const { container } = render(
      <MotifStrengthSymbol iconName="utensils" step="medium" fillPercent={50} />,
    )

    const { outline, fill } = layers(container)
    expect(outline.getAttribute('aria-hidden')).toBe('true')
    expect(fill.getAttribute('aria-hidden')).toBe('true')
  })

  it('faerbt den Umriss gedaempft', () => {
    // `text-text-muted`, nicht die Disabled-Farbe: die waere ohne Disabled-Variante vertraglich
    // verboten, und ein Umriss ist kein deaktivierter Zustand. Dass die Alternative nicht
    // vorkommt, sichert der Design-Vertragstest selbst; hier steht sie deshalb nicht als
    // Literal - sonst meldete er diese Zeile.
    const { container } = render(
      <MotifStrengthSymbol iconName="tag" step="strong" fillPercent={80} />,
    )

    const outline = container.querySelector('[data-motif-layer="outline"]') as HTMLElement
    expect(outline.className).toContain('text-text-muted')
  })

  it.each([
    ['strong', 'text-status-success'],
    ['medium', 'text-status-running'],
    ['weak', 'text-status-failed'],
  ] as const)('traegt fuer die Stufe %s die Bandfarbe %s an der oberen Ebene', (step, utility) => {
    const { container } = render(
      <MotifStrengthSymbol iconName="sparkles" step={step} fillPercent={70} />,
    )

    const fill = container.querySelector('[data-motif-layer="fill"]') as HTMLElement
    expect(fill.className).toContain(utility)
  })

  it('traegt fuer die Stufe none keine Bandfarbe', () => {
    const { container } = render(
      <MotifStrengthSymbol iconName="sparkles" step="none" fillPercent={0} />,
    )

    const fill = container.querySelector('[data-motif-layer="fill"]') as HTMLElement
    for (const utility of ['text-status-success', 'text-status-running', 'text-status-failed']) {
      expect(fill.className, utility).not.toContain(utility)
    }
  })

  it('uebergibt den Fuellanteil als CSS-Variable ueber style, nicht als willkuerliche Utility', () => {
    // Eine `[--motif-fill:…]`- oder `clip-path-[…]`-Utility im TSX loeste die Vertragsregel
    // "keine willkuerlichen Werte" aus; das Beschnitt-Rezept steht in index.css.
    const { container } = render(
      <MotifStrengthSymbol iconName="footprints" step="medium" fillPercent={37} />,
    )

    const fill = container.querySelector('[data-motif-layer="fill"]') as HTMLElement
    expect(fill.style.getPropertyValue('--motif-fill')).toBe('37%')
    expect(fill.className).toContain('motif-fill-clip')
  })

  it('uebernimmt den Prozentwert unveraendert, auch an den Raendern', () => {
    // Derselbe gerundete Wert, den die Aufrufstelle als Text zeigt: Hoehe und Zahl koennen nicht
    // auseinanderlaufen (AK4). Der absichernde Fall ist eine Staerke groesser null, die auf 0 %
    // rundet - sie kommt hier als 0 an und wird nicht heimlich angehoben.
    for (const percent of [0, 100]) {
      const { container, unmount } = render(
        <MotifStrengthSymbol iconName="mountain-snow" step="weak" fillPercent={percent} />,
      )
      const fill = container.querySelector('[data-motif-layer="fill"]') as HTMLElement
      expect(fill.style.getPropertyValue('--motif-fill')).toBe(`${percent}%`)
      unmount()
    }
  })
})
