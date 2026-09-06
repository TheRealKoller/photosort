import { matchPath } from 'react-router'

/*
 * Einzige Quelle der Wahrheit fuer alles, was am Projektkontext einer Route haengt
 * (specs/features/0298-projektnavigation-in-der-kopfzeile.md, Architektur-Abschnitt): welche
 * Routen es mit Projektbezug gibt, welcher Pfad Projektkontext hat, und welches der vier
 * Navigationsziele gerade aktiv ist.
 *
 * REINES TYPESCRIPT OHNE REACT-IMPORT (Vorbild: utils/pipelineSteps.ts, das PIPELINE_STEPS fuer
 * den Stepper haelt). Bewusst NICHT in App.tsx: sonst importierte components/ProjectNav.tsx aus
 * genau der Datei, die ProjectNav rendert.
 */

/**
 * Die neun Pfadmuster mit Projektkontext, benannt statt nur aufgezaehlt - App.tsx bezieht daraus
 * sowohl die <Route>-Deklarationen als auch die Matching-Liste, sodass eine kuenftige Route nicht
 * mehr nur in einer der beiden Stellen landen kann.
 */
export const PROJECT_ROUTE_PATHS = {
  detail: '/projects/:projectId',
  pipelineBase: '/projects/:projectId/pipeline',
  pipelineStep: '/projects/:projectId/pipeline/:step',
  photos: '/projects/:projectId/photos',
  photoDetail: '/projects/:projectId/photos/:photoId',
  compare: '/projects/:projectId/compare',
  settings: '/projects/:projectId/settings',
  stats: '/projects/:projectId/stats',
  // specs/features/0298: NEU im Projektkontext - kehrt die ausdrueckliche Gegenfestlegung aus
  // Spec 0033 um (dort trug die Kuratierungsseite bewusst keinen Kopfzeilen-Projektbezug). Spec
  // 0033 traegt dazu einen datierten Nachtrag statt eines Superseded-Status.
  curate: '/projects/:projectId/curate',
} as const

/**
 * Alle Muster als flache Liste - Grundlage von matchProjectId. EXPLIZITE AUFZAEHLUNG STATT
 * WILDCARD bleibt zwingend: ein "/projects/:projectId/*" wuerde "/projects/new" faelschlich als
 * Projektkontext mit projectId="new" lesen.
 */
export const PROJECT_CONTEXT_ROUTE_PATHS: readonly string[] = Object.values(PROJECT_ROUTE_PATHS)

/**
 * Literale Geschwister-Segmente unter /projects/, die keine projectId sind. Anders als React
 * Routers eigentliches Routing (das statische Segmente vor dynamischen bevorzugt) matcht ein
 * isolierter matchPath-Aufruf "/projects/new" gegen "/projects/:projectId" mit projectId="new".
 *
 * ACHTUNG: Dies ist KEINE automatisch abgeleitete Liste - eine kuenftige neue literale
 * Geschwister-Route unter /projects/ (z.B. "/projects/import") muss hier VON HAND ergaenzt
 * werden, sonst matcht sie faelschlich als Projektkontext.
 */
export const RESERVED_PROJECT_ID_SEGMENTS: ReadonlySet<string> = new Set(['new'])

/**
 * Die projectId eines Pfads, oder null ohne Projektkontext. Reine Funktion, kein Hook - dadurch
 * ohne Router-Provider testbar; App.tsx setzt seinen Hook als Einzeiler darauf.
 */
export function matchProjectId(pathname: string): string | null {
  for (const path of PROJECT_CONTEXT_ROUTE_PATHS) {
    const projectId = matchPath(path, pathname)?.params.projectId
    if (projectId !== undefined && projectId !== '' && !RESERVED_PROJECT_ID_SEGMENTS.has(projectId)) {
      return projectId
    }
  }
  return null
}

export type ProjectNavTargetId = 'pipeline' | 'photos' | 'compare' | 'settings'

export interface ProjectNavTarget {
  id: ProjectNavTargetId
  /** Sichtbarer Text UND zugaenglicher Name - steht genau hier und nirgends sonst. */
  label: string
  buildPath: (projectId: string) => string
  /** Muster, auf denen dieses Ziel als aktiv markiert wird. */
  activeRoutePaths: readonly string[]
}

/**
 * Die vier gleichrangigen Navigationsziele eines Projekts. DIE REIHENFOLGE IM ARRAY IST DIE
 * REIHENFOLGE IN DER LEISTE UND IM PANEL (specs/features/0298, Zuordnungstabelle).
 *
 * "Projekt" zeigt auf /pipeline statt auf /projects/{id}: letzteres ist laut eigenem Kommentar in
 * App.tsx ein reiner Bestandsschutz-Redirect fuer alte Lesezeichen, kein Ziel. Der
 * Redirect-Zwischenzustand zaehlt trotzdem als "Projektuebersicht aktiv", damit der Marker
 * waehrend des kurzen Zustands nicht flackert.
 *
 * buildPath kodiert bewusst NICHT (kein encodeURIComponent): matchPath dekodiert, ein einseitiges
 * Kodieren braeche den Rundlauf. Prozentkodierte IDs sind ueber die Oberflaeche unerreichbar (IDs
 * sind ganzzahlig aus dem Backend) - unveraendert zum bisherigen Verhalten in App.tsx.
 */
export const PROJECT_NAV_TARGETS: readonly ProjectNavTarget[] = [
  {
    id: 'pipeline',
    label: 'Projekt',
    buildPath: (projectId) => `/projects/${projectId}/pipeline`,
    activeRoutePaths: [
      PROJECT_ROUTE_PATHS.detail,
      PROJECT_ROUTE_PATHS.pipelineBase,
      PROJECT_ROUTE_PATHS.pipelineStep,
    ],
  },
  {
    id: 'photos',
    label: 'Fotos',
    buildPath: (projectId) => `/projects/${projectId}/photos`,
    activeRoutePaths: [PROJECT_ROUTE_PATHS.photos, PROJECT_ROUTE_PATHS.photoDetail],
  },
  {
    id: 'compare',
    label: 'Vergleich',
    buildPath: (projectId) => `/projects/${projectId}/compare`,
    activeRoutePaths: [PROJECT_ROUTE_PATHS.compare],
  },
  {
    id: 'settings',
    label: 'Einstellungen',
    buildPath: (projectId) => `/projects/${projectId}/settings`,
    activeRoutePaths: [PROJECT_ROUTE_PATHS.settings],
  },
]

/**
 * Das aktuell aktive Navigationsziel, oder null. Null bedeutet zweierlei und ist in beiden Faellen
 * richtig: gar kein Projektkontext, ODER eine Querschnittsansicht (/stats, /curate), die zu keinem
 * der vier Ziele gehoert - ein Link als aktiv zu markieren, der woanders hinfuehrt, waere
 * schlechter als gar kein Marker (AK8b).
 */
export function resolveActiveNavTargetId(pathname: string): ProjectNavTargetId | null {
  if (matchProjectId(pathname) === null) {
    return null
  }
  const target = PROJECT_NAV_TARGETS.find((candidate) =>
    candidate.activeRoutePaths.some((path) => matchPath(path, pathname) !== null)
  )
  return target?.id ?? null
}
