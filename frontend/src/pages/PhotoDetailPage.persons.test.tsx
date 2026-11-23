/*
 * Foto-Detailseite - Teil: Personen: Folge, Abschnitt und Gesichterwahl (Spec 0651; gemeinsamer Unterbau in src/test/photoDetailPage.tsx).
 */
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ApiError } from '../api/client'
import * as personsApi from '../api/persons'
import * as photosApi from '../api/photos'
import * as ratingsApi from '../api/ratings'
import type { PhotoListOut } from '../api/types'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  photo,
  suggestion,
  renderPage,
  resetPhotoDetailMocks,
  resetPersonsMock,
} from '../test/photoDetailPage'

vi.mock('../api/motifs')
vi.mock('../api/persons')
vi.mock('../api/photos')
vi.mock('../api/ratings')

// Der Personenabschnitt und der Personenfilter laden `GET /persons` in JEDEM Block
// dieser Datei. Die Vorgabe "keine Person festgelegt" gilt dateiweit; ein Block, der Personen
// braucht, setzt sie selbst.
beforeEach(() => {
  resetPersonsMock()
})

describe('PhotoDetailPage', () => {
  beforeEach(() => {
    resetPhotoDetailMocks()
  })

  afterEach(() => {
    window.localStorage.clear()
  })

  /* Die Detailansicht blättert in der nach `person` gefilterten Folge, ihr Zähler
     bezieht sich auf diese Folge, und jeder Weg zurück trägt `person` weiter. Eine Korrektur lässt
     das aktuelle Foto stehen; die Gesichterwahl gehört zum Foto, nicht zur Folge. */
  describe('Personen: Folge, Abschnitt und Gesichterwahl', () => {
    beforeEach(() => {
      vi.mocked(personsApi.listPersons).mockResolvedValue([
        { id: 7, name: 'Anna', reference_count: 1 },
      ])
    })

    it('lädt die gefilterte Folge, zählt in ihr und blättert mit dem Filter weiter', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [photo({ id: 4 }), photo({ id: 9 })],
        total: 2,
      })
      const user = userEvent.setup()

      renderPage('/projects/1/photos/4?filter=unrated&person=7')
      await screen.findByText('1/2')

      expect(photosApi.listPhotos).toHaveBeenCalledWith(
        1,
        expect.objectContaining({ ratingStatus: 'unrated', personIds: [7] }),
      )
      await user.click(screen.getByRole('button', { name: /weiter|nächst/i }))
      await screen.findByText('2/2')
      expect(screen.getByRole('link', { name: 'Zurück zum Grid' })).toHaveAttribute(
        'href',
        '/projects/1/photos?filter=unrated&person=7',
      )
    })

    it('trägt "Beide" (zweimal person) in "Zurück zum Grid" weiter', async () => {
      vi.mocked(personsApi.listPersons).mockResolvedValue([
        { id: 7, name: 'Anna', reference_count: 1 },
        { id: 8, name: 'Ben', reference_count: 1 },
      ])
      vi.mocked(photosApi.listPhotos).mockResolvedValue({ items: [photo({ id: 4 })], total: 1 })

      renderPage('/projects/1/photos/4?person=7&person=8')
      await screen.findByText('1/1')

      expect(screen.getByRole('link', { name: 'Zurück zum Grid' })).toHaveAttribute(
        'href',
        '/projects/1/photos?person=7&person=8',
      )
    })

    it('lässt das Foto nach dem Entfernen des Namens stehen, ohne die Folge neu zu laden', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [
          photo({ id: 4, persons: [{ person_id: 7, origin: 'recognized', face: null }] }),
          photo({ id: 9, persons: [{ person_id: 7, origin: 'recognized', face: null }] }),
        ],
        total: 2,
      })
      vi.mocked(personsApi.setPhotoPerson).mockResolvedValue([])
      const user = userEvent.setup()

      renderPage('/projects/1/photos/4?person=7')
      await screen.findByText('1/2')
      const requests = vi.mocked(photosApi.listPhotos).mock.calls.length

      await user.click(await screen.findByRole('button', { name: 'Entfernen: Anna' }))

      expect(await screen.findByText('Nicht zugeordnet')).toBeInTheDocument()
      expect(screen.getByText('1/2')).toBeInTheDocument()
      expect(photosApi.listPhotos).toHaveBeenCalledTimes(requests)
      await user.click(screen.getByRole('button', { name: /weiter|nächst/i }))
      await screen.findByText('2/2')
      expect(screen.getByText('Erkannt')).toBeInTheDocument()
      expect(photosApi.listPhotos).toHaveBeenCalledTimes(requests)
    })

    it('stellt den Personenabschnitt hinter die Urteilsfläche, nicht in den Motivbereich', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({ items: [photo({ id: 4 })], total: 1 })

      renderPage('/projects/1/photos/4')
      const persons = await screen.findByRole('region', { name: 'Personen' })

      expect(screen.getByTestId('verdict-section')).not.toContainElement(persons)
      expect(screen.getByTestId('motifs-section')).not.toContainElement(persons)
    })

    it('fragt beim Blättern keine Gesichter ab, klappt beim Fotowechsel zu und gibt die Ausschnitte frei', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [photo({ id: 4 }), photo({ id: 9 })],
        total: 2,
      })
      vi.mocked(personsApi.listFaces).mockResolvedValue([
        { index: 0, box: { x: 0, y: 0, width: 0.5, height: 0.5 } },
      ])
      vi.mocked(personsApi.fetchFaceImage).mockResolvedValue(new Blob(['x']))
      const revokeObjectURL = vi.fn()
      Object.assign(URL, { createObjectURL: vi.fn(() => 'blob:face-4'), revokeObjectURL })
      const user = userEvent.setup()

      renderPage('/projects/1/photos/4')
      await screen.findByText('1/2')
      await user.click(await screen.findByRole('button', { name: 'Gesicht zeigen' }))
      await screen.findByRole('button', { name: 'Gesicht 1 von 1' })
      await waitFor(() => expect(URL.createObjectURL).toHaveBeenCalledTimes(1))
      await user.click(screen.getByRole('button', { name: /weiter|nächst/i }))
      await screen.findByText('2/2')

      expect(screen.getByRole('button', { name: 'Gesicht zeigen' })).toHaveAttribute(
        'aria-expanded',
        'false',
      )
      expect(revokeObjectURL).toHaveBeenCalledWith('blob:face-4')
      expect(personsApi.listFaces).toHaveBeenCalledExactlyOnceWith(4)
    })

    it('stellt die Zeile nach dem Zeigen eines Gesichts auf "Von Hand zugeordnet"', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({ items: [photo({ id: 4 })], total: 1 })
      vi.mocked(personsApi.listFaces).mockResolvedValue([
        { index: 2, box: { x: 0, y: 0, width: 0.5, height: 0.5 } },
      ])
      vi.mocked(personsApi.fetchFaceImage).mockResolvedValue(new Blob(['x']))
      vi.mocked(personsApi.addReference).mockResolvedValue({
        person: { id: 7, name: 'Anna', reference_count: 2 },
        learned: true,
        photo_persons: [{ person_id: 7, origin: 'corrected', face: 'shown' }],
      })
      Object.assign(URL, { createObjectURL: vi.fn(() => 'blob:face'), revokeObjectURL: vi.fn() })
      const user = userEvent.setup()

      renderPage('/projects/1/photos/4')
      await user.click(await screen.findByRole('button', { name: 'Gesicht zeigen' }))
      await user.click(await screen.findByRole('button', { name: 'Gesicht 1 von 1' }))
      await user.click(
        within(screen.getByRole('group', { name: 'Wer ist das?' })).getByRole('button', {
          name: 'Anna',
        }),
      )

      expect(await screen.findByText('Von Hand zugeordnet, Gesicht gezeigt')).toBeInTheDocument()
      expect(personsApi.addReference).toHaveBeenCalledWith(7, 4, 2)
      expect(screen.getByText('Gesicht als Anna gezeigt.')).toBeInTheDocument()
    })
  })

  it('navigates to the next photo on ArrowRight', async () => {
    const list: PhotoListOut = { items: [photo({ id: 1 }), photo({ id: 2 })], total: 2 }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)
    const user = userEvent.setup()

    renderPage('/projects/1/photos/1')
    await screen.findByText('1/2')

    await user.keyboard('{ArrowRight}')

    await screen.findByText('2/2')
  })

  it('sets a rating and auto-advances to the next unrated photo', async () => {
    const list: PhotoListOut = {
      items: [photo({ id: 1 }), photo({ id: 2 }), photo({ id: 3 })],
      total: 3,
    }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)
    vi.mocked(ratingsApi.setRating).mockResolvedValue({
      photo_id: 1,
      user_id: 1,
      status: 'album_worthy',
      favorite: false,
      updated_at: '2026-09-13T10:00:00',
    })
    const user = userEvent.setup()

    renderPage('/projects/1/photos/1')
    await screen.findByText('1/3')

    await user.click(screen.getByRole('button', { name: /album-würdig/i }))

    expect(ratingsApi.setRating).toHaveBeenCalledWith(1, 'album_worthy')
    await screen.findByText('2/3')
  })

  it('does not auto-advance and does not touch the album decision when the favorite is set', async () => {
    // Die Auszeichnung ist keine Entscheidung UEBER dieses Foto, sondern eine Notiz daneben -
    // weiterzuspringen naehme dem Nutzer die Moeglichkeit, im selben Atemzug noch zu
    // entscheiden. Und sie geht ueber den EIGENEN Endpunkt: ein gemeinsamer Schreibweg setzte
    // die Albumentscheidung hier still zurueck.
    const list: PhotoListOut = { items: [photo({ id: 1 }), photo({ id: 2 })], total: 2 }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)
    vi.mocked(ratingsApi.setFavorite).mockResolvedValue({
      photo_id: 1,
      user_id: 1,
      status: null,
      favorite: true,
      updated_at: '2026-09-13T10:00:00',
    })
    const user = userEvent.setup()

    renderPage('/projects/1/photos/1')
    await screen.findByText('1/2')

    await user.click(screen.getByRole('button', { name: /favorit/i }))

    expect(ratingsApi.setFavorite).toHaveBeenCalledWith(1, true)
    expect(ratingsApi.setRating).not.toHaveBeenCalled()
    expect(ratingsApi.deleteRating).not.toHaveBeenCalled()
    expect(screen.getByText('1/2')).toBeInTheDocument()
  })

  it('clears the favorite marker on a second press without touching the album decision', async () => {
    const list: PhotoListOut = {
      items: [
        photo({
          id: 1,
          ratings: [{ user_id: 1, username: 'testuser', status: 'rejected', favorite: true }],
        }),
      ],
      total: 1,
    }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)
    vi.mocked(ratingsApi.setFavorite).mockResolvedValue({
      photo_id: 1,
      user_id: 1,
      status: 'rejected',
      favorite: false,
      updated_at: '2026-09-13T10:00:00',
    })
    const user = userEvent.setup()

    renderPage('/projects/1/photos/1')
    await screen.findByText('1/1')

    await user.click(screen.getByRole('button', { name: /favorit/i }))

    expect(ratingsApi.setFavorite).toHaveBeenCalledWith(1, false)
    expect(ratingsApi.deleteRating).not.toHaveBeenCalled()
  })

  it('still treats a photo that carries only the favorite marker as undecided', async () => {
    // Auto-Advance sucht das naechste Foto OHNE Albumentscheidung. Auf das Vorhandensein der
    // Zeile gepruefte Abwesenheit uebersprAenge ein nur als Favorit markiertes Foto still.
    const list: PhotoListOut = {
      items: [
        photo({ id: 1 }),
        photo({
          id: 2,
          ratings: [{ user_id: 1, username: 'testuser', status: null, favorite: true }],
        }),
        photo({ id: 3 }),
      ],
      total: 3,
    }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)
    vi.mocked(ratingsApi.setRating).mockResolvedValue({
      photo_id: 1,
      user_id: 1,
      status: 'album_worthy',
      favorite: false,
      updated_at: '2026-09-13T10:00:00',
    })
    const user = userEvent.setup()

    renderPage('/projects/1/photos/1')
    await screen.findByText('1/3')

    await user.click(screen.getByRole('button', { name: /album-würdig/i }))

    await screen.findByText('2/3')
  })

  /*
   * specs/features/0321-dark-utility-register-ansichten.md, Etappe 3: NEUE FEHLERKLASSE, die diese
   * Spec erst erzeugt - EIN KAESTCHEN, DAS LUEGT. Die sichtbare Ziffer steht seit dem Umbau in
   * `RatingButtons`, die Tastenbelegung hier in `PhotoDetailPage`; beide koennen auseinanderlaufen,
   * ohne dass irgendein anderer Test etwas merkt.
   *
   * Deshalb Tabelle ueber ALLE DREI Tasten, und je Zeile die zusaetzliche Zusicherung, dass die
   * Schaltflaeche des ausgeloesten Status genau diese Ziffer sichtbar traegt. Ein Test, der nur die
   * Anwesenheit der Ziffern prueft, erfuellt das nicht.
   */
  it.each([
    ['2', 'album_worthy', 'Album-würdig'],
    ['3', 'rejected', 'Verwerfen'],
  ] as const)(
    'sets the rating of key "%s" and shows that very key on its button',
    async (key, status, label) => {
      const list: PhotoListOut = { items: [photo({ id: 1 }), photo({ id: 2 })], total: 2 }
      vi.mocked(photosApi.listPhotos).mockResolvedValue(list)
      vi.mocked(ratingsApi.setRating).mockResolvedValue({
        photo_id: 1,
        user_id: 1,
        status,
        favorite: false,
        updated_at: '2026-09-13T10:00:00',
      })
      const user = userEvent.setup()

      renderPage('/projects/1/photos/1')
      await screen.findByText('1/2')

      await user.keyboard(key)

      expect(ratingsApi.setRating).toHaveBeenCalledWith(1, status)
      // Das Kennzeichen bleibt unberuehrt - die Taste schreibt genau ihr Feld.
      expect(ratingsApi.setFavorite).not.toHaveBeenCalled()
      expect(screen.getByRole('button', { name: label })).toHaveTextContent(key)
    },
  )

  it('routes key "1" to the favorite endpoint and shows that very key on its button', async () => {
    // Die dritte Zeile derselben Tabelle, aber mit ANDEREM Ziel: Die Belegung 1/2/3 bleibt, Taste
    // 1 schreibt seit ADR 0098 das unabhaengige Kennzeichen. Getrennt geschrieben, weil sonst
    // genau die Zusage "die Taste fasst das jeweils andere Feld nicht an" im Rauschen unterginge.
    const list: PhotoListOut = { items: [photo({ id: 1 }), photo({ id: 2 })], total: 2 }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)
    vi.mocked(ratingsApi.setFavorite).mockResolvedValue({
      photo_id: 1,
      user_id: 1,
      status: null,
      favorite: true,
      updated_at: '2026-09-13T10:00:00',
    })
    const user = userEvent.setup()

    renderPage('/projects/1/photos/1')
    await screen.findByText('1/2')

    await user.keyboard('1')

    expect(ratingsApi.setFavorite).toHaveBeenCalledWith(1, true)
    expect(ratingsApi.setRating).not.toHaveBeenCalled()
    expect(ratingsApi.deleteRating).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'Favorit' })).toHaveTextContent('1')
  })

  it('toggles an existing rating back to unrated when the same button is clicked again', async () => {
    const list: PhotoListOut = {
      items: [
        photo({
          id: 1,
          ratings: [{ user_id: 1, username: 'testuser', status: 'album_worthy', favorite: false }],
        }),
        photo({ id: 2 }),
      ],
      total: 2,
    }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)
    vi.mocked(ratingsApi.deleteRating).mockResolvedValue({
      photo_id: 1,
      user_id: 1,
      status: null,
      favorite: false,
      updated_at: null,
    })
    const user = userEvent.setup()

    renderPage('/projects/1/photos/1')
    await screen.findByText('1/2')

    await user.click(screen.getByRole('button', { name: /album-würdig/i }))

    expect(ratingsApi.deleteRating).toHaveBeenCalledWith(1)
    expect(ratingsApi.setRating).not.toHaveBeenCalled()
    // Anders als beim Setzen einer Bewertung (spec: "Nach dem Setzen einer Bewertung springt...")
    // ist ein Toggle-zurueck-auf-unbewertet eine Korrektur, kein "fertig mit diesem Foto" -
    // Auto-Advance waere hier ueberraschend (Nutzer klickt erneut, um einen Fehlklick
    // rueckgaengig zu machen, nicht um weiterzuspringen).
    await waitFor(() => expect(ratingsApi.deleteRating).toHaveBeenCalled())
    expect(screen.getByText('1/2')).toBeInTheDocument()
  })

  it('shows a completion message instead of a fatal error once no unrated photo is left', async () => {
    const list: PhotoListOut = { items: [photo({ id: 1 })], total: 1 }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)
    vi.mocked(ratingsApi.setRating).mockResolvedValue({
      photo_id: 1,
      user_id: 1,
      status: 'album_worthy',
      favorite: false,
      updated_at: '2026-09-13T10:00:00',
    })
    const user = userEvent.setup()

    renderPage('/projects/1/photos/1')
    await screen.findByText('1/1')

    await user.click(screen.getByRole('button', { name: /album-würdig/i }))

    expect(await screen.findByRole('status')).toHaveTextContent(
      /keine weiteren unbewerteten fotos/i,
    )
  })

  /*
   * specs/features/0298-projektnavigation-in-der-kopfzeile.md (AK14, Bestandsschutz): Beide Links
   * bleiben trotz der neuen Kopfzeilengruppe ausdruecklich erhalten - "Zur Endauswahl" ist
   * hier eine Handlungsaufforderung fuer den naechsten Arbeitsschritt (nur im Abschlusszustand),
   * "Zurück zum Grid" fuehrt zu einem ANDEREN Ziel als die Kopfzeile, weil es den aktiven Filter
   * der Fotoliste bewahrt. Eine Anwesenheits-, keine Abwesenheitspruefung: die Kopfzeilengruppe
   * darf sie nicht mitreissen.
   */
  it('keeps "Zurück zum Grid" and "Zur Endauswahl" in the completion state (AK14)', async () => {
    const list: PhotoListOut = { items: [photo({ id: 1 })], total: 1 }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)
    vi.mocked(ratingsApi.setRating).mockResolvedValue({
      photo_id: 1,
      user_id: 1,
      status: 'album_worthy',
      favorite: false,
      updated_at: '2026-09-13T10:00:00',
    })
    const user = userEvent.setup()

    renderPage('/projects/1/photos/1?filter=unrated')
    await screen.findByText('1/1')

    await user.click(screen.getByRole('button', { name: /album-würdig/i }))
    expect(await screen.findByRole('status')).toHaveTextContent(
      /keine weiteren unbewerteten fotos/i,
    )

    // Der Grid-Link bewahrt den aktiven Filter - genau das unterscheidet ihn vom Kopfzeilenziel
    // "Fotos", das immer auf die ungefilterte Liste zeigt.
    expect(screen.getByRole('link', { name: 'Zurück zum Grid' })).toHaveAttribute(
      'href',
      '/projects/1/photos?filter=unrated',
    )
    expect(screen.getByRole('link', { name: 'Zur Endauswahl' })).toHaveAttribute(
      'href',
      '/projects/1/selection',
    )
  })

  it('shows an inline error banner with a retry option on failure', async () => {
    vi.mocked(photosApi.listPhotos).mockRejectedValue(new ApiError(500, 'Serverfehler'))
    const user = userEvent.setup()

    renderPage('/projects/1/photos/1')
    expect(await screen.findByRole('alert')).toHaveTextContent('Serverfehler')

    vi.mocked(photosApi.listPhotos).mockResolvedValue({ items: [photo({ id: 1 })], total: 1 })
    await user.click(screen.getByRole('button', { name: /erneut versuchen/i }))

    await screen.findByText('1/1')
  })

  it('ignores keyboard shortcuts while a text input is focused elsewhere on the page', async () => {
    const list: PhotoListOut = { items: [photo({ id: 1 }), photo({ id: 2 })], total: 2 }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)
    const input = document.createElement('input')
    document.body.appendChild(input)
    input.focus()

    renderPage('/projects/1/photos/1')
    await screen.findByText('1/2')

    await userEvent.keyboard('1')

    await waitFor(() => expect(ratingsApi.setRating).not.toHaveBeenCalled())
    document.body.removeChild(input)
  })

  it('shows the suggestion reason and a confirm button for a low-quality suggestion', async () => {
    const list: PhotoListOut = {
      items: [photo({ id: 1, ratings: [], suggestion: suggestion({ reason: 'low_quality' }) })],
      total: 1,
    }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

    renderPage('/projects/1/photos/1')

    expect(await screen.findByText(/automatischer vorschlag: verworfen/i)).toBeInTheDocument()
    expect(screen.getByText(/geringe bildqualität/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /vorschlag übernehmen/i })).toBeInTheDocument()
  })

  it('shows the duplicate-of reason for a duplicate suggestion', async () => {
    const list: PhotoListOut = {
      items: [
        photo({
          id: 1,
          ratings: [],
          suggestion: suggestion({ reason: 'duplicate', duplicate_of: 42 }),
        }),
      ],
      total: 1,
    }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

    renderPage('/projects/1/photos/1')

    expect(await screen.findByText(/duplikat von foto #42/i)).toBeInTheDocument()
  })

  it('does not show a suggestion once an own rating exists', async () => {
    const list: PhotoListOut = {
      items: [
        photo({
          id: 1,
          ratings: [{ user_id: 1, username: 'testuser', status: 'rejected', favorite: false }],
          suggestion: null,
        }),
      ],
      total: 1,
    }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

    renderPage('/projects/1/photos/1')

    await screen.findByText('1/1')
    expect(screen.queryByText(/automatischer vorschlag/i)).not.toBeInTheDocument()
  })

  it('confirms a suggestion via the same mutation path as a manual rating and auto-advances', async () => {
    const list: PhotoListOut = {
      items: [
        photo({ id: 1, ratings: [], suggestion: suggestion({ status: 'rejected' }) }),
        photo({ id: 2, ratings: [] }),
      ],
      total: 2,
    }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)
    vi.mocked(ratingsApi.setRating).mockResolvedValue({
      photo_id: 1,
      user_id: 1,
      status: 'rejected',
      favorite: false,
      updated_at: '2026-09-13T10:00:00',
    })
    const user = userEvent.setup()

    renderPage('/projects/1/photos/1')
    const confirmButton = await screen.findByRole('button', { name: /vorschlag übernehmen/i })
    await user.click(confirmButton)

    expect(ratingsApi.setRating).toHaveBeenCalledWith(1, 'rejected')
    await screen.findByText('2/2')
  })
})
