/** "1 Foto" bzw. "{n} Fotos" - die eine Zählform der Personenübersicht. Gezählt werden dort nur
 * Fotos, nie Gesichter. */
export function photoCount(count: number): string {
  return count === 1 ? '1 Foto' : `${count} Fotos`
}

/** Der Basisname eines Fotopfads - sichtbar wird in den Karten nur er. */
export function baseName(path: string): string {
  return path.split('/').pop() ?? path
}

/** Die Zeilenkarte beider Gruppen der Übersicht: Liste und Karte. */
export const ROW_CARD_LIST_CLASSES = 'grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3'
export const ROW_CARD_CLASSES =
  'flex items-start gap-3 rounded-lg border border-border bg-elevated p-2'
