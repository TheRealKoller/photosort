import type { SuggestionOut } from '../api/types'
import { formatSuggestionReason, formatSuggestionStatusLabel } from '../utils/suggestionLabels'
import { Button } from './ui/button'

interface PhotoSuggestionNoticeProps {
  suggestion: SuggestionOut
  busy: boolean
  onAccept: () => void
}

export function PhotoSuggestionNotice({ suggestion, busy, onAccept }: PhotoSuggestionNoticeProps) {
  return (
    <div className="flex flex-col items-start gap-2 rounded-md border border-accent bg-elevated p-3 text-sm">
      <p className="text-text-h">
        Automatischer Vorschlag: {formatSuggestionStatusLabel(suggestion)}
      </p>
      {/* Formatierung aus utils/suggestionLabels.ts, keine zweite Kopie derselben Logik. */}
      <p className="text-text">{formatSuggestionReason(suggestion)}</p>
      {/* Ruft denselben Mutation-Pfad wie ein manueller Klick auf die passende
          RatingButtons-Option auf - der bestehende Auto-Advance greift danach unveraendert.
          Kein eigener "Vorschlag verwerfen"-Zustand: normale Weiternavigation ist das
          implizite Ignorieren. */}
      <Button type="button" variant="outline" size="sm" busy={busy} onClick={onAccept}>
        Vorschlag übernehmen
      </Button>
    </div>
  )
}
