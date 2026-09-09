import type { CloudPhaseSummaryOut, CriterionScoringRunSummary } from '../api/types'
import { formatProviderLabel } from '../utils/categoryLabels'
import {
  deriveClassificationSteps,
  type ClassificationStep,
  type ClassificationStepState,
} from '../utils/classificationSteps'
import { StatusDot } from './StatusDot'
import { Icon } from './ui/icon'
import { Progress } from './ui/progress'

/**
 * Die Teilschrittliste während eines laufenden Klassifizierungslaufs (specs/features/0348-
 * klassifizierungs-transparenz.md, Abschnitt "Während des Laufs").
 *
 * Die Ableitung "welcher Teilschritt, welcher Zustand, welcher Fortschritt" steht vollständig in
 * `utils/classificationSteps.ts` - hier bleibt reine Darstellung.
 *
 * ZUSTANDSDARSTELLUNG: Jede Zeile trägt ihren Zustand als AUSGESCHRIEBENES WORT und zusätzlich als
 * `data-step-state`, nie allein über Farbe oder Symbol. Das Zeichen links ist bewusst der bereits
 * im Produkt etablierte `StatusDot` (laufend: Puls in der Prozessfarbe, `motion-reduce`-fest) bzw.
 * der `check`-Haken - kein neuer Spinner und kein durchgestrichener Kreis: das Design-System führt
 * `rounded-full` als abschließende Fundstellenliste und kennt kein neutrales Kreuz-Symbol. Die
 * Zustandsaussage hängt ohnehin am Text, das Zeichen begleitet ihn nur.
 */

const STATE_LABELS: Record<ClassificationStepState, string> = {
  pending: 'ausstehend',
  running: 'läuft',
  done: 'erledigt',
  skipped: 'übersprungen',
}

interface ClassificationProgressProps {
  run: CriterionScoringRunSummary
}

export function ClassificationProgress({ run }: ClassificationProgressProps) {
  const steps = deriveClassificationSteps(run)

  return (
    <ul
      aria-live="polite"
      aria-label="Teilschritte der Klassifizierung"
      className="flex w-full max-w-sm flex-col gap-3"
    >
      {steps.map((step) => (
        <li
          key={step.id}
          data-testid={`classification-step-${step.id}`}
          data-step-id={step.id}
          data-step-state={step.state}
          className="flex flex-col gap-1"
        >
          <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
            <span className="flex items-center gap-2 text-sm text-text-h">
              <StepMarker state={step.state} />
              {step.label}
            </span>
            <span className="text-xs text-text-muted">
              {STATE_LABELS[step.state]}
              {progressValue(step) !== null && ` · ${progressValue(step)}`}
            </span>
          </div>
          {step.cloud !== null && (
            <p className="text-xs text-text-muted">
              <CloudDetail cloud={step.cloud} state={step.state} />
            </p>
          )}
          {step.total !== null &&
            // `max={0}` ist als HTML-Attribut ungültig - im kurzen Fenster unmittelbar nach dem
            // Auslösen steht `photos_total` noch auf 0. Dort der unbestimmte Balken, der ohnehin
            // die ehrlichere Aussage ist ("läuft, Menge noch unbekannt").
            (step.total > 0 ? (
              <Progress className="h-1.5" value={step.processed ?? 0} max={step.total}>
                {step.processed ?? 0}/{step.total}
              </Progress>
            ) : (
              <Progress className="h-1.5" />
            ))}
        </li>
      ))}
    </ul>
  )
}

/** `null` = kein anzeigbarer Fortschrittswert (ausstehend, übersprungen, oder ohne Gesamtzahl). */
function progressValue(step: ClassificationStep): string | null {
  if (step.state === 'pending' || step.state === 'skipped') {
    return null
  }
  if (step.total === null || step.processed === null) {
    return null
  }
  return `${step.processed}/${step.total}`
}

function StepMarker({ state }: { state: ClassificationStepState }) {
  if (state === 'done') {
    return <Icon name="check" size={16} className="shrink-0 text-accent" />
  }
  return <StatusDot status={state === 'running' ? 'running' : null} />
}

function CloudDetail({
  cloud,
  state,
}: {
  cloud: CloudPhaseSummaryOut
  state: ClassificationStepState
}) {
  // Anbieter und Modell sind reguläre Textknoten (Herstellerbezeichnungen aus der Antwort). Ist
  // der Anbieter unbekannt, steht die Modell-ID ALLEIN da - nie ein geratener Anbieter und nie ein
  // Konfigurationshinweis der Art "Anbieter prüfen".
  const source =
    cloud.model === null
      ? null
      : cloud.provider === null
        ? `Modell ${cloud.model}`
        : `${formatProviderLabel(cloud.provider)}, Modell ${cloud.model}`

  if (state === 'running') {
    return (
      <>
        Aufrufe abgesetzt: {cloud.photos_processed ?? '—'} · fehlgeschlagen:{' '}
        {cloud.failed_calls ?? '—'}
        {source !== null && ` · ${source}`}
      </>
    )
  }
  return (
    <>
      {cloud.photos_total ?? '—'} Fotos · {cloud.responses_used ?? '—'} Antworten ·{' '}
      {cloud.failed_calls ?? '—'} fehlgeschlagen
      {source !== null && ` · ${source}`}
    </>
  )
}
