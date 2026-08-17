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

  // Schlanker Integrations-Nachweis statt der vollen Content-Matrix (die lebt seit Spec 0041 in
  // CriterionDetailsList.test.tsx, specs/architecture/0002-testkonzept.md Punkt 8) - prueft nur,
  // dass Props korrekt an CriterionDetailsList durchgereicht werden: ein Kriterium, ein Ranking und
  // eine Suggestion gemeinsam sichtbar nach dem Oeffnen.
  it('opens the popover on click and passes criterionScores/ranking/suggestion through to CriterionDetailsList', async () => {
    const user = userEvent.setup()
    render(
      <CriterionDetailsPopover
        criterionScores={[criterionScore({ display_name: 'Schärfe', value: 0.734 })]}
        ranking={ranking({ category_key: 'landscape', rank_position: 2, partition_size: 5 })}
        suggestion={suggestion({ reason: 'duplicate', duplicate_of: 42, status: 'rejected' })}
      />
    )

    await user.click(screen.getByRole('button', { name: 'Bewertungsdetails anzeigen' }))

    const dialog = screen.getByRole('dialog')
    expect(within(dialog).getByText('Schärfe')).toBeInTheDocument()
    expect(within(dialog).getByText('73%')).toBeInTheDocument()
    expect(within(dialog).getByText('Landscape')).toBeInTheDocument()
    expect(within(dialog).getByText('Rang 2 von 5')).toBeInTheDocument()
    expect(within(dialog).getByText('Duplikat von Foto #42')).toBeInTheDocument()
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

  // Test-Review-Fund: die eigentliche Hover-vor-Klick-Falle war bisher ungetestet - jede
  // bestehende Klick-Assertion lief mit stubMatchMedia(false), der Ref-Pfad in
  // handleTriggerClick wurde also nie durchlaufen. Diese Sequenz deckt genau den Pfad ab, fuer
  // den justOpenedByHoverRef gebaut wurde.
  it('stays open through the click that immediately follows a hover-open, then closes on a genuinely separate click (matches: true)', async () => {
    stubMatchMedia(true)
    const user = userEvent.setup()
    render(
      <CriterionDetailsPopover
        criterionScores={[criterionScore()]}
        ranking={null}
        suggestion={null}
      />
    )
    const trigger = screen.getByRole('button', { name: 'Bewertungsdetails anzeigen' })

    // Ein echter Mausklick loest zuerst pointerenter (oeffnet per Hover), dann erst click aus -
    // userEvent.click() bildet genau diese Ereignisfolge nach.
    await user.click(trigger)
    expect(screen.getByRole('dialog')).toBeInTheDocument()

    // Ein zweiter, unabhaengiger Klick (Maus bleibt ueber dem Trigger, kein erneutes
    // pointerenter noetig) schliesst wie in Akzeptanzkriterium 4 gefordert ganz normal.
    await user.click(trigger)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  // Test-Review-Fund (echter Bug in einer frueheren Fassung): eine generische
  // "erste Schliessen-Anfrage nach Hover-Oeffnen schlucken"-Logik in onOpenChange haette hier
  // faelschlich auch Escape unmittelbar nach einem Hover-Oeffnen verschluckt - Akzeptanzkriterium
  // 4 verlangt aber, dass Escape zuverlaessig schliesst.
  it('closes on Escape immediately after a hover-open, without needing a second attempt (matches: true)', async () => {
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

    await user.keyboard('{Escape}')

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  // Derselbe Bug wie oben, hier fuer den Aussenklick-Schliessweg.
  it('closes on an outside click immediately after a hover-open (matches: true)', async () => {
    stubMatchMedia(true)
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

    await user.hover(screen.getByRole('button', { name: 'Bewertungsdetails anzeigen' }))
    expect(screen.getByRole('dialog')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Ausserhalb' }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  // Akzeptanzkriterium 15: Trigger per Tab erreichbar, Enter oeffnet.
  it('opens the popover via keyboard (Tab then Enter)', async () => {
    const user = userEvent.setup()
    render(
      <CriterionDetailsPopover
        criterionScores={[criterionScore()]}
        ranking={null}
        suggestion={null}
      />
    )

    await user.tab()
    expect(screen.getByRole('button', { name: 'Bewertungsdetails anzeigen' })).toHaveFocus()

    await user.keyboard('{Enter}')

    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  // Die volle Content-Matrix (Rundung, fehlendes Kriterium, Kategorie/Rang vorhanden/entfaellt,
  // Ausschuss-Gruppe vorhanden/entfaellt, dl/dt/dd-Semantik) lebt seit Spec 0041 in
  // CriterionDetailsList.test.tsx (specs/architecture/0002-testkonzept.md Punkt 8) - der obige
  // Integrationstest deckt die korrekte Durchreichung ab, keine Duplizierung hier.
})
