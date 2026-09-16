import { render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { MotifAssessmentOut, MotifStrengthOut } from '../api/types'
import { MOTIF_KEYS, MOTIF_SET } from '../test/motifSetFixture'
import { MotifStrengthSection } from './MotifStrengthSection'

/**
 * specs/features/0427-motive-mit-staerke.md, UI/UX-Abschnitt „components/MotifStrengthList.tsx".
 *
 * Zwei Nachweise tragen mehr als eine Textprüfung:
 *
 * * Das PAAR „noch nicht klassifiziert" gegen „acht Nullen": geprüft über die KARDINALITÄT von
 *   `[data-motif-key]`, nicht über eine Textsuche nach dem Satz - der Satz kann über acht
 *   Nullzeilen stehen, und dann ist er grün und falsch.
 * * Die Zeilenreihenfolge ist die Registry-Reihenfolge, NIE nach Stärke sortiert: acht
 *   gleichnamige Korrekturschalter, die von Foto zu Foto die Position wechseln, laden zum
 *   Fehlklick ein - und ein Fehlklick schreibt hier einen Datenwert.
 */

const CLOUD_ASSESSMENT: MotifAssessmentOut = {
  source: 'cloud',
  provider: 'anthropic',
  excluded_document: false,
  computed_at: '2026-09-12T10:00:00',
}

const LOCAL_ASSESSMENT: MotifAssessmentOut = {
  source: 'local',
  provider: null,
  excluded_document: false,
  computed_at: '2026-09-12T10:00:00',
}

function strengths(overrides: Record<string, Partial<MotifStrengthOut>> = {}): MotifStrengthOut[] {
  return MOTIF_KEYS.map((key) => ({
    key,
    strength: 0,
    correction: null,
    present: false,
    ...(overrides[key] ?? {}),
  }))
}

function renderList(props: Partial<Parameters<typeof MotifStrengthSection>[0]> = {}) {
  const onCorrect = vi.fn()
  const onWithdraw = vi.fn()
  render(
    <MotifStrengthSection
      motifSet={MOTIF_SET}
      assessment={CLOUD_ASSESSMENT}
      motifs={strengths()}
      editable
      onCorrect={onCorrect}
      onWithdraw={onWithdraw}
      pendingMotifKey={null}
      error={null}
      {...props}
    />,
  )
  return { onCorrect, onWithdraw }
}

function rowOf(motifKey: string): HTMLElement {
  const row = document.querySelector(`[data-motif-key="${motifKey}"]`)
  expect(row).not.toBeNull()
  return row as HTMLElement
}

describe('MotifStrengthSection: die Liste', () => {
  it('renders the eight motifs in registry order, not sorted by strength', () => {
    renderList({
      motifs: strengths({
        menschen: { strength: 0.1 },
        detail_stimmung: { strength: 0.99 },
      }),
    })

    const keys = [...document.querySelectorAll('[data-motif-key]')].map((node) =>
      node.getAttribute('data-motif-key'),
    )

    expect(keys).toEqual(MOTIF_KEYS)
  })

  it('names the list for assistive technology', () => {
    renderList()

    expect(screen.getByRole('list', { name: 'Motive' })).toBeTruthy()
  })

  it('shows the display name and the percentage of every motif', () => {
    renderList({ motifs: strengths({ menschen: { strength: 0.42 } }) })

    const row = rowOf('menschen')
    expect(within(row).getByText('Menschen')).toBeTruthy()
    expect(within(row).getByText('42%')).toBeTruthy()
  })

  it('carries the ratio on the bar instead of an inline style', () => {
    renderList({ motifs: strengths({ menschen: { strength: 0.42 } }) })

    const bar = rowOf('menschen').querySelector('progress')
    expect(bar).not.toBeNull()
    expect(bar?.getAttribute('value')).toBe('0.42')
    expect(bar?.getAttribute('max')).toBe('1')
    expect(bar?.getAttribute('aria-hidden')).toBe('true')
    expect(bar?.getAttribute('style')).toBeNull()
  })

  it('drives the rows from the registry, not from the strength rows of the photo', () => {
    // Ein Altwert aus der Laufhistorie erzeugt keine Zeile - er kann hier strukturell nicht
    // durchfallen, und die Reihenfolge bleibt auf jedem Foto dieselbe.
    renderList({
      motifs: [
        { key: 'menschen', strength: 0.5, correction: null, present: true },
        { key: 'unerkannt', strength: 0.9, correction: null, present: true },
      ],
    })

    const keys = [...document.querySelectorAll('[data-motif-key]')].map((node) =>
      node.getAttribute('data-motif-key'),
    )

    expect(keys).toEqual(MOTIF_KEYS)
    expect(within(rowOf('menschen')).getByText('50%')).toBeTruthy()
  })

  it('shows zero for a motif whose strength row is missing entirely', () => {
    // Der Vektor kann unvollstaendig sein - die Liste bleibt achtzeilig.
    renderList({ motifs: [{ key: 'menschen', strength: 0.5, correction: null, present: true }] })

    expect(within(rowOf('tiere')).getByText('0%')).toBeTruthy()
    expect(rowOf('tiere').hasAttribute('data-motif-corrected')).toBe(false)
  })
})

describe('MotifStrengthSection: die vier Fotozustände', () => {
  it('shows a sentence instead of the list when the photo was never classified', () => {
    renderList({ assessment: null })

    expect(document.querySelectorAll('[data-motif-key]')).toHaveLength(0)
    expect(screen.queryByRole('list', { name: 'Motive' })).toBeNull()
    expect(screen.getByText(/Noch nicht klassifiziert/)).toBeTruthy()
  })

  it('offers no correction button at all when the photo was never classified', () => {
    renderList({ assessment: null })

    expect(screen.queryByRole('button', { name: /Trifft zu/ })).toBeNull()
  })

  it('renders differently for an unclassified photo than for eight zeroes', () => {
    // DAS PAAR. Ohne diesen Fall machte ein `?? 0` im Lesepfad aus „noch nicht klassifiziert"
    // acht Nullzeilen, und kein anderer Fall bräche.
    const { unmount } = render(
      <MotifStrengthSection
        motifSet={MOTIF_SET}
        assessment={null}
        motifs={[]}
        editable
        onCorrect={vi.fn()}
        onWithdraw={vi.fn()}
        pendingMotifKey={null}
        error={null}
      />,
    )
    const unassessedMarkup = document.body.innerHTML
    const unassessedRows = document.querySelectorAll('[data-motif-key]').length
    unmount()

    render(
      <MotifStrengthSection
        motifSet={MOTIF_SET}
        assessment={CLOUD_ASSESSMENT}
        motifs={strengths()}
        editable
        onCorrect={vi.fn()}
        onWithdraw={vi.fn()}
        pendingMotifKey={null}
        error={null}
      />,
    )

    expect(unassessedRows).toBe(0)
    expect(document.querySelectorAll('[data-motif-key]')).toHaveLength(MOTIF_KEYS.length)
    expect(document.body.innerHTML).not.toBe(unassessedMarkup)
  })

  it('shows the eight short bars without a computed "nothing recognised" verdict', () => {
    // Dafür bräuchte die Oberfläche eine Schwelle, und die schafft diese Story ab. Geprüft wird
    // die LISTE selbst - der Glossartext darf das Wort tragen, die Zeilen nicht.
    renderList({ motifs: strengths() })

    const list = screen.getByRole('list', { name: 'Motive' })
    expect(document.querySelectorAll('[data-motif-key]')).toHaveLength(MOTIF_KEYS.length)
    expect(within(list).getAllByText('0%')).toHaveLength(MOTIF_KEYS.length)
    expect(list.textContent ?? '').not.toMatch(/nichts erkannt/i)
    expect(screen.queryByText(/Noch nicht klassifiziert/)).toBeNull()
  })

  it('names the cloud basis with provider and time', () => {
    renderList()

    expect(screen.getByText(/Grundlage: Cloud-Klassifizierung \(Anthropic\)/)).toBeTruthy()
  })

  it('names the local basis and that it cannot judge every motif', () => {
    renderList({ assessment: LOCAL_ASSESSMENT })

    expect(screen.getByText(/Grundlage: lokale Erkennung/)).toBeTruthy()
    expect(screen.getByText(/kann nicht jedes Motiv beurteilen/)).toBeTruthy()
  })

  it('shows the reason instead of a bar for a locally unassessable motif', () => {
    // Ein `0 %` wäre dort die Aussage „nicht zu sehen" statt „nicht angesehen".
    renderList({ assessment: LOCAL_ASSESSMENT })

    const row = rowOf('aktivitaet')
    expect(within(row).getByText('lokal nicht beurteilbar')).toBeTruthy()
    expect(within(row).queryByText('0%')).toBeNull()
    expect(row.querySelector('progress')).toBeNull()
  })

  it('keeps the buttons of a locally unassessable motif operable', () => {
    renderList({ assessment: LOCAL_ASSESSMENT })

    const row = rowOf('aktivitaet')
    const applies = within(row).getByRole('button', { name: 'Trifft zu: Aktivität' })
    expect(applies.hasAttribute('disabled')).toBe(false)
  })

  it('shows bar and number for a locally ASSESSABLE motif on a local basis', () => {
    renderList({
      assessment: LOCAL_ASSESSMENT,
      motifs: strengths({ menschen: { strength: 0.3 } }),
    })

    const row = rowOf('menschen')
    expect(within(row).getByText('30%')).toBeTruthy()
    expect(row.querySelector('progress')).not.toBeNull()
  })

  it('shows bar and number on a CLOUD basis even for a locally unassessable motif', () => {
    // Der Hinweis hängt an der Grundlage, nicht am Motiv: das Modell hat es beurteilt.
    renderList({ motifs: strengths({ aktivitaet: { strength: 0.7 } }) })

    const row = rowOf('aktivitaet')
    expect(within(row).getByText('70%')).toBeTruthy()
    expect(within(row).queryByText('lokal nicht beurteilbar')).toBeNull()
  })

  it('states the exclusion first and shows the list read-only', () => {
    renderList({
      assessment: { ...CLOUD_ASSESSMENT, excluded_document: true },
      motifs: strengths({ menschen: { strength: 0.9 } }),
    })

    expect(screen.getByText(/Als Dokument oder Bildschirmabbildung erkannt/)).toBeTruthy()
    expect(screen.getByText(/lässt sich nicht von Hand ändern/)).toBeTruthy()
    expect(document.querySelectorAll('[data-motif-key]')).toHaveLength(MOTIF_KEYS.length)
    expect(screen.queryByRole('button', { name: /Trifft zu/ })).toBeNull()
  })

  it('names the way back out of the exclusion', () => {
    renderList({ assessment: { ...CLOUD_ASSESSMENT, excluded_document: true } })

    expect(screen.getByText(/neuer Klassifizierungslauf beurteilt das Foto erneut/)).toBeTruthy()
  })

  it('renders no disabled correction button for an excluded photo', () => {
    // Kein deaktivierter Schalter, nach dem niemand suchen soll.
    renderList({ assessment: { ...CLOUD_ASSESSMENT, excluded_document: true } })

    expect(screen.queryAllByRole('button', { name: /Trifft/ })).toHaveLength(0)
  })
})

describe('MotifStrengthSection: die Korrektur', () => {
  it('offers both directions per row with the motif name in the accessible name', () => {
    // Acht gleichnamige Schaltflächen sind sonst per Tastatur nicht auseinanderzuhalten.
    renderList()

    const row = rowOf('menschen')
    expect(within(row).getByRole('button', { name: 'Trifft zu: Menschen' })).toBeTruthy()
    expect(within(row).getByRole('button', { name: 'Trifft nicht zu: Menschen' })).toBeTruthy()
  })

  it('reports both directions as unpressed without a correction', () => {
    renderList()

    const row = rowOf('menschen')
    for (const name of ['Trifft zu: Menschen', 'Trifft nicht zu: Menschen']) {
      expect(within(row).getByRole('button', { name }).getAttribute('aria-pressed')).toBe('false')
    }
  })

  it('marks the applying direction as pressed', () => {
    renderList({ motifs: strengths({ menschen: { strength: 1, correction: true } }) })

    const row = rowOf('menschen')
    expect(
      within(row).getByRole('button', { name: 'Trifft zu: Menschen' }).getAttribute('aria-pressed'),
    ).toBe('true')
    expect(
      within(row)
        .getByRole('button', { name: 'Trifft nicht zu: Menschen' })
        .getAttribute('aria-pressed'),
    ).toBe('false')
  })

  it('marks the rejecting direction as pressed', () => {
    renderList({ motifs: strengths({ menschen: { strength: 0, correction: false } }) })

    const row = rowOf('menschen')
    expect(
      within(row)
        .getByRole('button', { name: 'Trifft nicht zu: Menschen' })
        .getAttribute('aria-pressed'),
    ).toBe('true')
  })

  it('replaces the percentage with the correction word', () => {
    // Die überstimmte Modellzahl steht NICHT daneben.
    renderList({ motifs: strengths({ menschen: { strength: 1, correction: true } }) })

    const row = rowOf('menschen')
    expect(within(row).getByText('Trifft zu (korrigiert)')).toBeTruthy()
    expect(within(row).queryByText('100%')).toBeNull()
    expect(within(row).queryByText('90%')).toBeNull()
  })

  it('uses the rejecting word for a rejecting correction', () => {
    renderList({ motifs: strengths({ menschen: { strength: 0, correction: false } }) })

    expect(within(rowOf('menschen')).getByText('Trifft nicht zu (korrigiert)')).toBeTruthy()
  })

  it('marks the corrected row in the DOM', () => {
    renderList({
      motifs: strengths({
        menschen: { strength: 1, correction: true },
        tiere: { strength: 0, correction: false },
      }),
    })

    expect(rowOf('menschen').getAttribute('data-motif-corrected')).toBe('applies')
    expect(rowOf('tiere').getAttribute('data-motif-corrected')).toBe('rejected')
    expect(rowOf('landschaft').hasAttribute('data-motif-corrected')).toBe(false)
  })

  it('fills the bar of an applying correction and empties it for a rejecting one', () => {
    renderList({
      motifs: strengths({
        menschen: { strength: 1, correction: true },
        tiere: { strength: 0, correction: false },
      }),
    })

    expect(rowOf('menschen').querySelector('progress')?.getAttribute('value')).toBe('1')
    expect(rowOf('tiere').querySelector('progress')?.getAttribute('value')).toBe('0')
  })

  it('offers the withdrawal only while a correction exists', () => {
    renderList({ motifs: strengths({ menschen: { strength: 1, correction: true } }) })

    expect(
      within(rowOf('menschen')).getByRole('button', { name: 'Zurücknehmen: Menschen' }),
    ).toBeTruthy()
    expect(within(rowOf('tiere')).queryByRole('button', { name: 'Zurücknehmen: Tiere' })).toBeNull()
  })

  it('reports a pointless correction as corrected as well', () => {
    // `applies=false` auf einem Motiv, dessen Grundlage schon 0 ist: die Zeile zeigt das
    // Korrekturwort, obwohl sich keine Zahl bewegt.
    renderList({ motifs: strengths({ menschen: { strength: 0, correction: false } }) })

    const row = rowOf('menschen')
    expect(row.getAttribute('data-motif-corrected')).toBe('rejected')
    expect(within(row).getByText('Trifft nicht zu (korrigiert)')).toBeTruthy()
  })

  it('calls the handler with motif key and direction', () => {
    const { onCorrect } = renderList()

    within(rowOf('tiere')).getByRole('button', { name: 'Trifft zu: Tiere' }).click()
    within(rowOf('tiere')).getByRole('button', { name: 'Trifft nicht zu: Tiere' }).click()

    expect(onCorrect).toHaveBeenNthCalledWith(1, 'tiere', true)
    expect(onCorrect).toHaveBeenNthCalledWith(2, 'tiere', false)
  })

  it('calls the withdrawal handler with the motif key', () => {
    const { onWithdraw } = renderList({
      motifs: strengths({ menschen: { strength: 1, correction: true } }),
    })

    within(rowOf('menschen')).getByRole('button', { name: 'Zurücknehmen: Menschen' }).click()

    expect(onWithdraw).toHaveBeenCalledWith('menschen')
  })

  it('renders no button at all when the list is read-only', () => {
    renderList({ editable: false })

    expect(screen.queryAllByRole('button')).toHaveLength(0)
    expect(document.querySelectorAll('[data-motif-key]')).toHaveLength(MOTIF_KEYS.length)
  })

  it('still shows the values when the list is read-only', () => {
    renderList({ editable: false, motifs: strengths({ menschen: { strength: 0.6 } }) })

    expect(within(rowOf('menschen')).getByText('60%')).toBeTruthy()
  })
})

describe('MotifStrengthSection: die Zustände', () => {
  it('disables only the buttons of the row whose correction is running', () => {
    renderList({ pendingMotifKey: 'menschen' })

    const pending = rowOf('menschen')
    const other = rowOf('tiere')
    expect(
      within(pending).getByRole('button', { name: 'Trifft zu: Menschen' }).hasAttribute('disabled'),
    ).toBe(true)
    expect(
      within(other).getByRole('button', { name: 'Trifft zu: Tiere' }).hasAttribute('disabled'),
    ).toBe(false)
  })

  it('shows eight skeleton rows while the motif set is loading', () => {
    render(
      <MotifStrengthSection
        motifSet={undefined}
        motifSetLoading
        assessment={CLOUD_ASSESSMENT}
        motifs={strengths()}
        editable
        onCorrect={vi.fn()}
        onWithdraw={vi.fn()}
        pendingMotifKey={null}
        error={null}
      />,
    )

    expect(screen.getAllByTestId('motif-skeleton-row')).toHaveLength(8)
    expect(screen.queryByRole('progressbar')).toBeNull()
  })

  it('shows an alert with a retry action when the motif set failed to load', () => {
    // Keine Liste mit Rohschlüsseln.
    render(
      <MotifStrengthSection
        motifSet={undefined}
        motifSetError="Motive konnten nicht geladen werden."
        onMotifSetRetry={vi.fn()}
        assessment={CLOUD_ASSESSMENT}
        motifs={strengths()}
        editable
        onCorrect={vi.fn()}
        onWithdraw={vi.fn()}
        pendingMotifKey={null}
        error={null}
      />,
    )

    expect(screen.getByRole('button', { name: 'Erneut versuchen' })).toBeTruthy()
    expect(document.querySelectorAll('[data-motif-key]')).toHaveLength(0)
  })

  it('shows the backend detail and the motif name when a correction failed', () => {
    // Der `detail` steht WOERTLICH als Textknoten, und die Meldung sagt, welche Zeile es war.
    renderList({
      error: { motifKey: 'menschen', detail: 'Bitte erneut versuchen.' },
    })

    const alert = screen.getByRole('alert')
    expect(within(alert).getByText('Bitte erneut versuchen.')).toBeTruthy()
    expect(alert.textContent ?? '').toContain('Menschen')
  })

  it('offers no retry button for a failed correction', () => {
    // Die Schaltfläche der Zeile IST die Wiederholung - ein zweites „Erneut versuchen" wären
    // zwei Bedienelemente für eine Aktion.
    renderList({ error: { motifKey: 'menschen', detail: 'Bitte erneut versuchen.' } })

    expect(screen.queryByRole('button', { name: 'Erneut versuchen' })).toBeNull()
  })
})

describe('MotifStrengthSection: das Glossar', () => {
  it('carries exactly one collapsed details element at the end of the list', () => {
    renderList()

    const details = document.querySelectorAll('details')
    expect(details).toHaveLength(1)
    expect((details[0] as HTMLDetailsElement).open).toBe(false)
    expect(screen.getByText('Was die acht Motive bedeuten')).toBeTruthy()
  })

  it('explains every motif with its definition and its delimitation', () => {
    renderList()

    const glossary = document.querySelector('details') as HTMLElement
    for (const item of MOTIF_SET.items) {
      expect(within(glossary).getByText(item.display_name)).toBeTruthy()
      expect(within(glossary).getByText(item.definition)).toBeTruthy()
      expect(within(glossary).getByText(`Abgrenzung: ${item.delimitation}`)).toBeTruthy()
    }
  })

  it('renders the registry text as plain text nodes', () => {
    // SICHERHEIT (S19): nie über `dangerouslySetInnerHTML`, nie als HTML-String-Prop.
    renderList({
      motifSet: {
        ...MOTIF_SET,
        items: [
          {
            key: 'menschen',
            display_name: '<img src=x onerror=alert(1)>',
            definition: '<script>alert(2)</script>',
            delimitation: '<b>fett</b>',
            locally_assessable: true,
          },
        ],
      },
      motifs: [{ key: 'menschen', strength: 0.5, correction: null, present: true }],
    })

    expect(document.querySelector('img')).toBeNull()
    expect(document.querySelector('script')).toBeNull()
    expect(document.querySelector('details b')).toBeNull()
    expect(screen.getAllByText('<img src=x onerror=alert(1)>').length).toBeGreaterThan(0)
  })

  it('has no info trigger per row', () => {
    // Acht zusätzliche Trefferflächen für Nachschlagetext - und die Liste steckt ihrerseits in
    // einem Popover, in dem kein zweites Panel zulässig ist.
    renderList()

    expect(screen.queryAllByRole('button', { name: /Erklärung/ })).toHaveLength(0)
  })

  it('shows no band word anywhere outside the statistics table', () => {
    // Ein Bandwort neben dem Einzelwert eines Fotos lehrte den Nutzer genau die
    // Zugehörigkeitsschwelle, die diese Story abschafft.
    renderList({ motifs: strengths({ menschen: { strength: 0.95 } }) })

    const text = document.body.textContent ?? ''
    expect(text).not.toMatch(/\bstark\b/i)
    expect(text).not.toMatch(/\bmittel\b/i)
    expect(text).not.toMatch(/\bschwach\b/i)
  })
})
