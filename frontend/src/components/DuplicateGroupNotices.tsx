import { ApiError } from '../api/client'
import {
  DUPLICATE_CONSEQUENCE_TEXT,
  DUPLICATE_EMPTY_TEXT,
  DUPLICATE_HINT_TEXT,
} from '../utils/duplicateTexts'
import { Alert } from './ui/alert'

export interface DuplicateGroupNoticesProps {
  filled: boolean
  autoDecided: boolean
  autoUndoneAndOpen: boolean
  empty: boolean
  /** Der Ladefehler, der keine leere Gruppe ist; `null` ohne Störung. */
  loadError: Error | null
  onRetry: () => void
}

/** Die Sätze über der Handlung: automatisch entschieden, leer, Ladefehler, Rücknahme, Hinweise. */
export function DuplicateGroupNotices({
  filled,
  autoDecided,
  autoUndoneAndOpen,
  empty,
  loadError,
  onRetry,
}: DuplicateGroupNoticesProps) {
  return (
    <>
      {filled && autoDecided && (
        <div className="flex max-w-3xl flex-col gap-2">
          <p data-testid="duplicate-auto-decided" className="text-sm text-text">
            Automatisch entschieden – praktisch identische Aufnahmen
          </p>
          <p className="text-sm text-text">
            Zurücknehmen: „Behalten“ auf einer Aufnahme wählen. Die Gruppe ist danach offen, und ein
            späterer Lauf entscheidet sie nicht erneut automatisch.
          </p>
        </div>
      )}

      {empty && <p className="text-sm text-text">{DUPLICATE_EMPTY_TEXT}</p>}

      {loadError !== null && (
        <Alert onRetry={onRetry}>
          {loadError instanceof ApiError
            ? loadError.detail
            : 'Fehler beim Laden der Duplikat-Gruppe.'}
        </Alert>
      )}

      {filled && (
        <>
          {autoUndoneAndOpen && (
            <p role="status" className="text-sm text-text">
              Automatische Entscheidung zurückgenommen — die Gruppe ist jetzt offen.
            </p>
          )}

          {/* Immer sichtbar, nie eingeklappt, kein `Alert` - und unmittelbar an der Handlung. */}
          <div className="flex max-w-3xl flex-col gap-2">
            <p className="text-sm text-text">{DUPLICATE_HINT_TEXT}</p>
            <p data-testid="duplicate-consequence" className="text-sm text-text">
              {DUPLICATE_CONSEQUENCE_TEXT}
            </p>
          </div>
        </>
      )}
    </>
  )
}
