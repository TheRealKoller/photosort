import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as feedbackApi from '../api/feedback'
import type { FeedbackDiagnosisOut } from '../api/types'
import { FeedbackDiagnosisSection } from './FeedbackDiagnosisSection'

vi.mock('../api/feedback')

/**
 * Die Zahlen werden über SEMANTISCHE ATTRIBUTE geprüft, nie über formatierten Text: Eine
 * Assertion auf "2" fände die 2 irgendwo im Abschnitt - auch in der Kennzahl daneben.
 */
function empty(): FeedbackDiagnosisOut {
  return {
    correction_count: 0,
    motif_errors: [
      { case: 'too_weak', count: 0 },
      { case: 'missing', count: 0 },
      { case: 'overcalled', count: 0 },
    ],
    exchanges: [
      {
        kind: 'within_level',
        count: 0,
        preferred_lower_rated_count: 0,
        quality_incomparable_count: 0,
      },
      {
        kind: 'across_level',
        count: 0,
        preferred_lower_rated_count: 0,
        quality_incomparable_count: 0,
      },
      {
        kind: 'undetermined',
        count: 0,
        preferred_lower_rated_count: 0,
        quality_incomparable_count: 0,
      },
    ],
    criteria: [{ criterion_key: 'sharpness', case_count: 0, agreement: 0 }],
  }
}

function filled(): FeedbackDiagnosisOut {
  return {
    ...empty(),
    correction_count: 9,
    motif_errors: [
      { case: 'too_weak', count: 2 },
      { case: 'missing', count: 1 },
      { case: 'overcalled', count: 0 },
    ],
    exchanges: [
      {
        kind: 'within_level',
        count: 4,
        preferred_lower_rated_count: 3,
        quality_incomparable_count: 1,
      },
      {
        kind: 'across_level',
        count: 2,
        preferred_lower_rated_count: 0,
        quality_incomparable_count: 0,
      },
      {
        kind: 'undetermined',
        count: 1,
        preferred_lower_rated_count: 0,
        quality_incomparable_count: 1,
      },
    ],
    criteria: [{ criterion_key: 'sharpness', case_count: 3, agreement: 0.5 }],
  }
}

function renderSection() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <FeedbackDiagnosisSection />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.mocked(feedbackApi.getFeedbackDiagnosis).mockReset()
})

describe('FeedbackDiagnosisSection', () => {
  it('nennt seinen Abschnitt und spricht die projektübergreifende Zählung aus', async () => {
    vi.mocked(feedbackApi.getFeedbackDiagnosis).mockResolvedValue(filled())

    renderSection()

    expect(
      screen.getByRole('heading', { name: 'Rückmeldung aus der Nacharbeit' }),
    ).toBeInTheDocument()
    // Ohne diese Zeile liest jeder die Zahlen als Aussage über das offene Projekt - genau der
    // Fehlschluss, den die projektübergreifende Zählung sonst einlädt.
    expect(screen.getByTestId('feedback-diagnosis-scope')).toHaveTextContent(
      /über alle Projekte hinweg/i,
    )
  })

  it('behält die Unterzeile im Lade-, Leer- und Fehlerzustand', async () => {
    // Alle drei Zustände in einem Fall, weil die Zusage genau die ist: Sie behält ihren Platz
    // IMMER. Eine Umsetzung, die sie nur im Inhaltszweig rendert, besteht den Fall oben.
    let resolve: (value: FeedbackDiagnosisOut) => void = () => {}
    vi.mocked(feedbackApi.getFeedbackDiagnosis).mockReturnValue(
      new Promise<FeedbackDiagnosisOut>((inner) => {
        resolve = inner
      }),
    )

    renderSection()
    expect(screen.getByTestId('feedback-diagnosis-scope')).toBeInTheDocument()

    resolve(empty())
    await waitFor(() => expect(screen.getByTestId('feedback-diagnosis-empty')).toBeInTheDocument())
    expect(screen.getByTestId('feedback-diagnosis-scope')).toBeInTheDocument()

    vi.mocked(feedbackApi.getFeedbackDiagnosis).mockRejectedValue(new Error('kaputt'))
    renderSection()
    await waitFor(() => expect(screen.getAllByRole('alert').length).toBeGreaterThan(0))
    expect(screen.getAllByTestId('feedback-diagnosis-scope').length).toBeGreaterThan(0)
  })

  it('zeigt im Leerzustand KEINE einzige Fehlerfall- oder Tauschzeile', async () => {
    // D6: Der Leerzustand muss von "N Korrekturen, 0 Fehler" unterscheidbar bleiben. Eine
    // Umsetzung, die einfach überall Nullen zeichnet, besteht jede Zahlenassertion und genau
    // diesen Fall nicht.
    vi.mocked(feedbackApi.getFeedbackDiagnosis).mockResolvedValue(empty())

    renderSection()

    await waitFor(() => expect(screen.getByTestId('feedback-diagnosis-empty')).toBeInTheDocument())
    expect(document.querySelectorAll('[data-motif-error-case]')).toHaveLength(0)
    expect(document.querySelectorAll('[data-exchange-kind]')).toHaveLength(0)
  })

  it('zeigt bei null Fehlern sehr wohl alle Zeilen, sobald korrigiert wurde', async () => {
    // Die Gegenprobe zum Leerzustand: "9 Korrekturen, 0 mal überschätzt" IST eine Aussage.
    vi.mocked(feedbackApi.getFeedbackDiagnosis).mockResolvedValue(filled())

    renderSection()

    await waitFor(() =>
      expect(document.querySelectorAll('[data-motif-error-case]')).toHaveLength(3),
    )
    expect(screen.queryByTestId('feedback-diagnosis-empty')).not.toBeInTheDocument()
    expect(
      document.querySelector('[data-motif-error-case="overcalled"]')?.getAttribute('data-count'),
    ).toBe('0')
  })

  it('führt jeden Motiv-Fehlerfall mit seiner Fallzahl und der Bezugsgröße', async () => {
    vi.mocked(feedbackApi.getFeedbackDiagnosis).mockResolvedValue(filled())

    renderSection()

    await waitFor(() =>
      expect(
        document.querySelector('[data-motif-error-case="too_weak"]')?.getAttribute('data-count'),
      ).toBe('2'),
    )
    expect(
      document.querySelector('[data-motif-error-case="missing"]')?.getAttribute('data-count'),
    ).toBe('1')
    expect(document.querySelector('[data-motif-error-case="too_weak"]')).toHaveTextContent(
      /von 9 Korrekturen/,
    )
  })

  it('weist die drei Tauschklassen getrennt aus und summiert sie nirgends', async () => {
    vi.mocked(feedbackApi.getFeedbackDiagnosis).mockResolvedValue(filled())

    renderSection()

    await waitFor(() => expect(document.querySelectorAll('[data-exchange-kind]')).toHaveLength(3))
    const counts = [...document.querySelectorAll('[data-exchange-kind]')].map((node) =>
      node.getAttribute('data-count'),
    )
    expect(counts).toEqual(['4', '2', '1'])
    // Die Summe 7 steht nirgends - sie wäre eine vierte Zahl, die die Aussage über die lokalen
    // Kriterien mit der über das Modell mischte.
    expect(screen.queryByText('7')).not.toBeInTheDocument()
  })

  it('nennt bei einer Tauschklasse mit Fällen, wie oft schlechter bewertet vorgezogen wurde', async () => {
    vi.mocked(feedbackApi.getFeedbackDiagnosis).mockResolvedValue(filled())

    renderSection()

    await waitFor(() =>
      expect(document.querySelector('[data-exchange-kind="within_level"]')).toHaveTextContent(
        /3× ein schlechter bewertetes Bild vorgezogen/,
      ),
    )
    expect(document.querySelector('[data-exchange-kind="across_level"]')).not.toHaveTextContent(
      /vorgezogen/,
    )
  })

  it('meldet einen Fehler nur für diesen Abschnitt und lässt ihn wiederholen', async () => {
    vi.mocked(feedbackApi.getFeedbackDiagnosis).mockRejectedValueOnce(new Error('kaputt'))
    vi.mocked(feedbackApi.getFeedbackDiagnosis).mockResolvedValue(filled())

    renderSection()

    const retry = await screen.findByRole('button', { name: /erneut versuchen/i })
    await userEvent.click(retry)

    await waitFor(() => expect(document.querySelectorAll('[data-exchange-kind]')).toHaveLength(3))
  })
})
