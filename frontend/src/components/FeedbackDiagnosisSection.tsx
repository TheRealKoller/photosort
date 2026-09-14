import { ApiError } from '../api/client'
import type { FeedbackDiagnosisOut } from '../api/types'
import { useFeedbackDiagnosisQuery } from '../hooks/useFeedbackDiagnosis'
import {
  EXCHANGE_KIND_LABELS,
  MOTIF_ERROR_CASE_LABELS,
  exchangeQualityNote,
  hasCorrections,
} from '../utils/feedbackDiagnosis'
import { formatCount } from '../utils/formatStats'
import { DetailRow, Metric, MetricRow, Section } from './StatsLayout'
import { Alert } from './ui/alert'
import { Skeleton } from './ui/skeleton'

/**
 * Was die Nacharbeit am Album-Entwurf über die Modellfehler sagt - ein eigener Abschnitt der
 * Projekt-Statistikseite.
 *
 * ER LÄDT SEINE ZAHLEN SELBST und nimmt keine Projekt-Id entgegen: Sie zählen über alle Projekte
 * und beide Nutzer. Eingebettet in die Projektstatistik zwänge er die ganze Seite in seinen
 * Ladezustand, und ein Projektparameter wäre der Weg, auf dem die Zahlen stillschweigend wieder
 * projektweise würden.
 *
 * DER TITEL NENNT WEDER LERNEN NOCH TRAINING: Beides findet nicht statt und ist ausdrücklich
 * ausgeschlossen - es wird ausgezählt, nicht trainiert.
 */
export function FeedbackDiagnosisSection() {
  const query = useFeedbackDiagnosisQuery()

  return (
    <Section id="stats-feedback" title="Rückmeldung aus der Nacharbeit">
      {/* IMMER SICHTBAR, auch im Lade-, Leer- und Fehlerzustand: Ohne sie liest jeder die Zahlen
          als Aussage über das offene Projekt - genau der Fehlschluss, den die
          projektübergreifende Zählung sonst einlädt. */}
      <p data-testid="feedback-diagnosis-scope" className="text-xs text-text-muted">
        Diese Zahlen zählen die Korrekturen beider Nutzer über alle Projekte hinweg — die Gewichte
        der Qualitätskriterien gelten für die ganze Instanz und nicht je Projekt.
      </p>
      <DiagnosisBody
        diagnosis={query.data}
        isLoading={query.isLoading}
        isError={query.isError}
        error={query.error}
        onRetry={() => void query.refetch()}
      />
    </Section>
  )
}

function DiagnosisBody({
  diagnosis,
  isLoading,
  isError,
  error,
  onRetry,
}: {
  diagnosis: FeedbackDiagnosisOut | undefined
  isLoading: boolean
  isError: boolean
  error: unknown
  onRetry: () => void
}) {
  if (isLoading) {
    return <DiagnosisSkeleton />
  }
  if (isError || diagnosis === undefined) {
    // Der Fehler betrifft NUR diesen Abschnitt, nicht die Seite: Die Projektzahlen darüber
    // stammen aus einer eigenen Abfrage und stehen weiter.
    return (
      <Alert onRetry={onRetry}>
        {error instanceof ApiError ? error.detail : 'Fehler beim Laden der Rückmeldung.'}
      </Alert>
    )
  }
  if (!hasCorrections(diagnosis)) {
    // KEINE EINZIGE Fehlerfall- oder Tauschzeile, damit dieser Zustand von "N Korrekturen,
    // 0 Fehler" unterscheidbar bleibt. Der Leerzustandstext ist die Hauptaussage des Abschnitts
    // und steht deshalb in `--text`, nicht in `--text-muted`.
    return (
      <p data-testid="feedback-diagnosis-empty" className="text-sm text-text">
        Noch keine Korrekturen festgehalten. Zahlen entstehen hier, sobald ihr im Album-Entwurf
        Bilder austauscht, aufnehmt oder streicht — oder ein Motiv korrigiert.
      </p>
    )
  }
  return <DiagnosisContent diagnosis={diagnosis} />
}

function DiagnosisSkeleton() {
  return (
    <div className="flex flex-col gap-4">
      <MetricRow>
        {[0, 1, 2].map((index) => (
          <div key={index} className="col-span-12 flex flex-col gap-1 sm:col-span-6 lg:col-span-3">
            <Skeleton className="h-8 w-16" />
            <Skeleton className="h-4 w-32" />
          </div>
        ))}
      </MetricRow>
      <div className="flex flex-col gap-2">
        {[0, 1, 2].map((index) => (
          <Skeleton key={index} className="h-8 rounded-lg" />
        ))}
      </div>
    </div>
  )
}

function DiagnosisContent({ diagnosis }: { diagnosis: FeedbackDiagnosisOut }) {
  const reference = `von ${formatCount(diagnosis.correction_count)} Korrekturen`

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3">
        <h3 className="text-base text-text-h">Motive, bei denen das Modell danebenlag</h3>
        <MetricRow>
          {diagnosis.motif_errors.map((entry) => (
            <Metric
              key={entry.case}
              data-motif-error-case={entry.case}
              data-count={entry.count}
              value={formatCount(entry.count)}
              label={MOTIF_ERROR_CASE_LABELS[entry.case]}
            >
              {/* Die Bezugsgröße ist die Gesamtzahl der Korrekturen, NICHT die Summe der drei
                  Fehlerfälle: Eine Korrektur ohne Modellfehler zählt in keinem von ihnen. */}
              <span className="text-xs text-text-muted">{reference}</span>
            </Metric>
          ))}
        </MetricRow>
      </div>
      <div className="flex flex-col gap-3">
        <h3 className="text-base text-text-h">Ausgetauschte Bilder</h3>
        <dl className="flex flex-col">
          {diagnosis.exchanges.map((entry) => {
            const note = exchangeQualityNote(entry)
            return (
              <DetailRow
                key={entry.kind}
                data-exchange-kind={entry.kind}
                data-count={entry.count}
                data-preferred-lower-rated-count={entry.preferred_lower_rated_count}
                term={EXCHANGE_KIND_LABELS[entry.kind]}
              >
                <span className="flex flex-col items-end gap-1 text-right">
                  <span>{formatCount(entry.count)}</span>
                  {note !== null && <span className="text-xs text-text-muted">{note}</span>}
                </span>
              </DetailRow>
            )
          })}
        </dl>
      </div>
    </div>
  )
}
