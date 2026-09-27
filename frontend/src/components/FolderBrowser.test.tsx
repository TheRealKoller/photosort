import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Profiler, useState } from 'react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as opencloudApi from '../api/opencloud'
import { ApiError } from '../api/client'
import type { BrowseEntry, FolderCountOut } from '../api/types'
import { FolderBrowser } from './FolderBrowser'

vi.mock('../api/opencloud')

function renderWithClient(ui: ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return render(ui, { wrapper })
}

function renderBrowser(value: string, onChange = vi.fn(), onErrorChange = vi.fn()) {
  const utils = renderWithClient(
    <FolderBrowser value={value} onChange={onChange} onErrorChange={onErrorChange} />,
  )
  return { ...utils, onChange, onErrorChange }
}

describe('FolderBrowser', () => {
  beforeEach(() => {
    vi.mocked(opencloudApi.browseFolder).mockReset()
    vi.mocked(opencloudApi.fetchFolderCounts).mockReset()
    // Standard-Fixture fuer Tests, denen die konkreten Zaehler egal sind - vermeidet ein
    // dauerhaft haengendes Ladeicon (unresolved Promise) in jedem bereits bestehenden Test.
    vi.mocked(opencloudApi.fetchFolderCounts).mockResolvedValue([])
  })

  it('loads the root level (no path) when value is empty', async () => {
    vi.mocked(opencloudApi.browseFolder).mockResolvedValue([
      { name: 'CostaRica', path: 'CostaRica', modified_at: null },
    ])

    renderBrowser('')

    await waitFor(() => expect(opencloudApi.browseFolder).toHaveBeenCalledWith(''))
    expect(await screen.findByText('CostaRica')).toBeInTheDocument()
  })

  it('calls onChange with the child path when a folder entry is clicked', async () => {
    vi.mocked(opencloudApi.browseFolder).mockResolvedValue([
      { name: 'Sub', path: 'CostaRica/Sub', modified_at: null },
    ])
    const user = userEvent.setup()

    const { onChange } = renderBrowser('CostaRica')

    const entry = await screen.findByRole('button', { name: 'Sub' })
    await user.click(entry)

    expect(onChange).toHaveBeenCalledWith('CostaRica/Sub')
  })

  it('renders a breadcrumb for the current path with a clickable root and each segment', async () => {
    vi.mocked(opencloudApi.browseFolder).mockResolvedValue([])
    const user = userEvent.setup()

    const { onChange } = renderBrowser('CostaRica/Sub')

    await waitFor(() => expect(opencloudApi.browseFolder).toHaveBeenCalledWith('CostaRica/Sub'))

    await user.click(screen.getByRole('button', { name: /wurzel|root/i }))
    expect(onChange).toHaveBeenCalledWith('')

    await user.click(screen.getByRole('button', { name: 'CostaRica' }))
    expect(onChange).toHaveBeenCalledWith('CostaRica')
  })

  it('shows an inline error and reports it via onErrorChange on a backend error', async () => {
    vi.mocked(opencloudApi.browseFolder).mockRejectedValue(
      new ApiError(400, 'Ordner nicht gefunden'),
    )

    const { onErrorChange } = renderBrowser('Nope')

    expect(await screen.findByText('Ordner nicht gefunden')).toBeInTheDocument()
    await waitFor(() => expect(onErrorChange).toHaveBeenCalledWith(true))
  })

  it('reports no error via onErrorChange once loading succeeds', async () => {
    vi.mocked(opencloudApi.browseFolder).mockResolvedValue([])

    const { onErrorChange } = renderBrowser('CostaRica')

    await waitFor(() => expect(onErrorChange).toHaveBeenCalledWith(false))
  })

  it('does not refetch an already-loaded level when navigating back to it via the breadcrumb', async () => {
    vi.mocked(opencloudApi.browseFolder).mockResolvedValue([
      { name: 'Sub', path: 'CostaRica/Sub', modified_at: null },
    ])
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    )

    const { rerender } = render(
      <FolderBrowser value="CostaRica" onChange={vi.fn()} onErrorChange={vi.fn()} />,
      { wrapper },
    )
    await waitFor(() => expect(opencloudApi.browseFolder).toHaveBeenCalledTimes(1))

    rerender(<FolderBrowser value="CostaRica/Sub" onChange={vi.fn()} onErrorChange={vi.fn()} />)
    await waitFor(() => expect(opencloudApi.browseFolder).toHaveBeenCalledTimes(2))

    rerender(<FolderBrowser value="CostaRica" onChange={vi.fn()} onErrorChange={vi.fn()} />)
    await waitFor(() => screen.findByText('Sub'))

    // Zurueckspringen auf eine bereits geladene Ebene darf keinen dritten Request ausloesen
    // (React-Query-Cache pro Pfad, siehe specs/features/0005-minimal-project-frontend.md).
    expect(opencloudApi.browseFolder).toHaveBeenCalledTimes(2)
  })

  describe('Dateianzahl pro Unterordner (specs/features/0050-dateianzahl-im-ordner-browser.md)', () => {
    it('eagerly fetches folder counts for the same path as the browse request, without a click', async () => {
      vi.mocked(opencloudApi.browseFolder).mockResolvedValue([
        { name: 'Sub', path: 'CostaRica/Sub', modified_at: null },
      ])
      vi.mocked(opencloudApi.fetchFolderCounts).mockResolvedValue([
        { path: 'CostaRica/Sub', count: 3, at_limit: false, error: false },
      ])

      renderBrowser('CostaRica')

      await waitFor(() => expect(opencloudApi.fetchFolderCounts).toHaveBeenCalledWith('CostaRica'))
    })

    it('shows a loading indicator while the count request is pending', async () => {
      vi.mocked(opencloudApi.browseFolder).mockResolvedValue([
        { name: 'Sub', path: 'CostaRica/Sub', modified_at: null },
      ])
      vi.mocked(opencloudApi.fetchFolderCounts).mockReturnValue(new Promise(() => {}))

      renderBrowser('CostaRica')

      expect(await screen.findByTestId('folder-count-loading')).toBeInTheDocument()
    })

    it('shows the exact count once loaded', async () => {
      vi.mocked(opencloudApi.browseFolder).mockResolvedValue([
        { name: 'Sub', path: 'CostaRica/Sub', modified_at: null },
      ])
      vi.mocked(opencloudApi.fetchFolderCounts).mockResolvedValue([
        { path: 'CostaRica/Sub', count: 42, at_limit: false, error: false },
      ])

      renderBrowser('CostaRica')

      expect(await screen.findByText('42')).toBeInTheDocument()
    })

    it('shows "0" (not hidden) for a folder with zero images', async () => {
      vi.mocked(opencloudApi.browseFolder).mockResolvedValue([
        { name: 'Sub', path: 'CostaRica/Sub', modified_at: null },
      ])
      vi.mocked(opencloudApi.fetchFolderCounts).mockResolvedValue([
        { path: 'CostaRica/Sub', count: 0, at_limit: false, error: false },
      ])

      renderBrowser('CostaRica')

      expect(await screen.findByText('0')).toBeInTheDocument()
    })

    it('shows "500+" when the folder is at the count limit, with an accessible label (not just title)', async () => {
      // Copilot-Review-Fund (PR #110): title allein ist auf Touch-Geraeten nicht nutzbar und wird
      // von Screenreadern i.d.R. nicht vorgelesen - analog zum Fehlerzustand ("?") braucht "500+"
      // deshalb zusaetzlich ein aria-label, nicht nur title.
      vi.mocked(opencloudApi.browseFolder).mockResolvedValue([
        { name: 'Sub', path: 'CostaRica/Sub', modified_at: null },
      ])
      vi.mocked(opencloudApi.fetchFolderCounts).mockResolvedValue([
        { path: 'CostaRica/Sub', count: 500, at_limit: true, error: false },
      ])

      renderBrowser('CostaRica')

      const indicator = await screen.findByText('500+')
      expect(indicator).toBeInTheDocument()
      expect(indicator).toHaveAttribute('aria-label', 'Mindestens 500 Bilder')
    })

    it('shows an error indicator for a subfolder whose count failed, without affecting others', async () => {
      vi.mocked(opencloudApi.browseFolder).mockResolvedValue([
        { name: 'Good', path: 'CostaRica/Good', modified_at: null },
        { name: 'Bad', path: 'CostaRica/Bad', modified_at: null },
      ])
      vi.mocked(opencloudApi.fetchFolderCounts).mockResolvedValue([
        { path: 'CostaRica/Good', count: 7, at_limit: false, error: false },
        { path: 'CostaRica/Bad', count: 0, at_limit: false, error: true },
      ])

      renderBrowser('CostaRica')

      expect(await screen.findByText('7')).toBeInTheDocument()
      expect(await screen.findByText('?')).toBeInTheDocument()
      // Navigation in den fehlerhaften Ordner bleibt unangetastet (kein disabled-Button).
      expect(screen.getByRole('button', { name: 'Bad' })).toBeEnabled()
    })

    it('does not block or delay rendering the folder list while counts are still loading', async () => {
      vi.mocked(opencloudApi.browseFolder).mockResolvedValue([
        { name: 'Sub', path: 'CostaRica/Sub', modified_at: null },
      ])
      vi.mocked(opencloudApi.fetchFolderCounts).mockReturnValue(new Promise(() => {}))

      renderBrowser('CostaRica')

      expect(await screen.findByRole('button', { name: 'Sub' })).toBeInTheDocument()
    })

    it('shows an error indicator for every row when the whole count request fails, without breaking the list', async () => {
      // Review-Fund (test-engineer): der bisherige "Fehler"-Test deckte nur einen einzelnen
      // error:true-Eintrag ab, nicht den kompletten Fehlschlag der Anfrage selbst (z.B.
      // Netzwerkfehler) - der Code behandelt das bereits ueber counts.isError, aber es fehlte
      // eine Testabsicherung dafuer.
      vi.mocked(opencloudApi.browseFolder).mockResolvedValue([
        { name: 'Sub1', path: 'CostaRica/Sub1', modified_at: null },
        { name: 'Sub2', path: 'CostaRica/Sub2', modified_at: null },
      ])
      vi.mocked(opencloudApi.fetchFolderCounts).mockRejectedValue(new Error('Netzwerkfehler'))

      renderBrowser('CostaRica')

      const errorIndicators = await screen.findAllByText('?')
      expect(errorIndicators).toHaveLength(2)
      // Die Liste selbst bleibt unbeeinflusst - beide Ordner weiterhin navigierbar.
      expect(screen.getByRole('button', { name: 'Sub1' })).toBeEnabled()
      expect(screen.getByRole('button', { name: 'Sub2' })).toBeEnabled()
    })
  })

  describe('Sortieren und Suchen (specs/features/0532-ordnerauswahl-sortieren-suchen.md)', () => {
    const HINT = 'Vorläufig nach Name sortiert – die Bildanzahl wird noch gezählt.'

    function folder(parent: string, name: string, modified_at: string | null = null): BrowseEntry {
      return { name, path: parent ? `${parent}/${name}` : name, modified_at }
    }

    function exactCount(path: string, count: number): FolderCountOut {
      return { path, count, at_limit: false, error: false }
    }

    // Die vier Kriterien ergeben auf dieser Ebene paarweise verschiedene Reihenfolgen:
    // Name A–Z a,b,c · Name Z–A c,b,a · Bildanzahl a,c,b · Änderungsdatum b,c,a.
    const LEVEL = [
      folder('Ebene', 'b', '2024-01-01T00:00:00Z'),
      folder('Ebene', 'a', '2022-01-01T00:00:00Z'),
      folder('Ebene', 'c', '2023-01-01T00:00:00Z'),
    ]
    const LEVEL_COUNTS = [
      exactCount('Ebene/b', 1),
      exactCount('Ebene/a', 5),
      exactCount('Ebene/c', 3),
    ]

    function mockLevels(
      levels: Record<string, BrowseEntry[]>,
      counts: Record<string, FolderCountOut[] | Promise<FolderCountOut[]>>,
    ) {
      vi.mocked(opencloudApi.browseFolder).mockImplementation(async (path) => levels[path] ?? [])
      vi.mocked(opencloudApi.fetchFolderCounts).mockImplementation(
        async (path) => counts[path] ?? [],
      )
    }

    function deferredCounts() {
      let resolve: (value: FolderCountOut[]) => void = () => {}
      let reject: (reason: Error) => void = () => {}
      const promise = new Promise<FolderCountOut[]>((res, rej) => {
        resolve = res
        reject = rej
      })
      return { promise, resolve, reject }
    }

    function rowNames(): string[] {
      const list = screen.queryByRole('list')
      if (!list) {
        return []
      }
      return within(list)
        .getAllByRole('listitem')
        .map((item) => within(item).getByRole('button').textContent ?? '')
    }

    const searchField = () => screen.getByRole('textbox', { name: 'Unterordner durchsuchen' })
    const sortSelect = () => screen.getByRole('combobox', { name: 'Sortierung' })

    function NavigatingBrowser({ initial }: { initial: string }) {
      const [value, setValue] = useState(initial)
      return <FolderBrowser value={value} onChange={setValue} />
    }

    it('bietet die Sortierung mit vier Optionen in fester Reihenfolge an, voreingestellt Name A–Z', async () => {
      mockLevels({ Ebene: LEVEL }, { Ebene: LEVEL_COUNTS })

      renderBrowser('Ebene')

      const options = within(sortSelect()).getAllByRole('option')
      expect(options.map((option) => option.textContent)).toEqual([
        'Name A–Z',
        'Name Z–A',
        'Bildanzahl, meiste zuerst',
        'Änderungsdatum, neueste zuerst',
      ])
      expect(sortSelect()).toHaveDisplayValue('Name A–Z')
      await waitFor(() => expect(rowNames()).toEqual(['a', 'b', 'c']))
    })

    it.each([
      [
        'beim Laden',
        () => vi.mocked(opencloudApi.browseFolder).mockReturnValue(new Promise(() => {})),
        () => screen.findByText('Ordner werden geladen…'),
      ],
      [
        'im Fehlerfall',
        () =>
          vi
            .mocked(opencloudApi.browseFolder)
            .mockRejectedValue(new ApiError(400, 'Ordner nicht gefunden')),
        () => screen.findByText('Ordner nicht gefunden'),
      ],
      [
        'in einer leeren Ebene',
        () => vi.mocked(opencloudApi.browseFolder).mockResolvedValue([]),
        () => screen.findByText('Dieser Ordner hat keine Unterordner.'),
      ],
      [
        'mit Liste',
        () => vi.mocked(opencloudApi.browseFolder).mockResolvedValue(LEVEL),
        () => screen.findByRole('button', { name: 'a' }),
      ],
    ])('zeigt Suchfeld und Sortierung aktiv %s', async (_, arrange, reached) => {
      arrange()

      renderBrowser('Ebene')
      await reached()

      expect(searchField()).toBeEnabled()
      expect(sortSelect()).toBeEnabled()
    })

    it.each([
      ['Name A–Z', ['a', 'b', 'c']],
      ['Name Z–A', ['c', 'b', 'a']],
      ['Bildanzahl, meiste zuerst', ['a', 'c', 'b']],
      ['Änderungsdatum, neueste zuerst', ['b', 'c', 'a']],
    ])('ordnet die Ebene bei „%s“', async (option, expected) => {
      mockLevels({ Ebene: LEVEL }, { Ebene: LEVEL_COUNTS })
      const user = userEvent.setup()

      renderBrowser('Ebene')
      await screen.findByText('5')
      await user.selectOptions(sortSelect(), option)

      expect(sortSelect()).toHaveDisplayValue(option)
      expect(rowNames()).toEqual(expected)
    })

    it('zeigt den Hinweis „vorläufig“ nur bei Bildanzahl, solange die Zähler laden', async () => {
      mockLevels({ Ebene: LEVEL }, { Ebene: deferredCounts().promise })
      const user = userEvent.setup()

      renderBrowser('Ebene')
      await screen.findByRole('button', { name: 'a' })
      expect(screen.queryByText(HINT)).not.toBeInTheDocument()

      await user.selectOptions(sortSelect(), 'Bildanzahl, meiste zuerst')
      expect(screen.getByRole('status')).toHaveTextContent(HINT)
      expect(rowNames()).toEqual(['a', 'b', 'c'])

      await user.selectOptions(sortSelect(), 'Änderungsdatum, neueste zuerst')
      expect(screen.queryByText(HINT)).not.toBeInTheDocument()

      await user.selectOptions(sortSelect(), 'Name Z–A')
      expect(screen.queryByText(HINT)).not.toBeInTheDocument()
    })

    it('sortiert bei Bildanzahl genau einmal um - im selben Commit, in dem Hinweis und Ladeanzeige verschwinden', async () => {
      const levelA = [folder('A', 'k'), folder('A', 'l'), folder('A', 'm')]
      const countsA = [exactCount('A/k', 1), exactCount('A/l', 3), exactCount('A/m', 8)]
      const levelB = [folder('B', 'x'), folder('B', 'y'), folder('B', 'z')]
      const countsB = deferredCounts()
      mockLevels({ A: levelA, B: levelB }, { A: countsA, B: countsB.promise })
      const commits: { rows: string[]; hint: boolean; loading: boolean }[] = []
      let recording = false
      const record = () => {
        if (recording) {
          commits.push({
            rows: rowNames(),
            hint: screen.queryByText(HINT) !== null,
            loading: screen.queryAllByTestId('folder-count-loading').length > 0,
          })
        }
      }
      const browserAt = (value: string) => (
        <Profiler id="ordner-browser" onRender={record}>
          <FolderBrowser value={value} onChange={vi.fn()} />
        </Profiler>
      )
      const user = userEvent.setup()

      const { rerender } = renderWithClient(browserAt('A'))
      await screen.findByText('8')
      await user.selectOptions(sortSelect(), 'Bildanzahl, meiste zuerst')
      expect(rowNames()).toEqual(['m', 'l', 'k'])

      recording = true
      rerender(browserAt('B'))
      await waitFor(() => expect(rowNames()).toEqual(['x', 'y', 'z']))
      await act(async () =>
        countsB.resolve([exactCount('B/x', 1), exactCount('B/y', 5), exactCount('B/z', 9)]),
      )
      await waitFor(() => expect(rowNames()).toEqual(['z', 'y', 'x']))

      const withRows = commits.filter((commit) => commit.rows.length > 0)
      const isNameOrder = (rows: string[]) => rows.join() === 'x,y,z'
      expect(withRows.map(({ hint, loading }) => ({ hint, loading }))).toEqual(
        withRows.map(({ rows }) => ({ hint: isNameOrder(rows), loading: isNameOrder(rows) })),
      )
      const orders = withRows
        .map(({ rows }) => rows.join())
        .filter((order, index, all) => index === 0 || order !== all[index - 1])
      expect(orders).toEqual(['x,y,z', 'z,y,x'])

      commits.length = 0
      rerender(browserAt('A'))
      await waitFor(() => expect(rowNames()).toEqual(['m', 'l', 'k']))
      expect(commits.find((commit) => commit.rows.length > 0)).toEqual({
        rows: ['m', 'l', 'k'],
        hint: false,
        loading: false,
      })
    })

    it('lässt den Fokus beim Umsortieren auf demselben Ordner', async () => {
      const counts = deferredCounts()
      mockLevels({ Ebene: LEVEL }, { Ebene: counts.promise })
      const user = userEvent.setup()

      renderBrowser('Ebene')
      await user.selectOptions(sortSelect(), 'Bildanzahl, meiste zuerst')
      const row = await screen.findByRole('button', { name: 'b' })
      act(() => row.focus())
      await act(async () => counts.resolve(LEVEL_COUNTS))
      await waitFor(() => expect(rowNames()).toEqual(['a', 'c', 'b']))

      expect(document.activeElement).toHaveAccessibleName('b')
    })

    it('beendet die Vorläufigkeit auch, wenn die ganze Zählanfrage scheitert', async () => {
      const counts = deferredCounts()
      mockLevels({ Ebene: LEVEL }, { Ebene: counts.promise })
      const user = userEvent.setup()

      renderBrowser('Ebene')
      await user.selectOptions(sortSelect(), 'Bildanzahl, meiste zuerst')
      expect(await screen.findByText(HINT)).toBeInTheDocument()
      await act(async () => counts.reject(new Error('Netzwerkfehler')))

      await waitFor(() => expect(screen.queryByText(HINT)).not.toBeInTheDocument())
      expect(screen.getAllByText('?')).toHaveLength(3)
      expect(rowNames()).toEqual(['a', 'b', 'c'])
    })

    it('behält die gewählte Sortierung beim Ordnerwechsel und ordnet die neue Ebene danach', async () => {
      mockLevels(
        { '': [folder('', 'Ebene')], Ebene: LEVEL },
        { '': [exactCount('Ebene', 9)], Ebene: LEVEL_COUNTS },
      )
      const user = userEvent.setup()

      renderWithClient(<NavigatingBrowser initial="" />)
      await user.selectOptions(sortSelect(), 'Bildanzahl, meiste zuerst')
      await user.click(await screen.findByRole('button', { name: 'Ebene' }))

      await waitFor(() => expect(rowNames()).toEqual(['a', 'c', 'b']))
      expect(sortSelect()).toHaveDisplayValue('Bildanzahl, meiste zuerst')
    })

    it('filtert die Liste bei jeder Eingabe', async () => {
      mockLevels(
        { Reisen: [folder('Reisen', 'Panama'), folder('Reisen', 'Costa Rica')] },
        { Reisen: [] },
      )
      const user = userEvent.setup()

      renderBrowser('Reisen')
      await screen.findByRole('button', { name: 'Panama' })
      await user.type(searchField(), 'p')
      expect(rowNames()).toEqual(['Panama'])

      await user.type(searchField(), 'x')
      expect(rowNames()).toEqual([])
    })

    it('leert einen Begriff mit Esc, der Fokus bleibt im Feld', async () => {
      mockLevels({ Ebene: LEVEL }, { Ebene: LEVEL_COUNTS })
      const user = userEvent.setup()

      renderBrowser('Ebene')
      await screen.findByRole('button', { name: 'a' })
      await user.type(searchField(), 'c')
      expect(rowNames()).toEqual(['c'])
      await user.keyboard('{Escape}')

      expect(searchField()).toHaveValue('')
      expect(searchField()).toHaveFocus()
      expect(rowNames()).toEqual(['a', 'b', 'c'])
    })

    it('stellt beim Tippen keine weitere Anfrage', async () => {
      mockLevels({ Ebene: LEVEL }, { Ebene: LEVEL_COUNTS })
      const user = userEvent.setup()

      renderBrowser('Ebene')
      await screen.findByText('5')
      await user.type(searchField(), 'Ebene')

      expect(opencloudApi.browseFolder).toHaveBeenCalledTimes(1)
      expect(opencloudApi.fetchFolderCounts).toHaveBeenCalledTimes(1)
    })

    it('zeigt an einer gefilterten Zeile ihren Zähler und führt beim Anklicken in den Ordner', async () => {
      mockLevels({ Ebene: LEVEL }, { Ebene: LEVEL_COUNTS })
      const user = userEvent.setup()

      const { onChange } = renderBrowser('Ebene')
      await screen.findByText('5')
      await user.type(searchField(), 'c')

      const [row] = within(screen.getByRole('list')).getAllByRole('listitem')
      expect(within(row).getByText('3')).toBeInTheDocument()
      await user.click(within(row).getByRole('button', { name: 'c' }))
      expect(onChange).toHaveBeenCalledWith('Ebene/c')
    })

    it('nennt den getrimmten Begriff, wenn die Ebene Unterordner hat, aber keiner passt', async () => {
      mockLevels({ Ebene: LEVEL }, { Ebene: LEVEL_COUNTS })
      const user = userEvent.setup()

      renderBrowser('Ebene')
      await screen.findByRole('button', { name: 'a' })
      await user.type(searchField(), '  xyz ')

      expect(screen.getByText('Kein Unterordner enthält „xyz“ im Namen.')).toBeInTheDocument()
      expect(screen.queryByText('Dieser Ordner hat keine Unterordner.')).not.toBeInTheDocument()
    })

    it('meldet eine Ebene ohne Unterordner auch mit Begriff als leer, nicht als Kein-Treffer', async () => {
      mockLevels({ Ebene: [] }, { Ebene: [] })
      const user = userEvent.setup()

      renderBrowser('Ebene')
      await screen.findByText('Dieser Ordner hat keine Unterordner.')
      await user.type(searchField(), 'xyz')

      expect(screen.getByText('Dieser Ordner hat keine Unterordner.')).toBeInTheDocument()
      expect(screen.queryByText(/Kein Unterordner enthält/)).not.toBeInTheDocument()
    })

    it('zeigt einen Begriff mit Markup wörtlich als Text', async () => {
      mockLevels({ Ebene: LEVEL }, { Ebene: LEVEL_COUNTS })
      const user = userEvent.setup()

      const { container } = renderBrowser('Ebene')
      await screen.findByRole('button', { name: 'a' })
      await user.type(searchField(), '<img src=x onerror=alert(1)>')

      expect(
        screen.getByText('Kein Unterordner enthält „<img src=x onerror=alert(1)>“ im Namen.'),
      ).toBeInTheDocument()
      expect(container.querySelector('img')).toBeNull()
    })

    it('lässt den Begriff bei keinem Treffer stehen und setzt ihn per „Suche zurücksetzen“ zurück', async () => {
      mockLevels({ Ebene: LEVEL }, { Ebene: LEVEL_COUNTS })
      const user = userEvent.setup()

      renderBrowser('Ebene')
      await screen.findByRole('button', { name: 'a' })
      await user.type(searchField(), 'xyz')
      expect(searchField()).toHaveValue('xyz')
      expect(rowNames()).toEqual([])

      await user.click(screen.getByRole('button', { name: 'Suche zurücksetzen' }))

      expect(searchField()).toHaveValue('')
      expect(searchField()).toHaveFocus()
      expect(rowNames()).toEqual(['a', 'b', 'c'])
    })

    it('leert den Begriff bei jedem Ordnerwechsel, auch bei der Rückkehr auf eine durchsuchte Ebene', async () => {
      mockLevels(
        { '': [folder('', 'Ebene'), folder('', 'Anderes')], Ebene: LEVEL },
        { '': [], Ebene: LEVEL_COUNTS },
      )
      const user = userEvent.setup()

      renderWithClient(<NavigatingBrowser initial="" />)
      await screen.findByRole('button', { name: 'Anderes' })
      await user.type(searchField(), 'Ebe')
      await user.click(screen.getByRole('button', { name: 'Ebene' }))
      await waitFor(() => expect(rowNames()).toEqual(['a', 'b', 'c']))
      expect(searchField()).toHaveValue('')

      await user.click(screen.getByRole('button', { name: 'Wurzel' }))
      await waitFor(() => expect(rowNames()).toEqual(['Anderes', 'Ebene']))
      expect(searchField()).toHaveValue('')
    })

    it('ändert beim Tippen, Esc, Enter, Zurücksetzen und Sortierwechsel nie den Pfad', async () => {
      mockLevels({ Ebene: LEVEL }, { Ebene: LEVEL_COUNTS })
      const user = userEvent.setup()

      const { onChange } = renderBrowser('Ebene')
      await screen.findByText('5')
      await user.type(searchField(), 'c{Enter}')
      await user.keyboard('{Escape}')
      await user.type(searchField(), 'xyz')
      await user.click(screen.getByRole('button', { name: 'Suche zurücksetzen' }))
      await user.selectOptions(sortSelect(), 'Änderungsdatum, neueste zuerst')

      expect(onChange).not.toHaveBeenCalled()
    })
  })
})
