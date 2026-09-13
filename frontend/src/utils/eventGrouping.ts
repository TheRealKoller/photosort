import type { PhotoOut } from '../api/types'
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
