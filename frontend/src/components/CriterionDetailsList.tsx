import type { CriterionScoreOut, RankingOut, SuggestionOut } from '../api/types'
import { formatCategoryKey } from '../utils/categoryLabels'
import { formatSuggestionReason, formatSuggestionStatusLabel } from '../utils/suggestionLabels'

interface CriterionDetailsListProps {
  criterionScores: CriterionScoreOut[]
  ranking: RankingOut | null
  suggestion: SuggestionOut | null
  // Blendet die Ausschuss-Gruppe unbedingt aus, unabhaengig von `suggestion` (Akzeptanzkriterium
  // 6, specs/features/0041-bewertungsdetails-permanent-in-detailansicht-hover-auto-close.md) -
  // die permanente Sektion in PhotoDetailPage.tsx reicht `suggestion` zwar ohnehin nicht durch,
  // dieses Flag ist trotzdem die alleinige, direkt getestete Absicherung gegen ein versehentliches
  // kuenftiges Durchreichen.
  showSuggestion: boolean
}

// Kaufmaennisch gerundete Prozentzahl ohne Nachkommastelle (Akzeptanzkriterium 9 der Spec 0040) -
// vermeidet eine Scheingenauigkeit, die die zugrundeliegenden, teils heuristischen Scores nicht
// hergeben. Kriterien-Werte sind immer bereits auf [0, 1] normiert (backend criteria.py), also nie
// negativ - Math.round rundet in diesem Bereich identisch zu "kaufmaennisch" (0.5 aufwaerts).
function formatCriterionPercent(value: number): string {
  return `${Math.round(value * 100)}%`
}

/**
 * Reine Praesentationskomponente mit den Bewertungsdetails eines Fotos - extrahiert aus dem
 * bisher inline in CriterionDetailsPopover.tsx liegenden `<dl>`-Markup
 * (specs/features/0041-bewertungsdetails-permanent-in-detailansicht-hover-auto-close.md,
 * Architektur-Abschnitt), damit sowohl das Popover (Grid/Kuratierung) als auch die permanente
 * Sektion in PhotoDetailPage.tsx dieselbe Darstellung/Formatierungslogik teilen (DRY,
 * Akzeptanzkriterium 5/13). Rendert unveraendert nichts, wenn criterionScores leer ist - diese
 * Entscheidung bleibt bei den jeweiligen Aufrufern (Popover-Sichtbarkeit vs. permanente Sektion),
 * nicht hier, da beide Stellen die gleiche Bedingung ohnehin schon selbst pruefen muessen (Popover
 * fuer den Trigger, PhotoDetailPage.tsx fuer den Abschnitts-Rahmen).
 */
export function CriterionDetailsList({
  criterionScores,
  ranking,
  suggestion,
  showSuggestion,
}: CriterionDetailsListProps) {
  return (
    <dl className="flex flex-col gap-3">
      <div className="flex flex-col gap-1.5">
        {criterionScores.map((score) => (
          <div key={score.criterion_key} className="flex items-baseline justify-between gap-3">
            <dt className="text-text">{score.display_name}</dt>
            <dd className="font-medium text-text-h">{formatCriterionPercent(score.value)}</dd>
          </div>
        ))}
      </div>
      {ranking !== null && (
        <div className="flex flex-col gap-1.5">
          <div className="flex items-baseline justify-between gap-3">
            <dt className="text-text">Kategorie</dt>
            <dd className="font-medium text-text-h">{formatCategoryKey(ranking.category_key)}</dd>
          </div>
          <div className="flex items-baseline justify-between gap-3">
            <dt className="text-text">Rang</dt>
            <dd className="font-medium text-text-h">
              Rang {ranking.rank_position} von {ranking.partition_size}
            </dd>
          </div>
        </div>
      )}
      {showSuggestion && suggestion !== null && (
        <div className="flex flex-col gap-1.5">
          <div className="flex items-baseline justify-between gap-3">
            <dt className="text-text">Ausschuss-Vorschlag</dt>
            <dd className="font-medium text-text-h">{formatSuggestionStatusLabel(suggestion)}</dd>
          </div>
          <div className="flex items-baseline justify-between gap-3">
            <dt className="text-text">Grund</dt>
            <dd className="font-medium text-text-h">{formatSuggestionReason(suggestion)}</dd>
          </div>
        </div>
      )}
    </dl>
  )
}
