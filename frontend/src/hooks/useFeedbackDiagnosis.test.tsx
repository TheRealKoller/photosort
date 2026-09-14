import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'

import * as feedbackApi from '../api/feedback'
import type { FeedbackDiagnosisOut } from '../api/types'
import { feedbackDiagnosisQueryKey, useFeedbackDiagnosisQuery } from './useFeedbackDiagnosis'

vi.mock('../api/feedback')

const DIAGNOSIS: FeedbackDiagnosisOut = {
  correction_count: 3,
  motif_errors: [],
  exchanges: [],
  criteria: [],
}

function wrapper(client: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
}

describe('useFeedbackDiagnosisQuery', () => {
  it('lädt die Diagnose', async () => {
    vi.mocked(feedbackApi.getFeedbackDiagnosis).mockResolvedValue(DIAGNOSIS)
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })

    const { result } = renderHook(() => useFeedbackDiagnosisQuery(), { wrapper: wrapper(client) })

    await waitFor(() => expect(result.current.data).toEqual(DIAGNOSIS))
  })

  it('führt weder Projekt noch Nutzer im Schlüssel', () => {
    // Der Endpunkt ist in Menge und in jedem Feld nutzerunabhängig und zählt über alle Projekte.
    // Ein Projekt- oder Nutzersegment im Schlüssel behauptete eine Trennung, die es nicht gibt -
    // und lüde denselben Stand mehrfach.
    expect(feedbackDiagnosisQueryKey()).toEqual(['feedback-diagnosis'])
  })
})
