import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { PhotoOut, RankingOut, RatingStatus } from '../api/types'
import { MOTIF_SET } from '../test/motifSetFixture'
import { ALBUM_SUITABILITY_NOT_RATED_TEXT } from '../utils/albumSuitability'
import { ALBUM_STATE_LABELS } from '../utils/albumStateLabels'
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
    persons: [],
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
    onToggleAlternatives?: () => void
    alternativesExpanded?: boolean
    error?: string | null
    onOpenLarge?: (photoId: number) => void
    largeTriggerRef?: (element: HTMLElement | null) => void
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
      alternatives={{
        expanded: tile.alternativesExpanded ?? false,
        controls: 'band-1',
        onToggle: tile.onToggleAlternatives ?? (() => {}),
      }}
      error={tile.error ?? null}
      onOpenLarge={tile.onOpenLarge ?? (() => {})}
      largeTriggerRef={tile.largeTriggerRef ?? (() => {})}
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

describe('CurationPhotoTile: die Entscheidungsfläche nennt die Handlung', () => {
  it('says "Streichen" on a photo of the album, with the file name, never aria-pressed', () => {
    renderTile({}, { ownStatus: null })

    const button = screen.getByRole('button', { name: 'Streichen: a.jpg' })
    expect(button).not.toHaveAttribute('aria-pressed')
    expect(button).toHaveTextContent('Streichen')
  })

  it('says "Wieder aufnehmen" on a struck photo, again without aria-pressed', () => {
    renderTile({}, { ownStatus: 'rejected' })

    const button = screen.getByRole('button', { name: 'Wieder aufnehmen: a.jpg' })
    expect(button).not.toHaveAttribute('aria-pressed')
    expect(screen.queryByRole('button', { name: /^Streichen: / })).toBeNull()
  })

  it('acts on the first press, without a confirmation step', async () => {
    const onDecide = vi.fn()
    const user = userEvent.setup()
    renderTile({}, { ownStatus: 'album_worthy', onDecide })

    await user.click(screen.getByRole('button', { name: 'Streichen: a.jpg' }))

    expect(onDecide).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('is busy while its own decision runs and takes no second press', async () => {
    // Ein zweiter Druck auf DASSELBE Foto liefe in den Unique-Constraint der Bewertungszeile.
    const onDecide = vi.fn()
    const user = userEvent.setup()
    renderTile({}, { ownStatus: null, deciding: true, onDecide })

    await user.click(screen.getByRole('button', { name: 'Streichen: a.jpg' }))

    expect(onDecide).not.toHaveBeenCalled()
  })

  it('shows the reason of a failed action at the tile', () => {
    renderTile({}, { error: 'Die Bewertung wurde gerade verändert.' })

    expect(screen.getByRole('alert')).toHaveTextContent('Die Bewertung wurde gerade verändert.')
  })
})

describe('CurationPhotoTile: das Kennzeichen des Zustands', () => {
  function badge(container: HTMLElement): HTMLElement {
    const found = container.querySelector<HTMLElement>('[data-album-state]')
    if (found === null) {
      throw new Error('kein Kennzeichen')
    }
    return found
  }

  function icons(element: HTMLElement): string[] {
    return [...element.querySelectorAll('[data-icon]')].map((icon) => icon.getAttribute('data-icon') ?? '')
  }

  it('marks an untouched proposed photo as "Vorschlag" with cog and book', () => {
    const { container } = renderTile({}, { ownStatus: null })

    const element = badge(container)
    expect(element).toHaveAccessibleName(ALBUM_STATE_LABELS.proposal)
    expect(icons(element)).toEqual(['cog', 'book'])
  })

  it('marks an own album decision as "Aufgenommen" with book alone - also on a proposed photo', () => {
    const { container } = renderTile({}, { ownStatus: 'album_worthy' })

    const element = badge(container)
    expect(element).toHaveAccessibleName(ALBUM_STATE_LABELS.taken)
    expect(icons(element)).toEqual(['book'])
  })

  it('marks a struck photo as "Gestrichen" with x-circle and a struck file name', () => {
    const { container } = renderTile({}, { ownStatus: 'rejected' })

    const element = badge(container)
    expect(element).toHaveAccessibleName(ALBUM_STATE_LABELS.struck)
    expect(icons(element)).toEqual(['x-circle'])
    expect(within(container).getByText('a.jpg')).toHaveAttribute('data-struck', 'true')
  })

  it('carries exactly one state badge and no rating badge of the photo grid', () => {
    const { container } = renderTile({}, { ownStatus: 'album_worthy' })

    expect(container.querySelectorAll('[data-album-state]')).toHaveLength(1)
    expect(container.querySelector('[data-rating-status]')).toBeNull()
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
  it('offers "Alternativen" next to "Streichen", with the file name in its name', () => {
    renderTile()

    expect(screen.getByRole('button', { name: 'Alternativen: a.jpg' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Streichen: a.jpg' })).toBeInTheDocument()
  })

  it('is a disclosure that names the band it controls', async () => {
    const onToggleAlternatives = vi.fn()
    const user = userEvent.setup()
    renderTile({}, { onToggleAlternatives, alternativesExpanded: true })

    const trigger = screen.getByRole('button', { name: 'Alternativen: a.jpg' })
    expect(trigger).toHaveAttribute('aria-expanded', 'true')
    expect(trigger).toHaveAttribute('aria-controls', 'band-1')

    await user.click(trigger)
    expect(onToggleAlternatives).toHaveBeenCalledTimes(1)
  })

  it('is absent on a struck tile - its way back is "Wieder aufnehmen"', () => {
    renderTile({}, { ownStatus: 'rejected' })

    expect(screen.queryByRole('button', { name: /^Alternativen: / })).toBeNull()
  })

  it('keeps both hit areas at least 44px tall on the phone', () => {
    renderTile()

    for (const name of ['Streichen: a.jpg', 'Alternativen: a.jpg']) {
      expect(screen.getByRole('button', { name }).className).toContain('h-11')
    }
  })
})

describe('CurationPhotoTile: die Grossansicht (Spec 0531)', () => {
  it('opens the large view of exactly this photo from the image area, without deciding', () => {
    const onOpenLarge = vi.fn()
    const onDecide = vi.fn()
    renderTile({ id: 17, relative_path: '2024/07/IMG_0042.jpg' }, { onOpenLarge, onDecide })

    fireEvent.click(screen.getByRole('button', { name: 'Großansicht: 2024/07/IMG_0042.jpg' }))

    expect(onOpenLarge).toHaveBeenCalledTimes(1)
    expect(onOpenLarge).toHaveBeenCalledWith(17)
    expect(onDecide).not.toHaveBeenCalled()
  })

  it.each([/^Streichen: /, /^Alternativen: /])('does not open the large view from %s', (name) => {
    const onOpenLarge = vi.fn()
    renderTile({}, { onOpenLarge, ownStatus: 'album_worthy' })

    fireEvent.click(screen.getByRole('button', { name }))

    expect(onOpenLarge).not.toHaveBeenCalled()
  })

  it('makes the image trigger the first tabbable element and hands it out', async () => {
    const largeTriggerRef = vi.fn()
    renderTile({}, { largeTriggerRef })

    await userEvent.tab()

    const trigger = screen.getByRole('button', { name: 'Großansicht: a.jpg' })
    expect(trigger).toHaveFocus()
    expect(largeTriggerRef).toHaveBeenLastCalledWith(trigger)
  })
})
