import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { MotifAssessmentOut, MotifStrengthOut } from '../api/types'
import { MOTIF_KEYS, MOTIF_SET } from '../test/motifSetFixture'
import { MotifStrengthSection } from './MotifStrengthSection'

/**
 * specs/features/0490-motivstaerke-kompakt.md — die Reihe aus acht Fuellstandssymbolen mit der
 * aufklappenden Detailzeile.
 *
 * Vier Nachweise tragen mehr als eine Textpruefung:
 *
 * * Das PAAR „noch nicht klassifiziert" gegen „acht Nullen": geprueft ueber die KARDINALITAET von
 *   `[data-motif-key]`, nicht ueber eine Textsuche nach dem Satz - der Satz kann ueber acht
 *   leeren Symbolen stehen, und dann ist er gruen und falsch.
 * * Die Reihenfolge ist die Registry-Reihenfolge, NIE nach Staerke sortiert: acht gleichartige
 *   Schaltflaechen, die von Foto zu Foto die Position wechseln, laden zum Fehlklick ein - und ein
 *   Fehlklick schreibt hier ueber die Detailzeile einen Datenwert.
 * * Jede Abwesenheitszusage ueber einen Korrekturschalter braucht den Klick auf ein Symbol VOR
 *   der negativen Assertion. Ohne ihn bestuende sie auch dann, wenn nach dem Aufklappen sehr wohl
 *   Schalter erschienen.
 * * Die Werte stehen im zugaenglichen NAMEN der Schaltflaechen. Eine Zusage, die nur
 *   `document.body.textContent` liest, erfasst sie nicht mehr.
 *
 * Die Bandgrenzen stehen als `MOTIF_SET.strength_bands`, nie als Dezimalliteral - sonst prueften
 * die Faelle die Kalibrierung statt die Stufung.
 */

const BANDS = MOTIF_SET.strength_bands

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

function renderSection(props: Partial<Parameters<typeof MotifStrengthSection>[0]> = {}) {
  const onCorrect = vi.fn()
  const onWithdraw = vi.fn()
  const view = render(
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
  return { onCorrect, onWithdraw, view }
}

/** Die Schaltflaeche eines Motivs - der Traeger von `data-motif-key`. */
function symbolOf(motifKey: string): HTMLElement {
  const button = document.querySelector(`[data-motif-key="${motifKey}"]`)
  expect(button).not.toBeNull()
  return button as HTMLElement
}

/** Die Detailzeile ueber die `aria-controls`-Verknuepfung - nie ueber einen eigenen Testhaken:
 * so ist zugleich geprueft, dass die Verknuepfung ueberhaupt irgendwohin zeigt. */
function detailRow(motifKey = MOTIF_KEYS[0]): HTMLElement {
  const id = symbolOf(motifKey).getAttribute('aria-controls')
  expect(id).not.toBeNull()
  const row = document.getElementById(id!)
  expect(row, `Detailzeile ${id}`).not.toBeNull()
  return row as HTMLElement
}

function accessibleNames(): string[] {
  return [...document.querySelectorAll('[data-motif-key]')].map(
    (node) => node.getAttribute('aria-label') ?? '',
  )
}

describe('MotifStrengthSection: die Reihe', () => {
  it('shows the eight motifs in registry order, not sorted by strength', () => {
    renderSection({
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
    // Zwei Abwesenheitszusagen anderer Ansichten (PhotoGridPage, SelectionPhotoTile) haengen an
    // genau diesem Namen; faellt er weg, werden beide still bedeutungslos.
    renderSection()

    expect(screen.getByRole('list', { name: 'Motive' })).toBeTruthy()
  })

  it('carries exactly eight list items, each with one button', () => {
    renderSection()

    const list = screen.getByRole('list', { name: 'Motive' })
    const items = within(list).getAllByRole('listitem')
    expect(items).toHaveLength(MOTIF_KEYS.length)
    for (const item of items) {
      expect(within(item).getAllByRole('button')).toHaveLength(1)
    }
  })

  it('shows no bar anywhere in the motif section', () => {
    // AK1: Die Balkenliste bleibt nirgends stehen.
    renderSection({ motifs: strengths({ menschen: { strength: 0.42 } }) })

    expect(document.querySelector('progress')).toBeNull()
    expect(screen.queryByRole('progressbar')).toBeNull()
  })

  it('draws one filled symbol per motif', () => {
    renderSection()

    for (const key of MOTIF_KEYS) {
      expect(symbolOf(key).querySelector('[data-motif-layer="outline"]'), key).not.toBeNull()
      expect(symbolOf(key).querySelector('[data-motif-layer="fill"]'), key).not.toBeNull()
    }
  })

  it.each([
    ['menschen', 'user-round'],
    ['landschaft', 'mountain-snow'],
    ['bauwerk_sehenswuerdigkeit', 'landmark'],
    ['stadt_strasse', 'building-2'],
    ['tiere', 'paw-print'],
    ['essen_trinken', 'utensils'],
    ['aktivitaet', 'footprints'],
    ['detail_stimmung', 'sparkles'],
  ])('gives %s the icon %s', (motifKey, iconName) => {
    renderSection()

    expect(symbolOf(motifKey).querySelector(`[data-icon="${iconName}"]`)).not.toBeNull()
  })

  it('names every symbol with its motif and its value', () => {
    // Damit steht JEDE Angabe auch ohne Zeigen und ohne Aufklappen zur Verfuegung (AK4).
    renderSection({ motifs: strengths({ menschen: { strength: 0.42 } }) })

    expect(screen.getByRole('button', { name: 'Menschen: 42%' })).toBeTruthy()
  })

  it('drives the row from the registry, not from the strength rows of the photo', () => {
    renderSection({
      motifs: [
        { key: 'menschen', strength: 0.5, correction: null, present: true },
        { key: 'unerkannt', strength: 0.9, correction: null, present: true },
      ],
    })

    const keys = [...document.querySelectorAll('[data-motif-key]')].map((node) =>
      node.getAttribute('data-motif-key'),
    )

    expect(keys).toEqual(MOTIF_KEYS)
    expect(symbolOf('menschen').getAttribute('aria-label')).toBe('Menschen: 50%')
  })

  it('shows zero for a motif whose strength row is missing entirely', () => {
    // Der Vektor darf unvollstaendig sein - die Reihe bleibt achtteilig.
    renderSection({ motifs: [{ key: 'menschen', strength: 0.5, correction: null, present: true }] })

    expect(symbolOf('tiere').getAttribute('aria-label')).toBe('Tiere: 0%')
    expect(symbolOf('tiere').hasAttribute('data-motif-corrected')).toBe(false)
  })

  it('takes the fill height from the same rounded percentage as the text', () => {
    // AK4: Fuellhoehe und angezeigter Wert koennen nicht auseinanderlaufen. Der absichernde Fall
    // ist eine Staerke GROESSER NULL, die auf 0 % rundet - waere die Hoehe anders gerundet,
    // zeigte das Symbol eine Fuellung, die die Zahl nicht nennt.
    renderSection({
      motifs: strengths({ menschen: { strength: 0.426 }, tiere: { strength: 0.004 } }),
    })

    expect(symbolOf('menschen').getAttribute('aria-label')).toBe('Menschen: 43%')
    expect(
      (
        symbolOf('menschen').querySelector('[data-motif-layer="fill"]') as HTMLElement
      ).style.getPropertyValue('--motif-fill'),
    ).toBe('43%')
    expect(symbolOf('tiere').getAttribute('aria-label')).toBe('Tiere: 0%')
    expect(
      (
        symbolOf('tiere').querySelector('[data-motif-layer="fill"]') as HTMLElement
      ).style.getPropertyValue('--motif-fill'),
    ).toBe('0%')
  })

  it.each([
    ['strong', BANDS.strong, 'text-status-success'],
    ['medium', BANDS.medium, 'text-status-running'],
    ['weak', BANDS.medium / 2, 'text-status-failed'],
  ])('colours a %s motif with its band colour', (_step, strength, utility) => {
    renderSection({ motifs: strengths({ menschen: { strength } }) })

    const fill = symbolOf('menschen').querySelector('[data-motif-layer="fill"]') as HTMLElement
    expect(fill.className).toContain(utility)
  })

  it('never carries text from the strength field into the inline style', () => {
    // SICHERHEIT (specs/architecture/0003-securitykonzept.md): Die Fuellhoehe ist die einzige
    // Stelle des Frontends, die einen gerechneten Wert ueber eine CSS-CUSTOM-PROPERTY traegt. Die
    // Konzeptzeile erlaubt das nur, solange der Traeger eine ZAHL ist und nicht aus einem
    // API-Feld zusammengesetzt wird. Hier kommt das Feld feindlich herein - wie es eine
    // fehlerhafte oder manipulierte Antwort liefern koennte, entgegen dem Typ.
    const feindlich = 'red;--x:url(javascript:alert(1))' as unknown as number
    renderSection({
      motifs: [{ key: 'menschen', strength: feindlich, correction: null, present: true }],
    })

    const fill = symbolOf('menschen').querySelector('[data-motif-layer="fill"]') as HTMLElement
    const wert = fill.style.getPropertyValue('--motif-fill')
    // `Math.round` schliesst den Wert mechanisch: aus einer Nicht-Zahl wird `NaN`, nie der Text.
    expect(wert).toMatch(/^(\d+|NaN)%$/)
    expect(wert).not.toContain('url(')
    expect(wert).not.toContain(';')
    // Und auch der sichtbare Text traegt ihn nicht - dieselbe eine Rundungsstelle.
    expect(document.body.innerHTML).not.toContain('javascript:')
  })

  it('leaves a motif at zero without any fill at all', () => {
    renderSection()

    const fill = symbolOf('menschen').querySelector('[data-motif-layer="fill"]') as HTMLElement
    expect(fill.style.getPropertyValue('--motif-fill')).toBe('0%')
  })
})

describe('MotifStrengthSection: die Detailzeile', () => {
  it('shows a prompt instead of an empty area while nothing is chosen', () => {
    // Die Zeile behaelt ihre Hoehe - die Reihe springt beim ersten Klick nicht.
    renderSection()

    expect(within(detailRow()).getByText(/Symbol antippen/)).toBeTruthy()
  })

  it('keeps the row in the document even while nothing is chosen', () => {
    // `aria-controls` zeigt nie ins Leere.
    renderSection()

    for (const key of MOTIF_KEYS) {
      expect(symbolOf(key).getAttribute('aria-controls')).toBe(detailRow().id)
    }
  })

  it('reports every symbol as collapsed while nothing is pinned', () => {
    renderSection()

    for (const key of MOTIF_KEYS) {
      expect(symbolOf(key).getAttribute('aria-expanded'), key).toBe('false')
    }
  })

  it('opens the row with full name and exact value on click', async () => {
    const user = userEvent.setup()
    renderSection({ motifs: strengths({ menschen: { strength: 0.42 } }) })

    await user.click(symbolOf('menschen'))

    const row = detailRow()
    expect(within(row).getByText('Menschen')).toBeTruthy()
    expect(within(row).getByText('42%')).toBeTruthy()
    expect(symbolOf('menschen').getAttribute('aria-expanded')).toBe('true')
  })

  it('unpins the row again on a second click on the same symbol', async () => {
    // Der Klick loest die Anheftung. Dass die Zeile danach WEITER steht, solange der Zeiger auf
    // dem Symbol bleibt, ist kein Rest der Anheftung, sondern AK10 (Zeigen blendet ein) - und
    // genau deshalb ist der Nachweis zweiteilig: erst `aria-expanded`, dann das Verlassen.
    const user = userEvent.setup()
    renderSection()

    await user.click(symbolOf('menschen'))
    await user.click(symbolOf('menschen'))
    expect(symbolOf('menschen').getAttribute('aria-expanded')).toBe('false')

    await user.unhover(symbolOf('menschen'))
    expect(within(detailRow()).getByText(/Symbol antippen/)).toBeTruthy()
  })

  it('switches the row to the other motif on a click on another symbol', async () => {
    const user = userEvent.setup()
    renderSection({ motifs: strengths({ tiere: { strength: 0.8 } }) })

    await user.click(symbolOf('menschen'))
    await user.click(symbolOf('tiere'))

    expect(symbolOf('menschen').getAttribute('aria-expanded')).toBe('false')
    expect(symbolOf('tiere').getAttribute('aria-expanded')).toBe('true')
    expect(within(detailRow()).getByText('Tiere')).toBeTruthy()
  })

  it('shows name and value on hover, without a click', async () => {
    // AK10: Zeigen ERGAENZT.
    const user = userEvent.setup()
    renderSection({ motifs: strengths({ landschaft: { strength: 0.6 } }) })

    await user.hover(symbolOf('landschaft'))

    const row = detailRow()
    expect(within(row).getByText('Landschaft')).toBeTruthy()
    expect(within(row).getByText('60%')).toBeTruthy()
  })

  it('marks the pinned symbol visibly, not only for assistive technology', async () => {
    // AK6 „das geoeffnete Symbol ist als solches ausgezeichnet": `aria-expanded` allein traegt das
    // nur fuer assistive Technik. Ohne sichtbares Merkmal ist am Bildschirm nicht zu sehen, WELCHES
    // der acht Symbole zu der Zeile darunter gehoert.
    const user = userEvent.setup()
    renderSection()

    expect(symbolOf('menschen').className).not.toContain('bg-overlay')

    await user.click(symbolOf('menschen'))

    expect(symbolOf('menschen').className).toContain('bg-overlay')
    expect(symbolOf('tiere').className).not.toContain('bg-overlay')
  })

  it('does not mark a merely hovered symbol as pinned', async () => {
    // Dieselbe Trennung wie bei `aria-expanded`: Zeigen blendet die Zeile ein, heftet aber nichts
    // an - eine Markierung unter dem Zeiger behauptete einen Zustand, der nicht besteht.
    const user = userEvent.setup()
    renderSection()

    await user.hover(symbolOf('menschen'))

    expect(symbolOf('menschen').className).not.toContain('bg-overlay')
  })

  it('does not report a merely hovered symbol as expanded', () => {
    // `aria-expanded` folgt NUR dem Anheften: ein Zeigen ist keine Zustandsaenderung, die
    // assistive Technik ansagen soll.
    const user = userEvent.setup()
    renderSection()

    return user.hover(symbolOf('menschen')).then(() => {
      expect(symbolOf('menschen').getAttribute('aria-expanded')).toBe('false')
    })
  })

  /**
   * Tabbt weiter, bis das genannte Symbol den Fokus hat - der ECHTE Tastaturweg, statt
   * `element.focus()` von aussen zu rufen (das liefe zudem ausserhalb von `act()`).
   *
   * Bewusst „bis erreicht" statt „n-mal": Wo der Fokus startet, haengt davon ab, was der Fall
   * vorher getan hat - ein Klick laesst ihn auf dem geklickten Symbol stehen. Eine feste
   * Schrittzahl landete dann still auf dem falschen Symbol.
   */
  async function tabToSymbol(user: ReturnType<typeof userEvent.setup>, motifKey: string) {
    for (let schritt = 0; schritt < MOTIF_KEYS.length * 2; schritt += 1) {
      await user.tab()
      if (document.activeElement?.getAttribute('data-motif-key') === motifKey) {
        return
      }
    }
    throw new Error(`Symbol ${motifKey} per Tabulator nicht erreichbar`)
  }

  it('shows name and value on keyboard focus, like on hover', async () => {
    // Ein sehender Tastaturnutzer bekommt sonst beim Durchtabben nichts zu sehen: Der zugaengliche
    // Name traegt zwar alle Angaben, ist aber genau fuer ihn unsichtbar.
    const user = userEvent.setup()
    renderSection({ motifs: strengths({ landschaft: { strength: 0.6 } }) })

    await tabToSymbol(user, 'landschaft')

    const row = detailRow()
    expect(within(row).getByText('Landschaft')).toBeTruthy()
    expect(within(row).getByText('60%')).toBeTruthy()

    // Weitertabben nimmt die Vorschau mit - sie haengt am Fokus, nicht an einem Rest.
    await user.tab()
    expect(within(detailRow()).queryByText('Landschaft')).toBeNull()
  })

  it('does not report a merely focused symbol as expanded', async () => {
    // `aria-expanded` folgt AUSSCHLIESSLICH dem Anheften. Folgte es dem Fokus, saehe assistive
    // Technik beim blossen Durchtabben acht aufklappende Bereiche, von denen keiner offen ist.
    const user = userEvent.setup()
    renderSection()

    await tabToSymbol(user, 'menschen')

    expect(symbolOf('menschen').getAttribute('aria-expanded')).toBe('false')
    expect(symbolOf('menschen').className).not.toContain('bg-overlay')
  })

  it('lets a pinned symbol survive keyboard focus on another one', async () => {
    // Dieselbe Vorrangregel wie beim Zeigen - sonst zoege der Fokus die Zeile vom angehefteten
    // Symbol weg, waehrend man zu dessen Korrekturschaltern tabbt.
    const user = userEvent.setup()
    renderSection({ motifs: strengths({ menschen: { strength: 0.42 }, tiere: { strength: 0.8 } }) })

    await user.click(symbolOf('menschen'))
    await tabToSymbol(user, 'tiere')

    expect(within(detailRow()).getByText('Menschen')).toBeTruthy()
    expect(within(detailRow()).queryByText('Tiere')).toBeNull()
  })

  it('lets a pinned symbol survive hovering another one', async () => {
    // AK10: Sonst wechselte die Zeile unter dem Zeiger auf dem Weg zu den Korrekturschaltern.
    const user = userEvent.setup()
    renderSection({ motifs: strengths({ menschen: { strength: 0.42 }, tiere: { strength: 0.8 } }) })

    await user.click(symbolOf('menschen'))
    await user.hover(symbolOf('tiere'))

    const row = detailRow()
    expect(within(row).getByText('Menschen')).toBeTruthy()
    expect(within(row).queryByText('Tiere')).toBeNull()
  })

  it('falls back to the hovered symbol again once nothing is pinned', async () => {
    const user = userEvent.setup()
    renderSection({ motifs: strengths({ tiere: { strength: 0.8 } }) })

    await user.click(symbolOf('menschen'))
    await user.click(symbolOf('menschen'))
    await user.hover(symbolOf('tiere'))

    expect(within(detailRow()).getByText('Tiere')).toBeTruthy()
  })

  it('offers the same entries on hover as after a click', async () => {
    // AK10: Auf Geraeten ohne Maus ist der Klick der VOLLSTAENDIGE Weg - keine Angabe und keine
    // Aktion ist allein ueber Zeigen erreichbar.
    const user = userEvent.setup()
    const { view } = renderSection({ motifs: strengths({ menschen: { strength: 0.42 } }) })

    await user.hover(symbolOf('menschen'))
    const hovered = detailRow().innerHTML
    await user.unhover(symbolOf('menschen'))
    await user.click(symbolOf('menschen'))
    const clicked = detailRow().innerHTML
    view.unmount()

    expect(clicked).toBe(hovered)
  })

  it('shows the reason instead of the value for a locally unassessable motif', async () => {
    // AK7: Ein `0 %` waere dort die Aussage „nicht zu sehen" statt „nicht angesehen".
    const user = userEvent.setup()
    renderSection({ assessment: LOCAL_ASSESSMENT })

    await user.click(symbolOf('aktivitaet'))

    const row = detailRow()
    expect(within(row).getByText('lokal nicht beurteilbar')).toBeTruthy()
    expect(within(row).queryByText('0%')).toBeNull()
  })

  it('names a locally unassessable motif with the reason instead of a number', () => {
    renderSection({ assessment: LOCAL_ASSESSMENT })

    expect(symbolOf('aktivitaet').getAttribute('aria-label')).toBe(
      'Aktivität: lokal nicht beurteilbar',
    )
  })

  it('leaves a locally unassessable symbol unfilled', () => {
    // AK7: In der Reihe traegt dieser Fall dieselbe leere Fuellung wie „gar nicht vertreten".
    renderSection({
      assessment: LOCAL_ASSESSMENT,
      motifs: strengths({ aktivitaet: { strength: 0.9 } }),
    })

    const fill = symbolOf('aktivitaet').querySelector('[data-motif-layer="fill"]') as HTMLElement
    expect(fill.style.getPropertyValue('--motif-fill')).toBe('0%')
    for (const utility of ['text-status-success', 'text-status-running', 'text-status-failed']) {
      expect(fill.className, utility).not.toContain(utility)
    }
  })

  it('shows value and fill on a CLOUD basis even for a locally unassessable motif', () => {
    // Der Hinweis haengt an der Grundlage, nicht am Motiv: das Modell hat es beurteilt.
    renderSection({ motifs: strengths({ aktivitaet: { strength: 0.7 } }) })

    expect(symbolOf('aktivitaet').getAttribute('aria-label')).toBe('Aktivität: 70%')
  })

  it('keeps a pinned symbol pinned across a photo change and shows the NEW value', async () => {
    // Die Komponente kann den Fotowechsel mangels Fotoidentitaet in den Props nicht erkennen.
    // Zugesichert wird deshalb, dass die Zeile danach den neuen Wert zeigt, nie einen
    // stehengebliebenen alten.
    const user = userEvent.setup()
    const { view } = renderSection({ motifs: strengths({ menschen: { strength: 0.42 } }) })

    await user.click(symbolOf('menschen'))
    view.rerender(
      <MotifStrengthSection
        motifSet={MOTIF_SET}
        assessment={CLOUD_ASSESSMENT}
        motifs={strengths({ menschen: { strength: 0.91 } })}
        editable
        onCorrect={vi.fn()}
        onWithdraw={vi.fn()}
        pendingMotifKey={null}
        error={null}
      />,
    )

    expect(symbolOf('menschen').getAttribute('aria-expanded')).toBe('true')
    const row = detailRow()
    expect(within(row).getByText('91%')).toBeTruthy()
    expect(within(row).queryByText('42%')).toBeNull()
  })
})

describe('MotifStrengthSection: die vier Fotozustände', () => {
  it('shows a sentence instead of the row when the photo was never classified', () => {
    renderSection({ assessment: null })

    expect(document.querySelectorAll('[data-motif-key]')).toHaveLength(0)
    expect(screen.queryByRole('list', { name: 'Motive' })).toBeNull()
    expect(screen.getByText(/Noch nicht klassifiziert/)).toBeTruthy()
  })

  it('offers no correction button at all when the photo was never classified', () => {
    renderSection({ assessment: null })

    expect(screen.queryByRole('button', { name: /^Trifft zu:/ })).toBeNull()
  })

  it('renders differently for an unclassified photo than for eight zeroes', () => {
    // DAS PAAR. Ohne diesen Fall machte ein `?? 0` im Lesepfad aus „noch nicht klassifiziert"
    // acht leere Symbole, und kein anderer Fall braeche.
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
    const unassessedSymbols = document.querySelectorAll('[data-motif-key]').length
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

    expect(unassessedSymbols).toBe(0)
    expect(document.querySelectorAll('[data-motif-key]')).toHaveLength(MOTIF_KEYS.length)
    expect(document.body.innerHTML).not.toBe(unassessedMarkup)
  })

  it('shows the eight empty symbols without a computed "nothing recognised" verdict', () => {
    renderSection({ motifs: strengths() })

    const list = screen.getByRole('list', { name: 'Motive' })
    expect(document.querySelectorAll('[data-motif-key]')).toHaveLength(MOTIF_KEYS.length)
    expect(accessibleNames().filter((name) => name.endsWith(': 0%'))).toHaveLength(
      MOTIF_KEYS.length,
    )
    expect(list.textContent ?? '').not.toMatch(/nichts erkannt/i)
    expect(screen.queryByText(/Noch nicht klassifiziert/)).toBeNull()
  })

  it('names the cloud basis with provider and time', () => {
    renderSection()

    expect(screen.getByText(/Grundlage: Cloud-Klassifizierung \(Anthropic\)/)).toBeTruthy()
  })

  it('names the local basis and that it cannot judge every motif', () => {
    renderSection({ assessment: LOCAL_ASSESSMENT })

    expect(screen.getByText(/Grundlage: lokale Erkennung/)).toBeTruthy()
    expect(screen.getByText(/kann nicht jedes Motiv beurteilen/)).toBeTruthy()
  })

  it('keeps the buttons of a locally unassessable motif operable', async () => {
    const user = userEvent.setup()
    renderSection({ assessment: LOCAL_ASSESSMENT })

    await user.click(symbolOf('aktivitaet'))

    const applies = within(detailRow()).getByRole('button', { name: 'Trifft zu: Aktivität' })
    expect(applies.hasAttribute('disabled')).toBe(false)
  })

  it('states the exclusion first and shows the row read-only', () => {
    renderSection({
      assessment: { ...CLOUD_ASSESSMENT, excluded_document: true },
      motifs: strengths({ menschen: { strength: 0.9 } }),
    })

    expect(screen.getByText(/Als Dokument oder Bildschirmabbildung erkannt/)).toBeTruthy()
    expect(screen.getByText(/lässt sich nicht von Hand ändern/)).toBeTruthy()
    expect(document.querySelectorAll('[data-motif-key]')).toHaveLength(MOTIF_KEYS.length)
  })

  it('names the way back out of the exclusion', () => {
    renderSection({ assessment: { ...CLOUD_ASSESSMENT, excluded_document: true } })

    expect(screen.getByText(/neuer Klassifizierungslauf beurteilt das Foto erneut/)).toBeTruthy()
  })

  it('renders no correction button for an excluded photo, not even after expanding', async () => {
    // DER KLICK STEHT VOR DER NEGATIVEN ASSERTION: ohne ihn bestuende die Zusage auch dann, wenn
    // nach dem Aufklappen sehr wohl Schalter erschienen. Kein deaktivierter Schalter, nach dem
    // niemand suchen soll.
    const user = userEvent.setup()
    renderSection({ assessment: { ...CLOUD_ASSESSMENT, excluded_document: true } })

    await user.click(symbolOf('menschen'))

    expect(screen.queryAllByRole('button', { name: /^Trifft/ })).toHaveLength(0)
    expect(screen.queryByRole('button', { name: /^Zurücknehmen:/ })).toBeNull()
  })

  it('still shows name and value of an excluded photo after expanding', () => {
    renderSection({
      assessment: { ...CLOUD_ASSESSMENT, excluded_document: true },
      motifs: strengths({ menschen: { strength: 0.9 } }),
    })

    expect(symbolOf('menschen').getAttribute('aria-label')).toBe('Menschen: 90%')
  })
})

describe('MotifStrengthSection: die Korrektur', () => {
  async function openCorrection(motifKey: string, props = {}) {
    const user = userEvent.setup()
    const handlers = renderSection(props)
    await user.click(symbolOf(motifKey))
    return { ...handlers, user, row: detailRow() }
  }

  it('offers both directions in the expanded row with the motif name in the accessible name', async () => {
    const { row } = await openCorrection('menschen')

    expect(within(row).getByRole('button', { name: 'Trifft zu: Menschen' })).toBeTruthy()
    expect(within(row).getByRole('button', { name: 'Trifft nicht zu: Menschen' })).toBeTruthy()
  })

  it('reports both directions as unpressed without a correction', async () => {
    const { row } = await openCorrection('menschen')

    for (const name of ['Trifft zu: Menschen', 'Trifft nicht zu: Menschen']) {
      expect(within(row).getByRole('button', { name }).getAttribute('aria-pressed')).toBe('false')
    }
  })

  it('marks the applying direction as pressed', async () => {
    const { row } = await openCorrection('menschen', {
      motifs: strengths({ menschen: { strength: 1, correction: true } }),
    })

    expect(
      within(row).getByRole('button', { name: 'Trifft zu: Menschen' }).getAttribute('aria-pressed'),
    ).toBe('true')
    expect(
      within(row)
        .getByRole('button', { name: 'Trifft nicht zu: Menschen' })
        .getAttribute('aria-pressed'),
    ).toBe('false')
  })

  it('marks the rejecting direction as pressed', async () => {
    const { row } = await openCorrection('menschen', {
      motifs: strengths({ menschen: { strength: 0, correction: false } }),
    })

    expect(
      within(row)
        .getByRole('button', { name: 'Trifft nicht zu: Menschen' })
        .getAttribute('aria-pressed'),
    ).toBe('true')
  })

  it('replaces the percentage with the correction word', async () => {
    // Die ueberstimmte Modellzahl steht NICHT daneben - weder in der Zeile noch im Namen.
    const { row } = await openCorrection('menschen', {
      motifs: strengths({ menschen: { strength: 1, correction: true } }),
    })

    expect(within(row).getByText('Trifft zu (korrigiert)')).toBeTruthy()
    expect(within(row).queryByText('100%')).toBeNull()
    expect(symbolOf('menschen').getAttribute('aria-label')).toBe('Menschen: Trifft zu (korrigiert)')
  })

  it('uses the rejecting word for a rejecting correction', async () => {
    const { row } = await openCorrection('menschen', {
      motifs: strengths({ menschen: { strength: 0, correction: false } }),
    })

    expect(within(row).getByText('Trifft nicht zu (korrigiert)')).toBeTruthy()
  })

  it('marks the corrected symbol in the DOM', () => {
    renderSection({
      motifs: strengths({
        menschen: { strength: 1, correction: true },
        tiere: { strength: 0, correction: false },
      }),
    })

    expect(symbolOf('menschen').getAttribute('data-motif-corrected')).toBe('applies')
    expect(symbolOf('tiere').getAttribute('data-motif-corrected')).toBe('rejected')
    expect(symbolOf('landschaft').hasAttribute('data-motif-corrected')).toBe(false)
  })

  it('fills the symbol of an applying correction and empties it for a rejecting one', () => {
    // Die wirksame Staerke ist bereits 1 bzw. 0 - die Fuellung folgt ihr ohne Sonderweg.
    renderSection({
      motifs: strengths({
        menschen: { strength: 1, correction: true },
        tiere: { strength: 0, correction: false },
      }),
    })

    const filled = symbolOf('menschen').querySelector('[data-motif-layer="fill"]') as HTMLElement
    const empty = symbolOf('tiere').querySelector('[data-motif-layer="fill"]') as HTMLElement
    expect(filled.style.getPropertyValue('--motif-fill')).toBe('100%')
    expect(empty.style.getPropertyValue('--motif-fill')).toBe('0%')
  })

  it('offers the withdrawal only while a correction exists', async () => {
    const { user, row } = await openCorrection('menschen', {
      motifs: strengths({ menschen: { strength: 1, correction: true } }),
    })

    expect(within(row).getByRole('button', { name: 'Zurücknehmen: Menschen' })).toBeTruthy()

    await user.click(symbolOf('tiere'))
    expect(within(detailRow()).queryByRole('button', { name: 'Zurücknehmen: Tiere' })).toBeNull()
  })

  it('reports a pointless correction as corrected as well', async () => {
    const { row } = await openCorrection('menschen', {
      motifs: strengths({ menschen: { strength: 0, correction: false } }),
    })

    expect(symbolOf('menschen').getAttribute('data-motif-corrected')).toBe('rejected')
    expect(within(row).getByText('Trifft nicht zu (korrigiert)')).toBeTruthy()
  })

  it('calls the handler with motif key and direction', async () => {
    const { onCorrect, row } = await openCorrection('tiere')

    within(row).getByRole('button', { name: 'Trifft zu: Tiere' }).click()
    within(row).getByRole('button', { name: 'Trifft nicht zu: Tiere' }).click()

    expect(onCorrect).toHaveBeenNthCalledWith(1, 'tiere', true)
    expect(onCorrect).toHaveBeenNthCalledWith(2, 'tiere', false)
  })

  it('calls the withdrawal handler with the motif key', async () => {
    const { onWithdraw, row } = await openCorrection('menschen', {
      motifs: strengths({ menschen: { strength: 1, correction: true } }),
    })

    within(row).getByRole('button', { name: 'Zurücknehmen: Menschen' }).click()

    expect(onWithdraw).toHaveBeenCalledWith('menschen')
  })

  it('renders no CORRECTION button when the section is read-only, not even after expanding', async () => {
    // Geschaerft: die acht Symbole SIND Schaltflaechen, „gar keine Schaltflaeche" waere hier
    // zwangslaeufig rot und saegte die eigentliche Zusage ab. Der Klick steht vor der negativen
    // Assertion.
    const user = userEvent.setup()
    renderSection({ editable: false })

    await user.click(symbolOf('menschen'))

    expect(screen.queryAllByRole('button', { name: /^Trifft/ })).toHaveLength(0)
    expect(screen.queryByRole('button', { name: /^Zurücknehmen:/ })).toBeNull()
    expect(document.querySelectorAll('[data-motif-key]')).toHaveLength(MOTIF_KEYS.length)
  })

  it('still shows the values when the section is read-only', async () => {
    const user = userEvent.setup()
    renderSection({ editable: false, motifs: strengths({ menschen: { strength: 0.6 } }) })

    expect(symbolOf('menschen').getAttribute('aria-label')).toBe('Menschen: 60%')

    await user.click(symbolOf('menschen'))
    expect(within(detailRow()).getByText('60%')).toBeTruthy()
  })
})

describe('MotifStrengthSection: die Zustände', () => {
  it('disables only the buttons of the motif whose correction is running', async () => {
    const user = userEvent.setup()
    renderSection({ pendingMotifKey: 'menschen' })

    await user.click(symbolOf('menschen'))
    expect(
      within(detailRow())
        .getByRole('button', { name: 'Trifft zu: Menschen' })
        .hasAttribute('disabled'),
    ).toBe(true)

    await user.click(symbolOf('tiere'))
    expect(
      within(detailRow())
        .getByRole('button', { name: 'Trifft zu: Tiere' })
        .hasAttribute('disabled'),
    ).toBe(false)
  })

  it('keeps the symbol row operable while a correction is running', async () => {
    // Nur die Schaltflaechen DIESER Zeile werden gesperrt, nie die Reihe.
    renderSection({ pendingMotifKey: 'menschen' })

    expect(symbolOf('menschen').hasAttribute('disabled')).toBe(false)
  })

  function renderLoading() {
    return render(
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
  }

  it('shows the placeholders in the shape of the ROW, not stacked as rows', () => {
    // DIE FORM, NICHT DIE ZAHL: Acht Platzhalter untereinander waren die Form der abgeloesten
    // Balkenliste und beanspruchen rund 340 px gegen die rund 60 px der geladenen Reihe. Der
    // Bereich schoebe beim Eintrudeln der Antwort alles darunter um rund 280 px zurueck - genau
    // die "Bewegung von Layout oder Position", die das Design-System ausschliesst.
    //
    // Die Hoehe selbst ist in jsdom nicht messbar (keine Layout-Engine); geprueft wird deshalb
    // die Achse des Platzhalter-Containers - dieselbe Ebene, auf der auch der Design-Vertrag
    // Klassen liest.
    renderLoading()

    const reihe = screen.getByTestId('motif-skeleton-row')
    const klassen = reihe.className.split(/\s+/)
    expect(klassen).toContain('flex')
    expect(klassen).not.toContain('flex-col')
    expect(within(reihe).getAllByTestId('motif-skeleton-symbol')).toHaveLength(8)
  })

  it.each([
    ['motif-skeleton-basis', 'Grundlagenzeile'],
    ['motif-skeleton-detail', 'Detailzeile'],
    ['motif-skeleton-glossary', 'Glossar'],
  ])('holds a placeholder for the %s (%s)', (testId) => {
    // JEDER Bereich, den der geladene Baustein traegt, braucht seinen Platzhalter - fehlt einer,
    // springt die Seite beim Eintrudeln genau um dessen Hoehe. Detailzeile und Glossar stehen im
    // geladenen Zustand IMMER, nicht nur nach einer Auswahl.
    renderLoading()

    expect(screen.getByTestId(testId)).toBeTruthy()
  })

  it('draws no bar while the motif set is loading', () => {
    renderLoading()

    expect(screen.queryByRole('progressbar')).toBeNull()
    expect(document.querySelector('progress')).toBeNull()
  })

  it('shows an alert with a retry action when the motif set failed to load', () => {
    // Keine Reihe mit Rohschluesseln.
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
    // Der Fehler nennt den Motivnamen, AUCH wenn dieses Motiv gerade nicht aufgeklappt ist.
    renderSection({
      error: { motifKey: 'menschen', detail: 'Bitte erneut versuchen.' },
    })

    const alert = screen.getByRole('alert')
    expect(within(alert).getByText('Bitte erneut versuchen.')).toBeTruthy()
    expect(alert.textContent ?? '').toContain('Menschen')
  })

  it('offers no retry button for a failed correction', () => {
    renderSection({ error: { motifKey: 'menschen', detail: 'Bitte erneut versuchen.' } })

    expect(screen.queryByRole('button', { name: 'Erneut versuchen' })).toBeNull()
  })
})

describe('MotifStrengthSection: das Glossar', () => {
  it('carries exactly one collapsed details element at the end of the section', () => {
    renderSection()

    const details = document.querySelectorAll('details')
    expect(details).toHaveLength(1)
    expect((details[0] as HTMLDetailsElement).open).toBe(false)
    expect(screen.getByText('Was die acht Motive bedeuten')).toBeTruthy()
  })

  it('explains every motif with its definition and its delimitation', () => {
    renderSection()

    const glossary = document.querySelector('details') as HTMLElement
    for (const item of MOTIF_SET.items) {
      expect(within(glossary).getByText(item.display_name)).toBeTruthy()
      expect(within(glossary).getByText(item.definition)).toBeTruthy()
      expect(within(glossary).getByText(`Abgrenzung: ${item.delimitation}`)).toBeTruthy()
    }
  })

  it('renders the registry text as plain text nodes - in the row and in the accessible name', async () => {
    // SICHERHEIT (S19): nie ueber `dangerouslySetInnerHTML`, nie als HTML-String-Prop. Die
    // Detailzeile und der zugaengliche Name sind seit dem Umbau eigene Austrittsstellen des
    // Registry-Texts und deshalb HIER mit abgedeckt.
    const user = userEvent.setup()
    renderSection({
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

    expect(symbolOf('menschen').getAttribute('aria-label')).toBe(
      '<img src=x onerror=alert(1)>: 50%',
    )
    await user.click(symbolOf('menschen'))

    expect(document.querySelector('img')).toBeNull()
    expect(document.querySelector('script')).toBeNull()
    expect(document.querySelector('details b')).toBeNull()
    expect(detailRow().querySelector('img')).toBeNull()
    expect(screen.getAllByText('<img src=x onerror=alert(1)>').length).toBeGreaterThan(0)
  })

  it('has no info trigger per motif', () => {
    renderSection()

    expect(screen.queryAllByRole('button', { name: /Erklärung/ })).toHaveLength(0)
  })

  it('opens no second panel inside the popover', () => {
    // Die Reihe steht im Kachel-Popover bereits in einem Panel; ein zweites darin ist nicht
    // zulaessig - deshalb kein Popover und kein `title`-Attribut an den Symbolen.
    renderSection()

    expect(screen.queryByRole('dialog')).toBeNull()
    for (const key of MOTIF_KEYS) {
      expect(symbolOf(key).hasAttribute('title'), key).toBe(false)
    }
  })

  it('shows no band word anywhere outside the statistics table', async () => {
    // Ein Bandwort neben dem Einzelwert lehrte den Nutzer genau die Zugehoerigkeitsschwelle, die
    // es im Auswahlpfad nicht gibt. Geprueft werden Text UND die zugaenglichen Namen - die Werte
    // wandern dorthin, und `document.body.textContent` erfasst `aria-label` nicht.
    const user = userEvent.setup()
    renderSection({ motifs: strengths({ menschen: { strength: 0.95 } }) })
    await user.click(symbolOf('menschen'))

    const haystack = [document.body.textContent ?? '', ...accessibleNames()].join(' ')
    expect(haystack).not.toMatch(/\bstark\b/i)
    expect(haystack).not.toMatch(/\bmittel\b/i)
    expect(haystack).not.toMatch(/\bschwach\b/i)
  })
})

/* specs/features/0497-bilddetail-urteil-zuerst.md, AK6/AK7 — der reservierte Platz der
   Detailzeile. Neuer describe-Block: kein Bestandsfall dieser Datei ist angetastet.

   WAS HIER PRUEFBAR IST UND WAS NICHT: Die Zusage „nichts darunter bewegt sich um mehr als 1 px"
   ist echte Geometrie und wird im Browser gemessen (`e2e/tests/bilddetail-buehne.spec.ts`,
   Fall 2). In jsdom bleibt die BAUFORM, die sie ueberhaupt erst moeglich macht: EIN Container fuer
   beide Zustaende, und die Reservierung folgt `rowsEditable` statt `editable`. */
describe('MotifStrengthSection: der reservierte Platz der Detailzeile', () => {
  it('trägt beide Zustände im selben Container', async () => {
    // AK7: Der Aufforderungssatz und die aufgeklappte Zeile stehen im SELBEN Element - das ist die
    // Bauform, die die Reservierung moeglich macht. Zwei Container koennten nie dieselbe Hoehe
    // halten, und `aria-controls` zeigte beim Zuklappen ins Leere.
    const user = userEvent.setup()
    renderSection()

    const zugeklappt = detailRow()
    expect(within(zugeklappt).getByText('Symbol antippen für Details')).toBeInTheDocument()

    await user.click(symbolOf('menschen'))

    const aufgeklappt = detailRow()
    expect(aufgeklappt).toBe(zugeklappt)
    expect(within(aufgeklappt).getByText('Menschen')).toBeInTheDocument()
    expect(within(aufgeklappt).queryByText('Symbol antippen für Details')).toBeNull()
  })

  it('reserviert den Platz an der bedienbaren Stelle', () => {
    renderSection({ editable: true })

    expect(detailRow()).toHaveAttribute('data-detail-reserved', 'true')
  })

  /* Die Reservierung folgt `rowsEditable` (`editable && !excluded`), NICHT `editable` allein:
     Bei einem als Dokument ausgeschlossenen Foto gibt es keine Korrekturschalter, und eine
     Reservierung nach `editable` liesse dort dauerhaft leere Flaeche stehen, die nie gefuellt
     wird. */
  it('reserviert bei einem ausgeschlossenen Dokument keinen Platz', () => {
    renderSection({
      editable: true,
      assessment: { ...CLOUD_ASSESSMENT, excluded_document: true },
    })

    expect(detailRow()).not.toHaveAttribute('data-detail-reserved')
  })

  it('reserviert an der schreibgeschützten Stelle keinen Platz', () => {
    // Das Kachel-Popover zeigt die Reihe ohne Bedienteil; dort waere die Reservierung toter Raum.
    renderSection({ editable: false })

    expect(detailRow()).not.toHaveAttribute('data-detail-reserved')
  })

  /* Der Platz bleibt ueber JEDEN der vier Zustandswechsel aus AK6 derselbe Container mit
     derselben Reservierung - auch bei einem Motiv MIT bestehender Korrektur, dessen Zeile eine
     dritte Schaltflaeche traegt und damit der ungünstigste Fall ist. */
  it('hält Container und Reservierung über alle vier Zustände', async () => {
    const user = userEvent.setup()
    renderSection({ motifs: strengths({ menschen: { correction: true } }) })

    const container = detailRow()
    expect(container).toHaveAttribute('data-detail-reserved', 'true')

    // (i) laengster Anzeigename angeheftet
    await user.click(symbolOf('bauwerk_sehenswuerdigkeit'))
    expect(detailRow()).toBe(container)
    expect(within(container).getByText('Bauwerk und Sehenswürdigkeit')).toBeInTheDocument()

    // (ii) Motiv MIT bestehender Korrektur angeheftet - drei Schaltflaechen
    await user.click(symbolOf('menschen'))
    expect(detailRow()).toBe(container)
    expect(
      within(container).getByRole('button', { name: 'Zurücknehmen: Menschen' }),
    ).toBeInTheDocument()

    // (iii) Tastaturfokus statt Klick zeigt vor. Der ECHTE Tastaturweg, nicht `element.focus()`
    // von aussen - das liefe ausserhalb von `act()`.
    await user.click(symbolOf('menschen'))
    for (let schritt = 0; schritt < MOTIF_KEYS.length * 2; schritt += 1) {
      await user.tab()
      if (document.activeElement?.getAttribute('data-motif-key') === 'tiere') {
        break
      }
    }
    expect(document.activeElement?.getAttribute('data-motif-key')).toBe('tiere')
    expect(detailRow()).toBe(container)
    expect(within(container).getByText('Tiere')).toBeInTheDocument()

    // (iv) wieder zugeklappt - weitertabben nimmt die Vorschau mit. Getabbt wird ueber die Reihe
    // HINAUS: das naechste Symbol uebernaehme die Vorschau sonst nur.
    for (let schritt = 0; schritt < MOTIF_KEYS.length * 2; schritt += 1) {
      await user.tab()
      if (document.activeElement?.getAttribute('data-motif-key') === null) {
        break
      }
    }
    expect(document.activeElement?.getAttribute('data-motif-key')).toBeNull()
    expect(detailRow()).toBe(container)
    expect(within(container).getByText('Symbol antippen für Details')).toBeInTheDocument()
    expect(container).toHaveAttribute('data-detail-reserved', 'true')
  })
})
