import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { RatingStatus } from '../api/types'
import { PhotoGridTile } from './PhotoGridTile'
import type { PhotoGridTileProps } from './PhotoGridTile'

/*
 * specs/features/0489-fotouebersicht-ohne-beschnitt.md, AK3-AK9: Die Rasterkachel.
 *
 * Geprueft wird ueber zugaengliche Namen und semantische `data-*`, NIE ueber Klassennamen - eine
 * Klassenpruefung bindet den Test an die Gestaltung statt an die Aussage.
 */

const BASE: PhotoGridTileProps = {
  to: '/projects/7/photos/42',
  relativePath: 'Reise/2024/IMG_0042.jpg',
  status: null,
  suggestedStatus: null,
  favorite: false,
  width: 300,
  height: 200,
  image: <span data-testid="bildinhalt" />,
}

function renderTile(props: Partial<PhotoGridTileProps> = {}) {
  return render(
    <MemoryRouter initialEntries={['/projects/7/photos']}>
      <Routes>
        <Route
          path="/projects/7/photos"
          element={
            <ul>
              <PhotoGridTile {...BASE} {...props} />
            </ul>
          }
        />
        <Route path="/projects/7/photos/:photoId" element={<p>Detailansicht</p>} />
      </Routes>
    </MemoryRouter>,
  )
}

function marks(): HTMLElement[] {
  return Array.from(document.querySelectorAll<HTMLElement>('[data-mark]'))
}

/**
 * Ein Druck der angegebenen Dauer auf das uebergebene Element. Zeit kommt ueber Fake-Timer, NIE
 * ueber echtes Warten - ein Test, der 500 ms schlaeft, verlaengert den Prueflauf um genau diese
 * Zeit und wird auf einer langsamen Maschine trotzdem sprunghaft.
 *
 * DAS ABSCHLIESSENDE `pointerleave` GEHOERT ZWINGEND DAZU: Ein Touch-Pointer wird nach `pointerup`
 * vom Browser ZERSTOERT, und dabei feuert er `pointerleave` - ohne Zutun des Nutzers. Ein Helfer,
 * der nur `pointerdown`/`pointerup` sendet, bildet den Druck am Telefon nicht ab, und jede daran
 * haengende Zusage bestuende, ohne im Browser zu gelten.
 */
function press(element: HTMLElement, milliseconds: number): void {
  vi.useFakeTimers()
  act(() => {
    element.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true }))
  })
  act(() => {
    vi.advanceTimersByTime(milliseconds)
  })
  act(() => {
    element.dispatchEvent(new MouseEvent('pointerup', { bubbles: true }))
    // Gesendet wird `pointerout`, nicht `pointerleave`: React synthetisiert `onPointerLeave`
    // ueber das Ueber-/Austritts-Paar, und ein direkt abgesetztes `pointerleave` erreichte den
    // Rueckruf gar nicht - der Fall bliebe gruen, ohne etwas zu pruefen.
    element.dispatchEvent(new MouseEvent('pointerout', { bubbles: true, relatedTarget: null }))
  })
}

function stubHover(matches: boolean): void {
  vi.stubGlobal(
    'matchMedia',
    vi.fn().mockReturnValue({
      matches,
      media: '(hover: hover) and (pointer: fine)',
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  )
}

beforeEach(() => {
  stubHover(false)
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe('PhotoGridTile: Struktur (AK2, Barrierefreiheit)', () => {
  it('is a list item with exactly one link to the photo', () => {
    // Daran haengen vier E2E-Specs: `photoTiles()` findet `listitem` mit `a[href*="/photos/"]`.
    renderTile()

    const item = screen.getByRole('listitem')
    const links = within(item).getAllByRole('link')
    expect(links).toHaveLength(1)
    expect(links[0]).toHaveAttribute('href', '/projects/7/photos/42')
  })

  it('carries the computed size as an inline style, never as a class', () => {
    // Auflage S6: Das gerechnete Mass geht als ZAHL in eine gewoehnliche CSS-Eigenschaft - keine
    // Custom-Property, kein aus API-Daten zusammengesetzter Zeichenkettenwert, kein `url()`.
    renderTile({ width: 317, height: 211 })

    const item = screen.getByRole('listitem')
    expect(item.style.width).toBe('317px')
    expect(item.style.height).toBe('211px')
    expect(item.className).not.toMatch(/\[/)
  })

  it('shows the image inside the tile', () => {
    renderTile()

    expect(screen.getByTestId('bildinhalt')).toBeInTheDocument()
  })
})

describe('PhotoGridTile: die zwei Zeichen (AK3-AK5)', () => {
  it('shows no mark at all on an untouched photo', () => {
    renderTile()

    expect(marks()).toHaveLength(0)
  })

  it('shows the star exactly when the photo is an own favourite', () => {
    renderTile({ favorite: true })

    const found = marks()
    expect(found).toHaveLength(1)
    expect(found[0]).toHaveAttribute('data-mark', 'favorite')
    expect(screen.getByRole('listitem')).toHaveTextContent('Favorit')
  })

  it('shows no empty star as a counter state', () => {
    // "Er steht da oder er ist nicht im Dokument."
    renderTile({ favorite: false, status: 'album_worthy' })

    expect(marks().map((mark) => mark.dataset.mark)).toEqual(['album'])
  })

  it.each<[RatingStatus]>([['album_worthy'], ['rejected']])(
    'shows a filled dot for the own decision %s',
    (status) => {
      renderTile({ status })

      const dot = marks().find((mark) => mark.dataset.mark === 'album')
      expect(dot).toHaveAttribute('data-mark-shape', 'filled')
      expect(dot).toHaveAttribute('data-mark-status', status)
    },
  )

  it.each<[RatingStatus]>([['album_worthy'], ['rejected']])(
    'shows a ring for the unconfirmed suggestion %s',
    (suggestedStatus) => {
      renderTile({ suggestedStatus })

      const dot = marks().find((mark) => mark.dataset.mark === 'album')
      expect(dot).toHaveAttribute('data-mark-shape', 'ring')
      expect(dot).toHaveAttribute('data-mark-status', suggestedStatus)
    },
  )

  it('lets the own decision win over a suggestion', () => {
    renderTile({ status: 'album_worthy', suggestedStatus: 'rejected' })

    const dot = marks().find((mark) => mark.dataset.mark === 'album')
    expect(dot).toHaveAttribute('data-mark-shape', 'filled')
    expect(dot).toHaveAttribute('data-mark-status', 'album_worthy')
  })

  it('never shows a third mark, whatever the combination', () => {
    const combinations: Partial<PhotoGridTileProps>[] = [
      {},
      { favorite: true },
      { status: 'album_worthy' },
      { status: 'rejected' },
      { suggestedStatus: 'album_worthy' },
      { suggestedStatus: 'rejected' },
      { favorite: true, status: 'album_worthy' },
      { favorite: true, status: 'rejected' },
      { favorite: true, suggestedStatus: 'album_worthy' },
      { favorite: true, suggestedStatus: 'rejected' },
      { favorite: true, status: 'rejected', suggestedStatus: 'album_worthy' },
    ]

    for (const props of combinations) {
      const { unmount } = renderTile(props)
      expect(marks().length).toBeLessThanOrEqual(2)
      unmount()
    }
  })

  it.each([
    { props: { favorite: true }, text: 'Favorit' },
    { props: { status: 'album_worthy' as const }, text: 'Album-würdig' },
    { props: { status: 'rejected' as const }, text: 'Verworfen' },
    { props: { suggestedStatus: 'album_worthy' as const }, text: 'Album-würdig vorgeschlagen' },
    { props: { suggestedStatus: 'rejected' as const }, text: 'Verworfen vorgeschlagen' },
  ])('names the state $text as invisible text', ({ props, text }) => {
    // Der Stern und der Punkt ersetzen das bisherige beschriftete Kennzeichen; ohne diesen Text
    // verloere die Ansicht ihre Aussage fuer Bildschirmleser.
    renderTile(props)

    expect(screen.getByRole('listitem')).toHaveTextContent(text)
  })

  it('gives the marks no own hit area and no own focus', () => {
    // "Die beiden Zeichen sind KEINE Bedienelemente."
    renderTile({ favorite: true, status: 'rejected' })

    for (const mark of marks()) {
      expect(mark.tagName.toLowerCase()).not.toBe('button')
      expect(mark).not.toHaveAttribute('tabindex')
      expect(mark.closest('button')).toBeNull()
    }
  })
})

/*
 * specs/features/0498-volle-helligkeit.md, AK2/AK4 (hebt AK6 der Spec 0489 auf): Die Bildflaeche
 * der verworfenen Aufnahme wird nicht mehr gedaempft. Traeger des Zustands bleibt der Punkt in der
 * Bildecke - und seine FORM trennt weiterhin die Entscheidung vom Vorschlag (Spec 0489 AK5), was
 * bis hierher am dritten Fall des entfallenen Daempfungs-Blocks hing.
 */
describe('PhotoGridTile: volle Helligkeit, Zustand am Punkt', () => {
  it.each([
    { label: 'a rejected photo', props: { status: 'rejected' as const }, shape: 'filled' },
    { label: 'an album-worthy photo', props: { status: 'album_worthy' as const }, shape: 'filled' },
    {
      label: 'a photo merely suggested for rejection',
      props: { suggestedStatus: 'rejected' as const },
      shape: 'ring',
    },
  ])('shows $label undimmed, with its state on the dot', ({ props, shape }) => {
    renderTile({ ...props, favorite: true })

    const item = screen.getByRole('listitem')
    expect(item).not.toHaveAttribute('data-dimmed')
    expect(item.querySelectorAll('[data-dimmed]')).toHaveLength(0)

    // Ein Vorschlag ist keine Entscheidung - er tritt nicht zurueck, er fragt. Gefuellt heisst
    // entschieden, der blosse Ring heisst vorgeschlagen.
    const dot = item.querySelector('[data-mark="album"]')
    expect(dot).toHaveAttribute('data-mark-shape', shape)
    expect(dot).toHaveAttribute('data-mark-status', props.status ?? props.suggestedStatus)
  })

  it('keeps the marks outside the image area', () => {
    // Die beiden Zeichen sind GESCHWISTER der Bildflaeche, nie ihre Kinder: Sie liegen auf der
    // undurchsichtigen Flaeche `--overlay`, damit ihr Kontrast nachrechenbar bleibt.
    renderTile({ status: 'rejected', favorite: true })

    const bildflaeche = screen.getByTestId('bildinhalt').parentElement
    expect(marks()).toHaveLength(2)
    for (const mark of marks()) {
      expect(bildflaeche?.contains(mark)).toBe(false)
    }
  })
})

describe('PhotoGridTile: die Angabenzeile (AK7, AK8)', () => {
  it('keeps the file name out of the document while at rest', () => {
    renderTile()

    expect(screen.queryByText('IMG_0042.jpg')).not.toBeInTheDocument()
  })

  it('shows the line on hover where the device has a fine pointer', async () => {
    stubHover(true)
    const user = userEvent.setup()
    renderTile()

    await user.hover(screen.getByRole('listitem'))

    expect(screen.getByText('IMG_0042.jpg')).toBeInTheDocument()
  })

  it('does not show the line on hover where the device has no fine pointer', async () => {
    stubHover(false)
    const user = userEvent.setup()
    renderTile()

    await user.hover(screen.getByRole('listitem'))

    expect(screen.queryByText('IMG_0042.jpg')).not.toBeInTheDocument()
  })

  it('shows the line on focus', async () => {
    const user = userEvent.setup()
    renderTile()

    await user.tab()

    expect(screen.getByText('IMG_0042.jpg')).toBeInTheDocument()
  })

  it('caps the line at a quarter of the image height', () => {
    // Auflage S6 und AK7 in einem: das gerechnete Mass als ZAHL in einer gewoehnlichen
    // CSS-Eigenschaft, nie als willkuerliche Klasse (`max-h-[25%]`).
    renderTile({ height: 240 })
    const link = screen.getByRole('link')

    press(link, 600)

    expect(screen.getByText('IMG_0042.jpg').style.maxHeight).toBe('60px')
  })

  it('shows the line after a press of at least 500 ms, without navigating', () => {
    renderTile()
    const link = screen.getByRole('link')

    press(link, 500)

    expect(screen.getByText('IMG_0042.jpg')).toBeInTheDocument()
    expect(screen.queryByText('Detailansicht')).not.toBeInTheDocument()
  })

  it('leaves the line hidden after a shorter press and navigates instead', async () => {
    renderTile()
    const link = screen.getByRole('link')

    press(link, 499)
    expect(screen.queryByText('IMG_0042.jpg')).not.toBeInTheDocument()

    vi.useRealTimers()
    await userEvent.setup().click(link)

    expect(screen.getByText('Detailansicht')).toBeInTheDocument()
  })

  it('keeps the line after the finger is lifted', () => {
    // DER FALL AM TELEFON: Nach `pointerup` zerstoert der Browser den Touch-Pointer und feuert
    // dabei `pointerleave`. Blendete das aus, waere der Dateiname genau so lange zu sehen, wie der
    // Finger ihn verdeckt - also nie.
    renderTile()

    press(screen.getByRole('link'), 600)

    expect(screen.getByText('IMG_0042.jpg')).toBeInTheDocument()
  })

  it('closes the pressed line on the next press anywhere', () => {
    // Das Gegenstueck zum langen Druck: Am Zeigegeraet schliesst das Verlassen der Kachel die
    // Zeile, am Telefon gibt es das nicht - dort schliesst sie der naechste Druck.
    renderTile()
    press(screen.getByRole('link'), 600)
    expect(screen.getByText('IMG_0042.jpg')).toBeInTheDocument()

    act(() => {
      document.body.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true }))
    })

    expect(screen.queryByText('IMG_0042.jpg')).not.toBeInTheDocument()
  })

  it('closes the pressed line on scrolling', () => {
    renderTile()
    press(screen.getByRole('link'), 600)

    act(() => {
      window.dispatchEvent(new Event('scroll'))
    })

    expect(screen.queryByText('IMG_0042.jpg')).not.toBeInTheDocument()
  })

  it('stops listening once the tile is gone', () => {
    // Ohne Ruecknahme lauschte je eingeblendeter Kachel dauerhaft ein Zuhoerer am Dokument.
    renderTile()
    press(screen.getByRole('link'), 600)
    const entfernen = vi.spyOn(document, 'removeEventListener')

    act(() => {
      document.body.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true }))
    })

    expect(entfernen).toHaveBeenCalledWith('pointerdown', expect.any(Function), { capture: true })
    entfernen.mockRestore()
  })

  it('still hides the hovered line when the pointer leaves', () => {
    // Die Gegenprobe zum Fall darueber: Was durch Ueberfahren kam, verschwindet beim Verlassen
    // weiterhin. Ohne sie bestuende die Zusage auch gegen eine Kachel, die nie mehr ausblendet.
    stubHover(true)
    renderTile()
    const item = screen.getByRole('listitem')

    act(() => {
      item.dispatchEvent(new MouseEvent('pointerover', { bubbles: true, relatedTarget: null }))
    })
    expect(screen.getByText('IMG_0042.jpg')).toBeInTheDocument()

    act(() => {
      item.dispatchEvent(new MouseEvent('pointerout', { bubbles: true, relatedTarget: null }))
    })

    expect(screen.queryByText('IMG_0042.jpg')).not.toBeInTheDocument()
  })

  it('suppresses the navigation of the long press itself', () => {
    renderTile()
    const link = screen.getByRole('link')

    press(link, 600)
    act(() => {
      link.click()
    })

    expect(screen.queryByText('Detailansicht')).not.toBeInTheDocument()
  })
})

describe('PhotoGridTile: die Gate-Aktionen (AK12)', () => {
  it('shows nothing below the image without actions', () => {
    renderTile()

    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('shows the handed-in actions permanently', () => {
    renderTile({ actions: <button type="button">Übernehmen</button> })

    expect(screen.getByRole('button', { name: 'Übernehmen' })).toBeVisible()
  })
})
