import type {
  AlbumDecisionOut,
  AlbumParticipantOut,
  AlbumSelectionOut,
  PhotoOut,
} from '../api/types'

/**
 * Reine Ableitungen der gemeinsamen Endauswahl - getrennt von der Ansicht, damit sie ohne Router,
 * QueryClient und Rendering prüfbar sind.
 *
 * DIE REGEL SELBST STEHT NICHT HIER. Ob ein Bild zur Endauswahl gehört und ob es strittig ist,
 * sagt der Server (`backend album_selection.py::selection_state`) über `in_final_selection` und
 * `contested`; `utils/albumDraft.ts::isInAlbum` wird auf diesem Weg ausdrücklich NICHT benutzt -
 * seine Aussage (`status !== 'rejected'`) gilt nur innerhalb der Antwortmenge des Entwurfszweigs,
 * und die Endauswahl enthält auch Fotos, die in keinem der beiden Entwürfe stehen.
 *
 * `applyAlbumDecision` unten ist der EINZIGE lokal ausgewertete Teil der Regel, und er ist exakt:
 * Eine Entscheidung überschreibt immer, der Konsenszweig wird hier nie betreten.
 */

/** Die Haltung EINES Teilnehmers zu einem Bild. */
export type ParticipantStance = 'taken' | 'struck' | 'untouched'

/**
 * Wie steht dieser Teilnehmer zu diesem Bild?
 *
 * DIE ZUORDNUNG LÄUFT ÜBER `user_id`, NIE ÜBER POSITION ODER `some()`. Die Reihenfolge von
 * `ratings[]` ist keine Zusage des Servers und stimmt nicht mit der von `participants` überein;
 * ein `ratings[0]` oder ein `ratings.some(...)` stellte die Haltung des einen als die des anderen
 * dar - genau das, was diese Ansicht ausschließt. Auch der `username` taugt nicht als Schlüssel:
 * er ist fremdbestimmter Text, `user_id` ist die Identität.
 *
 * GELESEN WIRD `status`, NICHT DAS VORHANDENSEIN DER ZEILE: Seit ADR 0098 kann eine Zeile allein
 * das Favoriten-Kennzeichen tragen, und das ist keine Albumentscheidung.
 */
export function participantStance(
  photo: PhotoOut,
  participant: AlbumParticipantOut,
): ParticipantStance {
  const rating = photo.ratings.find((entry) => entry.user_id === participant.user_id)
  if (rating?.status === 'album_worthy') {
    return 'taken'
  }
  if (rating?.status === 'rejected') {
    return 'struck'
  }
  return 'untouched'
}

/**
 * Schreibt eine gerade getroffene gemeinsame Entscheidung in eine bereits geladene Endauswahl
 * fort - rein, ohne Cache und ohne Netz.
 *
 * ALLE DREI FELDER GEMEINSAM, und alle drei aus der SERVERANTWORT (Auflage S5): Nach einer
 * Entscheidung sind die beiden abgeleiteten Werte trivial bestimmt - `contested` ist `false`, und
 * `in_final_selection` ist die Entscheidung selbst. Der lokal beabsichtigte Wert wird nirgends
 * gelesen; nach einem verlorenen Wettlauf zeigte er dauerhaft eine Zugehörigkeit an, die so nicht
 * gespeichert ist.
 *
 * DIE REIHENFOLGE BLEIBT, und unbeteiligte Fotos behalten ihre OBJEKTREFERENZ (wie
 * `applyWrittenRating`): Das entschiedene Bild verlässt die Arbeitssicht sofort, ohne dass sich
 * die Ergebnissicht dabei umordnet.
 */
export function applyAlbumDecision(
  selection: AlbumSelectionOut,
  written: AlbumDecisionOut,
): AlbumSelectionOut {
  return {
    ...selection,
    items: selection.items.map((item) =>
      item.id === written.photo_id
        ? {
            ...item,
            final_selection_decision: written.included,
            in_final_selection: written.included,
            contested: false,
          }
        : item,
    ),
  }
}

/** Die Beschriftungen des Umschalters - der sichtbare Text UND der zugängliche Name. */
export const SELECTION_VIEW_LABELS = {
  /** Die Arbeitssicht: nur die Bilder, über die die beiden uneins sind. */
  contested: 'Unterschiede',
  /** Die Ergebnissicht: die ganze Endauswahl, chronologisch nach Event. */
  all: 'Endauswahl',
} as const

/**
 * Leerzustand B - die Arbeitssicht hat nichts mehr abzuarbeiten.
 *
 * GETRENNT VON `DRAFT_EMPTY_TEXT` und nie mit ihm zusammengefasst: Die beiden Leerzustände
 * verlangen verschiedene Handlungen - einmal einen Lauf starten, einmal nichts tun. Ein Text für
 * beide schickte den Nutzer in die Pipeline, obwohl dort nichts zu tun ist.
 */
export const SELECTION_NOTHING_CONTESTED_TEXT =
  'Keine Unterschiede offen — hier ist gerade nichts zu tun. Die ganze Auswahl steht unter ' +
  '„Endauswahl".'
