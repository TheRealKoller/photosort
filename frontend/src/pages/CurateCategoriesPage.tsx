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
import { formatClusterHeading, formatDayHeading } from '../utils/timeOfDay'

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

interface ClusterMeta {
  dayKey: string
  heading: string
  // Nur fuer die chronologische Cluster-Sortierung innerhalb eines Tages (Akzeptanzkriterium 2)
  // - formatClusterHeading() selbst liefert bewusst nur die fertige Anzeige-Ueberschrift, kein
  // sortierbares Roh-Datum (siehe frontend/src/utils/timeOfDay.ts).
  earliestTakenAt: string
}

interface GroupedPhotos {
  [dayKey: string]: {
    [clusterKey: string]: {
      [categoryKey: string]: PhotoOut[]
    }
  }
}

/**
 * Erster Durchlauf sammelt pro `cluster_key` alle zugehoerigen Fotos (kategorieuebergreifend)
 * und berechnet einmal die Cluster-Meta-Info (Tag + Ueberschrift), zweiter Durchlauf sortiert die
 * Fotos in die dreistufige {Tag: {Cluster: {Kategorie: Fotos}}}-Struktur ein (Architektur-
 * Abschnitt der Spec 0039).
 */
function groupByClusterAndCategory(items: PhotoOut[]): {
  groups: GroupedPhotos
  clusterMeta: Map<string, ClusterMeta>
} {
  const photosByCluster = new Map<string, PhotoOut[]>()
  for (const photo of items) {
    if (photo.ranking === null) {
      continue
    }
    const clusterKey = photo.ranking.cluster_key
    const clusterPhotos = photosByCluster.get(clusterKey) ?? []
    clusterPhotos.push(photo)
    photosByCluster.set(clusterKey, clusterPhotos)
  }

  const clusterMeta = new Map<string, ClusterMeta>()
  for (const [clusterKey, photos] of photosByCluster) {
    const { dayKey, heading, earliestIso } = formatClusterHeading(photos)
    clusterMeta.set(clusterKey, { dayKey, heading, earliestTakenAt: earliestIso })
  }

  const groups: GroupedPhotos = {}
  for (const photo of items) {
    if (photo.ranking === null) {
      continue
    }
    const { cluster_key: clusterKey, category_key: categoryKey } = photo.ranking
    const meta = clusterMeta.get(clusterKey)
    if (meta === undefined) {
      // Unerreichbar: photosByCluster wurde aus denselben `items` gebaut, jeder hier
      // auftauchende clusterKey hat also zwingend einen Eintrag. Defensive Absicherung statt
      // einer Non-Null-Assertion.
      continue
    }
    groups[meta.dayKey] ??= {}
    groups[meta.dayKey][clusterKey] ??= {}
    groups[meta.dayKey][clusterKey][categoryKey] ??= []
    groups[meta.dayKey][clusterKey][categoryKey].push(photo)
  }
  return { groups, clusterMeta }
}

/** Ob mindestens eine Kategorie in dieser Cluster-Ebene noch (sichtbare) Fotos hat. */
function categoriesHavePhotos(categories: { [categoryKey: string]: PhotoOut[] }): boolean {
  return Object.values(categories).some((photos) => photos.length > 0)
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

  // Erschoepfter Pool (Akzeptanzkriterium 7 der Spec): eine Partition, die inzwischen komplett
  // leer ist (letztes Foto gerade abgelehnt), wuerde sonst spurlos aus der Gruppierung
  // verschwinden - einmal gesehene Partitionen bleiben deshalb fuer die Dauer des Seitenbesuchs
  // bekannt, damit ihr Abschnitt (mit eigenem Leerzustand statt kommentarlosem Verschwinden)
  // sichtbar bleibt. Schluessel via JSON.stringify() statt eines zusammengesetzten Strings mit
  // Trennzeichen (Review-Fund test-engineer/security-engineer/architect): ein einzelnes
  // Trennzeichen waere anfaellig fuer eine Kollision, sollte ein kuenftiger cluster_key/
  // category_key es selbst enthalten - JSON.stringify(["a","b","c"]) ist immer eindeutig
  // umkehrbar. Seit Spec 0039 3-Tupel [dayKey, clusterKey, categoryKey] statt 2-Tupel.
  const knownGroupKeysRef = useRef<Set<string>>(new Set())
  // Cache fuer die Cluster-Meta-Info (Tag + Ueberschrift + Sortier-Zeitstempel): sobald das
  // letzte Foto eines Clusters abgelehnt wird, verschwindet der cluster_key komplett aus `items`
  // - formatClusterHeading() laesst sich dann nicht mehr aus aktuellen Daten neu berechnen. Wird
  // bei jedem Render fuer alle in `items` noch vorhandenen Cluster ueberschrieben, liefert fuer
  // erschoepfte Cluster weiterhin die zuletzt bekannte Meta-Info.
  const clusterMetaRef = useRef<Map<string, ClusterMeta>>(new Map())

  const { groups, clusterMeta } = groupByClusterAndCategory(items)
  for (const [clusterKey, meta] of clusterMeta) {
    clusterMetaRef.current.set(clusterKey, meta)
  }

  for (const dayKey of Object.keys(groups)) {
    for (const clusterKey of Object.keys(groups[dayKey])) {
      for (const categoryKey of Object.keys(groups[dayKey][clusterKey])) {
        knownGroupKeysRef.current.add(JSON.stringify([dayKey, clusterKey, categoryKey]))
      }
    }
  }
  for (const key of knownGroupKeysRef.current) {
    const [dayKey, clusterKey, categoryKey] = JSON.parse(key) as [string, string, string]
    groups[dayKey] ??= {}
    groups[dayKey][clusterKey] ??= {}
    groups[dayKey][clusterKey][categoryKey] ??= []
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

  // dayKey-Format YYYY-MM-DD sortiert lexikographisch = chronologisch (Akzeptanzkriterium 1).
  const dayKeys = Object.keys(groups).sort()

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

      {query.isSuccess && dayKeys.length === 0 && (
        <p className="text-sm text-text">
          Noch keine Kategorie-Kuratierung verfügbar — führe zuerst eine Kriterien-Bewertung aus.
        </p>
      )}

      {dayKeys.map((dayKey) => {
        const clustersForDay = groups[dayKey]
        // Chronologisch nach dem fruehesten taken_at im Cluster sortiert, nicht lexikographisch
        // nach cluster_key (Akzeptanzkriterium 2, behebt den latenten Sortier-Bug
        // "cluster-10" < "cluster-2").
        const clusterKeysForDay = Object.keys(clustersForDay).sort((a, b) => {
          const earliestA = clusterMetaRef.current.get(a)?.earliestTakenAt ?? ''
          const earliestB = clusterMetaRef.current.get(b)?.earliestTakenAt ?? ''
          if (earliestA < earliestB) return -1
          if (earliestA > earliestB) return 1
          return 0
        })
        const dayIsEmpty = !Object.values(clustersForDay).some(categoriesHavePhotos)
        return (
          // UI/UX-Abschnitt der Spec: gap-6 (24px) gilt zwischen Tagen - das liefert bereits der
          // aeussere Seiten-Wrapper (naechste Zeile im JSX-Baum, `flex flex-col gap-6`), da jede
          // Tag-<section> dort ein direktes Geschwisterelement ist. Innerhalb eines Tages gilt
          // stattdessen gap-4 (16px) zwischen den Clustern (Review-Fund ux-ui-designer: gap-6
          // hier haette faelschlich auch zwischen Clustern 24px statt 16px erzeugt).
          <section key={dayKey} className="flex flex-col gap-4">
            <h2 className="text-xl font-semibold text-text-h">{formatDayHeading(dayKey)}</h2>
            {dayIsEmpty && <p className="text-sm text-text">Keine Fotos für diesen Tag</p>}
            {!dayIsEmpty &&
              clusterKeysForDay.map((clusterKey) => {
                const categories = clustersForDay[clusterKey]
                const categoryKeys = Object.keys(categories).sort()
                const clusterIsEmpty = !categoriesHavePhotos(categories)
                const heading = clusterMetaRef.current.get(clusterKey)?.heading ?? clusterKey
                return (
                  <section key={clusterKey} className="flex flex-col gap-4">
                    <h3 className="text-lg font-semibold text-text-h">{heading}</h3>
                    {clusterIsEmpty && (
                      <p className="text-sm text-text">Keine Fotos in dieser Tageszeit</p>
                    )}
                    {!clusterIsEmpty &&
                      categoryKeys.map((categoryKey) => {
                        const photos = categories[categoryKey]
                        return (
                          <div key={categoryKey} className="flex flex-col gap-2">
                            <h4 className="flex items-center gap-2 text-sm font-semibold text-text-h">
                              <CategoryBadge categoryKey={categoryKey} />
                              {formatCategoryKey(categoryKey)}
                            </h4>
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
                                              specs/features/0040-bewertungsdetails-info-popover.md) -
                                              kein bereits belegtes Element in dieser Ecke. Waehrend
                                              isRejecting zeigt die Kachel nur den Skeleton-
                                              Platzhalter, kein Trigger. */}
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
          </section>
        )
      })}

      <Button asChild variant="ghost" className="self-start">
        <Link to={`/projects/${id}`}>Zurück zum Projekt</Link>
      </Button>
    </div>
  )
}
