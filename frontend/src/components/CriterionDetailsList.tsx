import type { CategoryCandidateOut, CategoryKey, CriterionScoreOut, RankingOut, SuggestionOut } from '../api/types'
import { formatCategoryKey, formatProviderLabel } from '../utils/categoryLabels'
import { formatSuggestionReason, formatSuggestionStatusLabel } from '../utils/suggestionLabels'
import { Badge } from './ui/badge'
import { Button } from './ui/button'

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
  // specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md, UI/UX-Abschnitt
  // "Mehrfachkandidaten-Vergleich mit Override-Aktion" - alle sechs Props sind optional mit
  // neutralen Defaults, damit bestehende Aufrufer (die diese Props noch nicht kennen) unveraendert
  // weiterlaufen (Regressionspflicht): mit dem Default `categoryCandidates=[]` bleibt die neue
  // Gruppe immer ausgeblendet (0 <= 1 Kandidat), die bisherige einzeilige "Kategorie"-Anzeige
  // bleibt unveraendert sichtbar.
  categoryCandidates?: CategoryCandidateOut[]
  categoryOverride?: CategoryKey | null
  onOverrideCategory?: (categoryKey: CategoryKey) => void
  onResetOverride?: () => void
  /** Der `category_key`, dessen "Übernehmen"-Button gerade eine laufende Anfrage hat - nur DIESER
   * eine Button wird disabled, der Rest der Liste bleibt bedienbar (Design-System: "blockiert
   * nicht die uebrige Liste"). */
  pendingOverrideKey?: CategoryKey | null
  /** Ob die "Zuruecksetzen"-Anfrage fuer den aktuellen Override-Ziel-Kandidaten laeuft - es gibt
   * nur genau ein Override-Ziel gleichzeitig, deshalb reicht ein einzelnes Flag statt eines Keys. */
  resetPending?: boolean
}

// Kaufmaennisch gerundete Prozentzahl ohne Nachkommastelle (Akzeptanzkriterium 9 der Spec 0040) -
// vermeidet eine Scheingenauigkeit, die die zugrundeliegenden, teils heuristischen Scores nicht
// hergeben. Kriterien-Werte sind immer bereits auf [0, 1] normiert (backend criteria.py), also nie
// negativ - Math.round rundet in diesem Bereich identisch zu "kaufmaennisch" (0.5 aufwaerts).
function formatCriterionPercent(value: number): string {
  return `${Math.round(value * 100)}%`
}

interface CategoryCandidateRow extends CategoryCandidateOut {
  /** Ein aktiver Override, dessen Ziel-Kandidat in der aktuellen Kandidatenliste nicht (mehr)
   * auftaucht (z.B. nach einem neuen Scoring-Lauf mit geaenderten lokalen Werten) - wird als
   * zusaetzliche Zeile am Ende angehaengt statt zu verschwinden (Design-System: "Verlaesslichkeit
   * statt Onboarding"). Hat keinen sinnvollen Score/keine Herkunft, beides wird fuer diese Zeile
   * nicht angezeigt. */
  isOrphan?: boolean
}

function buildCategoryCandidateRows(
  categoryCandidates: CategoryCandidateOut[],
  categoryOverride: CategoryKey | null
): CategoryCandidateRow[] {
  // Review-Fund (test-engineer): expliziter Sekundaer-Schluessel statt eines impliziten Verlasses
  // auf Sortier-Stabilitaet - Score/Konfidenz absteigend, bei Gleichstand alphabetisch nach
  // category_key (dieselbe Tie-Break-Regel wie backend api/photos.py::_category_candidates_out).
  const rows: CategoryCandidateRow[] = [...categoryCandidates].sort(
    (a, b) => b.score - a.score || a.category_key.localeCompare(b.category_key)
  )
  const overrideIsOrphan =
    categoryOverride !== null && !categoryCandidates.some((c) => c.category_key === categoryOverride)
  if (overrideIsOrphan) {
    rows.push({ category_key: categoryOverride, origin: 'local', score: 0, provider: null, isOrphan: true })
  }
  return rows
}

/**
 * Reine Praesentationskomponente mit den Bewertungsdetails eines Fotos - extrahiert aus dem
 * bisher inline in CriterionDetailsPopover.tsx liegenden `<dl>`-Markup
 * (specs/features/0041-bewertungsdetails-permanent-in-detailansicht-hover-auto-close.md,
 * Architektur-Abschnitt), damit sowohl das Popover (Grid/Kuratierung) als auch die permanente
 * Sektion in PhotoDetailPage.tsx dieselbe Darstellung/Formatierungslogik teilen (DRY,
 * Akzeptanzkriterium 5/13). Prueft selbst NICHT, ob `criterionScores` leer ist, und rendert in
 * diesem Fall unveraendert ein leeres `<dl>` - die Entscheidung, den Bereich bei leerer Liste gar
 * nicht erst einzubinden, bleibt bewusst bei den jeweiligen Aufrufern (Popover-Sichtbarkeit vs.
 * permanente Sektion), da beide Stellen die gleiche Bedingung ohnehin schon selbst pruefen muessen
 * (Popover fuer den Trigger, PhotoDetailPage.tsx fuer den Abschnitts-Rahmen). Copilot-Review-Fund
 * auf PR #103: eine fruehere Fassung dieses Kommentars behauptete faelschlich, die Komponente
 * selbst rendere bei leerer Liste nichts.
 */
export function CriterionDetailsList({
  criterionScores,
  ranking,
  suggestion,
  showSuggestion,
  categoryCandidates = [],
  categoryOverride = null,
  onOverrideCategory,
  onResetOverride,
  pendingOverrideKey = null,
  resetPending = false,
}: CriterionDetailsListProps) {
  const candidateRows = buildCategoryCandidateRows(categoryCandidates, categoryOverride)
  const showCandidateGroup = candidateRows.length > 1

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
          {showCandidateGroup ? (
            <div className="flex flex-col gap-2">
              <dt className="text-text">Kategorie-Kandidaten</dt>
              <dd>
                <ul className="flex flex-col gap-2">
                  {candidateRows.map((row) => {
                    const isEffective = !row.isOrphan && ranking.category_key === row.category_key
                    const isOverrideTarget = categoryOverride === row.category_key
                    const isPending = pendingOverrideKey === row.category_key
                    return (
                      <li
                        key={row.category_key}
                        data-testid={`category-candidate-row-${row.category_key}`}
                        className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border p-2"
                      >
                        <div className="flex flex-wrap items-baseline gap-2">
                          <span className="font-medium text-text-h">
                            {formatCategoryKey(row.category_key)}
                          </span>
                          {!row.isOrphan && (
                            <>
                              <Badge tone="neutral">
                                {row.origin === 'remote' && row.provider
                                  ? formatProviderLabel(row.provider)
                                  : 'Lokal erkannt'}
                              </Badge>
                              <span className="text-sm text-text">
                                {formatCriterionPercent(row.score)}
                              </span>
                            </>
                          )}
                        </div>
                        {isOverrideTarget ? (
                          <div className="flex items-center gap-2">
                            <Badge tone="neutral">Manuell übernommen</Badge>
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              busy={resetPending}
                              disabled={resetPending}
                              onClick={() => onResetOverride?.()}
                            >
                              Zurücksetzen
                            </Button>
                          </div>
                        ) : isEffective ? (
                          <Badge tone="neutral">Aktuell</Badge>
                        ) : (
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            busy={isPending}
                            disabled={isPending}
                            onClick={() => onOverrideCategory?.(row.category_key)}
                          >
                            Übernehmen
                          </Button>
                        )}
                      </li>
                    )
                  })}
                </ul>
              </dd>
            </div>
          ) : (
            <div className="flex items-baseline justify-between gap-3">
              <dt className="text-text">Kategorie</dt>
              <dd className="font-medium text-text-h">{formatCategoryKey(ranking.category_key)}</dd>
            </div>
          )}
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
