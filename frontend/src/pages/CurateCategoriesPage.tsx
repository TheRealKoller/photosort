import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'

import { ApiError } from '../api/client'
import type { PhotoOut } from '../api/types'
import { CategoryBadge } from '../components/CategoryBadge'
import { CategoryOverrideMarker } from '../components/CategoryOverrideMarker'
import { CriterionDetailsPopover } from '../components/CriterionDetailsPopover'
import { PhotoImage } from '../components/PhotoImage'
import { QualityMeter } from '../components/QualityMeter'
import { Alert } from '../components/ui/alert'
import { Button } from '../components/ui/button'
import { Skeleton } from '../components/ui/skeleton'
import { useCategoryOverrideControls } from '../hooks/useCategoryOverrideControls'
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
  // Nur fuer die chronologische Cluster-Sortierung innerhalb eines Tages (Akzeptanzkriterium 2) -
  // 1:1 aus `formatClusterHeading()`s `earliestIso`-Rueckgabewert uebernommen (siehe
  // frontend/src/utils/timeOfDay.ts), damit der rohe Zeitstempel nicht ein zweites Mal separat
  // berechnet werden muss.
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

/**
 * Fotoanzahl eines Tages fuer die Kurzinfo im zugeklappten Zustand (Akzeptanzkriterium 6 der Spec
 * 0043) - reine Ableitung aus bereits geladenen Daten (Summe `photos.length` ueber alle Cluster/
 * Kategorien des Tages), kein neuer State/Request.
 */
export function countPhotosInDay(clustersForDay: {
  [clusterKey: string]: { [categoryKey: string]: PhotoOut[] }
}): number {
  let total = 0
  for (const categories of Object.values(clustersForDay)) {
    for (const photos of Object.values(categories)) {
      total += photos.length
    }
  }
  return total
}

/**
 * Toggelt den Klapp-Zustand eines einzelnen Tages (Akzeptanzkriterium 3 der Spec 0043) - liefert
 * ein neues `Set` statt das uebergebene zu mutieren, andere `dayKey`s bleiben unveraendert.
 */
export function toggleDayCollapse(collapsedDayKeys: Set<string>, dayKey: string): Set<string> {
  const next = new Set(collapsedDayKeys)
  if (next.has(dayKey)) {
    next.delete(dayKey)
  } else {
    next.add(dayKey)
  }
  return next
}

/**
 * Auffang-Kategorie des Backends (`criteria.py::CATEGORY_UNRECOGNIZED`) - Fotos, fuer die kein
 * aktives Kriterium erfuellt war (specs/features/0217-landschaft-erkennung-spezifitaets-
 * vorrang.md). Kein verwaister Key, sondern ein regulaer erzeugter Zustand.
 */
const CATCH_ALL_CATEGORY_KEY = 'unerkannt'

/**
 * Neutraler Erklaertext des Auffang-Abschnitts (UI/UX-Abschnitt der Spec 0217) - struktureller
 * Text, KEINE Fehler-Semantik (kein `role="alert"`, keine Fehlerfarbe): das Fehlen einer
 * Erkennung ist kein Fehler.
 */
const CATCH_ALL_EXPLANATION = 'Diese Fotos konnten nicht automatisch kategorisiert werden.'

/**
 * Reihenfolge der Kategorie-Abschnitte innerhalb eines Clusters (specs/features/0217): normale
 * Kategorien alphabetisch nach `category_key`, der Auffang-Abschnitt "Nicht erkannt" IMMER
 * zuletzt - das macht visuell deutlich, dass er ein Auffangzustand und keine gleichberechtigte
 * Inhaltskategorie ist. Liefert ein neues Array statt das uebergebene zu sortieren.
 */
export function sortCategoryKeys(categoryKeys: string[]): string[] {
  return [...categoryKeys].sort((a, b) => {
    if (a === b) return 0
    if (a === CATCH_ALL_CATEGORY_KEY) return 1
    if (b === CATCH_ALL_CATEGORY_KEY) return -1
    return a < b ? -1 : 1
  })
}

const SKELETON_TILE_COUNT = 6

export function CurateCategoriesPage() {
  const { projectId } = useParams()
  const id = Number(projectId)
  const [searchParams] = useSearchParams()
  const topN = parseTopN(searchParams.get('topN'))

  const query = useCurationQuery(id, topN)
  const setRatingMutation = useSetRatingMutation(id)
  const categoryOverrideControls = useCategoryOverrideControls(id)
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

  // Klapp-Zustand der Tages-Abschnitte (Spec 0043): leeres Set = alles aufgeklappt (Default,
  // Akzeptanzkriterium 2) - kein localStorage/sessionStorage/Query-Param, keine Persistierung
  // ueber einen Reload hinaus (Out-of-Scope-Abschnitt der Spec).
  const [collapsedDayKeys, setCollapsedDayKeys] = useState<Set<string>>(new Set())

  function toggleDay(dayKey: string): void {
    setCollapsedDayKeys((prev) => toggleDayCollapse(prev, dayKey))
  }

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
        <h1 className="text-2xl">Kategorie-Kuratierung</h1>
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

      {dayKeys.length > 0 && (
        // Zwei globale Aktionen (Akzeptanzkriterium 7 der Spec 0043) - bleiben auch bei genau
        // einem Tag im Projekt sichtbar/funktionsfaehig, da hier nicht extra auf `dayKeys.length
        // > 1` geprueft wird. Sekundaerer Ton (Hilfsfunktion, keine Akzentfarbe, UI/UX-Abschnitt).
        <div className="flex gap-2">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => setCollapsedDayKeys(new Set())}
          >
            Alle Tage aufklappen
          </Button>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => setCollapsedDayKeys(new Set(dayKeys))}
          >
            Alle Tage zuklappen
          </Button>
        </div>
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
        // dayKey (Format YYYY-MM-DD) ist bereits ID-sicher (Architektur-Abschnitt der Spec 0043).
        const panelId = `day-panel-${dayKey}`
        const isCollapsed = collapsedDayKeys.has(dayKey)
        return (
          // UI/UX-Abschnitt der Spec: gap-6 (24px) gilt zwischen Tagen - das liefert bereits der
          // aeussere Seiten-Wrapper (naechste Zeile im JSX-Baum, `flex flex-col gap-6`), da jede
          // Tag-<section> dort ein direktes Geschwisterelement ist. Innerhalb eines Tages gilt
          // stattdessen gap-4 (16px) zwischen den Clustern (Review-Fund ux-ui-designer: gap-6
          // hier haette faelschlich auch zwischen Clustern 24px statt 16px erzeugt).
          <section key={dayKey} className="flex flex-col gap-4">
            <h2 className="text-xl">
              {/* Gesamte Kopfzeile als Trigger (Akzeptanzkriterium 1) - kein separates Icon als
                  alleiniger interaktiver Traeger, `w-full`+`text-left` macht die ganze Zeile
                  klickbar, `min-h-11` sichert ein Touch-Ziel von mindestens 44px. */}
              <button
                type="button"
                aria-expanded={!isCollapsed}
                aria-controls={panelId}
                onClick={() => toggleDay(dayKey)}
                className="flex min-h-11 w-full items-center gap-2 rounded-md py-1 text-left transition-colors hover:bg-border/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-bg"
              >
                <span aria-hidden="true">{isCollapsed ? '▶' : '▼'}</span>
                <span>{formatDayHeading(dayKey)}</span>
                {/* Kurzinfo nur im zugeklappten Zustand (Akzeptanzkriterium 5) - reine Ableitung
                    aus bereits geladenen Daten, kein neuer State/Request (Akzeptanzkriterium 6).
                    Explizites `{' '}` (statt sich auf das visuelle `gap-2` zu verlassen): der
                    zugaengliche Name eines Elements wird aus dem Text seiner Kindknoten
                    zusammengesetzt, CSS-`gap` erzeugt dabei keinen Text-/Namensraum. */}
                {isCollapsed && (
                  <>
                    {' '}
                    <span className="font-normal text-text">
                      {`(${countPhotosInDay(clustersForDay)} Fotos)`}
                    </span>
                  </>
                )}
              </button>
            </h2>
            {!isCollapsed && (
              // Kompletter Cluster-Teilbaum wird bei Zugeklapptheit per conditional JSX gar nicht
              // gerendert statt nur CSS-versteckt (Akzeptanzkriterium 4) - spart bei grossen
              // Projekten auch tatsaechliche Render-Arbeit (Architektur-Abschnitt der Spec).
              <div id={panelId} className="flex flex-col gap-4">
                {dayIsEmpty && <p className="text-sm text-text">Keine Fotos für diesen Tag</p>}
                {!dayIsEmpty &&
                  clusterKeysForDay.map((clusterKey) => {
                    const categories = clustersForDay[clusterKey]
                    const categoryKeys = sortCategoryKeys(Object.keys(categories))
                    const clusterIsEmpty = !categoriesHavePhotos(categories)
                    const heading = clusterMetaRef.current.get(clusterKey)?.heading ?? clusterKey
                    return (
                      <section key={clusterKey} className="flex flex-col gap-4">
                        <h3 className="text-lg">{heading}</h3>
                        {clusterIsEmpty && (
                          <p className="text-sm text-text">Keine Fotos in dieser Tageszeit</p>
                        )}
                        {!clusterIsEmpty &&
                          categoryKeys.map((categoryKey) => {
                            const photos = categories[categoryKey]
                            return (
                              <div key={categoryKey} className="flex flex-col gap-2">
                                <h4 className="flex items-center gap-2 text-sm">
                                  <CategoryBadge categoryKey={categoryKey} />
                                  {formatCategoryKey(categoryKey)}
                                </h4>
                                {/* Auffangkorb-Kategorie mit erklärend dezentem Signal
                                    (specs/architecture/0004-design-system.md, Spec 0217):
                                    kurzer struktureller Hinweistext direkt unter der
                                    Überschrift, kein Icon/Badge, keine Fehler-Optik. */}
                                {categoryKey === CATCH_ALL_CATEGORY_KEY && (
                                  <p className="text-sm text-text">{CATCH_ALL_EXPLANATION}</p>
                                )}
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
                                                categoryCandidates={photo.category_candidates}
                                                categoryOverride={photo.category_override}
                                                onOverrideCategory={(categoryKey) =>
                                                  categoryOverrideControls.overrideCategory(
                                                    photo.id,
                                                    categoryKey
                                                  )
                                                }
                                                onResetOverride={() =>
                                                  categoryOverrideControls.resetOverride(photo.id)
                                                }
                                                pendingOverrideKey={categoryOverrideControls.pendingOverrideKeyFor(
                                                  photo.id
                                                )}
                                                resetPending={categoryOverrideControls.isResetPendingFor(
                                                  photo.id
                                                )}
                                              />
                                              {/* specs/features/0055-remote-kategorie-
                                                  klassifizierung-mit-kostenschaetzung.md: bislang
                                                  unbelegte Ecke (oben links). */}
                                              {photo.category_override !== null && (
                                                <div className="absolute left-1.5 top-1.5">
                                                  <CategoryOverrideMarker />
                                                </div>
                                              )}
                                            </>
                                          )}
                                        </div>
                                        {level && (
                                          <QualityMeter level={level} className="text-xs" />
                                        )}
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
              </div>
            )}
          </section>
        )
      })}

      <Button asChild variant="ghost" className="self-start">
        <Link to={`/projects/${id}`}>Zurück zum Projekt</Link>
      </Button>
    </div>
  )
}
