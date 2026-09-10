import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { ProjectOut } from '../api/types'
import { PIPELINE_STEPS, stepProgress, type PipelineStepState } from '../utils/pipelineSteps'
import { Stepper } from './Stepper'

// window.matchMedia existiert in jsdom nicht (siehe CriterionDetailsPopover.test.tsx) - gleicher
// Stub, da der Blockiert-Grund-Popover-Trigger dieselbe Radix-Popover-Primitive wiederverwendet
// (specs/architecture/0002-testkonzept.md, Abschnitt "Mehrschritt-Routing", Punkt 6).
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

function project(overrides: Partial<ProjectOut> = {}): ProjectOut {
  return {
    id: 1,
    name: 'Costa Rica',
    opencloud_drive_id: 'drive-1',
    opencloud_path: 'CostaRica',
    created_at: '2026-07-20T10:00:00Z',
    last_scan: null,
    last_scoring_run: null,
    last_criterion_scoring_run: null,
    category_selection_enabled: true,
    cloud_vision_detection_enabled: false,
    cloud_vision_consent_at: null,
    ...overrides,
  }
}

const FRESH_STATES: PipelineStepState[] = [
  { id: 'scan', isDone: false, isReachable: true },
  { id: 'ausschuss', isDone: false, isReachable: true },
  { id: 'gate', isDone: false, isReachable: false },
  { id: 'kriterien', isDone: false, isReachable: false },
  { id: 'kuratierung', isDone: false, isReachable: false },
]

const ALLE_ERREICHBAR: PipelineStepState[] = PIPELINE_STEPS.map((step) => ({
  id: step.id,
  isDone: false,
  isReachable: true,
}))

/**
 * Standort-Sonde: "der gesperrte Schritt loest keine Navigation aus" war frueher strukturell
 * unmoeglich (ein `<span>` navigiert nicht) und ist seit specs/features/0387-schrittleiste-
 * fortschritt.md eine VERHALTENSzusage - der Schritt ist jetzt ein `<button>`. Ohne die Sonde
 * bestuende der Negativtest auch dann, wenn die Leiste heimlich navigierte.
 */
function LocationProbe() {
  return <span data-testid="pfad">{useLocation().pathname}</span>
}

function renderStepper(
  states: PipelineStepState[] = FRESH_STATES,
  activeStepId: PipelineStepState['id'] = 'scan',
  projectOverrides: Partial<ProjectOut> = {}
) {
  return render(
    <MemoryRouter initialEntries={['/projects/1/pipeline/scan']}>
      <LocationProbe />
      <Stepper projectId={1} project={project(projectOverrides)} states={states} activeStepId={activeStepId} />
    </MemoryRouter>
  )
}

/** Die Standard-Kandidatenmenge fokussierbarer Knoten. Eingegrenzt auf das `<nav>` - der
 * Skip-Link steht davor und darf nicht mitzaehlen. */
const FOKUSSIERBAR = 'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])'

function fokussierbareInDerLeiste(): HTMLElement[] {
  const nav = screen.getByRole('navigation', { name: 'Fortschritt der Pipeline' })
  return Array.from(nav.querySelectorAll<HTMLElement>(FOKUSSIERBAR))
}

function gesperrterSchritt(name: string): HTMLElement {
  return screen.getByLabelText(name)
}

describe('Stepper', () => {
  beforeEach(() => {
    stubMatchMedia(false)
  })

  it('renders the progress nav landmark with a skip link right before it', () => {
    renderStepper()

    const skipLink = screen.getByRole('link', { name: /zum seiteninhalt springen/i })
    expect(skipLink).toHaveAttribute('href', '#pipeline-content')
    const nav = screen.getByRole('navigation', { name: 'Fortschritt der Pipeline' })
    // Skip-Link steht vor der Leiste (Akzeptanzkriterium 15) - ueber die DOM-Position pruefbar.
    expect(
      skipLink.compareDocumentPosition(nav) & Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy()
  })

  it('renders all 5 steps as an ordered list, in the fixed pipeline order', () => {
    renderStepper()

    const nav = screen.getByRole('navigation', { name: 'Fortschritt der Pipeline' })
    const items = within(nav).getAllByRole('listitem')
    expect(items).toHaveLength(5)
    expect(
      within(nav).getByRole('link', { name: /schritt 1 von 5: scan/i })
    ).toBeInTheDocument()
    expect(
      within(nav).getByLabelText(/^schritt 5 von 5: kategorie-kuratierung/i)
    ).toBeInTheDocument()
  })

  it('renders a reachable, not-yet-done step as a clickable link with the pending status in its label', () => {
    renderStepper()

    const link = screen.getByRole('link', { name: 'Schritt 2 von 5: Ausschuss-Erkennung, ausstehend' })
    expect(link).toHaveAttribute('href', '/projects/1/pipeline/ausschuss')
  })

  it('marks the currently viewed step with aria-current="step"', () => {
    renderStepper(FRESH_STATES, 'ausschuss')

    const link = screen.getByRole('link', { name: 'Schritt 2 von 5: Ausschuss-Erkennung, aktuell' })
    expect(link).toHaveAttribute('aria-current', 'step')
  })

  it('shows a done step as "erledigt" in its label, still clickable', () => {
    const states: PipelineStepState[] = [
      { id: 'scan', isDone: true, isReachable: true },
      ...FRESH_STATES.slice(1),
    ]
    renderStepper(states, 'ausschuss')

    const link = screen.getByRole('link', { name: 'Schritt 1 von 5: Scan, erledigt' })
    expect(link).toHaveAttribute('href', '/projects/1/pipeline/scan')
  })

  /*
   * ERSETZT die fruehere Zusicherung `tabIndex="-1"` - sie sicherte GENAU DAS GEGENTEIL zu und
   * war die Ursache der Luecke "der Sperrgrund ist fuer Tastaturnutzer gar nicht erreichbar"
   * (specs/features/0387-schrittleiste-fortschritt.md). Der gesperrte Schritt ist jetzt ein
   * `<button>` mit `aria-disabled`, NIE mit `disabled`: `disabled` naehme ihn aus der
   * Tab-Reihenfolge UND schaltete Zeigerereignisse ab.
   */
  it('rendert einen gesperrten Schritt als fokussierbaren Knopf mit aria-disabled, nie mit disabled', () => {
    renderStepper()

    const blocked = gesperrterSchritt('Schritt 3 von 5: Ausschuss-Gate, blockiert')
    expect(blocked.tagName).toBe('BUTTON')
    expect(blocked).toHaveAttribute('aria-disabled', 'true')
    expect(blocked).not.toBeDisabled()
    expect(blocked).not.toHaveAttribute('tabindex', '-1')
    expect(screen.queryByRole('link', { name: /ausschuss-gate/i })).not.toBeInTheDocument()
  })

  it('loest von einem gesperrten Schritt aus keine Navigation aus', async () => {
    const user = userEvent.setup()
    renderStepper()
    const vorher = screen.getByTestId('pfad').textContent

    const blocked = gesperrterSchritt('Schritt 3 von 5: Ausschuss-Gate, blockiert')
    expect(blocked).not.toHaveAttribute('href')
    await user.click(blocked)

    expect(screen.getByTestId('pfad')).toHaveTextContent(vorher!)
  })

  /* Der eigene `i`-Ausloeser neben gesperrten Schritten entfaellt ERSATZLOS. Der bisherige
     Positivtest darauf ist gestrichen, nicht umbenannt - hier steht seine Umkehrung. */
  it('fuehrt keinen eigenen Info-Ausloeser mehr neben gesperrten Schritten', () => {
    renderStepper()

    expect(screen.queryByRole('button', { name: /grund für sperrung von/i })).toBeNull()
  })

  /*
   * Der Sperrgrund steht zusaetzlich als `sr-only`-Text im Baum und ist per `aria-describedby`
   * verlinkt - damit hat Screenreader-Bedienung ihn auch OHNE Oeffnen. Geprueft ueber die
   * ID-AUFLOESUNG, nicht ueber eine Textsuche irgendwo im Dokument: sonst bestuende der Test
   * auch bei einer verwaisten ID.
   */
  it('verlinkt den Sperrgrund per aria-describedby auf einen vorhandenen Knoten', () => {
    renderStepper()

    const blocked = gesperrterSchritt('Schritt 3 von 5: Ausschuss-Gate, blockiert')
    const id = blocked.getAttribute('aria-describedby')
    expect(id, 'aria-describedby fehlt').toBeTruthy()

    const beschreibung = document.getElementById(id!)
    expect(beschreibung, 'aria-describedby zeigt ins Leere').not.toBeNull()
    expect(beschreibung).toHaveTextContent('Sichte zuerst den Ausschuss oben.')
  })

  it('gibt den Grund am gesperrten Schritt selbst preis, beim Antippen', async () => {
    const user = userEvent.setup()
    renderStepper()

    await user.click(gesperrterSchritt('Schritt 3 von 5: Ausschuss-Gate, blockiert'))

    const panel = await screen.findByRole('dialog')
    expect(within(panel).getByText('Sichte zuerst den Ausschuss oben.')).toBeInTheDocument()
  })

  it('shows the feature-flag-off reason for a blocked kriterien step', async () => {
    const user = userEvent.setup()
    const states: PipelineStepState[] = [
      { id: 'scan', isDone: true, isReachable: true },
      { id: 'ausschuss', isDone: true, isReachable: true },
      { id: 'gate', isDone: true, isReachable: true },
      { id: 'kriterien', isDone: false, isReachable: false },
      { id: 'kuratierung', isDone: false, isReachable: false },
    ]
    renderStepper(states, 'gate', { category_selection_enabled: false })

    await user.click(gesperrterSchritt('Schritt 4 von 5: Kriterien-Bewertung, blockiert'))

    const panel = await screen.findByRole('dialog')
    expect(within(panel).getByText('Diese Funktion ist derzeit nicht aktiviert.')).toBeInTheDocument()
  })

  it('shows the gate-unconfirmed reason for a blocked kriterien step when the flag is on', async () => {
    const user = userEvent.setup()
    const states: PipelineStepState[] = [
      { id: 'scan', isDone: true, isReachable: true },
      { id: 'ausschuss', isDone: true, isReachable: true },
      { id: 'gate', isDone: false, isReachable: true },
      { id: 'kriterien', isDone: false, isReachable: false },
      { id: 'kuratierung', isDone: false, isReachable: false },
    ]
    renderStepper(states, 'gate')

    await user.click(gesperrterSchritt('Schritt 4 von 5: Kriterien-Bewertung, blockiert'))

    const panel = await screen.findByRole('dialog')
    expect(within(panel).getByText('Bestätige zuerst den Ausschuss oben.')).toBeInTheDocument()
  })

  it('shows the criterion-scoring reason for a blocked kuratierung step', async () => {
    const user = userEvent.setup()
    renderStepper()

    await user.click(gesperrterSchritt('Schritt 5 von 5: Kategorie-Kuratierung, blockiert'))

    const panel = await screen.findByRole('dialog')
    expect(within(panel).getByText('Führe zuerst die Kriterien-Bewertung oben aus.')).toBeInTheDocument()
  })

  /*
   * Die fruehere `size-8`/`tap-target-square`-Assertion ist mit specs/features/0387-
   * schrittleiste-fortschritt.md ERSATZLOS entfallen, nicht vergessen: Die Trefferflaeche haengt
   * seitdem am spaltenfuellenden Bedienelement (`tap-target`, nur senkrecht aufspannend) statt am
   * Marker, und ob sie tatsaechlich 44 x 44 px trifft, ist eine Frage echter Geometrie - geprueft
   * in `e2e/tests/tap-targets.spec.ts` bei 360 px, fuer den ersten UND einen gesperrten Schritt.
   * Eine Klassennamen-Assertion hier waere die schwaechere Aussage am falschen Ort.
   */

  /*
   * specs/features/0321-dark-utility-register-ansichten.md, Etappe 3: Die sichtbare
   * Schrittbeschriftung zieht IN das Nav-Element hinein und bleibt `aria-hidden`. Zugesichert
   * wird, dass der zugaengliche Name dadurch unveraendert vollstaendig aus dem `aria-label` kommt -
   * die e2e-Selektoren und die Tests oben haengen wortgleich daran.
   */
  it('keeps the accessible name coming entirely from the aria-label, label moved inside', () => {
    renderStepper()

    const step = screen.getByRole('link', { name: 'Schritt 1 von 5: Scan, aktuell' })
    expect(step).toHaveAccessibleName('Schritt 1 von 5: Scan, aktuell')
    // Die Beschriftung sitzt jetzt IM Nav-Element und ist dort vor Screenreadern verborgen.
    const label = within(step).getByText('Scan')
    expect(label).toHaveAttribute('aria-hidden', 'true')
  })

  /*
   * specs/features/0387-schrittleiste-fortschritt.md: "Die Umrandung fasst nur noch das Zeichen
   * des Schritts". Die in jsdom pruefbare Haelfte davon ist die BAUMSTELLUNG - die Beschriftung
   * liegt im selben Bedienelement, aber NICHT im Marker. Dass die Umrandung am Marker haengt, ist
   * CSS und gehoert in den Design-Vertrag, nicht hierher.
   */
  it('stellt die Beschriftung neben die Umrandung statt hinein', () => {
    renderStepper()

    const step = screen.getByRole('link', { name: 'Schritt 1 von 5: Scan, aktuell' })
    const marker = step.querySelector('[data-step-state]')
    expect(marker, 'Marker im Bedienelement').not.toBeNull()

    const label = within(step).getByText('Scan')
    expect(marker!.contains(label), 'Beschriftung liegt in der Umrandung').toBe(false)
    expect(step.contains(label), 'Beschriftung liegt ausserhalb des Bedienelements').toBe(true)
  })

  /*
   * DIE ORIENTIERUNGSZEILE VERLAESST DAS `<nav>` (Architektur-Abschnitt 2 der Spec 0387): Damit
   * ist die haftende Leiste schmal rund 25 px flacher und in beiden Breiten DERSELBE DOM-Baum.
   * Eine blosse "ist vorhanden"-Pruefung ginge an der Aussage vorbei - gepruegt wird die Stellung.
   */
  it('stellt die Orientierungszeile vor das nav, nicht hinein', () => {
    renderStepper(FRESH_STATES, 'gate')

    const nav = screen.getByRole('navigation', { name: 'Fortschritt der Pipeline' })
    expect(within(nav).queryByText(/schritt 3 von 5: ausschuss-gate$/i)).toBeNull()

    const zeile = screen.getByText('Schritt 3 von 5: Ausschuss-Gate')
    expect(nav.contains(zeile), 'Zeile steckt noch im nav').toBe(false)
    expect(
      zeile.compareDocumentPosition(nav) & Node.DOCUMENT_POSITION_FOLLOWING,
      'Zeile steht nicht vor dem nav'
    ).toBeTruthy()
  })

  /*
   * DER FORTSCHRITTSBALKEN (Architektur-Abschnitt 4): genau EINER in der Leiste - das ist zugleich
   * die pruefbare Form von "in beiden Breiten dieselbe, einzige Fassung": es gibt nur eine, also
   * kann sie nicht auseinanderlaufen. Kein zweiter jsdom-Lauf in einer zweiten Breite - jsdom hat
   * kein Layout, das waere der immer-gruene Test.
   *
   * `value`/`max` werden am gerenderten Element gelesen UND gegen die reine Funktion gehalten; die
   * DECKUNGSGLEICHHEIT mit der Spaltenmitte ist Geometrie und liegt in
   * `e2e/tests/stepper-progress.spec.ts`.
   */
  it.each(PIPELINE_STEPS.map((step, index) => ({ id: step.id, index })))(
    'traegt fuer $id genau einen Balken mit dem Wert der Spaltenmitte',
    ({ id, index }) => {
      renderStepper(ALLE_ERREICHBAR, id)

      const nav = screen.getByRole('navigation', { name: 'Fortschritt der Pipeline' })
      const balken = nav.querySelectorAll('progress')
      expect(balken, 'Balken in der Leiste').toHaveLength(1)

      const { value, max } = stepProgress(index)
      expect(balken[0]).toHaveAttribute('value', String(value))
      expect(balken[0]).toHaveAttribute('max', String(max))
    }
  )

  it('haelt den Balken aus dem Barrierefreiheitsbaum heraus', () => {
    // Die Information steht vollstaendig und besser im Schrittlisten-Baum (`aria-current`, der
    // Zustand im Namen, die Orientierungszeile). Ein zweites, prozentual vorgelesenes
    // Fortschrittselement waere Laerm. Beide Zusagen zusammen, sonst ist "der Balken ist da"
    // entweder unbelegt oder doppelt vorgelesen.
    renderStepper()

    expect(screen.queryByRole('progressbar')).toBeNull()
    const nav = screen.getByRole('navigation', { name: 'Fortschritt der Pipeline' })
    expect(nav.querySelector('progress')).toHaveAttribute('aria-hidden', 'true')
  })

  // -----------------------------------------------------------------------------------------
  // Die Invariante: genau fuenf fokussierbare Elemente
  // -----------------------------------------------------------------------------------------

  /*
   * Eines je Schritt. Heute schwankte die Zahl zustandsabhaengig zwischen vier und sieben (ein
   * gesperrter Schritt hatte ZWEI Knoten und war selbst keiner) - eine einzelne Messung machte
   * das nicht sichtbar. Deshalb drei Zustaende, und der dritte ist der entscheidende: er belegt
   * zugleich, dass das Panel samt Schliessen-Schaltflaeche per Portal AUSSERHALB der Leiste
   * landet.
   */
  it('fuehrt ohne gesperrten Schritt genau fuenf fokussierbare Elemente', () => {
    renderStepper(ALLE_ERREICHBAR)

    const fokussierbare = fokussierbareInDerLeiste()
    expect(fokussierbare).toHaveLength(5)
    expect(fokussierbare.every((knoten) => knoten.tagName === 'A')).toBe(true)
    // Edge Case 5: kein Knopf, kein aria-describedby, kein Popover.
    expect(screen.queryByRole('button')).toBeNull()
    expect(fokussierbare.some((knoten) => knoten.hasAttribute('aria-describedby'))).toBe(false)
  })

  it('fuehrt mit drei gesperrten Schritten weiterhin genau fuenf', () => {
    renderStepper()

    const fokussierbare = fokussierbareInDerLeiste()
    expect(fokussierbare).toHaveLength(5)
    expect(fokussierbare.filter((knoten) => knoten.tagName === 'A')).toHaveLength(2)
    expect(fokussierbare.filter((knoten) => knoten.tagName === 'BUTTON')).toHaveLength(3)
  })

  it('fuehrt auch bei geoeffnetem Sperrgrund genau fuenf - das Panel liegt ausserhalb der Leiste', async () => {
    const user = userEvent.setup()
    renderStepper()

    await user.click(gesperrterSchritt('Schritt 3 von 5: Ausschuss-Gate, blockiert'))
    expect(await screen.findByRole('dialog')).toBeInTheDocument()

    expect(fokussierbareInDerLeiste()).toHaveLength(5)
  })

  /* Die Menge der fuenf ist GENAU die Menge der fuenf Schritt-Bedienelemente, nicht irgendwelche
     fuenf Knoten - abgeglichen ueber den Marker, den jedes von ihnen enthaelt. */
  it('sind die fuenf genau die fuenf Schritt-Bedienelemente', () => {
    renderStepper()

    const zustaende = fokussierbareInDerLeiste().map((knoten) =>
      knoten.querySelector('[data-step-state]')?.getAttribute('data-step-state')
    )
    expect(zustaende).toEqual(['aktuell', 'ausstehend', 'blockiert', 'blockiert', 'blockiert'])
  })

  // -----------------------------------------------------------------------------------------
  // Der Weg: Tastatur
  // -----------------------------------------------------------------------------------------

  /*
   * Ohne jeden Mauszeiger und mit `matchMedia` auf `matches: false` - der Telefonfall, in dem
   * Ueberfahren gar nichts tun darf und der Grund trotzdem erreichbar sein muss. Enter UND
   * Leertaste, weil die Spec beides zusagt und es bei einem `aria-disabled`-Knopf keine
   * Selbstverstaendlichkeit ist, sondern der Punkt.
   */
  it.each(['{Enter}', ' '])(
    'oeffnet den Sperrgrund per Tastatur mit "%s" und gibt den Fokus zurueck',
    async (taste) => {
      const user = userEvent.setup()
      renderStepper()

      const blocked = gesperrterSchritt('Schritt 3 von 5: Ausschuss-Gate, blockiert')
      // Bis zum gesperrten Schritt tabben statt ihn zu fokussieren: dass er ueberhaupt in der
      // Tab-Reihenfolge liegt, ist die halbe Zusage.
      for (let schritte = 0; schritte < 10 && document.activeElement !== blocked; schritte += 1) {
        await user.tab()
      }
      expect(blocked).toHaveFocus()

      await user.keyboard(taste)
      const panel = await screen.findByRole('dialog')
      expect(within(panel).getByText('Sichte zuerst den Ausschuss oben.')).toBeInTheDocument()
      expect(panel.contains(document.activeElement), 'Fokus liegt nicht im Panel').toBe(true)

      await user.keyboard('{Escape}')
      await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
      expect(blocked).toHaveFocus()
    }
  )

  // -----------------------------------------------------------------------------------------
  // Der Weg: Zeiger
  // -----------------------------------------------------------------------------------------

  it('oeffnet beim Ueberfahren nur auf einem Zeigergeraet mit Hover', async () => {
    const user = userEvent.setup()
    renderStepper()
    const blocked = gesperrterSchritt('Schritt 3 von 5: Ausschuss-Gate, blockiert')

    await user.hover(blocked)
    expect(screen.queryByRole('dialog')).toBeNull()

    stubMatchMedia(true)
    fireEvent.pointerEnter(blocked)
    expect(await screen.findByRole('dialog')).toBeInTheDocument()
  })

  it('schliesst ein per Klick geoeffnetes Panel nicht, wenn der Zeiger den Ausloeser verlaesst', async () => {
    const user = userEvent.setup()
    renderStepper()
    const blocked = gesperrterSchritt('Schritt 3 von 5: Ausschuss-Gate, blockiert')

    await user.click(blocked)
    expect(await screen.findByRole('dialog')).toBeInTheDocument()

    // Schliessen per fireEvent mit `relatedTarget` statt `userEvent.unhover()` - dieselbe
    // dokumentierte Falle wie in CriterionDetailsPopover.test.tsx.
    fireEvent.mouseLeave(blocked, { relatedTarget: document.body })
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('schliesst ein per Ueberfahren geoeffnetes Panel beim Verlassen des Ausloesers', async () => {
    stubMatchMedia(true)
    renderStepper()
    const blocked = gesperrterSchritt('Schritt 3 von 5: Ausschuss-Gate, blockiert')

    fireEvent.pointerEnter(blocked)
    expect(await screen.findByRole('dialog')).toBeInTheDocument()

    fireEvent.mouseLeave(blocked, { relatedTarget: document.body })
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  })

  /*
   * WER KLICKT, MEINT "FESTHALTEN" (Review-Fund zu Spec 0387). Bis dahin galt ein per Ueberfahren
   * geoeffnetes Panel auch nach einem Klick weiter als hover-geoeffnet und schloss beim Verlassen
   * des Ausloesers - ein Klick blieb also folgenlos, obwohl er eine Absicht ausdrueckt. Der Fall
   * ist die Partition zu "schliesst ein per Ueberfahren geoeffnetes Panel beim Verlassen": beide
   * beginnen identisch, EIN Klick dazwischen kehrt das Ergebnis um.
   */
  it('haelt ein per Ueberfahren geoeffnetes Panel nach einem Klick fest, auch wenn der Zeiger geht', async () => {
    stubMatchMedia(true)
    const user = userEvent.setup()
    renderStepper()
    const blocked = gesperrterSchritt('Schritt 3 von 5: Ausschuss-Gate, blockiert')

    fireEvent.pointerEnter(blocked)
    expect(await screen.findByRole('dialog')).toBeInTheDocument()

    await user.click(blocked)
    fireEvent.mouseLeave(blocked, { relatedTarget: document.body })

    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  /* Bestehende `justOpenedByHoverRef`-Mechanik: der unmittelbar auf ein Hover-Oeffnen folgende
     Klick darf das Panel nicht sofort wieder schliessen. */
  it('haelt das Panel offen, wenn direkt nach dem Ueberfahren geklickt wird', async () => {
    stubMatchMedia(true)
    const user = userEvent.setup()
    renderStepper()
    const blocked = gesperrterSchritt('Schritt 3 von 5: Ausschuss-Gate, blockiert')

    fireEvent.pointerEnter(blocked)
    expect(await screen.findByRole('dialog')).toBeInTheDocument()

    await user.click(blocked)
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  /*
   * FOKUS ALS PARTITION, nicht als Positivfall: "springt nie" waere sonst von "springt immer"
   * nicht zu unterscheiden. Beim blossen Darueberfahren darf der Fokus NICHT ins Panel wandern -
   * beim frueheren, nicht fokussierbaren Ausloeser war das folgenlos, beim neuen waere es ein
   * Rueckschritt.
   */
  it('nimmt beim Ueberfahren den Fokus nicht, beim Klicken sehr wohl', async () => {
    stubMatchMedia(true)
    const user = userEvent.setup()
    renderStepper()
    const blocked = gesperrterSchritt('Schritt 3 von 5: Ausschuss-Gate, blockiert')

    fireEvent.pointerEnter(blocked)
    const panel = await screen.findByRole('dialog')
    expect(panel.contains(document.activeElement), 'Fokus ist ins Panel gesprungen').toBe(false)

    fireEvent.mouseLeave(blocked, { relatedTarget: document.body })
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())

    // Die andere Haelfte der Partition auf einem Geraet OHNE Hover: dort ist ein Klick wirklich
    // ein Klick. Auf einem hover-faehigen Geraet geht jedem Klick zwingend ein `pointerenter`
    // voraus - er waere dort also gar kein zweiter Fall, sondern derselbe.
    stubMatchMedia(false)
    await user.click(blocked)
    const zweitesPanel = await screen.findByRole('dialog')
    await waitFor(() =>
      expect(zweitesPanel.contains(document.activeElement), 'Fokus fehlt im Panel').toBe(true)
    )
  })

  // -----------------------------------------------------------------------------------------
  // Randfaelle
  // -----------------------------------------------------------------------------------------

  /* Edge Case 4: drei gleichzeitig gesperrte Schritte tragen drei UNABHAENGIGE Zustaende - ein
     geteilter `useState` waere der klassische Fehler an dieser Stelle. */
  it('oeffnet mit einem Sperrgrund nicht zugleich die anderen', async () => {
    const user = userEvent.setup()
    renderStepper()

    await user.click(gesperrterSchritt('Schritt 3 von 5: Ausschuss-Gate, blockiert'))
    await screen.findByRole('dialog')

    const panels = screen.getAllByRole('dialog')
    expect(panels).toHaveLength(1)
    // Der Grund des FUENFTEN Schritts steht zwar als sr-only-Text im Baum (aria-describedby),
    // aber nicht in einem geoeffneten Panel - genau das ist hier die Aussage.
    expect(within(panels[0]).queryByText('Führe zuerst die Kriterien-Bewertung oben aus.')).toBeNull()
  })

  /* Edge Case 6: leerer Sperrgrund (defensiver Fallback von `getBlockedReason` fuer
     `scan`/`ausschuss`) - kein leeres Panel und kein leeres aria-describedby-Ziel. */
  it('oeffnet bei leerem Sperrgrund kein Panel und verlinkt nichts', async () => {
    const user = userEvent.setup()
    renderStepper(
      [{ id: 'scan', isDone: false, isReachable: false }, ...FRESH_STATES.slice(1)],
      'ausschuss'
    )

    const blocked = gesperrterSchritt('Schritt 1 von 5: Scan, blockiert')
    expect(blocked).not.toHaveAttribute('aria-describedby')

    await user.click(blocked)
    expect(screen.queryByRole('dialog')).toBeNull()

    // Auch auf einem hover-faehigen Zeigergeraet stoesst das Ueberfahren hier nichts an - es gibt
    // kein Panel, das oeffnen koennte.
    stubMatchMedia(true)
    fireEvent.pointerEnter(blocked)
    expect(screen.queryByRole('dialog')).toBeNull()

    expect(fokussierbareInDerLeiste()).toHaveLength(5)
  })

  /*
   * Edge Cases 2 und 3 als VOLLSTAENDIGE Wahrheitstabelle ueber alle acht Kombinationen, nicht
   * ueber die drei bequemen Faelle - sonst wandert die Rangfolge bei der naechsten Umgestaltung
   * still. Es gilt: blockiert vor aktuell vor erledigt vor ausstehend fuer die Benennung, Haken
   * vor Schloss fuer die Glyphe.
   */
  it.each([
    { isDone: false, isReachable: true, isCurrent: false, auspraegung: 'ausstehend', glyphe: 'nummer' },
    { isDone: false, isReachable: true, isCurrent: true, auspraegung: 'aktuell', glyphe: 'nummer' },
    { isDone: true, isReachable: true, isCurrent: false, auspraegung: 'erledigt', glyphe: 'haken' },
    { isDone: true, isReachable: true, isCurrent: true, auspraegung: 'aktuell', glyphe: 'haken' },
    { isDone: false, isReachable: false, isCurrent: false, auspraegung: 'blockiert', glyphe: 'schloss' },
    { isDone: false, isReachable: false, isCurrent: true, auspraegung: 'blockiert', glyphe: 'schloss' },
    { isDone: true, isReachable: false, isCurrent: false, auspraegung: 'blockiert', glyphe: 'haken' },
    { isDone: true, isReachable: false, isCurrent: true, auspraegung: 'blockiert', glyphe: 'haken' },
  ])(
    'benennt erledigt=$isDone erreichbar=$isReachable aktuell=$isCurrent als $auspraegung mit der Glyphe $glyphe',
    ({ isDone, isReachable, isCurrent, auspraegung, glyphe }) => {
      renderStepper(
        [
          { id: 'gate', isDone, isReachable },
          ...ALLE_ERREICHBAR.filter((zustand) => zustand.id !== 'gate'),
        ],
        isCurrent ? 'gate' : 'scan'
      )

      const control = screen.getByLabelText(`Schritt 3 von 5: Ausschuss-Gate, ${auspraegung}`)
      expect(control.querySelector('[data-step-state]')).toHaveAttribute(
        'data-step-state',
        auspraegung
      )
      expect(control.querySelector('[data-glyph]')).toHaveAttribute('data-glyph', glyphe)
    }
  )

  /* Edge Case 1: kein aktiver Schritt (Index -1) - leerer Balken, keine Orientierungszeile, kein
     `aria-current`, und trotzdem fuenf Schritte. */
  it('zeigt ohne aktiven Schritt einen leeren Balken und keine Orientierungszeile', () => {
    renderStepper(ALLE_ERREICHBAR, 'unbekannt' as PipelineStepState['id'])

    const nav = screen.getByRole('navigation', { name: 'Fortschritt der Pipeline' })
    expect(nav.querySelector('progress')).toHaveAttribute('value', '0')
    expect(screen.queryByText(/^Schritt \d von 5: /)).toBeNull()
    expect(nav.querySelector('[aria-current]')).toBeNull()
    expect(within(nav).getAllByRole('listitem')).toHaveLength(5)
  })

  it('keeps exactly five list items - the responsive break uses utilities, not a second subtree', () => {
    // Zwei parallele Markup-Zweige (`hidden sm:flex` neben `flex sm:hidden`) wuerden Rollen, Namen
    // und Elementanzahl verdoppeln. Diese Kardinalitaet ist die Absicherung dagegen.
    renderStepper()

    const nav = screen.getByRole('navigation', { name: 'Fortschritt der Pipeline' })
    const items = within(nav).getAllByRole('listitem')
    expect(items).toHaveLength(5)
    expect(within(items[0]).getAllByText('Scan')).toHaveLength(1)
  })

  /*
   * Die vier Schrittzustaende bleiben ohne Farbwahrnehmung unterscheidbar: `aria-current` bzw.
   * `data-step-state` plus das Symbol im Marker tragen die Aussage, nicht die Farbe.
   */
  it('keeps the step states distinguishable without colour', () => {
    renderStepper(
      [
        { id: 'scan', isDone: true, isReachable: true },
        { id: 'ausschuss', isDone: false, isReachable: true },
        { id: 'gate', isDone: false, isReachable: false },
        { id: 'kriterien', isDone: false, isReachable: false },
        { id: 'kuratierung', isDone: false, isReachable: false },
      ],
      'ausschuss'
    )

    // `data-step-state` sitzt seit Spec 0387 am Marker IM Bedienelement, nicht mehr am
    // Bedienelement selbst - der Marker ist der Traeger der Auspraegung.
    function auspraegungVon(control: HTMLElement): string | null {
      return control.querySelector('[data-step-state]')?.getAttribute('data-step-state') ?? null
    }

    const current = screen.getByRole('link', { name: /schritt 2 von 5: ausschuss-erkennung/i })
    expect(current).toHaveAttribute('aria-current', 'step')
    expect(auspraegungVon(current)).toBe('aktuell')

    const done = screen.getByRole('link', { name: /schritt 1 von 5: scan/i })
    expect(auspraegungVon(done)).toBe('erledigt')
    expect(done).not.toHaveAttribute('aria-current')

    const blocked = gesperrterSchritt('Schritt 3 von 5: Ausschuss-Gate, blockiert')
    expect(auspraegungVon(blocked)).toBe('blockiert')
    expect(blocked).toHaveAttribute('aria-disabled', 'true')

    expect(new Set([current, done, blocked].map(auspraegungVon)).size).toBe(3)
  })
})
