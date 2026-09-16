import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { CriterionScoreOut, FineLabelOut, RankingOut, SuggestionOut } from '../api/types'
import { ALBUM_SUITABILITY_NOT_RATED_TEXT } from '../utils/albumSuitability'
import { CriterionDetailsList } from './CriterionDetailsList'

/**
 * specs/features/0427-motive-mit-staerke.md, PR 3: die Komponente verliert ihren
 * Kategorien-Block. Was bleibt, sind vier Bereiche - der Qualitätsblock, der Bildinhalt-Block
 * samt „Rang", die Feinlabels und der Ausschuss-Vorschlag; die Motivstärken sind ein eigener
 * Baustein daneben (`MotifStrengthSection`).
 */
function criterionScore(overrides: Partial<CriterionScoreOut> = {}): CriterionScoreOut {
  return {
    criterion_key: 'sharpness',
    display_name: 'Schärfe',
    value: 0.8,
    source: 'local_heuristic',
    // Default-Key ist `sharpness` (ohne Präsenz-Schwelle) - der Default muss dazu passen, damit
    // kein Bestandstest unbemerkt in den Bildinhalt-Block rutscht.
    has_presence_threshold: false,
    ...overrides,
  }
}

function ranking(overrides: Partial<RankingOut> = {}): RankingOut {
  return {
    event_id: 1,
    rank_score: 0.8,
    rank_position: 3,
    proposed: true,
    partition_size: 12,
    curation_position: null,
    ...overrides,
  }
}

function suggestion(overrides: Partial<SuggestionOut> = {}): SuggestionOut {
  return {
    status: 'rejected',
    reason: 'low_quality',
    duplicate_of: null,
    sharpness: 0.1,
    exposure: 0.2,
    cluster_key: null,
    computed_at: '2026-07-20T10:00:00',
    ...overrides,
  }
}

function fineLabel(overrides: Partial<FineLabelOut> = {}): FineLabelOut {
  return {
    canonical_key: 'urlaub',
    display_name: 'Urlaub',
    raw_label: 'urlaub',
    provider: 'anthropic',
    ...overrides,
  }
}

function renderList(props: Partial<Parameters<typeof CriterionDetailsList>[0]> = {}) {
  return render(
    <CriterionDetailsList
      criterionScores={[criterionScore()]}
      ranking={null}
      suggestion={null}
      showSuggestion={false}
      {...props}
    />,
  )
}

describe('CriterionDetailsList', () => {
  it('renders criteria as rounded percentages in the given order', () => {
    renderList({
      criterionScores: [
        criterionScore({ criterion_key: 'sharpness', display_name: 'Schärfe', value: 0.8 }),
        criterionScore({ criterion_key: 'exposure', display_name: 'Belichtung', value: 0.425 }),
      ],
    })

    const rows = screen.getAllByRole('term')
    expect(rows.map((row) => row.textContent)).toEqual(['Schärfe', 'Belichtung'])
    expect(screen.getByText('80%')).toBeInTheDocument()
    expect(screen.getByText('43%')).toBeInTheDocument()
  })

  it('does not fill a missing criterion with a placeholder', () => {
    renderList({ criterionScores: [criterionScore({ criterion_key: 'sharpness' })] })

    expect(screen.getAllByRole('term')).toHaveLength(1)
    expect(screen.queryByText('—')).toBeNull()
  })

  it('shows "Rang M von N" when a ranking row exists', () => {
    renderList({ ranking: ranking({ rank_position: 3, partition_size: 12 }) })

    expect(screen.getByText('Rang')).toBeInTheDocument()
    expect(screen.getByText('Rang 3 von 12')).toBeInTheDocument()
  })

  it('omits the rank row entirely when there is no ranking', () => {
    renderList({ ranking: null })

    expect(screen.queryByText('Rang')).toBeNull()
  })

  it('omits the rank row when the ranking row carries no position', () => {
    /* „Rang – von 12" wäre eine Rangaussage über ein Foto ohne Rang. Geprüft auf `!== null`,
     * nie auf Falsyness. */
    renderList({ ranking: ranking({ rank_position: null, rank_score: null }) })

    expect(screen.queryByText('Rang')).toBeNull()
  })

  it('keeps the rank row for position 1 - the falsy case of the guard', () => {
    /* Gegenprobe zum Fall darüber: eine Falsyness-Prüfung (`ranking.rank_position &&`) verlöre
     * hier nichts, wohl aber bei einem künftigen 0-basierten Rang; entscheidend ist, dass die
     * Zeile für einen echten Rang bleibt. */
    renderList({ ranking: ranking({ rank_position: 1, partition_size: 4 }) })

    expect(screen.getByText('Rang 1 von 4')).toBeInTheDocument()
  })

  it('shows the suggestion reason when a suggestion exists and showSuggestion is true', () => {
    renderList({ suggestion: suggestion(), showSuggestion: true })

    expect(screen.getByText('Ausschuss-Vorschlag')).toBeInTheDocument()
    expect(screen.getByText('Grund')).toBeInTheDocument()
  })

  it('suppresses the suggestion group when showSuggestion is false, despite a suggestion', () => {
    /* Die Ausschuss-Gruppe bleibt exklusiv im Vorschlagskasten der Einzelbildansicht - das Flag
     * ist die alleinige, direkt geprüfte Absicherung gegen ein versehentliches Durchreichen. */
    renderList({ suggestion: suggestion(), showSuggestion: false })

    expect(screen.queryByText('Ausschuss-Vorschlag')).toBeNull()
  })
})

describe('CriterionDetailsList — Blöcke Qualität/Bildinhalt', () => {
  const QUALITY = criterionScore({
    criterion_key: 'sharpness',
    display_name: 'Schärfe',
    has_presence_threshold: false,
  })
  const CONTENT = criterionScore({
    criterion_key: 'tier',
    display_name: 'Tier erkannt',
    has_presence_threshold: true,
  })

  it('puts every criterion in exactly one labeled block according to has_presence_threshold', () => {
    /* Die Zuordnung folgt AUSSCHLIESSLICH dem Registry-Flag der Antwort - im Frontend wird dazu
     * keine Schlüsselliste gepflegt, sonst liefen Backend-Registry und Frontend beim nächsten
     * neuen Kriterium auseinander. */
    renderList({ criterionScores: [QUALITY, CONTENT] })

    const quality = screen.getByRole('group', { name: 'Qualität' })
    const content = screen.getByRole('group', { name: 'Bildinhalt' })
    expect(within(quality).getByText('Schärfe')).toBeInTheDocument()
    expect(within(quality).queryByText('Tier erkannt')).toBeNull()
    expect(within(content).getByText('Tier erkannt')).toBeInTheDocument()
    expect(within(content).queryByText('Schärfe')).toBeNull()
  })

  it('names the second block "Bildinhalt" and nowhere "Kategorien"', () => {
    /* Die Umbenennung als eigener Fall samt NEGATIVER Assertion: eine stehengebliebene
     * Überschrift „Kategorien" wäre für jede Positivprüfung der Zeilen darunter unsichtbar. */
    renderList({ criterionScores: [QUALITY, CONTENT] })

    expect(screen.getByRole('heading', { name: 'Bildinhalt' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Kategorien' })).toBeNull()
    expect(screen.queryByText(/Kategorie/)).toBeNull()
  })

  it('partitions the input list without losing or duplicating an entry', () => {
    renderList({ criterionScores: [QUALITY, CONTENT] })

    const quality = screen.getByRole('group', { name: 'Qualität' })
    const content = screen.getByRole('group', { name: 'Bildinhalt' })
    expect(within(quality).getAllByRole('term')).toHaveLength(1)
    expect(within(content).getAllByRole('term')).toHaveLength(1)
    expect(screen.getAllByRole('term')).toHaveLength(2)
  })

  it('keeps the given order within each block for an interleaved input', () => {
    renderList({
      criterionScores: [
        criterionScore({ criterion_key: 'sharpness', display_name: 'Schärfe' }),
        criterionScore({
          criterion_key: 'tier',
          display_name: 'Tier erkannt',
          has_presence_threshold: true,
        }),
        criterionScore({ criterion_key: 'exposure', display_name: 'Belichtung' }),
        criterionScore({
          criterion_key: 'gebaeude',
          display_name: 'Gebäude erkannt',
          has_presence_threshold: true,
        }),
      ],
    })

    const quality = screen.getByRole('group', { name: 'Qualität' })
    const content = screen.getByRole('group', { name: 'Bildinhalt' })
    expect(
      within(quality)
        .getAllByRole('term')
        .map((row) => row.textContent),
    ).toEqual(['Schärfe', 'Belichtung'])
    expect(
      within(content)
        .getAllByRole('term')
        .map((row) => row.textContent),
    ).toEqual(['Tier erkannt', 'Gebäude erkannt'])
  })

  it('omits the quality block entirely when no criterion is quality-related', () => {
    renderList({ criterionScores: [CONTENT] })

    expect(screen.queryByRole('group', { name: 'Qualität' })).toBeNull()
    expect(screen.getByRole('group', { name: 'Bildinhalt' })).toBeInTheDocument()
  })

  it('omits the content block when there is neither a content criterion nor a ranking', () => {
    renderList({ criterionScores: [QUALITY], ranking: null })

    expect(screen.queryByRole('group', { name: 'Bildinhalt' })).toBeNull()
  })

  it('shows the content block for a ranking alone, without any content criterion', () => {
    /* „Rang" gehört fachlich in den Bildinhalt-Block und erscheint deshalb auch ohne ein
     * einziges Inhalts-Kriterium. */
    renderList({ criterionScores: [QUALITY], ranking: ranking() })

    const content = screen.getByRole('group', { name: 'Bildinhalt' })
    expect(within(content).getByText('Rang')).toBeInTheDocument()
  })

  it('renders no heading and no dt/dd at all for completely empty input', () => {
    renderList({ criterionScores: [], ranking: null })

    expect(screen.queryByRole('heading')).toBeNull()
    expect(screen.queryAllByRole('term')).toHaveLength(0)
    expect(screen.queryAllByRole('definition')).toHaveLength(0)
  })

  it('keeps the suggestion area outside both blocks and without a heading', () => {
    renderList({
      criterionScores: [QUALITY, CONTENT],
      suggestion: suggestion(),
      showSuggestion: true,
    })

    const quality = screen.getByRole('group', { name: 'Qualität' })
    const content = screen.getByRole('group', { name: 'Bildinhalt' })
    expect(within(quality).queryByText('Ausschuss-Vorschlag')).toBeNull()
    expect(within(content).queryByText('Ausschuss-Vorschlag')).toBeNull()
    expect(screen.getByText('Ausschuss-Vorschlag')).toBeInTheDocument()
    expect(screen.getAllByRole('heading')).toHaveLength(2)
  })

  it('links each block to its own heading via a resolvable aria-labelledby', () => {
    const { container } = renderList({ criterionScores: [QUALITY, CONTENT] })

    for (const group of container.querySelectorAll('[role="group"]')) {
      const id = group.getAttribute('aria-labelledby')
      expect(id).toBeTruthy()
      expect(container.querySelector(`#${CSS.escape(id as string)}`)).not.toBeNull()
    }
  })

  it('generates collision-free ids for two instances in the same render', () => {
    /* Popover über der permanenten Sektion: zwei Instanzen stehen gleichzeitig im DOM, feste
     * Ids kollidierten dann. */
    const { container } = render(
      <>
        <CriterionDetailsList
          criterionScores={[QUALITY]}
          ranking={null}
          suggestion={null}
          showSuggestion={false}
        />
        <CriterionDetailsList
          criterionScores={[QUALITY]}
          ranking={null}
          suggestion={null}
          showSuggestion={false}
        />
      </>,
    )

    const ids = [...container.querySelectorAll('[role="group"]')].map((group) =>
      group.getAttribute('aria-labelledby'),
    )
    expect(ids).toHaveLength(2)
    expect(new Set(ids).size).toBe(2)
  })
})

describe('CriterionDetailsList: Feinlabel-Chips', () => {
  const CONTENT = criterionScore({
    criterion_key: 'tier',
    display_name: 'Tier erkannt',
    has_presence_threshold: true,
  })

  it('renders the fine labels of a photo', () => {
    renderList({
      criterionScores: [CONTENT],
      fineLabels: [fineLabel({ canonical_key: 'urlaub', display_name: 'Urlaub' })],
    })

    const list = screen.getByRole('list', { name: 'Feinlabels' })
    expect(within(list).getByText('Urlaub')).toBeInTheDocument()
  })

  it('renders no placeholder at all without fine labels', () => {
    renderList({ criterionScores: [CONTENT], fineLabels: [] })

    expect(screen.queryByRole('list', { name: 'Feinlabels' })).toBeNull()
    expect(screen.queryByText('Feinlabels')).toBeNull()
  })

  it('never renders a fine label via dangerouslySetInnerHTML', () => {
    /* SICHERHEIT: freier, extern erzeugter LLM-Text. Ausschließlich als regulärer
     * React-Textknoten - das ist die tragende Voraussetzung dafür, dass das Session-Token in
     * `localStorage` liegen darf. */
    renderList({
      criterionScores: [CONTENT],
      fineLabels: [
        fineLabel({
          canonical_key: 'boese',
          display_name: '<img src=x onerror="alert(1)">',
          raw_label: '<img src=x onerror="alert(1)">',
        }),
      ],
    })

    const list = screen.getByRole('list', { name: 'Feinlabels' })
    expect(list.querySelector('img')).toBeNull()
    expect(within(list).getByText('<img src=x onerror="alert(1)">')).toBeInTheDocument()
  })
})

describe('CriterionDetailsList: die Albumtauglichkeit', () => {
  it('shows the exact model level inside the quality block', () => {
    /* Die genaue Stufe erscheint NUR hier - nicht neben der Dreistufigkeit auf der Kachel: zwei
     * Skalen nebeneinander wären zwei Zahlen für eine Aussage. */
    renderList({ albumSuitability: { level: 4, reason: 'Alle schauen in die Kamera.' } })

    const quality = screen.getByRole('group', { name: 'Qualität' })
    expect(within(quality).getByText('Albumtauglichkeit')).toBeInTheDocument()
    expect(within(quality).getByText('Stufe 4 von 5')).toBeInTheDocument()
  })

  it('shows the full reason, not a shortened one', () => {
    const reason =
      'Die Person ist am linken Bildrand angeschnitten und der Hintergrund ist unruhig, ' +
      'dadurch wirkt der Bildaufbau zufällig.'

    renderList({ albumSuitability: { level: 2, reason } })

    expect(screen.getByText(reason)).toBeInTheDocument()
  })

  it('says "Noch nicht bewertet" instead of a level when there is no verdict', () => {
    renderList({ albumSuitability: null })

    const quality = screen.getByRole('group', { name: 'Qualität' })
    expect(within(quality).getByText('Albumtauglichkeit')).toBeInTheDocument()
    expect(within(quality).getByText(ALBUM_SUITABILITY_NOT_RATED_TEXT)).toBeInTheDocument()
  })

  it('renders no reason carrier at all without a verdict', () => {
    const { container } = renderList({ albumSuitability: null })

    expect(container.querySelectorAll('[data-album-suitability-reason]')).toHaveLength(0)
  })

  it('renders no reason carrier when the reason is null', () => {
    /* Kardinalität Null über ein `data-`-Attribut statt über eine Textsuche: ein leerer Träger
     * fiele einer Textsuche nicht auf. */
    const { container } = renderList({ albumSuitability: { level: 3, reason: null } })

    expect(
      within(screen.getByRole('group', { name: 'Qualität' })).getByText('Stufe 3 von 5'),
    ).toBeInTheDocument()
    expect(container.querySelectorAll('[data-album-suitability-reason]')).toHaveLength(0)
  })

  it('renders exactly one reason carrier when there is a reason', () => {
    const { container } = renderList({ albumSuitability: { level: 3, reason: 'Solide.' } })

    expect(container.querySelectorAll('[data-album-suitability-reason]')).toHaveLength(1)
  })

  it('never renders the reason via dangerouslySetInnerHTML', () => {
    /* SICHERHEIT (S12): freier, extern erzeugter LLM-Text aus einem Bild, das Text enthalten
     * kann - ausschließlich als regulärer React-Textknoten. */
    const payload = '<img src=x onerror="alert(1)">'

    const { container } = renderList({ albumSuitability: { level: 1, reason: payload } })

    expect(container.querySelector('img')).toBeNull()
    expect(screen.getByText(payload)).toBeInTheDocument()
  })

  it('never turns a javascript: payload into a link or an image', () => {
    const payload = 'javascript:alert(1)'

    const { container } = renderList({ albumSuitability: { level: 1, reason: payload } })

    expect(container.querySelector('a')).toBeNull()
    expect(container.querySelector('img')).toBeNull()
    expect(screen.getByText(payload)).toBeInTheDocument()
  })

  it('omits the whole row when the field was not passed at all', () => {
    /* `undefined` heißt "diese Einbindungsstelle reicht das Feld nicht durch" und ist keine
     * Aussage über den Bewertungsstand - dann erscheint auch kein Satz. */
    renderList({})

    expect(screen.queryByText('Albumtauglichkeit')).toBeNull()
  })

  it('never dresses the model statement as the human rating badge', () => {
    /* Die Abgrenzung zur Bewertung „Album-würdig": keine Badge, keine Bewertungsfarbe, kein
     * `book`-Symbol - sonst lägen die Entscheidung eines Menschen und die Schätzung eines
     * Modells in derselben Form auf einer Kachel. */
    const { container } = renderList({ albumSuitability: { level: 5, reason: 'Sehr gut.' } })

    const quality = screen.getByRole('group', { name: 'Qualität' })
    expect(quality.querySelector('svg')).toBeNull()
    expect(container.innerHTML).not.toContain('rating-album-worthy')
  })
})
