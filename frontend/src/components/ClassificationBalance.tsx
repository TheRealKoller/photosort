import type { CloudPhaseSummaryOut, CriterionScoringRunSummary } from '../api/types'
import { formatCount, formatUsd } from '../utils/formatStats'

/**
 * Die Bilanz des zuletzt abgeschlossenen Durchlaufs (specs/features/0348-klassifizierungs-
 * transparenz.md, Abschnitt "Nach dem Lauf").
 *
 * Tritt an die Stelle der Teilschrittliste, sobald der Lauf beendet ist, und beschreibt
 * AUSSCHLIESSLICH diesen einen Durchlauf - eine Historie früherer Läufe entsteht dadurch
 * ausdrücklich nicht (die projektweite Auswertung bleibt die Statistikseite).
 *
 * DER PREIS JE BILD ERSCHEINT HIER NICHT. Er ist die Grundlage der SCHÄTZUNG; der Ist-Betrag
 * entsteht über den tatsächlichen Tokenverbrauch. Ihn in der Bilanz zu nennen behauptete eine
 * Rechnung, die so nie stattgefunden hat - deshalb stehen hier Modell und Tokenverbrauch.
 *
 * `null` bleibt `null`: "kein Preis hinterlegt" statt eines Betrags, "unvollständig" statt einer
 * Summe. Ein stilles "0,00 USD" tarnte einen kostenpflichtigen Lauf als kostenlos.
 */

const PHASE_LABELS: Record<CloudPhaseSummaryOut['purpose'], string> = {
  remote_category: 'Kategorie-Vorschläge',
  landmark: 'Sehenswürdigkeits-Erkennung',
}

interface ClassificationBalanceProps {
  run: CriterionScoringRunSummary
}

export function ClassificationBalance({ run }: ClassificationBalanceProps) {
  return (
    <div
      data-testid="classification-balance"
      className="flex w-full max-w-sm flex-col gap-2 text-sm"
    >
      <h3 className="text-sm font-semibold text-text-h">Ergebnis dieses Durchlaufs</h3>

      {run.cloud_phases.length > 0 ? (
        <>
          {run.cloud_phases.map((phase) => (
            <CloudPhaseRow key={phase.purpose} phase={phase} />
          ))}
          <p className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 border-t border-separator pt-1">
            <span className="font-semibold text-text-h">Kosten dieses Durchlaufs</span>
            <span className="shrink-0 font-semibold text-text-h">
              {run.cloud_cost_total_usd === null
                ? 'unvollständig'
                : formatUsd(run.cloud_cost_total_usd)}
            </span>
          </p>
          {run.estimated_cost_usd !== null && (
            <p className="text-xs text-text-muted">
              Vor dem Start geschätzt: {formatUsd(run.estimated_cost_usd)}
            </p>
          )}
        </>
      ) : run.cloud_requested ? (
        // Fall (C): Altlauf ohne erfasste Bilanz, oder eine zwischen Auslösen und Start entzogene
        // Einwilligung. Eine ehrliche Aussage statt erfundener Zahlen - es ist nicht nachholbar
        // und heilt mit dem nächsten Lauf.
        <p className="text-sm text-text">Für diesen Durchlauf wurde keine Cloud-Bilanz erfasst.</p>
      ) : (
        // Fall (B): bewusst KEIN Fehler-Styling und keine leere Tabelle - ein rein lokaler
        // Durchlauf ist ein gewünschtes Ergebnis.
        <p className="text-sm text-text">
          Ohne Cloud-Anreicherung durchgeführt — es wurden keine Fotos an einen Anbieter gesendet.
        </p>
      )}
    </div>
  )
}

function CloudPhaseRow({ phase }: { phase: CloudPhaseSummaryOut }) {
  return (
    <div
      data-testid={`classification-balance-phase-${phase.purpose}`}
      className="flex flex-col gap-1 border-t border-separator pt-1"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <span className="text-sm text-text-h">{PHASE_LABELS[phase.purpose]}</span>
        <span className="text-xs text-text-muted">
          {countOrDash(phase.photos_total)} Fotos gesendet · {countOrDash(phase.responses_used)}{' '}
          Antworten verwertet
        </span>
      </div>
      <p className="text-xs text-text-muted">
        {countOrDash(phase.failed_calls)} fehlgeschlagen ·{' '}
        {phase.cost_usd === null ? 'kein Preis hinterlegt' : formatUsd(phase.cost_usd)}
        {/* Grundlage des Betrags: Modell und abgerechneter Tokenverbrauch - reine Textknoten,
            nie HTML. Ohne sie stünde der Betrag unerklärt da. */}
        {phase.model !== null && ` · Modell ${phase.model}`} · {countOrDash(phase.input_tokens)}{' '}
        Eingabe-/{countOrDash(phase.output_tokens)} Ausgabe-Tokens
      </p>
    </div>
  )
}

/** `null` heisst "nicht erfasst" und wird als Strich gezeigt - nie als `0`. */
function countOrDash(value: number | null): string {
  return value === null ? '—' : formatCount(value)
}
