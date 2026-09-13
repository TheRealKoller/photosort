import { useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router'

import { ApiError } from '../api/client'
import type { PhotoOut } from '../api/types'
import { decodeUsername } from '../auth/jwt'
import { getToken } from '../auth/token'
import { CurationCandidates } from '../components/CurationCandidates'
import { CurationPhotoTile } from '../components/CurationPhotoTile'
import { Alert } from '../components/ui/alert'
import { Button } from '../components/ui/button'
import { Skeleton } from '../components/ui/skeleton'
import { useMotifsQuery } from '../hooks/useMotifs'
import { useDraftQuery, useSetRatingMutation } from '../hooks/usePhotos'
import { useProjectQuery } from '../hooks/useProjects'
import { ownRatingStatus } from '../utils/ownRating'
import { curatedRanking } from '../utils/rankings'
import { formatDayHeading, formatEventHeading } from '../utils/timeOfDay'

interface EventMeta {
  dayKey: string
  heading: string
  // Die chronologische Reihenfolge innerhalb eines Tages kommt aus der Nummer des Events
  // (lueckenlos ab 1, ueberschneidungsfrei) - kein zweiter Sortierschluessel und kein
  // Zeitstempelvergleich.
  position: number
}

/**
 * ZWEI Gruppierungsebenen: Tag und Event. Die Kategorie-Ebene ist mit Spec 0427 entfallen - ein
 * Foto steht je Lauf in genau einer Zeile und damit in genau einer Gruppe, und der Kachel-Key ist
 * wieder `photo.id`.
 */
interface GroupedPhotos {
  [dayKey: string]: {
    [eventKey: string]: PhotoOut[]
  }
}

/**
 * Der Schluessel eines Events in den Gruppierungsobjekten. Die `event_id` ist eine ZAHL, ein
 * Objektschluessel ist immer ein String - die Umwandlung passiert an genau dieser einen Stelle,
 * statt an jeder Lesestelle erneut.
 */
function eventKeyOf(eventId: number): string {
  return String(eventId)
}

/**
 * Erster Durchlauf sammelt die Event-Meta-Info (Tag, Ueberschrift, Nummer) je `event_id`, zweiter
 * Durchlauf sortiert die Fotos in die zweistufige {Tag: {Event: Fotos}}-Struktur ein.
 *
 * Die Meta-Info entsteht aus `photo.event` - EINER Zeile, nicht aus einer Aggregation ueber die
 * sichtbaren Fotos. Der Server sichert zu, dass sie auf jedem Foto desselben Events feldgleich
 * ist; deshalb genuegt ein beliebiges.
 *
 * Ein Foto ohne `curation_position` gehoert nicht zur angeforderten Auswahl und wird
 * uebersprungen. Welche Fotos das sind, entscheidet ausschliesslich der Server; das Frontend
 * bildet weder die Auswahl noch eine Schwelle nach.
 */
function groupByEvent(items: PhotoOut[]): {
  groups: GroupedPhotos
  eventMeta: Map<string, EventMeta>
} {
  const eventMeta = new Map<string, EventMeta>()
  for (const photo of items) {
    if (!photo.event) {
      continue
    }
    const { dayKey, heading } = formatEventHeading(photo.event)
    eventMeta.set(eventKeyOf(photo.event.id), {
      dayKey,
      heading,
      position: photo.event.position,
    })
  }

  const groups: GroupedPhotos = {}
  for (const photo of items) {
    const ranking = curatedRanking(photo)
    if (ranking === null) {
      continue
    }
    const eventKey = eventKeyOf(ranking.event_id)
    const meta = eventMeta.get(eventKey)
    if (meta === undefined) {
      // Erreichbar nur, wenn ein Foto eine Rangzeile ohne zugehoeriges `event` traegt - der
      // Server liefert das nicht. Defensive Absicherung statt einer Non-Null-Assertion.
      continue
    }
    groups[meta.dayKey] ??= {}
    groups[meta.dayKey][eventKey] ??= []
    groups[meta.dayKey][eventKey].push(photo)
  }
  return { groups, eventMeta }
}

/**
 * Fotoanzahl eines Tages fuer die Kurzinfo im zugeklappten Zustand - reine Ableitung aus bereits
 * geladenen Daten, kein neuer State/Request.
 *
 * Zaehlt EINDEUTIGE Foto-Ids und nicht schlicht die Laenge der Listen: ein Foto steht je Lauf
 * zwar in genau einer Gruppe, aber die Zusage der Beschriftung ("N Fotos") haengt nicht daran -
 * sie soll auch dann stimmen, wenn die Gruppierung sich einmal aendert.
 */
export function countPhotosInDay(eventsForDay: { [eventKey: string]: PhotoOut[] }): number {
  const photoIds = new Set<number>()
  for (const photos of Object.values(eventsForDay)) {
    for (const photo of photos) {
      photoIds.add(photo.id)
    }
  }
  return photoIds.size
}

/**
 * Kandidatenzahl eines Events: schlicht die `partition_size` - alle Fotos einer Partition tragen
 * denselben Wert, weil er lauf-global je `event_id` berechnet wird und nicht nutzerspezifisch
 * gefiltert ist.
 *
 * `0` fuer ein leergelaufenes Event (nur noch ueber `knownGroupKeysRef` bekannt). Die Ueberschrift
 * bekommt dann GAR KEINE Zahl - "0 Kandidaten" waere eine Aussage ueber einen Bestand, den die
 * Antwort gar nicht mehr beschreibt.
 */
export function candidateCountOfEvent(photos: PhotoOut[]): number {
  return photos[0]?.ranking?.partition_size ?? 0
}

/** "1 Kandidat" / "N Kandidaten". */
export function formatCandidateCount(count: number): string {
  return `${count} ${count === 1 ? 'Kandidat' : 'Kandidaten'}`
}

/**
 * Toggelt den Klapp-Zustand eines einzelnen Tages - liefert ein neues `Set` statt das uebergebene
 * zu mutieren, andere `dayKey`s bleiben unveraendert.
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

/**
 * Leertext einer erschoepften Gruppe. Frueher war er an die Tageszeit gebunden ("Keine Fotos in
 * dieser Tageszeit") - die Ueberschrift traegt seit Spec 0425 keine Tageszeit mehr, und der Text
 * traefe schlicht nicht mehr zu.
 */
const EMPTY_EVENT_TEXT = 'Keine Fotos in dieser Gruppe'

/**
 * Der Leerzustand der ganzen Ansicht. Er traegt ZWEI Faelle, die das Frontend nicht
 * unterscheiden kann - beide liefern eine leere Liste:
 *
 * 1. Es gab noch nie einen erfolgreichen Kriterien-Lauf.
 * 2. Der letzte erfolgreiche Lauf stammt von VOR der Umstellung auf Events; seine Rangzeilen sind
 *    mit der Migration entfallen. Ein erfolgreicher Lauf OHNE Rangzeilen ist neu.
 *
 * Beide Male hilft dieselbe Handlung weiter, deshalb ein Text statt zweier: neu berechnen.
 */
export const CURATION_EMPTY_TEXT =
  'Noch keine Kuratierung verfügbar — führe eine Kriterien-Bewertung aus. ' +
  'Ein Lauf von vor der Umstellung auf Events muss einmal neu berechnet werden.'

/**
 * Der Leerzustand OHNE Cloud-Freigabe - mit Vorrang vor `CURATION_EMPTY_TEXT`: ohne Freigabe
 * entsteht gar kein Album-Entwurf, und „führe eine Kriterien-Bewertung aus" wäre ein Rat, der
 * nicht hilft.
 *
 * Er benennt die fehlende Freigabe und den Ort, an dem sie erteilt wird - und WIEDERHOLT DEN
 * ZUSTIMMUNGSTEXT NICHT. Was an die Cloud geht, steht weiterhin an genau einer Stelle, im
 * Info-Popover neben dem Schalter der Projekteinstellungen; zwei Fassungen desselben Textes
 * driften, und eine Einwilligung, die an zwei Orten verschieden beschrieben ist, ist keine.
 */
export const CURATION_CLOUD_CONSENT_TEXT =
  'Ohne Cloud-Freigabe entsteht kein Album-Entwurf. Die Freigabe erteilst du in den ' +
  'Projekteinstellungen.'

/**
 * Der Hinweis, wenn der Vorschlag kleiner ausfällt als der wirksame Richtwert. Beide Zahlen
 * ausgeschrieben: „weniger als angestrebt" allein beantwortet die Frage nicht, die ein Nutzer
 * dann stellt.
 */
export function shortDraftText(drafted: number, target: number): string {
  return (
    `Der Vorschlag umfasst ${drafted} von angestrebten ${target} Bildern — ` +
    'für mehr reicht der Bildbestand nicht.'
  )
}

const SKELETON_TILE_COUNT = 6

export function CuratePage() {
  const { projectId } = useParams()
  const id = Number(projectId)
  // Das Motivset kommt vom Server und wird langlebig gecacht - es speist die schreibgeschuetzte
  // Motivliste im Info-Popover jeder Kachel. EIN Request fuer alle Kacheln.
  const motifsQuery = useMotifsQuery()
  // Der EIGENE Bewertungszustand wird ausschliesslich hierueber abgeleitet (`ownRatingStatus` mit
  // dem `username`-Claim des JWT, wie in Raster- und Detailansicht) - nie ueber `ratings[]`
  // insgesamt, sonst stellte die Ansicht die Bewertung des jeweils anderen als eigene dar
  // (Sicherheits-Muss-Kriterium).
  const token = getToken()
  const username = token ? decodeUsername(token) : null

  const query = useDraftQuery(id)
  // Die Cloud-Freigabe ist eine PROJEKTeinstellung und steht nicht am Foto - ohne sie entsteht
  // kein Album-Entwurf, und die Ansicht sagt das, statt eine leere Liste zu zeigen.
  const projectQuery = useProjectQuery(id)
  const setRatingMutation = useSetRatingMutation(id)
  // useMemo statt einer neuen `?? []`-Array-Referenz bei jedem Render (Lint-Fund: der Effekt
  // unten haengt von `items` ab, ein staendig neuer Referenzwert wuerde ihn bei jedem Render neu
  // ausloesen, obwohl sich die tatsaechlichen Daten nicht geaendert haben).
  const items = useMemo(() => query.data?.items ?? [], [query.data])

  // Die Fotos mit gerade LAUFENDER Verwerfen-Mutation - eine MENGE, nicht eine einzelne Id
  // - die fruehere seitenweite Einfach-Sperre war sinnvoll, solange die Liste danach umsprang;
  // ohne Nachruecken springt nichts mehr, und ein zweiter Klick verpuffte still. Jedes Foto
  // verwirft unabhaengig.
  //
  // ZWEI Ablagen fuer dieselbe Menge, mit verschiedenen Aufgaben: der Ref ist die SYNCHRONE
  // Wahrheit fuer die Sperre je Foto (siehe `handleReject`), der State loest das Neurendern der
  // betroffenen Kacheln aus. Beide werden ausschliesslich zusammen fortgeschrieben.
  const rejectingPhotoIdsRef = useRef<Set<number>>(new Set())
  const [rejectingPhotoIds, setRejectingPhotoIds] = useState<Set<number>>(new Set())

  // Klapp-Zustand der Tages-Abschnitte: leeres Set = alles aufgeklappt (Default) - kein
  // localStorage/sessionStorage/Query-Param, keine Persistierung ueber einen Reload hinaus.
  const [collapsedDayKeys, setCollapsedDayKeys] = useState<Set<string>>(new Set())

  // Aufgeklappte Kandidatenbereiche, Schluessel je Partition. Dieselbe Schluesselbildung wie
  // `knownGroupKeysRef` (JSON.stringify eines 2-Tupels).
  // Standardmaessig ist alles zugeklappt - der Kandidaten-Request laeuft ausschliesslich im
  // aufgeklappten Zustand.
  const [expandedGroupKeys, setExpandedGroupKeys] = useState<Set<string>>(new Set())

  function toggleDay(dayKey: string): void {
    setCollapsedDayKeys((prev) => toggleDayCollapse(prev, dayKey))
  }

  function toggleCandidates(groupKey: string): void {
    setExpandedGroupKeys((prev) => toggleDayCollapse(prev, groupKey))
  }

  // Erschoepfter Pool: eine Partition, die inzwischen komplett leer ist (letztes Foto gerade
  // abgelehnt), wuerde sonst spurlos aus der Gruppierung verschwinden - einmal gesehene
  // Partitionen bleiben deshalb fuer die Dauer des Seitenbesuchs bekannt, damit ihr Abschnitt
  // (mit eigenem Leerzustand statt kommentarlosem Verschwinden) sichtbar bleibt.
  //
  // Schluessel via JSON.stringify() statt eines zusammengesetzten Strings mit Trennzeichen: ein
  // einzelnes Trennzeichen waere anfaellig fuer eine Kollision, JSON.stringify(["a","b"]) ist
  // immer eindeutig umkehrbar. Beide Bestandteile sind heute Zahlen bzw. ein Datum, die Form
  // bleibt trotzdem - sie kostet nichts und traegt die Zusage.
  const knownGroupKeysRef = useRef<Set<string>>(new Set())
  // Cache fuer die Event-Meta-Info (Tag + Ueberschrift + Nummer): sobald das letzte Foto eines
  // Events abgelehnt wird, verschwindet seine `event_id` komplett aus `items` - die Ueberschrift
  // laesst sich dann nicht mehr aus aktuellen Daten bilden.
  const eventMetaRef = useRef<Map<string, EventMeta>>(new Map())

  const { groups, eventMeta } = groupByEvent(items)
  for (const [eventKey, meta] of eventMeta) {
    eventMetaRef.current.set(eventKey, meta)
  }

  for (const dayKey of Object.keys(groups)) {
    for (const eventKey of Object.keys(groups[dayKey])) {
      knownGroupKeysRef.current.add(JSON.stringify([dayKey, eventKey]))
    }
  }
  for (const key of knownGroupKeysRef.current) {
    const [dayKey, eventKey] = JSON.parse(key) as [string, string]
    groups[dayKey] ??= {}
    groups[dayKey][eventKey] ??= []
  }

  function handleReject(photo: PhotoOut): void {
    // SPERRE JE FOTO, nicht seitenweit: verschiedene Fotos verwerfen unabhaengig voneinander, ein
    // ZWEITER Vorgang fuer DASSELBE Foto wird verhindert. `Rating` traegt
    // `UniqueConstraint(photo_id, user_id)`, zwei nebenlaeufige Anfragen laufen in einen
    // IntegrityError und damit in eine 500.
    //
    // Geprueft wird gegen den REF, nicht gegen den State: `disabled` an der Schaltflaeche und
    // `rejectingPhotoIds` im Render-Closure entstehen beide erst durch ein State-Update, das
    // React fruehestens beim naechsten Render verarbeitet - zwei Klicks im selben Durchlauf
    // saehen beide denselben, leeren Schnappschuss. Auch die funktionale Updater-Form traegt
    // nicht: sie laeuft erst in der Render-Phase, also nach dem zweiten Klick. Der Ref ist die
    // synchrone Wahrheit, der State speist ausschliesslich die Anzeige.
    if (rejectingPhotoIdsRef.current.has(photo.id)) {
      return
    }
    rejectingPhotoIdsRef.current = new Set(rejectingPhotoIdsRef.current).add(photo.id)
    setRejectingPhotoIds(new Set(rejectingPhotoIdsRef.current))
    setRatingMutation.mutate(
      { photoId: photo.id, status: 'rejected' },
      {
        // `onSettled` statt `onError`: das Foto bleibt ohne Nachruecken in der Liste, es gibt
        // also kein "verschwindet" mehr, an dem sich das Ende der Mutation ablesen liesse.
        onSettled: () => {
          const next = new Set(rejectingPhotoIdsRef.current)
          next.delete(photo.id)
          rejectingPhotoIdsRef.current = next
          setRejectingPhotoIds(next)
        },
      },
    )
  }

  // Auf `=== true` gepruueft statt auf Falsyness: waehrend des Ladens ist das Feld `undefined`,
  // und das ist keine Aussage ueber die Freigabe.
  const cloudConsentGiven = projectQuery.data?.cloud_vision_detection_enabled === true

  // Die wirksame Zahl kommt FERTIG vom Server - das Frontend leitet sie nie selbst ab. Vor dem
  // Laden steht `0`, und die Bedingung unten ist damit unwahr: der Hinweis blitzt nicht auf,
  // bevor die Zahl bekannt ist.
  const effectiveSelectionTarget = projectQuery.data?.effective_selection_target ?? 0

  const motifSetError = motifsQuery.isError
    ? motifsQuery.error instanceof ApiError
      ? motifsQuery.error.detail
      : 'Fehler beim Laden der Motive.'
    : undefined

  function renderTile(photo: PhotoOut) {
    return (
      <CurationPhotoTile
        /* Ein Foto steht je Lauf in genau einer Zeile - `photo.id` ist wieder der belastbare
           Schluessel. */
        key={photo.id}
        photo={photo}
        motifSet={motifsQuery.data}
        motifSetLoading={motifsQuery.isLoading}
        motifSetError={motifSetError}
        onMotifSetRetry={() => {
          void motifsQuery.refetch()
        }}
        ownStatus={ownRatingStatus(photo.ratings, username)}
        rejecting={rejectingPhotoIds.has(photo.id)}
        onReject={() => handleReject(photo)}
      />
    )
  }

  // dayKey-Format YYYY-MM-DD sortiert lexikographisch = chronologisch.
  const dayKeys = Object.keys(groups).sort()

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-xl sm:text-2xl">Kuratierung</h1>
        {/* Personenbezug: Rating ist personenbezogen, die gezeigte Top-N-Auswahl deshalb je
            Nutzer individuell. */}
        <p className="text-sm text-text">Deine Auswahl</p>
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

      {/* Der Hinweis erscheint erst, wenn Projekt UND Kuratierungsantwort geladen sind - sonst
          blitzt er beim Laden eines freigegebenen Projekts kurz auf. Kein `Alert`, kein
          `role="alert"`, keine Fehlerfarbe, kein Symbol: eine fehlende Einwilligung ist kein
          Fehler. Die Schaltfläche ist bewusst SEKUNDÄR - sie navigiert, sie erteilt nichts. */}
      {query.isSuccess && projectQuery.isSuccess && !cloudConsentGiven && (
        <div className="flex flex-col items-start gap-3">
          <p className="text-sm text-text">{CURATION_CLOUD_CONSENT_TEXT}</p>
          <Button asChild variant="secondary" size="sm">
            <Link to={`/projects/${id}/settings`}>Zu den Projekteinstellungen</Link>
          </Button>
        </div>
      )}

      {query.isSuccess && projectQuery.isSuccess && cloudConsentGiven && dayKeys.length === 0 && (
        <p className="text-sm text-text">{CURATION_EMPTY_TEXT}</p>
      )}

      {/* Der Hinweis gilt allein dem Fall "Vorschlag KLEINER als der wirksame Richtwert" - dann
          hat der Bildbestand für mehr nicht gereicht, und beide Zahlen liegen bereits vor. Ist
          der Vorschlag GRÖSSER, sagt die Oberfläche nichts: dass jeder Foto-Moment vorkommt, ist
          die zugesagte Eigenschaft und kein Überraschungsfall.

          KEIN `Alert`, kein `role="alert"`, keine Warnfarbe, kein Symbol - schlichter Absatz in
          Sekundärtext, wie beim Auffangkorb und bei der fehlenden Einwilligung. Der Richtwert ist
          ein ZIEL und keine Obergrenze; ein kleinerer Vorschlag ist damit das zugesagte
          Normalverhalten und kein Warnfall. Eine Warnoptik suggerierte Handlungsdruck, den es
          nicht gibt - mehr Bilder gibt es schlicht nicht. */}
      {query.isSuccess &&
        projectQuery.isSuccess &&
        cloudConsentGiven &&
        items.length > 0 &&
        items.length < effectiveSelectionTarget && (
          <p className="text-sm text-text">
            {shortDraftText(items.length, effectiveSelectionTarget)}
          </p>
        )}

      {dayKeys.length > 0 && (
        // Zwei globale Aktionen - bleiben auch bei genau einem Tag im Projekt
        // sichtbar/funktionsfaehig. Sekundaerer Ton (Hilfsfunktion, keine Akzentfarbe). `gap-3`
        // statt `gap-2`: zwischen aufgespannten Trefferflaechen verlangt das Design-System
        // mindestens 12px.
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

      {dayKeys.map((dayKey) => {
        const eventsForDay = groups[dayKey]
        // Chronologisch nach der NUMMER des Events sortiert, nicht nach seiner Id: die Nummer ist
        // je Lauf lueckenlos ab 1 und chronologisch vergeben, die Id ist ein Surrogatschluessel
        // ohne zugesicherte Ordnung.
        const eventKeysForDay = Object.keys(eventsForDay).sort(
          (a, b) =>
            (eventMetaRef.current.get(a)?.position ?? 0) -
            (eventMetaRef.current.get(b)?.position ?? 0),
        )
        const dayIsEmpty = !Object.values(eventsForDay).some((photos) => photos.length > 0)
        // dayKey (Format YYYY-MM-DD) ist bereits ID-sicher.
        const panelId = `day-panel-${dayKey}`
        const isCollapsed = collapsedDayKeys.has(dayKey)
        return (
          // gap-6 (24px) gilt zwischen Tagen - das liefert bereits der aeussere Seiten-Wrapper,
          // da jede Tag-<section> dort ein direktes Geschwisterelement ist. Innerhalb eines Tages
          // gilt stattdessen gap-4 (16px) zwischen den Events.
          <section key={dayKey} className="flex flex-col gap-4">
            <h2 className="text-lg">
              {/* Gesamte Kopfzeile als Trigger - kein separates Icon als alleiniger interaktiver
                  Traeger, `w-full`+`text-left` macht die ganze Zeile klickbar, `min-h-11` sichert
                  ein Touch-Ziel von mindestens 44px. Flaeche, Zustaende und Trefferflaeche kommen
                  aus dem `Button`-Primitiv; die ZEILENFORM wird ausgeschrieben ueberschrieben:
                  `min-h-11` als Zeilenhoehe einer zeilenweisen Liste,
                  `whitespace-normal` gegen das `whitespace-nowrap` des Primitivs (die
                  Tagesueberschrift muss bei 360px umbrechen duerfen, sonst entsteht waagerechtes
                  Scrollen) und die Schriftstufe der Ueberschrift. */}
              <Button
                variant="ghost"
                aria-expanded={!isCollapsed}
                aria-controls={panelId}
                onClick={() => toggleDay(dayKey)}
                className="h-auto min-h-11 w-full justify-start whitespace-normal px-2 py-1 text-left text-lg font-normal"
              >
                <span aria-hidden="true">{isCollapsed ? '▶' : '▼'}</span>
                <span>{formatDayHeading(dayKey)}</span>
                {/* Kurzinfo nur im zugeklappten Zustand - reine Ableitung aus bereits geladenen
                    Daten, kein neuer State/Request. Explizites `{' '}` (statt sich auf das
                    visuelle `gap-2` zu verlassen): der zugaengliche Name eines Elements wird aus
                    dem Text seiner Kindknoten zusammengesetzt, CSS-`gap` erzeugt dabei keinen
                    Text-/Namensraum. */}
                {isCollapsed && (
                  <>
                    {' '}
                    <span className="font-normal text-text">
                      {`(${countPhotosInDay(eventsForDay)} Fotos)`}
                    </span>
                  </>
                )}
              </Button>
            </h2>
            {!isCollapsed && (
              // Kompletter Event-Teilbaum wird bei Zugeklapptheit per conditional JSX gar nicht
              // gerendert statt nur CSS-versteckt - spart bei grossen Projekten auch
              // tatsaechliche Render-Arbeit.
              <div id={panelId} className="flex flex-col gap-4">
                {dayIsEmpty && <p className="text-sm text-text">Keine Fotos für diesen Tag</p>}
                {!dayIsEmpty &&
                  eventKeysForDay.map((eventKey) => {
                    const photos = eventsForDay[eventKey]
                    const eventIsEmpty = photos.length === 0
                    const heading = eventMetaRef.current.get(eventKey)?.heading ?? eventKey
                    const eventCandidateCount = candidateCountOfEvent(photos)
                    // Ob es weitere Kandidaten gibt, steht VOR jedem Laden fest - kein
                    // Probe-Request. `rank_position` ist je Partition lueckenlos ab 1 vergeben,
                    // die Zahl der gezeigten Fotos ist damit zugleich der hoechste bereits
                    // gezeigte Rang.
                    const remainingCandidateCount = eventCandidateCount - photos.length
                    const groupKey = JSON.stringify([dayKey, eventKey])
                    return (
                      <section key={eventKey} className="flex flex-col gap-2">
                        {/* Die Zahl steht NEBEN der Ueberschrift in einem eigenen Element, nicht
                            in ihr: der von `formatEventHeading()` gelieferte Text (Name oder
                            Position, dazu die Zeitspanne) bleibt unveraendert. Gleiche
                            Formsprache wie die `(N Fotos)`-Kurzinfo der Tages-Kopfzeile. */}
                        <div className="flex flex-wrap items-baseline gap-2">
                          <h3 className="text-base">{heading}</h3>
                          {eventCandidateCount > 0 && (
                            <span className="text-sm text-text">
                              {`(${formatCandidateCount(eventCandidateCount)})`}
                            </span>
                          )}
                        </div>
                        {eventIsEmpty && <p className="text-sm text-text">{EMPTY_EVENT_TEXT}</p>}
                        {!eventIsEmpty && (
                          <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
                            {photos.map((photo) => renderTile(photo))}
                          </ul>
                        )}
                        {/* Der Auslöser erst NACH der Top-Foto-Reihe und nur, wenn der Vorrat
                            tatsaechlich groesser ist als das Gezeigte. */}
                        {remainingCandidateCount > 0 && (
                          <CurationCandidates
                            projectId={id}
                            eventId={Number(eventKey)}
                            afterRank={photos.length}
                            remainingCount={remainingCandidateCount}
                            panelId={`candidates-panel-${encodeURIComponent(groupKey)}`}
                            expanded={expandedGroupKeys.has(groupKey)}
                            onToggle={() => toggleCandidates(groupKey)}
                            renderTile={renderTile}
                          />
                        )}
                      </section>
                    )
                  })}
              </div>
            )}
          </section>
        )
      })}

      {/* "Zurück zum Projekt" entfaellt hier ersatzlos - die Kopfzeile traegt die
          Projektnavigation auf jeder Projektseite, /curate eingeschlossen. */}
    </div>
  )
}
