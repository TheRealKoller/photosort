import type { SuggestionOut } from '../api/types'
import { RATING_STATUS_LABELS } from './ratingLabels'

// Aus PhotoDetailPage.tsx extrahiert (specs/features/0040-bewertungsdetails-info-popover.md,
// Architektur-Abschnitt) - der bestehende Ausschuss-Kasten dort UND das neue
// CriterionDetailsPopover.tsx brauchen dieselbe Formatierung, keine zweite, potenziell
// auseinanderlaufende Kopie. Server liefert die Begruendung bereits regelbasiert ueber `reason`
// (backend/src/photosort/api/photos.py::_to_suggestion_out) - hier bewusst nicht erneut aus
// duplicate_of abgeleitet.
export function formatSuggestionReason(suggestion: SuggestionOut): string {
  if (suggestion.reason === 'duplicate') {
    return `Duplikat von Foto #${suggestion.duplicate_of}`
  }
  return 'Geringe Bildqualität'
}

export function formatSuggestionStatusLabel(suggestion: SuggestionOut): string {
  return RATING_STATUS_LABELS[suggestion.status]
}
