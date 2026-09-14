import type { ProjectStand } from '../utils/pipelineSteps'
import { StatusTag } from './StatusTag'
import { Icon } from './ui/icon'

interface ProjectStandLineProps {
  stand: ProjectStand
  /** Nur fuer den Testanker - die Zeile traegt keine eigene Bedienung. */
  projectId: number
}

/**
 * Die Stand-Zeile einer Projektkarte: eine Zeile, vier Ausprägungen.
 *
 * Sie ENTSCHEIDET NICHTS - die Zuordnung Projektzustand -> Ausprägung liegt in
 * `utils/pipelineSteps.ts::deriveProjectStand`, damit sie nicht nur über das DOM prüfbar ist.
 * Hier steht ausschließlich, wie eine bereits entschiedene Ausprägung aussieht.
 *
 * Hierarchie über Farbe und Schnitt in EINER Zeile, ohne zweite Textzeile: das Präfix „Weiter:"
 * in `--text-muted`, der Schrittname in `--text-h` und Semi-Bold.
 *
 * Randfall B trägt das Symbol `check` ausdrücklich `aria-hidden` - das WORT trägt die Aussage - und
 * bewusst kein grünes Erfolgs-Kennzeichen: ein fertiges Projekt ist ein Ruhezustand, keine
 * Meldung. Laufende und fehlgeschlagene Läufe behalten dagegen die Kennzeichen-Optik; auf der
 * Karte trägt das Kennzeichen seine Aussage über Rand und Beschriftung, nicht über die Fläche.
 */
export function ProjectStandLine({ stand, projectId }: ProjectStandLineProps) {
  return (
    // Kein Flex-Container: die Zeile ist Fliesstext, und ein `gap` statt eines echten Leerzeichens
    // liesse "Weiter:Kuratierung" als Textinhalt zurueck - sichtbar getrennt, vorgelesen als ein
    // Wort.
    <span data-testid={`project-stand-${projectId}`} className="block min-w-0 text-sm">
      {stand.kind === 'weiter' && (
        <>
          <span className="text-text-muted">Weiter:</span>{' '}
          <span className="font-semibold text-text-h">{stand.stepLabel}</span>
        </>
      )}
      {stand.kind === 'hinweis' && <span className="text-text">{stand.label}</span>}
      {stand.kind === 'lauf' && <StatusTag status={stand.status} label={stand.label} />}
      {stand.kind === 'fertig' && (
        <>
          <span aria-hidden="true" className="inline-flex align-text-bottom text-text-muted">
            <Icon name="check" size={16} />
          </span>{' '}
          <span className="text-text">Alles erledigt</span>
        </>
      )}
    </span>
  )
}
