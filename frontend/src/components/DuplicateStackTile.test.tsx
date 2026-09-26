import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it, vi } from 'vitest'

import type { AusschussGroupEntry, PhotoOut } from '../api/types'
import { DuplicateStackTile } from './DuplicateStackTile'

vi.mock('./PhotoImage', () => ({
  PhotoImage: ({ alt, className }: { alt: string; className?: string }) => (
    <img alt={alt} className={className} />
  ),
}))

function photo(id: number): PhotoOut {
  return {
    id,
    relative_path: `Reise/serie-${id}.jpg`,
    taken_at: '2026-07-20T10:00:00',
    taken_at_original: '2026-07-20T10:00:00',
    time_offset_minutes: 0,
    camera: null,
    ratings: [],
    suggestion: null,
    ranking: null,
    criterion_scores: [],
    fine_labels: [],
    cloud_vision_status: [],
    final_selection_decision: null,
    in_final_selection: false,
    contested: false,
  }
}

function stack(overrides: Partial<AusschussGroupEntry> = {}): AusschussGroupEntry {
  return {
    kind: 'group',
    group_anchor_photo_id: 40,
    cover: photo(41),
    member_count: 5,
    group_size: 6,
    decision_counts: { undecided: 3, keep: 1, discard: 1 },
    ...overrides,
  }
}

function renderStack(entry: AusschussGroupEntry = stack()) {
  render(
    <MemoryRouter>
      <ul>
        <DuplicateStackTile projectId={7} entry={entry} width={200} height={150} />
      </ul>
    </MemoryRouter>,
  )
  return screen.getByRole('listitem')
}

describe('DuplicateStackTile - Form (B1/B2)', () => {
  it('traegt genau zwei hintere Rahmen ohne Bild vor der vorderen Karte', () => {
    const kachel = renderStack()

    const rahmen = Array.from(kachel.querySelectorAll('[aria-hidden="true"][data-stack-card]'))
    const bild = within(kachel).getByRole('img')
    expect(rahmen).toHaveLength(2)
    expect(within(kachel).getAllByRole('img')).toHaveLength(1)
    for (const karte of rahmen) {
      expect(karte.querySelector('img')).toBeNull()
      expect(karte.compareDocumentPosition(bild) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    }
  })

  it('behaelt Zeichen und Wort "Duplikat" am Bild', () => {
    const kachel = renderStack()

    const wort = within(kachel).getByText('Duplikat')
    expect(wort.querySelector('svg')).not.toBeNull()
  })

  it('traegt in keinem Teil ein data-dimmed', () => {
    const kachel = renderStack()

    expect(kachel.querySelectorAll('[data-dimmed]')).toHaveLength(0)
  })
})

describe('DuplicateStackTile - ein Link (B4)', () => {
  it('ist genau EIN fokussierbares Element', () => {
    // Gezaehlt, nicht ueber einen Namen gesucht: Eine Namensabfrage uebersaehe ein zweites Ziel.
    const kachel = renderStack()

    const fokussierbar = kachel.querySelectorAll('a[href], button, input, [tabindex]')
    expect(fokussierbar).toHaveLength(1)
    expect(fokussierbar[0]?.tagName).toBe('A')
  })

  it('nennt Serie, Zusammenfassung und Titelbild im zugaenglichen Namen', () => {
    renderStack()

    const link = screen.getByRole('link')
    expect(link.getAttribute('aria-label')).toBe(
      'Duplikat-Gruppe mit 6 Aufnahmen vergleichen (3 vorgeschlagen, 1 Ausschuss, 1 behalten): ' +
        'Reise/serie-41.jpg',
    )
    expect(link.getAttribute('aria-label')).not.toMatch(/^Duplikate vergleichen[:\s—]/)
  })

  it('fuehrt in die Vergleichsansicht am Anker, mit Rueckweg in den Ausschuss', () => {
    renderStack()

    expect(screen.getByRole('link').getAttribute('href')).toBe(
      '/projects/7/photos/40/duplicates?from=ausschuss',
    )
  })
})

describe('DuplicateStackTile - Zahlen (B7)', () => {
  it('zeigt die ganze Serie, nicht nur die Ausschuss-Aufnahmen', () => {
    const kachel = renderStack(stack({ member_count: 2, group_size: 6 }))

    expect(within(kachel).getByText('6 Aufnahmen')).toBeTruthy()
    expect(within(kachel).queryByText('2 Aufnahmen')).toBeNull()
  })

  it.each<[AusschussGroupEntry['decision_counts'], string[]]>([
    [{ undecided: 3, keep: 1, discard: 1 }, ['3 vorgeschlagen', '1 Ausschuss', '1 behalten']],
    [{ undecided: 0, keep: 2, discard: 0 }, ['2 behalten']],
    [{ undecided: 4, keep: 0, discard: 2 }, ['4 vorgeschlagen', '2 Ausschuss']],
  ])('nennt nur Teile ungleich null, in fester Reihenfolge', (zaehlung, erwartet) => {
    const kachel = renderStack(stack({ decision_counts: zaehlung }))

    const teile = Array.from(kachel.querySelectorAll('[data-stack-summary]')).map(
      (teil) => teil.textContent,
    )
    expect(teile).toEqual(erwartet)
  })
})
