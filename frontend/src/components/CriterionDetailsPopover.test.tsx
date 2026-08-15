import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { CriterionScoreOut, RankingOut, SuggestionOut } from '../api/types'
import { CriterionDetailsPopover } from './CriterionDetailsPopover'

// window.matchMedia existiert in jsdom nicht (specs/architecture/0002-testkonzept.md, Sektion
// "Radix Popover mit geraetespezifischem Hover-Verhalten") - minimaler MediaQueryList-Stub statt
// eines globalen Default in setupTests.ts, da unterschiedliche Tests bewusst unterschiedliche
// matches-Werte brauchen. Radix fragt `matches` nur einmalig bei Interaktion ab (kein Listener),
// deshalb reicht ein simpler Stub ohne funktionierendes addEventListener.
function stubMatchMedia(matches: boolean): void {
  vi.stubGlobal(
    'matchMedia',
    vi.fn().mockReturnValue({
      matches,
      media: '(hover: hover) and (pointer: fine)',
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })
  )
}

function criterionScore(overrides: Partial<CriterionScoreOut> = {}): CriterionScoreOut {
  return {
    criterion_key: 'sharpness',
    display_name: 'Schärfe',
    value: 0.734,
    source: 'local_heuristic',
    ...overrides,
  }
}

function ranking(overrides: Partial<RankingOut> = {}): RankingOut {
  return {
    cluster_key: 'cluster-0',
    category_key: 'landscape',
    rank_score: 0.8,
    rank_position: 2,
    partition_size: 5,
    ...overrides,
  }
}

function suggestion(overrides: Partial<SuggestionOut> = {}): SuggestionOut {
  return {
    status: 'rejected',
    reason: 'low_quality',
    duplicate_of: null,
    sharpness: 1.0,
    exposure: 0.2,
    cluster_key: null,
    computed_at: '2026-07-20T10:00:00Z',
    ...overrides,
  }
}

describe('CriterionDetailsPopover', () => {
  beforeEach(() => {
    // Standardmaessig Touch-Emulation (kein Fine-Pointer) - Klick-Tests bleiben davon unberuehrt
    // (Akzeptanzkriterium 6/Testkonzept-Punkt 3: Klick funktioniert geraeteunabhaengig, auch
    // wenn userEvent.click() inzident Pointer-/Maus-Hover-Events ausloest).
    stubMatchMedia(false)
  })

  // Akzeptanzkriterium 1: kein Icon/Popover im DOM, wenn criterion_scores leer ist.
  it('renders nothing when criterionScores is empty', () => {
    render(
      <CriterionDetailsPopover criterionScores={[]} ranking={null} suggestion={null} />
    )

    expect(
      screen.queryByRole('button', { name: 'Bewertungsdetails anzeigen' })
    ).not.toBeInTheDocument()
  })

  it('renders the trigger with the accessible label and no open popover initially', () => {
    render(
      <CriterionDetailsPopover
        criterionScores={[criterionScore()]}
        ranking={null}
        suggestion={null}
      />
    )

    expect(screen.getByRole('button', { name: 'Bewertungsdetails anzeigen' })).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('opens the popover on click, showing criteria as rounded percentages in the given order', async () => {
    const user = userEvent.setup()
    render(
      <CriterionDetailsPopover
        criterionScores={[
          criterionScore({ criterion_key: 'sharpness', display_name: 'Schärfe', value: 0.734 }),
          criterionScore({
            criterion_key: 'exposure',
            display_name: 'Belichtung',
            value: 0.2,
          }),
        ]}
        ranking={null}
        suggestion={null}
      />
    )

    await user.click(screen.getByRole('button', { name: 'Bewertungsdetails anzeigen' }))

    const dialog = screen.getByRole('dialog')
    const dtTexts = within(dialog).getAllByText(/Schärfe|Belichtung/).map((el) => el.textContent)
    expect(dtTexts).toEqual(['Schärfe', 'Belichtung'])
    expect(within(dialog).getByText('73%')).toBeInTheDocument()
    expect(within(dialog).getByText('20%')).toBeInTheDocument()
  })

  it('closes the popover on a second click of the trigger', async () => {
    const user = userEvent.setup()
    render(
      <CriterionDetailsPopover
        criterionScores={[criterionScore()]}
        ranking={null}
        suggestion={null}
      />
    )
    const trigger = screen.getByRole('button', { name: 'Bewertungsdetails anzeigen' })

    await user.click(trigger)
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    await user.click(trigger)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('closes the popover via the header close button', async () => {
    const user = userEvent.setup()
    render(
      <CriterionDetailsPopover
        criterionScores={[criterionScore()]}
        ranking={null}
        suggestion={null}
      />
    )

    await user.click(screen.getByRole('button', { name: 'Bewertungsdetails anzeigen' }))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Schließen' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('closes the popover on Escape', async () => {
    const user = userEvent.setup()
    render(
      <CriterionDetailsPopover
        criterionScores={[criterionScore()]}
        ranking={null}
        suggestion={null}
      />
    )

    await user.click(screen.getByRole('button', { name: 'Bewertungsdetails anzeigen' }))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('closes the popover on an outside click', async () => {
    const user = userEvent.setup()
    render(
      <div>
        <CriterionDetailsPopover
          criterionScores={[criterionScore()]}
          ranking={null}
          suggestion={null}
        />
        <button type="button">Ausserhalb</button>
      </div>
    )

    await user.click(screen.getByRole('button', { name: 'Bewertungsdetails anzeigen' }))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Ausserhalb' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  // Akzeptanzkriterium 5: Hover oeffnet zusaetzlich, wenn matchMedia(...).matches === true.
  it('opens the popover on hover when the device reports a fine pointer with hover support', async () => {
    stubMatchMedia(true)
    const user = userEvent.setup()
    render(
      <CriterionDetailsPopover
        criterionScores={[criterionScore()]}
        ranking={null}
        suggestion={null}
      />
    )

    await user.hover(screen.getByRole('button', { name: 'Bewertungsdetails anzeigen' }))

    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  // Akzeptanzkriterium 6: bei matches === false hat Hover keine Wirkung.
  it('does not open the popover on hover when the device has no fine pointer/hover support', async () => {
    stubMatchMedia(false)
    const user = userEvent.setup()
    render(
      <CriterionDetailsPopover
        criterionScores={[criterionScore()]}
        ranking={null}
        suggestion={null}
      />
    )

    await user.hover(screen.getByRole('button', { name: 'Bewertungsdetails anzeigen' }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  // Testkonzept-Punkt 3: Klick funktioniert unabhaengig vom matchMedia-Zustand - Regressionsschutz
  // gegen eine Implementierung, die Klick faelschlich nur im Touch-Zweig verdrahtet.
  it('opens the popover on click regardless of hover capability (matches: true)', async () => {
    stubMatchMedia(true)
    const user = userEvent.setup()
    render(
      <CriterionDetailsPopover
        criterionScores={[criterionScore()]}
        ranking={null}
        suggestion={null}
      />
    )

    await user.click(screen.getByRole('button', { name: 'Bewertungsdetails anzeigen' }))

    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('does not fill a missing criterion with a placeholder, only renders what is given', async () => {
    const user = userEvent.setup()
    render(
      <CriterionDetailsPopover
        criterionScores={[criterionScore({ criterion_key: 'sharpness', display_name: 'Schärfe' })]}
        ranking={null}
        suggestion={null}
      />
    )

    await user.click(screen.getByRole('button', { name: 'Bewertungsdetails anzeigen' }))

    expect(screen.queryByText('Belichtung')).not.toBeInTheDocument()
  })

  // Akzeptanzkriterium 10: Kategorie/Rang-Gruppe bei vorhandenem ranking.
  it('shows category and rank when ranking is not null', async () => {
    const user = userEvent.setup()
    render(
      <CriterionDetailsPopover
        criterionScores={[criterionScore()]}
        ranking={ranking({ category_key: 'landscape', rank_position: 2, partition_size: 5 })}
        suggestion={null}
      />
    )

    await user.click(screen.getByRole('button', { name: 'Bewertungsdetails anzeigen' }))

    expect(screen.getByText('Landscape')).toBeInTheDocument()
    expect(screen.getByText('Rang 2 von 5')).toBeInTheDocument()
  })

  // Akzeptanzkriterium 11: Kategorie/Rang-Gruppe entfaellt vollstaendig ohne ranking.
  it('omits the category/rank group entirely when ranking is null', async () => {
    const user = userEvent.setup()
    render(
      <CriterionDetailsPopover
        criterionScores={[criterionScore()]}
        ranking={null}
        suggestion={null}
      />
    )

    await user.click(screen.getByRole('button', { name: 'Bewertungsdetails anzeigen' }))

    expect(screen.queryByText(/^Rang /)).not.toBeInTheDocument()
  })

  // Akzeptanzkriterium 12: Ausschuss-Gruppe bei vorhandenem suggestion, ueber suggestionLabels.ts.
  it('shows the suggestion reason when suggestion is not null', async () => {
    const user = userEvent.setup()
    render(
      <CriterionDetailsPopover
        criterionScores={[criterionScore()]}
        ranking={null}
        suggestion={suggestion({ reason: 'duplicate', duplicate_of: 42, status: 'rejected' })}
      />
    )

    await user.click(screen.getByRole('button', { name: 'Bewertungsdetails anzeigen' }))

    expect(screen.getByText('Verworfen')).toBeInTheDocument()
    expect(screen.getByText('Duplikat von Foto #42')).toBeInTheDocument()
  })

  // Akzeptanzkriterium 13: Ausschuss-Gruppe entfaellt vollstaendig ohne suggestion.
  it('omits the suggestion group entirely when suggestion is null', async () => {
    const user = userEvent.setup()
    render(
      <CriterionDetailsPopover
        criterionScores={[criterionScore()]}
        ranking={null}
        suggestion={null}
      />
    )

    await user.click(screen.getByRole('button', { name: 'Bewertungsdetails anzeigen' }))

    expect(screen.queryByText('Duplikat von Foto #42')).not.toBeInTheDocument()
    expect(screen.queryByText('Geringe Bildqualität')).not.toBeInTheDocument()
  })

  // Akzeptanzkriterium 16: dl/dt/dd-Semantik.
  it('renders the criteria group using dl/dt/dd semantics', async () => {
    const user = userEvent.setup()
    render(
      <CriterionDetailsPopover
        criterionScores={[criterionScore()]}
        ranking={null}
        suggestion={null}
      />
    )

    await user.click(screen.getByRole('button', { name: 'Bewertungsdetails anzeigen' }))

    const dialog = screen.getByRole('dialog')
    expect(dialog.querySelector('dl')).not.toBeNull()
    expect(dialog.querySelector('dt')).not.toBeNull()
    expect(dialog.querySelector('dd')).not.toBeNull()
  })
})
