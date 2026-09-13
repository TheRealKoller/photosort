import type { PhotoOut, RatingStatus } from '../api/types'
import { formatEventHeading } from './timeOfDay'

/**
 * Reine Ableitungen des Album-Entwurfs - getrennt von der Ansicht, damit sie ohne Router,
 * QueryClient und Rendering prüfbar sind.
 */

/**
 * Ist dieses Foto im Album? Der Zweizustand der Entwurfskachel.
 *
 * `true` für alles außer einer eigenen Streichung: Die Antwortmenge des Entwurfszweigs enthält
 * ausschließlich Vorgeschlagenes und selbst Aufgenommenes, und beides gehört ins Album, solange
 * keine eigene Streichung dagegen steht. Ein noch nie bewertetes Foto steht deshalb als „Im
 * Album" da — der Vorschlag entscheidet, bis der Nutzer widerspricht.
 */
export function isInAlbum(ownStatus: RatingStatus | null): boolean {
  return ownStatus !== 'rejected'
}

/**
 * „Aufgenommen, vom aktuellen Vorschlag nicht getragen" — der Zustand hinter dem Abzeichen
 * `NOT_PROPOSED_BADGE_TEXT`.
 *
 * ZWEI DATENFORMEN, EIN ANZEIGEZUSTAND: `ranking: null` (im Ausschuss-Schritt aussortiert, nie
 * eine Rangzeile bekommen) und `ranking.proposed === false` (noch Kandidat, aber nicht gewählt).
 * Beide bedeuten dasselbe und müssen dieselbe Kennzeichnung tragen; eine Prüfung, die nur eine
 * der beiden Formen kennt, lässt die andere unmarkiert durch.
 *
 * Ohne eigene Aufnahme gibt es den Zustand nicht: Dann steht das Foto im Entwurf, WEIL der Lauf
 * es vorschlägt.
 */
export function isTakenWithoutProposal(photo: PhotoOut, ownStatus: RatingStatus | null): boolean {
  if (ownStatus !== 'album_worthy') {
    return false
  }
  const ranking = photo.ranking
  return !ranking || ranking.proposed === false
}

/** Eine Eventgruppe des Entwurfs - die Fotos in der Reihenfolge der Serverantwort. */
export interface DraftEventGroup {
  eventId: number
  heading: string
  photos: PhotoOut[]
}

/** Ein Tages-Abschnitt des Entwurfs mit seinen Eventgruppen. */
export interface DraftDay {
  dayKey: string
  events: DraftEventGroup[]
}

/**
 * Die zwei Gruppierungsebenen des Entwurfs: Tag und Event.
 *
 * DIE REIHENFOLGE IST DIE DER SERVERANTWORT - Tage, Eventgruppen und Fotos erscheinen in der
 * Reihenfolge ihres ersten Auftretens, und innerhalb einer Gruppe unverändert. Der Server sortiert
 * nach `(events.position, taken_at, photo_id)`; eine zweite Sortierung hier wäre eine zweite
 * Wahrheit über dieselbe Liste und liefe an dem Tag auseinander, an dem eine der beiden sich
 * ändert.
 *
 * Ein Foto ohne `event` wird ÜBERSPRUNGEN. Der Server liefert das Event auf jedem Foto des
 * Entwurfs; die Ausfallrichtung ist „nicht zeigen", nie eine erfundene Gruppe.
 */
export function groupDraftByDay(items: PhotoOut[]): DraftDay[] {
  const days: DraftDay[] = []
  const dayByKey = new Map<string, DraftDay>()
  const groupByEventId = new Map<number, DraftEventGroup>()

  for (const photo of items) {
    const photoEvent = photo.event
    if (!photoEvent) {
      continue
    }
    const { dayKey, heading } = formatEventHeading(photoEvent)
    let day = dayByKey.get(dayKey)
    if (day === undefined) {
      day = { dayKey, events: [] }
      dayByKey.set(dayKey, day)
      days.push(day)
    }
    let group = groupByEventId.get(photoEvent.id)
    if (group === undefined) {
      group = { eventId: photoEvent.id, heading, photos: [] }
      groupByEventId.set(photoEvent.id, group)
      day.events.push(group)
    }
    group.photos.push(photo)
  }
  return days
}

/**
 * Der Kopfzeilentext: Ist-Anzahl und Richtwert NEBENEINANDER.
 *
 * Beide Zahlen ausgeschrieben und in beiden Abweichungsrichtungen derselbe Satzbau: Der Richtwert
 * ist ein Ziel und keine Obergrenze, eine Abweichung nach oben wie nach unten ist ein neutraler
 * Hinweis. Ein zweiter Ton („zu wenig", „zu viel") machte daraus einen Zustand, der behoben werden
 * müsste — es gibt hier nichts zu beheben.
 */
export function draftSizeText(actual: number, target: number): string {
  return `${actual} von etwa ${target} Bildern`
}

/** „1 Bild" / „N Bilder" - die Anzahl der Bilder eines Events im Entwurf. */
export function formatDraftPhotoCount(count: number): string {
  return `${count} ${count === 1 ? 'Bild' : 'Bilder'}`
}
