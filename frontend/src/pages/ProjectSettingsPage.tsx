import { useState } from 'react'
import { useParams } from 'react-router'

import { ApiError } from '../api/client'
import { Alert } from '../components/ui/alert'
import { Popover, PopoverClose, PopoverContent, PopoverTrigger } from '../components/ui/popover'
import { Switch } from '../components/ui/switch'
import { useProjectQuery, useSetCloudVisionConsentMutation } from '../hooks/useProjects'

/**
 * Erste dedizierte Projekteinstellungs-Seite im Projekt (specs/features/0047-sehenswuerdigkeit-
 * erkennung-cloud-vision-api.md, UI/UX-Abschnitt) - Toggle-Switch fuer die projektweite Cloud-
 * Bilderkennungs-Einwilligung + Info-Popover, das den Cloud-Versand erklaert. Label/Erklaertext
 * seit specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md auf
 * "Cloud-Bilderkennung" erweitert (reine Textpflege, kein neues UI-Element) - derselbe Schalter
 * gated ab sofort zusaetzlich die neue Remote-Kategorie-Klassifizierung.
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
  const consentMutation = useSetCloudVisionConsentMutation(id)
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
        <h1 className="text-xl sm:text-2xl">Projekteinstellungen</h1>
        <p className="text-sm text-text">{project.name}</p>
      </header>

      <div className="flex flex-col gap-4 rounded-xl border border-border bg-surface p-4">
        {/* flex-wrap + min-w-0 auf der Label-Gruppe (Review-Fund, ship-feature-Runde): auf sehr
            engen Viewports (<400px) soll das lange, zusammengesetzte Label auf eine eigene Zeile
            umbrechen koennen, statt den Switch aus der Zeile zu draengen/zu ueberlappen. */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2">
            <span id="cloud-vision-consent-label" className="font-medium text-text-h">
              Cloud-Bilderkennung
            </span>
            <Popover open={infoOpen} onOpenChange={setInfoOpen}>
              <PopoverTrigger asChild>
                <button
                  type="button"
                  aria-label="Erkläre Cloud-Bilderkennung"
                  className="tap-target-square flex size-8 shrink-0 items-center justify-center rounded-md border border-border-control text-xs font-semibold text-text transition-colors hover:bg-overlay hover:text-text-h active:bg-border active:text-text-muted"
                >
                  i
                </button>
              </PopoverTrigger>
              <PopoverContent>
                <div className="flex items-center justify-between gap-3 pb-3">
                  <p className="text-sm font-semibold text-text-h">Cloud-Bilderkennung</p>
                  <PopoverClose
                    aria-label="Schließen"
                    className="tap-target-square flex size-8 shrink-0 items-center justify-center rounded-md text-text transition-colors hover:bg-overlay hover:text-text-h active:bg-border active:text-text-muted"
                  >
                    <span aria-hidden="true">×</span>
                  </PopoverClose>
                </div>
                <p className="text-sm text-text">
                  Fotos, die als Landschaft oder Gebäude erkannt wurden, werden zur Analyse an die
                  Anthropic-Cloud-API versendet, um Sehenswürdigkeiten zu erkennen. Derselbe
                  Schalter gibt zusätzlich die optionale Remote-Kategorisierung frei (Kuratierungs-
                  Schritt): dort ausgewählte Fotos werden an dieselbe Cloud-API gesendet, um ihre
                  Kategorie aus dem festen Set und bis zu zwei freie Feinlabels zu bestimmen.
                </p>
              </PopoverContent>
            </Popover>
          </div>
          <Switch
            checked={project.cloud_vision_detection_enabled}
            onCheckedChange={(next) => consentMutation.mutate(next)}
            disabled={consentMutation.isPending}
            aria-labelledby="cloud-vision-consent-label"
          />
        </div>
      </div>
    </div>
  )
}
