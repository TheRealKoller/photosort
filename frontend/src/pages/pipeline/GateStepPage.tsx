import { Link, useOutletContext } from 'react-router'

import { StatusDot } from '../../components/StatusDot'
import { Button } from '../../components/ui/button'
import type { PipelineOutletContext } from './ProjectPipelineLayout'

/**
 * 1:1-Migration der bisherigen Ausschuss-Gate-Section aus ProjectDetailPage.tsx
 * (Akzeptanzkriterium 7/8). Kein "nicht aktiv"-Zweig mehr noetig (anders als bisher): der
 * zentrale Redirect-Guard in ProjectPipelineLayout stellt bereits sicher, dass diese Route nur
 * gerendert wird, wenn die Ausschuss-Erkennung erfolgreich war (isReachable('gate')) - die alte
 * "Sichte zuerst den Ausschuss oben."-Erklaerung lebt jetzt als Blockiert-Grund im Stepper-Popover
 * weiter (utils/pipelineSteps.ts::getBlockedReason), nicht mehr redundant auch hier.
 *
 * Zusaetzlich zur bisherigen Statuszeile jetzt eine kurze Erklaerzeile (Akzeptanzkriterium 8,
 * Konsistenz mit den bereits beschrifteten Schritten Kriterien-Bewertung/Kuratierung). Das
 * bestehende "Automatisch uebersprungener Schritt bleibt sichtbar nachvollziehbar"-Muster bleibt
 * unveraendert: der dauerhaft sichtbare Statusbereich zeigt weiterhin den erklaerenden Text statt
 * eines fluechtigen Toasts, unabhaengig davon, dass der Stepper diesen Schritt als "erledigt" zeigt.
 */
export function GateStepPage() {
  const { project } = useOutletContext<PipelineOutletContext>()
  const scoringRun = project.last_scoring_run
  const gateConfirmedAt = scoringRun?.gate_confirmed_at ?? null
  const isGateAutoConfirmed = gateConfirmedAt !== null && scoringRun?.suggestions_found === 0

  return (
    <section className="flex flex-col items-start gap-3">
      <h2 className="text-lg">Ausschuss-Gate</h2>
      <p className="text-sm text-text">
        Bestätige einmalig, dass du die Ausschuss-Vorschläge gesichtet hast, bevor es mit der
        Kriterien-Bewertung weitergeht.
      </p>

      <p aria-live="polite" className="flex items-center gap-2 text-sm text-text">
        <StatusDot status={gateConfirmedAt !== null ? 'success' : null} />
        {gateConfirmedAt === null && 'Ausstehend'}
        {isGateAutoConfirmed && 'Kein Ausschuss gefunden — automatisch bestätigt'}
        {gateConfirmedAt !== null &&
          !isGateAutoConfirmed &&
          `Ausschuss gesichtet am ${new Date(gateConfirmedAt).toLocaleString('de-DE')}`}
      </p>

      {gateConfirmedAt === null && (
        <Button asChild variant="secondary" size="sm">
          <Link to={`/projects/${project.id}/photos?filter=suggested&gate=1`}>Ausschuss sichten</Link>
        </Button>
      )}
    </section>
  )
}
