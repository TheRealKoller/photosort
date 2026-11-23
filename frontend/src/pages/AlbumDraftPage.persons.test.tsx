/*
 * Entwurfsseite - Teil: Personenfilter und Zustaende - gemeinsamer Unterbau: src/test/albumDraftPage.tsx.
 */
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ApiError } from '../api/client'
import * as personsApi from '../api/persons'
import * as photosApi from '../api/photos'
import * as projectsApi from '../api/projects'
import * as ratingsApi from '../api/ratings'
import type { PersonOut } from '../api/types'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  projectOut,
  EVENT_A,
  EVENT_B,
  ranking,
  photo,
  own,
  written,
  renderPage,
  noObserver,
  NO_POSITION,
  resetAlbumDraftMocks,
} from '../test/albumDraftPage'
import type { DraftInput } from '../test/albumDraftPage'
import { MOTIF_SET } from '../test/motifSetFixture'

vi.mock('../api/photos')
vi.mock('../api/projects')
vi.mock('../api/ratings')
vi.mock('../api/motifs')
vi.mock('../api/persons')

beforeEach(() => {
  resetAlbumDraftMocks()
})

describe('AlbumDraftPage: Personenfilter', () => {
  const anna: PersonOut = { id: 1, name: 'Anna', reference_count: 2 }
  const ben: PersonOut = { id: 2, name: 'Ben', reference_count: 2 }
  const withAnna = photo(1, { persons: [{ person_id: 1, origin: 'recognized', face: null }] })
  const nobody = photo(2)
  const struckNobody = photo(4, { ratings: own('rejected') })
  const withBen = photo(3, {
    event: EVENT_B,
    taken_at: '2026-07-21T10:03:00',
    persons: [{ person_id: 2, origin: 'corrected', face: null }],
  })
  const draft: DraftInput = {
    events: [EVENT_A, EVENT_B],
    items: [withAnna, nobody, struckNobody, withBen],
  }

  beforeEach(() => {
    vi.mocked(personsApi.listPersons).mockResolvedValue([anna, ben])
  })

  it('counts the whole draft in the head and keeps every section standing', async () => {
    renderPage(draft, noObserver, '/projects/1/album?person=1')

    expect(await screen.findByText('1 von 3 Fotos des Entwurfs sichtbar.')).toHaveAttribute(
      'role',
      'status',
    )
    expect(
      screen.getByText('3 im Album · Richtwert etwa 3 · 0 aufgenommen · 1 gestrichen'),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Streichen: 1.jpg' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Streichen: 2.jpg' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Streichen: 3.jpg' })).toBeNull()
    // Beide Eventabschnitte bleiben stehen - auch der, in dem der Filter alles verbirgt.
    expect(screen.getAllByRole('heading', { level: 3 })).toHaveLength(2)
    expect(screen.getByRole('button', { name: /^Foto hinzufügen: .*Lyon/ })).toBeInTheDocument()
  })

  it('filters neither the struck row nor the add panel nor the band', async () => {
    const user = userEvent.setup()
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue({
      items: [photo(5, { ranking: ranking(false) })],
      total: 1,
      ...NO_POSITION,
    })
    renderPage(draft, noObserver, '/projects/1/album?person=1')

    await user.click(await screen.findByRole('button', { name: '1 gestrichen – anzeigen' }))
    expect(screen.getByRole('button', { name: 'Wieder aufnehmen: 4.jpg' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Alternativen: 1.jpg' }))
    expect(await screen.findByRole('button', { name: 'Tauschen: 5.jpg' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /^Foto hinzufügen: .*Paris/ }))
    expect(await screen.findByRole('button', { name: 'Hinzufügen: 5.jpg' })).toBeInTheDocument()
  })

  it('focuses the heading and says so when the exchanged photo is hidden by the filter', async () => {
    const user = userEvent.setup()
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue({
      items: [photo(5, { ranking: ranking(false) })],
      total: 1,
      ...NO_POSITION,
    })
    renderPage(draft, noObserver, '/projects/1/album?person=1')
    vi.mocked(photosApi.exchangeDraftPhoto).mockResolvedValueOnce({
      taken: written(5, 'album_worthy'),
      struck: written(1, 'rejected'),
    })

    await user.click(await screen.findByRole('button', { name: 'Alternativen: 1.jpg' }))
    await user.click(await screen.findByRole('button', { name: 'Tauschen: 5.jpg' }))

    await waitFor(() => expect(screen.getByRole('heading', { level: 1 })).toHaveFocus())
    expect(
      screen.getByText('Das eingetauschte Foto ist durch den Filter ausgeblendet.'),
    ).toHaveAttribute('role', 'status')
    expect(screen.queryByRole('button', { name: 'Streichen: 5.jpg' })).toBeNull()
  })

  it('neither writes nor reloads the draft when the filter changes', async () => {
    const user = userEvent.setup()
    renderPage(draft, noObserver)
    await screen.findByRole('button', { name: 'Streichen: 1.jpg' })

    await user.click(await screen.findByRole('button', { name: 'Anna' }))
    await user.click(screen.getByRole('button', { name: 'Beide: Anna und Ben' }))
    await user.click(screen.getByRole('button', { name: 'Alle' }))

    expect(photosApi.getAlbumDraft).toHaveBeenCalledTimes(1)
    expect(ratingsApi.setRating).not.toHaveBeenCalled()
    expect(ratingsApi.deleteRating).not.toHaveBeenCalled()
    expect(personsApi.setPhotoPerson).not.toHaveBeenCalled()
  })
})

describe('AlbumDraftPage: Zustände und Fremdtext', () => {
  it('shows a skeleton grid while loading', () => {
    vi.mocked(photosApi.getAlbumDraft).mockReturnValue(new Promise(() => {}))
    renderPage(null, noObserver)

    expect(screen.getByRole('status', { name: 'Fotos werden geladen…' })).toBeInTheDocument()
  })

  it('shows a failed project request with a retry instead of an empty page', async () => {
    const user = userEvent.setup()
    vi.mocked(projectsApi.getProject).mockRejectedValue(new ApiError(500, 'Projekt weg.'))
    renderPage({ events: [EVENT_A], items: [photo(1)] }, noObserver)

    expect(await screen.findByText('Projekt weg.')).toBeInTheDocument()
    vi.mocked(projectsApi.getProject).mockResolvedValue(projectOut())
    await user.click(screen.getByRole('button', { name: 'Erneut versuchen' }))

    expect(await screen.findByRole('button', { name: 'Streichen: 1.jpg' })).toBeInTheDocument()
    expect(screen.queryByText('Projekt weg.')).toBeNull()
  })

  it('shows an error alert whose retry triggers exactly one new request', async () => {
    const user = userEvent.setup()
    vi.mocked(photosApi.getAlbumDraft).mockRejectedValue(new ApiError(500, 'Serverfehler'))
    renderPage(null, noObserver)

    expect(await screen.findByText('Serverfehler')).toBeInTheDocument()
    const before = vi.mocked(photosApi.getAlbumDraft).mock.calls.length
    await user.click(screen.getByRole('button', { name: 'Erneut versuchen' }))

    await waitFor(() =>
      expect(vi.mocked(photosApi.getAlbumDraft).mock.calls.length).toBe(before + 1),
    )
  })

  it('strikes one photo while the decision on another is still running', async () => {
    // Die Sperre gilt je Foto: ein zweiter Druck auf ein ANDERES Foto verpufft nicht.
    const user = userEvent.setup()
    renderPage({ events: [EVENT_A], items: [photo(1), photo(2)] }, noObserver)
    vi.mocked(ratingsApi.setRating).mockImplementation((photoId) =>
      photoId === 1 ? new Promise(() => {}) : Promise.resolve(written(photoId, 'rejected')),
    )

    await user.click(await screen.findByRole('button', { name: 'Streichen: 1.jpg' }))
    await user.click(screen.getByRole('button', { name: 'Streichen: 2.jpg' }))

    await waitFor(() => expect(ratingsApi.setRating).toHaveBeenCalledWith(2, 'rejected'))
  })

  it('drops a motif from the event line as soon as its last carrier is struck', async () => {
    const user = userEvent.setup()
    const assessed = {
      source: 'cloud' as const,
      provider: 'anthropic',
      excluded_document: false,
      computed_at: '2026-07-21T09:00:00',
    }
    const motifsWith = (present: string[]) =>
      MOTIF_SET.items.map((item) => ({
        key: item.key,
        strength: 0.5,
        correction: null,
        present: present.includes(item.key),
      }))
    renderPage(
      {
        events: [EVENT_A],
        items: [
          photo(1, { motif_assessment: assessed, motifs: motifsWith(['menschen']) }),
          photo(2, { motif_assessment: assessed, motifs: motifsWith(['tiere']) }),
        ],
      },
      noObserver,
    )
    vi.mocked(ratingsApi.setRating).mockResolvedValueOnce(written(2, 'rejected'))
    await screen.findByText('Menschen, Tiere')

    await user.click(screen.getByRole('button', { name: 'Streichen: 2.jpg' }))

    expect(await screen.findByText('Menschen')).toBeInTheDocument()
    expect(screen.queryByText('Menschen, Tiere')).toBeNull()
  })

  /*
   * Spec 0434 S8 / Spec 0514 S1: `place_name` und `landmark_name` sind freier Fremdtext und
   * erscheinen ausschließlich als React-Textknoten. Der Nachweis gehört an die Rendering-Stelle.
   */
  const hostile = '<img src=x onerror="window.__pwned = true">'

  it('renders a hostile landmark and place name as ONE text node, never as markup', async () => {
    renderPage(
      {
        events: [
          {
            ...EVENT_A,
            place: { kind: 'landmark', landmark_name: hostile, lat: null, lon: null },
            place_name: hostile,
          },
        ],
        items: [photo(1)],
      },
      noObserver,
    )

    const heading = await screen.findByRole('heading', { level: 3 })
    expect(heading.textContent).toBe(`${hostile}, ${hostile} (10:00–11:00 Uhr)`)
    expect(heading.childNodes).toHaveLength(1)
    expect(heading.childNodes[0]?.nodeType).toBe(Node.TEXT_NODE)
    expect(document.querySelector('img[src="x"]')).toBeNull()
    expect((window as unknown as Record<string, unknown>).__pwned).toBeUndefined()
  })

  it('renders a hostile person name in the filter group as plain text', async () => {
    vi.mocked(personsApi.listPersons).mockResolvedValue([
      { id: 1, name: hostile, reference_count: 2 },
      { id: 2, name: 'Ben', reference_count: 2 },
    ])
    renderPage({ events: [EVENT_A], items: [photo(1)] }, noObserver)

    const group = await screen.findByRole('group', { name: 'Personen' })
    expect(within(group).getByRole('button', { name: hostile })).toBeInTheDocument()
    expect(document.querySelector('img[src="x"]')).toBeNull()
  })
})
