import { matchPath } from 'react-router'

/*
 * Einzige Quelle der Wahrheit fuer alles, was am Projektkontext einer Route haengt
 * (specs/features/0298-projektnavigation-in-der-kopfzeile.md, Architektur-Abschnitt; seit
 * specs/features/0347-navigation-nebenbereich.md in zwei Gruppen): welche Routen es mit
 * Projektbezug gibt, welcher Pfad Projektkontext hat, und welches der fuenf Navigationsziele
 * gerade aktiv ist.
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
 * ZWEI GRUPPEN STATT EINER FLACHEN LISTE (specs/features/0347-navigation-nebenbereich.md): die
 * drei Hauptziele, zwischen denen beim Sortieren staendig gewechselt wird, und die zwei
 * Nebenziele, die selten gebraucht werden und deshalb nicht denselben Platz in der Leiste
 * beanspruchen. DIE REIHENFOLGE INNERHALB EINER GRUPPE IST DIE ANZEIGEREIHENFOLGE (Leiste UND
 * Panel).
 *
 * DER NAME `PROJECT_NAV_TARGETS` IST BEWUSST VERSCHWUNDEN statt "alle fuenf" zu bedeuten: haette
 * er ueberlebt, aenderte sich die Bedeutung eines Bezeichners still unter allen bestehenden
 * Aufrufstellen hinweg, und jede von ihnen kompilierte zufaellig weiter.
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

/**
 * Die beiden Nebenziele. `stats` ist mit Spec 0347 ueberhaupt erst ein Navigationsziel geworden -
 * bis dahin war die Statistikseite eine Querschnittsansicht ohne Eintrag und ausschliesslich ueber
 * einen Link am Ende der Pipeline-Seite erreichbar.
 */
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
 * Gehoert dieses Ziel dem Nebenbereich an? Traegt die Aktiv-Markierung des geschlossenen
 * Ausloesers (AK6) und ist bewusst eine REINE FUNKTION statt eines Inline-Ausdrucks in
 * ProjectNav: so ist sie ohne Rendering pruefbar.
 *
 * `null` ist ausdruecklich KEIN Nebenbereich. Die naheliegende Fehlimplementierung "kein Hauptziel
 * aktiv, also Nebenbereich" markierte den Ausloeser auf /curate faelschlich als aktuell.
 */
export function isSecondaryNavTargetId(id: ProjectNavTargetId | null): boolean {
  return id !== null && PROJECT_NAV_SECONDARY_TARGETS.some((target) => target.id === id)
}

/**
 * Das aktuell aktive Navigationsziel, oder null. Null bedeutet zweierlei und ist in beiden Faellen
 * richtig: gar kein Projektkontext, ODER die Kuratierung (/curate), die zu keinem der fuenf Ziele
 * gehoert - ein Link als aktiv zu markieren, der woanders hinfuehrt, waere schlechter als gar kein
 * Marker (AK8b). /stats faellt seit Spec 0347 NICHT mehr darunter: es ist ein Nebenziel geworden
 * und wird als solches markiert.
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
