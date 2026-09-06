import { describe, expect, it } from 'vitest'

import {
  matchProjectId,
  PROJECT_CONTEXT_ROUTE_PATHS,
  PROJECT_NAV_TARGETS,
  PROJECT_ROUTE_PATHS,
  resolveActiveNavTargetId,
} from './projectRoutes'

/**
 * Reines Modul ohne React (specs/features/0298-projektnavigation-in-der-kopfzeile.md,
 * Teststrategie): die Fallunterscheidungen werden hier geprueft, NICHT auf Rendering-Ebene. Die
 * frueher in App.test.tsx gefuehrten Sonderfaelle (Query-Parameter, nicht-numerische projectId,
 * verschachtelte :photoId-Route) sind mit dieser Spec hierher gewandert.
 */

/** Die neun Muster mit eingesetzten Parametern - Grundlage beider Funktionen. */
const PATHS_WITH_PROJECT_CONTEXT = [
  '/projects/1',
  '/projects/1/pipeline',
  '/projects/1/pipeline/scan',
  '/projects/1/photos',
  '/projects/1/photos/42',
  '/projects/1/compare',
  '/projects/1/settings',
  '/projects/1/stats',
  '/projects/1/curate',
]

describe('projectRoutes - PROJECT_ROUTE_PATHS', () => {
  it('fuehrt genau die neun Muster mit Projektkontext', () => {
    expect(Object.values(PROJECT_ROUTE_PATHS)).toHaveLength(9)
    expect(PROJECT_CONTEXT_ROUTE_PATHS).toHaveLength(9)
    expect([...PROJECT_CONTEXT_ROUTE_PATHS].sort()).toEqual(
      [
        '/projects/:projectId',
        '/projects/:projectId/compare',
        '/projects/:projectId/curate',
        '/projects/:projectId/photos',
        '/projects/:projectId/photos/:photoId',
        '/projects/:projectId/pipeline',
        '/projects/:projectId/pipeline/:step',
        '/projects/:projectId/settings',
        '/projects/:projectId/stats',
      ].sort()
    )
  })

  // AK2: /curate ist neu im Projektkontext und kehrt die ausdrueckliche Gegenfestlegung aus
  // Spec 0033 um - ein eigener Fall, nicht nur ein Tabelleneintrag.
  it('enthaelt die Kuratierungsroute (AK2, Umkehrung der Spec-0033-Ausnahme)', () => {
    expect(PROJECT_ROUTE_PATHS.curate).toBe('/projects/:projectId/curate')
    expect(PROJECT_CONTEXT_ROUTE_PATHS).toContain('/projects/:projectId/curate')
  })
})

describe('projectRoutes - matchProjectId', () => {
  it.each(PATHS_WITH_PROJECT_CONTEXT)('erkennt %s als Projektkontext', (pathname) => {
    expect(matchProjectId(pathname)).toBe('1')
  })

  // Der Umzug von RESERVED_PROJECT_ID_SEGMENTS in ein neues Modul ist genau die Gelegenheit, bei
  // der die Zeile still verlorengeht (Edge Case der Spec) - deshalb hier UND als Rendering-Fall
  // in App.test.tsx.
  it.each(['/', '/projects/new', '/login', '/some/unknown/path', '/projects'])(
    'weist %s ab',
    (pathname) => {
      expect(matchProjectId(pathname)).toBeNull()
    }
  )

  it('akzeptiert eine nicht-numerische projectId ohne clientseitige Validierung', () => {
    expect(matchProjectId('/projects/abc/photos')).toBe('abc')
  })

  it('liest den Pfad ohne Query-Parameter (matchPath bekommt nur den pathname)', () => {
    expect(matchProjectId('/projects/1/photos')).toBe('1')
  })

  it('liest die projectId auch aus der verschachtelten Foto-Detailroute', () => {
    expect(matchProjectId('/projects/7/photos/42')).toBe('7')
  })
})

describe('projectRoutes - PROJECT_NAV_TARGETS', () => {
  // Die Anzeigereihenfolge IST die Array-Reihenfolge (Leiste UND Panel) und haette sonst keinen
  // Waechter.
  it('fuehrt genau vier Ziele in fixierter Reihenfolge (AK1)', () => {
    expect(PROJECT_NAV_TARGETS).toHaveLength(4)
    expect(PROJECT_NAV_TARGETS.map((target) => target.id)).toEqual([
      'pipeline',
      'photos',
      'compare',
      'settings',
    ])
    expect(PROJECT_NAV_TARGETS.map((target) => target.label)).toEqual([
      'Projekt',
      'Fotos',
      'Vergleich',
      'Einstellungen',
    ])
  })

  it.each([
    ['pipeline', '/projects/1/pipeline'],
    ['photos', '/projects/1/photos'],
    ['compare', '/projects/1/compare'],
    ['settings', '/projects/1/settings'],
  ])('baut fuer %s den Pfad %s', (id, expected) => {
    const target = PROJECT_NAV_TARGETS.find((candidate) => candidate.id === id)
    expect(target, `Ziel ${id}`).toBeDefined()
    expect(target!.buildPath('1')).toBe(expected)
  })

  // Rundlauf fuer einen nicht-numerischen, zeichenharmlosen Wert (bestehende Konvention):
  // matchPath dekodiert, buildPath kodiert nicht - ein einseitiges encodeURIComponent braeche ihn.
  it('haelt den Rundlauf matchProjectId -> buildPath fuer eine nicht-numerische id', () => {
    for (const target of PROJECT_NAV_TARGETS) {
      expect(matchProjectId(target.buildPath('abc'))).toBe('abc')
    }
  })
})

describe('projectRoutes - resolveActiveNavTargetId', () => {
  it.each([
    // Der Redirect-Zwischenzustand zaehlt bereits als "Projektuebersicht aktiv", damit der Marker
    // nicht flackert.
    ['/projects/1', 'pipeline'],
    // Basiszustand ohne :step - der Fall, den bei Spec 0042 erst ein Copilot-Review fand.
    ['/projects/1/pipeline', 'pipeline'],
    ['/projects/1/pipeline/kriterien', 'pipeline'],
    ['/projects/1/photos', 'photos'],
    ['/projects/1/photos/42', 'photos'],
    ['/projects/1/compare', 'compare'],
    ['/projects/1/settings', 'settings'],
  ])('markiert auf %s das Ziel %s als aktiv (AK8a)', (pathname, expected) => {
    expect(resolveActiveNavTargetId(pathname)).toBe(expected)
  })

  // AK8b: Querschnittsansichten. Ein Link als aktiv zu markieren, der woanders hinfuehrt, waere
  // schlechter als gar kein Marker.
  it.each(['/projects/1/stats', '/projects/1/curate'])(
    'markiert auf %s kein Ziel als aktiv (AK8b)',
    (pathname) => {
      expect(resolveActiveNavTargetId(pathname)).toBeNull()
    }
  )

  it.each(['/', '/projects/new', '/login', '/some/unknown/path'])(
    'liefert ohne Projektkontext null (%s)',
    (pathname) => {
      expect(resolveActiveNavTargetId(pathname)).toBeNull()
    }
  )
})
