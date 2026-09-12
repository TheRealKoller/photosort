import { useMemo, useRef, useState } from 'react'
import { useParams, useSearchParams } from 'react-router'

import { ApiError } from '../api/client'
import type { PhotoOut, RankingOut } from '../api/types'
import { decodeUsername } from '../auth/jwt'
import { getToken } from '../auth/token'
import { CategoryBadge } from '../components/CategoryBadge'
import { CurationCandidates } from '../components/CurationCandidates'
import { CurationPhotoTile } from '../components/CurationPhotoTile'
import { Alert } from '../components/ui/alert'
import { Button } from '../components/ui/button'
import { Checkbox } from '../components/ui/checkbox'
import { Skeleton } from '../components/ui/skeleton'
import { useCategoriesQuery } from '../hooks/useCategories'
import { useCategoryOverrideControls } from '../hooks/useCategoryOverrideControls'
import { useCurationQuery, useSetRatingMutation } from '../hooks/usePhotos'
import {
  CATCH_ALL_CATEGORY_KEY,
  formatCategoryKey,
  sortCategoryKeys,
} from '../utils/categoryLabels'
import { parseTopN } from '../utils/curationTopN'
import { ownRatingStatus } from '../utils/ownRating'
import { curatedRankings } from '../utils/rankings'
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
 * EIN gerendertes Kachel-Vorkommen: das Foto UND die Zugehoerigkeit, unter der es an dieser Stelle
 * steht. Bei Mehrfachzugehoerigkeit reicht das Foto allein nicht - dasselbe Foto kann in zwei
 * Kategorien stehen und traegt dort verschiedene Rollen (Haupt- bzw. Nebenkategorie).
 */
export interface CurationEntry {
  photo: PhotoOut
  ranking: RankingOut
}

interface GroupedPhotos {
  [dayKey: string]: {
    [eventKey: string]: {
      [categoryKey: string]: CurationEntry[]
    }
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
 * Durchlauf sortiert die Zugehoerigkeiten in die dreistufige
 * {Tag: {Event: {Kategorie: Eintraege}}}-Struktur ein.
 *
 * Die Meta-Info entsteht aus `photo.event` - EINER Zeile, nicht aus einer Aggregation ueber die
 * sichtbaren Fotos. Der Server sichert zu, dass sie auf jedem Foto desselben Events feldgleich
 * ist; deshalb genuegt ein beliebiges.
 *
 * Iteriert je Foto ueber `curatedRankings(photo)` - ein Foto kann damit in MEHREREN Kategorien
 * erscheinen. Welche das sind, entscheidet ausschliesslich der Server (`curation_position !==
 * null`); das Frontend bildet weder die Auswahl noch eine Schwelle nach.
 */
function groupByEventAndCategory(items: PhotoOut[]): {
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
    for (const ranking of curatedRankings(photo)) {
      const eventKey = eventKeyOf(ranking.event_id)
      const categoryKey = ranking.category_key
      const meta = eventMeta.get(eventKey)
      if (meta === undefined) {
        // Erreichbar nur, wenn ein Foto eine Rangzeile ohne zugehoeriges `event` traegt - der
        // Server liefert das nicht. Defensive Absicherung statt einer Non-Null-Assertion.
        continue
      }
      groups[meta.dayKey] ??= {}
      groups[meta.dayKey][eventKey] ??= {}
      groups[meta.dayKey][eventKey][categoryKey] ??= []
      groups[meta.dayKey][eventKey][categoryKey].push({ photo, ranking })
    }
  }
  return { groups, eventMeta }
}

/** Ob mindestens eine Kategorie in dieser Event-Ebene noch (sichtbare) Fotos hat. */
function categoriesHavePhotos(categories: { [categoryKey: string]: CurationEntry[] }): boolean {
  return Object.values(categories).some((entries) => entries.length > 0)
}

/**
 * Fotoanzahl eines Tages fuer die Kurzinfo im zugeklappten Zustand - reine Ableitung aus bereits
 * geladenen Daten, kein neuer State/Request.
 *
 * Zaehlt EINDEUTIGE FOTOS, nicht Zugehoerigkeiten: die Beschriftung lautet "N Fotos" - ein Foto,
 * das an diesem Tag in zwei Kategorien erscheint, erhoeht die Zahl um eins.
 */
export function countPhotosInDay(eventsForDay: {
  [eventKey: string]: { [categoryKey: string]: CurationEntry[] }
}): number {
  const photoIds = new Set<number>()
  for (const categories of Object.values(eventsForDay)) {
    for (const entries of Object.values(categories)) {
      for (const entry of entries) {
        photoIds.add(entry.photo.id)
      }
    }
  }
  return photoIds.size
}

/**
 * Kandidatenzahl EINER Kategorie eines Events: schlicht die `partition_size` - alle Eintraege
 * einer Partition tragen denselben Wert, weil er lauf-global je (event_id, category_key)
 * berechnet wird und nicht nutzerspezifisch gefiltert ist.
 *
 * `0` fuer eine leergelaufene Kategorie (nur noch ueber `knownGroupKeysRef` bekannt, nach einem
 * Kategorie-Override). Die Ueberschrift bekommt dann GAR KEINE Zahl - "0 Kandidaten" waere eine
 * Aussage ueber einen Bestand, den die Antwort gar nicht mehr beschreibt (Akzeptanzkriterium 10).
 */
export function candidateCountOfCategory(entries: CurationEntry[]): number {
  return entries[0]?.ranking.partition_size ?? 0
}

/**
 * Kandidatenzahl eines Events: die SUMME der Kategorie-Zahlen darunter. Ein Foto, das im selben
 * Event in zwei Kategorien steht, zaehlt darin ZWEIMAL - bewusste Produktentscheidung Daniels:
 * die Zahl beschreibt, was tatsaechlich zu sichten ist (die Kachel erscheint zweimal und ist
 * zweimal einzeln zu beurteilen), nicht wie viele verschiedene Fotos es sind.
 *
 * Genau deshalb heisst sie "Kandidaten" und nicht "Fotos" - die Tages-Ueberschrift zaehlt
 * ausdruecklich eindeutige FOTOS (siehe `countPhotosInDay`). Verschiedene Groessen tragen
 * verschiedene Woerter; das ist die einzige Stelle, an der diese Entscheidung fuer den Nutzer
 * lesbar bleibt.
 */
export function candidateCountOfEvent(photosByCategory: {
  [categoryKey: string]: CurationEntry[]
}): number {
  return Object.values(photosByCategory).reduce(
    (sum, entries) => sum + candidateCountOfCategory(entries),
    0,
  )
}

/** "1 Kandidat" / "N Kandidaten" (Akzeptanzkriterium 9). */
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
 * Die Schwelle des Kuratierungsfilters "Nur unsichere Zuordnungen" - EXKLUSIV: `0.6` selbst gilt
 * nicht als niedrig.
 *
 * Sie lebt bewusst NUR hier im Frontend: weder API noch Datenbank kennen einen Begriff von
 * "unsicher". Eine Schwelle, die beide Seiten braeuchten, muesste gespiegelt oder ueber ein neues
 * API-Feld transportiert werden - fuer eine Frage, die keine fachliche ist, sondern eine Sicht.
 */
export const LOW_CONFIDENCE_THRESHOLD = 0.6

/**
 * Hinweistext einer durch den Filter LEER GEWORDENEN Partition - bewusst ein anderer Text als
 * "Kein weiteres Foto verfügbar" (erschoepfter Pool). Beide Zustaende sehen sonst gleich aus,
 * bedeuten aber Gegensaetzliches: hier gibt es Fotos, sie sind nur alle sicher genug.
 *
 * Aus der Konstante gebildet statt ausgeschrieben, damit Schwelle und Text nicht auseinanderlaufen.
 */
export const LOW_CONFIDENCE_EMPTY_TEXT = `Keine Fotos mit einer Sicherheit unter ${
  LOW_CONFIDENCE_THRESHOLD * 100
} % in dieser Gruppe.`

/**
 * Variante fuer eine Partition, in der noch Fotos stehen, aber weniger als `topN` - bei aktivem
 * Filter fehlen die uebrigen Plaetze wegen des Filters, NICHT weil der Pool erschoepft waere.
 * "Kein weiteres Foto verfügbar" waere dort eine falsche Aussage ueber den Bearbeitungsstand.
 */
const LOW_CONFIDENCE_NO_MORE_TEXT = `Kein weiteres Foto unter ${
  LOW_CONFIDENCE_THRESHOLD * 100
} % in dieser Gruppe.`

const LOW_CONFIDENCE_EMPTY_DAY_TEXT = `Keine Fotos mit einer Sicherheit unter ${
  LOW_CONFIDENCE_THRESHOLD * 100
} % an diesem Tag.`

const LOW_CONFIDENCE_EMPTY_EVENT_TEXT = `Keine Fotos mit einer Sicherheit unter ${
  LOW_CONFIDENCE_THRESHOLD * 100
} % in dieser Gruppe.`

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
  'Noch keine Kategorie-Kuratierung verfügbar — führe eine Kriterien-Bewertung aus. ' +
  'Ein Lauf von vor der Umstellung auf Events muss einmal neu berechnet werden.'

const LOW_CONFIDENCE_FILTER_LABEL = 'Nur unsichere Zuordnungen'

/**
 * Reine Filterfunktion ueber den bereits geladenen Fotos (Akzeptanzkriterium 5) - laeuft VOR
 * `groupByEventAndCategory`, damit die Gruppierung selbst unveraendert bleibt.
 *
 * Ein Foto OHNE Angabe faellt heraus (Produktentscheidung Daniels): es ist keine unsichere
 * Zuordnung, sondern eine unbekannte. Deshalb die Pruefung auf `!== null` und nicht auf
 * Falsyness - `0` ist ein gueltiger Wert und gehoert eindeutig unter die Schwelle.
 */
export function filterLowConfidence(items: PhotoOut[]): PhotoOut[] {
  return items.filter(
    (item) =>
      item.category_confidence !== null && item.category_confidence < LOW_CONFIDENCE_THRESHOLD,
  )
}

/**
 * Neutraler Erklaertext des Auffang-Abschnitts (Set-Eintrag "Nicht erkannt") - struktureller Text,
 * KEINE Fehler-Semantik (kein `role="alert"`, keine Fehlerfarbe): das Fehlen einer Erkennung ist
 * kein Fehler.
 */
const CATCH_ALL_EXPLANATION = 'Für diese Fotos war kein Bildmotiv sicher bestimmbar.'

const SKELETON_TILE_COUNT = 6

export function CurateCategoriesPage() {
  const { projectId } = useParams()
  const id = Number(projectId)
  const [searchParams] = useSearchParams()
  const topN = parseTopN(searchParams.get('topN'))
  // Das feste Set kommt vom Server und wird langlebig gecacht - es speist Anzeigenamen,
  // Abschnitts-Reihenfolge und die "Alle Kategorien"-Auswahl.
  const categoriesQuery = useCategoriesQuery()
  const categorySet = categoriesQuery.data ?? []
  // Der EIGENE Bewertungszustand wird ausschliesslich hierueber abgeleitet (`ownRatingStatus` mit
  // dem `username`-Claim des JWT, wie in Raster- und Detailansicht) - nie ueber `ratings[]`
  // insgesamt, sonst stellte die Ansicht die Bewertung des jeweils anderen als eigene dar
  // (Sicherheits-Muss-Kriterium).
  const token = getToken()
  const username = token ? decodeUsername(token) : null

  const query = useCurationQuery(id, topN)
  const setRatingMutation = useSetRatingMutation(id)
  const categoryOverrideControls = useCategoryOverrideControls(id)
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

  // Der Filterzustand lebt in `useState` wie `collapsedDayKeys`, NICHT in den Suchparametern - dort
  // steht nur, was das Backend als Query-Parameter sieht, und dieser Filter loest bewusst keine
  // neue Anfrage aus.
  const [lowConfidenceOnly, setLowConfidenceOnly] = useState(false)

  // Aufgeklappte Kandidatenbereiche, Schluessel je Partition. Dieselbe kollisionssichere
  // Schluesselbildung wie `knownGroupKeysRef` (JSON.stringify eines 3-Tupels), damit ein
  // category_key mit Trennzeichen keine zwei Bereiche verschmelzen laesst.
  // Standardmaessig ist alles zugeklappt (Akzeptanzkriterium 20) - der Kandidaten-Request laeuft
  // ausschliesslich im aufgeklappten Zustand.
  const [expandedGroupKeys, setExpandedGroupKeys] = useState<Set<string>>(new Set())

  function toggleDay(dayKey: string): void {
    setCollapsedDayKeys((prev) => toggleDayCollapse(prev, dayKey))
  }

  function toggleCandidates(groupKey: string): void {
    setExpandedGroupKeys((prev) => toggleDayCollapse(prev, groupKey))
  }

  // Der frueher hier stehende `useEffect`, der den Busy-Zustand zuruecksetzte, sobald das Foto aus
  // `items` verschwand, ist mit dem Nachruecken entfallen: ohne Backfill verschwindet das Foto nie,
  // die Schaltflaeche bliebe dauerhaft busy. Ersatz ist der `onSettled`-Callback der Mutation in
  // `handleReject`.

  // Erschoepfter Pool (Akzeptanzkriterium 7 der Spec): eine Partition, die inzwischen komplett leer
  // ist (letztes Foto gerade abgelehnt), wuerde sonst spurlos aus der Gruppierung verschwinden -
  // einmal gesehene Partitionen bleiben deshalb fuer die Dauer des Seitenbesuchs bekannt, damit ihr
  // Abschnitt (mit eigenem Leerzustand statt kommentarlosem Verschwinden) sichtbar bleibt.
  // Schluessel via JSON.stringify() statt eines zusammengesetzten Strings mit Trennzeichen
  // (Review-Fund test-engineer/security-engineer/architect): ein einzelnes Trennzeichen waere
  // anfaellig fuer eine Kollision, sollte ein kuenftiger category_key es selbst enthalten -
  // JSON.stringify(["a","b","c"]) ist immer eindeutig umkehrbar. 3-Tupel [dayKey, eventKey,
  // categoryKey], nicht 2-Tupel.
  const knownGroupKeysRef = useRef<Set<string>>(new Set())
  // Cache fuer die Event-Meta-Info (Tag + Ueberschrift + Nummer): sobald das letzte Foto eines
  // Events abgelehnt wird, verschwindet seine `event_id` komplett aus `items` - die Ueberschrift
  // laesst sich dann nicht mehr aus aktuellen Daten bilden. Wird bei jedem Render fuer alle in
  // `items` noch vorhandenen Events ueberschrieben und liefert fuer erschoepfte weiterhin die
  // zuletzt bekannte Meta-Info.
  const eventMetaRef = useRef<Map<string, EventMeta>>(new Map())

  // ZWEI Gruppierungen, wenn der Filter aktiv ist - das ist kein Versehen: die Merkliste gesehener
  // Partitionen und der Event-Meta-Cache werden weiterhin aus den UNGEFILTERTEN `items` gespeist.
  // Speiste man sie aus der gefilterten Sicht, verschwaenden Partitionen beim Einschalten des
  // Filters DAUERHAFT: sie waeren nach dem Ausschalten nicht mehr in der Merkliste und ihre
  // Event-Ueberschrift nicht mehr bildbar.
  const unfiltered = groupByEventAndCategory(items)
  const groups = lowConfidenceOnly
    ? groupByEventAndCategory(filterLowConfidence(items)).groups
    : unfiltered.groups
  for (const [eventKey, meta] of unfiltered.eventMeta) {
    eventMetaRef.current.set(eventKey, meta)
  }

  for (const dayKey of Object.keys(unfiltered.groups)) {
    for (const eventKey of Object.keys(unfiltered.groups[dayKey])) {
      for (const categoryKey of Object.keys(unfiltered.groups[dayKey][eventKey])) {
        knownGroupKeysRef.current.add(JSON.stringify([dayKey, eventKey, categoryKey]))
      }
    }
  }
  for (const key of knownGroupKeysRef.current) {
    const [dayKey, eventKey, categoryKey] = JSON.parse(key) as [string, string, string]
    groups[dayKey] ??= {}
    groups[dayKey][eventKey] ??= {}
    groups[dayKey][eventKey][categoryKey] ??= []
  }

  function handleReject(photo: PhotoOut): void {
    // SPERRE JE FOTO, nicht seitenweit: verschiedene Fotos verwerfen unabhaengig voneinander, ein
    // ZWEITER Vorgang fuer DASSELBE Foto wird verhindert. Aufgegeben wurde die seitenweite
    // Einfachsperre, nicht dieser Schutz: `Rating` traegt `UniqueConstraint(photo_id, user_id)`,
    // zwei nebenlaeufige Anfragen laufen in einen IntegrityError und damit in eine 500. Dasselbe
    // Foto hat ausserdem bis zu vier Kacheln mit je eigener Schaltflaeche - ein schneller Klick auf
    // zwei davon ist ein realistischer Bedienweg.
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

  // dayKey-Format YYYY-MM-DD sortiert lexikographisch = chronologisch (Akzeptanzkriterium 1).
  const dayKeys = Object.keys(groups).sort()

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-xl sm:text-2xl">Kategorie-Kuratierung</h1>
        {/* Personenbezug (UI/UX-Abschnitt der Spec): Rating ist personenbezogen, die gezeigte
            Top-N-Auswahl deshalb je Nutzer individuell. */}
        <p className="text-sm text-text">Deine Auswahl</p>
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
          {query.error instanceof ApiError ? query.error.detail : 'Fehler beim Laden der Fotos.'}
        </Alert>
      )}

      {query.isSuccess && dayKeys.length === 0 && (
        <p className="text-sm text-text">{CURATION_EMPTY_TEXT}</p>
      )}

      {dayKeys.length > 0 && (
        // Zwei globale Aktionen - bleiben auch bei genau einem Tag im Projekt
        // sichtbar/funktionsfaehig, da hier nicht extra auf `dayKeys.length > 1` geprueft wird.
        // Sekundaerer Ton (Hilfsfunktion, keine Akzentfarbe, UI/UX-Abschnitt). `gap-3` statt
        // `gap-2`: zwischen aufgespannten Trefferflaechen verlangt das Design-System mindestens
        // 12px - das Kontrollkaestchen bringt eine eigene mit.
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
          {/* Kontrollkaestchen statt Schalter - der Schalter steht im Produkt fuer eine
              DAUERHAFTE Einstellung, dies ist eine Sicht-Entscheidung dieses Besuchs. Der Filter
              arbeitet auf den bereits geladenen Daten und loest keine neue Anfrage aus. */}
          <Checkbox
            checked={lowConfidenceOnly}
            onCheckedChange={setLowConfidenceOnly}
            label={LOW_CONFIDENCE_FILTER_LABEL}
          />
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
        const dayIsEmpty = !Object.values(eventsForDay).some(categoriesHavePhotos)
        // dayKey (Format YYYY-MM-DD) ist bereits ID-sicher.
        const panelId = `day-panel-${dayKey}`
        const isCollapsed = collapsedDayKeys.has(dayKey)
        return (
          // UI/UX-Abschnitt der Spec: gap-6 (24px) gilt zwischen Tagen - das liefert bereits der
          // aeussere Seiten-Wrapper (naechste Zeile im JSX-Baum, `flex flex-col gap-6`), da jede
          // Tag-<section> dort ein direktes Geschwisterelement ist. Innerhalb eines Tages gilt
          // stattdessen gap-4 (16px) zwischen den Events (Review-Fund ux-ui-designer: gap-6
          // hier haette faelschlich auch zwischen ihnen 24px statt 16px erzeugt).
          <section key={dayKey} className="flex flex-col gap-4">
            <h2 className="text-lg">
              {/* Gesamte Kopfzeile als Trigger (Akzeptanzkriterium 1) - kein separates Icon als
                  alleiniger interaktiver Traeger, `w-full`+`text-left` macht die ganze Zeile
                  klickbar, `min-h-11` sichert ein Touch-Ziel von mindestens 44px. */}
              {/* Keine handgerollte Schaltflaeche - Flaeche, Zustaende
                  und Trefferflaeche kommen aus dem `Button`-Primitiv. Die ZEILENFORM bleibt und
                  wird ausgeschrieben ueberschrieben: `min-h-11` als Zeilenhoehe einer zeilenweisen
                  Liste (Trefferflaechen-Regel 3), `whitespace-normal` gegen das `whitespace-nowrap`
                  des Primitivs (die Tagesueberschrift muss bei 360px umbrechen duerfen, sonst
                  entsteht waagerechtes Scrollen) und die Schriftstufe der Ueberschrift statt der
                  Board-Schaltflaechenschrift. */}
              <Button
                variant="ghost"
                aria-expanded={!isCollapsed}
                aria-controls={panelId}
                onClick={() => toggleDay(dayKey)}
                className="h-auto min-h-11 w-full justify-start whitespace-normal px-2 py-1 text-left text-lg font-normal"
              >
                <span aria-hidden="true">{isCollapsed ? '▶' : '▼'}</span>
                <span>{formatDayHeading(dayKey)}</span>
                {/* Kurzinfo nur im zugeklappten Zustand (Akzeptanzkriterium 5) - reine Ableitung
                    aus bereits geladenen Daten, kein neuer State/Request (Akzeptanzkriterium 6).
                    Explizites `{' '}` (statt sich auf das visuelle `gap-2` zu verlassen): der
                    zugaengliche Name eines Elements wird aus dem Text seiner Kindknoten
                    zusammengesetzt, CSS-`gap` erzeugt dabei keinen Text-/Namensraum. */}
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
              // gerendert statt nur CSS-versteckt (Akzeptanzkriterium 4) - spart bei grossen
              // Projekten auch tatsaechliche Render-Arbeit (Architektur-Abschnitt der Spec).
              <div id={panelId} className="flex flex-col gap-4">
                {dayIsEmpty && (
                  <p className="text-sm text-text">
                    {lowConfidenceOnly
                      ? LOW_CONFIDENCE_EMPTY_DAY_TEXT
                      : 'Keine Fotos für diesen Tag'}
                  </p>
                )}
                {!dayIsEmpty &&
                  eventKeysForDay.map((eventKey) => {
                    const photosByCategory = eventsForDay[eventKey]
                    const categoryKeys = sortCategoryKeys(
                      Object.keys(photosByCategory),
                      categorySet,
                    )
                    const eventIsEmpty = !categoriesHavePhotos(photosByCategory)
                    const heading = eventMetaRef.current.get(eventKey)?.heading ?? eventKey
                    // Die Zahlen kommen AUSSCHLIESSLICH aus der ungefilterten Gruppierung
                    // (Akzeptanzkriterium 7): sonst verschwaenden sie genau dort, wo der
                    // Konfidenzfilter eine Gruppe leer raeumt, obwohl der Bestand unveraendert
                    // ist - und die Event-Summe verloere die weggefilterten Kategorien.
                    const unfilteredCategories = unfiltered.groups[dayKey]?.[eventKey] ?? {}
                    const eventCandidateCount = candidateCountOfEvent(unfilteredCategories)
                    return (
                      <section key={eventKey} className="flex flex-col gap-4">
                        {/* Die Zahl steht NEBEN der Ueberschrift in einem eigenen Element, nicht
                            in ihr (Akzeptanzkriterium 4): der von `formatEventHeading()`
                            gelieferte Text (Tageszeit + Zeitraum) bleibt unveraendert, und die
                            fuer einen spaeteren Ausbau vorgesehene Ortsangabe behaelt ihren
                            Platz. Gleiche Formsprache wie die `(N Fotos)`-Kurzinfo der
                            Tages-Kopfzeile. */}
                        <div className="flex flex-wrap items-baseline gap-2">
                          <h3 className="text-base">{heading}</h3>
                          {eventCandidateCount > 0 && (
                            <span className="text-sm text-text">
                              {`(${formatCandidateCount(eventCandidateCount)})`}
                            </span>
                          )}
                        </div>
                        {eventIsEmpty && (
                          <p className="text-sm text-text">
                            {lowConfidenceOnly ? LOW_CONFIDENCE_EMPTY_EVENT_TEXT : EMPTY_EVENT_TEXT}
                          </p>
                        )}
                        {!eventIsEmpty &&
                          categoryKeys.map((categoryKey) => {
                            const entries = photosByCategory[categoryKey]
                            const unfilteredEntries = unfilteredCategories[categoryKey] ?? []
                            const categoryCandidateCount =
                              candidateCountOfCategory(unfilteredEntries)
                            // Ob es weitere Kandidaten gibt, steht VOR jedem Laden fest - kein
                            // Probe-Request (Entwurfsentscheidung 8). `rank_position` ist je
                            // Partition lueckenlos ab 1 vergeben, die Zahl der ungefilterten
                            // Eintraege ist damit zugleich der hoechste bereits gezeigte Rang.
                            const remainingCandidateCount =
                              categoryCandidateCount - unfilteredEntries.length
                            const groupKey = JSON.stringify([dayKey, eventKey, categoryKey])
                            return (
                              <div key={categoryKey} className="flex flex-col gap-2">
                                <h4 className="flex flex-wrap items-center gap-2 text-sm font-semibold">
                                  <CategoryBadge
                                    categoryKey={categoryKey}
                                    categories={categorySet}
                                  />
                                  {formatCategoryKey(categoryKey, categorySet)}
                                  {/* Eine leergelaufene Kategorie bekommt GAR KEINE Zahl
                                      (Akzeptanzkriterium 10) - "0 Kandidaten" waere eine Aussage
                                      ueber einen Bestand, den die Antwort nicht mehr beschreibt. */}
                                  {categoryCandidateCount > 0 && (
                                    <span className="font-normal text-text">
                                      {`— ${formatCandidateCount(categoryCandidateCount)}`}
                                    </span>
                                  )}
                                </h4>
                                {/* Auffangkorb-Kategorie mit erklärend dezentem Signal:
                                    kurzer struktureller Hinweistext direkt unter der
                                    Überschrift, kein Icon/Badge, keine Fehler-Optik. */}
                                {categoryKey === CATCH_ALL_CATEGORY_KEY && (
                                  <p className="text-sm text-text">{CATCH_ALL_EXPLANATION}</p>
                                )}
                                <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
                                  {entries.map(({ photo, ranking }) => (
                                    <CurationPhotoTile
                                      /* photo.id allein ist beim Mehrfachrendering desselben
                                         Datensatzes keine belastbare Zusage mehr - React braucht
                                         den Schluessel je VORKOMMEN. */
                                      key={`${photo.id}-${ranking.category_key}`}
                                      photo={photo}
                                      ranking={ranking}
                                      categories={categorySet}
                                      categoriesLoading={categoriesQuery.isLoading}
                                      categoriesError={categoriesQuery.isError}
                                      onRetryCategories={() => {
                                        void categoriesQuery.refetch()
                                      }}
                                      categoryOverrideControls={categoryOverrideControls}
                                      ownStatus={ownRatingStatus(photo.ratings, username)}
                                      rejecting={rejectingPhotoIds.has(photo.id)}
                                      onReject={() => handleReject(photo)}
                                    />
                                  ))}
                                  {/* Zwei UNTERSCHEIDBARE Leerzustaende (Akzeptanzkriterium 5):
                                      eine leer GEFILTERTE Partition ist das Gegenteil eines
                                      erschoepften Pools - dort gibt es Fotos, sie sind nur alle
                                      sicher genug. Derselbe Text fuer beide liesse den Nutzer
                                      glauben, er haette die Gruppe bereits abgearbeitet. */}
                                  {/* Der Erschoepfungshinweis und der Auslöser weiter unten
                                      schliessen einander aus (Akzeptanzkriterium 25): "Kein
                                      weiteres Foto verfügbar" waere neben "es gibt noch drei"
                                      ein Widerspruch. */}
                                  {entries.length < topN &&
                                    (lowConfidenceOnly || remainingCandidateCount <= 0) && (
                                      <li className="flex aspect-square w-full flex-col items-center justify-center rounded-lg border border-dashed border-separator p-2 text-center text-xs text-text">
                                        {!lowConfidenceOnly
                                          ? 'Kein weiteres Foto verfügbar'
                                          : entries.length === 0
                                            ? LOW_CONFIDENCE_EMPTY_TEXT
                                            : LOW_CONFIDENCE_NO_MORE_TEXT}
                                      </li>
                                    )}
                                </ul>
                                {/* Der Auslöser erst NACH der Top-Foto-Reihe und nur, wenn der
                                    Vorrat tatsaechlich groesser ist als das Gezeigte. */}
                                {remainingCandidateCount > 0 && (
                                  <CurationCandidates
                                    projectId={id}
                                    eventId={Number(eventKey)}
                                    categoryKey={categoryKey}
                                    afterRank={unfilteredEntries.length}
                                    remainingCount={remainingCandidateCount}
                                    panelId={`candidates-panel-${encodeURIComponent(groupKey)}`}
                                    expanded={expandedGroupKeys.has(groupKey)}
                                    onToggle={() => toggleCandidates(groupKey)}
                                    filterPhotos={
                                      lowConfidenceOnly ? filterLowConfidence : undefined
                                    }
                                    renderTile={(photo, ranking) => (
                                      <CurationPhotoTile
                                        key={`${photo.id}-${ranking.category_key}`}
                                        photo={photo}
                                        ranking={ranking}
                                        categories={categorySet}
                                        categoriesLoading={categoriesQuery.isLoading}
                                        categoriesError={categoriesQuery.isError}
                                        onRetryCategories={() => {
                                          void categoriesQuery.refetch()
                                        }}
                                        categoryOverrideControls={categoryOverrideControls}
                                        ownStatus={ownRatingStatus(photo.ratings, username)}
                                        rejecting={rejectingPhotoIds.has(photo.id)}
                                        onReject={() => handleReject(photo)}
                                      />
                                    )}
                                  />
                                )}
                              </div>
                            )
                          })}
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
