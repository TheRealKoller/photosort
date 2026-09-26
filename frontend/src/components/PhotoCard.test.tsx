import { fireEvent, render, screen } from '@testing-library/react'
import { createRef } from 'react'
import { describe, expect, it, vi } from 'vitest'

import type { RatingStatus } from '../api/types'
import { PhotoCard } from './PhotoCard'

/*
 * specs/features/0321-dark-utility-register-ansichten.md, Etappe 3.
 *
 * KEINE CSS-ASSERTIONEN (Regel aus Stufe 1): Zustaende werden ueber `data-*`, Rollen und
 * sichtbaren Text geprueft. Alles Gerechnete, Gestrichene oder Gedaempfte liegt im Vertragstest
 * `designSystem.contract.test.ts`. Auch `sm:`-Verhalten (`p-2 sm:p-3`) wird hier NIE geprueft -
 * eine Zusicherung auf den Klassennamen prueft die Schreibweise, nicht die Wirkung.
 */
function renderCard(props: Partial<Parameters<typeof PhotoCard>[0]> = {}) {
  return render(
    <ul>
      <PhotoCard
        relativePath="2024/07/IMG_0042.jpg"
        image={<img alt="2024/07/IMG_0042.jpg" src="blob:x" />}
        onImageActivate={() => {}}
        imageTriggerLabel="Großansicht: 2024/07/IMG_0042.jpg"
        {...props}
      />
    </ul>,
  )
}

describe('PhotoCard', () => {
  /*
   * Die vier Zustaende des Boards, die im Produkt vorkommen. Der fuenfte Board-Zustand
   * "ausgewaehlt" wird bewusst NICHT gebaut (Entscheidung 5: PhotoSort kennt keine Foto-Auswahl)
   * und deshalb auch nicht getestet.
   *
   * Geprueft als PAARWEISE VERSCHIEDENHEIT statt als vier abgeschriebene Einzelfaelle: Genau das
   * ist die Zusage - die Zustaende muessen sich voneinander unterscheiden lassen, und zwar an
   * mehreren, nicht-farblichen Merkmalen zugleich.
   */
  it('keeps the four card states pairwise distinguishable without colour perception', () => {
    // Vier Zustaende wie bisher - seit ADR 0098 aber aus ZWEI Feldern gebildet: der Favorit ist
    // kein Wert von `status` mehr, sondern das Kennzeichen ohne Albumentscheidung.
    const states: { status: RatingStatus | null; favorite?: boolean }[] = [
      { status: null },
      { status: null, favorite: true },
      { status: 'album_worthy' },
      { status: 'rejected' },
    ]

    const signatures = states.map(({ status, favorite }) => {
      const { container, unmount } = render(
        <ul>
          <PhotoCard
            relativePath="2024/07/IMG_0042.jpg"
            status={status}
            favorite={favorite}
            image={<img alt="2024/07/IMG_0042.jpg" src="blob:x" />}
          />
        </ul>,
      )
      const item = container.querySelector('li')!
      const signature = [
        // BEIDE Felder, nicht nur `status`: "unbewertet" und "nur Favorit" tragen dasselbe
        // `data-rating-status` und waeren allein daran nicht auseinanderzuhalten.
        `${item.getAttribute('data-rating-status')}/${item.getAttribute('data-rating-favorite') ?? 'kein Favorit'}`,
        item.textContent?.replace('IMG_0042.jpg', '').trim(),
        item.querySelector('[data-icon]')?.getAttribute('data-icon') ?? 'kein Symbol',
      ].join('|')
      unmount()
      return signature
    })

    expect(new Set(signatures).size).toBe(4)
    for (const field of [0, 1, 2]) {
      expect(
        new Set(signatures.map((entry) => entry.split('|')[field])).size,
        `Merkmal ${field}`,
      ).toBe(4)
    }
  })

  it('marks only the rejected state with the struck-through file name', () => {
    for (const status of [null, 'album_worthy'] as const) {
      const { container, unmount } = renderCard({ status })
      expect(container.querySelector('[data-struck]'), `${status}`).toBeNull()
      unmount()
    }
    const favoriteOnly = renderCard({ status: null, favorite: true })
    expect(favoriteOnly.container.querySelector('[data-struck]')).toBeNull()
    favoriteOnly.unmount()

    // Im aussortierten Zustand traegt der Dateiname die Durchstreichung als DOM-Merkmal. Das
    // Kennzeichen selbst fuehrt `data-struck` seit Stufe 1 ebenfalls (es benennt den Zustand,
    // ohne selbst gestrichen zu sein) - geprueft wird deshalb gezielt der Dateiname.
    const { container } = renderCard({ status: 'rejected' })
    const struck = [...container.querySelectorAll('[data-struck="true"]')].map(
      (node) => node.textContent,
    )
    expect(struck).toContain('IMG_0042.jpg')
  })

  /*
   * Entscheidung 3: Auf der Karte steht im Zustand "neu" das WORT "Neu", nicht das neutrale
   * "–"-Badge. Der Prueffall haelt beide Haelften fest - ohne die zweite koennte das Badge hier
   * unbemerkt zurueckkehren und das Wort verdoppeln.
   */
  it('shows the word "Neu" for an unrated photo, without the neutral badge', () => {
    renderCard({ status: null })

    expect(screen.getByText('Neu')).toBeInTheDocument()
    expect(screen.queryByLabelText('Unbewertet')).not.toBeInTheDocument()
    expect(screen.queryByText('–')).not.toBeInTheDocument()
  })

  /*
   * `setAside` ist die gemeinsame Herausnahme aus der Endauswahl (Spec 0431): erkennbar, aber OHNE
   * Bewertungs-Kennzeichen. Beide Haelften gehoeren in EINEN Fall - getrennt bestuende jede auch
   * bei einer Umsetzung, die `setAside` einfach auf `status='rejected'` abbildet und damit ein
   * unbenanntes "Verworfen" an den Kartenkoerper haengt.
   *
   * TRAEGER IST DER DURCHGESTRICHENE DATEINAME, nicht mehr die Bildflaeche (Spec 0498 AK4): Die
   * Bildflaeche steht seither in voller Helligkeit, und ohne Bewertungszustand ist die
   * Durchstreichung der einzige Zustandstraeger dieser Karte.
   */
  it('marks a set-aside card by its struck file name, WITHOUT asserting a rating state', () => {
    const { container } = renderCard({ setAside: true })

    expect(container.querySelector('[data-struck="true"]')?.textContent).toBe('IMG_0042.jpg')
    expect(container.querySelector('[data-rating-status]')).toBeNull()
    expect(screen.queryByLabelText('Verworfen')).not.toBeInTheDocument()
  })

  it('shows no rating indicator at all when the card carries no rating state', () => {
    // Kuratierung und Vergleich zeigen den Zustand woanders bzw. gar nicht - die Karte darf dort
    // nichts hinzufuegen ("es wird nichts hinzugefuegt" ist Akzeptanzkriterium).
    const { container } = renderCard()

    expect(container.querySelector('[data-rating-status]')).toBeNull()
    expect(screen.queryByText('Neu')).not.toBeInTheDocument()
  })

  it('renders the image area as neither link nor button without onImageActivate', () => {
    renderCard({ onImageActivate: undefined })

    expect(screen.queryByRole('link')).not.toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(screen.getByRole('listitem')).toBeInTheDocument()
  })

  it('makes the image area a button that activates once and hands out its element', () => {
    const onImageActivate = vi.fn()
    const imageTriggerRef = createRef<HTMLButtonElement>()
    renderCard({ onImageActivate, imageTriggerRef })

    const trigger = screen.getByRole('button', { name: 'Großansicht: 2024/07/IMG_0042.jpg' })
    fireEvent.click(trigger)

    expect(onImageActivate).toHaveBeenCalledTimes(1)
    expect(trigger).toHaveAttribute('type', 'button')
    expect(imageTriggerRef.current).toBe(trigger)
  })

  /*
   * Fallstrick "tap-target nie in einen beschneidenden Container": Die Bildflaeche traegt
   * `overflow-hidden`; ein Ecken-Trigger als Kind wuerde still seine Trefferflaeche abgeschnitten
   * bekommen. Die Zusicherung wandert mit dem Baustein aus PhotoGridPage.test.tsx eine Ebene nach
   * unten - sie ist zugleich der Ersatz fuer den entfallenen `pointer-events-none`-Test.
   */
  it('keeps the corner slots siblings of the image trigger, never children of it', () => {
    renderCard({
      topLeft: <button type="button">Marker</button>,
      topRight: <button type="button">Details</button>,
    })

    const item = screen.getByRole('listitem')
    const imageTrigger = screen.getByRole('button', { name: /^Großansicht: / })
    for (const name of ['Marker', 'Details']) {
      const trigger = screen.getByRole('button', { name })
      expect(imageTrigger.contains(trigger), name).toBe(false)
      expect(item.contains(trigger), name).toBe(true)
    }
  })

  it('renders footer children outside the image trigger', () => {
    renderCard({ footer: <button type="button">Übernehmen</button> })

    const item = screen.getByRole('listitem')
    const action = screen.getByRole('button', { name: 'Übernehmen' })
    expect(screen.getByRole('button', { name: /^Großansicht: / }).contains(action)).toBe(false)
    expect(item.contains(action)).toBe(true)
  })

  it('shows only the base name of the file, never the folder part', () => {
    renderCard()

    expect(screen.getByText('IMG_0042.jpg')).toBeInTheDocument()
    expect(screen.queryByText(/2024\/07/)).not.toBeInTheDocument()
  })

  it('keeps the file name outside the image trigger and out of its accessible name', () => {
    renderCard()

    const trigger = screen.getByRole('button', { name: /^Großansicht: / })
    const fileName = screen.getByText('IMG_0042.jpg')
    expect(trigger.contains(fileName)).toBe(false)
    expect(trigger).toHaveAccessibleName('Großansicht: 2024/07/IMG_0042.jpg')
    // Der Dateiname ist Inhalt, kein Dekor - er wird NICHT vor Screenreadern versteckt.
    expect(fileName).not.toHaveAttribute('aria-hidden')
  })

  /*
   * Sicherheits-Muss-Kriterium der Spec: Der Dateiname stammt aus dem WebDAV-Walk der OpenCloud
   * und ist damit extern entstandener Text. Er wird ausschliesslich als regulaerer React-Textknoten
   * gerendert - nie ueber `dangerouslySetInnerHTML`. Seit ADR 0005 liegt das Session-Token in
   * `localStorage`; ein eingeschleustes Skript laese es unmittelbar aus.
   */
  it('never renders the file name via dangerouslySetInnerHTML (plain text node)', () => {
    const hostile = '<img src=x onerror="window.__pwned = true">'
    renderCard({ relativePath: `2024/07/${hostile}` })

    expect(screen.getByText(hostile)).toBeInTheDocument()
    expect(document.querySelector('img[src="x"]')).toBeNull()
    expect((window as unknown as Record<string, unknown>).__pwned).toBeUndefined()
  })

  // Entscheidung 5, von Daniel zurueckgestellt: der fuenfte Board-Zustand wird weder gebaut noch
  // vorbereitet. Diese Zusicherung haelt fest, dass keine stille Vorbereitung entstanden ist.
  it('does not build the board state "selected"', () => {
    const { container } = renderCard({ status: 'album_worthy', favorite: true })

    expect(container.querySelector('[data-selected]')).toBeNull()
  })
})
