import { useId } from 'react'

import type { CategoryKey } from '../api/types'
import {
  CATCH_ALL_CATEGORY_KEY,
  formatCategoryKey,
  sortCategoryKeys,
  type CategorySet,
} from '../utils/categoryLabels'
import { Alert } from './ui/alert'

interface CategorySelectProps {
  /** Das ueber `GET /categories` geladene Set - Quelle der angebotenen Eintraege UND ihrer
   * Reihenfolge (Registry-Anzeigereihenfolge, siehe `sortCategoryKeys`). */
  categories: CategorySet
  /** Der aktuell wirksame Kategorie-Key des Fotos - dient nur als Vorauswahl. Ein Altwert aus der
   * Laufhistorie (nicht im Set) waehlt bewusst nichts vor, statt eine falsche Kategorie zu
   * suggerieren. */
  value: CategoryKey | null
  onSelect: (categoryKey: CategoryKey) => void
  /** Laeuft gerade eine Override-Anfrage fuer dieses Foto? */
  pending?: boolean
  /** Das Set laedt noch (`useCategoriesQuery`) - Auswahl deaktiviert, kein Bypass. */
  isLoading?: boolean
  /** Das Set konnte nicht geladen werden - Inline-Alert mit "Erneut versuchen" statt einer leeren,
   * scheinbar funktionsfaehigen Auswahl. */
  isError?: boolean
  onRetry?: () => void
}

/**
 * "Alle Kategorien"-Auswahl fuer die manuelle Uebersteuerung (specs/features/0289-feste-
 * kategorien.md, UI/UX-Abschnitt) - bietet ALLE 13 Eintraege des festen Sets an, unabhaengig
 * davon, was fuer dieses Foto erkannt wurde. Die bestehende "Kategorie-Kandidaten"-Gruppe bleibt
 * daneben als Erklaerung erhalten ("das hat das System erkannt"), sie wird nicht ersetzt.
 *
 * Bedienform: ein natives `<select>`. Die Spec skizziert Desktop-Dropdown UND einen eigenen
 * Modal-Dialog fuer Mobil mit 44x44px-Tap-Zielen - eine technische Detailentscheidung dieser
 * Umsetzung ist, dass das native `<select>` beides bereits erfuellt: mobile Browser rendern es
 * ohnehin als bildschirmfuellenden System-Picker mit systemeigenen (grossen) Tap-Zielen, und ein
 * handgebauter Dialog haette dieselbe Bedienung mit schlechterer Tastatur-/Screenreader-
 * Unterstuetzung nachgebaut. Deckt sich mit dem Design-System ("Radix-Primitives nur dort, wo
 * natives HTML nicht reicht"). Der Trigger selbst ist 44px hoch.
 *
 * "Nicht erkannt" steht immer zuletzt (`sortCategoryKeys`), traegt denselben neutralen Ton wie
 * jede andere Kategorie (kein Fehler-Styling) und bekommt einen kurzen Erklaertext unter der
 * Auswahl.
 */
export function CategorySelect({
  categories,
  value,
  onSelect,
  pending = false,
  isLoading = false,
  isError = false,
  onRetry,
}: CategorySelectProps) {
  const selectId = useId()
  const hintId = `${selectId}-hint`

  if (isError) {
    return (
      <Alert onRetry={onRetry}>
        Kategorien konnten nicht geladen werden. Bitte versuche es erneut.
      </Alert>
    )
  }

  const orderedKeys = sortCategoryKeys(
    categories.map((entry) => entry.key),
    categories
  )
  const selectedValue = value !== null && orderedKeys.includes(value) ? value : ''

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={selectId} className="text-xs font-medium text-text-h">
        Alle Kategorien
      </label>
      <select
        id={selectId}
        aria-describedby={hintId}
        className="h-11 rounded-sm border border-border-control bg-surface px-3 text-sm text-text-h disabled:border-border disabled:text-text-disabled"
        value={selectedValue}
        disabled={isLoading || pending || orderedKeys.length === 0}
        onChange={(event) => {
          const next = event.target.value
          if (next !== '') {
            onSelect(next)
          }
        }}
      >
        <option value="" disabled>
          {isLoading ? 'wird geladen…' : 'Kategorie wählen…'}
        </option>
        {orderedKeys.map((key) => (
          <option key={key} value={key}>
            {formatCategoryKey(key, categories)}
          </option>
        ))}
      </select>
      <p id={hintId} className="text-xs text-text">
        „{formatCategoryKey(CATCH_ALL_CATEGORY_KEY, categories)}“ verwendest du, wenn kein
        Bildmotiv sicher bestimmbar ist.
      </p>
    </div>
  )
}
