import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { ProjectOut } from '../api/types'
import type { PipelineStepState } from '../utils/pipelineSteps'
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
    last_remote_category_classification_run: null,
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

function renderStepper(
  states: PipelineStepState[] = FRESH_STATES,
  activeStepId: PipelineStepState['id'] = 'scan',
  projectOverrides: Partial<ProjectOut> = {}
) {
  return render(
    <MemoryRouter>
      <Stepper projectId={1} project={project(projectOverrides)} states={states} activeStepId={activeStepId} />
    </MemoryRouter>
  )
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

  it('renders a blocked (not reachable) step as a non-clickable, aria-disabled element, never hidden', () => {
    renderStepper()

    const blocked = screen.getByLabelText('Schritt 3 von 5: Ausschuss-Gate, blockiert')
    expect(blocked.tagName).not.toBe('A')
    expect(blocked).toHaveAttribute('aria-disabled', 'true')
    expect(blocked).toHaveAttribute('tabIndex', '-1')
    expect(screen.queryByRole('link', { name: /ausschuss-gate/i })).not.toBeInTheDocument()
  })

  it('offers a popover trigger next to a blocked step explaining the reason on click', async () => {
    const user = userEvent.setup()
    renderStepper()

    const reasonTrigger = screen.getByRole('button', {
      name: 'Grund für Sperrung von Schritt 3 von 5: Ausschuss-Gate anzeigen',
    })
    await user.click(reasonTrigger)

    expect(await screen.findByText('Sichte zuerst den Ausschuss oben.')).toBeInTheDocument()
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

    const reasonTrigger = screen.getByRole('button', {
      name: 'Grund für Sperrung von Schritt 4 von 5: Kriterien-Bewertung anzeigen',
    })
    await user.click(reasonTrigger)

    expect(await screen.findByText('Diese Funktion ist derzeit nicht aktiviert.')).toBeInTheDocument()
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

    const reasonTrigger = screen.getByRole('button', {
      name: 'Grund für Sperrung von Schritt 4 von 5: Kriterien-Bewertung anzeigen',
    })
    await user.click(reasonTrigger)

    expect(await screen.findByText('Bestätige zuerst den Ausschuss oben.')).toBeInTheDocument()
  })

  it('shows the criterion-scoring reason for a blocked kuratierung step', async () => {
    const user = userEvent.setup()
    renderStepper()

    const reasonTrigger = screen.getByRole('button', {
      name: 'Grund für Sperrung von Schritt 5 von 5: Kategorie-Kuratierung anzeigen',
    })
    await user.click(reasonTrigger)

    expect(
      await screen.findByText('Führe zuerst die Kriterien-Bewertung oben aus.')
    ).toBeInTheDocument()
  })

  /*
   * Ersetzt die fruehere `size-11`-Assertion (specs/features/0320-dark-utility-register.md,
   * Teststrategie): Die 44px-GROESSENregel ist zu einer TREFFERFLAECHENregel geworden - sichtbar
   * gilt das kompakte Board-Mass 32px, die 44px kommen ueber die beidachsige Aufspannung. Beide
   * Schritt-Marker, klickbar oder nicht, tragen weiterhin dasselbe Mass ("Konsistenz wichtiger
   * als Platzersparnis", Akzeptanzkriterium 15 der Spec 0042).
   */
  it('keeps every step marker at the shared board size with a spanned 44px tap target', () => {
    renderStepper()

    for (const marker of [
      screen.getByRole('link', { name: /schritt 1 von 5: scan/i }),
      screen.getByLabelText('Schritt 3 von 5: Ausschuss-Gate, blockiert'),
    ]) {
      expect(marker).toHaveClass('size-8')
      expect(marker).toHaveClass('tap-target-square')
    }
  })

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

    const current = screen.getByRole('link', { name: /schritt 2 von 5: ausschuss-erkennung/i })
    expect(current).toHaveAttribute('aria-current', 'step')
    expect(current).toHaveAttribute('data-step-state', 'aktuell')

    const done = screen.getByRole('link', { name: /schritt 1 von 5: scan/i })
    expect(done).toHaveAttribute('data-step-state', 'erledigt')
    expect(done).not.toHaveAttribute('aria-current')

    const blocked = screen.getByLabelText('Schritt 3 von 5: Ausschuss-Gate, blockiert')
    expect(blocked).toHaveAttribute('data-step-state', 'blockiert')
    expect(blocked).toHaveAttribute('aria-disabled', 'true')

    const states = [current, done, blocked].map((node) => node.getAttribute('data-step-state'))
    expect(new Set(states).size).toBe(3)
  })
})
