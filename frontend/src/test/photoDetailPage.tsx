/*
 * Gemeinsamer Unterbau der Tests der Foto-Detailseite (`src/pages/PhotoDetailPage.*.test.tsx`):
 * Fotoobjekt, Abfragefabriken, Render-Funktion und Mock-Grundzustand. Die `vi.mock(...)`-Aufrufe
 * stehen in jeder Testdatei selbst (vitest hebt sie je Datei), die Module hier sind dann dieselben
 * Attrappen.
 */
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { vi } from 'vitest'

import * as personsApi from '../api/persons'
import * as photosApi from '../api/photos'
import * as ratingsApi from '../api/ratings'
import * as motifsApi from '../api/motifs'
import type {
  CloudVisionStatusOut,
  CriterionScoreOut,
  MotifAssessmentOut,
  MotifStrengthOut,
  PhotoOut,
  SuggestionOut,
} from '../api/types'
import { setToken } from '../auth/token'
import { PhotoDetailPage } from '../pages/PhotoDetailPage'
import { MOTIF_KEYS, MOTIF_SET } from './motifSetFixture'
import { makePhoto } from './fixtures'
import { makeQueryClient, queryWrapper } from './render'

export function makeToken(payload: unknown): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
  const body = btoa(JSON.stringify(payload))
  return `${header}.${body}.signature-irrelevant`
}

export function photo(overrides: Partial<PhotoOut> = {}): PhotoOut {
  return makePhoto({
    taken_at: '2026-07-20T10:00:00Z',
    taken_at_original: '2026-07-20T10:00:00Z',
    ...overrides,
  })
}

export function criterionScore(overrides: Partial<CriterionScoreOut> = {}): CriterionScoreOut {
  return {
    criterion_key: 'sharpness',
    display_name: 'Schärfe',
    value: 0.8,
    source: 'local_heuristic',
    // Default-Key ist `sharpness` (ohne Praesenz-Schwelle) - der Default muss dazu passen,
    // damit kein Bestandstest unbemerkt in den Bildinhalt-Block rutscht.
    has_presence_threshold: false,
    ...overrides,
  }
}

export function suggestion(overrides: Partial<SuggestionOut> = {}): SuggestionOut {
  return {
    status: 'rejected',
    reason: 'low_quality',
    duplicate_of: null,
    sharpness: 1.0,
    exposure: 0.5,
    cluster_key: null,
    computed_at: '2026-07-20T10:00:00Z',
    ...overrides,
  }
}

// specs/features/0427-motive-mit-staerke.md: die Kopfzeile des Regelfalls (Cloud-Grundlage, nicht
// ausgeschlossen) und ein vollbesetzter Achter-Vektor.
export const CLOUD_ASSESSMENT: MotifAssessmentOut = {
  source: 'cloud',
  provider: 'anthropic',
  excluded_document: false,
  computed_at: '2026-09-12T10:00:00',
}

export function motifStrengths(
  overrides: Record<string, Partial<MotifStrengthOut>> = {},
): MotifStrengthOut[] {
  return MOTIF_KEYS.map((key) => ({
    key,
    strength: 0,
    correction: null,
    // Bewusst NICHT aus `strength` abgeleitet: `present` ist die Aussage des Servers, und eine
    // Kopplung hier machte jeden Fall blind fuer eine Oberflaeche, die doch selbst vergleicht.
    present: false,
    ...(overrides[key] ?? {}),
  }))
}

export function cloudVisionStatusEntry(
  overrides: Partial<CloudVisionStatusOut> = {},
): CloudVisionStatusOut {
  return {
    phase: 'landmark',
    status: 'not_run',
    error_message: null,
    attempted_at: null,
    ...overrides,
  }
}

export function renderPage(initialPath: string) {
  const queryClient = makeQueryClient()
  const wrapper = queryWrapper(queryClient)
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/projects/:projectId/photos" element={<p>Grid-Seite</p>} />
        <Route path="/projects/:projectId/photos/:photoId" element={<PhotoDetailPage />} />
      </Routes>
    </MemoryRouter>,
    { wrapper },
  )
}

/** Die permanente Motivsektion - von mehreren Beschreibungsbloecken gebraucht. */
export function motifSection(): HTMLElement {
  return screen.getByTestId('motifs-section')
}

/**
 * Vorbereitung jedes Falls der Detailseite: alle Abrufe zuruecksetzen, Motivset und Bildabruf
 * vorbelegen, angemeldeten Nutzer setzen. Kein window.matchMedia-Stub noetig: Die Seite bindet
 * kein Popover mit geraetespezifischem Oeffnungsverhalten ein.
 */
export function resetPhotoDetailMocks(): void {
  vi.mocked(photosApi.listPhotos).mockReset()
  vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockReset()
  vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockResolvedValue('blob:fake-url')
  vi.mocked(ratingsApi.setRating).mockReset()
  vi.mocked(ratingsApi.setFavorite).mockReset()
  vi.mocked(motifsApi.listMotifs).mockReset()
  vi.mocked(motifsApi.listMotifs).mockResolvedValue(MOTIF_SET)
  vi.mocked(photosApi.setMotifCorrection).mockReset()
  vi.mocked(photosApi.deleteMotifCorrection).mockReset()
  vi.mocked(ratingsApi.deleteRating).mockReset()
  setToken(makeToken({ sub: '1', username: 'testuser' }))
}

/** Die Vorgabe "keine Person festgelegt": der Personenabschnitt und der Personenfilter laden
 * `GET /persons` in JEDEM Block; ein Block, der Personen braucht, setzt sie selbst. */
export function resetPersonsMock(): void {
  vi.mocked(personsApi.listPersons).mockReset()
  vi.mocked(personsApi.listPersons).mockResolvedValue([])
}
