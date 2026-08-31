import type { CategoryKey } from '../api/types'
import { categoryAbbreviation, formatCategoryKey, type CategorySet } from '../utils/categoryLabels'
import { Badge } from './ui/badge'

interface CategoryBadgeProps {
  categoryKey: CategoryKey
  /** Das ueber `GET /categories` geladene Set (specs/features/0289-feste-kategorien.md) - liefert
   * Anzeigename und Kuerzel. Darf leer sein, solange das Set noch laedt; dann greift der
   * generische Fallback, das Badge bleibt lesbar statt leer. */
  categories: CategorySet
  className?: string
}

/**
 * Kategorie-Chip fuer die Kategorie-Kuratierungs-Ansicht (specs/features/0037-gatefuehrte-
 * bewertungs-pipeline-mit-backfill.md, UI/UX-Abschnitt "Dynamische Kategorie-Keys") -
 * `tone="neutral"` (wie schon zu Spec-0024-Zeiten), damit keine Verwechslung mit den
 * Bewertungsfarben entsteht: Kategorie ist eine Einordnung, kein Qualitaetsurteil. Das gilt
 * ausdruecklich auch fuer den Auffangkorb "Nicht erkannt" - kein Fehler-Styling, ein fehlendes
 * Erkennungsergebnis ist kein Fehler.
 *
 * Sichtbar sind drei Grossbuchstaben aus dem ANZEIGENAMEN (specs/features/0289-feste-
 * kategorien.md - ueber das feste Set kollisionsfrei), der vollstaendige Name steht als
 * `aria-label`/`title`.
 */
export function CategoryBadge({ categoryKey, categories, className }: CategoryBadgeProps) {
  const label = formatCategoryKey(categoryKey, categories)
  return (
    <Badge className={className} tone="neutral" aria-label={label} title={label}>
      {categoryAbbreviation(categoryKey, categories)}
    </Badge>
  )
}
