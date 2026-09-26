import type { MotifAssessmentOut, MotifStrengthOut } from '../api/types'
import { useMotifsQuery } from '../hooks/useMotifs'
import { cn } from '../lib/utils'
import { motifIconName } from '../utils/motifIcons'
import { motifStrengthEntries, UNASSESSED_TEXT } from '../utils/motifStrength'
import { MotifStrengthSymbol } from './MotifStrengthSymbol'
import { Alert } from './ui/alert'
import { Skeleton } from './ui/skeleton'

const MOTIF_SET_ERROR_TEXT = 'Die Motive konnten nicht geladen werden.'

interface MotifStrengthRowProps {
  /** `null` heisst "noch nicht klassifiziert" - dann steht der Satz statt der Reihe. */
  assessment: MotifAssessmentOut | null | undefined
  motifs: readonly MotifStrengthOut[] | undefined
  /** Lage der Reihe in der umgebenden Zeile. */
  className?: string
}

/**
 * Die schreibgeschuetzte Fuellstandsreihe fuer eine Kopfzeile: acht Motivsymbole in
 * Registry-Reihenfolge, jedes mit dem zugaenglichen Namen "{Motiv}: {Wert}".
 *
 * NICHTS DARIN IST BEDIENBAR: kein Fokus, keine Trefferflaeche, kein `title`, keine
 * Grundlagenzeile und kein Glossar - die Reihe liefert die Motivkennung ohne Handgriff. Eine
 * ausgeschlossene Einstufung (`excluded_document`) zeigt die Reihe unveraendert und ohne Satz.
 *
 * Laedt das Motivset selbst (`useMotifsQuery`, langlebig gecacht).
 */
export function MotifStrengthRow({ assessment, motifs, className }: MotifStrengthRowProps) {
  const motifsQuery = useMotifsQuery()

  if (motifsQuery.isError) {
    // Die Meldung nimmt die volle Breite der umgebenden Zeile ein und steht an ihrem Ende.
    return (
      <Alert onRetry={() => void motifsQuery.refetch()} className="order-last w-full">
        {MOTIF_SET_ERROR_TEXT}
      </Alert>
    )
  }

  if (motifsQuery.data === undefined) {
    return (
      <div role="status" aria-label="Motive werden geladen" className={cn('flex gap-2', className)}>
        {Array.from({ length: 8 }, (_, index) => (
          <Skeleton key={index} className="size-6 rounded-sm" />
        ))}
      </div>
    )
  }

  if (assessment === null || assessment === undefined) {
    return <p className={cn('text-xs text-text', className)}>{UNASSESSED_TEXT}</p>
  }

  return (
    <ul aria-label="Motive" className={cn('flex gap-2', className)}>
      {motifStrengthEntries(motifsQuery.data, assessment, motifs).map((entry) => (
        <li key={entry.key}>
          <span role="img" aria-label={`${entry.displayName}: ${entry.value.text}`}>
            <MotifStrengthSymbol
              iconName={motifIconName(entry.key)}
              step={entry.step}
              fillPercent={entry.fillPercent}
              size={24}
            />
          </span>
        </li>
      ))}
    </ul>
  )
}
