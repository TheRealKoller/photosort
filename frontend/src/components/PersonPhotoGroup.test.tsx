import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createRef } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import * as personsApi from '../api/persons'
import * as photosApi from '../api/photos'
import type { PersonFace, PersonOrigin, PhotoListOut, PhotoOut } from '../api/types'
import { PERSONS_QUERY_KEY } from '../hooks/usePersons'
import { PersonPhotoGroup } from './PersonPhotoGroup'

vi.mock('../api/persons')
vi.mock('../api/photos')

const ANNA = { id: 7, name: 'Anna' } as const

function photo(id: number, origin: PersonOrigin = 'recognized', face: PersonFace = null): PhotoOut {
  return {
    id,
    relative_path: `reise/p${id}.jpg`,
    persons: [{ person_id: ANNA.id, origin, face }],
  } as unknown as PhotoOut
}

function listOf(items: PhotoOut[], total = items.length): PhotoListOut {
  return { items, total } as unknown as PhotoListOut
}

function renderGroup() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const props = {
    onOpenLarge: vi.fn(),
    onPhotosChange: vi.fn(),
    onNameRemoved: vi.fn(),
    onPersonGone: vi.fn(),
  }
  const headingRef = createRef<HTMLHeadingElement>()
  render(
    <QueryClientProvider client={queryClient}>
      <PersonPhotoGroup
        projectId={3}
        person={{ ...ANNA, reference_count: 1 } as never}
        headingId="gruppe-7"
        headingRef={headingRef}
        largeTriggerRef={() => () => {}}
        {...props}
      />
    </QueryClientProvider>,
  )
  return { ...props, queryClient }
}

function card(fileName: string): HTMLElement {
  const item = screen.getByText(fileName).closest('li')
  if (item === null) {
    throw new Error(`keine Karte ${fileName}`)
  }
  return item
}

/** Die eine Statuszeile der Gruppe - die Ladezustände der Vorschaubilder in den Karten zählen
 * nicht dazu. */
function groupStatus(): HTMLElement {
  const lines = screen.getAllByRole('status').filter((node) => node.closest('li') === null)
  expect(lines).toHaveLength(1)
  return lines[0]
}

beforeEach(() => {
  vi.mocked(photosApi.listPhotos).mockReset()
  vi.mocked(personsApi.setPhotoPerson).mockReset()
  vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockReturnValue(new Promise(() => {}))
})

describe('PersonPhotoGroup - Kopf und Karten', () => {
  it('nennt die Anzahl erst nach der ersten Seite, im Singular und Plural', async () => {
    let resolve: (value: PhotoListOut) => void = () => {}
    vi.mocked(photosApi.listPhotos).mockReturnValue(
      new Promise((done) => {
        resolve = done
      }),
    )
    renderGroup()

    expect(screen.getByRole('heading', { level: 2, name: 'Anna' })).toBeInTheDocument()
    expect(groupStatus()).toHaveTextContent('Fotos werden geladen…')
    expect(screen.queryByText(/^\d+ Fotos?$/)).not.toBeInTheDocument()

    resolve(listOf([photo(1)], 1))

    expect(await screen.findByText('1 Foto')).toBeInTheDocument()
  })

  it('zählt im Plural', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue(listOf([photo(1), photo(2)], 2))
    renderGroup()

    expect(await screen.findByText('2 Fotos')).toBeInTheDocument()
  })

  it('nennt Herkunft und gebundenes Gesicht je Karte als Wörter', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue(
      listOf([
        photo(1, 'recognized', null),
        photo(2, 'corrected', null),
        photo(3, 'corrected', 'shown'),
        photo(4, 'corrected', 'assigned'),
      ]),
    )
    renderGroup()
    await screen.findByText('p1.jpg')

    const texts = (fileName: string) =>
      within(card(fileName))
        .getAllByText(/./, { selector: 'p' })
        .map((node) => node.textContent)
    expect(texts('p1.jpg')).toEqual(['p1.jpg', 'Erkannt'])
    expect(texts('p2.jpg')).toEqual(['p2.jpg', 'Von Hand zugeordnet'])
    expect(texts('p3.jpg')).toEqual(['p3.jpg', 'Von Hand zugeordnet', 'Gesicht gezeigt'])
    expect(texts('p4.jpg')).toEqual([
      'p4.jpg',
      'Von Hand zugeordnet',
      'Gesicht gewählt, nicht gelernt',
    ])
  })

  it('heißt die Aktion bei einem gezeigten Gesicht "Gesicht zurücknehmen", sonst "Name entfernen"', async () => {
    const user = userEvent.setup()
    vi.mocked(photosApi.listPhotos).mockResolvedValue(
      listOf([photo(1, 'corrected', 'shown'), photo(2, 'corrected', 'assigned'), photo(3)]),
    )
    vi.mocked(personsApi.setPhotoPerson).mockReturnValue(new Promise(() => {}))
    renderGroup()

    const withdraw = await screen.findByRole('button', { name: 'Gesicht zurücknehmen: p1.jpg' })
    expect(withdraw).toHaveTextContent('Gesicht zurücknehmen')
    expect(screen.getByRole('button', { name: 'Name entfernen: p2.jpg' })).toHaveTextContent(
      'Name entfernen',
    )
    await user.click(withdraw)
    await user.click(screen.getByRole('button', { name: 'Name entfernen: p3.jpg' }))

    expect(personsApi.setPhotoPerson).toHaveBeenCalledWith(1, ANNA.id, false)
    expect(personsApi.setPhotoPerson).toHaveBeenCalledWith(3, ANNA.id, false)
  })

  it('sperrt während der Anfrage nur die Schaltfläche der eigenen Karte', async () => {
    const user = userEvent.setup()
    vi.mocked(photosApi.listPhotos).mockResolvedValue(
      listOf([photo(1, 'corrected', 'shown'), photo(2)]),
    )
    vi.mocked(personsApi.setPhotoPerson).mockReturnValue(new Promise(() => {}))
    renderGroup()

    await user.click(await screen.findByRole('button', { name: 'Gesicht zurücknehmen: p1.jpg' }))

    expect(
      within(card('p1.jpg')).getByRole('button', { name: /Wird zurückgenommen…/ }),
    ).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Name entfernen: p2.jpg' })).toBeEnabled()
  })
})

describe('PersonPhotoGroup - nach Erfolg', () => {
  it('nimmt die Karte heraus, senkt die Anzahl und meldet das Entfernen', async () => {
    const user = userEvent.setup()
    vi.mocked(photosApi.listPhotos).mockResolvedValue(listOf([photo(1), photo(2)]))
    vi.mocked(personsApi.setPhotoPerson).mockResolvedValue([])
    const { onNameRemoved } = renderGroup()

    await user.click(await screen.findByRole('button', { name: 'Name entfernen: p1.jpg' }))

    await waitFor(() => expect(screen.queryByText('p1.jpg')).not.toBeInTheDocument())
    expect(screen.getByText('1 Foto')).toBeInTheDocument()
    expect(groupStatus()).toHaveTextContent('Anna auf p1.jpg entfernt.')
    expect(onNameRemoved).toHaveBeenCalledWith(1, 'p1.jpg')
  })

  it('meldet die Rücknahme eines gezeigten Gesichts mit ihrem Wortlaut', async () => {
    const user = userEvent.setup()
    vi.mocked(photosApi.listPhotos).mockResolvedValue(listOf([photo(1, 'corrected', 'shown')]))
    vi.mocked(personsApi.setPhotoPerson).mockResolvedValue([])
    renderGroup()

    await user.click(await screen.findByRole('button', { name: 'Gesicht zurücknehmen: p1.jpg' }))

    await waitFor(() =>
      expect(groupStatus()).toHaveTextContent(
        'Gesicht auf p1.jpg zurückgenommen. Es steht wieder unter „Ohne Namen“ und wirkt ab dem nächsten Klassifizierungslauf nicht mehr auf die Erkennung.',
      ),
    )
  })

  it('setzt den Fokus auf die nachrückende Karte an derselben Stelle', async () => {
    const user = userEvent.setup()
    vi.mocked(photosApi.listPhotos).mockResolvedValue(listOf([photo(1), photo(2), photo(3)]))
    vi.mocked(personsApi.setPhotoPerson).mockResolvedValue([])
    renderGroup()

    await user.click(await screen.findByRole('button', { name: 'Name entfernen: p2.jpg' }))

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Name entfernen: p3.jpg' })).toHaveFocus(),
    )
  })

  it('setzt den Fokus auf die vorige Karte, wenn keine nachrückt', async () => {
    const user = userEvent.setup()
    vi.mocked(photosApi.listPhotos).mockResolvedValue(listOf([photo(1), photo(2)]))
    vi.mocked(personsApi.setPhotoPerson).mockResolvedValue([])
    renderGroup()

    await user.click(await screen.findByRole('button', { name: 'Name entfernen: p2.jpg' }))

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Name entfernen: p1.jpg' })).toHaveFocus(),
    )
  })

  it('setzt den Fokus auf die Überschrift und zeigt den Leersatz, wenn die letzte Karte geht', async () => {
    const user = userEvent.setup()
    vi.mocked(photosApi.listPhotos).mockResolvedValue(listOf([photo(1)]))
    vi.mocked(personsApi.setPhotoPerson).mockResolvedValue([])
    renderGroup()

    await user.click(await screen.findByRole('button', { name: 'Name entfernen: p1.jpg' }))

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Anna' })).toHaveFocus())
    expect(screen.getByText('Kein Foto in diesem Projekt trägt diesen Namen.')).toBeInTheDocument()
    expect(screen.getByText('0 Fotos')).toBeInTheDocument()
  })
})

describe('PersonPhotoGroup - Fehler und Nachladen', () => {
  it('zeigt das detail einer Ablehnung an der Karte', async () => {
    const user = userEvent.setup()
    vi.mocked(photosApi.listPhotos).mockResolvedValue(listOf([photo(1), photo(2)]))
    vi.mocked(personsApi.setPhotoPerson).mockRejectedValue(
      new ApiError(409, 'Gleichzeitig geändert.'),
    )
    const { onPersonGone } = renderGroup()

    await user.click(await screen.findByRole('button', { name: 'Name entfernen: p1.jpg' }))

    expect(await within(card('p1.jpg')).findByRole('alert')).toHaveTextContent(
      'Gleichzeitig geändert.',
    )
    expect(within(card('p2.jpg')).queryByRole('alert')).not.toBeInTheDocument()
    expect(onPersonGone).not.toHaveBeenCalled()
  })

  it('lädt bei 404 die Personenliste neu und meldet die entfernte Person', async () => {
    const user = userEvent.setup()
    vi.mocked(photosApi.listPhotos).mockResolvedValue(listOf([photo(1)]))
    vi.mocked(personsApi.setPhotoPerson).mockRejectedValue(
      new ApiError(404, 'Person nicht gefunden.'),
    )
    const { onPersonGone, queryClient } = renderGroup()
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries')

    await user.click(await screen.findByRole('button', { name: 'Name entfernen: p1.jpg' }))

    await waitFor(() => expect(onPersonGone).toHaveBeenCalledTimes(1))
    expect(invalidate).toHaveBeenCalledWith({ queryKey: PERSONS_QUERY_KEY })
    expect(groupStatus()).toHaveTextContent('')
  })

  it('lädt mit "Mehr laden" weiter und nennt den geladenen Anteil', async () => {
    const user = userEvent.setup()
    const first = Array.from({ length: 24 }, (_, index) => photo(index + 1))
    vi.mocked(photosApi.listPhotos)
      .mockResolvedValueOnce(listOf(first, 25))
      .mockResolvedValueOnce(listOf([photo(25)], 25))
    renderGroup()

    expect(await screen.findByText('24 von 25 Fotos geladen')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Mehr laden' }))

    expect(await screen.findByText('p25.jpg')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Mehr laden' })).not.toBeInTheDocument()
    expect(vi.mocked(photosApi.listPhotos).mock.calls[1][1]).toMatchObject({ offset: 24 })
  })

  it('bietet beim Ladefehler der Gruppe "Erneut versuchen" an', async () => {
    const user = userEvent.setup()
    vi.mocked(photosApi.listPhotos)
      .mockRejectedValueOnce(new Error('netz'))
      .mockResolvedValueOnce(listOf([photo(1)]))
    renderGroup()

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Die Fotos konnten nicht geladen werden.',
    )
    await user.click(screen.getByRole('button', { name: 'Erneut versuchen' }))

    expect(await screen.findByText('p1.jpg')).toBeInTheDocument()
  })
})
