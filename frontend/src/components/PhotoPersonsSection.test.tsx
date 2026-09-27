import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import * as personsApi from '../api/persons'
import type { PersonOut, PhotoOut, PhotoPersonOut } from '../api/types'
import { PhotoPersonsSection } from './PhotoPersonsSection'

vi.mock('../api/persons')

const ANNA: PersonOut = { id: 7, name: 'Anna', reference_count: 2 }
const BEN: PersonOut = { id: 8, name: 'Ben', reference_count: 1 }

function photo(persons: PhotoPersonOut[] = [], id = 1): PhotoOut {
  return {
    id,
    relative_path: 'a.jpg',
    taken_at: '2026-07-20T10:00:00Z',
    taken_at_original: '2026-07-20T10:00:00Z',
    time_offset_minutes: 0,
    camera: null,
    ratings: [],
    suggestion: null,
    ranking: null,
    criterion_scores: [],
    fine_labels: [],
    cloud_vision_status: [],
    final_selection_decision: null,
    in_final_selection: false,
    contested: false,
    persons,
  }
}

function renderSection(current: PhotoOut = photo()) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const view = render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <PhotoPersonsSection projectId={3} photo={current} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return { ...view, queryClient }
}

function section(): HTMLElement {
  return screen.getByRole('region', { name: 'Personen' })
}

function rows(): HTMLElement[] {
  return within(section()).getAllByRole('listitem')
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

beforeEach(() => {
  vi.mocked(personsApi.listPersons).mockReset()
  vi.mocked(personsApi.setPhotoPerson).mockReset()
  vi.mocked(personsApi.listFaces).mockReset()
})

describe('PhotoPersonsSection: Zeilen', () => {
  it('zeigt je Person eine Zeile in der Reihenfolge von GET /persons, nie nach Zustand sortiert', async () => {
    vi.mocked(personsApi.listPersons).mockResolvedValue([BEN, ANNA])

    renderSection(photo([{ person_id: 7, origin: 'recognized' }]))

    await screen.findByText('Ben')
    expect(rows().map((row) => within(row).getByText(/^(Anna|Ben)$/).textContent)).toEqual([
      'Ben',
      'Anna',
    ])
  })

  it('nennt die drei Zustände je Zeile als ein Wort', async () => {
    vi.mocked(personsApi.listPersons).mockResolvedValue([
      ANNA,
      BEN,
      { id: 9, name: 'Cleo', reference_count: 1 },
    ])

    renderSection(
      photo([
        { person_id: 7, origin: 'recognized' },
        { person_id: 8, origin: 'corrected' },
      ]),
    )

    await screen.findByText('Cleo')
    const [anna, ben, cleo] = rows()
    expect(anna).toHaveAttribute('data-person-state', 'recognized')
    expect(within(anna).getByText('Erkannt')).toBeInTheDocument()
    expect(ben).toHaveAttribute('data-person-state', 'corrected')
    expect(within(ben).getByText('Von Hand zugeordnet')).toBeInTheDocument()
    expect(cleo).toHaveAttribute('data-person-state', 'unassigned')
    expect(within(cleo).getByText('Nicht zugeordnet')).toBeInTheDocument()
  })

  it('sendet "Ergänzen" als applies=true und "Entfernen" als applies=false', async () => {
    vi.mocked(personsApi.listPersons).mockResolvedValue([ANNA, BEN])
    vi.mocked(personsApi.setPhotoPerson).mockResolvedValue([])
    const user = userEvent.setup()

    renderSection(photo([{ person_id: 7, origin: 'recognized' }], 5))

    await user.click(await screen.findByRole('button', { name: 'Entfernen: Anna' }))
    await user.click(screen.getByRole('button', { name: 'Ergänzen: Ben' }))

    await waitFor(() => expect(personsApi.setPhotoPerson).toHaveBeenCalledTimes(2))
    expect(personsApi.setPhotoPerson).toHaveBeenNthCalledWith(1, 5, 7, false)
    expect(personsApi.setPhotoPerson).toHaveBeenNthCalledWith(2, 5, 8, true)
  })

  it('sperrt während der Anfrage nur die eigene Zeile', async () => {
    vi.mocked(personsApi.listPersons).mockResolvedValue([ANNA, BEN])
    const pending = deferred<PhotoPersonOut[]>()
    vi.mocked(personsApi.setPhotoPerson).mockReturnValue(pending.promise)
    const user = userEvent.setup()

    renderSection()

    await user.click(await screen.findByRole('button', { name: 'Ergänzen: Anna' }))

    expect(screen.getByRole('button', { name: 'Ergänzen: Anna' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Ergänzen: Ben' })).toBeEnabled()
    pending.resolve([{ person_id: 7, origin: 'corrected' }])
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Ergänzen: Anna' })).toBeEnabled(),
    )
  })

  it('zeigt einen Fehler mit dem wörtlichen detail, ohne "Erneut versuchen"', async () => {
    vi.mocked(personsApi.listPersons).mockResolvedValue([ANNA])
    vi.mocked(personsApi.setPhotoPerson).mockRejectedValue(
      new ApiError(422, 'Die Zuordnung ist ungültig.'),
    )
    const user = userEvent.setup()

    renderSection()

    await user.click(await screen.findByRole('button', { name: 'Ergänzen: Anna' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Die Zuordnung ist ungültig.')
    expect(within(alert).queryByRole('button', { name: 'Erneut versuchen' })).toBeNull()
    expect(personsApi.listPersons).toHaveBeenCalledTimes(1)
  })

  it('lädt bei 404 (Person inzwischen entfernt) die Personenliste neu', async () => {
    vi.mocked(personsApi.listPersons).mockResolvedValueOnce([ANNA]).mockResolvedValue([])
    vi.mocked(personsApi.setPhotoPerson).mockRejectedValue(
      new ApiError(404, 'Person nicht gefunden.'),
    )
    const user = userEvent.setup()

    renderSection()

    await user.click(await screen.findByRole('button', { name: 'Ergänzen: Anna' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Person nicht gefunden.')
    await waitFor(() => expect(personsApi.listPersons).toHaveBeenCalledTimes(2))
    expect(await screen.findByText('Noch keine Person festgelegt.')).toBeInTheDocument()
  })

  it('rendert einen Namen mit Markup als reinen Text', async () => {
    vi.mocked(personsApi.listPersons).mockResolvedValue([
      { id: 7, name: '<b>Anna</b>', reference_count: 1 },
    ])

    renderSection()

    expect(await screen.findByText('<b>Anna</b>')).toBeInTheDocument()
    expect(section().querySelector('b')).toBeNull()
  })
})

describe('PhotoPersonsSection: Zustände', () => {
  it('zeigt beim Laden zwei Platzhalterzeilen mit Statusansage', () => {
    vi.mocked(personsApi.listPersons).mockReturnValue(new Promise(() => {}))

    renderSection()

    expect(within(section()).getByRole('status')).toHaveTextContent('Personen werden geladen…')
  })

  it('zeigt bei einem Ladefehler einen Alert mit "Erneut versuchen" und keine Gesichterwahl', async () => {
    vi.mocked(personsApi.listPersons)
      .mockRejectedValueOnce(new ApiError(500, 'kaputt'))
      .mockResolvedValue([ANNA])
    const user = userEvent.setup()

    renderSection()

    const alert = await screen.findByRole('alert')
    expect(screen.queryByRole('button', { name: 'Gesicht zeigen' })).toBeNull()
    await user.click(within(alert).getByRole('button', { name: 'Erneut versuchen' }))
    expect(await screen.findByText('Anna')).toBeInTheDocument()
  })

  it('zeigt ohne festgelegte Person den Satz und darunter die Gesichterwahl', async () => {
    vi.mocked(personsApi.listPersons).mockResolvedValue([])

    renderSection()

    expect(await screen.findByText('Noch keine Person festgelegt.')).toBeInTheDocument()
    expect(within(section()).queryByRole('list')).toBeNull()
    expect(screen.getByRole('button', { name: 'Gesicht zeigen' })).toBeInTheDocument()
  })

  it('führt über "Personen verwalten" nach /persons', async () => {
    vi.mocked(personsApi.listPersons).mockResolvedValue([])

    renderSection()

    expect(screen.getByRole('link', { name: 'Personen verwalten' })).toHaveAttribute(
      'href',
      '/persons',
    )
  })
})
