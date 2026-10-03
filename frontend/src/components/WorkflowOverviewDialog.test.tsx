import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { describe, expect, it, vi } from 'vitest'

import type { ProjectOut } from '../api/types'
import { DRAFT_CLOUD_CONSENT_TEXT, SETTINGS_LINK_LABEL } from '../pages/AlbumDraftPage'
import {
  criterionRunSummary,
  enumerateProjects,
  projectFixture,
  scanSummary,
  scoringRunSummary,
} from '../test/projectStateSpace'
import {
  computeStepStates,
  deriveWorkflowOverview,
  getDefaultStepId,
  PIPELINE_STEPS,
} from '../utils/pipelineSteps'
import { STATION_LABELS } from '../utils/projectRoutes'
import { OVERVIEW_TEXTS } from '../utils/workflowOverview'
import { Stepper } from './Stepper'
import { WorkflowOverviewDialog } from './WorkflowOverviewDialog'

const GATE = '2026-08-12T09:30:00Z'

/** Kuratierung erreichbar, alles davor erledigt - jeder Eintrag hat seine Öffnen-Schaltfläche. */
const ALL_REACHABLE = projectFixture({
  id: 9,
  last_scan: scanSummary('success'),
  last_scoring_run: scoringRunSummary('success', GATE),
  last_criterion_scoring_run: criterionRunSummary('success'),
})

function renderDialog(
  project: ProjectOut,
  { onClose = vi.fn(), onOpenEntry = vi.fn() } = {},
): { onClose: () => void; onOpenEntry: () => void } {
  render(
    <MemoryRouter>
      <WorkflowOverviewDialog project={project} open onClose={onClose} onOpenEntry={onOpenEntry} />
    </MemoryRouter>,
  )
  return { onClose, onOpenEntry }
}

function entry(id: string): HTMLElement {
  const element = screen
    .getByRole('dialog')
    .querySelector<HTMLElement>(`[data-overview-entry="${id}"]`)
  if (element === null) {
    throw new Error(`Eintrag ${id} fehlt`)
  }
  return element
}

describe('WorkflowOverviewDialog: Inhalt', () => {
  it('ist ein Dialog "Ablauf im Überblick" mit Beschreibung', () => {
    renderDialog(ALL_REACHABLE)

    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveAccessibleName('Ablauf im Überblick')
    expect(dialog).toHaveAccessibleDescription(
      'Von den Fotos im OpenCloud-Ordner bis zur gemeinsamen Endauswahl. Bei jedem Schritt siehst du, wie weit dieses Projekt ist.',
    )
  })

  it('nennt die Schritte exakt wie die Schrittleiste, danach die Stationen', () => {
    renderDialog(ALL_REACHABLE)

    const steps = screen.getByRole('list', { name: 'Schritte' })
    expect(
      within(steps)
        .getAllByRole('heading', { level: 3 })
        .map((heading) => heading.textContent),
    ).toEqual(PIPELINE_STEPS.map((step) => step.label))

    const after = screen.getByRole('list', { name: 'Danach' })
    expect(
      within(after)
        .getAllByRole('heading', { level: 3 })
        .map((heading) => heading.textContent),
    ).toEqual([STATION_LABELS.album, STATION_LABELS.selection])
  })

  it('zeigt Zweck, Kennzeichnung, Zuständigkeit und Vorbedingung je Eintrag', () => {
    renderDialog(ALL_REACHABLE)

    for (const [id, text] of Object.entries(OVERVIEW_TEXTS)) {
      const element = entry(id)
      expect(within(element).getByText(text.purpose)).toBeInTheDocument()
      expect(within(element).getByText(text.worker.kind)).toBeInTheDocument()
      expect(element).toHaveTextContent(text.worker.detail)
      if (text.responsibility === null) {
        expect(within(element).queryByText('Zuständig')).toBeNull()
      } else {
        expect(within(element).getByText(text.responsibility)).toBeInTheDocument()
      }
      if (text.prerequisite === null) {
        expect(within(element).queryByText('Vorher')).toBeNull()
      } else {
        expect(within(element).getByText(text.prerequisite.text)).toBeInTheDocument()
      }
    }
  })

  it('zeigt am Album-Entwurf den Text des Leerzustands und den Weg zu den Einstellungen', () => {
    renderDialog(ALL_REACHABLE)

    const album = entry('album')
    expect(within(album).getByText(DRAFT_CLOUD_CONSENT_TEXT)).toBeInTheDocument()
    expect(within(album).getByRole('link', { name: SETTINGS_LINK_LABEL })).toHaveAttribute(
      'href',
      '/projects/9/settings',
    )
  })

  it('kündigt nichts über aria-live an - jeder Poll würde sonst vorgelesen', () => {
    renderDialog(ALL_REACHABLE)

    expect(screen.getByRole('dialog').querySelector('[aria-live]')).toBeNull()
  })
})

describe('WorkflowOverviewDialog: Bedienung', () => {
  it('gibt jedem erreichbaren Eintrag genau eine Öffnen-Schaltfläche mit dem Ziel der Leiste', () => {
    renderDialog(ALL_REACHABLE)

    for (const item of deriveWorkflowOverview(ALL_REACHABLE)) {
      const links = within(entry(item.id))
        .getAllByRole('link')
        .filter((link) => link.textContent?.endsWith(' öffnen'))
      expect(links).toHaveLength(1)
      expect(links[0]).toHaveAttribute('href', item.to)
    }
  })

  it('hebt nur die Schaltfläche des aktuellen Eintrags als primär hervor', () => {
    const project = projectFixture({ last_scan: scanSummary('success') })
    renderDialog(project)

    // Primär ist die gefüllte Akzentfläche, sekundär der Umriss (ui/button.tsx).
    expect(screen.getByRole('link', { name: 'Ausschuss öffnen' })).toHaveClass('bg-accent')
    expect(screen.getByRole('link', { name: 'Scan öffnen' })).toHaveClass('border-border-control')
    expect(screen.getByRole('link', { name: 'Scan öffnen' })).not.toHaveClass('bg-accent')
  })

  it('gibt gesperrten Einträgen kein Bedienelement, sondern den Sperrgrund als Text', () => {
    const project = projectFixture({ last_scan: scanSummary('success') })
    renderDialog(project)

    for (const id of ['kriterien', 'kuratierung', 'album', 'selection']) {
      const element = entry(id)
      expect(within(element).queryAllByRole('link')).toHaveLength(0)
      expect(within(element).queryAllByRole('button')).toHaveLength(0)
      expect(within(element).getByText('gesperrt')).toBeInTheDocument()
    }
    expect(
      within(entry('kriterien')).getByText('Bestätige zuerst den Ausschuss oben.'),
    ).toBeInTheDocument()
    expect(
      within(entry('album')).getByText('Führe zuerst die Klassifizierung oben aus.'),
    ).toBeInTheDocument()
  })

  it('nennt eine abgeschaltete Klassifizierung ohne Öffnen-Schaltfläche, auch nach einem Lauf', () => {
    renderDialog({ ...ALL_REACHABLE, category_selection_enabled: false })

    const kriterien = entry('kriterien')
    expect(within(kriterien).getByText('abgeschaltet')).toBeInTheDocument()
    expect(
      within(kriterien).getByText('Diese Funktion ist derzeit nicht aktiviert.'),
    ).toBeInTheDocument()
    expect(within(kriterien).queryAllByRole('link')).toHaveLength(0)
  })

  it('zeigt Stationen als "jederzeit möglich", nie als erledigt', () => {
    renderDialog(ALL_REACHABLE)

    for (const id of ['album', 'selection']) {
      expect(within(entry(id)).getByText('jederzeit möglich')).toBeInTheDocument()
      expect(within(entry(id)).queryByText('erledigt')).toBeNull()
    }
  })

  it('zeigt Lauf und Fehlschlag als Wort beim Schritt', () => {
    renderDialog(
      projectFixture({
        last_scan: scanSummary('failed'),
        last_scoring_run: scoringRunSummary('running', null),
      }),
    )

    expect(within(entry('scan')).getByText('fehlgeschlagen')).toHaveAttribute(
      'data-status',
      'failed',
    )
    expect(within(entry('ausschuss')).getByText('läuft…')).toHaveAttribute('data-status', 'running')
  })

  it('schließt über "Schließen" und Esc', async () => {
    const user = userEvent.setup()
    const { onClose } = renderDialog(ALL_REACHABLE)

    await user.click(screen.getByRole('button', { name: 'Schließen' }))
    await user.keyboard('{Escape}')

    expect(onClose).toHaveBeenCalledTimes(2)
  })

  it('meldet den Klick auf einen Eintrag, damit "gesehen" gemerkt wird', async () => {
    const user = userEvent.setup()
    const { onOpenEntry } = renderDialog(ALL_REACHABLE)

    await user.click(screen.getByRole('link', { name: 'Kuratierung öffnen' }))

    expect(onOpenEntry).toHaveBeenCalledTimes(1)
  })

  it('führt Tab von "Schließen" in DOM-Reihenfolge durch die Öffnen-Schaltflächen', async () => {
    const user = userEvent.setup()
    renderDialog(ALL_REACHABLE)
    expect(screen.getByRole('button', { name: 'Schließen' })).toHaveFocus()

    const order: string[] = []
    for (let step = 0; step < 8; step += 1) {
      await user.tab()
      order.push(document.activeElement?.textContent ?? '')
    }

    expect(order).toEqual([
      'Scan öffnen',
      'Ausschuss öffnen',
      'Klassifizierung öffnen',
      'Kuratierung öffnen',
      'Album-Entwurf öffnen',
      SETTINGS_LINK_LABEL,
      'Endauswahl öffnen',
      'Schließen',
    ])
  })
})

/*
 * Gleichlauf im selben DOM: Schrittleiste und Dialog für je eine Vertreterlage jeder beobachteten
 * Zustandsklasse. Verglichen werden Glyphe je Schritt, Sperrgrund und Zustandswort aller Schritte
 * außer der Leistenposition ("aktuell" ist dort eine Ortsangabe, kein Zustand).
 */
describe('WorkflowOverviewDialog: Gleichlauf mit der Schrittleiste', () => {
  const representatives = new Map<string, ProjectOut>()
  for (const project of enumerateProjects()) {
    const signature = deriveWorkflowOverview(project)
      .map((item) => `${item.id}:${item.state}:${item.isDone}`)
      .join('|')
    if (!representatives.has(signature)) {
      representatives.set(signature, project)
    }
  }

  const LEISTEN_WORT: Record<string, string> = { abgeschaltet: 'gesperrt' }

  it.each([...representatives.entries()])('stimmt in Lage %s überein', (_signature, project) => {
    const states = computeStepStates(project)
    const activeStepId = getDefaultStepId(states)
    render(
      <MemoryRouter>
        <Stepper
          projectId={project.id}
          project={project}
          states={states}
          activeStepId={activeStepId}
        />
        <WorkflowOverviewDialog project={project} open onClose={vi.fn()} onOpenEntry={vi.fn()} />
      </MemoryRouter>,
    )
    const nav = screen.getByRole('navigation', { name: 'Fortschritt der Pipeline' })

    PIPELINE_STEPS.forEach((step, index) => {
      const control = within(nav).getByLabelText(
        new RegExp(`^Schritt ${index + 1} von ${PIPELINE_STEPS.length}: ${step.label}, `),
      )
      const item = entry(step.id)
      const overview = deriveWorkflowOverview(project).find((candidate) => candidate.id === step.id)

      expect(item.querySelector('[data-glyph]')?.getAttribute('data-glyph')).toBe(
        control.querySelector('[data-glyph]')?.getAttribute('data-glyph'),
      )
      if (overview?.blockedReason) {
        expect(control).toHaveAccessibleDescription(overview.blockedReason)
        expect(within(item).getByText(overview.blockedReason)).toBeInTheDocument()
      }
      if (step.id !== activeStepId && overview !== undefined) {
        const word = LEISTEN_WORT[overview.state] ?? overview.state
        expect(control.getAttribute('aria-label')).toBe(
          `Schritt ${index + 1} von ${PIPELINE_STEPS.length}: ${step.label}, ${word}`,
        )
      }
    })
  })
})
