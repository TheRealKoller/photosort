import { useState } from 'react'

import { ApiError } from '../api/client'
import type { FeedbackDiagnosisOut } from '../api/types'
import {
  useAdoptFeedbackWeightsMutation,
  useFeedbackDiagnosisQuery,
  useRevertFeedbackWeightsMutation,
} from '../hooks/useFeedbackDiagnosis'
import {
  EXCHANGE_KIND_LABELS,
  MOTIF_ERROR_CASE_LABELS,
  exchangeQualityNote,
  hasCorrections,
} from '../utils/feedbackDiagnosis'
import { formatDelta, formatWeight, weightRows } from '../utils/feedbackWeights'
import type { WeightRow } from '../utils/feedbackWeights'
import { NOT_AVAILABLE, formatCount } from '../utils/formatStats'
import { DetailRow, Metric, MetricRow, Section } from './StatsLayout'
import { Alert } from './ui/alert'
import { Button } from './ui/button'
import { Dialog } from './ui/dialog'
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
      <WeightSection diagnosis={diagnosis} />
    </div>
  )
}

/**
 * Die Gewichts-Vorschau samt Handlungsbereich.
 *
 * DIE BELASTBARKEIT TRÄGT ALLEIN DIE SICHTBARE FALLZAHL - keine Fettschrift-Schwelle, die eine
 * Belastbarkeitsgrenze behauptete, die niemand festgelegt hat. Die Zustimmungsrate steht bewusst
 * nicht daneben: Fallzahl und Abweichung tragen die Aussage bereits, eine dritte Zahl zur selben
 * Sache würde gegen die Abweichung gelesen, aus der sie stammt.
 */
function WeightSection({ diagnosis }: { diagnosis: FeedbackDiagnosisOut }) {
  const [isDialogOpen, setDialogOpen] = useState(false)
  const [confirmation, setConfirmation] = useState<string | null>(null)
  const adopt = useAdoptFeedbackWeightsMutation()
  const revert = useRevertFeedbackWeightsMutation()
  const rows = weightRows(diagnosis)
  const isPending = adopt.isPending || revert.isPending
  const failure = adopt.error ?? revert.error

  function handleAdopt(): void {
    setConfirmation(null)
    adopt.mutate(diagnosis.weights.based_on_event_id, {
      onSuccess: () => {
        setDialogOpen(false)
        setConfirmation('Die Gewichte wurden übernommen.')
      },
      onError: () => {
        setDialogOpen(false)
      },
    })
  }

  function handleRevert(): void {
    const setId = diagnosis.weights.current_set_id
    if (setId === null) {
      return
    }
    setConfirmation(null)
    revert.mutate(setId, {
      onSuccess: () => {
        setConfirmation('Die vorigen Gewichte gelten wieder.')
      },
    })
  }

  return (
    <div className="flex flex-col gap-3">
      <h3 className="text-base text-text-h">Gewichte der Qualitätskriterien</h3>
      {/* Eigener Scroll-Container statt einer umstrukturierten Darstellung: Vier Zahlenspalten
          nebeneinander sind bei 360px schmal, aber lesbar - als Kartenliste verlören sie die
          Achse, auf der sie verglichen werden. */}
      <div className="overflow-x-auto">
        <table className="w-full min-w-80 border-collapse text-sm">
          <caption className="sr-only">
            Geltendes Gewicht, Vorschlag, Abweichung und Fallzahl je Qualitätskriterium
          </caption>
          <thead>
            <tr className="border-b border-separator text-xs font-semibold tracking-wide text-text-muted uppercase">
              <th scope="col" className="py-2 text-left">
                Kriterium
              </th>
              <th scope="col" className="py-2 text-right">
                Geltend
              </th>
              <th scope="col" className="py-2 text-right">
                Vorschlag
              </th>
              <th scope="col" className="py-2 text-right">
                Abweichung
              </th>
              <th scope="col" className="py-2 text-right">
                Fälle
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <WeightTableRow key={row.criterionKey} row={row} />
            ))}
          </tbody>
        </table>
      </div>
      {confirmation !== null && (
        <p data-testid="feedback-weights-confirmation" className="text-sm text-accent-2">
          {confirmation}
        </p>
      )}
      {failure !== null && (
        // Der Träger der Kennung steht AUSSEN: `Alert` reicht keine eigenen Attribute durch, und
        // sie ihm dafür beizubringen änderte ein geteiltes Grundelement für einen Testselektor.
        //
        // Kein `onRetry`: Die Schaltfläche darunter IST die Wiederholung. Im `409`-Fall wäre sie
        // sogar die falsche Aktion - dann muss erst der neue Stand geladen werden, und genau das
        // sagt der Text des Servers.
        <div data-testid="feedback-weights-error">
          <Alert title="Anpassung nicht möglich">
            {failure instanceof ApiError
              ? failure.detail
              : 'Die Gewichte konnten nicht geändert werden. Bitte versuche es erneut.'}
          </Alert>
        </div>
      )}
      {/* Ohne diesen Satz erwartet jeder eine sofortige Änderung seines offenen Entwurfs. */}
      <p data-testid="feedback-weights-effect-hint" className="text-xs text-text-muted">
        Eine Anpassung wirkt erst beim nächsten Durchlauf der Bewertung — die aktuellen Entwürfe und
        Reihenfolgen bleiben unverändert.
      </p>
      <div className="flex flex-col gap-3 sm:flex-row">
        <Button
          type="button"
          className="tap-target"
          disabled={isPending}
          onClick={() => {
            setDialogOpen(true)
          }}
        >
          Gewichte anpassen
        </Button>
        {diagnosis.weights.can_revert && (
          <Button
            type="button"
            variant="secondary"
            className="tap-target"
            busy={revert.isPending}
            disabled={adopt.isPending}
            onClick={handleRevert}
          >
            Auf vorige Gewichte zurücksetzen
          </Button>
        )}
      </div>
      <Dialog
        open={isDialogOpen}
        onClose={() => {
          if (!adopt.isPending) {
            setDialogOpen(false)
          }
        }}
        title="Gewichte anpassen?"
        description="Die Anpassung wirkt erst beim nächsten Durchlauf der Bewertung."
        cancelDisabled={adopt.isPending}
        actions={
          <Button type="button" busy={adopt.isPending} onClick={handleAdopt}>
            Anpassen
          </Button>
        }
      >
        {/* Die VERKÜRZTE Gegenüberstellung - Kriterium, geltend, neu. Sie ist die Einlösung von
            „vor dem Auslösen ist erkennbar, was sich ändert"; die Fallzahl steht in der Tabelle
            dahinter und wäre hier eine vierte Spalte ohne Entscheidungswert. */}
        <table className="w-full border-collapse text-sm">
          <caption className="sr-only">Geltendes und neues Gewicht je Kriterium</caption>
          <thead>
            <tr className="border-b border-separator text-xs font-semibold tracking-wide text-text-muted uppercase">
              <th scope="col" className="py-2 text-left">
                Kriterium
              </th>
              <th scope="col" className="py-2 text-right">
                Geltend
              </th>
              <th scope="col" className="py-2 text-right">
                Neu
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.criterionKey}
                data-dialog-criterion-key={row.criterionKey}
                className="border-b border-separator last:border-b-0"
              >
                <th scope="row" className="py-2 text-left font-normal text-text">
                  {row.displayName}
                </th>
                <td className="py-2 text-right font-mono text-text">{formatWeight(row.current)}</td>
                <td className="py-2 text-right font-mono text-text-h">
                  {row.proposed === null ? NOT_AVAILABLE : formatWeight(row.proposed)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Dialog>
    </div>
  )
}

function WeightTableRow({ row }: { row: WeightRow }) {
  return (
    <tr
      data-criterion-key={row.criterionKey}
      data-current={row.current}
      data-proposed={row.proposed ?? undefined}
      data-delta={row.delta ?? undefined}
      data-case-count={row.caseCount}
      className="border-b border-separator last:border-b-0"
    >
      <th scope="row" className="py-2 text-left font-normal text-text">
        {row.displayName}
      </th>
      <td className="py-2 text-right font-mono text-text">{formatWeight(row.current)}</td>
      <td className="py-2 text-right font-mono text-text-h">
        {row.proposed === null ? NOT_AVAILABLE : formatWeight(row.proposed)}
      </td>
      {/* Die Richtung steht im VORZEICHEN, nicht in einer Einfärbung - keine Aussage allein über
          Farbe. */}
      <td className="py-2 text-right font-mono text-text">
        {row.delta === null ? NOT_AVAILABLE : formatDelta(row.delta)}
      </td>
      <td className="py-2 text-right font-mono text-text-muted">{formatCount(row.caseCount)}</td>
    </tr>
  )
}
