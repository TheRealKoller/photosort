import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { CriterionScoreOut, RankingOut, SuggestionOut } from '../api/types'
import { CriterionDetailsList } from './CriterionDetailsList'

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

// Reine Praesentationskomponente, migriert aus CriterionDetailsPopover.test.tsx
// (specs/features/0041-bewertungsdetails-permanent-in-detailansicht-hover-auto-close.md,
// Testkonzept-Ergaenzung Punkt 8) - kein QueryClientProvider/Router noetig.
describe('CriterionDetailsList', () => {
  it('renders criteria as rounded percentages in the given order', () => {
    render(
      <CriterionDetailsList
        criterionScores={[
          criterionScore({ criterion_key: 'sharpness', display_name: 'Schärfe', value: 0.734 }),
          criterionScore({ criterion_key: 'exposure', display_name: 'Belichtung', value: 0.2 }),
        ]}
        ranking={null}
        suggestion={null}
        showSuggestion={true}
      />
    )

    const dtTexts = screen.getAllByText(/Schärfe|Belichtung/).map((el) => el.textContent)
    expect(dtTexts).toEqual(['Schärfe', 'Belichtung'])
    expect(screen.getByText('73%')).toBeInTheDocument()
    expect(screen.getByText('20%')).toBeInTheDocument()
  })

  // Akzeptanzkriterium 9 (Spec 0040): kaufmaennische Rundung auch am .5-Grenzfall.
  it('rounds a .5 percentage point boundary up (commercial rounding)', () => {
    render(
      <CriterionDetailsList
        criterionScores={[criterionScore({ value: 0.005 })]}
        ranking={null}
        suggestion={null}
        showSuggestion={true}
      />
    )

    expect(screen.getByText('1%')).toBeInTheDocument()
  })

  it('does not fill a missing criterion with a placeholder, only renders what is given', () => {
    render(
      <CriterionDetailsList
        criterionScores={[criterionScore({ criterion_key: 'sharpness', display_name: 'Schärfe' })]}
        ranking={null}
        suggestion={null}
        showSuggestion={true}
      />
    )

    expect(screen.queryByText('Belichtung')).not.toBeInTheDocument()
  })

  // Akzeptanzkriterium 10 (Spec 0040): Kategorie/Rang-Gruppe bei vorhandenem ranking.
  it('shows category and rank when ranking is not null', () => {
    render(
      <CriterionDetailsList
        criterionScores={[criterionScore()]}
        ranking={ranking({ category_key: 'landscape', rank_position: 2, partition_size: 5 })}
        suggestion={null}
        showSuggestion={true}
      />
    )

    expect(screen.getByText('Landscape')).toBeInTheDocument()
    expect(screen.getByText('Rang 2 von 5')).toBeInTheDocument()
  })

  // Akzeptanzkriterium 11 (Spec 0040): Kategorie/Rang-Gruppe entfaellt vollstaendig ohne ranking.
  it('omits the category/rank group entirely when ranking is null', () => {
    render(
      <CriterionDetailsList
        criterionScores={[criterionScore()]}
        ranking={null}
        suggestion={null}
        showSuggestion={true}
      />
    )

    expect(screen.queryByText(/^Rang /)).not.toBeInTheDocument()
  })

  // Akzeptanzkriterium 12 (Spec 0040): Ausschuss-Gruppe bei vorhandenem suggestion + showSuggestion.
  it('shows the suggestion reason when suggestion is not null and showSuggestion is true', () => {
    render(
      <CriterionDetailsList
        criterionScores={[criterionScore()]}
        ranking={null}
        suggestion={suggestion({ reason: 'duplicate', duplicate_of: 42, status: 'rejected' })}
        showSuggestion={true}
      />
    )

    expect(screen.getByText('Verworfen')).toBeInTheDocument()
    expect(screen.getByText('Duplikat von Foto #42')).toBeInTheDocument()
  })

  // Akzeptanzkriterium 13 (Spec 0040): Ausschuss-Gruppe entfaellt vollstaendig ohne suggestion.
  it('omits the suggestion group entirely when suggestion is null', () => {
    render(
      <CriterionDetailsList
        criterionScores={[criterionScore()]}
        ranking={null}
        suggestion={null}
        showSuggestion={true}
      />
    )

    expect(screen.queryByText('Duplikat von Foto #42')).not.toBeInTheDocument()
    expect(screen.queryByText('Geringe Bildqualität')).not.toBeInTheDocument()
  })

  // Akzeptanzkriterium 6 (Spec 0041): showSuggestion=false unterdrueckt die Ausschuss-Gruppe auch
  // dann, wenn eine nicht-null suggestion uebergeben wird - defensiver Test gegen die Prop-Logik
  // selbst (specs/architecture/0002-testkonzept.md, Testkonzept-Ergaenzung Punkt 8).
  it('suppresses the suggestion group when showSuggestion is false, even with a non-null suggestion', () => {
    render(
      <CriterionDetailsList
        criterionScores={[criterionScore()]}
        ranking={null}
        suggestion={suggestion({ reason: 'duplicate', duplicate_of: 42, status: 'rejected' })}
        showSuggestion={false}
      />
    )

    expect(screen.queryByText('Duplikat von Foto #42')).not.toBeInTheDocument()
    expect(screen.queryByText('Ausschuss-Vorschlag')).not.toBeInTheDocument()
  })

  // Akzeptanzkriterium 16 (Spec 0040): dl/dt/dd-Semantik.
  it('renders the criteria group using dl/dt/dd semantics', () => {
    const { container } = render(
      <CriterionDetailsList
        criterionScores={[criterionScore()]}
        ranking={null}
        suggestion={null}
        showSuggestion={true}
      />
    )

    expect(container.querySelector('dl')).not.toBeNull()
    expect(container.querySelector('dt')).not.toBeNull()
    expect(container.querySelector('dd')).not.toBeNull()
  })
})
