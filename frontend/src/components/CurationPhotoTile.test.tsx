import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { PhotoOut, RankingOut } from '../api/types'
import { MOTIF_SET } from '../test/motifSetFixture'
import { ALBUM_SUITABILITY_NOT_RATED_TEXT } from '../utils/albumSuitability'
import { CurationPhotoTile } from './CurationPhotoTile'

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
    })),
    album_suitability: { level: 4, reason: 'Alle schauen in die Kamera.' },
    ...overrides,
  }
}

function renderTile(overrides: Partial<PhotoOut> = {}) {
  return render(
    <CurationPhotoTile
      photo={photo(overrides)}
      motifSet={MOTIF_SET}
      motifSetLoading={false}
      motifSetError={undefined}
      onMotifSetRetry={() => {}}
      ownStatus={null}
      rejecting={false}
      onReject={() => {}}
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

  it('adds no second hit area to the tile footer', () => {
    /* Kein Ausklapp-Bedienelement je Kachel: die Fußzeile behält GENAU EINE Trefferfläche
     * (Verwerfen). Der Info-Trigger liegt im Kartenkörper, nicht in der Fußzeile. */
    renderTile({
      album_suitability: { level: 2, reason: 'Eine ziemlich lange Begründung des Modells.' },
    })

    expect(screen.getByRole('button', { name: 'Verwerfen: a.jpg' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /mehr|ausklappen|weiterlesen/i })).toBeNull()
  })
})
