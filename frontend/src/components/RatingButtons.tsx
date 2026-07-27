import type { RatingStatus } from '../api/types'

const OPTIONS: { status: RatingStatus; label: string }[] = [
  { status: 'favorite', label: 'Favorit' },
  { status: 'album_worthy', label: 'Album-würdig' },
  { status: 'rejected', label: 'Verwerfen' },
]

interface RatingButtonsProps {
  currentStatus: RatingStatus | null
  /**
   * Toggle-Entscheidung (erneutes Klicken derselben Bewertung setzt zurueck auf unbewertet,
   * siehe specs/features/0002-manual-categorization.md) liegt bewusst beim Aufrufer, nicht hier
   * in der Komponente - so kann dieselbe Logik auch von einem Tastatur-Shortcut-Handler
   * (1/2/3-Tasten) auf Seitenebene wiederverwendet werden, statt sie zu duplizieren.
   */
  onToggle: (status: RatingStatus) => void
  disabled?: boolean
}

export function RatingButtons({ currentStatus, onToggle, disabled = false }: RatingButtonsProps) {
  return (
    <div role="group" aria-label="Bewertung">
      {OPTIONS.map((option) => (
        <button
          key={option.status}
          type="button"
          aria-label={option.label}
          aria-pressed={currentStatus === option.status}
          disabled={disabled}
          onClick={() => onToggle(option.status)}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
