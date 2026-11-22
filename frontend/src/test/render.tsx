import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, type RenderOptions, type RenderResult } from '@testing-library/react'
import type { ReactElement, ReactNode } from 'react'
import { MemoryRouter } from 'react-router'

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

export interface ProvidersOptions extends Omit<RenderOptions, 'wrapper'> {
  /** Startpfad des MemoryRouter; ignoriert, sobald `initialEntries` gesetzt ist. */
  path?: string
  initialEntries?: string[]
  /** Vorbereiteter Client, etwa wenn ein Test seinen Cache beobachten will. */
  queryClient?: QueryClient
}

/** Die Umgebung als Element - fuer Faelle, die selbst `render` aufrufen. */
export function withProviders(node: ReactNode, options: ProvidersOptions = {}): ReactElement {
  const { path = '/', initialEntries, queryClient = makeQueryClient() } = options
  return (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={initialEntries ?? [path]}>{node}</MemoryRouter>
    </QueryClientProvider>
  )
}

/** Rendert `ui` in der gemeinsamen Umgebung. */
export function renderWithProviders(
  ui: ReactElement,
  options: ProvidersOptions = {},
): RenderResult {
  return render(withProviders(ui, options))
}
