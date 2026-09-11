import { useState } from 'react'
import { Link, useOutletContext } from 'react-router'

import { Button } from '../../components/ui/button'
import { Input } from '../../components/ui/input'
import { DEFAULT_TOP_N, MAX_TOP_N, MIN_TOP_N } from '../../utils/curationTopN'
import type { PipelineOutletContext } from './ProjectPipelineLayout'

/**
 * 1:1-Migration der bisherigen Kategorie-Kuratierungs-Section aus ProjectDetailPage.tsx
 * (Akzeptanzkriterium 7). Kein "nicht verfuegbar"-Zweig mehr noetig: der zentrale Redirect-Guard
 * in ProjectPipelineLayout rendert diese Route nur, wenn die Kriterien-Bewertung bereits
 * erfolgreich war (isReachable('kuratierung')).
 *
 * Die "Remote-Kategorisierung"-Section ist nicht hier eingebunden, sondern auf
 * KriterienStepPage.tsx (fachlich
 * naeher an ihrer Wirkung: Ergebnisse fliessen erst durch einen Kriterien-Bewertungs-Lauf ein).
 */
export function KuratierungStepPage() {
  const { project } = useOutletContext<PipelineOutletContext>()

  // Standardwert und Grenzen kommen aus utils/curationTopN.ts (eine Stelle fuer beide Seiten) -
  // die Grenzen sind nur clientseitige Hinweise, die eigentliche Grenze wird serverseitig
  // durchgesetzt. `''` ist ein bewusst erlaubter Zwischenzustand fuer ein geleertes Eingabefeld.
  const [topNPerCategory, setTopNPerCategory] = useState<number | ''>(DEFAULT_TOP_N)
  const effectiveTopNPerCategory = topNPerCategory === '' ? DEFAULT_TOP_N : topNPerCategory

  return (
    <div className="flex flex-col gap-8">
      <section className="flex flex-col items-start gap-3">
        <h2 className="text-lg">Kategorie-Kuratierung</h2>
        {/* Der frühere Satz "sortierst du eines aus, rückt automatisch das nächstbeste derselben
            Kategorie nach" ist unwahr — es rückt nichts mehr nach. */}
        <p className="text-sm text-text">
          Zeigt pro Foto-Moment und Kategorie die besten N Fotos — verworfene Fotos bleiben an ihrer
          Stelle sichtbar, und weitere Kandidaten lassen sich bei Bedarf einblenden.
        </p>

        <div className="flex flex-wrap items-end gap-3">
          <label htmlFor="top-n-per-category" className="flex flex-col gap-1 text-sm text-text">
            Top-Fotos pro Kategorie
            <Input
              id="top-n-per-category"
              type="number"
              min={MIN_TOP_N}
              max={MAX_TOP_N}
              value={topNPerCategory}
              onChange={(event) => {
                if (event.target.value === '') {
                  setTopNPerCategory('')
                  return
                }
                const value = event.target.valueAsNumber
                if (!Number.isNaN(value)) {
                  setTopNPerCategory(Math.min(MAX_TOP_N, Math.max(MIN_TOP_N, Math.round(value))))
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
    </div>
  )
}
