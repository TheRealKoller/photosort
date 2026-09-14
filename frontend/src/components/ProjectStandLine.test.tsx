import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ProjectStandLine } from './ProjectStandLine'

/*
 * specs/features/0375-projektuebersicht-umfang-und-naechster-schritt.md.
 *
 * HIER, UND NUR HIER, STEHEN DIE ANZEIGETEXTE LITERAL. Die Zuordnung Projektzustand -> Ausprägung
 * prueft utils/pipelineSteps.test.ts ueber dem vollstaendig aufgezaehlten Eingaberaum; diese Datei
 * prueft ausschliesslich, wie eine bereits entschiedene Ausprägung gezeichnet wird - je einmal.
 *
 * Randfall B (`fertig`) ist ueber die Projekt-Schnittstelle strukturell unerreichbar
 * (`kuratierung.isDone` ist ohne Abschlusssignal konstant `false`). Seine Darstellung wird deshalb
 * DIREKT hier geprueft; es wird ausdruecklich KEIN Testeinstieg geschaffen, der den Zustand
 * kuenstlich ueber ein Projektobjekt erzeugt.
 */
describe('ProjectStandLine', () => {
  it('setzt das Praefix "Weiter:" vor den Schrittnamen', () => {
    render(<ProjectStandLine stand={{ kind: 'weiter', stepLabel: 'Kuratierung' }} projectId={7} />)

    expect(screen.getByTestId('project-stand-7')).toHaveTextContent('Weiter: Kuratierung')
  })

  it('zeigt einen Hinweis als reinen Text, ohne Praefix und ohne Kennzeichen', () => {
    render(
      <ProjectStandLine stand={{ kind: 'hinweis', label: 'Noch nicht gescannt' }} projectId={7} />,
    )

    const line = screen.getByTestId('project-stand-7')
    expect(line).toHaveTextContent('Noch nicht gescannt')
    expect(line.textContent).not.toContain('Weiter:')
    expect(line.querySelector('[data-status]')).toBeNull()
  })

  it('zeichnet einen laufenden Lauf als Kennzeichen mit Ringindikator', () => {
    render(
      <ProjectStandLine
        stand={{ kind: 'lauf', status: 'running', label: 'Ausschuss-Erkennung läuft…' }}
        projectId={7}
      />,
    )

    // Zugesichert wird der SEMANTISCHE Haken, nicht die CSS-Klasse.
    expect(screen.getByText('Ausschuss-Erkennung läuft…')).toHaveAttribute('data-status', 'running')
    expect(screen.getByTestId('status-tag-spinner')).toBeInTheDocument()
  })

  it('zeichnet einen fehlgeschlagenen Lauf als Kennzeichen ohne Ringindikator', () => {
    render(
      <ProjectStandLine
        stand={{ kind: 'lauf', status: 'failed', label: 'Kriterien-Bewertung fehlgeschlagen' }}
        projectId={7}
      />,
    )

    expect(screen.getByText('Kriterien-Bewertung fehlgeschlagen')).toHaveAttribute(
      'data-status',
      'failed',
    )
    expect(screen.queryByTestId('status-tag-spinner')).not.toBeInTheDocument()
  })

  it('zeigt Randfall B als Wort - das Symbol traegt die Aussage nicht', () => {
    render(<ProjectStandLine stand={{ kind: 'fertig' }} projectId={7} />)

    const line = screen.getByTestId('project-stand-7')
    expect(line).toHaveTextContent('Alles erledigt')
    // Kein gruenes Erfolgs-Kennzeichen: ein fertiges Projekt ist ein Ruhezustand, keine Meldung.
    expect(line.querySelector('[data-status]')).toBeNull()
  })

  it('haelt das Symbol von Randfall B aus der Vorlesereihenfolge heraus', () => {
    const { container } = render(<ProjectStandLine stand={{ kind: 'fertig' }} projectId={7} />)

    // Kein Zustand haengt allein an Farbe oder Form - das Wort steht daneben und traegt sie.
    expect(container.querySelector('svg')?.closest('[aria-hidden="true"]')).not.toBeNull()
  })
})
