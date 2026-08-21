import { useState } from 'react'
import { useParams } from 'react-router'

import { ApiError } from '../api/client'
import { Alert } from '../components/ui/alert'
import { Popover, PopoverClose, PopoverContent, PopoverTrigger } from '../components/ui/popover'
import { Switch } from '../components/ui/switch'
import { useProjectQuery, useSetCloudLandmarkConsentMutation } from '../hooks/useProjects'

/**
 * Erste dedizierte Projekteinstellungs-Seite im Projekt (specs/features/0047-sehenswuerdigkeit-
 * erkennung-cloud-vision-api.md, UI/UX-Abschnitt) - Toggle-Switch fuer die projektweite Cloud-
 * Sehenswuerdigkeit-Einwilligung + Info-Popover, das den Cloud-Versand erklaert.
 *
 * Bewusst OHNE die geraetespezifische Hover-Auto-Close-Logik von CriterionDetailsPopover.tsx
 * (technische Detailentscheidung der Umsetzung): dieses Popover sitzt an einer einzelnen
 * Einstellungs-Zeile, nicht an potenziell Dutzenden Grid-Kacheln, wo Hover-Ergonomie beim
 * schnellen Durchsehen tatsaechlich zaehlt (siehe Design-System, "Durchsatz vor Erklaerung") -
 * ein reiner Klick/Tap-Trigger (Popover.onOpenChange ueber den kontrollierten Radix-Default)
 * reicht hier aus, ohne den Mehraufwand des Hover-Grace-Bereichs unnoetig zu duplizieren.
 *
 * Busy-Button-Muster (Design-System): der Switch wird waehrend einer laufenden PUT-Anfrage
 * disabled, um ein Doppel-Toggle/eine Race gegen die eigene, noch nicht abgeschlossene Anfrage zu
 * vermeiden - exakt dieselbe Regel wie fuer jeden anderen ausloesenden Button im Produkt.
 */
export function ProjectSettingsPage() {
  const { projectId } = useParams()
  const id = Number(projectId)
  const query = useProjectQuery(id)
  const consentMutation = useSetCloudLandmarkConsentMutation(id)
  const [infoOpen, setInfoOpen] = useState(false)

  if (query.isError && query.error instanceof ApiError && query.error.status === 404) {
    return (
      <div className="flex flex-col items-start gap-3">
        <p className="text-text">Projekt nicht gefunden.</p>
      </div>
    )
  }

  if (query.isLoading) {
    return (
      <p role="status" className="text-sm text-text">
        Projekt wird geladen…
      </p>
    )
  }

  if (query.isError || !query.data) {
    return (
      <div className="flex flex-col items-start gap-3">
        <Alert>
          {query.error instanceof ApiError ? query.error.detail : 'Fehler beim Laden des Projekts.'}
        </Alert>
      </div>
    )
  }

  const project = query.data

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-2xl font-semibold text-text-h">Projekteinstellungen</h1>
        <p className="text-sm text-text">{project.name}</p>
      </header>

      <div className="flex flex-col gap-4 rounded-md border border-border p-4">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span id="cloud-landmark-consent-label" className="font-medium text-text-h">
              Cloud-Sehenswürdigkeit-Erkennung
            </span>
            <Popover open={infoOpen} onOpenChange={setInfoOpen}>
              <PopoverTrigger asChild>
                <button
                  type="button"
                  aria-label="Erkläre Cloud-Sehenswürdigkeit-Erkennung"
                  className="flex size-11 shrink-0 items-center justify-center rounded-md border border-border text-xs font-semibold text-text transition-colors hover:bg-border/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-bg"
                >
                  i
                </button>
              </PopoverTrigger>
              <PopoverContent>
                <div className="flex items-center justify-between gap-3 pb-3">
                  <p className="text-sm font-semibold text-text-h">
                    Cloud-Sehenswürdigkeit-Erkennung
                  </p>
                  <PopoverClose
                    aria-label="Schließen"
                    className="flex size-8 shrink-0 items-center justify-center rounded-md text-text hover:bg-border/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                  >
                    <span aria-hidden="true">×</span>
                  </PopoverClose>
                </div>
                <p className="text-sm text-text">
                  Fotos, die als Landschaft oder Gebäude erkannt wurden, werden zur Analyse an die
                  Anthropic-Cloud-API versendet.
                </p>
              </PopoverContent>
            </Popover>
          </div>
          <Switch
            checked={project.cloud_landmark_detection_enabled}
            onCheckedChange={(next) => consentMutation.mutate(next)}
            disabled={consentMutation.isPending}
            aria-labelledby="cloud-landmark-consent-label"
          />
        </div>
      </div>
    </div>
  )
}
