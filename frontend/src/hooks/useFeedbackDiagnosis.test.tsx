import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'

import * as feedbackApi from '../api/feedback'
import type { FeedbackDiagnosisOut, FeedbackWeightPreview } from '../api/types'
import {
  feedbackDiagnosisQueryKey,
  useAdoptFeedbackWeightsMutation,
  useFeedbackDiagnosisQuery,
  useRevertFeedbackWeightsMutation,
} from './useFeedbackDiagnosis'

vi.mock('../api/feedback')

const PREVIEW: FeedbackWeightPreview = {
  current: [{ criterion_key: 'sharpness', weight: 1 }],
  proposed: [{ criterion_key: 'sharpness', weight: 1, delta: 0 }],
  based_on_event_id: 7,
  current_set_id: null,
  can_revert: false,
}

const DIAGNOSIS: FeedbackDiagnosisOut = {
  correction_count: 3,
  motif_errors: [],
  exchanges: [],
  criteria: [],
  weights: PREVIEW,
}

function wrapper(client: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
}

function freshClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
}

describe('useFeedbackDiagnosisQuery', () => {
  it('lädt die Diagnose', async () => {
    vi.mocked(feedbackApi.getFeedbackDiagnosis).mockResolvedValue(DIAGNOSIS)
    const client = freshClient()

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

describe('useAdoptFeedbackWeightsMutation', () => {
  it('reicht den Anker durch und lädt die Diagnose danach neu', async () => {
    // Das erneute Laden ist nicht Kosmetik: Nach der Übernahme ist das geltende Gewicht ein
    // anderes, die Abweichung wieder null und die Rücknahme möglich. Ohne Invalidierung stünde
    // die Tabelle weiter auf dem Stand von vorher und böte dieselbe Anpassung erneut an.
    vi.mocked(feedbackApi.getFeedbackDiagnosis).mockResolvedValue(DIAGNOSIS)
    vi.mocked(feedbackApi.adoptFeedbackWeights).mockResolvedValue(PREVIEW)
    const client = freshClient()
    await client.fetchQuery({
      queryKey: feedbackDiagnosisQueryKey(),
      queryFn: feedbackApi.getFeedbackDiagnosis,
    })

    const { result } = renderHook(() => useAdoptFeedbackWeightsMutation(), {
      wrapper: wrapper(client),
    })
    result.current.mutate(7)

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(feedbackApi.adoptFeedbackWeights).toHaveBeenCalledWith(7)
    expect(client.getQueryState(feedbackDiagnosisQueryKey())?.isInvalidated).toBe(true)
  })

  it('schreibt bei einem Fehlschlag nichts in den Zwischenspeicher', async () => {
    // Der `409`-Fall: Der Server hat NICHTS geschrieben. Ein optimistisch fortgeschriebener Stand
    // zeigte danach eine Fassung, die es nicht gibt.
    vi.mocked(feedbackApi.getFeedbackDiagnosis).mockResolvedValue(DIAGNOSIS)
    vi.mocked(feedbackApi.adoptFeedbackWeights).mockRejectedValue(new Error('konflikt'))
    const client = freshClient()
    await client.fetchQuery({
      queryKey: feedbackDiagnosisQueryKey(),
      queryFn: feedbackApi.getFeedbackDiagnosis,
    })

    const { result } = renderHook(() => useAdoptFeedbackWeightsMutation(), {
      wrapper: wrapper(client),
    })
    result.current.mutate(7)

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(client.getQueryData(feedbackDiagnosisQueryKey())).toEqual(DIAGNOSIS)
  })
})

describe('useRevertFeedbackWeightsMutation', () => {
  it('reicht die zurückzunehmende Fassung durch und lädt danach neu', async () => {
    vi.mocked(feedbackApi.getFeedbackDiagnosis).mockResolvedValue(DIAGNOSIS)
    vi.mocked(feedbackApi.revertFeedbackWeights).mockResolvedValue(PREVIEW)
    const client = freshClient()
    await client.fetchQuery({
      queryKey: feedbackDiagnosisQueryKey(),
      queryFn: feedbackApi.getFeedbackDiagnosis,
    })

    const { result } = renderHook(() => useRevertFeedbackWeightsMutation(), {
      wrapper: wrapper(client),
    })
    result.current.mutate(4)

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(feedbackApi.revertFeedbackWeights).toHaveBeenCalledWith(4)
    expect(client.getQueryState(feedbackDiagnosisQueryKey())?.isInvalidated).toBe(true)
  })
})
