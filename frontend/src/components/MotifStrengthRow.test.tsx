import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import * as motifsApi from '../api/motifs'
import type { MotifAssessmentOut, MotifStrengthOut } from '../api/types'
import { MOTIF_SET } from '../test/motifSetFixture'
import { MotifStrengthRow } from './MotifStrengthRow'
import { MotifStrengthSection } from './MotifStrengthSection'

vi.mock('../api/motifs')

/*
 * specs/features/0531-kuratierung-grossansicht.md, AK8 - die schreibgeschuetzte Motivreihe in der
 * Kopfzeile der Grossansicht.
 */

const CLOUD: MotifAssessmentOut = {
  source: 'cloud',
  provider: 'anthropic',
  excluded_document: false,
  computed_at: '2026-09-12T10:00:00',
}

const LOCAL: MotifAssessmentOut = { ...CLOUD, source: 'local', provider: null }

/* Werte weder nach Registry noch nach Groesse geordnet: Eine nach Staerke sortierte Reihe fiele
   hier ebenso auf wie eine alphabetische. */
const MOTIFS: MotifStrengthOut[] = [
  { key: 'tiere', strength: 0.91, correction: null, present: true },
  { key: 'menschen', strength: 0.12, correction: null, present: false },
  { key: 'essen_trinken', strength: 0.55, correction: true, present: true },
  { key: 'landschaft', strength: 0.4, correction: null, present: false },
  { key: 'stadt_strasse', strength: 0.73, correction: false, present: false },
  { key: 'bauwerk_sehenswuerdigkeit', strength: 0, correction: null, present: false },
  { key: 'aktivitaet', strength: 0.3, correction: null, present: false },
  { key: 'detail_stimmung', strength: 0.6, correction: null, present: true },
]

function renderWithQuery(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>)
}

describe('MotifStrengthRow', () => {
  beforeEach(() => {
    vi.mocked(motifsApi.listMotifs).mockReset()
    vi.mocked(motifsApi.listMotifs).mockResolvedValue(MOTIF_SET)
  })

  it('shows eight entries in registry order, each named "{Motiv}: {Wert}"', async () => {
    renderWithQuery(<MotifStrengthRow assessment={CLOUD} motifs={MOTIFS} />)

    const list = await screen.findByRole('list', { name: 'Motive' })
    const items = within(list).getAllByRole('listitem')
    expect(items).toHaveLength(8)
    expect(items.map((item) => within(item).getByRole('img').getAttribute('aria-label'))).toEqual([
      'Menschen: 12%',
      'Landschaft: 40%',
      'Bauwerk und Sehenswürdigkeit: 0%',
      'Stadt und Straße: Trifft nicht zu (korrigiert)',
      'Tiere: 91%',
      'Essen und Trinken: Trifft zu (korrigiert)',
      'Aktivität: 30%',
      'Detail und Stimmung: 60%',
    ])
  })

  /* Ein Wert an zwei Stellen (Spec 0490): Reihe und Bereich der Detailseite muessen fuer dasselbe
     Foto dieselben Namen tragen - mit Korrektur und mit „lokal nicht beurteilbar". */
  it('names every motif exactly like the motif section of the detail page', async () => {
    renderWithQuery(
      <>
        <div data-testid="row">
          <MotifStrengthRow assessment={LOCAL} motifs={MOTIFS} />
        </div>
        <div data-testid="section">
          <MotifStrengthSection
            motifSet={MOTIF_SET}
            assessment={LOCAL}
            motifs={MOTIFS}
            editable={false}
          />
        </div>
      </>,
    )

    const row = await within(screen.getByTestId('row')).findByRole('list', { name: 'Motive' })
    const rowNames = within(row)
      .getAllByRole('img')
      .map((element) => element.getAttribute('aria-label'))
    const sectionNames = within(screen.getByTestId('section'))
      .getAllByRole('button')
      .filter((button) => button.hasAttribute('data-motif-key'))
      .map((button) => button.getAttribute('aria-label'))

    expect(rowNames).toContain('Aktivität: lokal nicht beurteilbar')
    expect(rowNames).toEqual(sectionNames)
  })

  it('offers nothing focusable and no title', async () => {
    const { container } = renderWithQuery(<MotifStrengthRow assessment={CLOUD} motifs={MOTIFS} />)

    await screen.findByRole('list', { name: 'Motive' })
    expect(
      container.querySelectorAll('button, a[href], input, select, textarea, [tabindex]'),
    ).toHaveLength(0)
    expect(container.querySelectorAll('[title]')).toHaveLength(0)
  })

  it('shows placeholders and no list while the motif set loads', () => {
    vi.mocked(motifsApi.listMotifs).mockReturnValue(new Promise(() => {}))

    renderWithQuery(<MotifStrengthRow assessment={CLOUD} motifs={MOTIFS} />)

    expect(screen.getByRole('status', { name: 'Motive werden geladen' })).toBeInTheDocument()
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
  })

  it('shows an alert with a retry that loads the motif set again', async () => {
    vi.mocked(motifsApi.listMotifs)
      .mockRejectedValueOnce(new ApiError(500, 'kaputt'))
      .mockResolvedValueOnce(MOTIF_SET)

    renderWithQuery(<MotifStrengthRow assessment={CLOUD} motifs={MOTIFS} />)

    const alert = await screen.findByRole('alert')
    fireEvent.click(within(alert).getByRole('button', { name: 'Erneut versuchen' }))

    await waitFor(() => expect(motifsApi.listMotifs).toHaveBeenCalledTimes(2))
    expect(await screen.findByRole('list', { name: 'Motive' })).toBeInTheDocument()
  })

  it('shows the sentence instead of the list for an unclassified photo', async () => {
    renderWithQuery(<MotifStrengthRow assessment={null} motifs={[]} />)

    expect(await screen.findByText(/^Noch nicht klassifiziert — /)).toBeInTheDocument()
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
  })

  it('keeps the list unchanged and adds no sentence for an excluded document', async () => {
    renderWithQuery(
      <MotifStrengthRow assessment={{ ...CLOUD, excluded_document: true }} motifs={MOTIFS} />,
    )

    const list = await screen.findByRole('list', { name: 'Motive' })
    expect(within(list).getAllByRole('listitem')).toHaveLength(8)
    expect(screen.queryByText(/Dokument/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Noch nicht klassifiziert/)).not.toBeInTheDocument()
  })
})
