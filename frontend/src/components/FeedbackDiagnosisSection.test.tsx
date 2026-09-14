import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as feedbackApi from '../api/feedback'
import { ApiError } from '../api/client'
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
    weights: {
      current: [
        { criterion_key: 'sharpness', weight: 1 },
        { criterion_key: 'exposure', weight: 1 },
      ],
      proposed: [
        { criterion_key: 'sharpness', weight: 1, delta: 0 },
        { criterion_key: 'exposure', weight: 1, delta: 0 },
      ],
      based_on_event_id: 0,
      current_set_id: null,
      can_revert: false,
    },
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
    criteria: [
      { criterion_key: 'sharpness', display_name: 'Schärfe', case_count: 0, agreement: 0 },
      { criterion_key: 'exposure', display_name: 'Belichtung', case_count: 0, agreement: 0 },
    ],
  }
}

function filled(): FeedbackDiagnosisOut {
  return {
    ...empty(),
    correction_count: 9,
    weights: {
      current: [
        { criterion_key: 'sharpness', weight: 1 },
        { criterion_key: 'exposure', weight: 1 },
      ],
      proposed: [
        { criterion_key: 'sharpness', weight: 1.15, delta: 0.15 },
        { criterion_key: 'exposure', weight: 0.92, delta: -0.08 },
      ],
      based_on_event_id: 12,
      current_set_id: null,
      can_revert: false,
    },
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
    criteria: [
      { criterion_key: 'sharpness', display_name: 'Schärfe', case_count: 3, agreement: 0.5 },
      { criterion_key: 'exposure', display_name: 'Belichtung', case_count: 0, agreement: 0 },
    ],
  }
}

function adjusted(): FeedbackDiagnosisOut {
  const payload = filled()
  return {
    ...payload,
    weights: { ...payload.weights, current_set_id: 4, can_revert: true },
  }
}

function renderSection() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <FeedbackDiagnosisSection />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.mocked(feedbackApi.getFeedbackDiagnosis).mockReset()
  vi.mocked(feedbackApi.adoptFeedbackWeights).mockReset()
  vi.mocked(feedbackApi.revertFeedbackWeights).mockReset()
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

describe('FeedbackDiagnosisSection: Gewichts-Vorschau', () => {
  it('führt je Kriterium eine Zeile mit geltendem Gewicht, Vorschlag, Abweichung und Fallzahl', async () => {
    vi.mocked(feedbackApi.getFeedbackDiagnosis).mockResolvedValue(filled())

    renderSection()

    await waitFor(() => expect(document.querySelectorAll('[data-criterion-key]')).toHaveLength(2))
    const row = document.querySelector('[data-criterion-key="sharpness"]')
    // Über semantische Attribute geprüft, nie über formatierten Text: Eine Assertion auf "1,15"
    // fände die Zahl irgendwo in der Tabelle - auch in der Zeile daneben.
    expect(row?.getAttribute('data-current')).toBe('1')
    expect(row?.getAttribute('data-proposed')).toBe('1.15')
    expect(row?.getAttribute('data-delta')).toBe('0.15')
    expect(row?.getAttribute('data-case-count')).toBe('3')
  })

  it('nennt das Kriterium mit seinem Anzeigenamen aus der Antwort', async () => {
    // Keine im Frontend gepflegte Merkmalsliste: Sie liefe mit jedem neuen Kriterium auseinander,
    // und die Tabelle zeigte dann rohe Schlüssel.
    vi.mocked(feedbackApi.getFeedbackDiagnosis).mockResolvedValue(filled())

    renderSection()

    expect(await screen.findByRole('rowheader', { name: 'Schärfe' })).toBeInTheDocument()
  })

  it('trägt die Abweichung mit Vorzeichen im Text und die Null ohne', async () => {
    // „Keine Aussage allein über Farbe": Die Richtung steht im Text, nicht in einer Einfärbung.
    vi.mocked(feedbackApi.getFeedbackDiagnosis).mockResolvedValue(filled())

    renderSection()

    await waitFor(() =>
      expect(document.querySelector('[data-criterion-key="sharpness"]')).toHaveTextContent('+0,15'),
    )
    expect(document.querySelector('[data-criterion-key="exposure"]')).toHaveTextContent('−0,08')
  })

  it('sagt, dass die Änderung erst beim nächsten Durchlauf wirkt', async () => {
    // Ohne diesen Satz erwartet jeder eine sofortige Änderung seines offenen Entwurfs.
    vi.mocked(feedbackApi.getFeedbackDiagnosis).mockResolvedValue(filled())

    renderSection()

    expect(await screen.findByTestId('feedback-weights-effect-hint')).toHaveTextContent(
      /nächsten Durchlauf/i,
    )
  })

  it('zeigt im Leerzustand keine einzige Kriterienzeile und keinen Auslöser', async () => {
    // D6: Der Leerzustand bleibt von „N Korrekturen, 0 Fehler" unterscheidbar - und eine
    // Anpassung, die nichts anpasst, wird gar nicht erst angeboten.
    vi.mocked(feedbackApi.getFeedbackDiagnosis).mockResolvedValue(empty())

    renderSection()

    await waitFor(() => expect(screen.getByTestId('feedback-diagnosis-empty')).toBeInTheDocument())
    expect(document.querySelectorAll('[data-criterion-key]')).toHaveLength(0)
    expect(screen.queryByRole('button', { name: /gewichte anpassen/i })).not.toBeInTheDocument()
  })
})

describe('FeedbackDiagnosisSection: Anpassen und Zurücksetzen', () => {
  it('übernimmt erst nach der Bestätigung im Dialog', async () => {
    // Die tragende Assertion ist die negative: Der Dialog allein löst nichts aus. Er ist die
    // Einlösung von „vor dem Auslösen ist erkennbar, was sich ändert".
    vi.mocked(feedbackApi.getFeedbackDiagnosis).mockResolvedValue(filled())
    vi.mocked(feedbackApi.adoptFeedbackWeights).mockResolvedValue(adjusted().weights)

    renderSection()

    await userEvent.click(await screen.findByRole('button', { name: /gewichte anpassen/i }))
    expect(feedbackApi.adoptFeedbackWeights).not.toHaveBeenCalled()

    await userEvent.click(screen.getByRole('button', { name: 'Anpassen' }))

    await waitFor(() => expect(feedbackApi.adoptFeedbackWeights).toHaveBeenCalledWith(12))
  })

  it('zeigt im Dialog die verkürzte Gegenüberstellung je Kriterium', async () => {
    vi.mocked(feedbackApi.getFeedbackDiagnosis).mockResolvedValue(filled())

    renderSection()

    await userEvent.click(await screen.findByRole('button', { name: /gewichte anpassen/i }))

    const rows = document.querySelectorAll('[data-dialog-criterion-key]')
    expect(rows).toHaveLength(2)
    expect(document.querySelector('[data-dialog-criterion-key="sharpness"]')).toHaveTextContent(
      '1,15',
    )
  })

  it('löst beim Abbrechen nichts aus', async () => {
    vi.mocked(feedbackApi.getFeedbackDiagnosis).mockResolvedValue(filled())

    renderSection()

    await userEvent.click(await screen.findByRole('button', { name: /gewichte anpassen/i }))
    await userEvent.click(screen.getByRole('button', { name: 'Abbrechen' }))

    expect(feedbackApi.adoptFeedbackWeights).not.toHaveBeenCalled()
    expect(document.querySelectorAll('[data-dialog-criterion-key]')).toHaveLength(0)
  })

  it('bietet das Zurücksetzen erst an, wenn eine Fassung gespeichert ist', async () => {
    // Paarweise in einem Fall: Ohne die Gegenprobe bestünde die Assertion auch gegen eine
    // Umsetzung, die die Schaltfläche nie zeigt.
    vi.mocked(feedbackApi.getFeedbackDiagnosis).mockResolvedValue(filled())

    const { unmount } = renderSection()
    await screen.findByRole('button', { name: /gewichte anpassen/i })
    expect(screen.queryByRole('button', { name: /vorige gewichte/i })).not.toBeInTheDocument()
    unmount()

    vi.mocked(feedbackApi.getFeedbackDiagnosis).mockResolvedValue(adjusted())
    renderSection()

    expect(await screen.findByRole('button', { name: /vorige gewichte/i })).toBeInTheDocument()
  })

  it('nennt beim Zurücksetzen die geltende Fassung', async () => {
    // Ohne diese Angabe legten zwei Aufrufe kurz hintereinander erst die Rücknahme und dann deren
    // Rücknahme an - das Ergebnis wäre der Ausgangszustand, und keine Anzeige wiese das als
    // falsch aus.
    vi.mocked(feedbackApi.getFeedbackDiagnosis).mockResolvedValue(adjusted())
    vi.mocked(feedbackApi.revertFeedbackWeights).mockResolvedValue(filled().weights)

    renderSection()

    await userEvent.click(await screen.findByRole('button', { name: /vorige gewichte/i }))

    await waitFor(() => expect(feedbackApi.revertFeedbackWeights).toHaveBeenCalledWith(4))
  })

  it('bestätigt eine erfolgreiche Anpassung an der Tabelle', async () => {
    vi.mocked(feedbackApi.getFeedbackDiagnosis).mockResolvedValue(filled())
    vi.mocked(feedbackApi.adoptFeedbackWeights).mockResolvedValue(adjusted().weights)

    renderSection()

    await userEvent.click(await screen.findByRole('button', { name: /gewichte anpassen/i }))
    await userEvent.click(screen.getByRole('button', { name: 'Anpassen' }))

    expect(await screen.findByTestId('feedback-weights-confirmation')).toHaveTextContent(
      /übernommen/i,
    )
  })

  it('meldet einen Konflikt mit dem Text des Servers und ändert sonst nichts', async () => {
    // Der `409`-Fall: Der Server hat NICHTS geschrieben. Der Abschnitt darf danach nicht so
    // aussehen, als wäre die Anpassung erfolgt.
    vi.mocked(feedbackApi.getFeedbackDiagnosis).mockResolvedValue(filled())
    vi.mocked(feedbackApi.adoptFeedbackWeights).mockRejectedValue(
      new ApiError(409, 'Seit der Anzeige sind neue Korrekturen hinzugekommen.'),
    )

    renderSection()

    await userEvent.click(await screen.findByRole('button', { name: /gewichte anpassen/i }))
    await userEvent.click(screen.getByRole('button', { name: 'Anpassen' }))

    expect(await screen.findByTestId('feedback-weights-error')).toHaveTextContent(
      /neue Korrekturen hinzugekommen/i,
    )
    expect(screen.queryByTestId('feedback-weights-confirmation')).not.toBeInTheDocument()
  })
})
