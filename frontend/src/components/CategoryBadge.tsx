import type { CategoryKey } from '../api/types'
import { categoryAbbreviation, formatCategoryKey } from '../utils/categoryLabels'
import { Badge } from './ui/badge'

interface CategoryBadgeProps {
  categoryKey: CategoryKey
  className?: string
}

/**
 * Kategorie-Chip fuer die Kategorie-Kuratierungs-Ansicht (specs/features/0037-gatefuehrte-
 * bewertungs-pipeline-mit-backfill.md, UI/UX-Abschnitt "Dynamische Kategorie-Keys") -
 * `tone="neutral"` (wie schon zu Spec-0024-Zeiten), damit keine Verwechslung mit den
 * Bewertungsfarben entsteht: Kategorie ist eine Einordnung, kein Qualitaetsurteil. Kein festes
 * Kuerzel-Schema mehr moeglich (category_key ist ein freier String) - die ersten drei Zeichen in
 * Grossbuchstaben sind sichtbar, der vollstaendige (formatierte) Name nur als aria-label/title.
 */
export function CategoryBadge({ categoryKey, className }: CategoryBadgeProps) {
  const label = formatCategoryKey(categoryKey)
  return (
    <Badge className={className} tone="neutral" aria-label={label} title={label}>
      {categoryAbbreviation(categoryKey)}
    </Badge>
  )
}
