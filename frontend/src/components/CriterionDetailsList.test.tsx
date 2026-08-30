import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { CategoryCandidateOut, CriterionScoreOut, RankingOut, SuggestionOut } from '../api/types'
import { CriterionDetailsList } from './CriterionDetailsList'

function criterionScore(overrides: Partial<CriterionScoreOut> = {}): CriterionScoreOut {
  return {
    criterion_key: 'sharpness',
    display_name: 'Schärfe',
    value: 0.734,
    source: 'local_heuristic',
    // Default-Key ist `sharpness` (nicht kategoriefaehig) - der Default muss dazu passen,
    // damit kein Bestandstest unbemerkt in den Kategorien-Block rutscht (Spec 0209).
    category_eligible: false,
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

function candidate(overrides: Partial<CategoryCandidateOut> = {}): CategoryCandidateOut {
  return {
    category_key: 'hund',
    origin: 'remote',
    score: 0.9,
    provider: 'anthropic',
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

// specs/features/0209-bewertungsdetails-bloecke-qualitaet-kategorien.md: die Bewertungsdetails
// sind in zwei beschriftete Bloecke gegliedert, die Zuordnung folgt AUSSCHLIESSLICH dem
// `category_eligible`-Flag der API-Antwort (Architektur-Entscheidung 1 - keine Merkmalsliste im
// Frontend). Die Blockbildung wird vollstaendig hier auf Komponentenebene abgedeckt
// (specs/architecture/0002-testkonzept.md, Punkt 5 der useId-Sektion).
describe('CriterionDetailsList - Bloecke Qualität/Kategorien', () => {
  function qualityScore(key: string, displayName: string, value = 0.5): CriterionScoreOut {
    return criterionScore({
      criterion_key: key,
      display_name: displayName,
      value,
      category_eligible: false,
    })
  }

  function categoryScore(key: string, displayName: string, value = 0.5): CriterionScoreOut {
    return criterionScore({
      criterion_key: key,
      display_name: displayName,
      value,
      category_eligible: true,
    })
  }

  // Akzeptanzkriterium 1 + Testkonzept-Punkt 3: Zugehoerigkeit positiv UND negativ pruefen.
  it('puts every criterion in exactly one labeled block according to category_eligible', () => {
    render(
      <CriterionDetailsList
        criterionScores={[
          qualityScore('sharpness', 'Schärfe'),
          categoryScore('content_people', 'Menschen erkannt'),
          qualityScore('exposure', 'Belichtung'),
          categoryScore('tier', 'Tier erkannt'),
        ]}
        ranking={null}
        suggestion={null}
        showSuggestion={true}
      />
    )

    const quality = screen.getByRole('group', { name: 'Qualität' })
    const categories = screen.getByRole('group', { name: 'Kategorien' })

    expect(within(quality).getByText('Schärfe')).toBeInTheDocument()
    expect(within(quality).getByText('Belichtung')).toBeInTheDocument()
    expect(within(quality).queryByText('Menschen erkannt')).not.toBeInTheDocument()
    expect(within(quality).queryByText('Tier erkannt')).not.toBeInTheDocument()

    expect(within(categories).getByText('Menschen erkannt')).toBeInTheDocument()
    expect(within(categories).getByText('Tier erkannt')).toBeInTheDocument()
    expect(within(categories).queryByText('Schärfe')).not.toBeInTheDocument()
    expect(within(categories).queryByText('Belichtung')).not.toBeInTheDocument()
  })

  // Akzeptanzkriterium 5 (Partitions-Assertion): die Vereinigung beider Bloecke ist exakt die
  // Eingabeliste - nichts geht verloren, nichts erscheint doppelt.
  it('partitions the input list without losing or duplicating an entry', () => {
    const scores = [
      qualityScore('sharpness', 'Schärfe'),
      categoryScore('content_people', 'Menschen erkannt'),
      qualityScore('exposure', 'Belichtung'),
      categoryScore('tier', 'Tier erkannt'),
    ]
    render(
      <CriterionDetailsList
        criterionScores={scores}
        ranking={null}
        suggestion={null}
        showSuggestion={true}
      />
    )

    const terms = (block: HTMLElement) =>
      within(block).getAllByRole('term').map((el) => el.textContent)
    const union = [
      ...terms(screen.getByRole('group', { name: 'Qualität' })),
      ...terms(screen.getByRole('group', { name: 'Kategorien' })),
    ]

    expect(union).toHaveLength(scores.length)
    expect([...union].sort()).toEqual([...scores.map((s) => s.display_name)].sort())
  })

  // Akzeptanzkriterium 5 + Testkonzept-Punkt 4: verschraenkte Eingabe, damit ein versehentlich
  // neu sortierender Filter widerlegt werden kann.
  it('keeps the given order within each block for an interleaved input', () => {
    render(
      <CriterionDetailsList
        criterionScores={[
          qualityScore('sharpness', 'Schärfe'),
          categoryScore('content_people', 'Menschen erkannt'),
          qualityScore('exposure', 'Belichtung'),
          categoryScore('tier', 'Tier erkannt'),
        ]}
        ranking={null}
        suggestion={null}
        showSuggestion={true}
      />
    )

    const quality = screen.getByRole('group', { name: 'Qualität' })
    const categories = screen.getByRole('group', { name: 'Kategorien' })
    expect(within(quality).getAllByRole('term').map((el) => el.textContent)).toEqual([
      'Schärfe',
      'Belichtung',
    ])
    expect(within(categories).getAllByRole('term').map((el) => el.textContent)).toEqual([
      'Menschen erkannt',
      'Tier erkannt',
    ])
  })

  // Akzeptanzkriterium 9: unbekannter criterion_key (Backend-Fallback category_eligible=false)
  // bleibt sichtbar und landet im Qualitaets-Block.
  it('shows a criterion with the category_eligible fallback false in the quality block', () => {
    render(
      <CriterionDetailsList
        criterionScores={[
          qualityScore('future_criterion', 'future_criterion'),
          categoryScore('content_people', 'Menschen erkannt'),
        ]}
        ranking={null}
        suggestion={null}
        showSuggestion={true}
      />
    )

    expect(
      within(screen.getByRole('group', { name: 'Qualität' })).getByText('future_criterion')
    ).toBeInTheDocument()
    expect(
      within(screen.getByRole('group', { name: 'Kategorien' })).queryByText('future_criterion')
    ).not.toBeInTheDocument()
  })

  // Akzeptanzkriterium 7 (kein leerer Block): nur kategoriefaehige Kriterien -> keine
  // "Qualität"-Ueberschrift.
  it('omits the quality block entirely when no criterion is quality-related', () => {
    render(
      <CriterionDetailsList
        criterionScores={[categoryScore('content_people', 'Menschen erkannt')]}
        ranking={null}
        suggestion={null}
        showSuggestion={true}
      />
    )

    expect(screen.queryByRole('heading', { name: 'Qualität', level: 3 })).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Kategorien', level: 3 })).toBeInTheDocument()
  })

  // Akzeptanzkriterium 7: nur Qualitaetskriterien ohne Ranking -> kein Kategorien-Block.
  it('omits the categories block entirely when there is neither an eligible criterion nor a ranking', () => {
    render(
      <CriterionDetailsList
        criterionScores={[qualityScore('sharpness', 'Schärfe')]}
        ranking={null}
        suggestion={null}
        showSuggestion={true}
      />
    )

    expect(screen.getByRole('heading', { name: 'Qualität', level: 3 })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Kategorien', level: 3 })).not.toBeInTheDocument()
  })

  // Sichtbarkeitsregel: der Kategorien-Block erscheint auch ohne kategoriefaehiges Kriterium,
  // sobald ein Ranking vorliegt (Kandidaten/"Rang" gehoeren in diesen Block). Ueber die realen
  // Aufrufer nicht erreichbar - bewusst dokumentierte Luecke, siehe testkonzept useId-Punkt 6.
  it('shows the categories block for a ranking alone, without any eligible criterion', () => {
    render(
      <CriterionDetailsList
        criterionScores={[qualityScore('sharpness', 'Schärfe')]}
        ranking={ranking({ category_key: 'landscape', rank_position: 2, partition_size: 5 })}
        suggestion={null}
        showSuggestion={true}
      />
    )

    const categories = screen.getByRole('group', { name: 'Kategorien' })
    expect(within(categories).getByText('Rang 2 von 5')).toBeInTheDocument()
  })

  // Akzeptanzkriterium 6: Kandidatenliste, "Rang" und die Uebernehmen-Interaktion liegen INNERHALB
  // des Kategorien-Blocks und funktionieren von dort unveraendert.
  it('nests the candidate group and rank inside the categories block, override still works', async () => {
    const onOverrideCategory = vi.fn()
    const user = userEvent.setup()
    render(
      <CriterionDetailsList
        criterionScores={[qualityScore('sharpness', 'Schärfe')]}
        ranking={ranking({ category_key: 'hund' })}
        suggestion={null}
        showSuggestion={true}
        categoryCandidates={[
          candidate({ category_key: 'hund' }),
          candidate({ category_key: 'people', score: 0.1 }),
        ]}
        categoryOverride={null}
        onOverrideCategory={onOverrideCategory}
      />
    )

    const categories = screen.getByRole('group', { name: 'Kategorien' })
    expect(within(categories).getByText('Kategorie-Kandidaten')).toBeInTheDocument()
    expect(within(categories).getByText('Rang 2 von 5')).toBeInTheDocument()
    const otherRow = within(categories).getByTestId('category-candidate-row-people')
    await user.click(within(otherRow).getByRole('button', { name: /übernehmen/i }))

    expect(onOverrideCategory).toHaveBeenCalledWith('people')
  })

  // Akzeptanzkriterium 7 (zweiter Satz): komplett leere Eingabe -> keine Ueberschrift, kein
  // dt/dd, kein leeres <dl>.
  it('renders no heading and no dt/dd at all for completely empty input', () => {
    const { container } = render(
      <CriterionDetailsList
        criterionScores={[]}
        ranking={null}
        suggestion={null}
        showSuggestion={true}
      />
    )

    expect(screen.queryByRole('heading')).not.toBeInTheDocument()
    expect(container.querySelector('dt')).toBeNull()
    expect(container.querySelector('dd')).toBeNull()
    expect(container.querySelector('dl')).toBeNull()
  })

  // Akzeptanzkriterium 8: der Ausschuss-Vorschlag bleibt ein eigener, dritter Bereich OHNE eigene
  // Ueberschrift - und erscheint auch dann, wenn beide neuen Bloecke leer sind.
  it('still shows the suggestion area without a heading when both blocks are empty', () => {
    render(
      <CriterionDetailsList
        criterionScores={[]}
        ranking={null}
        suggestion={suggestion({ reason: 'duplicate', duplicate_of: 42, status: 'rejected' })}
        showSuggestion={true}
      />
    )

    expect(screen.getByText('Duplikat von Foto #42')).toBeInTheDocument()
    expect(screen.queryByRole('heading')).not.toBeInTheDocument()
  })

  it('keeps the suggestion area outside both blocks', () => {
    render(
      <CriterionDetailsList
        criterionScores={[
          qualityScore('sharpness', 'Schärfe'),
          categoryScore('content_people', 'Menschen erkannt'),
        ]}
        ranking={null}
        suggestion={suggestion({ reason: 'duplicate', duplicate_of: 42, status: 'rejected' })}
        showSuggestion={true}
      />
    )

    expect(
      within(screen.getByRole('group', { name: 'Qualität' })).queryByText('Ausschuss-Vorschlag')
    ).not.toBeInTheDocument()
    expect(
      within(screen.getByRole('group', { name: 'Kategorien' })).queryByText('Ausschuss-Vorschlag')
    ).not.toBeInTheDocument()
    expect(screen.getByText('Ausschuss-Vorschlag')).toBeInTheDocument()
  })

  // Copilot-Review-Fund auf PR #277 (unabhaengig auch von review-tests vermerkt): der
  // Kategorien-Block hatte eine zusaetzliche Wrapper-<div>-Ebene um seine Kriterienzeilen,
  // wodurch dt/dd dort eine Ebene tiefer hingen als im Qualitaets-Block - eine erst durch den
  // Umbau entstandene Asymmetrie zwischen zwei ansonsten gleichartigen Bloecken. Bewusst mit
  // gesetztem Ranking, damit die Kandidaten-/Rang-Gruppe im selben <dl> steht und der Test
  // nicht nur den trivialen Fall abdeckt.
  it('nests the criterion rows at the same depth in both blocks', () => {
    render(
      <CriterionDetailsList
        criterionScores={[
          qualityScore('sharpness', 'Schärfe'),
          categoryScore('content_people', 'Menschen erkannt'),
        ]}
        ranking={ranking()}
        suggestion={null}
        showSuggestion={true}
      />
    )

    // dt -> Zeilen-<div> -> <dl>: in beiden Bloecken identisch, keine Zwischenebene.
    expect(screen.getByText('Schärfe').parentElement?.parentElement?.tagName).toBe('DL')
    expect(screen.getByText('Menschen erkannt').parentElement?.parentElement?.tagName).toBe('DL')
  })

  // Testkonzept-Punkt 2: generierte IDs nie als Wert asserten, sondern aufloesen.
  it('links each block to its own heading via a resolvable aria-labelledby', () => {
    render(
      <CriterionDetailsList
        criterionScores={[
          qualityScore('sharpness', 'Schärfe'),
          categoryScore('content_people', 'Menschen erkannt'),
        ]}
        ranking={null}
        suggestion={null}
        showSuggestion={true}
      />
    )

    for (const label of ['Qualität', 'Kategorien']) {
      const block = screen.getByRole('group', { name: label })
      const labelledBy = block.getAttribute('aria-labelledby')
      expect(labelledBy).toBeTruthy()
      const heading = document.getElementById(labelledBy as string)
      expect(heading?.tagName).toBe('H3')
      expect(heading?.textContent).toBe(label)
    }
  })

  // Testkonzept-Punkt 2: genau deshalb useId() statt Konstanten - zwei Instanzen im selben Render
  // duerfen sich die IDs nicht teilen.
  it('generates collision-free ids for two instances in the same render', () => {
    render(
      <>
        <CriterionDetailsList
          criterionScores={[
            qualityScore('sharpness', 'Schärfe'),
            categoryScore('content_people', 'Menschen erkannt'),
          ]}
          ranking={null}
          suggestion={null}
          showSuggestion={true}
        />
        <CriterionDetailsList
          criterionScores={[
            qualityScore('sharpness', 'Schärfe'),
            categoryScore('content_people', 'Menschen erkannt'),
          ]}
          ranking={null}
          suggestion={null}
          showSuggestion={true}
        />
      </>
    )

    const ids = screen
      .getAllByRole('group')
      .map((block) => block.getAttribute('aria-labelledby'))
    expect(ids).toHaveLength(4)
    expect(new Set(ids).size).toBe(4)
  })
})

// specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md, UI/UX-Abschnitt:
// "Mehrfachkandidaten-Vergleich mit Override-Aktion" - nur bei mehr als einem Kandidaten
// eingeblendet, ersetzt dann die einzeilige "Kategorie"-Anzeige (das "Rang"-Feld bleibt).
describe('CriterionDetailsList - Kategorie-Kandidaten', () => {
  it('keeps the single-line category display when there is only one candidate', () => {
    render(
      <CriterionDetailsList
        criterionScores={[]}
        ranking={ranking({ category_key: 'hund' })}
        suggestion={null}
        showSuggestion={true}
        categoryCandidates={[candidate({ category_key: 'hund' })]}
      />
    )

    expect(screen.getByText('Kategorie')).toBeInTheDocument()
    expect(screen.getByText('Hund')).toBeInTheDocument()
    expect(screen.queryByText('Kategorie-Kandidaten')).not.toBeInTheDocument()
  })

  it('shows the candidate group instead of the single-line display with more than one candidate', () => {
    render(
      <CriterionDetailsList
        criterionScores={[]}
        ranking={ranking({ category_key: 'hund' })}
        suggestion={null}
        showSuggestion={true}
        categoryCandidates={[
          candidate({ category_key: 'hund', origin: 'remote', score: 0.9, provider: 'anthropic' }),
          candidate({ category_key: 'people', origin: 'local', score: 0.6, provider: null }),
        ]}
      />
    )

    expect(screen.getByText('Kategorie-Kandidaten')).toBeInTheDocument()
    expect(screen.getByText('Hund')).toBeInTheDocument()
    expect(screen.getByText('People')).toBeInTheDocument()
    // Genau EINE "Kategorie"-dt (aus der Rang-Gruppe entfaellt sie hier, aber "Rang" bleibt).
    expect(screen.queryByText('Kategorie')).not.toBeInTheDocument()
    expect(screen.getByText(/rang 2 von 5/i)).toBeInTheDocument()
  })

  it('sorts candidates by score descending', () => {
    render(
      <CriterionDetailsList
        criterionScores={[]}
        ranking={ranking()}
        suggestion={null}
        showSuggestion={true}
        categoryCandidates={[
          candidate({ category_key: 'people', score: 0.4 }),
          candidate({ category_key: 'hund', score: 0.9 }),
        ]}
      />
    )

    const rows = screen.getAllByRole('listitem')
    expect(rows.map((row) => row.textContent)).toEqual([
      expect.stringContaining('Hund'),
      expect.stringContaining('People'),
    ])
  })

  it('breaks a score tie alphabetically by category_key, independent of input order', () => {
    // Review-Fund (test-engineer): buildCategoryCandidateRows verliess sich bei Score-Gleichstand
    // bisher implizit auf die (zwar per ECMAScript garantierte, aber nicht explizit im Code
    // sichtbare) Sortier-Stabilitaet statt eines expliziten Sekundaer-Schluessels - Eingabe hier
    // bewusst NICHT bereits alphabetisch sortiert, um das nachzuweisen.
    render(
      <CriterionDetailsList
        criterionScores={[]}
        ranking={ranking()}
        suggestion={null}
        showSuggestion={true}
        categoryCandidates={[
          candidate({ category_key: 'strand', score: 0.5 }),
          candidate({ category_key: 'hund', score: 0.5 }),
        ]}
      />
    )

    const rows = screen.getAllByRole('listitem')
    expect(rows.map((row) => row.textContent)).toEqual([
      expect.stringContaining('Hund'),
      expect.stringContaining('Strand'),
    ])
  })

  it('shows the provider name for a remote candidate and "Lokal erkannt" for a local one', () => {
    render(
      <CriterionDetailsList
        criterionScores={[]}
        ranking={ranking()}
        suggestion={null}
        showSuggestion={true}
        categoryCandidates={[
          candidate({ category_key: 'hund', origin: 'remote', provider: 'anthropic' }),
          candidate({ category_key: 'people', origin: 'local', provider: null }),
        ]}
      />
    )

    expect(screen.getByText('Anthropic')).toBeInTheDocument()
    expect(screen.getByText('Lokal erkannt')).toBeInTheDocument()
  })

  it('shows a neutral "Aktuell" chip without a button for the currently effective candidate', () => {
    render(
      <CriterionDetailsList
        criterionScores={[]}
        ranking={ranking({ category_key: 'hund' })}
        suggestion={null}
        showSuggestion={true}
        categoryCandidates={[
          candidate({ category_key: 'hund' }),
          candidate({ category_key: 'people', score: 0.1 }),
        ]}
        categoryOverride={null}
      />
    )

    const currentRow = screen.getByTestId('category-candidate-row-hund')
    expect(currentRow).toHaveTextContent('Aktuell')
    expect(within(currentRow).queryByRole('button')).not.toBeInTheDocument()
  })

  it('shows "Manuell übernommen" + a reset button for the active override target', () => {
    render(
      <CriterionDetailsList
        criterionScores={[]}
        ranking={ranking({ category_key: 'hund' })}
        suggestion={null}
        showSuggestion={true}
        categoryCandidates={[
          candidate({ category_key: 'hund' }),
          candidate({ category_key: 'people', score: 0.1 }),
        ]}
        categoryOverride="hund"
      />
    )

    const currentRow = screen.getByTestId('category-candidate-row-hund')
    expect(currentRow).toHaveTextContent('Manuell übernommen')
    expect(within(currentRow).getByRole('button', { name: /zurücksetzen/i })).toBeInTheDocument()
  })

  it('shows an "Übernehmen" button for a candidate that is neither effective nor the override target', async () => {
    const onOverrideCategory = vi.fn()
    const user = userEvent.setup()
    render(
      <CriterionDetailsList
        criterionScores={[]}
        ranking={ranking({ category_key: 'hund' })}
        suggestion={null}
        showSuggestion={true}
        categoryCandidates={[
          candidate({ category_key: 'hund' }),
          candidate({ category_key: 'people', score: 0.1 }),
        ]}
        categoryOverride={null}
        onOverrideCategory={onOverrideCategory}
      />
    )

    const otherRow = screen.getByTestId('category-candidate-row-people')
    const button = within(otherRow).getByRole('button', { name: /übernehmen/i })
    await user.click(button)

    expect(onOverrideCategory).toHaveBeenCalledWith('people')
  })

  it('calls onResetOverride when the reset button is clicked', async () => {
    const onResetOverride = vi.fn()
    const user = userEvent.setup()
    render(
      <CriterionDetailsList
        criterionScores={[]}
        ranking={ranking({ category_key: 'hund' })}
        suggestion={null}
        showSuggestion={true}
        categoryCandidates={[candidate({ category_key: 'hund' }), candidate({ category_key: 'people' })]}
        categoryOverride="hund"
        onResetOverride={onResetOverride}
      />
    )

    await user.click(screen.getByRole('button', { name: /zurücksetzen/i }))

    expect(onResetOverride).toHaveBeenCalled()
  })

  it('shows an orphaned override as an extra row instead of letting it disappear', () => {
    render(
      <CriterionDetailsList
        criterionScores={[]}
        ranking={ranking({ category_key: 'detail' })}
        suggestion={null}
        showSuggestion={true}
        categoryCandidates={[
          candidate({ category_key: 'people', origin: 'local', score: 0.6 }),
          candidate({ category_key: 'hund', origin: 'remote', score: 0.2 }),
        ]}
        categoryOverride="urlaub"
      />
    )

    const orphanRow = screen.getByTestId('category-candidate-row-urlaub')
    expect(orphanRow).toHaveTextContent('Urlaub')
    expect(orphanRow).toHaveTextContent('Manuell übernommen')
    expect(within(orphanRow).getByRole('button', { name: /zurücksetzen/i })).toBeInTheDocument()
  })

  it('disables the specific pending button without blocking the rest of the list', () => {
    render(
      <CriterionDetailsList
        criterionScores={[]}
        ranking={ranking({ category_key: 'hund' })}
        suggestion={null}
        showSuggestion={true}
        categoryCandidates={[
          candidate({ category_key: 'hund' }),
          candidate({ category_key: 'people', score: 0.1 }),
          candidate({ category_key: 'strand', score: 0.05 }),
        ]}
        categoryOverride={null}
        pendingOverrideKey="people"
      />
    )

    const pendingRow = screen.getByTestId('category-candidate-row-people')
    const otherRow = screen.getByTestId('category-candidate-row-strand')
    expect(within(pendingRow).getByRole('button', { name: /übernehmen/i })).toBeDisabled()
    expect(within(otherRow).getByRole('button', { name: /übernehmen/i })).toBeEnabled()
  })
})
