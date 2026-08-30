import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { StatusTag } from './StatusTag'

/*
 * StatusTag traegt - anders als die rein praesentationellen Primitives - echte Verzweigungslogik
 * (vier Zustaende, davon einer mit zusaetzlichem Laufindikator). Geprueft ueber das
 * data-status-Attribut statt ueber CSS-Klassen (Selektor-Stabilitaetsregel,
 * specs/architecture/0002-testkonzept.md), plus je eine Zusicherung fuer die beiden Dinge, die
 * eine Verwechslung der Zustaende unbemerkt liesse: die Beschriftung und der Laufindikator.
 */
describe('StatusTag', () => {
  it.each([
    ['never', 'Noch nicht gescannt'],
    ['running', 'Scan läuft…'],
    ['success', 'Erfolgreich'],
    ['failed', 'Fehlgeschlagen'],
  ] as const)('labels the %s status', (status, label) => {
    render(<StatusTag status={status} />)

    expect(screen.getByText(label)).toHaveAttribute('data-status', status)
  })

  it('shows a spinning indicator only while the scan is running', () => {
    render(<StatusTag status="running" />)

    expect(screen.getByTestId('status-tag-spinner')).toBeInTheDocument()
  })

  it.each(['never', 'success', 'failed'] as const)(
    'shows no spinning indicator for the %s status',
    (status) => {
      render(<StatusTag status={status} />)

      expect(screen.queryByTestId('status-tag-spinner')).not.toBeInTheDocument()
    }
  )

  /*
   * Der Laufindikator ist rein dekorativ - die Zustandsinformation steht als Text daneben. Ohne
   * aria-hidden wuerde ein Screenreader ein leeres, bedeutungsloses Element ankuendigen.
   */
  it('hides the decorative indicator from assistive technology', () => {
    render(<StatusTag status="running" />)

    expect(screen.getByTestId('status-tag-spinner')).toHaveAttribute('aria-hidden', 'true')
  })
})
