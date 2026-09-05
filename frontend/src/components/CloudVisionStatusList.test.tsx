import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { CloudVisionStatusOut } from '../api/types'
import { CloudVisionStatusList } from './CloudVisionStatusList'

function statusEntry(overrides: Partial<CloudVisionStatusOut> = {}): CloudVisionStatusOut {
  return {
    phase: 'landmark',
    status: 'not_run',
    error_message: null,
    attempted_at: null,
    ...overrides,
  }
}

// specs/features/0058-cloud-vision-status-transparenz.md: reine Praesentationskomponente, analog
// CriterionDetailsList - alle sechs Zustaende mit Icon+Text, Fehlermeldung inline nur bei "error",
// permanente Sichtbarkeit unabhaengig vom Rating (kein bedingtes Ausblenden in der Komponente
// selbst - das entscheidet der Aufrufer, siehe CriterionDetailsList-Praezedenzfall).
describe('CloudVisionStatusList', () => {
  it('renders both phases in the given order', () => {
    render(
      <CloudVisionStatusList
        cloudVisionStatus={[
          statusEntry({ phase: 'landmark', status: 'not_run' }),
          statusEntry({ phase: 'remote_category', status: 'not_run' }),
        ]}
      />
    )

    const terms = screen.getAllByText(/Landmark-Erkennung|Remote-Kategorie/).map((el) => el.textContent)
    expect(terms).toEqual(['Landmark-Erkennung', 'Remote-Kategorie'])
  })

  it.each([
    ['not_run', 'Noch nicht verarbeitet'],
    ['not_candidate', 'Nicht als Kandidat qualifiziert'],
    ['consent_disabled', 'Cloud-Erkennung deaktiviert'],
    ['no_result', 'Erfolgreich, keine Treffer'],
    ['result', 'Ergebnis vorhanden'],
  ] as const)('renders the %s status with its text label', (status, label) => {
    // Companion-Phase bewusst mit einem ANDEREN Status befuellt, damit der Text-Match eindeutig
    // bleibt (sonst kollidiert z.B. der not_run-Fall mit sich selbst).
    const companionStatus = status === 'not_run' ? 'result' : 'not_run'
    render(
      <CloudVisionStatusList
        cloudVisionStatus={[
          statusEntry({ phase: 'landmark', status }),
          statusEntry({ phase: 'remote_category', status: companionStatus }),
        ]}
      />
    )

    expect(screen.getByText(label)).toBeInTheDocument()
  })

  it('renders the error status with an error label plus inline message and timestamp', () => {
    render(
      <CloudVisionStatusList
        cloudVisionStatus={[
          statusEntry({
            phase: 'landmark',
            status: 'error',
            error_message: 'Anthropic Vision API nicht erreichbar: timeout',
            attempted_at: '2026-08-24T10:00:00Z',
          }),
          statusEntry({ phase: 'remote_category', status: 'not_run' }),
        ]}
      />
    )

    expect(screen.getByText('Fehler beim Versuch')).toBeInTheDocument()
    expect(screen.getByText('Anthropic Vision API nicht erreichbar: timeout')).toBeInTheDocument()
  })

  it('does not render an error message block for a non-error status', () => {
    render(
      <CloudVisionStatusList
        cloudVisionStatus={[
          statusEntry({ phase: 'landmark', status: 'result', attempted_at: '2026-08-24T10:00:00Z' }),
          statusEntry({ phase: 'remote_category', status: 'not_run' }),
        ]}
      />
    )

    expect(screen.queryByText(/nicht erreichbar/)).not.toBeInTheDocument()
  })

  it('renders a mixed state for both phases simultaneously', () => {
    render(
      <CloudVisionStatusList
        cloudVisionStatus={[
          statusEntry({ phase: 'landmark', status: 'result', attempted_at: '2026-08-24T10:00:00Z' }),
          statusEntry({ phase: 'remote_category', status: 'consent_disabled' }),
        ]}
      />
    )

    expect(screen.getByText('Ergebnis vorhanden')).toBeInTheDocument()
    expect(screen.getByText('Cloud-Erkennung deaktiviert')).toBeInTheDocument()
  })

  it('never renders the error message via dangerouslySetInnerHTML (plain text node)', () => {
    // Sicherheits-Muss-Kriterium der Spec: error_message ausschliesslich als regulaerer
    // React-Textknoten. Ein <script>-artiger String darf nicht als Markup interpretiert werden.
    render(
      <CloudVisionStatusList
        cloudVisionStatus={[
          statusEntry({
            phase: 'landmark',
            status: 'error',
            error_message: '<img src=x onerror="window.__pwned = true">',
            attempted_at: '2026-08-24T10:00:00Z',
          }),
          statusEntry({ phase: 'remote_category', status: 'not_run' }),
        ]}
      />
    )

    expect(
      screen.getByText('<img src=x onerror="window.__pwned = true">')
    ).toBeInTheDocument()
    expect(document.querySelector('img')).not.toBeInTheDocument()
  })

  it('marks decorative icons as aria-hidden', () => {
    const { container } = render(
      <CloudVisionStatusList
        cloudVisionStatus={[
          statusEntry({ phase: 'landmark', status: 'error', error_message: 'x', attempted_at: '2026-08-24T10:00:00Z' }),
          statusEntry({ phase: 'remote_category', status: 'result', attempted_at: '2026-08-24T10:00:00Z' }),
        ]}
      />
    )

    const hiddenIcons = container.querySelectorAll('[aria-hidden="true"]')
    expect(hiddenIcons.length).toBeGreaterThanOrEqual(2)
  })

  /*
   * specs/features/0320-dark-utility-register.md, Teststrategie: Bis zur Symbolumstellung pruefte
   * KEIN Test die Glyphen hier - ihr Austausch braeche nichts, genau der stille Fall. Geprueft
   * wird deshalb, was tatsaechlich traegt: je Status ein sichtbarer, paarweise verschiedener TEXT.
   * Das Symbol darf ausdruecklich gleich sein - die drei "nicht gelaufen"-Zustaende teilen sich
   * den StatusDot, weil der Zwoelfer-Satz des Boards keinen leeren Kreis enthaelt.
   */
  it('gives every status a pairwise distinct visible text', () => {
    const statuses = [
      'not_run',
      'not_candidate',
      'consent_disabled',
      'error',
      'no_result',
      'result',
    ] as const

    const texts = statuses.map((status) => {
      const { container, unmount } = render(
        <CloudVisionStatusList cloudVisionStatus={[statusEntry({ phase: 'landmark', status })]} />
      )
      const text = container.querySelector('dd')!.textContent
      unmount()
      return text
    })

    expect(new Set(texts).size).toBe(statuses.length)
  })

  it('shares one neutral dot across the three "not run" states instead of inventing a symbol', () => {
    for (const status of ['not_run', 'not_candidate', 'consent_disabled'] as const) {
      const { container, unmount } = render(
        <CloudVisionStatusList cloudVisionStatus={[statusEntry({ phase: 'landmark', status })]} />
      )
      expect(container.querySelector('dd [data-icon]')).toBeNull()
      unmount()
    }
  })

  it.each([
    ['error', 'x-circle'],
    ['no_result', 'check'],
    ['result', 'check'],
  ] as const)('uses the board symbol %s -> %s', (status, icon) => {
    const { container } = render(
      <CloudVisionStatusList cloudVisionStatus={[statusEntry({ phase: 'landmark', status })]} />
    )

    expect(container.querySelector(`dd [data-icon="${icon}"]`)).not.toBeNull()
  })
})
