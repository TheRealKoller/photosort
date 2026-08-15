import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'

import { ApiError } from '../api/client'
import type { PhotoOut } from '../api/types'
import { CategoryBadge } from '../components/CategoryBadge'
import { CriterionDetailsPopover } from '../components/CriterionDetailsPopover'
import { PhotoImage } from '../components/PhotoImage'
import { QualityMeter } from '../components/QualityMeter'
import { Alert } from '../components/ui/alert'
import { Button } from '../components/ui/button'
import { Skeleton } from '../components/ui/skeleton'
import { useCurationQuery, useSetRatingMutation } from '../hooks/usePhotos'
import { formatCategoryKey } from '../utils/categoryLabels'
import { qualityLevel } from '../utils/qualityLevel'

// specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-backfill.md: serverseitig deklarativ
// begrenzt (Field(ge=1, le=10) auf GET /photos) - client-seitiges Klemmen ist nur ein Hinweis,
// die eigentliche Grenze gilt ohnehin serverseitig.
const MIN_TOP_N = 1
const MAX_TOP_N = 10
const DEFAULT_TOP_N = 3

function parseTopN(value: string | null): number {
  if (value === null || value === '') {
    return DEFAULT_TOP_N
  }
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) {
    return DEFAULT_TOP_N
  }
  return Math.min(MAX_TOP_N, Math.max(MIN_TOP_N, Math.round(parsed)))
}

interface GroupedPhotos {
  [clusterKey: string]: {
    [categoryKey: string]: PhotoOut[]
  }
}

function groupByClusterAndCategory(items: PhotoOut[]): GroupedPhotos {
  const groups: GroupedPhotos = {}
  for (const photo of items) {
    if (photo.ranking === null) {
      continue
    }
    const { cluster_key: clusterKey, category_key: categoryKey } = photo.ranking
    groups[clusterKey] ??= {}
    groups[clusterKey][categoryKey] ??= []
    groups[clusterKey][categoryKey].push(photo)
  }
  return groups
}

const SKELETON_TILE_COUNT = 6

export function CurateCategoriesPage() {
  const { projectId } = useParams()
  const id = Number(projectId)
  const [searchParams] = useSearchParams()
  const topN = parseTopN(searchParams.get('topN'))

  const query = useCurationQuery(id, topN)
  const setRatingMutation = useSetRatingMutation(id)
  // useMemo statt einer neuen `?? []`-Array-Referenz bei jedem Render (Lint-Fund: der Effekt
  // unten haengt von `items` ab, ein staendig neuer Referenzwert wuerde ihn bei jedem Render neu
  // ausloesen, obwohl sich die tatsaechlichen Daten nicht geaendert haben).
  const items = useMemo(() => query.data?.items ?? [], [query.data])

  // In-place Nachruecken statt Reflow (UI/UX-Abschnitt der Spec): die Kachel des gerade
  // abgelehnten Fotos zeigt einen Skeleton-Platzhalter, bis die per Rating-Invalidierung
  // ausgeloeste Refetch-Antwort eintrifft (siehe hooks/usePhotos.ts::curationQueryKey) - React
  // Query tauscht `data` erst aus, sobald die neuen Daten vorliegen (kein Zwischenzustand ohne
  // Daten), der Rest des Grids bleibt bis dahin unveraendert stehen.
  const [rejectingPhotoId, setRejectingPhotoId] = useState<number | null>(null)

  useEffect(() => {
    if (rejectingPhotoId !== null && !items.some((photo) => photo.id === rejectingPhotoId)) {
      setRejectingPhotoId(null)
    }
  }, [items, rejectingPhotoId])

  // Erschoepfter Pool (Akzeptanzkriterium der Spec): eine Partition, die inzwischen komplett leer
  // ist (letztes Foto gerade abgelehnt), wuerde sonst spurlos aus der Gruppierung verschwinden -
  // einmal gesehene Partitionen bleiben deshalb fuer die Dauer des Seitenbesuchs bekannt, damit
  // ihr Abschnitt (mit eigenem Leerzustand statt kommentarlosem Verschwinden) sichtbar bleibt.
  // Schluessel via JSON.stringify() statt eines zusammengesetzten Strings mit Trennzeichen
  // (Review-Fund test-engineer/security-engineer/architect): ein einzelnes Trennzeichen waere
  // anfaellig fuer eine Kollision, sollte ein kuenftiger cluster_key/category_key es selbst
  // enthalten - JSON.stringify(["a","b"]) ist immer eindeutig umkehrbar.
  const knownGroupKeysRef = useRef<Set<string>>(new Set())
  const groups = groupByClusterAndCategory(items)
  for (const clusterKey of Object.keys(groups)) {
    for (const categoryKey of Object.keys(groups[clusterKey])) {
      knownGroupKeysRef.current.add(JSON.stringify([clusterKey, categoryKey]))
    }
  }
  for (const key of knownGroupKeysRef.current) {
    const [clusterKey, categoryKey] = JSON.parse(key) as [string, string]
    groups[clusterKey] ??= {}
    groups[clusterKey][categoryKey] ??= []
  }

  function handleReject(photo: PhotoOut): void {
    if (rejectingPhotoId !== null) {
      return
    }
    setRejectingPhotoId(photo.id)
    setRatingMutation.mutate(
      { photoId: photo.id, status: 'rejected' },
      { onError: () => setRejectingPhotoId(null) }
    )
  }

  const clusterKeys = Object.keys(groups).sort()

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-2xl font-semibold text-text-h">Kategorie-Kuratierung</h1>
        {/* Personenbezug (UI/UX-Abschnitt der Spec): Rating ist personenbezogen, die gezeigte
            Top-N-Auswahl deshalb je Nutzer individuell. */}
        <p className="text-sm text-text">Deine Auswahl</p>
      </header>

      {query.isLoading && (
        <ul
          role="status"
          aria-label="Fotos werden geladen…"
          className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4"
        >
          {Array.from({ length: SKELETON_TILE_COUNT }, (_, index) => (
            <li key={index} aria-hidden="true">
              <Skeleton className="aspect-square w-full rounded-md" />
            </li>
          ))}
        </ul>
      )}

      {query.isError && (
        <Alert onRetry={() => void query.refetch()}>
          {query.error instanceof ApiError ? query.error.detail : 'Fehler beim Laden der Fotos.'}
        </Alert>
      )}

      {query.isSuccess && clusterKeys.length === 0 && (
        <p className="text-sm text-text">
          Noch keine Kategorie-Kuratierung verfügbar — führe zuerst eine Kriterien-Bewertung aus.
        </p>
      )}

      {clusterKeys.map((clusterKey) => {
        const categoryKeys = Object.keys(groups[clusterKey]).sort()
        return (
          <section key={clusterKey} className="flex flex-col gap-4">
            <h2 className="text-lg font-semibold text-text-h">{clusterKey}</h2>
            {categoryKeys.map((categoryKey) => {
              const photos = groups[clusterKey][categoryKey]
              return (
                <div key={categoryKey} className="flex flex-col gap-2">
                  <h3 className="flex items-center gap-2 text-sm font-semibold text-text-h">
                    <CategoryBadge categoryKey={categoryKey} />
                    {formatCategoryKey(categoryKey)}
                  </h3>
                  <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
                    {photos.map((photo) => {
                      const isRejecting = rejectingPhotoId === photo.id
                      const level = qualityLevel(photo.ranking?.rank_score ?? null)
                      return (
                        <li key={photo.id} className="flex flex-col gap-1.5">
                          <div className="relative">
                            {isRejecting ? (
                              <Skeleton className="aspect-square w-full rounded-md" />
                            ) : (
                              <>
                                <PhotoImage
                                  photoId={photo.id}
                                  variant="thumbnail"
                                  alt={photo.relative_path}
                                  className="aspect-square w-full rounded-md object-cover"
                                />
                                {/* Einheitliche Position "oben rechts" (UI/UX-Abschnitt,
                                    specs/features/0040-bewertungsdetails-info-popover.md) - kein
                                    bereits belegtes Element in dieser Ecke. Waehrend isRejecting
                                    zeigt die Kachel nur den Skeleton-Platzhalter, kein Trigger. */}
                                <CriterionDetailsPopover
                                  criterionScores={photo.criterion_scores}
                                  ranking={photo.ranking}
                                  suggestion={photo.suggestion}
                                  className="absolute right-1.5 top-1.5"
                                />
                              </>
                            )}
                          </div>
                          {level && <QualityMeter level={level} className="text-xs" />}
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            disabled={isRejecting}
                            busy={isRejecting}
                            aria-label={`Verwerfen: ${photo.relative_path}`}
                            onClick={() => handleReject(photo)}
                          >
                            {isRejecting ? 'Wird verworfen…' : 'Verwerfen'}
                          </Button>
                        </li>
                      )
                    })}
                    {photos.length < topN && (
                      <li className="flex aspect-square w-full flex-col items-center justify-center rounded-md border border-dashed border-border p-2 text-center text-xs text-text">
                        Kein weiteres Foto verfügbar
                      </li>
                    )}
                  </ul>
                </div>
              )
            })}
          </section>
        )
      })}

      <Button asChild variant="ghost" className="self-start">
        <Link to={`/projects/${id}`}>Zurück zum Projekt</Link>
      </Button>
    </div>
  )
}
