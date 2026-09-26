import { useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router'

import { ApiError } from '../api/client'
import type { PhotoOut, RatingStatus } from '../api/types'
import { decodeUsername } from '../auth/jwt'
import { getToken } from '../auth/token'
import { CurationLightbox } from '../components/CurationLightbox'
import { CurationPhotoTile } from '../components/CurationPhotoTile'
import { DraftAlternativesDialog } from '../components/DraftAlternativesDialog'
import { Alert } from '../components/ui/alert'
import { Button } from '../components/ui/button'
import { Skeleton } from '../components/ui/skeleton'
import { useCurationLightbox } from '../hooks/useCurationLightbox'
import { useMotifsQuery } from '../hooks/useMotifs'
import {
  useDraftDecisionMutation,
  useDraftExchangeMutation,
  useDraftQuery,
} from '../hooks/usePhotos'
import { useProjectQuery } from '../hooks/useProjects'
import { draftMotifText, draftSizeText, formatDraftPhotoCount } from '../utils/albumDraft'
import type { PhotoEventGroup } from '../utils/eventGrouping'
import { groupPhotosByDay } from '../utils/eventGrouping'
import { ownRatingStatus } from '../utils/ownRating'
import { formatDayHeading } from '../utils/timeOfDay'

/**
 * Der Leerzustand des Entwurfs. Er benennt den fehlenden Schritt und verlinkt ihn, statt eine
 * leere Liste zu zeigen: Ohne erfolgreichen Kriterien-Lauf gibt es keinen Vorschlag - und auch
 * bereits aufgenommene Bilder erscheinen dann nicht, weil es kein Event gibt, in das sie
 * einzuordnen wären.
 */
export const DRAFT_EMPTY_TEXT = 'Noch kein Auswahlvorschlag — führe die Kriterien-Bewertung aus.'

/**
 * Der Leerzustand OHNE Cloud-Freigabe - mit Vorrang vor `DRAFT_EMPTY_TEXT`: ohne Freigabe entsteht
 * gar kein Entwurf, und „führe die Kriterien-Bewertung aus" wäre ein Rat, der nicht hilft.
 *
 * Er benennt die fehlende Freigabe und den Ort, an dem sie erteilt wird - und WIEDERHOLT DEN
 * ZUSTIMMUNGSTEXT NICHT. Was an die Cloud geht, steht an genau einer Stelle, im Info-Popover neben
 * dem Schalter der Projekteinstellungen; zwei Fassungen desselben Textes driften, und eine
 * Einwilligung, die an zwei Orten verschieden beschrieben ist, ist keine.
 */
export const DRAFT_CLOUD_CONSENT_TEXT =
  'Ohne Cloud-Freigabe entsteht kein Album-Entwurf. Die Freigabe erteilst du in den ' +
  'Projekteinstellungen.'

/** Der Text einer Eventgruppe, in der gerade kein Bild des Entwurfs steht. */
export const DRAFT_EMPTY_EVENT_TEXT = 'Kein Bild im Entwurf'

const SKELETON_TILE_COUNT = 6

/**
 * Toggelt den Klapp-Zustand eines einzelnen Tages - liefert ein neues `Set` statt das übergebene
 * zu mutieren, andere `dayKey`s bleiben unverändert.
 */
export function toggleDayCollapse(collapsedDayKeys: Set<string>, dayKey: string): Set<string> {
  const next = new Set(collapsedDayKeys)
  if (next.has(dayKey)) {
    next.delete(dayKey)
  } else {
    next.add(dayKey)
  }
  return next
}

/** Die Bezeichnung einer einmal gesehenen Eventgruppe - Grundlage des Leerzustands je Event. */
interface KnownEventGroup {
  dayKey: string
  eventId: number
  heading: string
}

export function AlbumDraftPage() {
  const { projectId } = useParams()
  const id = Number(projectId)
  // Das Motivset kommt vom Server und wird langlebig gecacht - es speist die schreibgeschuetzte
  // Motivliste im Info-Popover jeder Kachel. EIN Request fuer alle Kacheln.
  const motifsQuery = useMotifsQuery()
  // Der EIGENE Bewertungszustand wird ausschliesslich hierueber abgeleitet (`ownRatingStatus` mit
  // dem `username`-Claim des JWT, wie in Raster- und Detailansicht) - nie ueber `ratings[]`
  // insgesamt, sonst stellte die Ansicht die Entscheidung des jeweils anderen als eigene dar
  // (Auflage S6).
  const token = getToken()
  const username = token ? decodeUsername(token) : null

  const query = useDraftQuery(id)
  // Die Cloud-Freigabe ist eine PROJEKTeinstellung und steht nicht am Foto; das Projekt traegt
  // ausserdem den wirksamen Richtwert des Kopfbereichs.
  const projectQuery = useProjectQuery(id)
  const decisionMutation = useDraftDecisionMutation(id, username)
  const exchangeMutation = useDraftExchangeMutation(id, username)
  const items = useMemo(() => query.data?.items ?? [], [query.data])

  // Die Grossansicht: offen ist, was im Verlaufseintrag steht - nachgeschlagen in der GELADENEN
  // Liste. Die Ueberschrift ist Fokusziel, wenn der Ausloeser des Fotos nicht mehr im Raster steht.
  const headingRef = useRef<HTMLHeadingElement>(null)
  const lightbox = useCurationLightbox({ items: query.data?.items, headingRef })

  // Das Bild, dessen Alternativen gerade offen stehen - EIN Dialog fuer die ganze Seite, nicht
  // einer je Kachel: sonst liefe beim Laden eine Abfrage je Kachel (Durchsatz-Zusage der Story).
  const [alternativesPhotoId, setAlternativesPhotoId] = useState<number | null>(null)
  // Die Kachel, die den Fokus bekommt: nach einem Austausch die NEU an dieser Stelle stehende.
  // Der Dialog gaebe den Fokus sonst an die Schaltflaeche des gerade gestrichenen Bildes zurueck.
  const [focusPhotoId, setFocusPhotoId] = useState<number | null>(null)

  // Die Fotos mit gerade LAUFENDER Entscheidung - eine MENGE, nicht eine einzelne Id: verschiedene
  // Fotos entscheiden unabhaengig voneinander, ein ZWEITER Vorgang fuer DASSELBE Foto wird
  // verhindert (`Rating` traegt `UniqueConstraint(photo_id, user_id)`, zwei nebenlaeufige Anfragen
  // liefen in einen IntegrityError).
  //
  // ZWEI Ablagen fuer dieselbe Menge, mit verschiedenen Aufgaben: der Ref ist die SYNCHRONE
  // Wahrheit fuer die Sperre je Foto, der State loest das Neurendern der betroffenen Kacheln aus.
  // Geprueft wird gegen den REF: `disabled` und der State-Schnappschuss im Render-Closure
  // entstehen beide erst durch ein State-Update, das React fruehestens beim naechsten Render
  // verarbeitet - zwei Klicks im selben Durchlauf saehen beide denselben, leeren Schnappschuss.
  const decidingPhotoIdsRef = useRef<Set<number>>(new Set())
  const [decidingPhotoIds, setDecidingPhotoIds] = useState<Set<number>>(new Set())

  // Klapp-Zustand der Tages-Abschnitte: leeres Set = alles aufgeklappt (Default) - kein
  // localStorage/sessionStorage/Query-Param, keine Persistierung ueber einen Reload hinaus.
  const [collapsedDayKeys, setCollapsedDayKeys] = useState<Set<string>>(new Set())

  // Einmal gesehene Eventgruppen bleiben fuer die Dauer des Seitenbesuchs bekannt: sonst
  // verschwaende ein leergeraeumtes Event kommentarlos aus der Gliederung, statt mit seiner
  // Ueberschrift und einem eigenen Leerzustand stehenzubleiben.
  const knownEventGroupsRef = useRef<Map<number, KnownEventGroup>>(new Map())

  const days = groupPhotosByDay(items)
  for (const day of days) {
    for (const group of day.events) {
      knownEventGroupsRef.current.set(group.eventId, {
        dayKey: day.dayKey,
        eventId: group.eventId,
        heading: group.heading,
      })
    }
  }
  const presentEventIds = new Set(days.flatMap((day) => day.events.map((group) => group.eventId)))
  for (const known of knownEventGroupsRef.current.values()) {
    if (presentEventIds.has(known.eventId)) {
      continue
    }
    let day = days.find((candidate) => candidate.dayKey === known.dayKey)
    if (day === undefined) {
      day = { dayKey: known.dayKey, events: [] }
      days.push(day)
    }
    day.events.push({ eventId: known.eventId, heading: known.heading, photos: [] })
  }
  // dayKey-Format YYYY-MM-DD sortiert lexikographisch = chronologisch. Nachtraeglich angehaengte
  // Leergruppen stuenden sonst hinter den gefuellten Tagen.
  days.sort((left, right) => left.dayKey.localeCompare(right.dayKey))

  function handleDecide(photo: PhotoOut, status: RatingStatus): void {
    if (decidingPhotoIdsRef.current.has(photo.id)) {
      return
    }
    decidingPhotoIdsRef.current = new Set(decidingPhotoIdsRef.current).add(photo.id)
    setDecidingPhotoIds(new Set(decidingPhotoIdsRef.current))
    decisionMutation.mutate(
      { photoId: photo.id, status },
      {
        // `onSettled` statt `onError`: das Foto bleibt in jedem Fall an seiner Stelle, es gibt
        // also kein "verschwindet", an dem sich das Ende der Mutation ablesen liesse.
        onSettled: () => {
          const next = new Set(decidingPhotoIdsRef.current)
          next.delete(photo.id)
          decidingPhotoIdsRef.current = next
          setDecidingPhotoIds(next)
        },
      },
    )
  }

  function handleExchange(replaced: PhotoOut, chosen: PhotoOut): void {
    exchangeMutation.mutate(
      { replaced, chosen },
      {
        onSuccess: () => {
          // Erst schliessen, dann den Fokus umlenken: Die Aufraeumfunktion des Dialogs gibt ihn
          // an das ausloesende Element zurueck, und React fuehrt ALLE Aufraeumfunktionen vor
          // allen neuen Effekten aus - die Fokusnahme der Kachel gewinnt deshalb.
          setAlternativesPhotoId(null)
          setFocusPhotoId(chosen.id)
        },
      },
    )
  }

  // Auf `=== true` gepruueft statt auf Falsyness: waehrend des Ladens ist das Feld `undefined`,
  // und das ist keine Aussage ueber die Freigabe.
  const cloudConsentGiven = projectQuery.data?.cloud_vision_detection_enabled === true
  // Die wirksame Zahl kommt FERTIG vom Server - das Frontend leitet sie nie selbst ab.
  const effectiveSelectionTarget = projectQuery.data?.effective_selection_target ?? null

  const motifSetError = motifsQuery.isError
    ? motifsQuery.error instanceof ApiError
      ? motifsQuery.error.detail
      : 'Fehler beim Laden der Motive.'
    : undefined

  function renderTile(photo: PhotoOut) {
    return (
      <CurationPhotoTile
        key={photo.id}
        photo={photo}
        motifSet={motifsQuery.data}
        motifSetLoading={motifsQuery.isLoading}
        motifSetError={motifSetError}
        onMotifSetRetry={() => {
          void motifsQuery.refetch()
        }}
        ownStatus={ownRatingStatus(photo.ratings, username)}
        deciding={decidingPhotoIds.has(photo.id)}
        onDecide={(status) => handleDecide(photo, status)}
        onOpenAlternatives={() => setAlternativesPhotoId(photo.id)}
        focusDecision={focusPhotoId === photo.id}
        onOpenLarge={lightbox.open}
        largeTriggerRef={lightbox.triggerRef(photo.id)}
      />
    )
  }

  function renderEventGroup(group: PhotoEventGroup) {
    // Die Motivmischung entsteht aus den KACHELN dieser Gruppe, nie aus einer Serveraggregation:
    // eine solche waere nach jeder Entscheidung veraltet (die Entwurfsliste laedt bewusst nicht
    // neu, ADR 0098 Punkt 6) und naennte ein Motiv, das kein Bild der Gruppe mehr traegt.
    const motifText = draftMotifText(group.photos, username, motifsQuery.data?.items ?? [])
    return (
      <section key={group.eventId} className="flex flex-col gap-2">
        {/* Die Zahl steht NEBEN der Ueberschrift in einem eigenen Element, nicht in ihr: der von
            `formatEventHeading()` gelieferte Text bleibt unveraendert. */}
        <div className="flex flex-wrap items-baseline gap-2">
          <h3 className="text-base">{group.heading}</h3>
          <span className="text-sm text-text">{`(${formatDraftPhotoCount(group.photos.length)})`}</span>
        </div>
        {/* Reiner Fliesstext, umbrechend - keine Werte, keine Balken, keine Reihung nach Staerke.
            In einer leergeraeumten Gruppe entfaellt die Zeile und es bleibt beim Leerzustand. */}
        {motifText !== null && <p className="text-sm text-text">{motifText}</p>}
        {group.photos.length === 0 && <p className="text-sm text-text">{DRAFT_EMPTY_EVENT_TEXT}</p>}
        {group.photos.length > 0 && (
          <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
            {group.photos.map((photo) => renderTile(photo))}
          </ul>
        )}
      </section>
    )
  }

  const dayKeys = days.map((day) => day.dayKey)
  // Das Bezugsbild kommt aus der GELADENEN Liste, nicht aus einer Kopie im Zustand: Bewertet es
  // jemand zwischendurch, zeigte eine Kopie den Stand von vorhin.
  const alternativesPhoto = items.find((item) => item.id === alternativesPhotoId)

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 ref={headingRef} tabIndex={-1} className="text-xl sm:text-2xl">
          Album-Entwurf
        </h1>
        {/* Richtwert und Ist-Anzahl NEBENEINANDER, in der Farbe des Fliesstextes. Eine Abweichung
            nach oben wie nach unten ist ein neutraler Hinweis - kein Warnton, kein Fehlerzustand,
            keine Schaltflaeche, die sie beseitigt. Der Text erscheint erst, wenn beide Zahlen
            vorliegen; „0 von etwa 12" waehrend des Ladens waere eine Aussage ueber einen Stand,
            den es noch nicht gibt. */}
        {query.isSuccess && effectiveSelectionTarget !== null && (
          <p className="text-sm text-text">
            {draftSizeText(items.length, effectiveSelectionTarget)}
          </p>
        )}
      </header>

      {(query.isLoading || projectQuery.isLoading) && (
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
          {query.error instanceof ApiError ? query.error.detail : 'Fehler beim Laden der Fotos.'}
        </Alert>
      )}

      {/* Kein `Alert`, kein `role="alert"`, keine Fehlerfarbe, kein Symbol: eine fehlende
          Einwilligung ist kein Fehler. Die Schaltflaeche ist bewusst SEKUNDAER - sie navigiert,
          sie erteilt nichts. */}
      {query.isSuccess && projectQuery.isSuccess && !cloudConsentGiven && (
        <div className="flex flex-col items-start gap-3">
          <p className="text-sm text-text">{DRAFT_CLOUD_CONSENT_TEXT}</p>
          <Button asChild variant="secondary" size="sm">
            <Link to={`/projects/${id}/settings`}>Zu den Projekteinstellungen</Link>
          </Button>
        </div>
      )}

      {query.isSuccess && projectQuery.isSuccess && cloudConsentGiven && dayKeys.length === 0 && (
        <div className="flex flex-col items-start gap-3">
          <p className="text-sm text-text">{DRAFT_EMPTY_TEXT}</p>
          <Button asChild variant="secondary" size="sm">
            <Link to={`/projects/${id}/pipeline/kriterien`}>Zur Kriterien-Bewertung</Link>
          </Button>
        </div>
      )}

      {dayKeys.length > 0 && (
        <div className="flex flex-wrap items-center gap-3">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => setCollapsedDayKeys(new Set())}
          >
            Alle Tage aufklappen
          </Button>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => setCollapsedDayKeys(new Set(dayKeys))}
          >
            Alle Tage zuklappen
          </Button>
        </div>
      )}

      {days.map((day) => {
        // dayKey (Format YYYY-MM-DD) ist bereits ID-sicher.
        const panelId = `day-panel-${day.dayKey}`
        const isCollapsed = collapsedDayKeys.has(day.dayKey)
        const photoCount = day.events.reduce((sum, group) => sum + group.photos.length, 0)
        return (
          <section key={day.dayKey} className="flex flex-col gap-4">
            <h2 className="text-lg">
              {/* Gesamte Kopfzeile als Trigger - `w-full`+`text-left` macht die ganze Zeile
                  klickbar, `min-h-11` sichert ein Touch-Ziel von mindestens 44px.
                  `whitespace-normal` gegen das `whitespace-nowrap` des Primitivs: die
                  Tagesueberschrift muss bei 360px umbrechen duerfen, sonst entsteht waagerechtes
                  Scrollen. */}
              <Button
                variant="ghost"
                aria-expanded={!isCollapsed}
                aria-controls={panelId}
                onClick={() => setCollapsedDayKeys((prev) => toggleDayCollapse(prev, day.dayKey))}
                className="h-auto min-h-11 w-full justify-start whitespace-normal px-2 py-1 text-left text-lg font-normal"
              >
                <span aria-hidden="true">{isCollapsed ? '▶' : '▼'}</span>
                <span>{formatDayHeading(day.dayKey)}</span>
                {/* Explizites `{' '}` (statt sich auf das visuelle `gap-2` zu verlassen): der
                    zugaengliche Name entsteht aus dem Text der Kindknoten, CSS-`gap` erzeugt dabei
                    keinen Text-/Namensraum. */}
                {isCollapsed && (
                  <>
                    {' '}
                    <span className="font-normal text-text">
                      {`(${formatDraftPhotoCount(photoCount)})`}
                    </span>
                  </>
                )}
              </Button>
            </h2>
            {!isCollapsed && (
              // Kompletter Event-Teilbaum wird bei Zugeklapptheit per conditional JSX gar nicht
              // gerendert statt nur CSS-versteckt - spart bei grossen Projekten Render-Arbeit.
              <div id={panelId} className="flex flex-col gap-4">
                {day.events.map((group) => renderEventGroup(group))}
              </div>
            )}
          </section>
        )
      })}

      {/* EIN Dialog fuer die ganze Seite, erst ab dem Oeffnen im Baum: So laeuft die Abfrage der
          Alternativen genau einmal je geoeffnetem Bild, nie einmal je Kachel. */}
      {alternativesPhoto !== undefined && (
        <DraftAlternativesDialog
          projectId={id}
          photo={alternativesPhoto}
          username={username}
          open
          onClose={() => setAlternativesPhotoId(null)}
          onChoose={(alternative) => handleExchange(alternativesPhoto, alternative)}
          exchanging={exchangeMutation.isPending}
        />
      )}

      {lightbox.photo !== undefined && (
        <CurationLightbox key={lightbox.photo.id} photo={lightbox.photo} onClose={lightbox.close} />
      )}
    </div>
  )
}
