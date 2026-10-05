import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { NOT_PROPOSED_BADGE_TEXT } from '../utils/albumDraft'
import { ALBUM_STATE_LABELS } from '../utils/albumStateLabels'
import type { AlbumState } from '../utils/albumStateLabels'
import { AlbumStateBadge } from './AlbumStateBadge'

function icons(element: HTMLElement): string[] {
  return [...element.querySelectorAll('[data-icon]')].map((icon) => icon.getAttribute('data-icon')!)
}

describe('AlbumStateBadge: Zustand nur aus Symbolen', () => {
  it.each<[AlbumState, string[]]>([
    ['proposal', ['cog', 'book']],
    ['taken', ['book']],
    ['struck', ['x-circle']],
  ])('%s is an image named by its word, showing %j and no visible text', (state, expected) => {
    render(<AlbumStateBadge state={state} />)

    const badge = screen.getByRole('img', { name: ALBUM_STATE_LABELS[state] })
    expect(badge).toHaveAttribute('data-album-state', state)
    expect(icons(badge)).toEqual(expected)
    expect(badge.textContent).toBe('')
    expect(badge).not.toHaveAttribute('title')
  })

  it('names a taken photo the run did not propose', () => {
    render(<AlbumStateBadge state="taken" notProposed />)

    expect(
      screen.getByRole('img', {
        name: `${ALBUM_STATE_LABELS.taken}, ${NOT_PROPOSED_BADGE_TEXT}`,
      }),
    ).toBeInTheDocument()
  })

  it('keeps the three states apart without colour, by number and form of symbols', () => {
    const signatures = (['proposal', 'taken', 'struck'] as const).map((state) => {
      const { unmount } = render(<AlbumStateBadge state={state} />)
      const signature = icons(screen.getByRole('img')).join('+')
      unmount()
      return signature
    })

    expect(new Set(signatures).size).toBe(3)
  })
})
