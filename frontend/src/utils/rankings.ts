import type { PhotoOut, RankingOut } from '../api/types'

/**
 * Die Rangzeile eines Fotos, WENN sie zur angeforderten Kuratierungsauswahl gehoert - sonst
 * `null`. Ohne angeforderte Auswahl ist das Ergebnis immer `null`.
 *
 * Bewusst ein eigenes, getestetes Modul und kein Inline-Ausdruck in den Seiten: die naheliegende
 * Abkuerzung ist falsch. Geprueft wird auf `!== null` und nicht auf Falsyness - `0` waere zwar
 * keine gueltige Position (sie ist 1-basiert), aber ein Falsyness-Filter verliert sie
 * stillschweigend, und genau diese Klasse Fehler faellt in keiner Ansicht auf.
 */
export function curatedRanking(photo: PhotoOut): RankingOut | null {
  const ranking = photo.ranking
  if (!ranking || ranking.curation_position === null) {
    return null
  }
  return ranking
}
