import type { EventOut, PhotoOut } from '../api/types'
import { formatEventHeading } from './timeOfDay'

/**
 * Die Gliederung einer Fotoliste nach Tag und Event - geteilt von Album-Entwurf und Endauswahl.
 *
 * SIE LEBT GENAU EINMAL: Beide Ansichten gliedern dieselbe Antwortform, und eine zweite Kopie
 * wäre genau die „zweite Wahrheit über dieselbe Liste", vor der die Reihenfolgen-Zusage unten
 * warnt - sie liefe an dem Tag auseinander, an dem eine der beiden sich ändert.
 */

/** Eine Eventgruppe - die Fotos in der Reihenfolge der Serverantwort. */
export interface PhotoEventGroup {
  eventId: number
  heading: string
  photos: PhotoOut[]
}

/** Ein Tages-Abschnitt mit seinen Eventgruppen. */
export interface PhotoDay {
  dayKey: string
  events: PhotoEventGroup[]
}

/**
 * Die zwei Gruppierungsebenen: Tag und Event.
 *
 * DIE REIHENFOLGE IST DIE DER SERVERANTWORT - Tage, Eventgruppen und Fotos erscheinen in der
 * Reihenfolge ihres ersten Auftretens, und innerhalb einer Gruppe unverändert. Der Server sortiert
 * nach `(events.position, taken_at, photo_id)`; eine zweite Sortierung hier wäre eine zweite
 * Wahrheit über dieselbe Liste und liefe an dem Tag auseinander, an dem eine der beiden sich
 * ändert.
 *
 * Ein Foto ohne `event` wird ÜBERSPRUNGEN. Der Server liefert das Event auf jedem Foto beider
 * Antwortmengen; die Ausfallrichtung ist „nicht zeigen", nie eine erfundene Gruppe.
 */
export function groupPhotosByDay(items: PhotoOut[]): PhotoDay[] {
  const days: PhotoDay[] = []
  const dayByKey = new Map<string, PhotoDay>()
  const groupByEventId = new Map<number, PhotoEventGroup>()

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

/** Ein Eventabschnitt des Album-Entwurfs - auch ohne ein einziges Foto. */
export interface DraftEventGroup {
  event: EventOut
  heading: string
  photos: PhotoOut[]
}

export interface DraftDay {
  dayKey: string
  events: DraftEventGroup[]
}

/**
 * Die Gliederung des Album-Entwurfs: Die Abschnitte kommen aus der EVENTLISTE des Laufs, nicht aus
 * den Fotos. Ein Event ohne Foto im Entwurf steht deshalb als eigener Abschnitt da (mit
 * Hinzufügen-Feld), und „Event p von E" bleibt stabil, gleich was gestrichen, gefiltert oder
 * zugeklappt ist. Die Endauswahl gliedert weiter über `groupPhotosByDay`.
 *
 * Reihenfolge der Abschnitte nach `position`; die Fotos eines Abschnitts in Antwortreihenfolge.
 * Ein Foto, dessen Event nicht in der Liste steht, wird übergangen - die Ausfallrichtung ist
 * „nicht zeigen", nie ein erfundener Abschnitt.
 */
export function groupEventsByDay(events: EventOut[], items: PhotoOut[]): DraftDay[] {
  const groupByEventId = new Map<number, DraftEventGroup>()
  const days: DraftDay[] = []
  for (const event of [...events].sort((left, right) => left.position - right.position)) {
    const { dayKey, heading } = formatEventHeading(event)
    let day = days.at(-1)
    if (day?.dayKey !== dayKey) {
      day = { dayKey, events: [] }
      days.push(day)
    }
    const group: DraftEventGroup = { event, heading, photos: [] }
    groupByEventId.set(event.id, group)
    day.events.push(group)
  }
  for (const photo of items) {
    if (photo.event) {
      groupByEventId.get(photo.event.id)?.photos.push(photo)
    }
  }
  return days
}
