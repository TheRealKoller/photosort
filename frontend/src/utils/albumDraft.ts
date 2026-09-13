import type { EventOut, PhotoListOut, PhotoOut, RatingStatus } from '../api/types'
import type { MotifSet } from './motifLabels'
import { formatMotifKey } from './motifLabels'
import { ownRatingStatus } from './ownRating'

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
 * Stand dieses Bild zuvor im Album? Der Zustand hinter dem Abzeichen „zuvor im Album" im
 * Alternativen-Raster.
 *
 * Er ist die EIGENE Streichung und nichts sonst: Der Alternativen-Endpunkt liefert die Fotos des
 * Events abzüglich des eigenen Entwurfs, und darunter ist ein gestrichenes genau deshalb, weil es
 * einmal drin war. Ein nie bewertetes Foto steht dort ebenfalls — es war nie im Album und trägt
 * kein Abzeichen.
 */
export function wasInAlbum(ownStatus: RatingStatus | null): boolean {
  return ownStatus === 'rejected'
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
 * Austausch steht das neue Bild damit dort, wo es auch nach dem nächsten vollständigen Laden
 * stünde. Ans Ende der Liste gehängt läge es in der falschen Eventgruppe; direkt neben das
 * ersetzte Bild gesetzt spränge es beim nächsten Laden an eine andere Stelle.
 *
 * Zwei Fälle lassen die Liste UNVERÄNDERT (dieselbe Objektreferenz): das Foto steht bereits darin
 * — ein zweites Vorkommen wäre eine Kachel, die zweimal dasteht —, und ein Foto ohne Event, das
 * `eventGrouping.ts::groupPhotosByDay` ohnehin überginge und dessen einzige Wirkung eine falsche
 * Ist-Anzahl im Kopfbereich wäre.
 *
 * Unberührte Fotos behalten ihre OBJEKTREFERENZ (wie `applyWrittenRating`).
 */
export function insertDraftPhoto(list: PhotoListOut, photo: PhotoOut): PhotoListOut {
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
  return { ...list, items, total: items.length }
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
 * GESTRICHENE BILDER ZÄHLEN NICHT MIT. Sie bleiben in der Antwortmenge sichtbar, gehören aber
 * nicht zum Entwurf (ADR 0098 Punkt 1: `… \ Gestrichen`). Daraus folgt das sichtbare Verhalten:
 * Mit dem letzten Bild eines Motivs verschwindet das Motiv aus der Zeile — ohne Neuladen, weil die
 * Zeile aus den bereits geladenen Kacheln entsteht.
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
  const inAlbum = photos.filter((photo) => isInAlbum(ownRatingStatus(photo.ratings, username)))
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
