import { Link } from 'react-router'

import type { ScoringRunSummary } from '../api/types'
import { formatDateTime } from '../utils/formatStats'
import { ausschussStepPath } from '../utils/projectRoutes'
import { AUSSCHUSS_NOTHING_SORTED_TEXT } from '../utils/stepActionTexts'
import { RerunBlock } from './RerunBlock'
import { Alert } from './ui/alert'
import { Button } from './ui/button'

export function AusschussRecognition({
  projectId,
  rerun,
  onRerun,
  disabled,
  busy,
  triggerError,
  scoringStatus,
  suggestionsFoundText,
  autoDecidedGroupCount,
  gateConfirmedAt,
  errorMessage,
}: {
  projectId: number
  rerun: { label: string; explanation: string } | null
  onRerun: () => void
  disabled: boolean
  busy: boolean
  triggerError: string | null
  scoringStatus: ScoringRunSummary['status'] | null
  suggestionsFoundText: string
  /** `null`, wenn der Zähler nicht steht: gefilterte Ansicht, Laden oder Fehler. */
  autoDecidedGroupCount: number | null
  gateConfirmedAt: string | null
  errorMessage: string | null | undefined
}) {
  return (
    <>
      <h2 className="text-lg">Ausschuss</h2>
      <p className="text-sm text-text">
        Erkennt automatisch unscharfe, überbelichtete oder doppelte Fotos als Ausschuss-Vorschläge —
        läuft vollständig lokal auf diesem Server.
      </p>
      <p className="text-sm text-text">{AUSSCHUSS_NOTHING_SORTED_TEXT}</p>
      {rerun !== null && (
        <RerunBlock rerun={rerun} onRerun={onRerun} disabled={disabled} busy={busy} />
      )}

      {triggerError && <Alert>{triggerError}</Alert>}

      {scoringStatus === 'success' && <p className="text-sm text-text">{suggestionsFoundText}</p>}

      {/* Zähler als Link in die gefilterte Ansicht. Bei 0 entfällt die Zeile ganz; solange
          geladen wird oder ein Fehler vorliegt, gibt es keine 0 und keinen Platzhalter. */}
      {autoDecidedGroupCount !== null && autoDecidedGroupCount > 0 && (
        <div className="flex flex-wrap">
          <Button asChild variant="outline" size="sm" className="h-11 sm:h-8">
            <Link to={ausschussStepPath(projectId, { auto: true })}>
              {autoDecidedGroupCount === 1
                ? '1 Gruppe automatisch entschieden'
                : `${autoDecidedGroupCount} Gruppen automatisch entschieden`}
            </Link>
          </Button>
        </div>
      )}

      {/* Nach der Bestaetigung bleibt der Schritt aufrufbar - weitere Anpassungen sind moeglich,
          und es kann erneut bestaetigt werden. */}
      {gateConfirmedAt !== null && (
        <p className="text-sm text-text">
          Ausschuss bestätigt am {formatDateTime(gateConfirmedAt)} — der Schritt bleibt aufrufbar.
        </p>
      )}

      {/* Ohne Wiederholung: Die einzige Wiederholung ist die Hauptaktion der Leiste. */}
      {scoringStatus === 'failed' && <Alert>{errorMessage}</Alert>}
    </>
  )
}
