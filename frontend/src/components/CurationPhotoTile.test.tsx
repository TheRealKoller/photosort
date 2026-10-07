import { act, fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { PhotoOut, RankingOut, RatingStatus } from '../api/types'
import { LONG_PRESS_MS } from '../hooks/useRevealOnDemand'
import { stubFocusVisible } from '../test/focusVisible'
import { MOTIF_SET } from '../test/motifSetFixture'
import { NOT_PROPOSED_BADGE_TEXT } from '../utils/albumDraft'
import { ALBUM_STATE_LABELS } from '../utils/albumStateLabels'
import { ALBUM_SUITABILITY_NOT_RATED_TEXT, REASON_ATTRIBUTION } from '../utils/albumSuitability'
import { HANDLES_FULL_WIDTH_PX } from '../utils/curationLayout'
import { CurationPhotoTile } from './CurationPhotoTile'

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
    motif_assessment: null,
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
    width?: number
  } = {},
) {
  return render(
    <ul>
      <CurationPhotoTile
        photo={photo(overrides)}
        width={tile.width ?? 300}
        imageHeight={200}
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
      />
    </ul>,
  )
}

function details(container: HTMLElement): HTMLElement {
  const found = container.querySelector<HTMLElement>('[data-tile-details]')
  if (found === null) {
    throw new Error('keine Leiste')
  }
  return found
}

function icons(element: Element): string[] {
  return [...element.querySelectorAll('[data-icon]')].map((icon) => icon.getAttribute('data-icon')!)
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.useRealTimers()
})

describe('CurationPhotoTile: die Albumtauglichkeit in der Leiste', () => {
  it('shows the coarse level label for a rated photo', () => {
    const { container } = renderTile({ ranking: ranking({ rank_score: 0.8 }) })

    expect(within(details(container)).getByText('Gut albumtauglich')).toBeInTheDocument()
  })

  it('shows the exact level nowhere on the tile', () => {
    renderTile({ album_suitability: { level: 4, reason: null } })

    expect(screen.queryByText('Stufe 4 von 5')).toBeNull()
  })

  it('says "Noch nicht bewertet" for a photo without a quality score', () => {
    renderTile({ ranking: ranking({ rank_score: null, rank_position: null }) })

    expect(screen.getByText(ALBUM_SUITABILITY_NOT_RATED_TEXT)).toBeInTheDocument()
  })

  it('keeps a quality score of 0 as a real level instead of "not rated"', () => {
    renderTile({ ranking: ranking({ rank_score: 0 }) })

    expect(screen.getByText('Wenig albumtauglich')).toBeInTheDocument()
    expect(screen.queryByText(ALBUM_SUITABILITY_NOT_RATED_TEXT)).toBeNull()
  })
})

describe('CurationPhotoTile: die Begründung', () => {
  const LONG_REASON =
    'Die Person ist am linken Bildrand angeschnitten, der Hintergrund ist unruhig, das Licht ' +
    'kommt hart von oben, und der Bildaufbau wirkt dadurch eher zufällig als bewusst gewählt.'

  it('keeps a reason of 160 characters complete, unclamped, even in a 100 px tile', () => {
    const reason = LONG_REASON.slice(0, 160)
    expect(reason).toHaveLength(160)

    const { container } = renderTile({ album_suitability: { level: 2, reason } }, { width: 100 })

    const carrier = container.querySelector('[data-album-suitability-reason]')
    expect(carrier?.lastChild?.textContent).toBe(reason)
    expect(carrier?.className ?? '').not.toMatch(/line-clamp|truncate/)
    for (const element of details(container).querySelectorAll('*')) {
      expect(element.className).not.toMatch(/line-clamp|truncate/)
    }
  })

  it('puts the reason first in the strip, before suitability and file name', () => {
    const { container } = renderTile()

    const strip = details(container)
    const carrier = strip.querySelector('[data-album-suitability-reason]')
    expect(strip.firstElementChild).toBe(carrier)
    expect(strip.lastElementChild).toHaveTextContent('a.jpg')
  })

  it('attributes the reason to the model inside its carrier', () => {
    const { container } = renderTile()

    const carrier = container.querySelector<HTMLElement>('[data-album-suitability-reason]')
    expect(carrier).toHaveTextContent(
      new RegExp(`${REASON_ATTRIBUTION}.*Alle schauen in die Kamera\\.`),
    )
  })

  it('the reason carrier is no alert', () => {
    const { container } = renderTile()

    const carrier = container.querySelector<HTMLElement>('[data-album-suitability-reason]')!
    expect(carrier.closest('[role="alert"], [role="status"]')).toBeNull()
    expect(carrier.querySelector('[role="alert"], [role="status"]')).toBeNull()
    expect(carrier.querySelector('[data-icon], [data-badge-tone]')).toBeNull()
  })

  it.each([null, ''])('renders no line at all for the reason %j', (reason) => {
    const { container } = renderTile({ album_suitability: { level: 3, reason } })

    expect(container.querySelectorAll('[data-album-suitability-reason]')).toHaveLength(0)
    const strip = details(container)
    expect(strip.firstElementChild?.textContent).not.toBe('')
    for (const element of strip.querySelectorAll('*')) {
      if (element.children.length === 0 && element.tagName !== 'svg') {
        expect(element.textContent, element.outerHTML).not.toBe('')
      }
    }
  })

  it('renders no carrier at all when the photo has no verdict', () => {
    const { container } = renderTile({ album_suitability: null })

    expect(container.querySelectorAll('[data-album-suitability-reason]')).toHaveLength(0)
  })

  it('never renders the reason as markup', () => {
    const payload = '<img src=x onerror="alert(1)">'

    const { container } = renderTile({ album_suitability: { level: 1, reason: payload } })

    expect(container.querySelector('img:not([alt="a.jpg"])')).toBeNull()
    expect(container.querySelector('img[src="x"]')).toBeNull()
    expect(screen.getByText(payload)).toBeInTheDocument()
  })

  it.each(['javascript:alert(1)', '<a href="https://evil.example">Anmelden</a>'])(
    'never turns %s into a link',
    (payload) => {
      const { container } = renderTile({ album_suitability: { level: 1, reason: payload } })

      expect(container.querySelector('a')).toBeNull()
      expect(container.querySelector('img[src="x"]')).toBeNull()
      expect(screen.getByText(payload)).toBeInTheDocument()
    },
  )

  it('the reason never reaches an attribute', () => {
    const payload = 'Nutzlast-7f3a <img src=x>'
    const { container } = renderTile({ album_suitability: { level: 1, reason: payload } })

    for (const element of container.querySelectorAll('*')) {
      for (const attribute of element.attributes) {
        expect(attribute.value, `${element.tagName}[${attribute.name}]`).not.toContain(
          'Nutzlast-7f3a',
        )
      }
    }
  })

  it('a hostile file name stays text', () => {
    const hostile = '<img src=x onerror="window.__pwned = true">.jpg'
    const { container } = renderTile({ relative_path: `2024/${hostile}` })

    for (const image of container.querySelectorAll('img')) {
      expect(image).toHaveAttribute('alt', `2024/${hostile}`)
    }
    expect(container.querySelector('img[src="x"]')).toBeNull()
    expect(screen.getByRole('button', { name: `Streichen: 2024/${hostile}` })).toBeInTheDocument()
    expect(within(details(container)).getByText(hostile)).toBeInTheDocument()
  })

  it('inline styles carry only numeric pixel values', () => {
    const { container } = renderTile({ aspect_ratio: '1;background:url(x)' as unknown as number })

    for (const element of container.querySelectorAll<HTMLElement>('[style]')) {
      for (const property of [...element.style]) {
        const value = element.style.getPropertyValue(property)
        expect(value).toMatch(/^\d+(\.\d+)?px$/)
        expect(value).not.toContain('url(')
        expect(value).not.toContain('var(')
      }
    }
  })
})

describe('CurationPhotoTile: die Leiste bei Bedarf', () => {
  it('is in the DOM at rest, screen-reader only', () => {
    const { container } = renderTile()

    expect(details(container)).toHaveClass('sr-only')
  })

  it.each([/^Großansicht: /, /^Streichen: /, /^Alternativen: /])(
    'shows while %s has keyboard focus',
    (name) => {
      stubFocusVisible(true)
      const { container } = renderTile()

      act(() => screen.getByRole('button', { name }).focus())

      expect(details(container)).toHaveAttribute('data-visible', 'true')
    },
  )

  it('carries no info trigger and no motif marker', () => {
    const { container } = renderTile({ motif_assessment: null })

    const tile = within(screen.getByRole('listitem'))
    expect(tile.queryByRole('button', { name: /Bewertungsdetails/ })).toBeNull()
    expect(container.querySelector('[data-motif-marker], [data-icon="info"]')).toBeNull()
    expect(container.querySelector('[data-rating-status]')).toBeNull()
  })
})

describe('CurationPhotoTile: die Handgriffe', () => {
  it('offers "Streichen" (x-circle) and "Alternativen" (repeat) side by side', () => {
    renderTile()

    const strike = screen.getByRole('button', { name: 'Streichen: a.jpg' })
    const alternatives = screen.getByRole('button', { name: 'Alternativen: a.jpg' })
    expect(icons(strike)).toEqual(['x-circle'])
    expect(icons(alternatives)).toEqual(['repeat'])
    expect(strike.parentElement).toBe(alternatives.parentElement)
    expect(strike).not.toHaveAttribute('aria-pressed')
  })

  it.each([
    [HANDLES_FULL_WIDTH_PX.draft - 1, true],
    [HANDLES_FULL_WIDTH_PX.draft, false],
  ])('at %s px shows symbols only: %s, for both buttons alike', (width, iconOnly) => {
    renderTile({}, { width })

    for (const name of ['Streichen: a.jpg', 'Alternativen: a.jpg']) {
      const button = screen.getByRole('button', { name })
      expect(button.querySelector('[data-tile-action-hint]') !== null, name).toBe(iconOnly)
    }
  })

  it('says "Wieder aufnehmen" (book) as the only button on a struck tile', () => {
    renderTile({}, { ownStatus: 'rejected' })

    const tile = within(screen.getByRole('listitem'))
    const buttons = tile
      .getAllByRole('button')
      .filter((button) => !/^Großansicht/.test(button.getAttribute('aria-label') ?? ''))
    expect(buttons).toHaveLength(1)
    expect(buttons[0]).toHaveAccessibleName('Wieder aufnehmen: a.jpg')
    expect(icons(buttons[0])).toEqual(['book'])
  })

  it('switches the struck tile by its own threshold', () => {
    renderTile({}, { ownStatus: 'rejected', width: HANDLES_FULL_WIDTH_PX.struck })

    expect(
      screen
        .getByRole('button', { name: 'Wieder aufnehmen: a.jpg' })
        .querySelector('[data-tile-action-hint]'),
    ).toBeNull()
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

  it('anchors the tile whose band is open', () => {
    renderTile({}, { alternativesExpanded: true })

    expect(screen.getByRole('listitem')).toHaveAttribute('data-anchored', 'true')
  })
})

describe('CurationPhotoTile: das Zustandszeichen', () => {
  it.each<[RatingStatus | null, string, string[]]>([
    [null, ALBUM_STATE_LABELS.proposal, ['cog', 'book']],
    ['album_worthy', ALBUM_STATE_LABELS.taken, ['book']],
    ['rejected', ALBUM_STATE_LABELS.struck, ['x-circle']],
  ])('own status %s is the symbol mark "%s"', (ownStatus, name, expected) => {
    renderTile({}, { ownStatus })

    expect(icons(screen.getByRole('img', { name }))).toEqual(expected)
  })

  it('strikes the file name of a struck photo', () => {
    const { container } = renderTile({}, { ownStatus: 'rejected' })

    expect(within(details(container)).getByText('a.jpg')).toHaveAttribute('data-struck', 'true')
  })

  it.each([{ ranking: null }, { ranking: ranking({ proposed: false }) }])(
    'names a taken photo the run did not propose in mark and strip (%j)',
    (overrides) => {
      const { container } = renderTile(overrides, { ownStatus: 'album_worthy' })

      expect(
        screen.getByRole('img', {
          name: `${ALBUM_STATE_LABELS.taken}, ${NOT_PROPOSED_BADGE_TEXT}`,
        }),
      ).toBeInTheDocument()
      expect(details(container)).toHaveTextContent(`· ${NOT_PROPOSED_BADGE_TEXT}`)
    },
  )

  it('marks nothing on a photo the run proposes', () => {
    renderTile({ ranking: ranking({ proposed: true }) }, { ownStatus: 'album_worthy' })

    expect(screen.queryByText(new RegExp(NOT_PROPOSED_BADGE_TEXT))).toBeNull()
  })
})

describe('CurationPhotoTile: die Grossansicht', () => {
  it('opens the large view of exactly this photo from the image area, without deciding', () => {
    const onOpenLarge = vi.fn()
    const onDecide = vi.fn()
    renderTile({ id: 17, relative_path: '2024/07/IMG_0042.jpg' }, { onOpenLarge, onDecide })

    fireEvent.click(screen.getByRole('button', { name: 'Großansicht: 2024/07/IMG_0042.jpg' }))

    expect(onOpenLarge).toHaveBeenCalledWith(17)
    expect(onDecide).not.toHaveBeenCalled()
  })

  it.each([/^Streichen: /, /^Alternativen: /])('does not open the large view from %s', (name) => {
    const onOpenLarge = vi.fn()
    renderTile({}, { onOpenLarge, ownStatus: 'album_worthy' })

    fireEvent.click(screen.getByRole('button', { name }))

    expect(onOpenLarge).not.toHaveBeenCalled()
  })

  it('does not open the large view after a long touch press', () => {
    const onOpenLarge = vi.fn()
    const { container } = renderTile({}, { onOpenLarge })
    const trigger = screen.getByRole('button', { name: /^Großansicht: / })

    vi.useFakeTimers()
    act(() => {
      fireEvent.pointerDown(trigger, { pointerType: 'touch' })
    })
    act(() => {
      vi.advanceTimersByTime(LONG_PRESS_MS)
    })
    fireEvent.click(trigger)

    expect(onOpenLarge).not.toHaveBeenCalled()
    expect(details(container)).toHaveAttribute('data-visible', 'true')
  })

  /*
   * Spec 0585 AK1/AK7: Die Grossansicht gibt den Fokus beim Schliessen an den Bildausloeser
   * zurueck. Nach einem Tippen ist dieser Fokus kein Tastaturfokus (`:focus-visible` = false) -
   * die Leiste bleibt verborgen; nach Tastaturbedienung ist er es - die Leiste erscheint.
   */
  it.each([
    { focusVisible: false, visible: false },
    { focusVisible: true, visible: true },
  ])(
    'after opening and the focus coming back (focus-visible $focusVisible) the strip is visible: $visible',
    ({ focusVisible, visible }) => {
      stubFocusVisible(focusVisible)
      const onOpenLarge = vi.fn()
      const { container } = renderTile({ id: 17 }, { onOpenLarge })
      const trigger = screen.getByRole('button', { name: /^Großansicht: / })

      fireEvent.pointerDown(trigger, { pointerType: 'touch' })
      fireEvent.pointerUp(trigger, { pointerType: 'touch' })
      fireEvent.click(trigger)
      expect(onOpenLarge).toHaveBeenCalledWith(17)

      act(() => trigger.blur())
      act(() => trigger.focus())

      expect(trigger).toHaveFocus()
      if (visible) {
        expect(details(container)).toHaveAttribute('data-visible', 'true')
      } else {
        expect(details(container)).not.toHaveAttribute('data-visible')
      }
    },
  )

  it('runs exactly the tapped strike and keeps the strip hidden while the button stays focused', () => {
    stubFocusVisible(false)
    const onDecide = vi.fn()
    const onOpenLarge = vi.fn()
    const { container } = renderTile({}, { onDecide, onOpenLarge, ownStatus: 'album_worthy' })
    const strike = screen.getByRole('button', { name: /^Streichen: / })

    fireEvent.pointerDown(strike, { pointerType: 'touch' })
    act(() => strike.focus())
    fireEvent.pointerUp(strike, { pointerType: 'touch' })
    fireEvent.click(strike)

    expect(onDecide).toHaveBeenCalledTimes(1)
    expect(onOpenLarge).not.toHaveBeenCalled()
    expect(strike).toHaveFocus()
    expect(details(container)).not.toHaveAttribute('data-visible')
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
