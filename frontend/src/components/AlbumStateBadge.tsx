import { NOT_PROPOSED_BADGE_TEXT } from '../utils/albumDraft'
import type { AlbumState } from '../utils/albumStateLabels'
import { ALBUM_STATE_LABELS } from '../utils/albumStateLabels'
import { Badge } from './ui/badge'
import { Icon } from './ui/icon'

/**
 * Das Kennzeichen der Haltung zu einem Foto in Album-Entwurf und Endauswahl: NUR Symbole, ohne
 * sichtbares Wort. Das Wort aus `albumStateLabels.ts` ist der zugaengliche Name (`role="img"`).
 *
 * OHNE FARBE UNTERSCHEIDBAR an Anzahl und Form der Symbole: „Vorschlag" `cog`+`book` auf der
 * Vorschlags-Konstruktion (Rand statt Fuellung), „Aufgenommen" `book` gefuellt, „Gestrichen"
 * `x-circle` gefuellt.
 *
 * Die Symbole stehen auf dem UNDURCHSICHTIGEN Chip `--overlay`, nie unmittelbar auf dem Foto:
 * Ueber einer Bildflaeche ist ein Kontrast statisch nicht nachrechenbar.
 */
export function AlbumStateBadge({
  state,
  notProposed = false,
}: {
  state: AlbumState
  /** Aufgenommen, vom aktuellen Vorschlag nicht getragen - nur im Namen, nicht sichtbar. */
  notProposed?: boolean
}) {
  const word = ALBUM_STATE_LABELS[state]
  const label = notProposed ? `${word}, ${NOT_PROPOSED_BADGE_TEXT}` : word
  return (
    <span
      role="img"
      aria-label={label}
      data-album-state={state}
      data-struck={state === 'struck' ? 'true' : undefined}
      className="pointer-events-none inline-flex rounded-sm bg-overlay p-1"
    >
      {state === 'proposal' && (
        <Badge tone="album-worthy" suggested className="px-1">
          <Icon name="cog" size={14} />
          <Icon name="book" size={14} />
        </Badge>
      )}
      {state === 'taken' && (
        <Badge tone="album-worthy" className="px-1">
          <Icon name="book" size={14} />
        </Badge>
      )}
      {state === 'struck' && (
        <Badge tone="rejected" className="px-1">
          <Icon name="x-circle" size={14} />
        </Badge>
      )}
    </span>
  )
}
