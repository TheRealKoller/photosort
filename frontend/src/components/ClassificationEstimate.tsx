import type { ClassificationEstimateOut, ClassificationEstimatePartOut } from '../api/types'
import { formatProviderLabel, formatUsd } from '../utils/formatStats'

/**
 * Die aufgeschlüsselte Kostenvorschau vor dem Start - JE WEG (`classification-estimate?mode=`).
 *
 * Bleibt an ihrer bisherigen Stelle VOR dem Auslöser, damit die Kosten sichtbar sind, während der
 * Nutzer ihn betätigt - das Design-System-Muster "dauerhaft sichtbare Kostenschätzung am Auslöser"
 * statt eines Bestätigungsdialogs bleibt unverändert in Kraft.
 *
 * WAS STATTFINDET, ENTSCHEIDET DER WEG, nicht die Zahl: `remote_categories` gehört nur zum
 * Cloud-Weg, die Sehenswürdigkeits-Erkennung zum Cloud-Weg und zum Eye-Weg MIT Einwilligung. Der
 * Server nennt in `mode` den Weg und in den Anteilen die Mengen; welche Anteile überhaupt laufen,
 * sagt ihm die Oberfläche über `landmarkParticipates` zurück, weil `candidate_count === null` für
 * "unbekannte Menge" UND für "findet nicht statt" stehen kann - beides `null`, aber nur das erste
 * ist eine Aussage über Kosten.
 *
 * Ein Weg ganz ohne Kosten zeigt EINE Zeile: „Dieser Durchlauf ist kostenfrei." — das Wort, nie
 * „0,00 USD" (S7). Einzelne kostenfreie Anteile tragen dasselbe Wort.
 *
 * Beträge durchgängig über `formatStats.ts::formatUsd` (`1,23 USD`) - die Bilanz trägt dieselbe
 * Formatierung.
 */

const NO_PRICE_TEXT = 'kein Preis hinterlegt'
const FREE_TEXT = 'kostenfrei'

interface ClassificationEstimateProps {
  estimate: ClassificationEstimateOut
  /** Findet die Sehenswürdigkeits-Erkennung in diesem Durchlauf statt? Cloud: immer. Eye: nur mit
   * Einwilligung. Lokal: nie. */
  landmarkParticipates: boolean
}

function formatPartCost(part: ClassificationEstimatePartOut): string {
  if (part.estimated_cost_usd === null) {
    return NO_PRICE_TEXT
  }
  // `0.0` heisst "es faellt nichts an" - als Wort, nie als Betrag.
  return part.estimated_cost_usd === 0 ? FREE_TEXT : formatUsd(part.estimated_cost_usd)
}

export function ClassificationEstimate({
  estimate,
  landmarkParticipates,
}: ClassificationEstimateProps) {
  const providerLabel = formatProviderLabel(estimate.provider)
  const showsRemoteCategories = estimate.mode === 'cloud'
  const showsLandmark = landmarkParticipates
  // Nur die Anteile, die in DIESEM Durchlauf laufen, zaehlen fuer Summe und Unbekannt-Hinweis.
  const parts = [
    showsRemoteCategories ? estimate.remote_categories : null,
    showsLandmark ? estimate.landmark : null,
  ].filter((part): part is ClassificationEstimatePartOut => part !== null)
  // "Alle Fotos bereits klassifiziert" darf NUR behauptet werden, wenn nichts offen UND nichts
  // unbekannt ist: bei unbekanntem Anteil wäre es eine Zusage über eine Menge, die niemand kennt -
  // und genau diese Zusage kostet dann Geld.
  const everythingKnown = parts.every((part) => part.candidate_count !== null)
  const nothingLeft = parts.length > 0 && everythingKnown && estimate.candidate_count === 0

  return (
    <div
      data-testid="classification-estimate"
      className="flex w-full max-w-sm flex-col gap-1 text-sm"
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
          {showsRemoteCategories && (
            <EstimatePart
              id="remote_categories"
              label="Kategorie-Vorschläge"
              part={estimate.remote_categories}
            />
          )}
          {showsLandmark && (
            <EstimatePart
              id="landmark"
              label="Sehenswürdigkeits-Erkennung"
              part={estimate.landmark}
              unknownHint="Menge noch unbekannt — für dieses Projekt gab es noch keinen Durchlauf. Dieser Anteil verursacht trotzdem Kosten."
            />
          )}
          <p className="flex items-baseline justify-between gap-3 border-t border-separator pt-1">
            {/* Ist ein Anteil unbekannt, ist die Summe nur eine UNTERE SCHRANKE. Sie
                unbeschriftet als "Gesamtsumme" zu zeigen, wäre genau die Fehlaussage, gegen die
                diese Anzeige antritt - nur eine Zeile tiefer als die `0`, die sie oben schon
                vermeidet. */}
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
        </>
      )}

      {/* Anbieter, Modell und Preisgrundlage stehen NUR am Cloud-Weg: beim Eye- und beim lokalen
          Weg gibt es keinen Anbieter, dessen Preis hier genannt werden dürfte. */}
      {showsRemoteCategories && (
        <>
          <p className="text-xs text-text-muted">
            {/* Reine Textknoten: `provider`/`model` sind Herstellerbezeichnungen aus der
                Server-Antwort, nie HTML. */}
            Grundlage: {providerLabel}, Modell {estimate.model}
          </p>
          {estimate.price_per_image_usd === null && (
            // Bewusst KEIN `Alert`: Alert ist im Projekt der Fehler-/Retry-Baustein, hier liegt
            // kein Ladefehler vor, sondern eine ehrliche Wissenslücke. Der Auslöser bleibt
            // bedienbar - eine Sperre bestrafte den Betreiber für einen Zustand, den er hier
            // nicht auflösen kann.
            <p className="text-xs text-text-muted">
              Für dieses Modell ist kein Preis hinterlegt — die Kosten lassen sich nicht schätzen.
            </p>
          )}
          <p className="text-xs text-text-muted">
            Schätzung, keine Abrechnung — die tatsächlichen Kosten können abweichen. Beide
            Cloud-Anteile werden mit demselben Preis je Bild gerechnet.
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
            <span className="text-sm text-text-h">{formatPartCost(part)}</span>
          </span>
        )}
      </div>
      {part.candidate_count === null && unknownHint !== undefined && (
        <span className="text-xs text-text-muted">{unknownHint}</span>
      )}
    </div>
  )
}
