import type { AlbumState } from '../utils/albumStateLabels'
import { ALBUM_STATE_LABELS } from '../utils/albumStateLabels'
import { Badge } from './ui/badge'
import { Icon } from './ui/icon'

/**
 * Das Kennzeichen der Haltung zu einem Foto in Album-Entwurf und Endauswahl - über die
 * bestehenden Kennzeichen-Konstruktionen, nie über ein neues Symbol.
 *
 * OHNE FARBE UNTERSCHEIDBAR: „Vorschlag" trägt die Vorschlags-Konstruktion (Rand statt Füllung)
 * und das Zahnrad vor `book`, „Aufgenommen" die gefüllte Fläche mit `book`, „Gestrichen" die
 * gefüllte Fläche mit `x-circle` und `data-struck`. Das Wort ist zugleich der zugängliche Name.
 */
export function AlbumStateBadge({ state }: { state: AlbumState }) {
  const label = ALBUM_STATE_LABELS[state]
  if (state === 'proposal') {
    return (
      <Badge tone="album-worthy" suggested data-album-state={state} aria-label={label}>
        <Icon name="cog" size={14} />
        <Icon name="book" size={14} />
        {label}
      </Badge>
    )
  }
  if (state === 'taken') {
    return (
      <Badge tone="album-worthy" data-album-state={state} aria-label={label}>
        <Icon name="book" size={14} />
        {label}
      </Badge>
    )
  }
  return (
    <Badge tone="rejected" data-album-state={state} data-struck="true" aria-label={label}>
      <Icon name="x-circle" size={14} />
      {label}
    </Badge>
  )
}
