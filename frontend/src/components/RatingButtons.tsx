import type { RatingStatus } from '../api/types'
import { cn } from '../lib/utils'
import { Button } from './ui/button'
import { Icon } from './ui/icon'
import type { IconName } from './ui/icon'

/*
 * Ein Eintrag der Board-Bewertungsleiste: Symbol, sichtbare Beschriftung und die Ziffer der
 * Taste, die ihn tatsächlich auslöst.
 *
 * DIE BELEGUNG BLEIBT 1 / 2 / 3: Übernommen wird die FORM des Kästchens, nicht die
 * Board-Beschriftung F/A/X. Die Ziffern stehen hier, die Belegung in `PhotoDetailPage` -
 * beide können auseinanderlaufen, deshalb prüft `PhotoDetailPage.test.tsx` sie
 * tabellengetrieben gegeneinander.
 *
 * ZIFFERNFARBE IN DER ZUSTANDSFARBE, aber für "Verwerfen" `--danger-text` statt
 * `--rating-rejected`: der Board-Ton erreicht auf `--overlay` nur 3.96:1 und ist hier TEXT.
 * Das ist die geltende --danger/--danger-text-Regel, keine neue Festlegung.
 */
const OPTIONS: { status: RatingStatus; label: string; icon: IconName; key: string; keyClass: string }[] = [
  { status: 'favorite', label: 'Favorit', icon: 'star', key: '1', keyClass: 'text-rating-favorite' },
  {
    status: 'album_worthy',
    label: 'Album-würdig',
    icon: 'book',
    key: '2',
    keyClass: 'text-rating-album-worthy',
  },
  { status: 'rejected', label: 'Verwerfen', icon: 'x-circle', key: '3', keyClass: 'text-danger-text' },
]

// Bewertungsfarben - nur auf dem aktiv gedrückten Button als volle Fläche, nicht auf allen
// dreien, damit "auf einen Blick" erkennbar bleibt, welche Stufe tatsächlich gesetzt ist. Als
// Beschriftungsfarbe die tonspezifische `--rating-<ton>-fg` (dieselbe Kalibrierung wie bei
// Badge) - die tonspezifische Kopplung bleibt bestehen, auch wenn alle drei Töne denselben
// Wert tragen.
//
// `active:` ist Pflicht: Tailwind bindet `hover:` an `@media (hover: hover)`, am Telefon
// fällt der Zustand ersatzlos weg - und das Bewerten ist genau die Handlung, die dort
// stattfindet.
const ACTIVE_TONE_CLASSES: Record<RatingStatus, string> = {
  favorite: 'bg-rating-favorite text-rating-favorite-fg hover:opacity-85 active:opacity-70',
  album_worthy: 'bg-rating-album-worthy text-rating-album-worthy-fg hover:opacity-85 active:opacity-70',
  rejected: 'bg-rating-rejected text-rating-rejected-fg hover:opacity-85 active:opacity-70',
}

/*
 * HEISSER PFAD: Bewertungsschaltflächen werden während des Sichtens wiederholt und schnell
 * getroffen, und ein Fehlgriff schreibt hier einen falschen DATENWERT, kein bloßes Ärgernis.
 * Deshalb am Telefon SICHTBAR mindestens 44px hoch, am Desktop das Board-Maß 32px - man
 * zielt auf das, was man sieht.
 *
 * Der Abstand ist aus demselben Grund 12px (`gap-3`) und kein Geschmack: die
 * Trefferflächen-Aufspannung ragt bis zu 6px je Seite über das Sichtbare hinaus, bei 8px
 * überlappen die Trefferflächen benachbarter Schaltflächen - und in der Überlappung gewinnt
 * das obenliegende Element.
 */
const HOT_PATH_HEIGHT = 'h-11 sm:h-8'

/*
 * UNTERHALB `sm:` STEHEN DIE EINTRÄGE UNTEREINANDER. Arithmetisch belegt: 360 - 32 (`px-4`)
 * - 16 (`p-2` des Containers) = 312px innen, minus 2x `gap-3` = 288px für drei Einträge;
 * drei Einträge mit Symbol, sichtbarer Beschriftung und Kästchen brauchen rund 400px.
 * Kürzen der Beschriftung verbietet ein Akzeptanzkriterium, waagerechtes Scrollen die
 * Abnahme.
 *
 * Der Umbruch entsteht über Utilities auf EINEM DOM-Baum, nicht über zwei parallele
 * Teilbäume (`hidden sm:flex` neben `flex sm:hidden`) - doppelte Zweige würden Rollen, Namen
 * und Elementanzahl verdoppeln und sowohl `toHaveCount(3)` als auch
 * `EXPECTED_CONTROL_COUNT = 6` brechen.
 *
 * Nebeneffekt und Gewinn: Die drei Einträge stehen dann von oben nach unten in derselben
 * Reihenfolge wie ihre Tasten 1/2/3, statt in einer je nach Breite unterschiedlich
 * umbrechenden Reihe.
 */
const ENTRY_LAYOUT = 'w-full justify-start sm:w-auto'

interface RatingButtonsProps {
  currentStatus: RatingStatus | null
  /**
   * Die Toggle-Entscheidung (erneutes Klicken derselben Bewertung setzt zurück auf
   * unbewertet) liegt bewusst beim Aufrufer, nicht hier in der Komponente - so kann
   * dieselbe Logik auch von einem Tastatur-Shortcut-Handler (1/2/3-Tasten) auf Seitenebene
   * wiederverwendet werden, statt sie zu duplizieren.
   */
  onToggle: (status: RatingStatus) => void
  disabled?: boolean
  /**
   * Busy-Button-Muster - zeigt einen Inline-Indikator, solange die auslösende
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
  // Zentral hier erzwungen statt über die Button-eigene busy-Prop: `isDisabled` bleibt
  // garantiert wahr, sobald `busy` gesetzt ist, unabhängig davon, ob der Aufrufer
  // `disabled` synchron mithält. Das Button-eigene busy-Prop (eigener Spinner je Button)
  // wird bewusst NICHT an alle drei Buttons weitergereicht - drei parallele Spinner plus
  // die separate "Speichert…"-Zeile wären redundante Bewegungsunruhe für eine häufig
  // wiederholte, schnelle Aktion ("Durchsatz vor Erklärung"). Die zentrale Statuszeile
  // bleibt der einzige Busy-Indikator.
  const isDisabled = disabled || busy

  return (
    // Board-Container der Leiste: Flaeche `--surface`, Radius 8px, Polsterung 8px. Der Abstand
    // zwischen den Eintraegen ist 12px und hier KEIN Gestaltungsspielraum: die aufgespannte
    // Trefferflaeche ragt bis zu 6px je Seite ueber das Sichtbare hinaus, in einer Ueberlappung
    // gewinnt das obenliegende Element - und ein Fehlgriff schreibt hier einen falschen Datenwert.
    <div
      role="group"
      aria-label="Bewertung"
      className="flex flex-col items-stretch gap-3 rounded-md bg-surface p-2 sm:flex-row sm:flex-wrap sm:items-center"
    >
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
            className={cn(
              HOT_PATH_HEIGHT,
              ENTRY_LAYOUT,
              'gap-1 px-3',
              isActive && ACTIVE_TONE_CLASSES[option.status]
            )}
            onClick={() => onToggle(option.status)}
          >
            <Icon name={option.icon} size={16} />
            {option.label}
            {/* TASTEN-KAESTCHEN: `aria-hidden`, sonst lautete der zugaengliche Name "Favorit 1" und
                die `exact: true`-Pruefungen in den e2e-Specs braechen. Die Tastenbelegung ist fuer
                Screenreader-Nutzer bereits ueber die Shortcut-Zeile im Text der Seite verfuegbar;
                das Kaestchen ist eine rein visuelle Wiederholung.

                `--overlay` als eigene, in JEDEM Zustand gleich bleibende Flaeche - dadurch bleibt
                das Kaestchen auch auf dem gefuellten aktiven Eintrag eine lesbare Insel und braucht
                keine sechs eigenen Zustandsvarianten. 12px statt der 10px des Boards: das
                Design-System setzt 12px als harte Untergrenze. */}
            <span
              aria-hidden="true"
              className={cn(
                'ml-auto inline-flex h-4 min-w-4 items-center justify-center rounded-xs bg-overlay px-1 font-mono text-xs leading-none sm:ml-0',
                option.keyClass
              )}
            >
              {option.key}
            </span>
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
