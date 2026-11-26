/** Der leere Bestand - dauerhaft sichtbar statt als fluechtiger Hinweis. Er deckt beide
 * Faelle ab, in denen nichts zu sichten ist: Der Lauf hat keinen Ausschuss gefunden, oder es gibt
 * noch gar keinen erfolgreichen Lauf mit Vorschlaegen. */
export const AUSSCHUSS_EMPTY_TEXT = 'Kein Ausschuss gefunden — es gibt derzeit nichts zu sichten.'

/** Der benannte Zustand der Detailansicht, wenn die Aufnahme nicht (mehr) im Bestand liegt: Die
 * Antwort des `photo_id`-Filters ist leer, weil ein neuer Lauf die Entscheidung aufgeloest hat -
 * kein Fehler, sondern ein definierter Zustand mit Rueckweg. */
/** Der eigene Leertext der gefilterten Ansicht: Der allgemeine Leertext erscheint
 * dann NICHT zusätzlich — zwei getrennte Leerzustände, nie zugleich. */
export const AUSSCHUSS_AUTO_EMPTY_TEXT = 'Keine automatisch entschiedenen Gruppen.'

/** Der Rückweg aus der gefilterten Ansicht steht an derselben Stelle wie sonst der Zähler und
 * hängt an der ADRESSE, nicht an der Antwort — er ist auch beim Laden und im Fehler bedienbar. */
export const AUSSCHUSS_AUTO_FILTER_TEXT = 'Nur automatisch entschiedene Gruppen'

export const AUSSCHUSS_MISSING_ENTRY_TEXT =
  'Diese Aufnahme gehört nicht mehr zum Ausschuss. Möglicherweise hat ein neuer Lauf sie aufgelöst.'
