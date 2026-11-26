import type { ProjectStatsCostByPurpose, ProjectStatsOut } from '../api/types'
import { formatUsd } from '../utils/formatStats'
import { COST_PURPOSE_LABELS } from '../utils/statsLabels'
import { Metric, MetricRow, Section } from './StatsLayout'

/**
 * Hinweis samt Erlaeuterung. Bewusst dezent und
 * ohne Fehler-Rot: eine unvollstaendig erfasste Summe ist kein Fehler, sondern eine Einschraenkung
 * der Aussage.
 *
 * Die Erlaeuterung steht als Beschreibungstext direkt darunter statt in einem Info-Popover:
 * sie erscheint ohnehin nur im Ausnahmefall, und auf einer Seite zur Kostenkontrolle soll der
 * Vorbehalt nicht erst auf Klick sichtbar werden. Ein Popover je Zweck braeuchte zudem zwei
 * Ausloeser mit identischem Text.
 */
function IncompleteHint() {
  return (
    <>
      <span className="text-xs text-text">Summe unvollständig erfasst</span>
      <span className="text-xs text-text">
        Für mindestens einen Lauf dieses Zwecks liegen keine Verbrauchsdaten vor. Es wird bewusst
        nichts geschätzt — der angezeigte Betrag ist die Summe des tatsächlich Erfassten.
      </span>
    </>
  )
}

/**
 * `data-purpose` ist ein semantisches Testattribut nach Projektkonvention (Design-System,
 * "Selektor-Stabilitaet") - es macht pruefbar, dass der Hinweis GENAU beim betroffenen Zweck
 * steht und nicht bei einem unbetroffenen.
 */
function CostEntry({ entry }: { entry: ProjectStatsCostByPurpose }) {
  return (
    <div
      data-purpose={entry.purpose}
      className="flex flex-wrap items-start justify-between gap-2 border-b border-separator py-2 last:border-b-0"
    >
      <dt className="text-sm text-text">{COST_PURPOSE_LABELS[entry.purpose]}</dt>
      <dd className="flex max-w-md flex-col items-end gap-1 text-right">
        <span className="text-sm font-medium text-text-h">{formatUsd(entry.cost_usd)}</span>
        {entry.has_unrecorded_runs && <IncompleteHint />}
      </dd>
    </div>
  )
}

export function StatsCostSection({ cost }: { cost: ProjectStatsOut['cost'] }) {
  return (
    <Section id="stats-cost" title="Kosten für Remote-Berechnungen">
      <MetricRow>
        {/* Bewusst OHNE Erlaeuterung am Gesamtwert: der
          Vorbehalt gilt je Zweck, und der zugehoerige Textbaustein spricht ausdruecklich von
          "diesem Zweck" - an der zweckuebergreifenden Summe stuende er sachlich falsch und
          erschiene selbst dann, wenn beide Zwecke vollstaendig erfasst sind. Er sitzt
          stattdessen unmittelbar am betroffenen Einzelposten (siehe CostEntry). */}
        <Metric
          value={formatUsd(cost.total_usd)}
          label={`Gesamt in diesem Projekt (${cost.currency})`}
        />
      </MetricRow>
      <dl className="flex flex-col">
        {cost.by_purpose.map((entry) => (
          <CostEntry key={entry.purpose} entry={entry} />
        ))}
      </dl>
    </Section>
  )
}
