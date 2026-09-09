import type { ReactNode } from 'react'

import { ApiError } from '../api/client'
import type { PhotoOut, RankingOut } from '../api/types'
import { useCurationCandidatesQuery } from '../hooks/usePhotos'
import { curatedRankings } from '../utils/rankings'
import { Alert } from './ui/alert'
import { Button } from './ui/button'
import { Skeleton } from './ui/skeleton'

/**
 * Der Bereich hat geladen, aber der Konfidenzfilter hat alles herausgenommen - bewusst ein
 * anderer Text als der Leerzustand "hier ist nichts angekommen".
 */
export const CANDIDATES_ALL_FILTERED_TEXT =
  'Keine der weiteren Kandidaten liegt unter der eingestellten Sicherheit.'

/** Der Server hat zu dieser Partition nichts weiter geliefert. */
export const CANDIDATES_NONE_TEXT = 'Keine weiteren Kandidaten vorhanden.'

/** Wie viele Platzhalter waehrend des Ladens stehen - dieselbe Zahl wie in der Top-Auswahl. */
const SKELETON_TILE_COUNT = 4

/** Dasselbe Raster wie die Top-Foto-Reihe: kein zweites Raster, gleiche Kachelgroessen. */
const TILE_GRID_CLASS = 'grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4'

export interface CurationCandidatesProps {
  projectId: number
  clusterKey: string
  categoryKey: string
  /** Es werden die Zugehoerigkeiten mit `rank_position > afterRank` geladen. */
  afterRank: number
  /** Die UNGEFILTERTE Restmenge - sie steht auch bei aktivem Konfidenzfilter in der Beschriftung. */
  remainingCount: number
  panelId: string
  expanded: boolean
  onToggle: () => void
  /**
   * Der Konfidenzfilter der Seite, auf die nachgeladenen Fotos angewendet (`filterLowConfidence`
   * aus der Seite hereingereicht) - der Filter hat EINE Bedeutung in der ganzen Ansicht.
   * `undefined`, wenn er ausgeschaltet ist.
   */
  filterPhotos?: (items: PhotoOut[]) => PhotoOut[]
  /** Baut die Kachel - die Seite besitzt Verwerfen-Zustand und Override-Steuerung. */
  renderTile: (photo: PhotoOut, ranking: RankingOut) => ReactNode
}

/**
 * Der Auslöser "Weitere Kandidaten laden" und der aufgeklappte Bereich darunter
 * (specs/features/0357-voller-bildvorrat-kuratierung.md, ADR 0071 Entscheidung 5).
 *
 * Ob es weitere Kandidaten gibt, steht VOR jedem Laden fest (`partition_size` gegen die Zahl der
 * angezeigten Eintraege) - es braucht keinen Probe-Request, und der Kandidaten-Request laeuft
 * ausschliesslich im aufgeklappten Zustand (`enabled`).
 *
 * Der Aufklapp-Zustand folgt exakt dem bestehenden Tages-Aufklappen: `aria-expanded`/
 * `aria-controls`, Inhalt per bedingtem JSX statt CSS-versteckt.
 */
export function CurationCandidates({
  projectId,
  clusterKey,
  categoryKey,
  afterRank,
  remainingCount,
  panelId,
  expanded,
  onToggle,
  filterPhotos,
  renderTile,
}: CurationCandidatesProps) {
  const query = useCurationCandidatesQuery(projectId, {
    clusterKey,
    categoryKey,
    afterRank,
    enabled: expanded,
  })

  const loaded = query.data?.pages.flatMap((page) => page.items) ?? []
  const visible = filterPhotos ? filterPhotos(loaded) : loaded

  return (
    <>
      <div>
        <Button variant="ghost" size="sm" aria-expanded={expanded} aria-controls={panelId} onClick={onToggle}>
          {expanded
            ? 'Weitere Kandidaten ausblenden'
            : `Weitere Kandidaten laden (${remainingCount})`}
        </Button>
      </div>
      {expanded && (
        <div id={panelId} className="flex flex-col gap-3">
          {query.isLoading && (
            <ul role="status" aria-label="Weitere Kandidaten werden geladen…" className={TILE_GRID_CLASS}>
              {Array.from({ length: SKELETON_TILE_COUNT }, (_, index) => (
                <li key={index} aria-hidden="true">
                  <Skeleton className="aspect-square w-full rounded-md" />
                </li>
              ))}
            </ul>
          )}

          {query.isError && (
            <Alert onRetry={() => void query.refetch()}>
              {query.error instanceof ApiError
                ? query.error.detail
                : 'Fehler beim Laden weiterer Kandidaten.'}
            </Alert>
          )}

          {query.isSuccess && visible.length > 0 && (
            <ul className={TILE_GRID_CLASS}>
              {visible.map((photo) =>
                // Die Rangfolge kommt vom Server und wird nicht nachsortiert. `curatedRankings`
                // liefert hier genau EINE Zugehoerigkeit: der Endpunkt setzt `curation_position`
                // ausschliesslich fuer die angefragte Partition.
                curatedRankings(photo).map((ranking) => renderTile(photo, ranking))
              )}
            </ul>
          )}

          {/* Zwei UNTERSCHEIDBARE Zustaende (Akzeptanzkriterium 24): "hier ist alles
              weggefiltert" ist etwas anderes als "hier ist noch nichts geladen" - derselbe
              Anblick fuer beide liesse den Nutzer glauben, der Vorrat sei leer. */}
          {query.isSuccess && visible.length === 0 && (
            <p className="text-sm text-text">
              {loaded.length > 0 ? CANDIDATES_ALL_FILTERED_TEXT : CANDIDATES_NONE_TEXT}
            </p>
          )}

          {query.hasNextPage && (
            <div>
              <Button
                variant="secondary"
                size="sm"
                disabled={query.isFetchingNextPage}
                busy={query.isFetchingNextPage}
                onClick={() => void query.fetchNextPage()}
              >
                Noch mehr Kandidaten laden
              </Button>
            </div>
          )}
        </div>
      )}
    </>
  )
}
