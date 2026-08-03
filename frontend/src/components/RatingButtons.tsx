import type { RatingStatus } from '../api/types'
import { Button } from './ui/button'

const OPTIONS: { status: RatingStatus; label: string }[] = [
  { status: 'favorite', label: 'Favorit' },
  { status: 'album_worthy', label: 'Album-würdig' },
  { status: 'rejected', label: 'Verwerfen' },
]

// Bewertungsfarben (specs/architecture/0004-design-system.md) - nur auf dem aktiv gedrueckten
// Button als volle Chip-Flaeche, nicht auf allen dreien, damit "auf einen Blick" erkennbar bleibt,
// welche Stufe tatsaechlich gesetzt ist. `--chip-fg` als Symbol-/Textfarbe (dieselbe Kalibrierung
// wie bei Badge/ProjectListPage-Statuspunkt).
const ACTIVE_TONE_CLASSES: Record<RatingStatus, string> = {
  favorite: 'bg-rating-favorite text-chip-fg hover:opacity-90',
  album_worthy: 'bg-rating-album-worthy text-chip-fg hover:opacity-90',
  rejected: 'bg-rating-rejected text-chip-fg hover:opacity-90',
}

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
  /**
   * Busy-Button-Muster (specs/architecture/0004-design-system.md: "gilt ab jetzt für jeden
   * auslösenden Button im Produkt") - zeigt einen Inline-Indikator, solange die auslösende
   * Bewertungsanfrage noch unterwegs ist, statt die Buttons nur stumm zu deaktivieren.
   */
  busy?: boolean
}

export function RatingButtons({
  currentStatus,
  onToggle,
  disabled = false,
  busy = false,
}: RatingButtonsProps) {
  // Funktionaler Fix 1 (specs/features/0012-visual-redesign.md) zentral hier statt ueber die
  // Button-eigene busy-Prop erzwungen: `isDisabled` bleibt garantiert wahr, sobald `busy` gesetzt
  // ist, unabhaengig davon, ob der Aufrufer `disabled` synchron mithaelt. UX-Review-Fund: das
  // Button-eigene busy-Prop (eigener Spinner pro Button) bewusst NICHT an alle drei Buttons
  // gleichzeitig weitergereicht - drei parallele Spinner plus die separate "Speichert…"-Zeile
  // waren redundante Bewegungsunruhe fuer eine haeufig wiederholte, schnelle Aktion (Designprinzip
  // "Durchsatz vor Erklaerung" / "keine Bewegungseffekte, die das zuegige Durchsehen bremsen").
  // Die zentrale Statuszeile bleibt der einzige Busy-Indikator.
  const isDisabled = disabled || busy

  return (
    <div role="group" aria-label="Bewertung" className="flex flex-wrap items-center gap-2">
      {OPTIONS.map((option) => {
        const isActive = currentStatus === option.status
        return (
          <Button
            key={option.status}
            type="button"
            variant={isActive ? 'default' : 'outline'}
            aria-label={option.label}
            aria-pressed={isActive}
            disabled={isDisabled}
            className={isActive ? ACTIVE_TONE_CLASSES[option.status] : undefined}
            onClick={() => onToggle(option.status)}
          >
            {option.label}
          </Button>
        )
      })}
      {busy && (
        <span role="status" className="text-sm text-text">
          Speichert…
        </span>
      )}
    </div>
  )
}
