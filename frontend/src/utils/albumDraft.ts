import type { AlbumDraftOut, EventOut, PhotoOut, RatingStatus } from '../api/types'
import type { AlbumState } from './albumStateLabels'
import type { MotifSet } from './motifLabels'
import { formatMotifKey } from './motifLabels'
import { ownRatingStatus } from './ownRating'

/**
 * Reine Ableitungen des Album-Entwurfs - getrennt von der Ansicht, damit sie ohne Router,
 * QueryClient und Rendering prüfbar sind.
 */

/** Wo ein Foto im Entwurf steht: im Album, in der Gestrichen-Zeile oder gar nicht. */
export type DraftMembership = 'album' | 'struck' | 'out'

/**
 * DIE EINE Stelle, die das Serverprädikat des Entwurfs-Lesepfads nachbildet
 * (`api/photos.py::_draft_photo_ids`): `Vorschlag ∪ eigene album_worthy ∪ (eigene rejected ∩
 * Rangzeile)`, im Album genau dann, wenn der eigene Status nicht `rejected` ist.
 *
 * Sie entscheidet nach jedem Handgriff, ob ein Foto im Cache bleibt; liefe sie vom Server weg,
 * zeigte die Seite nach einem Handgriff etwas anderes als nach dem Neuladen. Gegen dieselbe
 * Falltabelle geprüft wie der Server (`backend/tests/data/album_draft_membership.json`).
 *
 * `ownStatus` kommt ausschließlich über `ownRating.ts::ownRatingStatus` (S10), „vorgeschlagen"
 * ausschließlich über `ranking.proposed`.
 */
export function draftMembership(photo: PhotoOut, ownStatus: RatingStatus | null): DraftMembership {
  if (ownStatus === 'rejected') {
    return photo.ranking ? 'struck' : 'out'
  }
  if (ownStatus === 'album_worthy' || photo.ranking?.proposed === true) {
    return 'album'
  }
  return 'out'
}

/**
 * Der Zustand eines Fotos der Antwortmenge in den Wörtern von `albumStateLabels.ts`: eigenes
 * `album_worthy` ist „Aufgenommen" (auch an einem vorgeschlagenen Foto), eigenes `rejected`
 * „Gestrichen", sonst trägt der Vorschlag das Foto.
 */
export function albumState(ownStatus: RatingStatus | null): AlbumState {
  if (ownStatus === 'album_worthy') {
    return 'taken'
  }
  return ownStatus === 'rejected' ? 'struck' : 'proposal'
}

/** n, a und g der Akzeptanzkriterien - aus dem Zustand abgeleitet, nie aus gezählten Handgriffen. */
export interface DraftCounts {
  /** Fotos im Album. */
  inAlbum: number
  /** Eigene Aufnahmen im Album. */
  taken: number
  /** Eigene Streichungen mit Rangzeile. */
  struck: number
}

export function draftCounts(items: PhotoOut[], username: string | null): DraftCounts {
  const counts: DraftCounts = { inAlbum: 0, taken: 0, struck: 0 }
  for (const item of items) {
    const ownStatus = ownRatingStatus(item.ratings, username)
    const membership = draftMembership(item, ownStatus)
    if (membership === 'album') {
      counts.inAlbum += 1
      if (ownStatus === 'album_worthy') {
        counts.taken += 1
      }
    } else if (membership === 'struck') {
      counts.struck += 1
    }
  }
  return counts
}

/**
 * Was „Wieder aufnehmen" aus der Gestrichen-Zeile schreibt: Trägt der Vorschlag das Foto, wird die
 * eigene Entscheidung entfernt (zurück zum Vorschlag, `null` → `DELETE`), sonst wird es
 * aufgenommen.
 */
export function reAddDecision(photo: PhotoOut): RatingStatus | null {
  return photo.ranking?.proposed === true ? null : 'album_worthy'
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

/**
 * Nimmt ein Foto in eine bereits geladene Entwurfsliste auf — rein, ohne Cache und ohne Netz.
 *
 * DERSELBE SORTIERSCHLÜSSEL WIE DER SERVER (`(events.position, taken_at, photo_id)`): Nach einem
 * Tausch oder Hinzufügen steht das Bild damit dort, wo es auch nach dem nächsten vollständigen
 * Laden stünde. Ans Ende der Liste gehängt läge es in der falschen Eventgruppe.
 *
 * Zwei Fälle lassen die Liste UNVERÄNDERT (dieselbe Objektreferenz): das Foto steht bereits darin
 * — ein zweites Vorkommen wäre eine Kachel, die zweimal dasteht —, und ein Foto ohne Event, das
 * `eventGrouping.ts::groupEventsByDay` ohnehin keinem Abschnitt zuordnete.
 *
 * Unberührte Fotos behalten ihre OBJEKTREFERENZ (wie `applyWrittenRating`).
 */
export function insertDraftPhoto(list: AlbumDraftOut, photo: PhotoOut): AlbumDraftOut {
  const insertedEvent = photo.event
  if (!insertedEvent || list.items.some((item) => item.id === photo.id)) {
    return list
  }
  const key = (candidate: PhotoOut, candidateEvent: EventOut) =>
    [candidateEvent.position, candidate.taken_at, candidate.id] as const
  const insertedKey = key(photo, insertedEvent)
  const index = list.items.findIndex((item) => {
    const itemEvent = item.event
    if (!itemEvent) {
      return false
    }
    const itemKey = key(item, itemEvent)
    // Elementweiser Vergleich statt `localeCompare` über einen zusammengesetzten String: die drei
    // Glieder haben verschiedene Typen, und eine Verkettung machte aus `10` ein Zeichen vor `9`.
    for (let position = 0; position < itemKey.length; position += 1) {
      if (itemKey[position] !== insertedKey[position]) {
        return itemKey[position] > insertedKey[position]
      }
    }
    return false
  })
  const items = [...list.items]
  items.splice(index === -1 ? items.length : index, 0, photo)
  return { ...list, items }
}

/**
 * Der Kopftext: Fotos im Album, Richtwert und die eigenen Eingriffe.
 *
 * In beiden Abweichungsrichtungen derselbe Satzbau: Der Richtwert ist ein Ziel und keine
 * Obergrenze, eine Abweichung ist ein neutraler Hinweis. Ein zweiter Ton („zu wenig", „zu viel")
 * machte daraus einen Zustand, der behoben werden müsste - es gibt hier nichts zu beheben.
 */
export function draftSizeText(counts: DraftCounts, target: number): string {
  return `${counts.inAlbum} im Album · Richtwert etwa ${target} · ${counts.taken} aufgenommen · ${counts.struck} gestrichen`
}

/**
 * Die neutrale Zeile „kleinerer Vorschlag" - `null` heißt „keine Zeile".
 *
 * Sie erscheint nur, wenn der Vorschlagsanteil unter dem Richtwert liegt UND die auswahlfähigen
 * Kandidaten erschöpft sind. „Unter dem Richtwert" allein reichte nicht: Ein Bestandsvorschlag,
 * der noch nach der alten Vorbelegung (ein Zehntel der Bilderzahl) gerechnet wurde, ist klein,
 * obwohl genug Fotos da sind - die Zeile nennte dann eine falsche Ursache.
 *
 * „Erschöpft" entsteht aus den vorhandenen Zählungen, ohne eigenes API-Feld: `partition_size` ist
 * die Zahl bewerteter Kandidaten je Event. Jedes Event mit Kandidaten hat mindestens einen Platz
 * im Vorschlag (Abdeckung zuerst) und steht damit mit seiner Rangzeile in der Antwort - auch ein
 * gestrichenes Foto bleibt dort. Die Summe über die Events der Antwort ist also die
 * Kandidatenzahl des Laufs. Ein als Dokument ausgeschlossenes Foto zählt darin mit, ist aber nicht
 * auswahlfähig; die Ausfallrichtung ist dann „keine Zeile", nie eine falsche Behauptung.
 */
export function smallerProposalText(items: PhotoOut[], target: number): string | null {
  let proposed = 0
  const candidatesByEvent = new Map<number, number>()
  for (const item of items) {
    const ranking = item.ranking
    if (!ranking) {
      continue
    }
    if (ranking.proposed) {
      proposed += 1
    }
    candidatesByEvent.set(ranking.event_id, ranking.partition_size)
  }
  let candidates = 0
  for (const size of candidatesByEvent.values()) {
    candidates += size
  }
  if (proposed === 0 || proposed >= target || proposed < candidates) {
    return null
  }
  return `Der Vorschlag umfasst ${proposed} Fotos statt etwa ${target} – mehr auswahlfähige Fotos gibt dieses Projekt nicht her.`
}

/** Die drei Sätze des Abschlusses „Stand des Entwurfs" - dieselben Zahlen wie der Kopf. */
export function draftClosingTexts(counts: DraftCounts, target: number): [string, string, string] {
  return [
    `${counts.inAlbum} Fotos im Album, Richtwert etwa ${target}.`,
    counts.taken === 0 && counts.struck === 0
      ? 'Keine Eingriffe – der Vorschlag gilt unverändert.'
      : `Deine Eingriffe: ${counts.taken} aufgenommen, ${counts.struck} gestrichen.`,
    'Nichts muss bestätigt werden; du kannst jederzeit weiterarbeiten.',
  ]
}

/** „{T} Tage · {E} Events" aus der Eventliste des Laufs. */
export function draftOverviewText(dayCount: number, eventCount: number): string {
  return `${dayCount} Tage · ${eventCount} Events`
}

/** „1 Bild" / „N Bilder" - die Anzahl der Bilder eines Events im Entwurf. */
export function formatDraftPhotoCount(count: number): string {
  return `${count} ${count === 1 ? 'Bild' : 'Bilder'}`
}

/** Kein Bild des Events hat je einen Klassifizierungslauf gesehen. */
export const DRAFT_MOTIFS_UNASSESSED_TEXT = 'Motive noch nicht bestimmt'

/**
 * Klassifiziert, aber kein Motiv getragen. Bewusst ein ANDERER Text als
 * `DRAFT_MOTIFS_UNASSESSED_TEXT`: „nicht angesehen" und „nichts erkannt" sind zwei Zustände, und
 * ein Text für beide verwischte sie.
 */
export const DRAFT_MOTIFS_NONE_TEXT = 'Keine Motive erkannt'

/**
 * Die Motivmischung EINER Eventgruppe — die Namen der Motive, die die Bilder dieser Gruppe im
 * Album tragen. `null` heißt „keine Zeile".
 *
 * DIE GRENZE WIRD NICHT GELESEN: Ob ein Bild ein Motiv trägt, sagt ausschließlich
 * `MotifStrengthOut.present`. `strength` fließt hier nirgends ein — ein Vergleich an dieser Stelle
 * wäre die zweite Stelle, an der über Zugehörigkeit entschieden wird, und liefe bei der nächsten
 * Kalibrierung still auseinander. Ebenso wenig erscheint eine Zahl: keine Stärke, keine Anzahl,
 * keine Reihung nach Stärke.
 *
 * GESTRICHENE BILDER ZÄHLEN NICHT MIT: Sie stehen in der Antwortmenge, gehören aber nicht zum
 * Album. Mit dem letzten Bild eines Motivs verschwindet das Motiv aus der Zeile - ohne Neuladen,
 * weil die Zeile aus den bereits geladenen Fotos entsteht.
 *
 * Vier Fälle in dieser Reihenfolge: kein Bild im Album → `null`; Bilder im Album, aber keines mit
 * Kopfzeile → `DRAFT_MOTIFS_UNASSESSED_TEXT`; Kopfzeile vorhanden, kein `present` →
 * `DRAFT_MOTIFS_NONE_TEXT`; sonst die Namensliste, alphabetisch nach Anzeigename.
 */
export function draftMotifText(
  photos: PhotoOut[],
  username: string | null,
  motifs: MotifSet,
): string | null {
  const inAlbum = photos.filter(
    (photo) => draftMembership(photo, ownRatingStatus(photo.ratings, username)) === 'album',
  )
  if (inAlbum.length === 0) {
    return null
  }
  // Die LEERE Motivliste ist die Aussage „noch nicht klassifiziert" - der Server liefert ohne
  // Kopfzeile ausdrücklich keine acht Nullzeilen.
  if (!inAlbum.some((photo) => photo.motifs !== undefined && photo.motifs.length > 0)) {
    return DRAFT_MOTIFS_UNASSESSED_TEXT
  }
  const names = new Set<string>()
  for (const photo of inAlbum) {
    for (const motif of photo.motifs ?? []) {
      if (motif.present) {
        names.add(formatMotifKey(motif.key, motifs))
      }
    }
  }
  if (names.size === 0) {
    return DRAFT_MOTIFS_NONE_TEXT
  }
  return [...names].sort((left, right) => left.localeCompare(right, 'de')).join(', ')
}
