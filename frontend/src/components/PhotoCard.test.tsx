import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'

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
    <MemoryRouter>
      <ul>
        <PhotoCard
          to="/projects/1/photos/42"
          relativePath="2024/07/IMG_0042.jpg"
          image={<img alt="2024/07/IMG_0042.jpg" src="blob:x" />}
          {...props}
        />
      </ul>
    </MemoryRouter>
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
    const states: (RatingStatus | null)[] = [null, 'favorite', 'album_worthy', 'rejected']

    const signatures = states.map((status) => {
      const { container, unmount } = render(
        <MemoryRouter>
          <ul>
            <PhotoCard
              to="/projects/1/photos/42"
              relativePath="2024/07/IMG_0042.jpg"
              status={status}
              image={<img alt="2024/07/IMG_0042.jpg" src="blob:x" />}
            />
          </ul>
        </MemoryRouter>
      )
      const item = container.querySelector('li')!
      const signature = [
        item.getAttribute('data-rating-status'),
        item.textContent?.replace('IMG_0042.jpg', '').trim(),
        item.querySelector('[data-icon]')?.getAttribute('data-icon') ?? 'kein Symbol',
      ].join('|')
      unmount()
      return signature
    })

    expect(new Set(signatures).size).toBe(4)
    for (const field of [0, 1, 2]) {
      expect(new Set(signatures.map((entry) => entry.split('|')[field])).size, `Merkmal ${field}`).toBe(4)
    }
  })

  it('marks only the rejected state with the struck-through file name', () => {
    for (const status of [null, 'favorite', 'album_worthy'] as const) {
      const { container, unmount } = renderCard({ status })
      expect(container.querySelector('[data-struck]'), `${status}`).toBeNull()
      unmount()
    }

    // Im aussortierten Zustand traegt der Dateiname die Durchstreichung als DOM-Merkmal. Das
    // Kennzeichen selbst fuehrt `data-struck` seit Stufe 1 ebenfalls (es benennt den Zustand,
    // ohne selbst gestrichen zu sein) - geprueft wird deshalb gezielt der Dateiname.
    const { container } = renderCard({ status: 'rejected' })
    const struck = [...container.querySelectorAll('[data-struck="true"]')].map((node) => node.textContent)
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

  it('shows no rating indicator at all when the card carries no rating state', () => {
    // Kuratierung und Vergleich zeigen den Zustand woanders bzw. gar nicht - die Karte darf dort
    // nichts hinzufuegen ("es wird nichts hinzugefuegt" ist Akzeptanzkriterium).
    const { container } = renderCard()

    expect(container.querySelector('[data-rating-status]')).toBeNull()
    expect(screen.queryByText('Neu')).not.toBeInTheDocument()
  })

  // e2e-Vertragsflaeche: `photoTiles` = listitem, das ein a[href*="/photos/"] enthaelt.
  it('renders as a listitem containing the tile link', () => {
    renderCard()

    const item = screen.getByRole('listitem')
    expect(within(item).getByRole('link')).toHaveAttribute('href', '/projects/1/photos/42')
  })

  it('renders the image area as a non-link when no target is given', () => {
    renderCard({ to: undefined })

    expect(screen.queryByRole('link')).not.toBeInTheDocument()
    expect(screen.getByRole('listitem')).toBeInTheDocument()
  })

  /*
   * Fallstrick "tap-target nie in einen beschneidenden Container": Die Bildflaeche traegt
   * `overflow-hidden`; ein Ecken-Trigger als Kind wuerde still seine Trefferflaeche abgeschnitten
   * bekommen. Die Zusicherung wandert mit dem Baustein aus PhotoGridPage.test.tsx eine Ebene nach
   * unten - sie ist zugleich der Ersatz fuer den entfallenen `pointer-events-none`-Test.
   */
  it('keeps the corner slots siblings of the tile link, never children of it', () => {
    renderCard({
      topLeft: <button type="button">Marker</button>,
      topRight: <button type="button">Details</button>,
    })

    const item = screen.getByRole('listitem')
    const link = within(item).getByRole('link')
    for (const name of ['Marker', 'Details']) {
      const trigger = screen.getByRole('button', { name })
      expect(link.contains(trigger), name).toBe(false)
      expect(item.contains(trigger), name).toBe(true)
    }
  })

  it('renders footer children outside the tile link', () => {
    renderCard({ footer: <button type="button">Übernehmen</button> })

    const item = screen.getByRole('listitem')
    const action = screen.getByRole('button', { name: 'Übernehmen' })
    expect(within(item).getByRole('link').contains(action)).toBe(false)
    expect(item.contains(action)).toBe(true)
  })

  it('shows only the base name of the file, never the folder part', () => {
    renderCard()

    expect(screen.getByText('IMG_0042.jpg')).toBeInTheDocument()
    expect(screen.queryByText(/2024\/07/)).not.toBeInTheDocument()
  })

  it('keeps the file name outside the link and out of its accessible name', () => {
    renderCard()

    const link = screen.getByRole('link')
    const fileName = screen.getByText('IMG_0042.jpg')
    expect(link.contains(fileName)).toBe(false)
    // Der Name des Kachel-Links bleibt der alt-Text des Bildes, nicht der Dateiname daneben.
    expect(link).toHaveAccessibleName('2024/07/IMG_0042.jpg')
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
    const { container } = renderCard({ status: 'favorite' })

    expect(container.querySelector('[data-selected]')).toBeNull()
  })
})
