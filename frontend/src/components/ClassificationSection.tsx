import { useEffect, useId, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router'

import { ApiError } from '../api/client'
import type { ClassificationWay, ProjectOut } from '../api/types'
import {
  useClassificationEstimateQuery,
  useFineLabelsQuery,
  useTriggerClassificationMutation,
} from '../hooks/useProjects'
import { useTriggerConfirmation } from '../hooks/useTriggerConfirmation'
import { formatProviderLabel } from '../utils/formatStats'
import { deriveStepAction } from '../utils/stepActions'
import { ClassificationBalance } from './ClassificationBalance'
import { ClassificationEstimate } from './ClassificationEstimate'
import { ClassificationProgress } from './ClassificationProgress'
import { EyeAttribution } from './EyeAttribution'
import { RerunBlock } from './RerunBlock'
import { SelectionTargetField } from './SelectionTargetField'
import { StatusDot } from './StatusDot'
import { StepActionBar } from './StepActionBar'
import { Alert } from './ui/alert'

interface ClassificationSectionProps {
  project: ProjectOut
  refetchProject: () => unknown
}

/**
 * Obergrenze der angezeigten Feinlabels (maximal die haeufigsten 10-15 Eintraege). Die Kuerzung
 * sitzt bewusst HIER und nicht im Backend: der Endpunkt ist eine vollstaendige Auswertung, die
 * Begrenzung eine reine Darstellungsentscheidung gegen Ueberinformation.
 */
const MAX_FINE_LABELS_SHOWN = 15

/**
 * Die EINE "Klassifizierung"-Section auf KriterienStepPage.tsx. Ersetzt die frueher getrennten
 * Bedienelemente "Kriterien-Bewertung" (inline auf der Seite) und "Remote-Kategorisierung"
 * (RemoteCategoryClassificationSection.tsx, geloescht) vollstaendig - ein Auslöser, eine
 * Statusanzeige, ein Fortschritt.
 *
 * Drei Aenderungen gegenueber dem abgeloesten Stand, die leicht als Versehen gelesen werden
 * koennten und es nicht sind:
 *
 * 1. KEIN Bestaetigungsdialog mehr vor der kostenpflichtigen Aktion. Das Design-System-Muster ist
 *    mit dieser Spec ausdruecklich zurueckgenommen und durch die dauerhaft am Auslöser
 *    sichtbare Kostenschaetzung ersetzt - ein Dialog zeigte die Kosten erst NACH einem Klick und
 *    verschwand wieder. Bewusst in Kauf genommenes Restrisiko: bei vorausgewaehlter Checkbox
 *    loest ein einzelner Klick Cloud-Kosten aus.
 * 2. Der Hinweis "Diese Ergebnisse fliessen erst durch einen (ggf. erneuten) Kriterien-
 *    Bewertungs-Lauf ein" ist ersatzlos entfallen - die Verkettung im Backend macht
 *    ihn gegenstandslos.
 * 3. Die Aussage "laeuft vollstaendig lokal auf diesem Server" haengt jetzt am Checkbox-Zustand
 *    statt absolut dazustehen. Sie war zuvor schlicht unwahr, sobald die Cloud-Bilderkennung
 *    freigegeben war (die Sehenswuerdigkeits-Erkennung lief innerhalb der Bewertung mit).
 *
 * `useTriggerConfirmation` (etabliert fuer Scan/Score) ueberbrueckt unveraendert das Zeitfenster
 * zwischen der 202-Antwort und dem ersten Poll, der `status="running"` bestaetigt.
 *
 * Diese Datei ist der CONTAINER - Laufwahl, Consent-Gate, Mutation und Ausloeser bleiben hier, die
 * drei Detailbloecke (ClassificationEstimate, ClassificationProgress, ClassificationBalance) sind
 * eigene Komponenten.
 *
 * DIE LAUFWAHL (Spec 0609) ersetzt seit dieser Fassung die Checkbox: drei Wege, genau einer,
 * ohne Vorbelegung. Keine Vorbelegung ist die eigentliche Aenderung - die fruehere Checkbox war
 * mit der Projekteinstellung vorbelegt, und ein einzelner Klick loeste Cloud-Kosten aus. Jetzt
 * beginnt jeder Ausloesevorgang mit einer bewussten Wahl, und nach dem Start faellt sie zurueck
 * auf "nichts gewaehlt".
 *
 * Der Eye-Weg erscheint nur, wenn der Server ihn anbietet (`ProjectOut.eye_available`, allein aus
 * `EYE_ENABLED`). Ob der DIENST gerade antwortet, wird hier NICHT geprueft: das machte das Laden
 * der Projektseite von einem Sidecar abhaengig, und die Antwort auf einen toten Dienst gibt es
 * erst beim Ausloesen (503, mit "Erneut versuchen").
 *
 * Im Inhalt steht zu jedem Zeitpunkt GENAU EINER der beiden Zustandsbloecke - Fortschrittsliste
 * ODER Bilanz, nie beide. Das ist die pruefbare Form des Akzeptanzkriteriums "ueberfrachtet die
 * Seite nicht". Auslöser und Laufstatus stehen in der Aktionsleiste am Ende, „Erneut
 * klassifizieren" im Kopf; `isTriggerDisabled` sperrt alle drei Auslöser gleich.
 */
export function ClassificationSection({ project, refetchProject }: ClassificationSectionProps) {
  // Der Weg wird HIER gehalten und an die Schaetzung weitergereicht: je Weg liegt eine eigene
  // Query, und solange nichts gewaehlt ist, laedt gar keine.
  const [way, setWay] = useState<ClassificationWay | null>(null)
  const estimateQuery = useClassificationEstimateQuery(project.id, way)
  const fineLabelsQuery = useFineLabelsQuery(project.id)
  const triggerMutation = useTriggerClassificationMutation(project.id)
  const location = useLocation()
  const headingRef = useRef<HTMLHeadingElement>(null)

  // Nur nach dem automatischen Wechsel aus dem Ausschuss: Der Fokus läge sonst auf dem entfernten
  // Abschluss-Knopf und fiele auf `body`. Bei einem normalen Aufruf bleibt er, wo er ist.
  const focusHeading = (location.state as { focusHeading?: boolean } | null)?.focusHeading === true
  useEffect(() => {
    if (focusHeading) {
      headingRef.current?.focus()
    }
  }, [focusHeading])

  const consentEnabled = project.cloud_vision_detection_enabled
  const wayGroupName = useId()

  const scoringRun = project.last_scoring_run
  const run = project.last_criterion_scoring_run
  const runStatus = run?.status ?? null
  const runStartedAt = run?.started_at ?? null
  const [awaitingConfirmation, setAwaitingConfirmation] = useTriggerConfirmation(
    runStatus,
    runStartedAt,
    refetchProject,
  )

  const isTriggerPending = triggerMutation.isPending || awaitingConfirmation
  const isBusy = isTriggerPending || runStatus === 'running'
  const { action, rerun } = deriveStepAction('kriterien', project, {
    openCount: null,
    isTriggerPending,
  })
  const estimate = estimateQuery.data ?? null
  // Traegt der gewaehlte Weg Kosten? Cloud immer, Eye nur mit Einwilligung (dann laeuft die
  // Sehenswuerdigkeits-Erkennung mit), lokal nie. Dieselbe Bedingung entscheidet, ob die
  // Sehenswuerdigkeits-Erkennung ueberhaupt stattfindet - eine Wahrheit, zwei Verwendungen.
  const wayMayCost = way === 'cloud' || (way === 'eye' && consentEnabled)
  const landmarkParticipates = wayMayCost
  // Auslöse-Button bleibt deaktiviert, solange kein Weg gewaehlt ist und - bei einem Weg, der
  // Kosten tragen kann - solange dessen Schaetzung nicht geladen ist (Design-System: "kein
  // Bypass" - keine kostenpflichtige Aktion ohne sichtbare Schaetzung). Ein Fehler beim Laden
  // sperrt ebenfalls: er ist keine Aussage ueber 0 USD.
  // Cloud ohne Einwilligung ist ein Weg, den der Server mit 403 abweist: der Auslöser wird hier
  // gesperrt, statt den Fehlschlag zu provozieren. Eye und lokal sind davon unberuehrt.
  const cloudBlocked = way === 'cloud' && !consentEnabled
  const isTriggerDisabled =
    isBusy ||
    scoringRun === null ||
    way === null ||
    cloudBlocked ||
    (wayMayCost && estimate === null)

  // Der Sperrgrund steht als Text neben dem Ausloeser - ein ausgegrauter Knopf ohne Begruendung
  // laesst den Nutzer raten, was fehlt.
  const disabledReason = !isTriggerDisabled
    ? null
    : way === null
      ? 'Wähle zuerst einen Weg für diesen Durchlauf.'
      : cloudBlocked
        ? 'Cloud-Bilderkennung ist für dieses Projekt nicht aktiviert — erst die Einwilligung in den Projekteinstellungen erteilen.'
        : wayMayCost && estimate === null
          ? 'Die Kostenschätzung wird geladen…'
          : null

  function handleTrigger(): void {
    if (isTriggerDisabled || scoringRun === null || way === null) {
      return
    }
    setAwaitingConfirmation(true)
    triggerMutation.mutate(
      { scoringRunId: scoringRun.id, mode: way },
      {
        // Die Wahl gilt fuer EINEN Durchlauf. Sie stehen zu lassen luede dazu ein, den naechsten
        // Start als Wiederholung desselben Klicks zu lesen - bei einem kostenpflichtigen Weg ist
        // genau das die Falle, die die Checkbox vorher war.
        onSuccess: () => setWay(null),
        onError: () => setAwaitingConfirmation(false),
      },
    )
  }

  const triggerError = triggerMutation.isError
    ? triggerMutation.error instanceof ApiError
      ? triggerMutation.error
      : null
    : null
  const triggerErrorDetail = triggerMutation.isError
    ? (triggerError?.detail ?? 'Fehler beim Auslösen der Klassifizierung.')
    : null
  // 503 heisst "der Eye-Dienst antwortet nicht" - das ist die einzige Ausloese-Antwort, bei der
  // eine Wiederholung sinnvoll ist (der Dienst kann zurueckkommen). 403/409/404 sind Entscheidungen
  // des Servers: ein Wiederholungsknopf luede zu einem zweiten identischen Fehlschlag ein.
  const triggerRetry = triggerError?.status === 503 ? handleTrigger : undefined

  const providerLabel = estimate ? formatProviderLabel(estimate.provider) : ''
  // Die Serverreihenfolge (photo_count absteigend, Tie-Break canonical_key) wird uebernommen und
  // nur am Ende gekuerzt - die seltensten Eintraege fallen weg, nicht die haeufigsten.
  const shownFineLabels = (fineLabelsQuery.data ?? []).slice(0, MAX_FINE_LABELS_SHOWN)

  /* Die Schaetzung ersetzt den frueheren Bestaetigungsdialog (Kosten sichtbar vor dem Start) und
     steht am jeweiligen Auslöser: beim ersten Lauf und bei einer Wiederholung direkt über der
     Leiste, beim erneuten Lauf im Erneut-Block. Sie erscheint fuer JEDEN gewaehlten Weg - auch
     fuer die kostenfreien, dort mit der Zeile "Dieser Durchlauf ist kostenfrei." statt eines
     Betrags. Vor der Wahl steht sie gar nicht: es gibt dann keinen Durchlauf, dessen Kosten sie
     beschriebe. */
  const estimateBlock = way !== null && (
    <>
      {estimateQuery.isSuccess && estimate && (
        <ClassificationEstimate estimate={estimate} landmarkParticipates={landmarkParticipates} />
      )}
      {estimateQuery.isPending && (
        <p className="text-sm text-text">Kostenschätzung wird geladen…</p>
      )}
      {estimateQuery.isError && (
        <Alert onRetry={() => void estimateQuery.refetch()}>
          Kostenschätzung konnte nicht geladen werden.
        </Alert>
      )}
    </>
  )

  let statusText: string
  switch (action.kind) {
    case 'start':
      statusText = 'Noch nicht klassifiziert'
      break
    case 'running':
      statusText = 'Klassifizierung läuft…'
      break
    case 'retry':
      statusText = 'Klassifizierung fehlgeschlagen'
      break
    default:
      statusText = 'Klassifizierung abgeschlossen'
  }

  return (
    <section className="flex flex-col items-start gap-3">
      <h2 ref={headingRef} tabIndex={-1} className="text-lg">
        Klassifizierung
      </h2>
      <p className="text-sm text-text">
        Bewertet jedes verbleibende Foto nach mehreren Kriterien (Schärfe, Belichtung, Bildinhalt),
        leitet daraus eine Kategorie ab und bildet eine Rangfolge je Foto-Moment und Kategorie.
      </p>
      {rerun !== null && (
        <RerunBlock
          rerun={rerun}
          onRerun={handleTrigger}
          disabled={isTriggerDisabled}
          busy={isTriggerPending}
        >
          {estimateBlock}
        </RerunBlock>
      )}
      {/* Zustandsabhaengige Datenschutz-Aussage: die frueher absolute Formulierung "laeuft
          vollstaendig lokal auf diesem Server" war unwahr, sobald die Cloud-Bilderkennung
          freigegeben war. Sie gilt jetzt genau dann, wenn sie zutrifft.

          An DIESEM Text haengt die Einwilligung (Spec 0469, S7). Seit ADR 0106 geht mit dem Foto
          eine grobe Ortsangabe hinaus, und der Satz muss sie nennen - beide Stufen, und dass Fotos
          ohne Standortdaten nicht betroffen sind. Bliebe er bei "sendet Fotos", waere die
          Einwilligung fuer diese Datenklasse an einer Beschreibung erteilt, die sie nicht nennt.
          Der lokale Durchlauf behaelt seinen Satz unveraendert - dort geht nichts hinaus. */}
      <p className="text-sm text-text" data-testid="classification-scope-text">
        {way === null
          ? 'Noch kein Weg gewählt — was mit den Fotos geschieht, sagt dieser Abschnitt, sobald einer gewählt ist.'
          : way === 'cloud'
            ? `Dieser Durchlauf sendet Fotos an ${providerLabel || 'den Cloud-Anbieter'} — für Kategorie-Vorschläge und die Sehenswürdigkeits-Erkennung. Trägt ein Foto Standortdaten, geht dabei eine grobe Angabe zum Aufnahmeort mit: der Ortsname, sonst eine auf rund 11 km gerundete Koordinate. Fotos ohne Standortdaten sind davon nicht betroffen.`
            : way === 'eye'
              ? `Dieser Durchlauf wertet die Fotos auf diesem Server aus — kein Foto verlässt ihn.${
                  consentEnabled
                    ? ' Für die Sehenswürdigkeits-Erkennung geht mit dem Foto eine grobe Ortsangabe an den Cloud-Anbieter: der Ortsname, sonst eine auf rund 11 km gerundete Koordinate. Fotos ohne Standortdaten sind davon nicht betroffen.'
                    : ''
                } Eye sendet bei jedem Lauf eine Lizenzmeldung mit einer Zählkennung, aber ohne Bildinhalte an Desert Ant Labs; diese Meldung lässt sich nicht abschalten.`
              : 'Dieser Durchlauf läuft vollständig lokal auf diesem Server — kein Foto verlässt ihn.'}
      </p>

      {/* DIE LAUFWAHL. Ein echtes `fieldset` mit `legend`, weil die Gruppe eine Frage stellt
          ("Weg für diesen Durchlauf") und die Zeilen nur gemeinsam Sinn ergeben; Radios in einem
          `div` sind fuer Screenreader drei unabhaengige Schalter.

          Ganze Zeile anklickbar (`<label>`), Mindesthoehe 44 px (`min-h-11`) - die Trefferflaeche
          ist die Zeile, nicht der 16-px-Kreis. `disabled` am Fieldset sperrt waehrend eines Laufs
          alle Optionen in EINEM Attribut; einzelne `disabled`-Attribute an den Radios liessen
          sich vergessen.

          KEINE Vorbelegung: `way === null` ist der Anfangszustand jeder Sitzung. */}
      <fieldset
        className="flex w-full max-w-sm flex-col gap-2"
        disabled={isBusy}
        data-testid="classification-way-fieldset"
      >
        <legend className="text-sm font-medium text-text-h">Weg für diesen Durchlauf</legend>
        {(
          [
            {
              id: 'cloud',
              label: 'Cloud',
              meta: `Fotos an ${providerLabel || 'den Cloud-Anbieter'} · Abrechnung nach Verbrauch`,
              available: true,
            },
            {
              id: 'eye',
              label: 'Eye',
              meta: consentEnabled
                ? 'Bleibt auf diesem Server · kostenfrei — abgerechnet wird nur die Sehenswürdigkeits-Erkennung'
                : 'Bleibt auf diesem Server · kostenfrei',
              available: project.eye_available,
            },
            {
              id: 'local',
              label: 'Nur lokal',
              meta: 'Bleibt auf diesem Server · kostenfrei · ohne Kategorie-Vorschläge und Sehenswürdigkeits-Erkennung',
              available: true,
            },
          ] as const
        )
          .filter((option) => option.available)
          .map((option) => (
            <label
              key={option.id}
              className="flex min-h-11 w-full cursor-pointer flex-col justify-center gap-1 rounded-sm border border-border px-3 py-2 has-[:checked]:border-accent"
            >
              <span className="flex items-center gap-2">
                <input
                  type="radio"
                  name={wayGroupName}
                  value={option.id}
                  checked={way === option.id}
                  onChange={() => setWay(option.id)}
                  className="size-4 accent-accent"
                />
                <span className="text-sm font-semibold text-text-h">{option.label}</span>
              </span>
              {/* Die Nebenangabe ist KEIN zusaetzlicher Inhalt, sondern die Begruendung der Wahl:
                  sie sagt in einem Halbsatz, was der Weg kostet und wohin er geht. */}
              <span className="pl-6 text-xs text-text-muted">{option.meta}</span>
              {option.id === 'eye' && (
                <span className="pl-6">
                  <EyeAttribution />
                </span>
              )}
            </label>
          ))}
      </fieldset>

      {!consentEnabled && (
        <p className="text-sm text-text">
          Cloud-Bilderkennung ist für dieses Projekt nicht aktiviert.{' '}
          <Link
            className="text-accent-strong underline-offset-4 hover:underline"
            to={`/projects/${project.id}/settings`}
          >
            In den Projekteinstellungen aktivieren
          </Link>
          .
        </p>
      )}

      {/* Der Richtwert ist schon VOR dem ersten Lauf einstellbar - dieselbe Komponente wie in der
          Kuratierung, über dem Auslöser, damit der erste Vorschlag schon seine Größe hat. */}
      <p className="text-sm text-text">
        Der Richtwert ist ein Ziel, keine Obergrenze — reicht der Bildbestand nicht, wird der
        Vorschlag kleiner; damit jeder Foto-Moment vorkommt, kann er auch größer werden.
      </p>
      <SelectionTargetField project={project} />

      {triggerErrorDetail && <Alert onRetry={triggerRetry}>{triggerErrorDetail}</Alert>}
      {disabledReason !== null && (
        <p className="text-xs text-text-muted" data-testid="classification-disabled-reason">
          {disabledReason}
        </p>
      )}

      {/* GENAU EINER der beiden Zustandsblöcke, nie beide: läuft der Durchlauf, steht hier die
          Teilschrittliste, danach die Bilanz dieses einen Laufs. Beide gleichzeitig zu zeigen
          hieße, denselben Lauf zweimal zu beschreiben - und ließe die Sektion über ihre bisherige
          Höhe hinauswachsen (Akzeptanzkriterium "überfrachtet die Seite nicht"). */}
      {run !== null &&
        (runStatus === 'running' ? (
          <ClassificationProgress run={run} />
        ) : (
          <ClassificationBalance run={run} />
        ))}

      {/* Ohne Wiederholung: Die einzige Wiederholung ist die Hauptaktion der Leiste. */}
      {runStatus === 'failed' && <Alert>{run?.error_message}</Alert>}

      {/* Cloud-Anteil gescheitert: der Fehler wird sichtbar gemeldet UND das Ergebnis als nicht
          (vollstaendig) angereichert gekennzeichnet - beide Akzeptanzkriterien des Abschnitts
          "Fehlerverhalten" an einer Stelle. Der Lauf selbst ist dabei erfolgreich: der lokale
          Bewertungsanteil ist vollstaendig durchgelaufen. */}
      {run?.cloud_error_message != null && (
        <Alert>
          {run.cloud_error_message} Das Ergebnis ist ohne (vollständige) Cloud-Anreicherung
          entstanden.
        </Alert>
      )}

      {/* Feinlabel-Haeufigkeitsliste: das Kategorien-Set ist geschlossen, aber nicht fuer immer
          festgelegt - haeufige
          Feinlabels sind der Hinweis darauf, dass im Set eine Kategorie fehlt, und damit der
          Aenderungspfad. */}
      <div className="flex w-full max-w-sm flex-col gap-2">
        <h3 className="text-sm font-medium text-text-h">Häufigste Feinlabels</h3>
        {/* Der Kontexttext behauptet, Feinlabels seien haeufig aufgetreten - er erscheint deshalb
            nur, wenn tatsaechlich welche vorliegen. Ueber dem Leerzustand ("Keine zusaetzlichen
            Label ermittelt") waere er ein Widerspruch. */}
        {shownFineLabels.length > 0 && (
          <p className="text-xs text-text">
            Diese Feinlabels traten häufig auf — möglicherweise fehlt eine Kategorie im Set.
          </p>
        )}
        {fineLabelsQuery.isPending && (
          <p className="text-sm text-text">Feinlabels werden geladen…</p>
        )}
        {fineLabelsQuery.isError && (
          <Alert onRetry={() => void fineLabelsQuery.refetch()}>
            Feinlabels konnten nicht geladen werden.
          </Alert>
        )}
        {fineLabelsQuery.isSuccess &&
          (shownFineLabels.length === 0 ? (
            <p className="text-sm text-text">Keine zusätzlichen Label ermittelt.</p>
          ) : (
            <ul aria-label="Häufigste Feinlabels" className="flex flex-col gap-1">
              {shownFineLabels.map((label) => (
                <li
                  key={label.canonical_key}
                  className="flex items-baseline justify-between gap-3 text-sm"
                >
                  {/* Reiner React-Textknoten - freier LLM-Text, nie als HTML. */}
                  <span className="truncate text-text-h">{label.display_name}</span>
                  <span className="shrink-0 text-text">{label.photo_count} Mal</span>
                </li>
              ))}
            </ul>
          ))}
      </div>

      {rerun === null && estimateBlock}

      <StepActionBar
        action={action}
        status={
          <>
            <StatusDot status={action.kind === 'running' ? 'running' : runStatus} />
            {statusText}
          </>
        }
        onAction={handleTrigger}
        disabled={isTriggerDisabled}
      />
    </section>
  )
}
