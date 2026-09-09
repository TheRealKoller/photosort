import type { ClassificationEstimateOut, ClassificationEstimatePartOut } from '../api/types'
import { formatProviderLabel } from '../utils/categoryLabels'
import { formatUsd } from '../utils/formatStats'

/**
 * Die aufgeschlüsselte Kostenvorschau vor dem Start (specs/features/0348-klassifizierungs-
 * transparenz.md, Abschnitt "Vor dem Start").
 *
 * Bleibt an ihrer bisherigen Stelle VOR dem Auslöser, damit die Kosten sichtbar sind, während der
 * Nutzer ihn betätigt - das Design-System-Muster "dauerhaft sichtbare Kostenschätzung am Auslöser"
 * statt eines Bestätigungsdialogs bleibt unverändert in Kraft.
 *
 * Die drei Unbekannt-Fälle werden ausdrücklich benannt statt als `0` dargestellt. Der wichtigste
 * ist der Landmark-Anteil vor dem ersten Durchlauf: eine bloße Leerstelle liest sich wie "fällt
 * nicht an", deshalb steht dort ein zweiter Satz, der das Gegenteil sagt.
 *
 * Beträge durchgängig über `formatStats.ts::formatUsd` (`1,23 USD`) - das frühere lokale
 * `$1.23`-Format ist entfallen. Zwei Formate direkt nebeneinander unterliefen das
 * Akzeptanzkriterium "tatsächliche Kosten gegen die Schätzung einordenbar", weil die Bilanz
 * dieselbe Formatierung trägt.
 */

const NO_PRICE_TEXT = 'kein Preis hinterlegt'

interface ClassificationEstimateProps {
  estimate: ClassificationEstimateOut
}

export function ClassificationEstimate({ estimate }: ClassificationEstimateProps) {
  const providerLabel = formatProviderLabel(estimate.provider)
  // "Alle Fotos bereits klassifiziert" darf NUR behauptet werden, wenn nichts offen UND nichts
  // unbekannt ist: bei unbekanntem Landmark-Anteil wäre es eine Zusage über eine Menge, die
  // niemand kennt - und genau diese Zusage kostet dann Geld.
  const everythingKnown =
    estimate.remote_categories.candidate_count !== null &&
    estimate.landmark.candidate_count !== null
  const nothingLeft = everythingKnown && estimate.candidate_count === 0

  return (
    <div
      data-testid="classification-estimate"
      className="flex w-full max-w-sm flex-col gap-1 text-sm"
    >
      <h3 className="text-sm font-semibold text-text-h">Kostenvorschau</h3>

      {nothingLeft ? (
        <p className="text-sm text-text">
          Alle Fotos bereits klassifiziert — keine Cloud-Kosten zu erwarten.
        </p>
      ) : (
        <>
          <EstimatePart
            id="remote_categories"
            label="Kategorie-Vorschläge"
            part={estimate.remote_categories}
          />
          <EstimatePart
            id="landmark"
            label="Sehenswürdigkeits-Erkennung"
            part={estimate.landmark}
            unknownHint="Menge noch unbekannt — für dieses Projekt gab es noch keinen Durchlauf. Dieser Anteil verursacht trotzdem Kosten."
          />
          <p className="flex items-baseline justify-between gap-3 border-t border-separator pt-1">
            <span className="font-semibold text-text-h">Gesamtsumme</span>
            <span className="shrink-0 font-semibold text-text-h">
              {estimate.estimated_cost_usd === null
                ? NO_PRICE_TEXT
                : formatUsd(estimate.estimated_cost_usd)}
            </span>
          </p>
        </>
      )}

      <p className="text-xs text-text-muted">
        {/* Reine Textknoten: `provider`/`model` sind Herstellerbezeichnungen aus der
            Server-Antwort, nie HTML. */}
        Grundlage: {providerLabel}, Modell {estimate.model}
      </p>
      {estimate.price_per_image_usd === null && (
        // Bewusst KEIN `Alert`: Alert ist im Projekt der Fehler-/Retry-Baustein, hier liegt kein
        // Ladefehler vor, sondern eine ehrliche Wissenslücke. Der Auslöser bleibt bedienbar - eine
        // Sperre bestrafte den Betreiber für einen Zustand, den er hier nicht auflösen kann.
        <p className="text-xs text-text-muted">
          Für dieses Modell ist kein Preis hinterlegt — die Kosten lassen sich nicht schätzen.
        </p>
      )}
      <p className="text-xs text-text-muted">
        Schätzung, keine Abrechnung — die tatsächlichen Kosten können abweichen. Beide Cloud-Anteile
        werden mit demselben Preis je Bild gerechnet.
      </p>
    </div>
  )
}

function EstimatePart({
  id,
  label,
  part,
  unknownHint,
}: {
  id: string
  label: string
  part: ClassificationEstimatePartOut
  unknownHint?: string
}) {
  return (
    <div data-testid={`classification-estimate-part-${id}`} className="flex flex-col">
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-sm text-text">{label}</span>
        {part.candidate_count !== null && (
          <span className="flex shrink-0 items-baseline gap-2">
            <span className="text-xs text-text-muted">{part.candidate_count} Fotos</span>
            <span className="text-sm text-text-h">
              {part.estimated_cost_usd === null
                ? NO_PRICE_TEXT
                : formatUsd(part.estimated_cost_usd)}
            </span>
          </span>
        )}
      </div>
      {part.candidate_count === null && unknownHint !== undefined && (
        <span className="text-xs text-text-muted">{unknownHint}</span>
      )}
    </div>
  )
}
