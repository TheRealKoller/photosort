import type { ClassificationEstimateOut, ClassificationEstimatePartOut } from '../api/types'
import { formatProviderLabel, formatUsd, formatUsdPerImage } from '../utils/formatStats'

/**
 * Die Kostenvorschau vor dem Start - JE ANTEIL, nicht mehr je Weg (Spec 0383, ADR 0143).
 *
 * Jeder Anteil nennt seine Tätigkeit, die Menge, den Betrag und darunter die GRUNDLAGE (Anbieter
 * und Modell bzw. „Eye, auf diesem Server"). Ein `null`-Anteil heißt „findet nicht statt" und wird
 * als Satz gezeigt, nie als Zeile mit `0`. Damit ist „angezeigt = aufgerufen = abgerechnet" auch
 * dann lesbar, wenn die beiden Tätigkeiten verschiedene Modelle tragen - der frühere Satz „Beide
 * Cloud-Anteile werden mit demselben Preis je Bild gerechnet" wäre genau dann falsch und entfällt
 * deshalb ersatzlos.
 *
 * DREI Zustände, die auseinandergehalten werden müssen:
 *  - `candidate_count` bekannt und `estimated_cost_usd === 0` → das Wort „kostenfrei",
 *  - `candidate_count` bekannt und kein Preis hinterlegt → „kein Preis hinterlegt",
 *  - `candidate_count === null` → die MENGE ist unbekannt. Dann fällt die Mengenangabe weg
 *    („ Fotos" wäre keine Aussage) und die Summe heißt „Mindestens", weil sie nur die bekannten
 *    Anteile zählt.
 *
 * Ein Durchlauf ganz ohne Anteile zeigt EINE Zeile: „Dieser Durchlauf ist kostenfrei." — das Wort,
 * nie „0,00 USD". „Alle Fotos bereits klassifiziert" behauptet die Anzeige NUR, wenn nichts offen
 * UND nichts unbekannt ist: bei unbekanntem Anteil wäre es eine Zusage über eine Menge, die
 * niemand kennt - und genau diese Zusage kostet dann Geld.
 *
 * Beträge durchgängig über `formatStats.ts::formatUsd` (`1,23 USD`) - die Bilanz trägt dieselbe
 * Formatierung. Der Preis je Bild kommt aus `formatUsdPerImage` (mindestens vier
 * Nachkommastellen), weil `formatUsd` jedes Modell unter einem Cent zu „< 0,01 USD" machte.
 */

const NO_PRICE_TEXT = 'kein Preis hinterlegt'
const FREE_TEXT = 'kostenfrei'
const EYE_BASIS = 'Eye, auf diesem Server'
const UNKNOWN_COUNT_HINT =
  'Menge noch unbekannt — für dieses Projekt gab es noch keinen Durchlauf. Dieser Anteil verursacht trotzdem Kosten.'

interface ClassificationEstimateProps {
  estimate: ClassificationEstimateOut
}

function formatPartCost(part: ClassificationEstimatePartOut): string | null {
  if (part.estimated_cost_usd === null) {
    // Unbekannte Menge ist keine fehlende Preisangabe - der Hinweis darunter sagt es genauer.
    return part.candidate_count === null ? null : NO_PRICE_TEXT
  }
  // `0.0` heisst "es faellt nichts an" - als Wort, nie als Betrag.
  return part.estimated_cost_usd === 0 ? FREE_TEXT : formatUsd(part.estimated_cost_usd)
}

function partBasis(part: ClassificationEstimatePartOut): string {
  if (part.kind === 'eye') {
    return EYE_BASIS
  }
  const provider =
    part.provider === null ? 'Unbekannter Anbieter' : formatProviderLabel(part.provider)
  const model = part.model === null ? 'unbekanntes Modell' : part.model
  return `${provider}, ${model} · ${formatUsdPerImage(part.price_per_image_usd)}`
}

export function ClassificationEstimate({ estimate }: ClassificationEstimateProps) {
  const parts = [estimate.categorization, estimate.landmark].filter(
    (part): part is ClassificationEstimatePartOut => part !== null,
  )
  const everythingKnown = parts.every((part) => part.candidate_count !== null)
  const nothingLeft = parts.length > 0 && everythingKnown && estimate.candidate_count === 0

  return (
    <div
      data-testid="classification-estimate"
      className="flex w-full max-w-sm flex-col gap-2 text-sm"
    >
      <h3 className="text-sm font-semibold text-text-h">Kostenvorschau</h3>

      {parts.length === 0 ? (
        <p className="text-sm text-text">Dieser Durchlauf ist kostenfrei.</p>
      ) : nothingLeft ? (
        <p className="text-sm text-text">
          Alle Fotos bereits klassifiziert — keine Cloud-Kosten zu erwarten.
        </p>
      ) : (
        <>
          {estimate.categorization !== null && (
            <EstimatePart
              id="categorization"
              label="Kategorisierung"
              part={estimate.categorization}
            />
          )}
          {estimate.landmark !== null && (
            <EstimatePart
              id="landmark"
              label="Sehenswürdigkeits-Erkennung"
              part={estimate.landmark}
            />
          )}
          {estimate.categorization === null && (
            <p className="text-xs text-text-muted">
              Die Kategorisierung findet in diesem Durchlauf nicht statt.
            </p>
          )}
          {estimate.landmark === null && (
            <p className="text-xs text-text-muted">
              Die Sehenswürdigkeits-Erkennung findet in diesem Durchlauf nicht statt.
            </p>
          )}
          <p className="flex items-baseline justify-between gap-3 border-t border-separator pt-1">
            {/* Ist ein Anteil unbekannt, ist die Summe nur eine UNTERE SCHRANKE. Sie unbeschriftet
                als "Gesamtsumme" zu zeigen, waere genau die Fehlaussage, gegen die diese Anzeige
                antritt. */}
            <span className="font-semibold text-text-h">
              {everythingKnown ? 'Gesamtsumme' : 'Mindestens'}
            </span>
            <span className="shrink-0 font-semibold text-text-h">
              {estimate.estimated_cost_usd === null
                ? NO_PRICE_TEXT
                : estimate.estimated_cost_usd === 0
                  ? FREE_TEXT
                  : formatUsd(estimate.estimated_cost_usd)}
            </span>
          </p>
          {!everythingKnown && (
            <p className="text-xs text-text-muted">
              Ein Anteil ist noch unbekannt — der tatsächliche Betrag liegt höher.
            </p>
          )}
          <p className="text-xs text-text-muted">
            Schätzung, keine Abrechnung — die tatsächlichen Kosten können abweichen.
          </p>
        </>
      )}
    </div>
  )
}

function EstimatePart({
  id,
  label,
  part,
}: {
  id: string
  label: string
  part: ClassificationEstimatePartOut
}) {
  const cost = formatPartCost(part)
  return (
    <div data-testid={`classification-estimate-part-${id}`} className="flex flex-col gap-1">
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-sm text-text">{label}</span>
        <span className="flex shrink-0 items-baseline gap-2">
          {part.candidate_count !== null && (
            <span className="text-xs text-text-muted">{part.candidate_count} Fotos</span>
          )}
          {cost !== null && <span className="text-sm text-text-h">{cost}</span>}
        </span>
      </div>
      {part.candidate_count === null && (
        <span className="text-xs text-text-muted">{UNKNOWN_COUNT_HINT}</span>
      )}
      <span className="text-xs text-text-muted">{partBasis(part)}</span>
    </div>
  )
}
