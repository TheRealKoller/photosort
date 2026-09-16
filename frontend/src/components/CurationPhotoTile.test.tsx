import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { PhotoOut, RankingOut, RatingStatus } from '../api/types'
import { MOTIF_SET } from '../test/motifSetFixture'
import { ALBUM_SUITABILITY_NOT_RATED_TEXT } from '../utils/albumSuitability'
import { CurationPhotoTile, NOT_PROPOSED_BADGE_TEXT } from './CurationPhotoTile'

/**
 * specs/features/0428-albumtauglichkeit-vom-modell.md: die Kachel trägt ab hier die
 * Stufenbeschriftung der Albumtauglichkeit und darunter die Begründung des Modells - auf zwei
 * Zeilen GEKÜRZT, aber vollständig im DOM.
 */
function ranking(overrides: Partial<RankingOut> = {}): RankingOut {
  return {
    event_id: 1,
    rank_score: 0.8,
    rank_position: 1,
    proposed: true,
    partition_size: 3,
    curation_position: 1,
    ...overrides,
  }
}

function photo(overrides: Partial<PhotoOut> = {}): PhotoOut {
  return {
    id: 1,
    relative_path: 'a.jpg',
    taken_at: '2026-07-20T10:00:00',
    taken_at_original: '2026-07-20T10:00:00',
    time_offset_minutes: 0,
    camera: null,
    ratings: [],
    suggestion: null,
    ranking: ranking(),
    criterion_scores: [],
    fine_labels: [],
    cloud_vision_status: [],
    final_selection_decision: null,
    in_final_selection: false,
    contested: false,
    motif_assessment: {
      source: 'cloud' as const,
      provider: 'anthropic',
      excluded_document: false,
      computed_at: '2026-07-21T09:00:00',
    },
    motifs: MOTIF_SET.items.map((item) => ({
      key: item.key,
      strength: 0.5,
      correction: null,
      present: false,
    })),
    album_suitability: { level: 4, reason: 'Alle schauen in die Kamera.' },
    ...overrides,
  }
}

function renderTile(
  overrides: Partial<PhotoOut> = {},
  tile: {
    ownStatus?: RatingStatus | null
    deciding?: boolean
    onDecide?: () => void
    onOpenAlternatives?: () => void
    focusDecision?: boolean
  } = {},
) {
  return render(
    <CurationPhotoTile
      photo={photo(overrides)}
      motifSet={MOTIF_SET}
      motifSetLoading={false}
      motifSetError={undefined}
      onMotifSetRetry={() => {}}
      ownStatus={tile.ownStatus ?? null}
      deciding={tile.deciding ?? false}
      onDecide={tile.onDecide ?? (() => {})}
      onOpenAlternatives={tile.onOpenAlternatives ?? (() => {})}
      focusDecision={tile.focusDecision ?? false}
    />,
  )
}

describe('CurationPhotoTile: die Stufenzeile', () => {
  it('shows the coarse level label for a rated photo', () => {
    renderTile({ ranking: ranking({ rank_score: 0.8 }) })

    expect(screen.getByText('Gut albumtauglich')).toBeInTheDocument()
  })

  it('shows the exact level nowhere on the tile', () => {
    /* Zwei Skalen nebeneinander wären zwei Zahlen für eine Aussage - die genaue Stufe steht nur
     * in den Bewertungsdetails. */
    renderTile({ album_suitability: { level: 4, reason: null } })

    expect(screen.queryByText('Stufe 4 von 5')).toBeNull()
  })

  it('says "Noch nicht bewertet" for a photo without a quality score', () => {
    renderTile({ ranking: ranking({ rank_score: null, rank_position: null }) })

    expect(screen.getByText(ALBUM_SUITABILITY_NOT_RATED_TEXT)).toBeInTheDocument()
  })

  it('renders no meter glyph for a photo without a quality score', () => {
    const { container } = renderTile({
      ranking: ranking({ rank_score: null, rank_position: null }),
    })

    expect(container.querySelectorAll('[data-quality-meter-dots]')).toHaveLength(0)
  })

  it('keeps a quality score of 0 as a real level instead of "not rated"', () => {
    /* `0` ist ein gültiger Qualitätswert. Eine Falsyness-Prüfung zeigte hier fälschlich
     * „Noch nicht bewertet". */
    renderTile({ ranking: ranking({ rank_score: 0 }) })

    expect(screen.getByText('Wenig albumtauglich')).toBeInTheDocument()
    expect(screen.queryByText(ALBUM_SUITABILITY_NOT_RATED_TEXT)).toBeNull()
  })
})

describe('CurationPhotoTile: die Begründung', () => {
  it('keeps the full reason in the DOM even though it is visually clamped', () => {
    /* Assertion auf den TEXTINHALT, nicht auf die sichtbare Zeilenzahl - die kann jsdom nicht.
     * Die Kürzung geschieht per `line-clamp`, nie durch Abschneiden der Zeichenkette: der
     * vorgelesene Text bleibt vollständig. */
    const reason =
      'Die Person ist am linken Bildrand angeschnitten, der Hintergrund ist unruhig und ' +
      'der Bildaufbau wirkt dadurch zufällig gewählt.'

    const { container } = renderTile({ album_suitability: { level: 2, reason } })

    const carrier = container.querySelector('[data-album-suitability-reason]')
    expect(carrier).not.toBeNull()
    expect(carrier?.textContent).toBe(reason)
    expect(carrier?.className).toContain('line-clamp-2')
  })

  it('renders no carrier at all when there is no reason', () => {
    const { container } = renderTile({ album_suitability: { level: 3, reason: null } })

    expect(container.querySelectorAll('[data-album-suitability-reason]')).toHaveLength(0)
  })

  it('renders no carrier at all when the photo has no verdict', () => {
    const { container } = renderTile({ album_suitability: null })

    expect(container.querySelectorAll('[data-album-suitability-reason]')).toHaveLength(0)
  })

  it('never renders the reason as markup', () => {
    /* SICHERHEIT (S12): freier, extern erzeugter LLM-Text aus einem Bild, das Text enthalten
     * kann. */
    const payload = '<img src=x onerror="alert(1)">'

    const { container } = renderTile({ album_suitability: { level: 1, reason: payload } })

    expect(container.querySelector('img')).toBeNull()
    expect(screen.getByText(payload)).toBeInTheDocument()
  })

  it('never turns a javascript: payload into a link', () => {
    const payload = 'javascript:alert(1)'

    const { container } = renderTile({ album_suitability: { level: 1, reason: payload } })

    expect(container.querySelector('a')).toBeNull()
    expect(container.querySelector('img')).toBeNull()
    expect(screen.getByText(payload)).toBeInTheDocument()
  })

  it('adds no expand control to the tile footer', () => {
    /* Kein Ausklapp-Bedienelement je Kachel - die Begründung steht vollständig im DOM und wird
     * rein visuell gekürzt. */
    renderTile({
      album_suitability: { level: 2, reason: 'Eine ziemlich lange Begründung des Modells.' },
    })

    expect(screen.getByRole('button', { name: 'Im Album: a.jpg' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /mehr|ausklappen|weiterlesen/i })).toBeNull()
  })
})

describe('CurationPhotoTile: der Zweizustand Im Album ⇄ Gestrichen', () => {
  it('is pressed for a photo of the album and carries the file name in its name', () => {
    renderTile({}, { ownStatus: null })

    const toggle = screen.getByRole('button', { name: 'Im Album: a.jpg' })
    expect(toggle).toHaveAttribute('aria-pressed', 'true')
  })

  it('is not pressed for a struck photo and says so', () => {
    renderTile({}, { ownStatus: 'rejected' })

    const toggle = screen.getByRole('button', { name: 'Gestrichen: a.jpg' })
    expect(toggle).toHaveAttribute('aria-pressed', 'false')
  })

  it('strikes a photo of the album on the first press', async () => {
    const onDecide = vi.fn()
    const user = userEvent.setup()
    renderTile({}, { ownStatus: 'album_worthy', onDecide })

    await user.click(screen.getByRole('button', { name: 'Im Album: a.jpg' }))

    expect(onDecide).toHaveBeenCalledWith('rejected')
  })

  it('takes a struck photo back into the album on the next press', async () => {
    const onDecide = vi.fn()
    const user = userEvent.setup()
    renderTile({}, { ownStatus: 'rejected', onDecide })

    await user.click(screen.getByRole('button', { name: 'Gestrichen: a.jpg' }))

    expect(onDecide).toHaveBeenCalledWith('album_worthy')
  })

  it('stays enabled while its own decision is running and takes no second press', async () => {
    /* Ohne Bestätigungsschritt und ohne Dialog - aber ein zweiter Druck auf DASSELBE Foto während
     * der laufenden Mutation liefe in den Unique-Constraint der Bewertungszeile. */
    const onDecide = vi.fn()
    const user = userEvent.setup()
    renderTile({}, { ownStatus: null, deciding: true, onDecide })

    // Namentlich der Zweizustand: die Fußzeile trägt seit dem Austausch ZWEI Trefferflächen, und
    // gesperrt ist ausschließlich die schreibende.
    await user.click(screen.getByRole('button', { name: 'Im Album: a.jpg' }))

    expect(onDecide).not.toHaveBeenCalled()
  })

  it('keeps the struck photo in place, carrying its rating state', () => {
    /* Ein gestrichenes Foto verschwindet nicht und nichts rückt nach - es behält den bestehenden
     * Anzeigezustand der `PhotoCard`, und der ist seit Spec 0498 allein das Kennzeichen samt
     * durchgestrichenem Dateinamen; die Bildfläche steht in voller Helligkeit. */
    const { container } = renderTile({}, { ownStatus: 'rejected' })

    expect(container.querySelector('[data-rating-status="rejected"]')).not.toBeNull()
  })
})

describe('CurationPhotoTile: aufgenommen, vom Vorschlag nicht getragen', () => {
  it('marks a taken photo the run dropped from the candidate pool', () => {
    renderTile({ ranking: null }, { ownStatus: 'album_worthy' })

    expect(screen.getByText(NOT_PROPOSED_BADGE_TEXT)).toBeInTheDocument()
  })

  it('marks a taken candidate the run did not propose IDENTICALLY', () => {
    // Zusicherung 23: zwei Datenformen, EIN Anzeigezustand - geprueft ueber dieselbe Beschriftung.
    renderTile({ ranking: ranking({ proposed: false }) }, { ownStatus: 'album_worthy' })

    expect(screen.getByText(NOT_PROPOSED_BADGE_TEXT)).toBeInTheDocument()
  })

  it('marks nothing on a photo the run proposes', () => {
    renderTile({ ranking: ranking({ proposed: true }) }, { ownStatus: 'album_worthy' })

    expect(screen.queryByText(NOT_PROPOSED_BADGE_TEXT)).toBeNull()
  })

  it('marks nothing without an own decision', () => {
    renderTile({ ranking: ranking({ proposed: false }) }, { ownStatus: null })

    expect(screen.queryByText(NOT_PROPOSED_BADGE_TEXT)).toBeNull()
  })
})

describe('CurationPhotoTile: der Zugang zu den Alternativen', () => {
  it('offers a SECOND hit area next to the toggle, with the file name in its name', () => {
    // Die Fußzeile verliert hier bewusst ihre bisherige Ein-Trefferflächen-Regel. Der Dateiname
    // steht im zugänglichen Namen, sonst hießen auf einer Seite mit vielen Kacheln alle
    // Schaltflächen gleich.
    renderTile()

    expect(screen.getByRole('button', { name: 'Alternativen: a.jpg' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Im Album: a.jpg' })).toBeInTheDocument()
  })

  it('opens the alternatives on the first press - no confirmation step', async () => {
    const onOpenAlternatives = vi.fn()
    const user = userEvent.setup()
    renderTile({}, { onOpenAlternatives })

    await user.click(screen.getByRole('button', { name: 'Alternativen: a.jpg' }))

    expect(onOpenAlternatives).toHaveBeenCalledTimes(1)
  })

  it('stays reachable for a struck photo - the exchange is reversible from both sides', () => {
    renderTile({}, { ownStatus: 'rejected' })

    expect(screen.getByRole('button', { name: 'Alternativen: a.jpg' })).toBeEnabled()
  })

  it('keeps both hit areas at least 44px tall on the phone', () => {
    // `h-11 sm:h-8` wie die Bewertungsleiste. Beide Flächen gehören zum heißen Pfad und werden
    // auf dem Telefon mit dem Daumen getroffen.
    renderTile()

    for (const name of ['Im Album: a.jpg', 'Alternativen: a.jpg']) {
      expect(screen.getByRole('button', { name }).className).toContain('h-11')
    }
  })
})

describe('CurationPhotoTile: der Fokus nach einem Austausch', () => {
  it('takes the focus onto its album toggle when asked for it', () => {
    // Nach einem Austausch schließt der Dialog, und der Fokus gehört auf die Kachel, die nun an
    // dieser Stelle steht - nicht zurück auf eine Schaltfläche eines Bildes, das gerade den Platz
    // gewechselt hat.
    renderTile({}, { focusDecision: true })

    expect(screen.getByRole('button', { name: 'Im Album: a.jpg' })).toHaveFocus()
  })

  it('leaves the focus alone otherwise', () => {
    renderTile({}, { focusDecision: false })

    expect(screen.getByRole('button', { name: 'Im Album: a.jpg' })).not.toHaveFocus()
  })
})
