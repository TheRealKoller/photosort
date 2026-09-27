import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { UserEvent } from '@testing-library/user-event'
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

describe('PhotoPersonsSection: Gesichterwahl', () => {
  const FACES = [
    { index: 0, box: { x: 0.1, y: 0.1, width: 0.2, height: 0.2 } },
    { index: 3, box: { x: 0.5, y: 0.1, width: 0.2, height: 0.2 } },
  ]
  let created = 0

  beforeEach(() => {
    created = 0
    vi.mocked(personsApi.createPerson).mockReset()
    vi.mocked(personsApi.addReference).mockReset()
    vi.mocked(personsApi.fetchFaceImage).mockReset()
    vi.mocked(personsApi.fetchFaceImage).mockResolvedValue(new Blob(['x']))
    vi.mocked(personsApi.listFaces).mockResolvedValue(FACES)
    Object.assign(URL, {
      createObjectURL: vi.fn(() => `blob:face-${++created}`),
      revokeObjectURL: vi.fn(),
    })
  })

  function trigger(): HTMLElement {
    return screen.getByRole('button', { name: 'Gesicht zeigen' })
  }

  async function openAndPick(user: UserEvent, tile = 'Gesicht 2 von 2') {
    await user.click(await screen.findByRole('button', { name: 'Gesicht zeigen' }))
    await user.click(await screen.findByRole('button', { name: tile }))
  }

  it('ist anfangs zugeklappt und fragt die Gesichter erst beim Aufklappen ab', async () => {
    vi.mocked(personsApi.listPersons).mockResolvedValue([ANNA])
    const user = userEvent.setup()

    renderSection(photo([], 5))

    await screen.findByText('Anna')
    expect(trigger()).toHaveAttribute('aria-expanded', 'false')
    expect(personsApi.listFaces).not.toHaveBeenCalled()
    await user.click(trigger())
    expect(trigger()).toHaveAttribute('aria-expanded', 'true')
    expect(await screen.findByRole('button', { name: 'Gesicht 1 von 2' })).toBeInTheDocument()
    expect(personsApi.listFaces).toHaveBeenCalledExactlyOnceWith(5)
    expect(personsApi.fetchFaceImage).toHaveBeenCalledWith(5, 3)
    await waitFor(() =>
      expect(
        within(screen.getByRole('button', { name: 'Gesicht 2 von 2' })).getByRole('presentation'),
      ).toHaveAttribute('src', expect.stringMatching(/^blob:face-/)),
    )
  })

  it('schaltet aria-pressed um: wählen, wechseln, erneut drücken hebt auf', async () => {
    vi.mocked(personsApi.listPersons).mockResolvedValue([ANNA])
    const user = userEvent.setup()

    renderSection()
    await openAndPick(user, 'Gesicht 1 von 2')

    const first = screen.getByRole('button', { name: 'Gesicht 1 von 2' })
    const second = screen.getByRole('button', { name: 'Gesicht 2 von 2' })
    expect(first).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('group', { name: 'Wer ist das?' })).toBeInTheDocument()
    await user.click(second)
    expect(first).toHaveAttribute('aria-pressed', 'false')
    expect(second).toHaveAttribute('aria-pressed', 'true')
    await user.click(second)
    expect(second).toHaveAttribute('aria-pressed', 'false')
    expect(screen.queryByRole('group', { name: 'Wer ist das?' })).toBeNull()
  })

  it('gibt beim Zuklappen jede Blob-URL frei', async () => {
    vi.mocked(personsApi.listPersons).mockResolvedValue([ANNA])
    const user = userEvent.setup()

    renderSection()
    await user.click(await screen.findByRole('button', { name: 'Gesicht zeigen' }))
    await waitFor(() => expect(URL.createObjectURL).toHaveBeenCalledTimes(2))
    await user.click(trigger())

    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:face-1')
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:face-2')
    expect(screen.queryByRole('button', { name: 'Gesicht 1 von 2' })).toBeNull()
  })

  it('bietet das Namensformular nur bei weniger als zwei Personen an', async () => {
    vi.mocked(personsApi.listPersons).mockResolvedValue([ANNA, BEN])
    const user = userEvent.setup()

    renderSection()
    await openAndPick(user)

    const group = screen.getByRole('group', { name: 'Wer ist das?' })
    expect(within(group).getByRole('button', { name: 'Anna' })).toBeInTheDocument()
    expect(within(group).getByRole('button', { name: 'Ben' })).toBeInTheDocument()
    expect(within(group).queryByLabelText('Name der neuen Person')).toBeNull()
  })

  it('sperrt "Festlegen" bei getrimmt leerem Namen und sendet mit Enter ab', async () => {
    vi.mocked(personsApi.listPersons).mockResolvedValueOnce([]).mockResolvedValue([ANNA])
    vi.mocked(personsApi.createPerson).mockResolvedValue(ANNA)
    const user = userEvent.setup()

    renderSection(photo([], 5))
    await openAndPick(user)

    const field = screen.getByLabelText('Name der neuen Person')
    expect(field).toHaveAttribute('autocomplete', 'off')
    await user.type(field, '   ')
    expect(screen.getByRole('button', { name: 'Festlegen' })).toBeDisabled()
    await user.type(field, ' Anna ')
    expect(screen.getByRole('button', { name: 'Festlegen' })).toBeEnabled()
    await user.keyboard('{Enter}')

    await waitFor(() => expect(personsApi.createPerson).toHaveBeenCalledWith('Anna', 5, 3))
    expect(await screen.findByText('Anna ist festgelegt.')).toBeInTheDocument()
    expect(trigger()).toHaveAttribute('aria-expanded', 'false')
    expect(trigger()).toHaveFocus()
    await waitFor(() => expect(personsApi.listPersons).toHaveBeenCalledTimes(2))
  })

  it('sperrt während des Zeigens alle Kacheln und Wahl-Schaltflächen', async () => {
    vi.mocked(personsApi.listPersons).mockResolvedValue([ANNA])
    const pending = deferred<PersonOut>()
    vi.mocked(personsApi.addReference).mockReturnValue(pending.promise)
    const user = userEvent.setup()

    renderSection(photo([], 5))
    await openAndPick(user)
    await user.click(
      within(screen.getByRole('group', { name: 'Wer ist das?' })).getByRole('button', {
        name: 'Anna',
      }),
    )

    expect(personsApi.addReference).toHaveBeenCalledWith(7, 5, 3)
    expect(screen.getByRole('button', { name: 'Wird gespeichert…' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Gesicht 1 von 2' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Gesicht 2 von 2' })).toBeDisabled()
    pending.resolve(ANNA)
    expect(await screen.findByText('Gesicht als Anna gezeigt.')).toBeInTheDocument()
    expect(trigger()).toHaveFocus()
  })

  it('klappt mit "Abbrechen" zu und gibt den Fokus an "Gesicht zeigen" zurück', async () => {
    vi.mocked(personsApi.listPersons).mockResolvedValue([ANNA])
    const user = userEvent.setup()

    renderSection()
    await openAndPick(user)
    await user.click(screen.getByRole('button', { name: 'Abbrechen' }))

    expect(trigger()).toHaveAttribute('aria-expanded', 'false')
    expect(trigger()).toHaveFocus()
  })

  describe('409/422 beim Festlegen oder Zeigen', () => {
    async function refuse(status: number, detail: string, persons: PersonOut[] = []) {
      vi.mocked(personsApi.listPersons).mockResolvedValue(persons)
      vi.mocked(personsApi.createPerson).mockRejectedValue(new ApiError(status, detail))
      vi.mocked(personsApi.addReference).mockRejectedValue(new ApiError(status, detail))
      const user = userEvent.setup()
      renderSection()
      await openAndPick(user)
      return user
    }

    it('markiert bei einem ungültigen Namen (422) das Feld und verknüpft die Meldung', async () => {
      const user = await refuse(422, 'Der Name ist zu lang.')

      await user.type(screen.getByLabelText('Name der neuen Person'), 'Anna')
      await user.click(screen.getByRole('button', { name: 'Festlegen' }))

      const field = screen.getByLabelText('Name der neuen Person')
      await waitFor(() => expect(field).toHaveAttribute('aria-invalid', 'true'))
      expect(field).toHaveAccessibleDescription(expect.stringContaining('Der Name ist zu lang.'))
      expect(screen.getByRole('button', { name: 'Gesicht 2 von 2' })).toHaveAttribute(
        'aria-pressed',
        'true',
      )
      expect(
        within(screen.getByRole('alert')).queryByRole('button', { name: 'Erneut versuchen' }),
      ).toBeNull()
    })

    it('markiert bei einem doppelten Namen (409) das Feld', async () => {
      const user = await refuse(409, personsApi.PERSON_REFUSALS.duplicateName, [ANNA])

      await user.type(screen.getByLabelText('Name der neuen Person'), 'Anna')
      await user.click(screen.getByRole('button', { name: 'Festlegen' }))

      await waitFor(() =>
        expect(screen.getByLabelText('Name der neuen Person')).toHaveAttribute(
          'aria-invalid',
          'true',
        ),
      )
    })

    it('lädt bei "schon zwei Personen" die Liste neu, und das Formular verschwindet', async () => {
      const user = await refuse(409, personsApi.PERSON_REFUSALS.limitReached, [ANNA])
      vi.mocked(personsApi.listPersons).mockResolvedValue([ANNA, BEN])

      await user.type(screen.getByLabelText('Name der neuen Person'), 'Cleo')
      await user.click(screen.getByRole('button', { name: 'Festlegen' }))

      expect(await screen.findByRole('alert')).toHaveTextContent(
        personsApi.PERSON_REFUSALS.limitReached,
      )
      await waitFor(() => expect(screen.queryByLabelText('Name der neuen Person')).toBeNull())
      expect(screen.getByRole('button', { name: 'Gesicht 2 von 2' })).toHaveAttribute(
        'aria-pressed',
        'true',
      )
    })

    it('lädt bei "kein Gesicht an diesem Index" die Gesichter neu und hebt die Wahl auf', async () => {
      const user = await refuse(409, personsApi.PERSON_REFUSALS.faceNotFound, [ANNA])

      await user.click(
        within(screen.getByRole('group', { name: 'Wer ist das?' })).getByRole('button', {
          name: 'Anna',
        }),
      )

      expect(await screen.findByRole('alert')).toHaveTextContent(
        personsApi.PERSON_REFUSALS.faceNotFound,
      )
      await waitFor(() => expect(personsApi.listFaces).toHaveBeenCalledTimes(2))
      expect(screen.queryByRole('group', { name: 'Wer ist das?' })).toBeNull()
      expect(await screen.findByRole('button', { name: 'Gesicht 2 von 2' })).toHaveAttribute(
        'aria-pressed',
        'false',
      )
    })

    it('zeigt bei "gleicht der anderen Person" nur die Meldung', async () => {
      const user = await refuse(409, 'Dieses Gesicht gleicht der anderen Person.', [ANNA])

      await user.type(screen.getByLabelText('Name der neuen Person'), 'Cleo')
      await user.click(screen.getByRole('button', { name: 'Festlegen' }))

      expect(await screen.findByRole('alert')).toHaveTextContent(
        'Dieses Gesicht gleicht der anderen Person.',
      )
      expect(screen.getByLabelText('Name der neuen Person')).not.toHaveAttribute(
        'aria-invalid',
        'true',
      )
      expect(screen.getByRole('button', { name: 'Gesicht 2 von 2' })).toHaveAttribute(
        'aria-pressed',
        'true',
      )
      expect(personsApi.listPersons).toHaveBeenCalledTimes(1)
      expect(personsApi.listFaces).toHaveBeenCalledTimes(1)
    })
  })

  describe('Zustände', () => {
    beforeEach(() => {
      vi.mocked(personsApi.listPersons).mockResolvedValue([ANNA])
    })

    it('meldet beim Suchen drei Platzhalterkacheln', async () => {
      vi.mocked(personsApi.listFaces).mockReturnValue(new Promise(() => {}))
      const user = userEvent.setup()

      renderSection()
      await user.click(await screen.findByRole('button', { name: 'Gesicht zeigen' }))

      expect(screen.getByText('Gesichter werden gesucht…')).toHaveAttribute('role', 'status')
    })

    it('nennt eine leere Liste ruhig, ohne Alert', async () => {
      vi.mocked(personsApi.listFaces).mockResolvedValue([])
      const user = userEvent.setup()

      renderSection()
      await user.click(await screen.findByRole('button', { name: 'Gesicht zeigen' }))

      expect(
        await screen.findByText(
          'Auf diesem Foto ist kein Gesicht zu finden, das sich zeigen lässt.',
        ),
      ).toBeInTheDocument()
      expect(screen.queryByRole('alert')).toBeNull()
      expect(screen.getByRole('button', { name: 'Ergänzen: Anna' })).toBeEnabled()
    })

    it('nennt eine fehlende Vorschau (404 "Bild wird noch verarbeitet.") ruhig, ohne Alert', async () => {
      vi.mocked(personsApi.listFaces).mockRejectedValue(
        new ApiError(404, 'Bild wird noch verarbeitet.'),
      )
      const user = userEvent.setup()

      renderSection()
      await user.click(await screen.findByRole('button', { name: 'Gesicht zeigen' }))

      expect(
        await screen.findByText(
          'Für dieses Foto gibt es noch keine Vorschau – Gesichter lassen sich erst danach zeigen.',
        ),
      ).toBeInTheDocument()
      expect(screen.queryByRole('alert')).toBeNull()
    })

    it('zeigt bei sonstigen Fehlern einen Alert mit "Erneut versuchen"', async () => {
      vi.mocked(personsApi.listFaces)
        .mockRejectedValueOnce(new ApiError(500, 'kaputt'))
        .mockResolvedValue(FACES)
      const user = userEvent.setup()

      renderSection()
      await user.click(await screen.findByRole('button', { name: 'Gesicht zeigen' }))
      await user.click(
        within(await screen.findByRole('alert')).getByRole('button', { name: 'Erneut versuchen' }),
      )

      expect(await screen.findByRole('button', { name: 'Gesicht 1 von 2' })).toBeInTheDocument()
    })

    it('lässt eine Kachel stehen, deren Ausschnitt nicht lädt', async () => {
      vi.mocked(personsApi.fetchFaceImage).mockImplementation((_photoId, index) =>
        index === 3 ? Promise.reject(new ApiError(404, 'weg')) : Promise.resolve(new Blob(['x'])),
      )
      const user = userEvent.setup()

      renderSection()
      await user.click(await screen.findByRole('button', { name: 'Gesicht zeigen' }))

      const broken = await screen.findByRole('button', {
        name: 'Gesicht 2 von 2 – Ausschnitt nicht verfügbar',
      })
      expect(broken).toHaveAttribute('aria-disabled', 'true')
      await user.click(broken)
      expect(broken).toHaveAttribute('aria-pressed', 'false')
    })
  })
})
