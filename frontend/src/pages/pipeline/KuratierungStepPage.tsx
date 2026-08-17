import { useState } from 'react'
import { Link, useOutletContext } from 'react-router'

import { Button } from '../../components/ui/button'
import { Input } from '../../components/ui/input'
import type { PipelineOutletContext } from './ProjectPipelineLayout'

/**
 * 1:1-Migration der bisherigen Kategorie-Kuratierungs-Section aus ProjectDetailPage.tsx
 * (Akzeptanzkriterium 7). Kein "nicht verfuegbar"-Zweig mehr noetig: der zentrale Redirect-Guard
 * in ProjectPipelineLayout rendert diese Route nur, wenn die Kriterien-Bewertung bereits
 * erfolgreich war (isReachable('kuratierung')).
 */
export function KuratierungStepPage() {
  const { project } = useOutletContext<PipelineOutletContext>()

  // Default 3 (UI/UX-Abschnitt der Spec 0024) - min=1/max=10 sind nur clientseitige Hinweise, die
  // eigentliche Grenze wird serverseitig durchgesetzt. `''` ist ein bewusst erlaubter
  // Zwischenzustand fuer ein geleertes Eingabefeld (Copilot-Review-Fund, PR #51).
  const [topNPerCategory, setTopNPerCategory] = useState<number | ''>(3)
  const effectiveTopNPerCategory = topNPerCategory === '' ? 3 : topNPerCategory

  return (
    <section className="flex flex-col items-start gap-3">
      <h2 className="text-lg font-semibold text-text-h">Kategorie-Kuratierung</h2>
      <p className="text-sm text-text">
        Zeigt pro Foto-Moment und Kategorie die besten N Fotos — sortierst du eines aus, rückt
        automatisch das nächstbeste derselben Kategorie nach.
      </p>

      <div className="flex flex-wrap items-end gap-3">
        <label htmlFor="top-n-per-category" className="flex flex-col gap-1 text-sm text-text">
          Top-Fotos pro Kategorie
          <Input
            id="top-n-per-category"
            type="number"
            min={1}
            max={10}
            value={topNPerCategory}
            onChange={(event) => {
              if (event.target.value === '') {
                setTopNPerCategory('')
                return
              }
              const value = event.target.valueAsNumber
              if (!Number.isNaN(value)) {
                setTopNPerCategory(Math.min(10, Math.max(1, Math.round(value))))
              }
            }}
            className="w-24"
          />
        </label>
        <Button asChild variant="secondary">
          <Link to={`/projects/${project.id}/curate?topN=${effectiveTopNPerCategory}`}>
            Kuratierung öffnen
          </Link>
        </Button>
      </div>
    </section>
  )
}
