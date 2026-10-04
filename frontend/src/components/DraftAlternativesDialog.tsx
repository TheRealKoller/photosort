import { Fragment } from 'react'

import { ApiError } from '../api/client'
import type { PhotoOut } from '../api/types'
import { useDraftAlternativesQuery } from '../hooks/usePhotos'
import { ownRatingStatus } from '../utils/ownRating'
import { qualityLevel } from '../utils/qualityLevel'
import { referenceMarkerIndex } from '../utils/referenceMarker'
import { formatEventHeading } from '../utils/timeOfDay'
import { ALTERNATIVES_ORDER_TEXT, ReferenceMarker } from './DraftAlternativesBand'
import { PhotoImage } from './PhotoImage'
import { QualityMeter } from './QualityMeter'
import { Alert } from './ui/alert'
import { AlbumStateBadge } from './AlbumStateBadge'
import { Button } from './ui/button'
import { Dialog } from './ui/dialog'
import { Skeleton } from './ui/skeleton'

/** Das Event hält nichts, was nicht schon im eigenen Entwurf steht. */
export const ALTERNATIVES_NONE_TEXT = 'Keine Alternativen in diesem Event.'

/** Fehlschlag ohne Servertext. */
export const ALTERNATIVES_ERROR_TEXT = 'Fehler beim Laden der Alternativen.'

/** Die Stelle des zu ersetzenden Bildes liegt auf einer noch nicht geladenen Seite. */
export const REFERENCE_LATER_TEXT = 'Das zu ersetzende Bild folgt weiter hinten in der Reihe.'

/*
 * Gestrichene Fotos des Events tragen hier das Kennzeichen „Gestrichen" aus der Begriffsquelle.
 * Der Tausch ist über den Rückgängig-Hinweis der Seite umkehrbar und, solange dieser steht, über
 * die Gestrichen-Zeile des Events.
 */

const SKELETON_TILE_COUNT = 6

/** `grid-cols-2 sm:grid-cols-3` - auf 360px zwei Spalten, ohne waagerechtes Scrollen. */
const ALTERNATIVES_GRID_CLASS = 'grid grid-cols-2 gap-3 sm:grid-cols-3'

export interface DraftAlternativesDialogProps {
  projectId: number
  /** Das Bezugsbild des Austauschs. Es steuert Menge und zeitliche Position der Antwort. */
  photo: PhotoOut
  /** Der `username`-Claim des JWT - die EINE Quelle des eigenen Bewertungszustands (Auflage S6). */
  username: string | null
  open: boolean
  onClose: () => void
  /** Die gewählte Alternative. Den Austausch selbst führt der Aufrufer aus. */
  onChoose: (alternative: PhotoOut) => void
  /** true, solange der Austausch dieses Dialogs läuft. */
  exchanging: boolean
  /** Grund eines gescheiterten Austauschs aus diesem Dialog - steht hier, nicht hinter dem Modal. */
  error: string | null
}

/**
 * ALLE Alternativen zu EINEM Bild des Entwurfs, als Dialog mit Seitenabruf - geöffnet aus dem
 * Alternativen-Band. Namen („Tauschen: {Pfad}") und Wirkung des Tauschs sind dieselben wie dort.
 *
 * DIALOG UND NICHT POPOVER (ADR 0098): Der Inhalt ist ein Bildraster mit eigenem Blätterweg, das
 * auf 360px Breite die volle Fläche braucht, und der Vorgang verlangt Fokusfang und Escape. Beides
 * sind Zusagen von `ui/dialog` und werden hier nicht erneut geprüft.
 *
 * GELADEN WIRD ERST BEIM ÖFFNEN (`enabled`) - eine Abfrage je geöffnetem Bild, nie eine je Kachel.
 * Ohne Event wird gar nicht gefragt: Der Endpunkt verlangt beide Schlüssel, und die
 * Ausfallrichtung ist „nichts anbieten", nie eine Anfrage auf gut Glück.
 *
 * DIE REIHENFOLGE IST DIE DER ANTWORT: die zeitliche Ordnung aus dem Backend (Spec 0569). Eine
 * zweite Sortierung hier wäre eine zweite Wahrheit, und sie fiele nicht auf, weil beide plausibel
 * aussähen. Die Stelle des Bezugsbildes liefert der Server (`reference_index`); die Marke steht
 * über alle geladenen Seiten genau einmal - an der Seitengrenze erst mit der Folgeseite.
 */
export function DraftAlternativesDialog({
  projectId,
  photo,
  username,
  open,
  onClose,
  onChoose,
  exchanging,
  error,
}: DraftAlternativesDialogProps) {
  const event = photo.event ?? null
  const query = useDraftAlternativesQuery(projectId, {
    // `0` ist durch `ge=1` am Endpunkt keine gültige Id und wird nie gesendet: ohne Event steht
    // `enabled` auf `false`.
    eventId: event?.id ?? 0,
    photoId: photo.id,
    enabled: open && event !== null,
  })

  const pages = query.data?.pages ?? []
  const alternatives = pages.flatMap((page) => page.items)
  // Die geladenen Seiten bilden EINE Reihe ab `pages[0].offset`. Am Ende steht die Marke nur, wenn
  // keine Seite mehr folgt - sonst gehört sie an den Anfang der nächsten.
  const markerAt =
    pages.length === 0
      ? null
      : referenceMarkerIndex(pages[0].reference_index, pages[0].offset, alternatives.length)
  const showMarker = markerAt !== null && (markerAt < alternatives.length || !query.hasNextPage)
  const markerLater = !showMarker && alternatives.length > 0 && pages[0].reference_index !== null
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
              className="size-full object-contain"
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
        {error !== null && <Alert>{error}</Alert>}

        {alternatives.length > 0 && (
          <>
            <div className="flex flex-col gap-1">
              <p className="text-xs text-text">{ALTERNATIVES_ORDER_TEXT}</p>
              {markerLater && <p className="text-xs text-text">{REFERENCE_LATER_TEXT}</p>}
            </div>
            <ol aria-label="Alternativen, zeitlich geordnet" className={ALTERNATIVES_GRID_CLASS}>
              {alternatives.map((alternative, index) => {
                const ownStatus = ownRatingStatus(alternative.ratings, username)
                return (
                  <Fragment key={alternative.id}>
                    {showMarker && markerAt === index && (
                      <ReferenceMarker photo={photo} className="p-2" />
                    )}
                    <li>
                      {/* EIN Druck, kein Bestätigungsschritt: Alternativen öffnen ist der erste,
                          der Austausch der zweite. Der zugängliche Name trägt den Dateinamen -
                          sonst hießen alle Flächen des Rasters gleich. Während des laufenden
                          Austauschs ist das ganze Raster gesperrt: Ein zweiter Austausch desselben
                          Bezugsbildes schriebe auf dieselbe Bewertungszeile. */}
                      <Button
                        type="button"
                        variant="ghost"
                        aria-label={`Tauschen: ${alternative.relative_path}`}
                        disabled={exchanging}
                        className="flex h-auto w-full flex-col items-stretch gap-2 whitespace-normal p-2 text-left"
                        onClick={() => onChoose(alternative)}
                      >
                        <span className="block aspect-square w-full overflow-hidden rounded-md">
                          <PhotoImage
                            photoId={alternative.id}
                            variant="thumbnail"
                            alt={alternative.relative_path}
                            className="size-full object-contain"
                          />
                        </span>
                        {/* `?? null` für den FEHLENDEN Wert, nie für die Zahl selbst: `0` ist ein
                            gültiger Qualitätswert, und ein `||` verlöre ihn lautlos. Ein Bild ohne
                            Wert bleibt wählbar. */}
                        <QualityMeter
                          level={qualityLevel(alternative.ranking?.rank_score ?? null)}
                          className="text-xs font-normal"
                        />
                        {ownStatus === 'rejected' && (
                          <span className="block">
                            <AlbumStateBadge state="struck" />
                          </span>
                        )}
                      </Button>
                    </li>
                  </Fragment>
                )
              })}
              {showMarker && markerAt === alternatives.length && (
                <ReferenceMarker photo={photo} className="p-2" />
              )}
            </ol>
          </>
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
