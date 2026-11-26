/**
 * Der erste Hinweis: Antippen speichert sofort, und es gilt der ANGEZEIGTE Zustand.
 *
 * „Bleibt erhalten" hängt am angezeigten „Behalten" — nie an „nicht angetippt" oder
 * „unentschieden": Ein unentschiedener Duplikat-Verlierer zeigt bereits „Ausschuss" und scheidet
 * ohne weiteres Zutun aus. Eine Zusage über nicht Angetipptes wäre eine, die die Ansicht nicht
 * halten kann.
 */
export const DUPLICATE_HINT_TEXT =
  'Antippen von „Behalten“ oder „Ausschuss“ wird sofort gespeichert. Es gilt der angezeigte ' +
  'Zustand: Was „Behalten“ zeigt, bleibt erhalten; nur was „Ausschuss“ zeigt, scheidet aus der ' +
  'weiteren Bearbeitung aus.'

/**
 * Die Folge von „behalten", an der Handlung selbst.
 *
 * „Behalten" ist keine ansichtsinterne Buchführung: Die Aufnahme läuft danach in die
 * Kriterien-Bewertung und, bei erteilter Einwilligung, in die Cloud-Klassifizierung. Steht das
 * nicht hier — im Raster wie in der Großansicht —, trifft der Nutzer eine Entscheidung über einen
 * Datenabfluss, von dem er nichts weiß.
 */
export const DUPLICATE_CONSEQUENCE_TEXT =
  '„Behalten" heißt: Die Aufnahme läuft in die Bewertung weiter — und, solange die ' +
  'Cloud-Freigabe dieses Projekts gesetzt ist, auch an den Cloud-Anbieter.'

/** Der leere Zustand. Er deckt alle Fälle ab, in denen es zu dieser Aufnahme keine Gruppe gibt —
 * unbekanntes Foto, fremdes Projekt, kein Duplikat, oder eine Gruppe, die ein neuer Lauf
 * aufgelöst hat. Der Server unterscheidet sie nicht, und die Ansicht kann es deshalb auch
 * nicht. */
export const DUPLICATE_EMPTY_TEXT =
  'Zu dieser Aufnahme gibt es keine Duplikat-Gruppe. Möglicherweise hat ein neuer Lauf sie ' +
  'aufgelöst.'

export const LAST_GROUP_TEXT = 'Gespeichert — das war die letzte Gruppe.'
