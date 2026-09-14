import { describe, expect, it, vi } from 'vitest'

import { apiFetch } from './client'
import { getFeedbackDiagnosis } from './feedback'
import type { FeedbackDiagnosisOut } from './types'

vi.mock('./client', () => ({
  apiFetch: vi.fn(),
}))

const DIAGNOSIS: FeedbackDiagnosisOut = {
  correction_count: 0,
  motif_errors: [],
  exchanges: [],
  criteria: [],
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
})
