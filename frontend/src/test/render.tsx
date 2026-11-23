/* oxlint-disable react/only-export-components -- Testhelfer, kein Fast-Refresh-Modul */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, type RenderOptions, type RenderResult } from '@testing-library/react'
import type { ReactElement, ReactNode } from 'react'
import { MemoryRouter, type InitialEntry } from 'react-router'

/**
 * Die Testumgebung des Frontends - die EINE Fundstelle (specs/architecture/0002-testkonzept.md).
 *
 * Echter `QueryClient` (kein Retry) und echter `MemoryRouter`, API-Module je Testdatei gemockt.
 * Wer eine eigene Route oder einen eigenen Client braucht, gibt ihn hier hinein, statt die
 * Umgebung ein zweites Mal zusammenzubauen.
 */

/** Ein QueryClient fuer Tests: weder Abfragen noch Mutationen wiederholen. */
export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
}

/** Wrapper-Komponente mit dem Client - fuer `render`/`renderHook` ohne Router. */
export function queryWrapper(
  queryClient: QueryClient,
): (props: { children: ReactNode }) => ReactElement {
  return function Wrapper({ children }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
}

/** Frischer Client samt Wrapper, wenn ein Test den Cache beobachten oder teilen will. */
export function createQueryWrapper(): {
  queryClient: QueryClient
  wrapper: (props: { children: ReactNode }) => ReactElement
} {
  const queryClient = makeQueryClient()
  return { queryClient, wrapper: queryWrapper(queryClient) }
}

export interface ProvidersOptions extends Omit<RenderOptions, 'wrapper'> {
  /** Startpfad des MemoryRouter; ignoriert, sobald `initialEntries` gesetzt ist. */
  path?: string
  initialEntries?: InitialEntry[]
  /** Index des aktiven Eintrags in `initialEntries` (Vorgabe: der letzte, wie bei MemoryRouter). */
  initialIndex?: number
  /** Vorbereiteter Client, etwa wenn ein Test seinen Cache beobachten will. */
  queryClient?: QueryClient
}

/** Die Umgebung als Element - fuer Faelle, die selbst `render` aufrufen. */
export function withProviders(node: ReactNode, options: ProvidersOptions = {}): ReactElement {
  const { path = '/', initialEntries, initialIndex, queryClient = makeQueryClient() } = options
  return (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={initialEntries ?? [path]} initialIndex={initialIndex}>
        {node}
      </MemoryRouter>
    </QueryClientProvider>
  )
}

/** Nur der QueryClient, ohne Router - fuer Komponenten und Hooks, die keine Route brauchen. */
export function withQuery(
  node: ReactNode,
  queryClient: QueryClient = makeQueryClient(),
): ReactElement {
  return <QueryClientProvider client={queryClient}>{node}</QueryClientProvider>
}

/**
 * Wrapper, der bei jedem Render einen frischen Client baut - fuer `renderHook` und Faelle, in
 * denen ein Test den Client nicht beobachten muss. Wer den Cache teilen will, nimmt
 * `queryWrapper(client)`.
 */
export function FreshQueryWrapper({ children }: { children: ReactNode }): ReactElement {
  return withQuery(children)
}

/** Rendert `ui` in der gemeinsamen Umgebung. */
export function renderWithProviders(
  ui: ReactElement,
  options: ProvidersOptions = {},
): RenderResult {
  return render(withProviders(ui, options))
}
