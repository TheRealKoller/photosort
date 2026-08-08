import type { PhotoCategory } from '../api/types'
import { CATEGORY_ABBREVIATIONS, CATEGORY_LABELS } from '../utils/categoryLabels'
import { Badge } from './ui/badge'

interface CategoryBadgeProps {
  category: PhotoCategory
  className?: string
}

/**
 * Zweiter, von RatingBadge getrennter Chip fuer die lokal klassifizierte Motiv-Kategorie
 * (specs/features/0024-top-photo-selection-category-mix.md, UI/UX-Abschnitt "Kategorie-
 * Kennzeichnung") - `tone="neutral"` (wie bisher fuer "unbewertet" genutzt), damit keine
 * Verwechslung mit den Bewertungsfarben entsteht: Kategorie ist eine Einordnung, kein
 * Qualitaetsurteil. Kuerzel (L/D/M) sichtbar, ausgeschriebener Name nur als aria-label/title.
 */
export function CategoryBadge({ category, className }: CategoryBadgeProps) {
  const label = CATEGORY_LABELS[category]
  return (
    <Badge className={className} tone="neutral" aria-label={label} title={label}>
      {CATEGORY_ABBREVIATIONS[category]}
    </Badge>
  )
}
