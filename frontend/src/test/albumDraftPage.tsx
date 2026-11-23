/*
 * Gemeinsamer Unterbau der Tests der Entwurfsseite (`src/pages/AlbumDraftPage.*.test.tsx`):
 * Projekt-, Foto- und Bewertungsobjekte, Render-Funktion und Mock-Grundzustand. Die `vi.mock(...)`-
 * Aufrufe stehen in jeder Testdatei selbst (vitest hebt sie je Datei).
 */
import { render } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { vi } from 'vitest'

import * as motifsApi from '../api/motifs'
import * as personsApi from '../api/persons'
import * as photosApi from '../api/photos'
import * as projectsApi from '../api/projects'
import type {
  AlbumDraftOut,
  EventOut,
  PhotoOut,
  ProjectOut,
  RankingOut,
  RatingStatus,
  RatingWriteOut,
} from '../api/types'
import { setToken } from '../auth/token'
import { AlbumDraftPage } from '../pages/AlbumDraftPage'
import type { ObserverFactory } from '../hooks/useDraftPosition'
import { makePhoto, makeProject } from './fixtures'
import { MOTIF_SET } from './motifSetFixture'
import { makeQueryClient, queryWrapper } from './render'

export const USER_ID = 7

export function projectOut(overrides: Partial<ProjectOut> = {}): ProjectOut {
  return makeProject({
    opencloud_path: '/CostaRica',
    created_at: '2026-07-01T10:00:00',
    category_selection_enabled: false,
    cloud_vision_detection_enabled: true,
    cloud_vision_consent_at: '2026-07-01T10:00:00',
    selection_target: 3,
    effective_selection_target: 3,
    has_selection_proposal: true,
    ...overrides,
  })
}

export function makeToken(username: string): string {
  return `${btoa('{}')}.${btoa(JSON.stringify({ sub: String(USER_ID), username }))}.sig`
}

export const EVENT_A: EventOut = {
  id: 1,
  position: 1,
  started_at: '2026-07-20T10:00:00',
  ended_at: '2026-07-20T11:00:00',
  place: null,
  place_name: 'Paris',
}
export const EVENT_B: EventOut = {
  ...EVENT_A,
  id: 2,
  position: 2,
  place_name: 'Lyon',
  started_at: '2026-07-21T10:00:00',
  ended_at: '2026-07-21T11:00:00',
}

export function ranking(proposed: boolean): RankingOut {
  return {
    event_id: 1,
    rank_score: 0.8,
    rank_position: 1,
    proposed,
    partition_size: 3,
    curation_position: null,
  }
}

export function photo(id: number, overrides: Partial<PhotoOut> = {}): PhotoOut {
  return makePhoto({
    id,
    relative_path: `${id}.jpg`,
    taken_at: `2026-07-20T10:0${id}:00`,
    taken_at_original: `2026-07-20T10:0${id}:00`,
    ranking: ranking(true),
    motif_assessment: null,
    motifs: [],
    album_suitability: null,
    event: EVENT_A,
    ...overrides,
  })
}

export function own(status: RatingStatus) {
  return [{ user_id: USER_ID, username: 'daniel', status, favorite: false }]
}

export function written(photoId: number, status: RatingStatus | null): RatingWriteOut {
  return { photo_id: photoId, user_id: USER_ID, status, favorite: false, updated_at: null }
}

/**
 * Reichlich Kandidaten: ohne eigene Angabe bleibt der Hinweis „kleinerer Vorschlag" aus, damit
 * nur die Fälle ihn sehen, die ihn prüfen.
 */
export const PLENTY_OF_CANDIDATES = 1000

export type DraftInput = Omit<AlbumDraftOut, 'eligible_candidate_count'> &
  Partial<Pick<AlbumDraftOut, 'eligible_candidate_count'>>

/** `draft: null` lässt den Abruf so, wie der Fall ihn vorher eingerichtet hat (Laden, Fehler). */
export function renderPage(
  draft: DraftInput | null,
  observer?: ObserverFactory,
  path = '/projects/1/album',
) {
  if (draft !== null) {
    vi.mocked(photosApi.getAlbumDraft).mockResolvedValue({
      eligible_candidate_count: PLENTY_OF_CANDIDATES,
      ...draft,
    })
  }
  const queryClient = makeQueryClient()
  const wrapper = queryWrapper(queryClient)
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route
          path="/projects/:projectId/album"
          element={<AlbumDraftPage createPositionObserver={observer} />}
        />
        <Route path="/projects/:projectId/selection" element={<p>Endauswahl-Seite</p>} />
      </Routes>
    </MemoryRouter>,
    { wrapper },
  )
}

export const noObserver: ObserverFactory = () => ({ observe: () => {}, disconnect: () => {} })

/** Alternativen ohne Bezugsposition: diese Seitentests prüfen Tausch und Hinzufügen, nicht die
 * zeitliche Marke (die liegt in `DraftAlternativesBand.test.tsx`). */
export const NO_POSITION = { offset: 0, reference_index: null, series_rest: 0 }
/** Grundzustand jedes Falls der Entwurfsseite - in jeder Testdatei im `beforeEach` aufgerufen. */
export function resetAlbumDraftMocks(): void {
  vi.resetAllMocks()
  window.localStorage.clear()
  setToken(makeToken('daniel'))
  vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockResolvedValue('blob:fake-url')
  vi.mocked(motifsApi.listMotifs).mockResolvedValue(MOTIF_SET)
  vi.mocked(projectsApi.getProject).mockResolvedValue(projectOut())
  vi.mocked(personsApi.listPersons).mockResolvedValue([])
  vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue({
    items: [],
    total: 0,
    ...NO_POSITION,
  })
  vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({ matches: false }))
}
