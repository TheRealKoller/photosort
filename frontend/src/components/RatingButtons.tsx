import type { RatingStatus } from '../api/types'
import { Button } from './ui/button'

const OPTIONS: { status: RatingStatus; label: string }[] = [
  { status: 'favorite', label: 'Favorit' },
  { status: 'album_worthy', label: 'Album-würdig' },
  { status: 'rejected', label: 'Verwerfen' },
]

// Bewertungsfarben (specs/architecture/0004-design-system.md) - nur auf dem aktiv gedrueckten
// Button als volle Flaeche, nicht auf allen dreien, damit "auf einen Blick" erkennbar bleibt,
// welche Stufe tatsaechlich gesetzt ist. Als Beschriftungsfarbe die tonspezifische
// `--rating-<ton>-fg` (dieselbe Kalibrierung wie bei Badge) - die tonspezifische Kopplung bleibt
// bestehen, auch wenn alle drei Toene seit ADR 0055 Punkt 4e denselben Wert tragen.
//
// `active:` ist Pflicht: Tailwind bindet `hover:` an `@media (hover: hover)`, am Telefon faellt
// der Zustand also ersatzlos weg - und das Bewerten ist genau die Handlung, die dort stattfindet.
const ACTIVE_TONE_CLASSES: Record<RatingStatus, string> = {
  favorite: 'bg-rating-favorite text-rating-favorite-fg hover:opacity-85 active:opacity-70',
  album_worthy: 'bg-rating-album-worthy text-rating-album-worthy-fg hover:opacity-85 active:opacity-70',
  rejected: 'bg-rating-rejected text-rating-rejected-fg hover:opacity-85 active:opacity-70',
}

/*
 * HEISSER PFAD (specs/features/0320-dark-utility-register.md, UI/UX-Abschnitt 3, Stakeholder-
 * Entscheidung): Bewertungsschaltflaechen werden waehrend des Sichtens wiederholt und schnell
 * getroffen, und ein Fehlgriff schreibt hier einen falschen DATENWERT, kein blosses Aergernis.
 * Deshalb am Telefon SICHTBAR mindestens 44px hoch, am Desktop das Board-Mass 32px - man zielt auf
 * das, was man sieht.
 *
 * Der Abstand ist aus demselben Grund 12px (`gap-3`) statt der frueheren 8px: die
 * Trefferflaechen-Aufspannung ragt bis zu 6px je Seite ueber das Sichtbare hinaus, bei 8px
 * ueberlappen die Trefferflaechen benachbarter Schaltflaechen - und in der Ueberlappung gewinnt
 * das obenliegende Element.
 */
const HOT_PATH_HEIGHT = 'h-11 sm:h-8'

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
    <div role="group" aria-label="Bewertung" className="flex flex-wrap items-center gap-3">
      {OPTIONS.map((option) => {
        const isActive = currentStatus === option.status
        return (
          <Button
            key={option.status}
            type="button"
            variant={isActive ? 'default' : 'secondary'}
            aria-label={option.label}
            aria-pressed={isActive}
            disabled={isDisabled}
            className={
              isActive ? `${HOT_PATH_HEIGHT} ${ACTIVE_TONE_CLASSES[option.status]}` : HOT_PATH_HEIGHT
            }
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
