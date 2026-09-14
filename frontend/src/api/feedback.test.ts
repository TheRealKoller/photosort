import { describe, expect, it, vi } from 'vitest'

import { apiFetch } from './client'
import { adoptFeedbackWeights, getFeedbackDiagnosis, revertFeedbackWeights } from './feedback'
import type { FeedbackDiagnosisOut, FeedbackWeightPreview } from './types'

vi.mock('./client', () => ({
  apiFetch: vi.fn(),
}))

const PREVIEW: FeedbackWeightPreview = {
  current: [],
  proposed: [],
  based_on_event_id: 0,
  current_set_id: null,
  can_revert: false,
}

const DIAGNOSIS: FeedbackDiagnosisOut = {
  correction_count: 0,
  motif_errors: [],
  exchanges: [],
  criteria: [],
  weights: PREVIEW,
}

describe('api/feedback', () => {
  it('fragt die Diagnose OHNE Projektbezug ab', async () => {
    // Die tragende Assertion ist die Abwesenheit des Projekts im Pfad: Die Zahlen gelten
    // projektübergreifend, und ein Projektsegment wäre der Weg, auf dem sie stillschweigend
    // wieder projektweise würden.
    vi.mocked(apiFetch).mockResolvedValue(DIAGNOSIS)

    const result = await getFeedbackDiagnosis()

    expect(apiFetch).toHaveBeenCalledWith('/feedback/diagnosis')
    expect(result).toEqual(DIAGNOSIS)
  })

  it('schickt bei der Übernahme AUSSCHLIESSLICH den Anker mit', async () => {
    // Die tragende Assertion ist auch hier die Abwesenheit: kein Gewicht im Body. Der Server
    // rechnet den Vorschlag neu; ein mitgeschicktes `weight` wäre der einzige Wert, mit dem ein
    // Aufrufer die eigene Korrektur überproportional zählen ließe.
    vi.mocked(apiFetch).mockResolvedValue(PREVIEW)

    await adoptFeedbackWeights(12)

    expect(apiFetch).toHaveBeenCalledWith('/feedback/weights', {
      method: 'POST',
      body: { based_on_event_id: 12 },
    })
  })

  it('nennt bei der Rücknahme die Fassung, die zurückgenommen werden soll', async () => {
    vi.mocked(apiFetch).mockResolvedValue(PREVIEW)

    await revertFeedbackWeights(3)

    expect(apiFetch).toHaveBeenCalledWith('/feedback/weights/revert', {
      method: 'POST',
      body: { reverts_set_id: 3 },
    })
  })
})
