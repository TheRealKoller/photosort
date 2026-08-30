import { useId } from 'react'

import type {
  CategoryCandidateOut,
  CategoryKey,
  CriterionScoreOut,
  FineLabelOut,
  RankingOut,
  SuggestionOut,
} from '../api/types'
import { cn } from '../lib/utils'
import { formatCategoryKey, formatProviderLabel, type CategorySet } from '../utils/categoryLabels'
import { formatSuggestionReason, formatSuggestionStatusLabel } from '../utils/suggestionLabels'
import { CategorySelect } from './CategorySelect'
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
  /** Bis zu zwei frei formulierte Feinlabels (specs/features/0289-feste-kategorien.md) - reine
   * Zusatzinformation am Foto, keine Kategorie. Ohne Feinlabels wird KEIN Platzhalter gerendert.
   *
   * SICHERHEITSHINWEIS: freier, extern erzeugter LLM-Text - ausschliesslich als regulaerer
   * React-Textknoten rendern (nie dangerouslySetInnerHTML, nie als HTML-String-Prop, nie in
   * href/src/style). Das ist keine blosse Konvention, sondern die tragende Voraussetzung der
   * localStorage-Token-Entscheidung (ADR 0005). */
  fineLabels?: FineLabelOut[]
  /** Das ueber `GET /categories` geladene feste Set - Grundlage von Anzeigenamen, Reihenfolge und
   * der "Alle Kategorien"-Auswahl. Leer, solange es laedt (generischer Fallback greift). */
  categories?: CategorySet
  /** Ladezustand des Sets - deaktiviert die Auswahl statt sie leer anzubieten (kein Bypass). */
  categoriesLoading?: boolean
  /** Fehlerzustand des Sets - Inline-Alert mit "Erneut versuchen" statt einer leeren Auswahl. */
  categoriesError?: boolean
  onRetryCategories?: () => void
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

// specs/features/0209-bewertungsdetails-bloecke-qualitaet-kategorien.md,
// Architektur-Entscheidung 1: die Block-Zuordnung folgt AUSSCHLIESSLICH dem Registry-Flag
// `category_eligible` aus der API-Antwort - hier wird bewusst KEINE Key-Liste gepflegt, sonst
// liefen Backend-Registry und Frontend beim naechsten neuen Kriterium auseinander. Bewusst
// ordnungserhaltend (zweimal `filter`, kein Sortieren): die Reihenfolge innerhalb eines Blocks
// bleibt die vom Backend gelieferte Registry-Reihenfolge (Akzeptanzkriterium 5). Nicht
// exportiert - die Aufteilung ist ein Implementierungsdetail dieser Komponente.
function partitionByCategoryEligibility(criterionScores: CriterionScoreOut[]): {
  quality: CriterionScoreOut[]
  categories: CriterionScoreOut[]
} {
  return {
    quality: criterionScores.filter((score) => !score.category_eligible),
    categories: criterionScores.filter((score) => score.category_eligible),
  }
}

function CriterionRow({ score }: { score: CriterionScoreOut }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="text-text">{score.display_name}</dt>
      <dd className="font-medium text-text-h">{formatCriterionPercent(score.value)}</dd>
    </div>
  )
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
  // specs/features/0289-feste-kategorien.md: die Reihenfolge kommt seit dieser Spec bereits vom
  // Server (Registry-Anzeigereihenfolge) - hier wird bewusst NICHT mehr umsortiert. Das frueher
  // hier verwendete Score-Sortierkriterium ist mit dem `score`-Feld entfallen: die Auswahl
  // entscheidet die feste Vorrangreihenfolge im Backend, ein Zahlenvergleich in der Oberflaeche
  // haette keine Entsprechung mehr in der Logik.
  const rows: CategoryCandidateRow[] = [...categoryCandidates]
  const overrideIsOrphan =
    categoryOverride !== null && !categoryCandidates.some((c) => c.category_key === categoryOverride)
  if (overrideIsOrphan) {
    rows.push({ category_key: categoryOverride, origin: 'local', provider: null, isOrphan: true })
  }
  return rows
}

/**
 * Reine Praesentationskomponente mit den Bewertungsdetails eines Fotos - extrahiert aus dem
 * bisher inline in CriterionDetailsPopover.tsx liegenden `<dl>`-Markup
 * (specs/features/0041-bewertungsdetails-permanent-in-detailansicht-hover-auto-close.md,
 * Architektur-Abschnitt), damit sowohl das Popover (Grid/Kuratierung) als auch die permanente
 * Sektion in PhotoDetailPage.tsx dieselbe Darstellung/Formatierungslogik teilen (DRY,
 * Akzeptanzkriterium 5/13). Prueft selbst NICHT, ob `criterionScores` leer ist - die Entscheidung,
 * den Bereich bei leerer Liste gar nicht erst einzubinden, bleibt bewusst bei den jeweiligen
 * Aufrufern (Popover-Sichtbarkeit vs. permanente Sektion), da beide Stellen die gleiche Bedingung
 * ohnehin schon selbst pruefen muessen (Popover fuer den Trigger, PhotoDetailPage.tsx fuer den
 * Abschnitts-Rahmen).
 *
 * Gliedert die Kriterien in zwei beschriftete Bloecke "Qualitaet"/"Kategorien"
 * (specs/features/0209-bewertungsdetails-bloecke-qualitaet-kategorien.md): ein Block ohne Inhalt
 * wird komplett weggelassen (keine Ueberschrift, kein leeres `<dl>`), bei komplett leerer Eingabe
 * rendert die Komponente nur noch den aeusseren Container ohne jedes `dt`/`dd` - der bis Spec 0209
 * hier dokumentierte Sonderfall "leeres `<dl>`" gilt nicht mehr. Der Ausschuss-Vorschlag bleibt
 * ein dritter, eigener Bereich ausserhalb beider Bloecke und ohne eigene Ueberschrift.
 */
export function CriterionDetailsList({
  criterionScores,
  ranking,
  suggestion,
  showSuggestion,
  categoryCandidates = [],
  fineLabels = [],
  categories = [],
  categoriesLoading = false,
  categoriesError = false,
  onRetryCategories,
  categoryOverride = null,
  onOverrideCategory,
  onResetOverride,
  pendingOverrideKey = null,
  resetPending = false,
}: CriterionDetailsListProps) {
  const candidateRows = buildCategoryCandidateRows(categoryCandidates, categoryOverride)
  const showCandidateGroup = candidateRows.length > 1
  const { quality: qualityScores, categories: categoryScores } =
    partitionByCategoryEligibility(criterionScores)
  // Die Kandidatenliste bzw. die einzeilige "Kategorie"-Anzeige und "Rang" gehoeren fachlich in
  // den Kategorien-Block - er erscheint deshalb auch ohne kategoriefaehiges Kriterium, sobald ein
  // Ranking vorliegt.
  const showCategoriesBlock = categoryScores.length > 0 || ranking !== null
  // Ein einzelnes useId() mit Suffixen statt zweier Aufrufe (React-Doku-Muster fuer mehrere
  // zusammengehoerige Ids) - noetig, weil zwei Instanzen gleichzeitig im DOM stehen koennen
  // (Popover ueber der permanenten Sektion) und feste Ids dann kollidieren wuerden.
  const blockId = useId()
  const qualityHeadingId = `${blockId}-quality`
  const categoriesHeadingId = `${blockId}-categories`

  return (
    <div className="flex flex-col gap-4">
      {qualityScores.length > 0 && (
        // role="group" + aria-labelledby am Wrapper, NICHT am <dl>: ein <dl> hat in dieser
        // Toolchain keine namensfaehige Rolle, die Beschriftung kaeme dort weder im
        // Accessibility-Tree noch in einer Rollenabfrage an (Spec 0209,
        // Architektur-Entscheidung 3).
        <div role="group" aria-labelledby={qualityHeadingId} className="flex flex-col gap-1.5">
          <h3 id={qualityHeadingId} className="text-xs font-medium text-text-h">
            Qualität
          </h3>
          <dl className="flex flex-col gap-1.5">
            {qualityScores.map((score) => (
              <CriterionRow key={score.criterion_key} score={score} />
            ))}
          </dl>
        </div>
      )}
      {showCategoriesBlock && (
        <div role="group" aria-labelledby={categoriesHeadingId} className="flex flex-col gap-1.5">
          <h3 id={categoriesHeadingId} className="text-xs font-medium text-text-h">
            Kategorien
          </h3>
          <dl className="flex flex-col gap-1.5">
            {categoryScores.map((score) => (
              <CriterionRow key={score.criterion_key} score={score} />
            ))}
            {ranking !== null && (
              // Der groessere Abstand vor der Kandidaten-/Rang-Gruppe sitzt als Margin an der
              // Gruppe selbst statt als `gap-3` am <dl>: so haengen die Kriterienzeilen in beiden
              // Bloecken auf derselben Ebene (<dl> > Zeilen-<div> > dt/dd) statt im
              // Kategorien-Block eine Wrapper-<div>-Ebene tiefer (Copilot-Review-Fund auf PR
              // #277). `mt-1.5` (0.375rem) addiert sich zum `gap-1.5` des <dl> auf exakt die
              // 0.75rem des vorherigen `gap-3` - und entfaellt, wenn keine Kriterienzeile
              // vorausgeht, weil dann auch vorher kein Abstand gerendert wurde. Die Darstellung
              // bleibt damit in jedem Fall pixelgleich (Akzeptanzkriterium 6: reine
              // Umgruppierung, keine visuelle Aenderung).
              <div className={cn('flex flex-col gap-1.5', categoryScores.length > 0 && 'mt-1.5')}>
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
                                  {formatCategoryKey(row.category_key, categories)}
                                </span>
                                {!row.isOrphan && (
                                  <Badge tone="neutral">
                                    {row.origin === 'remote' && row.provider
                                      ? formatProviderLabel(row.provider)
                                      : 'Lokal erkannt'}
                                  </Badge>
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
                    <dd className="font-medium text-text-h">
                      {formatCategoryKey(ranking.category_key, categories)}
                    </dd>
                  </div>
                )}
                <div className="flex items-baseline justify-between gap-3">
                  <dt className="text-text">Rang</dt>
                  <dd className="font-medium text-text-h">
                    Rang {ranking.rank_position} von {ranking.partition_size}
                  </dd>
                </div>
                {/* specs/features/0289-feste-kategorien.md, UI/UX-Abschnitt: die
                    "Alle Kategorien"-Auswahl ERGAENZT die Kandidatenliste, sie ersetzt sie nicht -
                    der Nutzer sieht weiterhin, was das System erkannt hat, bevor er es
                    uebersteuert. Nur eingebunden, wenn ein Uebersteuern ueberhaupt vorgesehen ist
                    (Aufrufer reicht `onOverrideCategory` durch). */}
                {onOverrideCategory && (
                  <div className="mt-1.5">
                    <CategorySelect
                      categories={categories}
                      value={categoryOverride ?? ranking.category_key}
                      onSelect={onOverrideCategory}
                      pending={pendingOverrideKey !== null}
                      isLoading={categoriesLoading}
                      isError={categoriesError}
                      onRetry={onRetryCategories}
                    />
                  </div>
                )}
              </div>
            )}
          </dl>
          {/* Feinlabel-Chips (specs/features/0289-feste-kategorien.md, UI/UX-Abschnitt): raeumlich
              deutlich von der Kategorie getrennt, kompakter und in einem anderen Ton
              (`suggested`-Variante des Akzent-Chips) - sie sind Zusatzinformation, keine
              kategoriale Einordnung. Bewusst OHNE Icon/Symbol, damit sie nicht mit den
              Bewertungs-Chips verwechselt werden. Ohne Feinlabels wird KEIN Platzhalter
              gerendert - der Bereich entfaellt ersatzlos. Sichtbar auch bei "Nicht erkannt". */}
          {fineLabels.length > 0 && (
            <div className="mt-1.5 flex flex-col gap-1.5">
              <h4 className="text-xs text-text">Feinlabels</h4>
              <ul aria-label="Feinlabels" className="flex flex-wrap gap-1.5">
                {fineLabels.map((label) => (
                  <li key={label.canonical_key}>
                    {/* Reiner React-Textknoten - freier LLM-Text, nie als HTML. */}
                    <Badge tone="accent" suggested className="max-w-full truncate">
                      {label.display_name}
                    </Badge>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
      {/* Dritter, eigener Bereich ausserhalb beider Bloecke und bewusst OHNE eigene Ueberschrift
          (Spec 0209, Akzeptanzkriterium 8) - erscheint auch dann, wenn beide Bloecke leer sind. */}
      {showSuggestion && suggestion !== null && (
        <dl className="flex flex-col gap-1.5">
          <div className="flex items-baseline justify-between gap-3">
            <dt className="text-text">Ausschuss-Vorschlag</dt>
            <dd className="font-medium text-text-h">{formatSuggestionStatusLabel(suggestion)}</dd>
          </div>
          <div className="flex items-baseline justify-between gap-3">
            <dt className="text-text">Grund</dt>
            <dd className="font-medium text-text-h">{formatSuggestionReason(suggestion)}</dd>
          </div>
        </dl>
      )}
    </div>
  )
}
