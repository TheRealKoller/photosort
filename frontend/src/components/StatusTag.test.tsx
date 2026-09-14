import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { StatusTag } from './StatusTag'

/*
 * StatusTag traegt - anders als die rein praesentationellen Primitives - echte Verzweigungslogik
 * (vier Tonwerte, davon einer mit zusaetzlichem Laufindikator). Geprueft ueber das
 * data-status-Attribut statt ueber CSS-Klassen (Selektor-Stabilitaetsregel,
 * specs/architecture/0002-testkonzept.md), plus je eine Zusicherung fuer die beiden Dinge, die
 * eine Verwechslung der Zustaende unbemerkt liesse: die Beschriftung und der Laufindikator.
 *
 * `label` ist seit Spec 0375 eine PFLICHT-Prop: der einzige Aufrufer, der die frueher hinterlegte
 * Vorgabebeschriftung ausloeste, war die Projektkarte, und die traegt ihren Wortlaut jetzt selbst
 * (aus `PIPELINE_STEPS[].label` plus Zusatz). Eine Vorgabetabelle, die kein Aufrufer mehr
 * ausloest, waere eine zweite Textquelle ohne Leser.
 */
describe('StatusTag', () => {
  it.each(['never', 'running', 'success', 'failed'] as const)(
    'traegt den uebergebenen Wortlaut am %s-Tonwert',
    (status) => {
      render(<StatusTag status={status} label={`Beschriftung ${status}`} />)

      expect(screen.getByText(`Beschriftung ${status}`)).toHaveAttribute('data-status', status)
    },
  )

  it('shows a spinning indicator only while something is running', () => {
    render(<StatusTag status="running" label="Scan läuft…" />)

    expect(screen.getByTestId('status-tag-spinner')).toBeInTheDocument()
  })

  it.each(['never', 'success', 'failed'] as const)(
    'shows no spinning indicator for the %s status',
    (status) => {
      render(<StatusTag status={status} label="Irgendein Wortlaut" />)

      expect(screen.queryByTestId('status-tag-spinner')).not.toBeInTheDocument()
    },
  )

  /*
   * Der Laufindikator ist rein dekorativ - die Zustandsinformation steht als Text daneben. Ohne
   * aria-hidden wuerde ein Screenreader ein leeres, bedeutungsloses Element ankuendigen.
   */
  it('hides the decorative indicator from assistive technology', () => {
    render(<StatusTag status="running" label="Scan läuft…" />)

    expect(screen.getByTestId('status-tag-spinner')).toHaveAttribute('aria-hidden', 'true')
  })
})
