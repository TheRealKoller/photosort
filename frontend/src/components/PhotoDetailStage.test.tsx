import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { PhotoDetailStage } from './PhotoDetailStage'

vi.mock('../api/photos', () => ({
  fetchPhotoImageBlobUrl: vi.fn(() => new Promise(() => {})),
}))

function renderStage(props: Partial<Parameters<typeof PhotoDetailStage>[0]> = {}) {
  const onToggle = vi.fn()
  const onToggleFavorite = vi.fn()
  const onPrev = vi.fn()
  const onNext = vi.fn()
  const view = render(
    <PhotoDetailStage
      status="ready"
      counter="3/57"
      photoId={1}
      altText="a.jpg"
      currentStatus={null}
      favorite={false}
      onToggle={onToggle}
      onToggleFavorite={onToggleFavorite}
      ratingDisabled={false}
      ratingBusy={false}
      onPrev={onPrev}
      onNext={onNext}
      prevDisabled={false}
      nextDisabled={false}
      {...props}
    />,
  )
  return { ...view, onToggle, onToggleFavorite, onPrev, onNext }
}

/** Der Rahmen, den ALLE DREI Zustände tragen müssen - dieselbe Sondenliste dreimal. Springt die
 *  Seite beim Eintreffen der Daten, fehlt hier einer der drei. */
function rahmenSonden(): Record<string, boolean> {
  return {
    Zählerzeile: screen.queryByText('3/57') !== null,
    Bewertungsgruppe: screen.queryByRole('group', { name: 'Bewertung' }) !== null,
    'Navigation zurück': screen.queryByRole('button', { name: 'Vorheriges Foto' }) !== null,
    'Navigation weiter': screen.queryByRole('button', { name: 'Nächstes Foto' }) !== null,
  }
}

const RAHMEN_VOLLSTAENDIG = {
  Zählerzeile: true,
  Bewertungsgruppe: true,
  'Navigation zurück': true,
  'Navigation weiter': true,
}

describe('PhotoDetailStage: der Rahmen in allen drei Zuständen', () => {
  /* DIESELBE SONDENLISTE DREIMAL. Der Rahmen steht in `ladend` und `fehler` bereits in seiner
     endgültigen Geometrie - sonst springt die Seite beim Eintreffen der Daten, und das ist genau
     die "Bewegung von Layout oder Position", die das Design-System ausschließt. */
  it.each([
    { status: 'ready' as const },
    { status: 'loading' as const },
    { status: 'error' as const },
  ])('trägt im Zustand $status den vollständigen Rahmen', ({ status }) => {
    renderStage({ status, errorText: 'Fehler beim Laden der Fotos.' })

    expect(rahmenSonden()).toEqual(RAHMEN_VOLLSTAENDIG)
  })

  it('zeigt im Fehlerfall den Fehlertext innerhalb des Rahmens', () => {
    renderStage({ status: 'error', errorText: 'Fehler beim Laden der Fotos.' })

    const stage = screen.getByTestId('photo-detail-stage')
    expect(within(stage).getByRole('alert')).toHaveTextContent('Fehler beim Laden der Fotos.')
  })

  /* Im Fehlerfall sind Bewertung und Navigation SICHTBAR, aber nicht aktiv: Eine unsichtbare
     Bedienleiste änderte die Geometrie, eine aktive schriebe gegen einen unbekannten Zustand. */
  it('sperrt Bewertung und Navigation im Fehlerfall', () => {
    renderStage({ status: 'error', errorText: 'Fehler.' })

    const bewertung = screen.getByRole('group', { name: 'Bewertung' })
    for (const button of within(bewertung).getAllByRole('button')) {
      expect(button).toBeDisabled()
    }
    expect(screen.getByRole('button', { name: 'Vorheriges Foto' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Nächstes Foto' })).toBeDisabled()
  })

  it('sperrt Bewertung und Navigation im Ladezustand', () => {
    renderStage({ status: 'loading' })

    const bewertung = screen.getByRole('group', { name: 'Bewertung' })
    for (const button of within(bewertung).getAllByRole('button')) {
      expect(button).toBeDisabled()
    }
    expect(screen.getByRole('button', { name: 'Vorheriges Foto' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Nächstes Foto' })).toBeDisabled()
  })

  it('zeigt im Ladezustand einen Platzhalter statt eines vorgezogenen Satzes', () => {
    renderStage({ status: 'loading' })

    const stage = screen.getByTestId('photo-detail-stage')
    expect(within(stage).getByTestId('photo-detail-stage-placeholder')).toBeInTheDocument()
    expect(within(stage).queryByRole('alert')).toBeNull()
  })
})

describe('PhotoDetailStage: die Reihenfolge innerhalb der Bühne', () => {
  /* Fotofläche, dann Bewertung, dann Navigation - die primäre, häufigste Handlung steht
     unmittelbar unter dem Foto. */
  it('stellt das Foto vor die Bewertung und die Bewertung vor die Navigation', async () => {
    renderStage()

    const handles = [
      { name: 'Zähler', element: screen.getByText('3/57') },
      { name: 'Fotofläche', element: screen.getByTestId('photo-detail-stage-photo') },
      { name: 'Bewertung', element: screen.getByRole('group', { name: 'Bewertung' }) },
      { name: 'Navigation', element: screen.getByRole('button', { name: 'Vorheriges Foto' }) },
    ]

    const folge = [...handles]
      .sort((a, b) =>
        (a.element.compareDocumentPosition(b.element) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0
          ? -1
          : 1,
      )
      .map((handle) => handle.name)

    expect(folge).toEqual(['Zähler', 'Fotofläche', 'Bewertung', 'Navigation'])
  })
})

describe('PhotoDetailStage: sie entscheidet nichts selbst', () => {
  it('reicht die Bewertung nach oben durch', async () => {
    const user = userEvent.setup()
    const { onToggle, onToggleFavorite } = renderStage()

    await user.click(screen.getByRole('button', { name: /Album-würdig/ }))
    await user.click(screen.getByRole('button', { name: /Favorit/ }))

    expect(onToggle).toHaveBeenCalledWith('album_worthy')
    expect(onToggleFavorite).toHaveBeenCalledTimes(1)
  })

  it('reicht die Navigation nach oben durch', async () => {
    const user = userEvent.setup()
    const { onPrev, onNext } = renderStage()

    await user.click(screen.getByRole('button', { name: 'Vorheriges Foto' }))
    await user.click(screen.getByRole('button', { name: 'Nächstes Foto' }))

    expect(onPrev).toHaveBeenCalledTimes(1)
    expect(onNext).toHaveBeenCalledTimes(1)
  })

  it('folgt den Sperrflaggen des Aufrufers', () => {
    renderStage({ prevDisabled: true, nextDisabled: false, ratingDisabled: true })

    expect(screen.getByRole('button', { name: 'Vorheriges Foto' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Nächstes Foto' })).toBeEnabled()
  })

  it('zeigt ohne Zähler keine Zählerzeile', () => {
    renderStage({ counter: null })

    expect(screen.queryByText('3/57')).toBeNull()
  })
})

describe('PhotoDetailStage: die Höhengeometrie', () => {
  /* AK10 — DIE BÜHNENHÖHE HÄNGT AM SICHTFENSTER, NICHT AM BILD. In jsdom ist `dvh`/`calc` nicht
     auswertbar; gemessen wird im Browser (`e2e/tests/bilddetail-buehne.spec.ts`, Fall 1). Hier
     bleibt die ABWESENHEITSZUSAGE: kein breitengeführtes Seitenverhältnis am Bild, keine in
     JavaScript gerechnete Höhe in einem Inline-Stil.

     Ein `aspect-*` am Bild machte die Bühne je Format verschieden hoch und schöbe beim Hochformat
     die Bewertungsleiste aus dem Bild. */
  it('bindet das Bild an keine Seitenverhältnis-Utility', () => {
    const { container } = renderStage()

    expect(container.querySelector('[class*="aspect-"]')).toBeNull()
  })

  it('setzt keine gerechnete Höhe als Inline-Stil', () => {
    // Weder eine in JavaScript gemessene Höhe noch eine CSS-Custom-Property als Träger eines
    // gerechneten Wertes - beides ist im Sicherheitskonzept untersagt.
    const { container } = renderStage()

    for (const node of container.querySelectorAll('[style]')) {
      expect(node.getAttribute('style')).not.toMatch(/height|--/)
    }
  })

  /* AK9a — GLEICHE LESEREIHENFOLGE AUF BEIDEN BREITEN. Abwesenheitszusage am gerenderten Markup:
     keine breakpoint-gebundene `order-*`-Utility und kein `*-reverse`. */
  it('ordnet nichts breitenabhängig um', () => {
    const { container } = renderStage()

    const klassen = [...container.querySelectorAll('[class]')]
      .map((node) => node.getAttribute('class') ?? '')
      .join(' ')

    expect(klassen).not.toMatch(/\b(sm|md|lg|xl|2xl):order-/)
    expect(klassen).not.toMatch(/-reverse\b/)
  })
})
