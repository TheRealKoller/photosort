import { useRef, useState } from 'react'
import { Link, useParams } from 'react-router'

import { ApiError } from '../api/client'
import type { PhotoOut } from '../api/types'
import { CurationLightbox } from '../components/CurationLightbox'
import { SelectionPhotoTile } from '../components/SelectionPhotoTile'
import { Alert } from '../components/ui/alert'
import { Button } from '../components/ui/button'
import { Skeleton } from '../components/ui/skeleton'
import { useAlbumDecisionMutation, useAlbumSelectionQuery } from '../hooks/useAlbumSelection'
import { useCurationLightbox } from '../hooks/useCurationLightbox'
import { SELECTION_NOTHING_CONTESTED_TEXT, SELECTION_VIEW_LABELS } from '../utils/albumSelection'
import type { PhotoEventGroup } from '../utils/eventGrouping'
import { groupPhotosByDay } from '../utils/eventGrouping'
import { formatDayHeading } from '../utils/timeOfDay'
import { DRAFT_EMPTY_TEXT } from './AlbumDraftPage'

/** Die beiden Sichten - lokaler Zustand, keine zweite Route und kein Suchparameter. */
type SelectionView = keyof typeof SELECTION_VIEW_LABELS

const SKELETON_TILE_COUNT = 6

/**
 * Die gemeinsame Endauswahl: EIN Ort, ZWEI Sichten, EINE Abfrage.
 *
 * Die Arbeitssicht („Unterschiede") zeigt ausschließlich, worüber die beiden uneins sind; die
 * Ergebnissicht („Endauswahl") die Menge, die als Album gilt, plus die ausdrücklich
 * herausgenommenen Bilder als Anzeigezustand. Beide filtern dieselbe geladene Antwort — DER
 * UMSCHALTER LÄDT NICHTS NACH (ADR 0099 Punkt 6). Ein zweiter Abruf ordnete die Ergebnissicht bei
 * jedem Wechsel neu, und eine Entscheidung risse die gerade gedrückte Kachel unter dem Finger
 * weg.
 *
 * DIE ZUGEHÖRIGKEIT KOMMT VOM SERVER. `in_final_selection` und `contested` sind Serverfelder;
 * `utils/albumDraft.ts::isInAlbum` wird hier ausdrücklich NICHT benutzt — seine Aussage
 * (`status !== 'rejected'`) gilt nur innerhalb der Antwortmenge des Entwurfszweigs, und die
 * Endauswahl enthält auch Fotos, die in keinem der beiden Entwürfe stehen.
 *
 * NICHTS SPERRT DEN ZUGANG: Es gibt keinen Zustand „fertig" je Nutzer, keinen Bestätigungsschritt
 * und keinen Dialog. Diese Seite gibt an kein Bedienelement ein `disabled`; allein die gedrückte
 * Entscheidungs-Schaltfläche trägt `busy`, womit sich das Button-Primitiv gegen einen Doppeldruck
 * auf DASSELBE Bild selbst sperrt. Der Umschalter bleibt jederzeit bedienbar.
 */
export function AlbumSelectionPage() {
  const { projectId } = useParams()
  const id = Number(projectId)

  const query = useAlbumSelectionQuery(id)
  const decisionMutation = useAlbumDecisionMutation(id)

  // Vorbelegung ist die ARBEITSSICHT - dort fängt die Arbeit an.
  const [view, setView] = useState<SelectionView>('contested')

  // Die gerade laufenden Entscheidungen: eine ABBILDUNG Foto-Id -> geschriebener Wert, keine
  // einzelne Id. Verschiedene Fotos entscheiden unabhängig voneinander, und der geschriebene Wert
  // sagt, WELCHE der beiden Schaltflächen einer Kachel den Spinner trägt.
  const [decidingByPhotoId, setDecidingByPhotoId] = useState<Map<number, boolean>>(new Map())

  const selection = query.data
  const participants = selection?.participants ?? []
  const items = selection?.items ?? []

  // Die Grossansicht schlaegt in `items` nach, NICHT in der gefilterten Sicht: Ein Foto, das nur
  // die andere Sicht zeigt, oeffnet sich trotzdem; ohne Ausloeser geht der Fokus danach auf `h1`.
  const headingRef = useRef<HTMLHeadingElement>(null)
  const lightbox = useCurationLightbox({ items: selection?.items, headingRef })

  // Die beiden Filter. Die Ergebnissicht führt die ausdrücklich Herausgenommenen mit: Ein
  // herausgenommenes Bild verschwände sonst aus beiden Sichten, und die Entscheidung ließe sich
  // nicht mehr ändern (ADR 0099 Punkt 5).
  const visible = items.filter((photo) =>
    view === 'contested'
      ? photo.contested
      : photo.in_final_selection || photo.final_selection_decision === false,
  )
  const days = groupPhotosByDay(visible)

  function handleDecide(photo: PhotoOut, included: boolean): void {
    setDecidingByPhotoId((current) => new Map(current).set(photo.id, included))
    decisionMutation.mutate(
      { photoId: photo.id, included },
      {
        // `onSettled` statt `onError`: In der Ergebnissicht bleibt das Bild in jedem Fall an
        // seiner Stelle, es gibt also kein „verschwindet", an dem sich das Ende der Mutation
        // ablesen ließe.
        onSettled: () => {
          setDecidingByPhotoId((current) => {
            const next = new Map(current)
            next.delete(photo.id)
            return next
          })
        },
      },
    )
  }

  function renderEventGroup(group: PhotoEventGroup) {
    return (
      <section key={group.eventId} className="flex flex-col gap-2">
        <h3 className="text-base">{group.heading}</h3>
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
          {group.photos.map((photo) => (
            <SelectionPhotoTile
              key={photo.id}
              photo={photo}
              participants={participants}
              decidingIncluded={decidingByPhotoId.get(photo.id) ?? null}
              onDecide={(included) => handleDecide(photo, included)}
              onOpenLarge={lightbox.open}
              largeTriggerRef={lightbox.triggerRef(photo.id)}
            />
          ))}
        </ul>
      </section>
    )
  }

  function viewButton(target: SelectionView) {
    const active = view === target
    return (
      <Button
        type="button"
        variant="ghost"
        size="sm"
        // Der aktive trägt den Aktivstil der Projektnavigation, der inaktive bleibt `ghost`.
        // `aria-pressed` statt einer eigenen Umschalter-Rolle - dieselbe Konstruktion wie beim
        // Zweizustand der Entwurfskachel.
        className={active ? 'border border-border-control bg-overlay text-text-h' : undefined}
        aria-pressed={active}
        onClick={() => setView(target)}
      >
        {SELECTION_VIEW_LABELS[target]}
      </Button>
    )
  }

  // `=== false` geprüft und nicht auf Falsyness: während des Ladens ist das Feld `undefined`, und
  // das ist keine Aussage über den Auswahlvorschlag.
  const noProposal = selection?.has_proposal === false
  // Die beiden Leerzustände sind GETRENNT und nie beide da: Sie verlangen verschiedene
  // Handlungen - einmal einen Lauf starten, einmal nichts tun.
  const nothingContested =
    view === 'contested' && selection?.has_proposal === true && days.length === 0

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-3">
        <h1 ref={headingRef} tabIndex={-1} className="text-xl sm:text-2xl">
          Endauswahl
        </h1>
        {/* Der Umschalter steht ÜBER der Liste und bleibt in jedem Zustand bedienbar - auch
            während des Ladens und im Fehlerfall. */}
        <div className="flex flex-wrap gap-2">
          {viewButton('contested')}
          {viewButton('all')}
        </div>
      </header>

      {query.isLoading && (
        <ul
          role="status"
          aria-label="Fotos werden geladen…"
          className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4"
        >
          {Array.from({ length: SKELETON_TILE_COUNT }, (_, index) => (
            <li key={index} aria-hidden="true">
              <Skeleton className="aspect-square w-full rounded-md" />
            </li>
          ))}
        </ul>
      )}

      {query.isError && (
        <Alert onRetry={() => void query.refetch()}>
          {query.error instanceof ApiError
            ? query.error.detail
            : 'Fehler beim Laden der Endauswahl.'}
        </Alert>
      )}

      {/* Leerzustand A: ohne Auswahlvorschlag gibt es nichts gegenüberzustellen. Der Wortlaut ist
          DIE KONSTANTE der Entwurfsseite, nicht ein zweiter Satz für denselben Sachverhalt. */}
      {noProposal && (
        <div className="flex flex-col items-start gap-3">
          <p className="text-sm text-text">{DRAFT_EMPTY_TEXT}</p>
          <Button asChild variant="secondary" size="sm">
            <Link to={`/projects/${id}/pipeline/kriterien`}>Zur Kriterien-Bewertung</Link>
          </Button>
        </div>
      )}

      {/* Leerzustand B: der Vorschlag steht, die Arbeitssicht hat nichts mehr abzuarbeiten. */}
      {nothingContested && (
        <div className="flex flex-col items-start gap-3">
          <p className="text-sm text-text">{SELECTION_NOTHING_CONTESTED_TEXT}</p>
          <Button type="button" variant="secondary" size="sm" onClick={() => setView('all')}>
            {`Zur ${SELECTION_VIEW_LABELS.all}`}
          </Button>
        </div>
      )}

      {days.map((day) => (
        <section key={day.dayKey} className="flex flex-col gap-4">
          <h2 className="text-lg">{formatDayHeading(day.dayKey)}</h2>
          {day.events.map((group) => renderEventGroup(group))}
        </section>
      ))}

      {lightbox.photo !== undefined && (
        <CurationLightbox key={lightbox.photo.id} photo={lightbox.photo} onClose={lightbox.close} />
      )}
    </div>
  )
}
