import type { AusschussPhotoEntry } from '../api/types'
import { cn } from '../lib/utils'
import {
  ENTSCHEIDUNG_SCHRIFT,
  Entscheidungshinweise,
  entscheidungswort,
} from './AusschussDecisionLine'
import { GrundKennzeichen } from './AusschussGrund'
import { PhotoImage } from './PhotoImage'

export function AusschussTile({
  entry: eintrag,
  width,
  height,
  onOpen,
}: {
  entry: AusschussPhotoEntry
  width: number
  height: number
  onOpen: (photoId: number) => void
}) {
  return (
    <li style={{ width, height }} className="relative rounded-md bg-elevated">
      {/* Die Bildflaeche ist ein natives `<button>` - Enter und Leertaste wirken
          ohne eigenen Tastatur-Handler, und der zugaengliche Name nennt die
          Aktion samt Dateiname. Der Beschnitt liegt am Button selbst, nicht am
          `li` - am `li` schnitte `overflow-hidden` den Fokusring ab. */}
      <button
        type="button"
        onClick={() => onOpen(eintrag.photo.id)}
        aria-label={`${eintrag.photo.relative_path} öffnen`}
        data-testid="ausschuss-image"
        className="block size-full overflow-hidden rounded-md"
      >
        <PhotoImage
          photoId={eintrag.photo.id}
          variant="thumbnail"
          alt={eintrag.photo.relative_path}
          className="size-full object-cover"
        />
      </button>

      {/* Beide Kennzeichen liegen auf der UNDURCHSICHTIGEN Flaeche `--overlay` und
          sind fuer Zeigegeraete durchlaessig: Die Bildflaeche bleibt die eine
          Trefferflaeche dieser Kachel. Kachelgrosser Beschnitt NUR fuer die
          Angaben - der Fokusring des Buttons bleibt unbeschnitten, und sehr
          schmale Kacheln halten Zeile und Kennzeichen in ihren Grenzen. */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden rounded-md">
        {eintrag.reason !== 'earlier_decision' && (
          <span className="absolute left-1 top-1 rounded-sm bg-overlay p-1">
            <GrundKennzeichen reason={eintrag.reason} />
          </span>
        )}
        <span
          className={cn(
            'absolute inset-x-0 bottom-0 flex items-center justify-between gap-2 bg-overlay px-2 py-1 text-xs',
            ENTSCHEIDUNG_SCHRIFT[eintrag.decision ?? 'offen'],
          )}
        >
          <span data-testid="ausschuss-decision" className="flex min-w-0 items-center gap-1">
            {entscheidungswort(eintrag.decision)}
            <Entscheidungshinweise
              reason={eintrag.reason}
              decision={eintrag.decision}
              decisionEffective={eintrag.decision_effective}
              keepPossible={eintrag.keep_possible}
            />
          </span>
          <span className="min-w-6 truncate font-mono text-text-muted">
            {eintrag.photo.relative_path.split('/').pop()}
          </span>
        </span>
      </div>
    </li>
  )
}
