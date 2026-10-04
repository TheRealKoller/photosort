import { useOutletContext } from 'react-router'

import { SelectionTargetField } from '../../components/SelectionTargetField'
import { StepActionBar } from '../../components/StepActionBar'
import { deriveStepAction } from '../../utils/stepActions'
import type { PipelineOutletContext } from './ProjectPipelineLayout'

/**
 * Kuratierungs-Schritt der Pipeline: die Richtwert-Einstellung und der Weg in den Album-Entwurf
 * als einzige Hauptaktion in der Aktionsleiste.
 *
 * Das Feld ist DIESELBE Komponente wie im Klassifizierungs-Schritt (`SelectionTargetField`) -
 * eine zweite Kopie liefe beim nächsten Zustand auseinander.
 */
export function KuratierungStepPage() {
  const { project } = useOutletContext<PipelineOutletContext>()
  const { action } = deriveStepAction('kuratierung', project, {
    openCount: null,
    isTriggerPending: false,
  })

  return (
    <section className="flex flex-col items-start gap-3">
      <h2 className="text-lg">Kuratierung</h2>
      <p className="text-sm text-text">
        Der Vorschlag deckt alle Foto-Momente ab und mischt in jedem die vorkommenden Motive. Der
        Richtwert ist ein Ziel, keine Obergrenze — reicht der Bildbestand nicht, wird der Vorschlag
        kleiner; damit jeder Foto-Moment vorkommt, kann er auch größer werden.
      </p>

      <SelectionTargetField project={project} />

      <StepActionBar action={action} />
    </section>
  )
}
