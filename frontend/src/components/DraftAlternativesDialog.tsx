import { ApiError } from '../api/client'
import type { PhotoOut } from '../api/types'
import { useDraftAlternativesQuery } from '../hooks/usePhotos'
import { wasInAlbum } from '../utils/albumDraft'
import { ownRatingStatus } from '../utils/ownRating'
import { qualityLevel } from '../utils/qualityLevel'
import { formatEventHeading } from '../utils/timeOfDay'
import { PhotoImage } from './PhotoImage'
import { QualityMeter } from './QualityMeter'
import { Alert } from './ui/alert'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { Dialog } from './ui/dialog'
import { Skeleton } from './ui/skeleton'

/** Das Event hält nichts, was nicht schon im eigenen Entwurf steht. */
export const ALTERNATIVES_NONE_TEXT = 'Keine Alternativen in diesem Event.'

/** Fehlschlag ohne Servertext. */
export const ALTERNATIVES_ERROR_TEXT = 'Fehler beim Laden der Alternativen.'

/**
 * Das Abzeichen des ausgetauschten Bildes - die ganze Umkehrbarkeit des Austauschs.
 *
 * Es gibt keinen Rückgängig-Knopf und keinen Verlauf: Das ersetzte Bild steht wieder unter den
 * Alternativen (der Endpunkt liefert die eigenen Streichungen mit), und ein Druck darauf ist
 * derselbe Austausch in die andere Richtung - er stellt damit beide Bewertungszeilen zurück.
 */
export const PREVIOUSLY_IN_ALBUM_BADGE_TEXT = 'zuvor im Album'

const SKELETON_TILE_COUNT = 6

/** `grid-cols-2 sm:grid-cols-3` - auf 360px zwei Spalten, ohne waagerechtes Scrollen. */
const ALTERNATIVES_GRID_CLASS = 'grid grid-cols-2 gap-3 sm:grid-cols-3'

export interface DraftAlternativesDialogProps {
  projectId: number
  /** Das Bezugsbild des Austauschs. Es steuert Menge UND Reihenfolge der Antwort. */
  photo: PhotoOut
  /** Der `username`-Claim des JWT - die EINE Quelle des eigenen Bewertungszustands (Auflage S6). */
  username: string | null
  open: boolean
  onClose: () => void
  /** Die gewählte Alternative. Den Austausch selbst führt der Aufrufer aus. */
  onChoose: (alternative: PhotoOut) => void
  /** true, solange der Austausch dieses Dialogs läuft. */
  exchanging: boolean
}

/**
 * Die Alternativen zu EINEM Bild des Entwurfs, als Dialog.
 *
 * DIALOG UND NICHT POPOVER (ADR 0098): Der Inhalt ist ein Bildraster mit eigenem Blätterweg, das
 * auf 360px Breite die volle Fläche braucht, und der Vorgang verlangt Fokusfang und Escape. Beides
 * sind Zusagen von `ui/dialog` und werden hier nicht erneut geprüft.
 *
 * GELADEN WIRD ERST BEIM ÖFFNEN (`enabled`) - eine Abfrage je geöffnetem Bild, nie eine je Kachel.
 * Ohne Event wird gar nicht gefragt: Der Endpunkt verlangt beide Schlüssel, und die
 * Ausfallrichtung ist „nichts anbieten", nie eine Anfrage auf gut Glück.
 *
 * DIE REIHENFOLGE IST DIE DER ANTWORT. Sie hängt an den Motiven des Bezugsbildes, und die Grenze,
 * ab der ein Motiv getragen ist, wohnt im Backend - eine zweite Sortierung hier wäre eine zweite
 * Wahrheit, und sie fiele nicht auf, weil beide plausibel aussähen.
 */
export function DraftAlternativesDialog({
  projectId,
  photo,
  username,
  open,
  onClose,
  onChoose,
  exchanging,
}: DraftAlternativesDialogProps) {
  const event = photo.event ?? null
  const query = useDraftAlternativesQuery(projectId, {
    // `0` ist durch `ge=1` am Endpunkt keine gültige Id und wird nie gesendet: ohne Event steht
    // `enabled` auf `false`.
    eventId: event?.id ?? 0,
    photoId: photo.id,
    enabled: open && event !== null,
  })

  const alternatives = query.data?.pages.flatMap((page) => page.items) ?? []
  const title = event === null ? 'Alternativen' : formatEventHeading(event).heading
  const errorText = query.isError
    ? query.error instanceof ApiError
      ? query.error.detail
      : ALTERNATIVES_ERROR_TEXT
    : null

  return (
    <Dialog open={open} onClose={onClose} title={title} cancelLabel="Schließen">
      <div className="flex flex-col gap-4">
        {/* Das Bezugsbild klein - es beantwortet „wogegen tausche ich hier eigentlich?", ohne dem
            Raster Fläche wegzunehmen. */}
        <div className="flex items-center gap-3">
          <div className="size-16 shrink-0 overflow-hidden rounded-md">
            <PhotoImage
              photoId={photo.id}
              variant="thumbnail"
              alt={photo.relative_path}
              className="size-full object-cover"
            />
          </div>
          <p className="min-w-0 break-words text-sm text-text">{photo.relative_path}</p>
        </div>

        {query.isLoading && (
          <ul
            role="status"
            aria-label="Alternativen werden geladen…"
            className={ALTERNATIVES_GRID_CLASS}
          >
            {Array.from({ length: SKELETON_TILE_COUNT }, (_, index) => (
              <li key={index} aria-hidden="true">
                <Skeleton className="aspect-square w-full rounded-md" />
              </li>
            ))}
          </ul>
        )}

        {errorText !== null && <Alert onRetry={() => void query.refetch()}>{errorText}</Alert>}

        {alternatives.length > 0 && (
          <ul className={ALTERNATIVES_GRID_CLASS}>
            {alternatives.map((alternative) => {
              const ownStatus = ownRatingStatus(alternative.ratings, username)
              return (
                <li key={alternative.id}>
                  {/* EIN Druck, kein Bestätigungsschritt: Alternativen öffnen ist der erste, der
                      Austausch der zweite. Der zugängliche Name trägt den Dateinamen - sonst
                      hießen alle Flächen des Rasters gleich. Während des laufenden Austauschs ist
                      das ganze Raster gesperrt: Ein zweiter Austausch desselben Bezugsbildes
                      schriebe auf dieselbe Bewertungszeile. */}
                  <Button
                    type="button"
                    variant="ghost"
                    aria-label={`Austauschen gegen: ${alternative.relative_path}`}
                    disabled={exchanging}
                    className="flex h-auto w-full flex-col items-stretch gap-2 whitespace-normal p-2 text-left"
                    onClick={() => onChoose(alternative)}
                  >
                    <span className="block aspect-square w-full overflow-hidden rounded-md">
                      <PhotoImage
                        photoId={alternative.id}
                        variant="thumbnail"
                        alt={alternative.relative_path}
                        className="size-full object-cover"
                      />
                    </span>
                    {/* `?? null` für den FEHLENDEN Wert, nie für die Zahl selbst: `0` ist ein
                        gültiger Qualitätswert, und ein `||` verlöre ihn lautlos. Ein Bild ohne
                        Wert bleibt wählbar. */}
                    <QualityMeter
                      level={qualityLevel(alternative.ranking?.rank_score ?? null)}
                      className="text-xs font-normal"
                    />
                    {wasInAlbum(ownStatus) && (
                      <span className="block">
                        <Badge tone="neutral">{PREVIOUSLY_IN_ALBUM_BADGE_TEXT}</Badge>
                      </span>
                    )}
                  </Button>
                </li>
              )
            })}
          </ul>
        )}

        {query.hasNextPage && (
          <div>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              disabled={query.isFetchingNextPage}
              busy={query.isFetchingNextPage}
              onClick={() => void query.fetchNextPage()}
            >
              Weitere Alternativen laden
            </Button>
          </div>
        )}

        {!query.isLoading && errorText === null && alternatives.length === 0 && (
          <p className="text-sm text-text">{ALTERNATIVES_NONE_TEXT}</p>
        )}
      </div>
    </Dialog>
  )
}
