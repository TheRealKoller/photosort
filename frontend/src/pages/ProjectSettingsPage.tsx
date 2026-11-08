import { useState } from 'react'
import { useParams } from 'react-router'

import { ApiError } from '../api/client'
import type { ProjectCameraOut, ProjectOut } from '../api/types'
import { CameraTimeOffsetDialog } from '../components/CameraTimeOffsetDialog'
import { ModelChoiceSection } from '../components/ModelChoiceSection'
import { DeleteProjectDialog } from '../components/DeleteProjectDialog'
import { Alert } from '../components/ui/alert'
import { Button } from '../components/ui/button'
import { Popover, PopoverClose, PopoverContent, PopoverTrigger } from '../components/ui/popover'
import { Skeleton } from '../components/ui/skeleton'
import { Switch } from '../components/ui/switch'
import { useCamerasQuery } from '../hooks/useCameras'
import { useProjectQuery, useSetCloudVisionConsentMutation } from '../hooks/useProjects'
import { formatProviderLabel } from '../utils/formatStats'
import { formatTimeOffset } from '../utils/timeOffset'

/**
 * Der Abschnitt „Kameras und Zeitversatz" - je Kamera eine RUHIGE Zeile: Bezeichnung,
 * Fotoanzahl, geltender Versatz und eine Schaltfläche.
 *
 * Die Bearbeitung liegt AUSDRÜCKLICH NICHT in der Zeile, sondern im Dialog: vier Eingabefelder
 * je Kamera nebeneinander wären bei mehreren Kameras unlesbar, und der Vorschlagsfluss braucht
 * ohnehin Platz.
 */
function CameraSection({ projectId }: { projectId: number }) {
  const query = useCamerasQuery(projectId)
  const [editing, setEditing] = useState<ProjectCameraOut | null>(null)

  return (
    <section className="flex flex-col gap-4 rounded-lg border border-border bg-surface p-4">
      <div>
        <h2 className="text-lg text-text-h">Kameras und Zeitversatz</h2>
        <p className="text-sm text-text">
          Geht die Uhr einer Kamera falsch, lässt sich die Abweichung hier einmal für dieses Projekt
          benennen. Die Originalfotos bleiben unverändert.
        </p>
      </div>

      {query.isLoading && (
        <div role="status" aria-label="Kameras werden geladen" className="flex flex-col gap-3">
          <Skeleton className="h-11 w-full rounded-lg" />
          <Skeleton className="h-11 w-full rounded-lg" />
        </div>
      )}

      {query.isError && (
        <Alert variant="error">
          {query.error instanceof ApiError
            ? query.error.detail
            : 'Die Kameraliste konnte nicht geladen werden.'}
        </Alert>
      )}

      {/* LEERZUSTAND: erklärender Text, kein Fehlerton - dass ein Projekt noch keine Kamera
          kennt, ist der Normalfall vor dem ersten Scan. Die Aussage ist die Hauptaussage des
          Abschnitts und steht deshalb in `--text`, nicht in `--text-muted`. */}
      {query.isSuccess && query.data.length === 0 && (
        <p className="text-sm text-text">
          Für dieses Projekt ist noch keine Kamera bekannt. Die Zuordnung entsteht beim Scan aus den
          Fotos selbst.
        </p>
      )}

      {query.isSuccess && query.data.length > 0 && (
        <ul className="flex flex-col">
          {query.data.map((entry) => (
            <li
              key={entry.id}
              data-camera-id={entry.id}
              className="flex min-h-11 flex-wrap items-center justify-between gap-3 border-b border-separator py-2 last:border-b-0"
            >
              <div className="flex min-w-0 flex-col">
                {/* Die Bezeichnung ist extern entstandener Text (Kamera-Firmware) und steht
                    ausschließlich als regulärer React-Textknoten. */}
                <span className="truncate font-medium text-text-h">{entry.label}</span>
                <span className="text-xs text-text-muted">
                  {entry.photo_count} {entry.photo_count === 1 ? 'Foto' : 'Fotos'} ·{' '}
                  {formatTimeOffset(entry.offset_minutes)}
                </span>
              </div>
              <Button
                variant="secondary"
                onClick={() => {
                  setEditing(entry)
                }}
              >
                Versatz ändern
              </Button>
            </li>
          ))}
        </ul>
      )}

      {/* Nur gerendert, solange er offen ist - dasselbe Unmount-Muster wie beim Löschdialog:
          es erfasst jeden künftig hinzukommenden Zustand des Dialogs automatisch mit, statt
          eine Reset-Liste zu führen, die beim nächsten `useState` still unvollständig wird. */}
      {editing !== null && query.isSuccess && (
        <CameraTimeOffsetDialog
          open
          onClose={() => {
            setEditing(null)
          }}
          projectId={projectId}
          camera={editing}
          cameras={query.data}
        />
      )}
    </section>
  )
}

/**
 * Der Einwilligungstext nennt die Anbieter der AKTUELLEN Wahl (Spec 0383) statt der festen
 * „Anthropic-Cloud-API": welche Cloud einwilligt wird, entscheidet `project.model_choice`, und
 * ein Text mit festem Anbieternamen wäre nach einer Umstellung schlicht unwahr. Bei
 * Eye-Kategorisierung bleibt die Kategorisierung auf diesem Server.
 */
function consentExplainer(project: ProjectOut): string {
  const choice = project.model_choice
  const landmarkProvider = formatProviderLabel(choice.landmark_provider ?? 'des Anbieters')
  const categoriesOnServer = choice.category_method === 'eye'
  const categoryProvider = categoriesOnServer
    ? null
    : formatProviderLabel(choice.category_provider ?? 'des Anbieters')
  const sameProvider = categoryProvider !== null && categoryProvider === landmarkProvider
  const parts = [
    `Fotos, die als Landschaft oder Gebäude erkannt wurden, werden zur Analyse an ${landmarkProvider} gesendet, um Sehenswürdigkeiten zu erkennen.`,
  ]
  parts.push(
    categoriesOnServer
      ? 'Derselbe Schalter gibt zusätzlich die optionale Remote-Kategorisierung frei — nicht nötig: die Kategorisierung dieses Projekts läuft auf diesem Server und sendet kein Foto.'
      : sameProvider
        ? `Derselbe Schalter gibt zusätzlich die optionale Remote-Kategorisierung frei (Kuratierungs-Schritt): dort ausgewählte Fotos werden an ${categoryProvider} gesendet, um ihre Kategorie aus dem festen Set und bis zu zwei freie Feinlabels zu bestimmen.`
        : `Derselbe Schalter gibt zusätzlich die optionale Remote-Kategorisierung frei (Kuratierungs-Schritt): dort ausgewählte Fotos werden an ${categoryProvider} gesendet, um ihre Kategorie aus dem festen Set und bis zu zwei freie Feinlabels zu bestimmen.`,
  )
  return parts.join(' ')
}

/**
 * Erste dedizierte Projekteinstellungs-Seite im Projekt - Toggle-Switch fuer die projektweite
 * Cloud-Bilderkennungs-Einwilligung + Info-Popover, das den Cloud-Versand erklaert.
 * Label/Erklaertext lauten auf "Cloud-Bilderkennung" - derselbe Schalter gated zusaetzlich die
 * Remote-Kategorie-Klassifizierung.
 *
 * Bewusst OHNE geraetespezifische Hover-Auto-Close-Logik (technische Detailentscheidung der
 * Umsetzung): dieses Popover sitzt an einer einzelnen Einstellungs-Zeile, wo Hover-Ergonomie
 * beim schnellen Durchsehen nicht zaehlt - ein reiner Klick/Tap-Trigger
 * (Popover.onOpenChange ueber den kontrollierten Radix-Default) reicht.
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
  const [deleteOpen, setDeleteOpen] = useState(false)

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

      <div className="flex flex-col gap-4 rounded-lg border border-border bg-surface p-4">
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
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Erkläre Cloud-Bilderkennung"
                  className="shrink-0 border border-border-control"
                >
                  i
                </Button>
              </PopoverTrigger>
              <PopoverContent>
                <div className="flex items-center justify-between gap-3 pb-3">
                  <p className="text-sm font-semibold text-text-h">Cloud-Bilderkennung</p>
                  <PopoverClose asChild>
                    <Button variant="ghost" size="icon" aria-label="Schließen" className="shrink-0">
                      <span aria-hidden="true">×</span>
                    </Button>
                  </PopoverClose>
                </div>
                <p className="text-sm text-text">{consentExplainer(project)}</p>
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

      {/* Modellwahl VOR der Cloud-Vision-Panel? Nein: sie sitzt ZWISCHEN Cloud-Panel und
          Kameras (Spec 0383) - die Einwilligung beschreibt den Datenabfluss, die Wahl bestimmt
          den Empfänger. Die Gefahrenzone bleibt das letzte Kind des gap-6-Containers. */}
      <ModelChoiceSection projectId={id} />

      <CameraSection projectId={id} />

      {/* GEFAHRENZONE, letztes Kind des gap-6-Containers. Bewusst hier und nicht in der
          Projektliste: die Namenseingabe als Huerde
          setzt voraus, dass man weiss, welches Projekt man vor sich hat - eine Liste ist eine
          Ueberflieg-Oberflaeche und der schlechtere Ort fuer eine irreversible Aktion. Die
          Einstellungsseite liegt als Querschnittsansicht vollstaendig ausserhalb des Arbeitspfads,
          waehrend jede der fuenf Pipeline-Schritt-Seiten auf ihm liegt.

          KEIN Alert, KEIN role="alert", KEIN Symbol: eine Gefahrenzone ist ein dauerhafter
          Abschnitt, keine Meldung - ein role="alert" kuendigte bei jedem Seitenaufruf einen Fehler
          an, den es nicht gibt. Farbe tragen ausschliesslich Rand und Schaltflaeche.

          Die freistehende --separator-Linie auf dem Seitengrund ist genau ihre dokumentierte
          Rolle; --border waere dort mit 1,45:1 keine Linie. */}
      <section className="border-t border-separator pt-6">
        <div className="flex flex-col gap-3 rounded-lg border border-danger bg-surface p-4">
          <h2 className="text-lg text-text-h">Gefahrenzone</h2>
          <p className="text-sm text-text">
            Löscht dieses Projekt mit allen PhotoSort-Daten — Fotodatensätze, Bewertungen,
            Kategorien und alle Bewertungs- und Kuratierungsläufe. Die Original-Fotos auf OpenCloud
            bleiben unverändert.
          </p>
          {/* Linksbuendig und allein in der Zeile - kein Nachbar-Bedienelement, damit die
              12px-Regel zwischen aufgespannten Trefferflaechen gar nicht erst zum Thema wird. */}
          <div>
            <Button
              variant="destructive"
              onClick={() => {
                setDeleteOpen(true)
              }}
            >
              Projekt löschen
            </Button>
          </div>
        </div>
      </section>

      {/* Nur gerendert, solange er offen ist. Das Grundelement gibt bei
          `open=false` zwar `null` zurueck, aber DeleteProjectDialog selbst blieb dabei gemountet -
          und mit ihm seine getippte Bestaetigung: wer den Namen einmal vollstaendig tippte und
          abbrach, fand die Loeschen-Schaltflaeche beim naechsten Oeffnen sofort freigeschaltet.
          Das Unmount ist bewusst die gewaehlte Variante und nicht ein Reset im Dialog selbst: es
          erfasst jeden kuenftig hinzukommende Zustand automatisch mit, statt eine Reset-Liste zu
          fuehren, die beim naechsten `useState` still unvollstaendig wird. Die `open`-Prop bleibt
          trotzdem, sie gehoert zur Schnittstelle des Grundelements. */}
      {deleteOpen && (
        <DeleteProjectDialog
          open
          onClose={() => {
            setDeleteOpen(false)
          }}
          projectId={id}
          projectName={project.name}
        />
      )}
    </div>
  )
}
