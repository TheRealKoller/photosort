import { describe, expect, it } from 'vitest'

import type { SuggestionOut } from '../api/types'
import { formatSuggestionReason, formatSuggestionStatusLabel } from './suggestionLabels'

function suggestion(overrides: Partial<SuggestionOut> = {}): SuggestionOut {
  return {
    status: 'rejected',
    reason: 'low_quality',
    duplicate_of: null,
    sharpness: 1.0,
    exposure: 0.2,
    cluster_key: null,
    computed_at: '2026-07-20T10:00:00Z',
    ...overrides,
  }
}

describe('formatSuggestionReason', () => {
  // Server liefert die Begruendung bereits regelbasiert ueber `reason`
  // (backend/src/photosort/api/photos.py::_to_suggestion_out) - hier bewusst nicht erneut aus
  // duplicate_of abgeleitet (extrahiert aus PhotoDetailPage.tsx, specs/features/0040-
  // bewertungsdetails-info-popover.md).
  it('formats a duplicate reason with the referenced photo id', () => {
    expect(formatSuggestionReason(suggestion({ reason: 'duplicate', duplicate_of: 42 }))).toBe(
      'Duplikat von Foto #42'
    )
  })

  it('formats a low_quality reason', () => {
    expect(formatSuggestionReason(suggestion({ reason: 'low_quality' }))).toBe(
      'Geringe Bildqualität'
    )
  })
})

describe('formatSuggestionStatusLabel', () => {
  it('reuses RATING_STATUS_LABELS for the suggested status', () => {
    expect(formatSuggestionStatusLabel(suggestion({ status: 'rejected' }))).toBe('Verworfen')
    expect(formatSuggestionStatusLabel(suggestion({ status: 'album_worthy' }))).toBe(
      'Album-würdig'
    )
  })
})
