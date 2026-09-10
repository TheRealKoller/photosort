import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type {
  CategoryCandidateOut,
  CategoryOut,
  CriterionScoreOut,
  FineLabelOut,
  RankingOut,
  SuggestionOut,
} from '../api/types'
import {
  CONFIDENCE_EXPLANATION,
  CONFIDENCE_EXPLANATION_LABEL,
} from '../utils/confidenceLabels'
import {
  CriterionDetailsList,
  hasCategoryControls,
  type CriterionDetailsPart,
} from './CriterionDetailsList'

/** Verkuerztes Set (nur `key`/`display_name` werden ausgewertet) in Registry-Anzeigereihenfolge -
 * specs/features/0289-feste-kategorien.md. */
const CATEGORIES: CategoryOut[] = [
  { key: 'menschen', display_name: 'Menschen', definition: 'd', locally_available: true },
  { key: 'tier', display_name: 'Tier', definition: 'd', locally_available: true },
  { key: 'landschaft', display_name: 'Landschaft', definition: 'd', locally_available: true },
  { key: 'gegenstand', display_name: 'Gegenstand', definition: 'd', locally_available: false },
  {
    key: 'sport_aktivitaet',
    display_name: 'Sport & Aktivität',
    definition: 'd',
    locally_available: false,
  },
  { key: 'nicht_erkannt', display_name: 'Nicht erkannt', definition: 'd', locally_available: false },
]

function fineLabel(overrides: Partial<FineLabelOut> = {}): FineLabelOut {
  return {
    canonical_key: 'urlaub',
    display_name: 'Urlaub',
    raw_label: 'Urlaub',
    provider: 'anthropic',
    ...overrides,
  }
}

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
    is_primary: true,
    curation_position: null,
    ...overrides,
  }
}

function candidate(overrides: Partial<CategoryCandidateOut> = {}): CategoryCandidateOut {
  return {
    category_key: 'tier',
    origin: 'remote',
    provider: 'anthropic',
    // specs/features/0299-kategorie-konfidenz-anzeigen.md: Basiswert "keine Modellaussage".
    confidence: null,
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
          candidate({ category_key: 'people' }),
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
          candidate({ category_key: 'hund', origin: 'remote', provider: 'anthropic' }),
          candidate({ category_key: 'people', origin: 'local', provider: null }),
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

  it('keeps the server-given order of the candidates', () => {
    // specs/features/0289-feste-kategorien.md: die Reihenfolge kommt seit dieser Spec bereits vom
    // Server (Registry-Anzeigereihenfolge) - die Komponente sortiert bewusst NICHT mehr um. Das
    // frueher hier getestete Score-Kriterium ist mit dem `score`-Feld entfallen: die Auswahl
    // entscheidet die feste Vorrangreihenfolge im Backend, ein Zahlenvergleich in der Oberflaeche
    // haette dort keine Entsprechung mehr.
    render(
      <CriterionDetailsList
        criterionScores={[]}
        ranking={ranking()}
        suggestion={null}
        showSuggestion={true}
        categories={CATEGORIES}
        categoryCandidates={[
          candidate({ category_key: 'menschen' }),
          candidate({ category_key: 'tier' }),
        ]}
      />
    )

    const rows = screen.getAllByRole('listitem')
    expect(rows.map((row) => row.textContent)).toEqual([
      expect.stringContaining('Menschen'),
      expect.stringContaining('Tier'),
    ])
  })

  it('does not show a confidence percentage next to a candidate anymore', () => {
    render(
      <CriterionDetailsList
        criterionScores={[]}
        ranking={ranking()}
        suggestion={null}
        showSuggestion={true}
        categories={CATEGORIES}
        categoryCandidates={[
          candidate({ category_key: 'tier' }),
          candidate({ category_key: 'menschen' }),
        ]}
      />
    )

    const row = screen.getByTestId('category-candidate-row-tier')
    expect(row.textContent).not.toMatch(/\d+%/)
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
          candidate({ category_key: 'people' }),
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
          candidate({ category_key: 'people' }),
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
          candidate({ category_key: 'people' }),
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
    // specs/features/0217: "detail" wird nicht mehr automatisch vergeben, der Auffang-Key heisst
    // jetzt "unerkannt" - reine Fixture-Aktualisierung, die Assertion unten prueft unveraendert
    // die verwaiste Override-Zeile.
    render(
      <CriterionDetailsList
        criterionScores={[]}
        ranking={ranking({ category_key: 'unerkannt' })}
        suggestion={null}
        showSuggestion={true}
        categoryCandidates={[
          candidate({ category_key: 'people', origin: 'local' }),
          candidate({ category_key: 'hund', origin: 'remote' }),
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
          candidate({ category_key: 'people' }),
          candidate({ category_key: 'strand' }),
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

// specs/features/0289-feste-kategorien.md, Teststrategie Abschnitt 9 ab hier: die
// "Alle Kategorien"-Auswahl (alle 13 Eintraege, unabhaengig von der Erkennung) und die
// Feinlabel-Chips. Alle Selektoren ueber getByRole/getByLabelText, nie ueber Klassennamen.

describe('CriterionDetailsList: Alle-Kategorien-Auswahl', () => {
  function renderWithSelect(props: Record<string, unknown> = {}) {
    return render(
      <CriterionDetailsList
        criterionScores={[]}
        ranking={ranking({ category_key: 'tier' })}
        suggestion={null}
        showSuggestion={true}
        categories={CATEGORIES}
        categoryCandidates={[candidate({ category_key: 'tier' })]}
        onOverrideCategory={() => {}}
        {...props}
      />
    )
  }

  it('offers every entry of the set, not just the candidates', () => {
    renderWithSelect()

    const select = screen.getByLabelText('Alle Kategorien')
    const optionLabels = within(select)
      .getAllByRole('option')
      .map((option) => option.textContent)
    for (const entry of CATEGORIES) {
      expect(optionLabels).toContain(entry.display_name)
    }
  })

  it('lists the options in registry display order with the catch-all last', () => {
    renderWithSelect()

    const select = screen.getByLabelText('Alle Kategorien')
    const values = within(select)
      .getAllByRole('option')
      .map((option) => (option as HTMLOptionElement).value)
      .filter((value) => value !== '')
    expect(values[0]).toBe('menschen')
    expect(values.at(-1)).toBe('nicht_erkannt')
  })

  it('keeps the candidate list visible next to the select as an explanation', () => {
    // Zwei Kandidaten, weil die "Kategorie-Kandidaten"-Gruppe erst ab zwei Eintraegen erscheint
    // (Bestandsverhalten aus Spec 0055, von dieser Spec unveraendert) - bei genau einem Kandidaten
    // steht stattdessen die kompakte "Kategorie"-Zeile. Geprueft wird hier, dass die neue
    // "Alle Kategorien"-Auswahl die Kandidatenliste ERGAENZT statt sie zu ersetzen.
    renderWithSelect({
      categoryCandidates: [
        candidate({ category_key: 'tier' }),
        candidate({ category_key: 'menschen', origin: 'local', provider: null }),
      ],
    })

    expect(screen.getByLabelText('Alle Kategorien')).toBeInTheDocument()
    expect(screen.getByTestId('category-candidate-row-tier')).toBeInTheDocument()
    expect(screen.getByTestId('category-candidate-row-menschen')).toBeInTheDocument()
  })

  it('calls the mutation callback with the chosen key', async () => {
    const user = userEvent.setup()
    const onOverrideCategory = vi.fn()
    renderWithSelect({ onOverrideCategory })

    await user.selectOptions(screen.getByLabelText('Alle Kategorien'), 'sport_aktivitaet')

    expect(onOverrideCategory).toHaveBeenCalledWith('sport_aktivitaet')
  })

  it('offers the catch-all as a regular, selectable option with an explanation', async () => {
    const user = userEvent.setup()
    const onOverrideCategory = vi.fn()
    renderWithSelect({ onOverrideCategory })

    await user.selectOptions(screen.getByLabelText('Alle Kategorien'), 'nicht_erkannt')

    expect(onOverrideCategory).toHaveBeenCalledWith('nicht_erkannt')
    expect(screen.getByText(/kein bildmotiv sicher bestimmbar/i)).toBeInTheDocument()
  })

  it('disables the select while the category set is still loading', () => {
    renderWithSelect({ categories: [], categoriesLoading: true })

    expect(screen.getByLabelText('Alle Kategorien')).toBeDisabled()
  })

  it('disables the select while an override request is running', () => {
    renderWithSelect({ pendingOverrideKey: 'menschen' })

    expect(screen.getByLabelText('Alle Kategorien')).toBeDisabled()
  })

  it('shows an inline alert with a retry button when the set could not be loaded', async () => {
    const user = userEvent.setup()
    const onRetryCategories = vi.fn()
    renderWithSelect({ categories: [], categoriesError: true, onRetryCategories })

    expect(screen.getByRole('alert')).toHaveTextContent(/kategorien konnten nicht geladen werden/i)
    expect(screen.queryByLabelText('Alle Kategorien')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /erneut versuchen/i }))
    expect(onRetryCategories).toHaveBeenCalled()
  })

  it('renders no select at all when the caller does not allow overriding', () => {
    render(
      <CriterionDetailsList
        criterionScores={[]}
        ranking={ranking()}
        suggestion={null}
        showSuggestion={true}
        categories={CATEGORIES}
      />
    )

    expect(screen.queryByLabelText('Alle Kategorien')).not.toBeInTheDocument()
  })
})

describe('CriterionDetailsList: Feinlabel-Chips', () => {
  it('renders the fine labels of a photo', () => {
    render(
      <CriterionDetailsList
        criterionScores={[]}
        ranking={ranking()}
        suggestion={null}
        showSuggestion={true}
        categories={CATEGORIES}
        fineLabels={[fineLabel(), fineLabel({ canonical_key: 'bluete', display_name: 'Blüte' })]}
      />
    )

    const list = screen.getByRole('list', { name: 'Feinlabels' })
    expect(within(list).getByText('Urlaub')).toBeInTheDocument()
    expect(within(list).getByText('Blüte')).toBeInTheDocument()
  })

  it('renders the fine labels even when the category is the catch-all', () => {
    // Direktes Akzeptanzkriterium: erkennbar bleiben soll, was das System auch bei unbekannter
    // Hauptkategorie vermutete.
    render(
      <CriterionDetailsList
        criterionScores={[]}
        ranking={ranking({ category_key: 'nicht_erkannt' })}
        suggestion={null}
        showSuggestion={true}
        categories={CATEGORIES}
        fineLabels={[fineLabel()]}
      />
    )

    expect(within(screen.getByRole('list', { name: 'Feinlabels' })).getByText('Urlaub')).toBeInTheDocument()
  })

  it('renders no placeholder at all without fine labels', () => {
    render(
      <CriterionDetailsList
        criterionScores={[]}
        ranking={ranking()}
        suggestion={null}
        showSuggestion={true}
        categories={CATEGORIES}
        fineLabels={[]}
      />
    )

    expect(screen.queryByRole('list', { name: 'Feinlabels' })).toBeNull()
    expect(screen.queryByText('Feinlabels')).toBeNull()
  })

  it('renders the fine label with a different badge tone than the category badge', () => {
    // Sie sind Zusatzinformation, keine kategoriale Einordnung - geprueft ueber das semantische
    // `data-badge-tone`-Attribut, nicht ueber Klassennamen.
    const { container } = render(
      <CriterionDetailsList
        criterionScores={[]}
        ranking={ranking()}
        suggestion={null}
        showSuggestion={true}
        categories={CATEGORIES}
        fineLabels={[fineLabel()]}
      />
    )

    const chip = container.querySelector('[data-badge-tone="accent"][data-badge-variant="suggested"]')
    expect(chip).toHaveTextContent('Urlaub')
  })

  it('never renders a fine label via dangerouslySetInnerHTML', () => {
    // Security-Muss-Kriterium (specs/features/0289-feste-kategorien.md, Abschnitt 3): Feinlabels
    // sind die erste Stelle, an der freier LLM-Text tatsaechlich in der Oberflaeche landet - sie
    // duerfen ausschliesslich als regulaerer React-Textknoten gerendert werden. Analog
    // CloudVisionStatusList.test.tsx.
    const { container } = render(
      <CriterionDetailsList
        criterionScores={[]}
        ranking={ranking()}
        suggestion={null}
        showSuggestion={true}
        categories={CATEGORIES}
        fineLabels={[
          fineLabel({ display_name: '<img src=x onerror="alert(1)">', canonical_key: 'xss' }),
        ]}
      />
    )

    expect(container.querySelector('img')).toBeNull()
    expect(screen.getByText('<img src=x onerror="alert(1)">')).toBeInTheDocument()
  })
})


// specs/features/0299-kategorie-konfidenz-anzeigen.md, Akzeptanzkriterien 2/3/4/7
describe('CriterionDetailsList: Modell-Konfidenz', () => {
  function renderWithCandidates(candidates: CategoryCandidateOut[], categoryKey = 'tier') {
    return render(
      <CriterionDetailsList
        criterionScores={[]}
        ranking={ranking({ category_key: categoryKey })}
        suggestion={null}
        showSuggestion={false}
        categories={CATEGORIES}
        categoryCandidates={candidates}
      />
    )
  }

  it('zeigt die Zahl an jedem Kandidaten der Kandidatenliste', () => {
    renderWithCandidates([
      candidate({ category_key: 'tier', confidence: 0.92 }),
      candidate({ category_key: 'landschaft', origin: 'local', provider: null, confidence: 0.41 }),
    ])

    expect(
      within(screen.getByTestId('category-candidate-row-tier')).getByText('92%')
    ).toBeInTheDocument()
    expect(
      within(screen.getByTestId('category-candidate-row-landschaft')).getByText('41%')
    ).toBeInTheDocument()
  })

  it('rendert fuer einen Kandidaten ohne Angabe KEINEN Platzhalter', () => {
    // Negativ-Assertion: die Luecke IST das richtige Signal - kein Strich, kein "0%", kein
    // leeres Prozentzeichen.
    renderWithCandidates([
      candidate({ category_key: 'tier', confidence: 0.92 }),
      candidate({ category_key: 'landschaft', origin: 'local', provider: null, confidence: null }),
    ])

    const row = screen.getByTestId('category-candidate-row-landschaft')
    expect(within(row).queryByText(/%/)).not.toBeInTheDocument()
    expect(row).not.toHaveTextContent('—')
    expect(row).not.toHaveTextContent('0%')
  })

  it('zeigt die exakte Null als 0%, nicht als fehlende Angabe', () => {
    renderWithCandidates([
      candidate({ category_key: 'tier', confidence: 0 }),
      candidate({ category_key: 'landschaft', origin: 'local', provider: null }),
    ])

    expect(
      within(screen.getByTestId('category-candidate-row-tier')).getByText('0%')
    ).toBeInTheDocument()
  })

  it('rundet kaufmaennisch und kennt keine "< 1 %"-Sonderregel', () => {
    renderWithCandidates([
      candidate({ category_key: 'tier', confidence: 0.995 }),
      candidate({ category_key: 'landschaft', origin: 'local', provider: null, confidence: 0.004 }),
    ])

    expect(
      within(screen.getByTestId('category-candidate-row-tier')).getByText('100%')
    ).toBeInTheDocument()
    expect(
      within(screen.getByTestId('category-candidate-row-landschaft')).getByText('0%')
    ).toBeInTheDocument()
  })

  it('zeigt die Zahl auch in der einzeiligen Kategorie-Anzeige', () => {
    // Zweiter Zweig (hoechstens ein Kandidat) - er wird beim Einbau am leichtesten vergessen.
    renderWithCandidates([candidate({ category_key: 'tier', confidence: 0.78 })])

    expect(screen.getByText('Kategorie')).toBeInTheDocument()
    expect(screen.getByText('Tier')).toBeInTheDocument()
    expect(screen.getByText('78%')).toBeInTheDocument()
  })

  it('laesst die einzeilige Anzeige ohne Angabe unveraendert', () => {
    renderWithCandidates([candidate({ category_key: 'tier', confidence: null })])

    expect(screen.getByText('Tier')).toBeInTheDocument()
    expect(screen.queryByText(/%/)).not.toBeInTheDocument()
  })

  it('zeigt in der einzeiligen Anzeige die Zahl des ANGEZEIGTEN Schluessels', () => {
    // Die Zahl folgt dem Schluessel: steht in der Rangfolge eine andere Kategorie als beim
    // einzigen Kandidaten, gehoert dorthin keine fremde Zahl.
    renderWithCandidates([candidate({ category_key: 'tier', confidence: 0.78 })], 'landschaft')

    expect(screen.getByText('Landschaft')).toBeInTheDocument()
    expect(screen.queryByText('78%')).not.toBeInTheDocument()
  })

  it('weist die Zahl ueber einen festen Hinweis als Selbsteinschaetzung aus', async () => {
    const user = userEvent.setup()
    renderWithCandidates([candidate({ category_key: 'tier', confidence: 0.92 })])

    const trigger = screen.getByText(CONFIDENCE_EXPLANATION_LABEL)
    await user.click(trigger)

    expect(screen.getByText(CONFIDENCE_EXPLANATION)).toBeInTheDocument()
  })

  it('nennt die Zahl nirgends Trefferquote, Genauigkeit oder korrekt', async () => {
    // Negativ-Assertion zu Akzeptanzkriterium 7: die drei Woerter duerfen ausschliesslich im
    // Hinweistext selbst vorkommen, der sie ausdruecklich ZURUECKNIMMT.
    const user = userEvent.setup()
    const { container } = renderWithCandidates([candidate({ category_key: 'tier', confidence: 0.92 })])

    await user.click(screen.getByText(CONFIDENCE_EXPLANATION_LABEL))
    const text = (container.textContent ?? '').replace(CONFIDENCE_EXPLANATION, '')

    expect(text).not.toMatch(/Trefferquote/i)
    expect(text).not.toMatch(/Genauigkeit/i)
    expect(text).not.toMatch(/korrekt/i)
  })

  it('zeigt den Hinweis gar nicht, wenn kein einziger Wert dargestellt wird', () => {
    // Ein Hinweis auf eine Zahl, die nicht da ist, waere reines Rauschen - und der haeufigste
    // Fall ist der Altbestand ohne jede Angabe.
    renderWithCandidates([
      candidate({ category_key: 'tier', confidence: null }),
      candidate({ category_key: 'landschaft', origin: 'local', provider: null, confidence: null }),
    ])

    expect(screen.queryByText(CONFIDENCE_EXPLANATION_LABEL)).not.toBeInTheDocument()
  })
})

describe('CriterionDetailsList — Rollen der Zugehoerigkeiten', () => {
  /* specs/features/0300-nebenkategorien.md, Akzeptanzkriterium 13: zu jeder Kategorie des Fotos
   * ist seine Rolle ablesbar - ausschliesslich aus `is_primary`, nie aus einem Zahlenvergleich. */

  function renderWithMemberships(rankings: RankingOut[], current = rankings[0] ?? null) {
    return render(
      <CriterionDetailsList
        criterionScores={[]}
        ranking={current}
        rankings={rankings}
        suggestion={null}
        showSuggestion={false}
        categories={CATEGORIES}
      />
    )
  }

  it('listet jede Kategorie des Fotos mit ihrer Rolle als TEXT', () => {
    renderWithMemberships([
      ranking({ category_key: 'tier', is_primary: true }),
      ranking({ category_key: 'menschen', is_primary: false }),
    ])

    const section = screen.getByRole('list', { name: 'Kategorien dieses Fotos' })
    const rows = within(section).getAllByRole('listitem')
    expect(rows.map((row) => row.textContent)).toEqual(['TierHaupt', 'MenschenNeben'])
  })

  it('weist die Rolle AN DIESER STELLE aus (die gerenderte Zugehoerigkeit)', () => {
    const secondary = ranking({ category_key: 'menschen', is_primary: false })
    renderWithMemberships([ranking({ category_key: 'tier', is_primary: true }), secondary], secondary)

    const roleTerm = screen.getByText('Rolle')
    const row = roleTerm.parentElement
    expect(row).not.toBeNull()
    expect(within(row as HTMLElement).getByText('Neben')).toBeInTheDocument()
  })

  it('rendert bei genau einer Zugehoerigkeit weder Sektion noch Rollenzeile', () => {
    /* Akzeptanzkriterium 24: ohne Nebenkategorien ist die Oberflaeche von heute nicht zu
     * unterscheiden - Negativ-Assertion auf Text UND Textalternative. */
    renderWithMemberships([ranking({ category_key: 'tier', is_primary: true })])

    expect(screen.queryByText('Kategorien dieses Fotos')).not.toBeInTheDocument()
    expect(screen.queryByText('Rolle')).not.toBeInTheDocument()
    expect(screen.queryByText('Haupt')).not.toBeInTheDocument()
  })

  it('wiederholt die Konfidenzzahlen in der Rollen-Sektion NICHT', () => {
    /* Sie stehen unveraendert in der Kandidatenliste darueber (Spec 0299) - eine zweite Stelle
     * waere eine zweite, driftende Anzeige derselben Zahl. */
    render(
      <CriterionDetailsList
        criterionScores={[]}
        ranking={ranking({ category_key: 'tier', is_primary: true })}
        rankings={[
          ranking({ category_key: 'tier', is_primary: true }),
          ranking({ category_key: 'menschen', is_primary: false }),
        ]}
        suggestion={null}
        showSuggestion={false}
        categories={CATEGORIES}
      />
    )

    const section = screen.getByRole('list', { name: 'Kategorien dieses Fotos' })
    expect(section.textContent).not.toMatch(/%/)
  })
})

/* -------------------------------------------------------------------------------------------
 * specs/features/0370-bedienelemente-zuerst.md: Teilrendering ueber das Prop `part`.
 *
 * BEWUSST NUR ANGEHAENGT: die Bestandsfaelle oben bleiben inhaltlich unveraendert - dass sie mit
 * dem Vorgabewert 'all' woertlich weiterlaufen, IST der Regressionsnachweis fuer
 * Akzeptanzkriterium 8 (Raster/Kuratierung unveraendert). Neue Faelle stehen ausschliesslich in
 * diesen neuen describe-Bloecken.
 * ----------------------------------------------------------------------------------------- */

/** Maximal-Props: JEDER darstellbare Bereich ist aktiv. Grundlage der Partitions-Zusicherung -
 * eine Fixture, in der ein Bereich fehlte, koennte die Doppelanzeige dieses Bereichs gar nicht
 * finden. `part` bewusst optional durchgereicht, damit derselbe Aufbau auch den Vorgabewert
 * (kein `part`) abdeckt. */
function renderMaximalDetails(part?: CriterionDetailsPart) {
  return render(
    <CriterionDetailsList
      part={part}
      criterionScores={[
        criterionScore({ criterion_key: 'sharpness', display_name: 'Schärfe' }),
        criterionScore({
          criterion_key: 'content_people',
          display_name: 'Menschen erkannt',
          category_eligible: true,
        }),
      ]}
      ranking={ranking({ category_key: 'tier', is_primary: true })}
      rankings={[
        ranking({ category_key: 'tier', is_primary: true }),
        ranking({ category_key: 'menschen', is_primary: false }),
      ]}
      suggestion={suggestion()}
      showSuggestion={true}
      categoryCandidates={[
        candidate({ category_key: 'tier', confidence: 0.9 }),
        candidate({ category_key: 'menschen', origin: 'local', provider: null }),
      ]}
      fineLabels={[fineLabel()]}
      categories={CATEGORIES}
      onOverrideCategory={vi.fn()}
      onResetOverride={vi.fn()}
    />
  )
}

/** Literale Sondenliste je Bereich - NICHT aus dem Rendering abgeleitet (eine aus der Ausgabe
 * gewonnene Erwartung prueft sich selbst). Je Bereich eine Beschriftung, die es nur dort gibt. */
const PART_PROBES = [
  { text: 'Qualität', part: 'info' },
  { text: 'Schärfe', part: 'info' },
  { text: 'Kategorien', part: 'info' },
  { text: 'Menschen erkannt', part: 'info' },
  { text: 'Kategorie-Kandidaten', part: 'controls' },
  { text: CONFIDENCE_EXPLANATION_LABEL, part: 'controls' },
  { text: 'Alle Kategorien', part: 'controls' },
  { text: 'Rolle', part: 'info' },
  { text: 'Rang', part: 'info' },
  { text: 'Kategorien dieses Fotos', part: 'info' },
  { text: 'Feinlabels', part: 'info' },
  { text: 'Ausschuss-Vorschlag', part: 'info' },
] as const

function showsProbe(container: HTMLElement, text: string): boolean {
  return within(container).queryAllByText(text).length > 0
}

describe('CriterionDetailsList — Teilrendering über `part`', () => {
  /* Partition statt zweier Positivlisten: "in beiden Teilen" waere eine Doppelanzeige, "in
   * keinem" ein verschluckter Bereich - zwei getrennte Positivtests faenden beides nicht. */
  it('zeigt jeden in `all` vorhandenen Bereich in GENAU EINEM der beiden Teile', () => {
    const all = renderMaximalDetails('all').container
    const controls = renderMaximalDetails('controls').container
    const info = renderMaximalDetails('info').container

    const actual = PART_PROBES.map(({ text }) => ({
      text,
      all: showsProbe(all, text),
      controls: showsProbe(controls, text),
      info: showsProbe(info, text),
    }))

    expect(actual).toEqual(
      PART_PROBES.map(({ text, part }) => ({
        text,
        all: true,
        controls: part === 'controls',
        info: part === 'info',
      }))
    )
  })

  it('rendert ohne `part` exakt dieselben Bereiche wie `part="all"` (Vorgabewert)', () => {
    const withoutPart = renderMaximalDetails().container
    const all = renderMaximalDetails('all').container

    expect(PART_PROBES.map(({ text }) => showsProbe(withoutPart, text))).toEqual(
      PART_PROBES.map(({ text }) => showsProbe(all, text))
    )
  })

  /* Ohne eigenes <dl> stuenden dt/dd des Bedienteils ohne <dl>-Vorfahren - invalides Markup und
   * ein stiller Bruch von Spec 0041 AK12. */
  it('stellt die `dt` des Bedienteils unter einen `dl`-Vorfahren (Kandidatenliste)', () => {
    const { container } = renderMaximalDetails('controls')

    const term = within(container).getByText('Kategorie-Kandidaten')
    expect(term.tagName).toBe('DT')
    expect(term.closest('dl')).not.toBeNull()
  })

  it('stellt die `dt` des Bedienteils unter einen `dl`-Vorfahren (einzeilige Anzeige)', () => {
    const { container } = render(
      <CriterionDetailsList
        part="controls"
        criterionScores={[criterionScore()]}
        ranking={ranking({ category_key: 'tier' })}
        suggestion={null}
        showSuggestion={false}
        categories={CATEGORIES}
      />
    )

    const term = within(container).getByText('Kategorie')
    expect(term.tagName).toBe('DT')
    expect(term.closest('dl')).not.toBeNull()
  })

  it('gibt der einzeiligen "Kategorie"-Anzeige den Bedienteil, nicht den Informationsteil', () => {
    const controls = render(
      <CriterionDetailsList
        part="controls"
        criterionScores={[criterionScore()]}
        ranking={ranking({ category_key: 'tier' })}
        suggestion={null}
        showSuggestion={false}
        categories={CATEGORIES}
      />
    ).container
    const info = render(
      <CriterionDetailsList
        part="info"
        criterionScores={[criterionScore()]}
        ranking={ranking({ category_key: 'tier' })}
        suggestion={null}
        showSuggestion={false}
        categories={CATEGORIES}
      />
    ).container

    expect(showsProbe(controls, 'Kategorie')).toBe(true)
    expect(showsProbe(controls, 'Tier')).toBe(true)
    expect(showsProbe(info, 'Kategorie')).toBe(false)
  })

  /* Der Bedienteil traegt bewusst KEINE eigene Ueberschrift und kein role="group": zwei
   * gleichlautende "Kategorien"-Ueberschriften auf einer Seite waeren mehrdeutig, und eine
   * unbeschriftete Gruppe ist im Accessibility-Tree wertlos (Akzeptanzkriterium 6). */
  it('gibt dem Bedienteil weder Überschrift noch beschriftete Gruppe', () => {
    const { container } = renderMaximalDetails('controls')

    expect(within(container).queryByRole('heading')).not.toBeInTheDocument()
    // Gefragt ist die Abwesenheit des gesetzten Attributs, nicht der Rolle: das `<details>` des
    // Konfidenz-Hinweises traegt die Rolle `group` implizit und bleibt hier bewusst stehen.
    expect(container.querySelector('[role="group"]')).toBeNull()
    expect(container.querySelector('[aria-labelledby]')).toBeNull()
  })

  it('behält im Informationsteil beide beschrifteten Blöcke', () => {
    const { container } = renderMaximalDetails('info')

    expect(within(container).getByRole('group', { name: 'Qualität' })).toBeInTheDocument()
    expect(within(container).getByRole('group', { name: 'Kategorien' })).toBeInTheDocument()
  })

  /* Ein leerer Flex-Container erzeugte im `gap-4` der Seite eine sichtbare Luecke, die kein
   * anderer Test bemerkte - deshalb `null` statt eines leeren <div>. */
  it('gibt für einen leeren Teil `null` zurück statt eines leeren Containers', () => {
    const emptyControls = render(
      <CriterionDetailsList
        part="controls"
        criterionScores={[criterionScore()]}
        ranking={null}
        suggestion={null}
        showSuggestion={false}
      />
    ).container
    const emptyInfo = render(
      <CriterionDetailsList
        part="info"
        criterionScores={[]}
        ranking={null}
        suggestion={null}
        showSuggestion={false}
      />
    ).container

    expect(emptyControls.firstChild).toBeNull()
    expect(emptyInfo.firstChild).toBeNull()
  })

  /* Gegenprobe: `all` bleibt woertlich beim Bestandsverhalten (aeusserer Container auch ohne
   * Inhalt) - die `null`-Rueckgabe ist ausdruecklich NUR eine Zusage der beiden Teile. */
  it('lässt `all` bei leerer Eingabe unverändert den äußeren Container rendern', () => {
    const { container } = render(
      <CriterionDetailsList
        criterionScores={[]}
        ranking={null}
        suggestion={null}
        showSuggestion={false}
      />
    )

    expect(container.firstChild).not.toBeNull()
  })

  /* Die exportierte Vorbedingung wird an das tatsaechliche Rendern GEBUNDEN - ein reiner
   * Tabellentest belegte nur, was die Funktion sagt, und sie wuerde beim naechsten Gate zu einer
   * zweiten, driftenden Meinung. */
  it('bindet `hasCategoryControls` über alle vier Kombinationen an das Rendern von `controls`', () => {
    const combinations = [
      { criterionScores: [], ranking: null },
      { criterionScores: [criterionScore()], ranking: null },
      { criterionScores: [], ranking: ranking() },
      { criterionScores: [criterionScore()], ranking: ranking() },
    ]

    const actual = combinations.map((combination) => {
      const { container, unmount } = render(
        <CriterionDetailsList
          part="controls"
          criterionScores={combination.criterionScores}
          ranking={combination.ranking}
          suggestion={null}
          showSuggestion={false}
          categories={CATEGORIES}
        />
      )
      const renders = container.firstChild !== null
      unmount()
      return {
        precondition: hasCategoryControls(combination.criterionScores, combination.ranking),
        renders,
      }
    })

    expect(actual).toEqual([
      { precondition: false, renders: false },
      { precondition: false, renders: false },
      { precondition: false, renders: false },
      { precondition: true, renders: true },
    ])
  })

  it('zeigt im Informationsteil den Kategorien-Block auch ohne kategoriefähiges Kriterium', () => {
    const { container } = render(
      <CriterionDetailsList
        part="info"
        criterionScores={[criterionScore()]}
        ranking={ranking()}
        suggestion={null}
        showSuggestion={false}
        categories={CATEGORIES}
      />
    )

    expect(
      within(container).getByRole('heading', { name: 'Kategorien', level: 3 })
    ).toBeInTheDocument()
    expect(within(container).getByText('Rang 2 von 5')).toBeInTheDocument()
  })

  it('lässt im Informationsteil den Kategorien-Block ohne Ranking und ohne Kategorie-Kriterium weg', () => {
    const { container } = render(
      <CriterionDetailsList
        part="info"
        criterionScores={[criterionScore()]}
        ranking={null}
        suggestion={null}
        showSuggestion={false}
        categories={CATEGORIES}
      />
    )

    expect(
      within(container).getByRole('heading', { name: 'Qualität', level: 3 })
    ).toBeInTheDocument()
    expect(within(container).queryByRole('heading', { name: 'Kategorien' })).not.toBeInTheDocument()
  })

  it('zeigt die Ausschuss-Gruppe nur im Informationsteil', () => {
    const controls = render(
      <CriterionDetailsList
        part="controls"
        criterionScores={[criterionScore()]}
        ranking={ranking()}
        suggestion={suggestion()}
        showSuggestion={true}
        categories={CATEGORIES}
      />
    ).container

    expect(showsProbe(controls, 'Ausschuss-Vorschlag')).toBe(false)
  })

  it('zeigt den Konfidenz-Erklärhinweis unverändert als `details` im Bedienteil', () => {
    const { container } = renderMaximalDetails('controls')

    const summary = within(container).getByText(CONFIDENCE_EXPLANATION_LABEL)
    expect(summary.tagName).toBe('SUMMARY')
    expect(summary.closest('details')).not.toBeNull()
    expect(within(container).getByText(CONFIDENCE_EXPLANATION)).toBeInTheDocument()
  })
})

// specs/features/0370-bedienelemente-zuerst.md, Security-Abschnitt (Auflage des
// security-engineer): der Bestandsfall oben rendert ohne `part` und deckt damit nach dem Umbau
// nur noch den Vorgabewert 'all' ab - die Einzelbildansicht rendert die Chips ueber `part="info"`.
describe('CriterionDetailsList: Feinlabel-Sicherheit je Teilbereich', () => {
  const XSS_PAYLOAD = '<img src=x onerror="alert(1)">'

  function renderWithFineLabelPayload(part: CriterionDetailsPart) {
    return render(
      <CriterionDetailsList
        part={part}
        criterionScores={[]}
        ranking={ranking()}
        suggestion={null}
        showSuggestion={true}
        categories={CATEGORIES}
        fineLabels={[fineLabel({ display_name: XSS_PAYLOAD, canonical_key: 'xss' })]}
      />
    )
  }

  it('never renders a fine label via dangerouslySetInnerHTML with part="info"', () => {
    const { container } = renderWithFineLabelPayload('info')

    expect(container.querySelector('img')).toBeNull()
    expect(within(container).getByText(XSS_PAYLOAD)).toBeInTheDocument()
  })

  it('renders no fine-label chips at all in the controls part', () => {
    const { container } = renderWithFineLabelPayload('controls')

    expect(container.querySelector('img')).toBeNull()
    expect(within(container).queryByText(XSS_PAYLOAD)).not.toBeInTheDocument()
    expect(within(container).queryByRole('list', { name: 'Feinlabels' })).not.toBeInTheDocument()
  })
})
