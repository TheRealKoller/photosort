import { useCallback, useEffect, useMemo, useRef } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'

import { ApiError } from '../api/client'
import type { RatingFilter } from '../api/types'
import { decodeUsername } from '../auth/jwt'
import { getToken } from '../auth/token'
import { PhotoGridTile } from '../components/PhotoGridTile'
import { PhotoImage } from '../components/PhotoImage'
import { Alert } from '../components/ui/alert'
import { Button } from '../components/ui/button'
import { Skeleton } from '../components/ui/skeleton'
import { useDuplicateGroupIndexQuery } from '../hooks/useDuplicates'
import { useElementWidth } from '../hooks/useElementWidth'
import { usePhotoSequenceQuery } from '../hooks/usePhotos'
import {
  GRID_GAP_PX,
  MIN_ROW_HEIGHT_PX,
  TARGET_ROW_HEIGHT_PX,
  justifiedRows,
  naturalTiles,
} from '../utils/justifiedRows'
import type { JustifiedTile } from '../utils/justifiedRows'
import { ownFavorite, ownRatingStatus } from '../utils/ownRating'
import { parseRatingFilter } from '../utils/ratingFilter'

// Design-System-Muster "Skeleton-/Platzhalter-Kacheln ... wo Inhalte schrittweise eintrudeln" statt
// eines vollflaechigen Spinners - Anzahl ist nur eine plausible Annaeherung an einen typischen
// Batch, keine harte Vorgabe.
const SKELETON_TILE_COUNT = 6

/*
 * Die Einträge bleiben unverändert, ihre Bedeutung ändert sich an zwei Stellen (ADR 0098):
 *
 * - "Unbewertet" heißt KEINE ALBUMENTSCHEIDUNG, nicht mehr "keine Bewertungszeile". Ein nur als
 *   Favorit markiertes Bild bleibt darin und behält seinen Vorschlag.
 * - "Favorit" filtert auf das eigene Kennzeichen, nicht auf einen Bewertungsstatus. Die Einträge
 *   schließen einander damit nicht mehr aus: ein Foto kann in "Favorit" UND in "Album-würdig"
 *   erscheinen.
 */
const FILTERS: { value: RatingFilter | ''; label: string }[] = [
  { value: '', label: 'Alle' },
  { value: 'unrated', label: 'Unbewertet' },
  { value: 'suggested', label: 'Vorgeschlagen' },
  { value: 'favorite', label: 'Favorit' },
  { value: 'album_worthy', label: 'Album-würdig' },
  { value: 'rejected', label: 'Verworfen' },
]

export function PhotoGridPage() {
  const { projectId } = useParams()
  const id = Number(projectId)
  const [searchParams, setSearchParams] = useSearchParams()
  const filterParam = parseRatingFilter(searchParams.get('filter'))
  const ratingStatus = filterParam === '' ? undefined : filterParam

  const token = getToken()
  const username = token ? decodeUsername(token) : null

  const query = usePhotoSequenceQuery(id, ratingStatus)
  // Nur unter dem Vorschlags-Filter: Dort wird der Ausschuss gesichtet, und nur dort gehoert der
  // Weg durch die Serien hin. Unter jedem anderen Filter liefe die Anfrage ohne Adressaten.
  const duplicateGroupIndex = useDuplicateGroupIndexQuery(id, {
    enabled: filterParam === 'suggested',
  })
  const photos = useMemo(
    () => query.data?.pages.flatMap((page) => page.items) ?? [],
    [query.data?.pages],
  )
  // Die Gesamtzahl der gefilterten Menge - das "y" der Zaehlzeile unter dem Raster.
  const total = query.data?.pages[0]?.total ?? 0

  // Die Containerbreite kommt aus dem Beobachter-Eintrag, nie aus dem Element - siehe
  // `useElementWidth`. Sie ist `0`, solange noch nicht gemessen wurde.
  const { ref: gridRef, width: containerWidth } = useElementWidth<HTMLUListElement>()

  const tiles = useMemo(() => {
    const ratios = photos.map((photo) => photo.aspect_ratio ?? null)
    if (containerWidth <= 0) {
      return new Map(naturalTiles(ratios, TARGET_ROW_HEIGHT_PX).map((tile) => [tile.index, tile]))
    }
    const rows = justifiedRows({
      ratios,
      containerWidth,
      gap: GRID_GAP_PX,
      targetRowHeight: TARGET_ROW_HEIGHT_PX,
      minRowHeight: MIN_ROW_HEIGHT_PX,
    })
    return new Map<number, JustifiedTile>(
      rows.flatMap((row) => row.tiles.map((tile) => [tile.index, tile] as const)),
    )
  }, [photos, containerWidth])

  function handleFilterChange(value: RatingFilter | ''): void {
    const next = new URLSearchParams(searchParams)
    if (value === '') {
      next.delete('filter')
    } else {
      next.set('filter', value)
    }
    setSearchParams(next)
  }

  /*
   * SICHERHEIT (Auflage S7): Das Nachladen hat eine SPERRE und ein ENDE. Ein Abruf gleichzeitig
   * (`isFetchingNextPage`), und kein neuer, sobald alles geladen ist (`hasNextPage` wird falsch,
   * sobald die Summe der geladenen Eintraege `total` erreicht). Ohne beides feuerte der
   * Beobachter bei jedem Scroll-Schritt und erzeugte einen Anfragensturm - je Antwort bis zu 200
   * Fotos samt ihrer Bildabrufe - gegen den Homeserver, auf dem PhotoSort und OpenCloud zusammen
   * laufen.
   */
  // Die Sperre liegt in einem REF und nicht in einem Renderwert: Der Beobachter kann mehrfach
  // innerhalb DESSELBEN Ticks melden (Scroll-Schritt, Groessenaenderung, erneutes Einblenden), und
  // `isFetchingNextPage` wird erst beim naechsten Rendern wahr. Ein Renderwert liesse in genau
  // diesem Fenster beliebig viele Abrufe durch - gemessen elf statt zwei.
  const fetchingRef = useRef(false)
  const loadMoreRef = useRef<() => void>(() => {})
  loadMoreRef.current = () => {
    if (!query.hasNextPage || query.isFetchingNextPage || fetchingRef.current) {
      return
    }
    fetchingRef.current = true
    void query.fetchNextPage().finally(() => {
      fetchingRef.current = false
    })
  }

  const anchorObserverRef = useRef<IntersectionObserver | null>(null)
  const anchorRef = useCallback((node: HTMLDivElement | null) => {
    anchorObserverRef.current?.disconnect()
    anchorObserverRef.current = null
    if (node === null || typeof IntersectionObserver === 'undefined') {
      return
    }
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        loadMoreRef.current()
      }
    })
    observer.observe(node)
    anchorObserverRef.current = observer
  }, [])

  useEffect(
    () => () => {
      anchorObserverRef.current?.disconnect()
      anchorObserverRef.current = null
    },
    [],
  )

  const nextPageError = query.isFetchNextPageError
    ? query.error instanceof ApiError
      ? query.error.detail
      : 'Fehler beim Nachladen der Fotos.'
    : undefined

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl sm:text-2xl">Fotos</h1>

      {/* Am Telefon (< 640px) ist die Leiste ein EIGENER horizontaler Scrollbereich, einzeilig und
          am Rand angeschnitten - die Seite selbst scrollt nie seitlich (AK11). Ab `sm:` fliesst
          sie wieder um. */}
      <div
        role="group"
        aria-label="Filter"
        className="flex gap-2 overflow-x-auto sm:flex-wrap sm:overflow-x-visible"
      >
        {FILTERS.map((option) => (
          <Button
            key={option.value || 'all'}
            type="button"
            variant={filterParam === option.value ? 'default' : 'outline'}
            size="sm"
            aria-pressed={filterParam === option.value}
            onClick={() => handleFilterChange(option.value)}
            className="shrink-0"
          >
            {option.label}
          </Button>
        ))}
      </div>

      {/* EIN Weg für die ganze Liste, außerhalb des Kachelrasters. Bis Spec 0525 stand daneben ein
          zweiter, kachelgenauer Einstieg auf dieselbe Ansicht; er ist mit dem Gate-Modus
          entfallen. Der Durchgang durch die Serien bleibt über diese eine Stelle erreichbar.

          Der ZUGÄNGLICHE NAME beginnt mit der sichtbaren Beschriftung (WCAG 2.5.3) und sagt nach
          einem GEDANKENSTRICH, was der Weg tut: Er führt durch ALLE Gruppen, beginnend bei der
          ersten.

          Bei `total === 0` und während des Ladens ausgeblendet, nicht deaktiviert (AK8): Ein Weg,
          der auf einen Leerzustand führt, ist kein Weg, und ein kurz aufblitzender Einstieg wäre
          schlimmer als keiner. */}
      {duplicateGroupIndex.isSuccess && duplicateGroupIndex.data.first_photo_id !== null && (
        <Button asChild variant="secondary" size="sm" className="self-start">
          <Link
            to={`/projects/${id}/photos/${duplicateGroupIndex.data.first_photo_id}/duplicates`}
            aria-label="Duplikate vergleichen — alle Gruppen der Reihe nach durchgehen"
          >
            Duplikate vergleichen
          </Link>
        </Button>
      )}

      {query.isLoading && (
        <ul role="status" aria-label="Fotos werden geladen…" className="flex flex-wrap gap-3">
          {naturalTiles(
            Array.from({ length: SKELETON_TILE_COUNT }, () => null),
            TARGET_ROW_HEIGHT_PX,
          ).map((tile) => (
            <li key={tile.index} aria-hidden="true" style={{ width: tile.width }}>
              <Skeleton className="size-full rounded-md" style={{ height: tile.height }} />
            </li>
          ))}
        </ul>
      )}

      {query.isError && !query.isFetchNextPageError && (
        <Alert onRetry={() => void query.refetch()}>
          {query.error instanceof ApiError ? query.error.detail : 'Fehler beim Laden der Fotos.'}
        </Alert>
      )}

      {query.isSuccess && photos.length === 0 && (
        <div className="flex flex-col items-start gap-3 text-sm text-text">
          <p>Keine Fotos mit diesem Filter.</p>
          {filterParam !== '' && (
            <Button type="button" variant="outline" onClick={() => handleFilterChange('')}>
              Filter zurücksetzen
            </Button>
          )}
        </div>
      )}

      {photos.length > 0 && (
        <ul data-photo-grid ref={gridRef} className="flex flex-wrap gap-3">
          {photos.map((photo, index) => {
            const tile = tiles.get(index)
            const ownStatus = ownRatingStatus(photo.ratings, username)
            // SICHERHEIT: das EIGENE Kennzeichen, ueber `utils/ownRating.ts` - nie
            // `photo.ratings.some(r => r.favorite)`, das zeigte die Auszeichnung der anderen
            // Person als die eigene.
            const isFavorite = ownFavorite(photo.ratings, username)
            // Anzeigeregel: eine eigene Bewertung hat immer Vorrang - ein Vorschlag erscheint nur,
            // solange keine eigene existiert. Der Server garantiert das bereits, `ownStatus` wird
            // hier zusaetzlich geprueft statt sich blind darauf zu verlassen.
            const suggestedStatus = ownStatus === null ? (photo.suggestion?.status ?? null) : null

            return (
              <PhotoGridTile
                key={photo.id}
                to={`/projects/${id}/photos/${photo.id}${filterParam ? `?filter=${filterParam}` : ''}`}
                relativePath={photo.relative_path}
                status={ownStatus}
                suggestedStatus={suggestedStatus}
                favorite={isFavorite}
                width={tile?.width ?? 0}
                height={tile?.height ?? 0}
                image={
                  <PhotoImage
                    photoId={photo.id}
                    variant="thumbnail"
                    alt={photo.relative_path}
                    // `object-contain` statt des eingebauten `object-cover`: KEIN BESCHNITT (AK1).
                    // tailwind-merge laesst die durchgereichte Utility gewinnen.
                    className="size-full object-contain"
                  />
                }
              />
            )
          })}
        </ul>
      )}

      {/* Die Zählzeile ist zugleich die Fehlerstelle des Nachladens: Scheitert es, steht hier die
          Meldung mit "Erneut versuchen", und die bereits geladenen Bilder bleiben sichtbar. */}
      {photos.length > 0 && (
        <div className="flex flex-col items-start gap-3">
          {nextPageError === undefined ? (
            <p aria-live="polite" className="text-sm text-text">
              {photos.length} von {total} geladen
              {query.isFetchingNextPage ? ' — lädt…' : ''}
            </p>
          ) : (
            // Ueber DIESELBE Sperre wie der Anker (Auflage S7): "ein Abruf gleichzeitig" gilt
            // ohne Einschraenkung auf den Beobachterpfad. Ein `fetchNextPage()` direkt hier
            // ginge an `fetchingRef` vorbei, und mehrere Druecke im selben Tick erzeugten je
            // einen Abruf.
            <Alert onRetry={() => loadMoreRef.current()}>{nextPageError}</Alert>
          )}
          {/* Der Sichtbarkeitsanker. Er steht NUR unter einem gefüllten Raster - im Leerzustand
              löste er sofort einen Abruf aus. */}
          {query.hasNextPage && <div ref={anchorRef} aria-hidden="true" className="h-1 w-full" />}
        </div>
      )}
    </div>
  )
}
