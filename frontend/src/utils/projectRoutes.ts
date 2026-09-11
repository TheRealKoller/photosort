import { matchPath } from 'react-router'

/*
 * Einzige Quelle der Wahrheit für alles, was am Projektkontext einer Route hängt: welche
 * Routen es mit Projektbezug gibt, welcher Pfad Projektkontext hat, und welches der fünf
 * Navigationsziele gerade aktiv ist.
 *
 * REINES TYPESCRIPT OHNE REACT-IMPORT. Bewusst NICHT in App.tsx: sonst importierte
 * components/ProjectNav.tsx aus genau der Datei, die ProjectNav rendert.
 */

/**
 * Die neun Pfadmuster mit Projektkontext, benannt statt nur aufgezählt - App.tsx bezieht
 * daraus sowohl die <Route>-Deklarationen als auch die Matching-Liste, sodass eine neue
 * Route nicht mehr nur an einer der beiden Stellen landen kann.
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
    if (
      projectId !== undefined &&
      projectId !== '' &&
      !RESERVED_PROJECT_ID_SEGMENTS.has(projectId)
    ) {
      return projectId
    }
  }
  return null
}

export type ProjectNavTargetId = 'pipeline' | 'photos' | 'compare' | 'settings' | 'stats'

export interface ProjectNavTarget {
  id: ProjectNavTargetId
  /** Sichtbarer Text UND zugaenglicher Name - steht genau hier und nirgends sonst. */
  label: string
  buildPath: (projectId: string) => string
  /** Muster, auf denen dieses Ziel als aktiv markiert wird. */
  activeRoutePaths: readonly string[]
}

/*
 * ZWEI GRUPPEN STATT EINER FLACHEN LISTE: die drei Hauptziele, zwischen denen beim Sortieren
 * ständig gewechselt wird, und die zwei Nebenziele, die selten gebraucht werden und deshalb
 * nicht denselben Platz in der Leiste beanspruchen. DIE REIHENFOLGE INNERHALB EINER GRUPPE
 * IST DIE ANZEIGEREIHENFOLGE (Leiste UND Panel).
 *
 * "Projekt" zeigt auf /pipeline statt auf /projects/{id}: letzteres ist ein reiner
 * Bestandsschutz-Redirect für alte Lesezeichen, kein Ziel. Der Redirect-Zwischenzustand zählt
 * trotzdem als "Projektübersicht aktiv", damit der Marker während des kurzen Zustands nicht
 * flackert.
 *
 * buildPath kodiert bewusst NICHT (kein encodeURIComponent): matchPath dekodiert, ein
 * einseitiges Kodieren bräche den Rundlauf. Prozentkodierte IDs sind über die Oberfläche
 * unerreichbar, IDs sind ganzzahlig aus dem Backend.
 */
export const PROJECT_NAV_PRIMARY_TARGETS: readonly ProjectNavTarget[] = [
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
]

/** Die beiden Nebenziele. */
export const PROJECT_NAV_SECONDARY_TARGETS: readonly ProjectNavTarget[] = [
  {
    id: 'settings',
    label: 'Einstellungen',
    buildPath: (projectId) => `/projects/${projectId}/settings`,
    activeRoutePaths: [PROJECT_ROUTE_PATHS.settings],
  },
  {
    id: 'stats',
    label: 'Statistik',
    buildPath: (projectId) => `/projects/${projectId}/stats`,
    activeRoutePaths: [PROJECT_ROUTE_PATHS.stats],
  },
]

/**
 * Beide Gruppen in Anzeigereihenfolge - Grundlage von resolveActiveNavTargetId. ProjectNav
 * konsumiert diese Liste NICHT: das Panel mappt die beiden Gruppen getrennt, weil der Block der
 * Hauptziele einen eigenen Container mit Trenner und `lg:hidden` braucht.
 *
 * ABGELEITET STATT AUSGESCHRIEBEN: eine dritte, von Hand gepflegte Liste waere genau die Kopie,
 * die beim naechsten neuen Ziel auseinanderlaeuft.
 */
export const ALL_PROJECT_NAV_TARGETS: readonly ProjectNavTarget[] = [
  ...PROJECT_NAV_PRIMARY_TARGETS,
  ...PROJECT_NAV_SECONDARY_TARGETS,
]

/**
 * Gehört dieses Ziel dem Nebenbereich an? Trägt die Aktiv-Markierung des geschlossenen
 * Auslösers und ist bewusst eine REINE FUNKTION statt eines Inline-Ausdrucks in ProjectNav:
 * so ist sie ohne Rendering prüfbar.
 *
 * `null` ist ausdrücklich KEIN Nebenbereich. Die naheliegende Fehlimplementierung "kein
 * Hauptziel aktiv, also Nebenbereich" markierte den Auslöser auf /curate fälschlich als
 * aktuell.
 */
export function isSecondaryNavTargetId(id: ProjectNavTargetId | null): boolean {
  return id !== null && PROJECT_NAV_SECONDARY_TARGETS.some((target) => target.id === id)
}

/**
 * Das aktuell aktive Navigationsziel, oder null. Null bedeutet zweierlei und ist in beiden
 * Fällen richtig: gar kein Projektkontext, ODER die Kuratierung (/curate), die zu keinem der
 * fünf Ziele gehört - einen Link als aktiv zu markieren, der woanders hinführt, wäre
 * schlechter als gar kein Marker.
 */
export function resolveActiveNavTargetId(pathname: string): ProjectNavTargetId | null {
  if (matchProjectId(pathname) === null) {
    return null
  }
  const target = ALL_PROJECT_NAV_TARGETS.find((candidate) =>
    candidate.activeRoutePaths.some((path) => matchPath(path, pathname) !== null),
  )
  return target?.id ?? null
}
