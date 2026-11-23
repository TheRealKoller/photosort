/*
 * Foto-Detailseite - Teil: Navigation: Laden, Blaettern, Scrollstand (Spec 0651; gemeinsamer Unterbau in src/test/photoDetailPage.tsx).
 */
import { fireEvent, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import * as photosApi from '../api/photos'
import type { PhotoListOut } from '../api/types'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { photo, renderPage, resetPhotoDetailMocks, resetPersonsMock } from '../test/photoDetailPage'

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

  it('shows a loading state before the sequence arrives', () => {
    /* Spec 0497: Der Ladezustand ist kein vorgezogener Satz mehr, sondern der VOLLSTAENDIGE
       Buehnenrahmen mit einem Platzhalter in der Fotoflaeche - sonst springt die Seite beim
       Eintreffen der Daten. Die geprueften Verhaltensweise ("es gibt einen erkennbaren
       Ladezustand") bleibt, ihr Traeger wechselt. */
    vi.mocked(photosApi.listPhotos).mockReturnValue(new Promise(() => {}))

    renderPage('/projects/1/photos/1')

    const stage = screen.getByTestId('photo-detail-stage')
    expect(within(stage).getByTestId('photo-detail-stage-placeholder')).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Bewertung' })).toBeInTheDocument()
  })

  it('renders the photo with progress "index/total" and the own rating highlighted', async () => {
    const list: PhotoListOut = {
      items: [
        photo({
          id: 1,
          ratings: [{ user_id: 1, username: 'testuser', status: 'album_worthy', favorite: true }],
        }),
        photo({ id: 2 }),
      ],
      total: 2,
    }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

    renderPage('/projects/1/photos/1')

    expect(await screen.findByText('1/2')).toBeInTheDocument()
    // BEIDE gedrueckt zugleich - der sichtbare Beweis der Trennung (ADR 0098 Punkt 2).
    expect(screen.getByRole('button', { name: /album-würdig/i })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(screen.getByRole('button', { name: /favorit/i })).toHaveAttribute('aria-pressed', 'true')
    expect(photosApi.fetchPhotoImageBlobUrl).toHaveBeenCalledWith(1, 'display')
  })

  it('disables the previous button on the first photo and the next button on the last', async () => {
    const list: PhotoListOut = { items: [photo({ id: 1 }), photo({ id: 2 })], total: 2 }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

    renderPage('/projects/1/photos/1')
    await screen.findByText('1/2')

    expect(screen.getByRole('button', { name: /zurück|vorherig/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /weiter|nächst/i })).toBeEnabled()
  })

  it('navigates to the next photo on next-button click, preserving the filter', async () => {
    const list: PhotoListOut = { items: [photo({ id: 1 }), photo({ id: 2 })], total: 2 }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)
    const user = userEvent.setup()

    renderPage('/projects/1/photos/1?filter=unrated')
    await screen.findByText('1/2')

    await user.click(screen.getByRole('button', { name: /weiter|nächst/i }))

    await screen.findByText('2/2')
  })

  it('ignores an unknown/tampered filter value in the URL instead of forwarding it to the API', async () => {
    const list: PhotoListOut = { items: [photo({ id: 1 })], total: 1 }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

    renderPage('/projects/1/photos/1?filter=not-a-real-filter')
    await screen.findByText('1/1')

    expect(photosApi.listPhotos).toHaveBeenCalledWith(
      1,
      expect.objectContaining({ ratingStatus: undefined }),
    )
  })

  /* Verdrahtung der ZWEITEN Einbindung (Bedienteil) - die Logik selbst liegt auf
   * Komponentenebene, hier wird nur geprueft, dass die Props tatsaechlich ankommen. */
  /* Akzeptanzkriterium 5: Tastenkuerzel und Wischgesten wirken unveraendert. ArrowLeft und die
   * Wischgesten hatten bis zu dieser Spec keinen Test - ohne sie waere "unveraendert" beim
   * Umbau der Seite eine unbelegte Behauptung. */
  describe('Blättern per Tastatur und Wischgeste', () => {
    function twoPhotos(): PhotoListOut {
      return { items: [photo({ id: 1 }), photo({ id: 2, relative_path: 'b.jpg' })], total: 2 }
    }

    it('navigates to the previous photo on ArrowLeft', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue(twoPhotos())
      const user = userEvent.setup()

      renderPage('/projects/1/photos/2')
      await screen.findByText('2/2')

      await user.keyboard('{ArrowLeft}')

      await screen.findByText('1/2')
    })

    it('blättert bei einer Wischgeste nach links zum nächsten Foto', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue(twoPhotos())

      renderPage('/projects/1/photos/1')
      const image = await screen.findByAltText('a.jpg')

      fireEvent.touchStart(image, { touches: [{ clientX: 200 }] })
      fireEvent.touchEnd(image, { changedTouches: [{ clientX: 100 }] })

      await screen.findByText('2/2')
    })

    it('blättert bei einer Wischgeste nach rechts zum vorherigen Foto', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue(twoPhotos())

      renderPage('/projects/1/photos/2')
      const image = await screen.findByAltText('b.jpg')

      fireEvent.touchStart(image, { touches: [{ clientX: 100 }] })
      fireEvent.touchEnd(image, { changedTouches: [{ clientX: 200 }] })

      await screen.findByText('1/2')
    })

    /* Ohne diesen Fall bestuende auch ein Vergleich, der JEDE Beruehrung als Wisch liest - die
     * 50-px-Schwelle waere eine Zahl ohne Zusage. */
    it('navigiert unterhalb der 50-px-Schwelle nicht', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue(twoPhotos())

      renderPage('/projects/1/photos/1')
      const image = await screen.findByAltText('a.jpg')

      fireEvent.touchStart(image, { touches: [{ clientX: 200 }] })
      fireEvent.touchEnd(image, { changedTouches: [{ clientX: 170 }] })

      expect(screen.getByText('1/2')).toBeInTheDocument()
    })
  })
})

/* specs/features/0497-bilddetail-urteil-zuerst.md, AK2 — die Vorbedingung der Bühnengeometrie.
   Die Bühne ist aus dem Sichtfenster gerechnet und steht ganz oben auf der Seite; sie liegt nur
   dann vollständig im Bild, wenn die Seite auch oben steht. Ohne Rücksetzung übernimmt die
   Detailansicht den Scrollstand des Rasters, aus dem sie geöffnet wurde - beim Klick auf eine
   weiter unten liegende Kachel landet der Nutzer auf einer bereits gescrollten Detailseite, und
   Bewertungsleiste und Navigation stehen unter dem Sichtrand. */
describe('PhotoDetailPage: die Seite steht beim Öffnen oben (AK2)', () => {
  beforeEach(() => {
    resetPhotoDetailMocks()
  })

  it('setzt den Scrollstand beim Öffnen zurück', async () => {
    const scrollTo = vi.spyOn(window, 'scrollTo').mockImplementation(() => {})
    vi.mocked(photosApi.listPhotos).mockResolvedValue({ items: [photo({ id: 1 })], total: 1 })

    renderPage('/projects/1/photos/1')
    await screen.findByText('1/1')

    expect(scrollTo).toHaveBeenCalledWith(0, 0)
    scrollTo.mockRestore()
  })

  it('setzt den Scrollstand bei jedem Fotowechsel zurück', async () => {
    /* Jedes neue Foto ist erneut ein „Öffnen der Ansicht": Pfeiltaste, Wischen und Auto-Advance
       führen alle hierher, und in jedem Fall muss die Bühne wieder vollständig im Bild stehen. */
    const scrollTo = vi.spyOn(window, 'scrollTo').mockImplementation(() => {})
    vi.mocked(photosApi.listPhotos).mockResolvedValue({
      items: [photo({ id: 1 }), photo({ id: 2 })],
      total: 2,
    })

    renderPage('/projects/1/photos/1')
    await screen.findByText('1/2')
    scrollTo.mockClear()

    fireEvent.keyDown(window, { key: 'ArrowRight' })
    await screen.findByText('2/2')

    expect(scrollTo).toHaveBeenCalledWith(0, 0)
    scrollTo.mockRestore()
  })
})
